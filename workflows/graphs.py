"""
LangGraph Workflows — StateGraph definitions for L/C processing.

Each workflow is a compiled LangGraph graph. Nodes call FastMCP tools
via call_tool(). State flows as a TypedDict through the graph.

Graphs:
  - extraction_graph:   PDF → Extract → END
  - validation_graph:   Docs → Validate → END
  - verification_graph: Field → Verify → END
  - pipeline_graph:     PDF → Extract → Validate → Verify batch → END
  - chat_graph:         Message → Chat → END
"""
from __future__ import annotations
import base64
import logging
from typing import TypedDict, Optional

from langgraph.graph import StateGraph, START, END
from tools.server import call_tool

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  STATE DEFINITIONS
# ═══════════════════════════════════════════════════════════════

class ExtractionState(TypedDict, total=False):
    pdf_bytes_b64: str
    method: str
    llm_provider: str
    model_name: str
    language: str
    result: dict          # ExtractionResult
    extracted_data: dict
    error: str
    # PDF preprocessing outputs (passed from backend to frontend)
    pdf_text: str
    is_scanned: bool


class ValidationState(TypedDict, total=False):
    documents: dict       # {doc_type: extracted_data}
    language: str
    result: dict          # ValidationResult
    error: str


class VerificationState(TypedDict, total=False):
    tool_name: str        # e.g. "verify_swift_code"
    args: dict            # tool arguments
    result: dict          # VerificationResult
    error: str


class BatchVerificationState(TypedDict, total=False):
    fields: list          # [{tool_name, args}, ...]
    results: list         # [VerificationResult, ...]
    errors: list


class ChatState(TypedDict, total=False):
    message: str
    extracted_data: dict
    pdf_text: str
    history: list
    language: str
    response: dict
    error: str


class PipelineState(TypedDict, total=False):
    # Input
    pdf_bytes_b64: str
    method: str
    llm_provider: str
    model_name: str
    language: str
    verify_fields: list    # [{tool_name, args}]

    # Accumulated results
    extraction_result: dict
    extracted_data: dict
    validation_result: dict
    verification_results: list
    errors: list


# ═══════════════════════════════════════════════════════════════
#  NODE FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def node_extract(state: ExtractionState) -> dict:
    """Call extract_lc_document tool."""
    try:
        result = call_tool("extract_lc_document", {
            "pdf_bytes_b64": state["pdf_bytes_b64"],
            "method": state.get("method", "vision"),
            "llm_provider": state.get("llm_provider", "gemini"),
            "model_name": state.get("model_name", "gemini-2.5-flash"),
            "language": state.get("language", "en"),
        })
        return {
            "result": result,
            "extracted_data": result.get("extracted_data", {}),
            # Pass through PDF preprocessing outputs for frontend
            "pdf_text": result.get("pdf_text", ""),
            "is_scanned": result.get("is_scanned", False),
        }
    except Exception as e:
        return {"error": str(e)}


def node_validate(state: ValidationState) -> dict:
    """Call validate_documents tool."""
    try:
        result = call_tool("validate_documents", {
            "documents": state["documents"],
            "language": state.get("language", "en"),
        })
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}


def node_verify(state: VerificationState) -> dict:
    """Call any verification tool by name."""
    try:
        result = call_tool(state["tool_name"], state["args"])
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}


def node_verify_batch(state: BatchVerificationState) -> dict:
    """Verify multiple fields sequentially (use ThreadPool externally for parallel)."""
    results = []
    errors = []
    for field in (state.get("fields") or []):
        try:
            r = call_tool(field["tool_name"], field["args"])
            results.append(r)
        except Exception as e:
            errors.append(f"{field['tool_name']}: {e}")
    return {"results": results, "errors": errors}


def node_chat(state: ChatState) -> dict:
    """Call chat_with_document tool."""
    try:
        result = call_tool("chat_with_document", {
            "message": state["message"],
            "extracted_data": state.get("extracted_data", {}),
            "pdf_text": state.get("pdf_text", ""),
            "history": state.get("history", []),
            "language": state.get("language", "en"),
        })
        return {"response": result}
    except Exception as e:
        return {"error": str(e)}


# ── Pipeline-specific nodes ──

def pipeline_extract(state: PipelineState) -> dict:
    result = call_tool("extract_lc_document", {
        "pdf_bytes_b64": state["pdf_bytes_b64"],
        "method": state.get("method", "vision"),
        "llm_provider": state.get("llm_provider", "gemini"),
        "model_name": state.get("model_name", "gemini-2.5-flash"),
        "language": state.get("language", "en"),
    })
    return {"extraction_result": result, "extracted_data": result.get("extracted_data", {})}


def pipeline_validate(state: PipelineState) -> dict:
    docs = {"letter_of_credit": state.get("extracted_data", {})}
    result = call_tool("validate_documents", {"documents": docs, "language": state.get("language", "en")})
    return {"validation_result": result}


def pipeline_should_verify(state: PipelineState) -> str:
    """Conditional: go to verify if there are fields to verify."""
    if state.get("verify_fields"):
        return "verify"
    return "end"


def pipeline_verify(state: PipelineState) -> dict:
    results = []
    errors = state.get("errors") or []
    for field in (state.get("verify_fields") or []):
        try:
            r = call_tool(field["tool_name"], field["args"])
            results.append(r)
        except Exception as e:
            errors.append(str(e))
    return {"verification_results": results, "errors": errors}


# ═══════════════════════════════════════════════════════════════
#  GRAPH BUILDERS
# ═══════════════════════════════════════════════════════════════

def build_extraction_graph():
    g = StateGraph(ExtractionState)
    g.add_node("extract", node_extract)
    g.add_edge(START, "extract")
    g.add_edge("extract", END)
    return g.compile()


def build_validation_graph():
    g = StateGraph(ValidationState)
    g.add_node("validate", node_validate)
    g.add_edge(START, "validate")
    g.add_edge("validate", END)
    return g.compile()


def build_verification_graph():
    g = StateGraph(VerificationState)
    g.add_node("verify", node_verify)
    g.add_edge(START, "verify")
    g.add_edge("verify", END)
    return g.compile()


def build_chat_graph():
    g = StateGraph(ChatState)
    g.add_node("chat", node_chat)
    g.add_edge(START, "chat")
    g.add_edge("chat", END)
    return g.compile()


def build_pipeline_graph():
    """Full pipeline: Extract → Validate → (conditionally) Verify → END."""
    g = StateGraph(PipelineState)
    g.add_node("extract", pipeline_extract)
    g.add_node("validate", pipeline_validate)
    g.add_node("verify", pipeline_verify)

    g.add_edge(START, "extract")
    g.add_edge("extract", "validate")
    g.add_conditional_edges("validate", pipeline_should_verify, {
        "verify": "verify",
        "end": END,
    })
    g.add_edge("verify", END)
    return g.compile()


# ═══════════════════════════════════════════════════════════════
#  PREBUILT GRAPH INSTANCES (lazy singletons)
# ═══════════════════════════════════════════════════════════════

_graphs = {}

def get_graph(name: str):
    """Get a compiled graph by name. Built once, reused."""
    if name not in _graphs:
        builders = {
            "extraction": build_extraction_graph,
            "validation": build_validation_graph,
            "verification": build_verification_graph,
            "chat": build_chat_graph,
            "pipeline": build_pipeline_graph,
        }
        if name not in builders:
            raise ValueError(f"Unknown graph: {name}. Available: {list(builders.keys())}")
        _graphs[name] = builders[name]()
        logger.info(f"Built LangGraph workflow: {name}")
    return _graphs[name]
