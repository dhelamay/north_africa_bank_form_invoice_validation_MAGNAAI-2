"""
Shared Pydantic models for requests, responses, and state.
Used by: FastMCP tools, LangGraph workflows, FastAPI endpoints.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum
from datetime import datetime


# ═══════════════════════════════════════════════════
#  EXTRACTION
# ═══════════════════════════════════════════════════

class ExtractionMethod(str, Enum):
    TEXT = "text"
    VISION = "vision"
    OCR = "ocr"


class ExtractionResult(BaseModel):
    success: bool
    extracted_data: dict[str, Any] = {}
    raw_llm_response: str = ""
    fields_found: int = 0
    fields_total: int = 0
    method_used: ExtractionMethod = ExtractionMethod.VISION
    processing_time_ms: int = 0
    error: Optional[str] = None
    # PDF preprocessing outputs (moved from frontend to backend)
    pdf_text: str = ""
    is_scanned: bool = False


# ═══════════════════════════════════════════════════
#  VALIDATION
# ═══════════════════════════════════════════════════

class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    PASS = "pass"


class ValidationCheck(BaseModel):
    rule_id: str
    rule_name: str
    severity: ValidationSeverity
    passed: bool
    message: str
    field_keys: list[str] = []
    document_types: list[str] = []
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None


class ValidationResult(BaseModel):
    success: bool
    checks: list[ValidationCheck] = []
    total_checks: int = 0
    passed_checks: int = 0
    warnings: int = 0
    errors: int = 0
    processing_time_ms: int = 0
    error: Optional[str] = None


# ═══════════════════════════════════════════════════
#  VERIFICATION (External APIs)
# ═══════════════════════════════════════════════════

class VerificationResult(BaseModel):
    verification_type: str
    verified: bool
    confidence: float = 0.0
    message: str = ""
    details: dict[str, Any] = {}
    source: str = ""
    error: Optional[str] = None


# ═══════════════════════════════════════════════════
#  CHAT
# ═══════════════════════════════════════════════════

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatResponse(BaseModel):
    message: str
    action_taken: Optional[str] = None
    language: str = "en"


# ═══════════════════════════════════════════════════
#  ALIASES (backward compat with agents)
# ═══════════════════════════════════════════════════

class ExternalVerificationRequest(BaseModel):
    """Used by ExternalAPIAgent."""
    verification_type: str
    field_value: str
    additional_context: dict[str, Any] = {}
    language: str = "en"

class ExternalVerificationResult(BaseModel):
    """Returned by ExternalAPIAgent."""
    verification_type: str = ""
    verified: bool = False
    confidence: float = 0.0
    message: str = ""
    details: dict[str, Any] = {}
    source: str = ""
    error: Optional[str] = None

# Alias for validation agent
ValidationCheckResult = ValidationCheck

class ValidationRequest(BaseModel):
    documents: dict[str, dict[str, Any]]
    language: str = "en"
    user_id: Optional[str] = None

class ExtractionRequest(BaseModel):
    pdf_bytes: bytes
    method: ExtractionMethod = ExtractionMethod.VISION
    llm_provider: str = "gemini"
    model_name: str = "gemini-2.5-flash"
    language: str = "en"
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    extracted_data: dict[str, Any] = {}
    pdf_text: str = ""
    history: list[ChatMessage] = []
    language: str = "en"
    user_id: Optional[str] = None
