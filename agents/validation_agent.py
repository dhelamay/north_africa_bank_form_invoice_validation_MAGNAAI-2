"""
Validation Agent — cross-document consistency checks.
MCP Tool: validate_documents
"""

from __future__ import annotations
import logging
import re
from datetime import datetime
from typing import Any

from agents.base_agent import BaseAgent
from schemas.models import (
    ValidationRequest, ValidationResult,
    ValidationCheckResult, ValidationSeverity,
)

logger = logging.getLogger(__name__)


def _parse_date(val: Any) -> datetime | None:
    """Try to parse a date string in various formats."""
    if not val or not isinstance(val, str):
        return None
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(val.strip(), fmt)
        except ValueError:
            continue
    return None


def _parse_amount(val: Any) -> float | None:
    """Parse a currency amount string like 'USD 150,000.00' into a float."""
    if not val or not isinstance(val, str):
        return None
    cleaned = re.sub(r"[^\d.]", "", val.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


class ValidationAgent(BaseAgent):
    name = "validation_agent"
    description = "Validates consistency across multiple L/C documents"

    def _register_tools(self):
        self.register_tool(
            "validate_documents",
            self.validate,
            "Cross-validate multiple extracted documents for discrepancies",
        )

    @BaseAgent.timed
    def validate(self, request: ValidationRequest) -> ValidationResult:
        """Run all validation rules across the provided documents."""
        try:
            checks: list[ValidationCheckResult] = []
            docs = request.documents

            # Get the primary L/C document (if present)
            lc = docs.get("letter_of_credit") or docs.get("lc") or {}

            # Run all rule categories
            checks.extend(self._validate_dates(docs, lc))
            checks.extend(self._validate_amounts(docs, lc))
            checks.extend(self._validate_parties(docs, lc))
            checks.extend(self._validate_documents_required(docs, lc))
            checks.extend(self._validate_shipment(docs, lc))
            checks.extend(self._validate_numbers_consistency(docs))

            passed = sum(1 for c in checks if c.passed)
            warnings = sum(1 for c in checks if c.severity == ValidationSeverity.WARNING and not c.passed)
            errors = sum(1 for c in checks if c.severity == ValidationSeverity.ERROR and not c.passed)

            return ValidationResult(
                success=True,
                checks=checks,
                total_checks=len(checks),
                passed_checks=passed,
                warnings=warnings,
                errors=errors,
            )
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return ValidationResult(success=False, error=str(e))

    # ── Date Validation Rules ─────────────────────────────────────────────

    def _validate_dates(self, docs: dict, lc: dict) -> list[ValidationCheckResult]:
        checks = []

        # Rule: L/C expiry date must be after issue date
        issue = _parse_date(lc.get("date") or lc.get("lc_issue_date"))
        expiry = _parse_date(lc.get("expiry_date") or lc.get("lc_expiry_date"))
        if issue and expiry:
            checks.append(ValidationCheckResult(
                rule_id="DATE_001",
                rule_name="L/C expiry after issue date",
                severity=ValidationSeverity.ERROR,
                passed=expiry > issue,
                message=f"Expiry {expiry.strftime('%d/%m/%Y')} {'is after' if expiry > issue else 'is NOT after'} issue {issue.strftime('%d/%m/%Y')}",
                field_keys=["date", "expiry_date"],
            ))

        # Rule: Latest shipment date must be before L/C expiry
        shipment = _parse_date(lc.get("latest_shipment_date"))
        if shipment and expiry:
            checks.append(ValidationCheckResult(
                rule_id="DATE_002",
                rule_name="Shipment date before L/C expiry",
                severity=ValidationSeverity.ERROR,
                passed=shipment <= expiry,
                message=f"Shipment {shipment.strftime('%d/%m/%Y')} {'is before' if shipment <= expiry else 'is AFTER'} expiry {expiry.strftime('%d/%m/%Y')}",
                field_keys=["latest_shipment_date", "expiry_date"],
            ))

        # Rule: B/L on-board date must be before latest shipment date
        for doc_name, doc_data in docs.items():
            on_board = _parse_date(doc_data.get("on_board_date"))
            if on_board and shipment:
                checks.append(ValidationCheckResult(
                    rule_id="DATE_003",
                    rule_name=f"On-board date ({doc_name}) before latest shipment",
                    severity=ValidationSeverity.ERROR,
                    passed=on_board <= shipment,
                    message=f"On-board {on_board.strftime('%d/%m/%Y')} vs latest shipment {shipment.strftime('%d/%m/%Y')}",
                    field_keys=["on_board_date", "latest_shipment_date"],
                    document_types=[doc_name, "letter_of_credit"],
                ))

        return checks

    # ── Amount Validation Rules ───────────────────────────────────────────

    def _validate_amounts(self, docs: dict, lc: dict) -> list[ValidationCheckResult]:
        checks = []
        lc_amount = _parse_amount(lc.get("amount_in_figures"))
        if not lc_amount:
            return checks

        # Check invoice amounts don't exceed L/C amount
        for doc_name, doc_data in docs.items():
            if "invoice" in doc_name.lower():
                inv_amount = _parse_amount(doc_data.get("amount_in_figures") or doc_data.get("invoice_amount"))
                if inv_amount:
                    tolerance = float(lc.get("percentage_tolerance") or 0) / 100
                    max_allowed = lc_amount * (1 + tolerance)
                    checks.append(ValidationCheckResult(
                        rule_id="AMT_001",
                        rule_name=f"Invoice amount ({doc_name}) within L/C limit",
                        severity=ValidationSeverity.ERROR,
                        passed=inv_amount <= max_allowed,
                        message=f"Invoice: {inv_amount:.2f}, L/C max: {max_allowed:.2f}",
                        field_keys=["amount_in_figures"],
                        document_types=[doc_name, "letter_of_credit"],
                        expected_value=f"<= {max_allowed:.2f}",
                        actual_value=f"{inv_amount:.2f}",
                    ))

        return checks

    # ── Party Name Validation Rules ───────────────────────────────────────

    def _validate_parties(self, docs: dict, lc: dict) -> list[ValidationCheckResult]:
        checks = []
        lc_beneficiary = (lc.get("beneficiary_name") or "").strip().lower()
        lc_applicant = (lc.get("applicant_name") or "").strip().lower()

        for doc_name, doc_data in docs.items():
            if doc_name == "letter_of_credit":
                continue

            # Check beneficiary consistency
            doc_beneficiary = (doc_data.get("beneficiary_name") or doc_data.get("beneficiary") or "").strip().lower()
            if lc_beneficiary and doc_beneficiary:
                # Fuzzy match: check if one contains the other
                match = lc_beneficiary in doc_beneficiary or doc_beneficiary in lc_beneficiary
                checks.append(ValidationCheckResult(
                    rule_id="PARTY_001",
                    rule_name=f"Beneficiary name consistency ({doc_name})",
                    severity=ValidationSeverity.WARNING,
                    passed=match,
                    message=f"L/C: '{lc_beneficiary[:50]}' vs {doc_name}: '{doc_beneficiary[:50]}'",
                    field_keys=["beneficiary_name"],
                    document_types=[doc_name, "letter_of_credit"],
                ))

        return checks

    # ── Required Documents Checks ─────────────────────────────────────────

    def _validate_documents_required(self, docs: dict, lc: dict) -> list[ValidationCheckResult]:
        checks = []

        required_doc_fields = {
            "bills_of_lading": "bill_of_lading",
            "commercial_invoice": "commercial_invoice",
            "certificate_of_origin": "certificate_of_origin",
            "insurance_certificate": "insurance_certificate",
            "packing_list": "packing_list",
            "inspection_certificate": "inspection_certificate",
        }

        for lc_field, doc_type in required_doc_fields.items():
            required = str(lc.get(lc_field, "")).lower() in ("true", "yes", "1")
            if required:
                # Check if we have this document type uploaded
                has_doc = any(doc_type in name.lower() for name in docs.keys())
                checks.append(ValidationCheckResult(
                    rule_id=f"DOC_{lc_field.upper()}",
                    rule_name=f"Required document: {lc_field.replace('_', ' ').title()}",
                    severity=ValidationSeverity.WARNING,
                    passed=has_doc,
                    message=f"{'Present' if has_doc else 'MISSING'} in uploaded documents",
                    field_keys=[lc_field],
                ))

        return checks

    # ── Shipment Validation Rules ─────────────────────────────────────────

    def _validate_shipment(self, docs: dict, lc: dict) -> list[ValidationCheckResult]:
        checks = []

        lc_port_loading = (lc.get("port_loading") or "").strip().lower()
        lc_port_dest = (lc.get("port_destination") or "").strip().lower()

        for doc_name, doc_data in docs.items():
            if doc_name == "letter_of_credit":
                continue
            doc_port_loading = (doc_data.get("port_loading") or doc_data.get("port_of_loading") or "").strip().lower()
            if lc_port_loading and doc_port_loading:
                match = lc_port_loading in doc_port_loading or doc_port_loading in lc_port_loading
                checks.append(ValidationCheckResult(
                    rule_id="SHIP_001",
                    rule_name=f"Port of loading consistency ({doc_name})",
                    severity=ValidationSeverity.WARNING,
                    passed=match,
                    message=f"L/C: '{lc_port_loading}' vs {doc_name}: '{doc_port_loading}'",
                    field_keys=["port_loading"],
                    document_types=[doc_name, "letter_of_credit"],
                ))

        return checks

    # ── Cross-reference Number Consistency ────────────────────────────────

    def _validate_numbers_consistency(self, docs: dict) -> list[ValidationCheckResult]:
        checks = []

        # Collect all L/C numbers mentioned across documents
        lc_numbers = set()
        for doc_name, doc_data in docs.items():
            lc_num = (doc_data.get("lc_number") or "").strip()
            if lc_num:
                lc_numbers.add((doc_name, lc_num))

        # If we have L/C numbers from multiple documents, check consistency
        if len(lc_numbers) > 1:
            unique_nums = set(num for _, num in lc_numbers)
            consistent = len(unique_nums) == 1
            checks.append(ValidationCheckResult(
                rule_id="NUM_001",
                rule_name="L/C number consistency across documents",
                severity=ValidationSeverity.ERROR,
                passed=consistent,
                message=f"L/C numbers found: {', '.join(f'{name}={num}' for name, num in lc_numbers)}",
                field_keys=["lc_number"],
                document_types=[name for name, _ in lc_numbers],
            ))

        return checks
