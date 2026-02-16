"""
Database module — PostgreSQL via SQLAlchemy.

Tables:
  - lc_applications: Stores L/C form data
  - documents: Stores uploaded PDF metadata + extracted data
  - validation_runs: Stores validation results
  - audit_log: Tracks all user actions

Usage:
  from utils.database import get_db, init_db
  init_db()                        # Create tables
  db = get_db()
  db.save_application(data)
"""

from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    create_engine, Column, String, Text, DateTime, Boolean,
    Integer, Float, JSON, ForeignKey, Index, event,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from sqlalchemy.sql import func

from config.settings import get_settings

logger = logging.getLogger(__name__)

Base = declarative_base()


# ══════════════════════════════════════════════════════════════════════════════
#  MODELS
# ══════════════════════════════════════════════════════════════════════════════

class LCApplication(Base):
    """Stores a complete L/C application with all form fields."""
    __tablename__ = "lc_applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lc_number = Column(String(100), index=True, nullable=True)
    status = Column(String(50), default="draft")         # draft, submitted, approved, rejected
    language = Column(String(10), default="en")

    # All extracted/edited form data as JSON
    form_data = Column(JSON, nullable=False, default=dict)

    # Metadata
    user_id = Column(String(100), index=True, nullable=True)
    tenant_id = Column(String(100), index=True, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    documents = relationship("Document", back_populates="application", cascade="all, delete-orphan")
    validation_runs = relationship("ValidationRun", back_populates="application", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LCApplication id={self.id} lc={self.lc_number} status={self.status}>"


class Document(Base):
    """Stores uploaded PDF documents and their extraction results."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("lc_applications.id"), nullable=True, index=True)
    filename = Column(String(500), nullable=False)
    document_type = Column(String(100), nullable=True)   # letter_of_credit, invoice, bill_of_lading, etc.
    file_size = Column(Integer, nullable=True)
    page_count = Column(Integer, nullable=True)
    is_scanned = Column(Boolean, default=False)

    # Extraction results
    extracted_data = Column(JSON, nullable=True)
    extraction_method = Column(String(50), nullable=True)  # vision, text, ocr
    extraction_model = Column(String(100), nullable=True)   # gemini-2.5-flash, gpt-4o
    raw_llm_response = Column(Text, nullable=True)
    fields_found = Column(Integer, default=0)
    fields_total = Column(Integer, default=0)
    extraction_time_ms = Column(Integer, nullable=True)

    # PDF bytes stored externally (path reference) — not in DB for large files
    file_path = Column(String(1000), nullable=True)

    # Metadata
    user_id = Column(String(100), nullable=True)
    tenant_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    application = relationship("LCApplication", back_populates="documents")

    def __repr__(self):
        return f"<Document id={self.id} file={self.filename} type={self.document_type}>"


class ValidationRun(Base):
    """Stores validation run results."""
    __tablename__ = "validation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("lc_applications.id"), nullable=True, index=True)

    total_checks = Column(Integer, default=0)
    passed_checks = Column(Integer, default=0)
    warnings = Column(Integer, default=0)
    errors = Column(Integer, default=0)

    # Full results as JSON
    checks_detail = Column(JSON, nullable=True)
    external_verifications = Column(JSON, nullable=True)

    # Metadata
    user_id = Column(String(100), nullable=True)
    tenant_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    application = relationship("LCApplication", back_populates="validation_runs")


class AuditLog(Base):
    """Audit trail for all user actions."""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), index=True, nullable=True)
    tenant_id = Column(String(100), index=True, nullable=True)
    action = Column(String(100), nullable=False)           # upload, extract, validate, export, edit, chat
    target_type = Column(String(100), nullable=True)       # application, document
    target_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_audit_log_action_date", "action", "created_at"),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  ENGINE & SESSION
# ══════════════════════════════════════════════════════════════════════════════

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url_sync,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,        # Auto-reconnect stale connections
            echo=settings.app_log_level == "DEBUG",
        )
    return _engine


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)
    return _SessionLocal


def get_session() -> Session:
    """Get a new database session. Caller must close it."""
    return _get_session_factory()()


# ══════════════════════════════════════════════════════════════════════════════
#  INIT & MIGRATIONS
# ══════════════════════════════════════════════════════════════════════════════

def init_db():
    """Create all tables if they don't exist."""
    engine = _get_engine()
    Base.metadata.create_all(engine)
    logger.info("Database tables created/verified.")


def drop_db():
    """Drop all tables. USE WITH CAUTION."""
    engine = _get_engine()
    Base.metadata.drop_all(engine)
    logger.info("All database tables dropped.")


# ══════════════════════════════════════════════════════════════════════════════
#  HIGH-LEVEL DATABASE OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

class DatabaseService:
    """High-level database operations used by agents and frontend."""

    # ── Applications ──────────────────────────────────────────────────────

    def save_application(self, form_data: dict, user_id: str = None,
                         tenant_id: str = None, language: str = "en") -> int:
        """Save or create an L/C application. Returns application ID."""
        session = get_session()
        try:
            app = LCApplication(
                lc_number=form_data.get("lc_number"),
                form_data=form_data,
                user_id=user_id,
                tenant_id=tenant_id,
                language=language,
            )
            session.add(app)
            session.commit()
            app_id = app.id
            logger.info(f"Saved application {app_id}")
            return app_id
        finally:
            session.close()

    def update_application(self, app_id: int, form_data: dict) -> bool:
        """Update an existing application's form data."""
        session = get_session()
        try:
            app = session.query(LCApplication).get(app_id)
            if not app:
                return False
            app.form_data = form_data
            app.lc_number = form_data.get("lc_number")
            session.commit()
            return True
        finally:
            session.close()

    def get_application(self, app_id: int) -> Optional[dict]:
        """Get application by ID."""
        session = get_session()
        try:
            app = session.query(LCApplication).get(app_id)
            if not app:
                return None
            return {
                "id": app.id,
                "lc_number": app.lc_number,
                "status": app.status,
                "form_data": app.form_data,
                "language": app.language,
                "created_at": str(app.created_at),
                "updated_at": str(app.updated_at),
            }
        finally:
            session.close()

    def list_applications(self, user_id: str = None, tenant_id: str = None,
                          limit: int = 50) -> list[dict]:
        """List applications, optionally filtered by user/tenant."""
        session = get_session()
        try:
            query = session.query(LCApplication).order_by(LCApplication.updated_at.desc())
            if user_id:
                query = query.filter(LCApplication.user_id == user_id)
            if tenant_id:
                query = query.filter(LCApplication.tenant_id == tenant_id)
            apps = query.limit(limit).all()
            return [
                {
                    "id": a.id,
                    "lc_number": a.lc_number,
                    "status": a.status,
                    "applicant": (a.form_data or {}).get("applicant_name", ""),
                    "amount": (a.form_data or {}).get("amount_in_figures", ""),
                    "updated_at": str(a.updated_at),
                }
                for a in apps
            ]
        finally:
            session.close()

    # ── Documents ─────────────────────────────────────────────────────────

    def save_document(self, filename: str, document_type: str,
                      extracted_data: dict, extraction_method: str = None,
                      extraction_model: str = None, raw_llm_response: str = None,
                      fields_found: int = 0, fields_total: int = 0,
                      extraction_time_ms: int = 0, application_id: int = None,
                      user_id: str = None, tenant_id: str = None) -> int:
        """Save a document extraction result. Returns document ID."""
        session = get_session()
        try:
            doc = Document(
                application_id=application_id,
                filename=filename,
                document_type=document_type,
                extracted_data=extracted_data,
                extraction_method=extraction_method,
                extraction_model=extraction_model,
                raw_llm_response=raw_llm_response,
                fields_found=fields_found,
                fields_total=fields_total,
                extraction_time_ms=extraction_time_ms,
                user_id=user_id,
                tenant_id=tenant_id,
            )
            session.add(doc)
            session.commit()
            doc_id = doc.id
            logger.info(f"Saved document {doc_id}: {filename}")
            return doc_id
        finally:
            session.close()

    # ── Validation ────────────────────────────────────────────────────────

    def save_validation_run(self, application_id: int, total_checks: int,
                            passed_checks: int, warnings: int, errors: int,
                            checks_detail: list = None,
                            external_verifications: list = None,
                            user_id: str = None, tenant_id: str = None) -> int:
        """Save a validation run result."""
        session = get_session()
        try:
            run = ValidationRun(
                application_id=application_id,
                total_checks=total_checks,
                passed_checks=passed_checks,
                warnings=warnings,
                errors=errors,
                checks_detail=checks_detail,
                external_verifications=external_verifications,
                user_id=user_id,
                tenant_id=tenant_id,
            )
            session.add(run)
            session.commit()
            return run.id
        finally:
            session.close()

    # ── Audit Log ─────────────────────────────────────────────────────────

    def log_action(self, action: str, user_id: str = None, tenant_id: str = None,
                   target_type: str = None, target_id: int = None,
                   details: dict = None):
        """Log an audit event."""
        session = get_session()
        try:
            entry = AuditLog(
                user_id=user_id,
                tenant_id=tenant_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
            )
            session.add(entry)
            session.commit()
        except Exception as e:
            logger.warning(f"Audit log failed: {e}")
            session.rollback()
        finally:
            session.close()


# ── Singleton ─────────────────────────────────────────────────────────────────
_db_service: DatabaseService | None = None


def get_db() -> DatabaseService:
    """Get the database service singleton."""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service


# ══════════════════════════════════════════════════════════════════════════════
#  NAB_DEMO DATABASE LOOKUP (ASYNC)
# ══════════════════════════════════════════════════════════════════════════════

import asyncpg

# Database configuration for NAB_DEMO
NAB_DEMO_CONFIG = {
    "host": "204.12.251.157",
    "port": 5432,
    "database": "NAB_DEMO",
    "user": "postgres",
    "password": "nasser123"
}

# Connection pool for NAB_DEMO (created on first use)
_nab_pool: Optional[asyncpg.Pool] = None


async def get_nab_pool() -> asyncpg.Pool:
    """Get or create NAB_DEMO database connection pool."""
    global _nab_pool
    if _nab_pool is None:
        _nab_pool = await asyncpg.create_pool(
            **NAB_DEMO_CONFIG,
            min_size=1,
            max_size=10,
            command_timeout=10
        )
        logger.info("Created asyncpg connection pool for NAB_DEMO")
    return _nab_pool


async def db_lookup_customer(lookup_value: str) -> Optional[dict]:
    """
    Lookup customer in NAB_DEMO.cbl table by customer_no (cst_id) or account_no (current_account_number).

    Args:
        lookup_value: Customer number or account number to search for

    Returns:
        Dictionary with customer data if found, None otherwise

    Raises:
        Exception: If database connection or query fails
    """
    if not lookup_value or not lookup_value.strip():
        return None

    pool = await get_nab_pool()

    async with pool.acquire() as conn:
        # Query all three tables: fc1240_sttm_customer, fc1240_sttm_cust_account, and cbl
        # Join customer, account, and L/C tables
        # Cast columns to text to handle both numeric and text lookups
        query = """
            SELECT
                cust.customer_no,
                cust.customer_name1,
                cust.address_line1,
                cust.address_line2,
                cust.address_line3,
                cust.address_line4,
                cust.country,
                cust.nationality,
                cust.short_name,
                acc.cust_ac_no as account_number,
                acc.ac_desc as account_description,
                acc.ccy as account_currency,
                acc.acy_curr_balance as current_balance,
                acc.acc_status as account_status,
                acc.ac_open_date as account_open_date,
                lc.cst_id,
                lc.entity_name,
                lc.lc_number,
                lc.amount as lc_amount,
                lc.currency as lc_currency,
                lc.applicant_standing,
                lc.cst_status,
                lc.current_account_number,
                lc.swift_number,
                lc.applicant_bank,
                lc.hs_code,
                lc.تاريخ_الاستحقاق as expiry_date
            FROM fc1240_sttm_customer cust
            LEFT JOIN fc1240_sttm_cust_account acc
                ON cust.customer_no = acc.cust_no
            LEFT JOIN cbl lc
                ON cust.customer_no::text = lc.cst_id::text
                OR acc.cust_ac_no = lc.current_account_number
            WHERE cust.customer_no::text = $1
               OR acc.cust_ac_no::text = $1
               OR lc.cst_id::text = $1
               OR lc.current_account_number::text = $1
            LIMIT 1
        """

        try:
            row = await conn.fetchrow(query, lookup_value.strip())

            if row is None:
                return None

            # Convert asyncpg.Record to dict
            return dict(row)

        except Exception as e:
            logger.error(f"NAB_DEMO query failed for lookup_value={lookup_value}: {e}")
            raise


async def close_nab_pool():
    """Close NAB_DEMO database connection pool (call on shutdown)."""
    global _nab_pool
    if _nab_pool is not None:
        await _nab_pool.close()
        _nab_pool = None
        logger.info("Closed NAB_DEMO connection pool")
