"""
FastAPI Application — REST API for the frontend.

Endpoints mirror the LangGraph workflows:
  POST /extract      → extraction_graph
  POST /validate     → validation_graph
  POST /verify       → verification_graph
  POST /chat         → chat_graph
  POST /pipeline     → pipeline_graph (extract → validate → verify)
  GET  /tools        → list FastMCP tools
  GET  /health       → health check

All endpoints accept JSON, return JSON. The frontend (React/Next.js)
calls these endpoints. Each endpoint invokes a LangGraph graph.
"""
from __future__ import annotations
import base64
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  LIFESPAN (startup/shutdown)
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: pre-build graphs. Shutdown: cleanup."""
    from workflows.graphs import get_graph
    for name in ("extraction", "validation", "verification", "chat", "pipeline"):
        get_graph(name)
    logger.info("All LangGraph workflows compiled")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="MagnaAI L/C Platform",
    description="Letter of Credit processing — FastMCP + LangGraph",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"], allow_credentials=True)

# Mount static files (HTML/CSS/JS frontend)
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    logger.info(f"Mounted static files from {STATIC_DIR}")


# ═══════════════════════════════════════════════════════════════
#  REQUEST / RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════

class ExtractRequest(BaseModel):
    pdf_bytes_b64: str                    # Base64-encoded PDF
    method: str = "vision"                # vision | text | ocr
    llm_provider: str = "gemini"
    model_name: str = "gemini-2.5-flash"
    language: str = "en"

class ValidateRequest(BaseModel):
    documents: dict                       # {doc_type: extracted_data}
    language: str = "en"

class VerifyRequest(BaseModel):
    tool_name: str                        # e.g. "verify_swift_code"
    args: dict                            # tool arguments

class VerifyBatchRequest(BaseModel):
    fields: list                          # [{tool_name, args}, ...]

class ChatRequest(BaseModel):
    message: str
    extracted_data: dict = {}
    pdf_text: str = ""
    history: list = []
    language: str = "en"

class PipelineRequest(BaseModel):
    pdf_bytes_b64: str
    method: str = "vision"
    llm_provider: str = "gemini"
    model_name: str = "gemini-2.5-flash"
    language: str = "en"
    verify_fields: list = []              # [{tool_name, args}]

class CustomerLookupRequest(BaseModel):
    lookup_value: str                     # customer_no or account_no


# ═══════════════════════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Serve the HTML frontend."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "MagnaAI L/C Platform API", "version": "2.0.0", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "magna-ai-lc-platform", "version": "2.0.0"}


@app.get("/tools")
async def get_tools():
    """List all registered FastMCP tools."""
    from tools.server import list_tools
    return {"tools": list_tools()}


@app.post("/extract")
async def extract(req: ExtractRequest):
    """Extract L/C fields from a PDF."""
    from workflows.graphs import get_graph
    graph = get_graph("extraction")
    state = graph.invoke({
        "pdf_bytes_b64": req.pdf_bytes_b64,
        "method": req.method,
        "llm_provider": req.llm_provider,
        "model_name": req.model_name,
        "language": req.language,
    })
    if state.get("error"):
        raise HTTPException(500, detail=state["error"])
    return state.get("result", {})


@app.post("/extract/upload")
async def extract_upload(
    file: UploadFile = File(...),
    method: str = Form("vision"),
    llm_provider: str = Form("gemini"),
    model_name: str = Form("gemini-2.5-flash"),
    language: str = Form("en"),
):
    """Extract L/C fields — accepts multipart file upload."""
    pdf_bytes = await file.read()
    pdf_b64 = base64.b64encode(pdf_bytes).decode()

    from workflows.graphs import get_graph
    graph = get_graph("extraction")
    state = graph.invoke({
        "pdf_bytes_b64": pdf_b64,
        "method": method,
        "llm_provider": llm_provider,
        "model_name": model_name,
        "language": language,
    })
    if state.get("error"):
        raise HTTPException(500, detail=state["error"])
    return state.get("result", {})


@app.post("/validate")
async def validate(req: ValidateRequest):
    """Cross-validate multiple extracted documents."""
    from workflows.graphs import get_graph
    graph = get_graph("validation")
    state = graph.invoke({"documents": req.documents, "language": req.language})
    if state.get("error"):
        raise HTTPException(500, detail=state["error"])
    return state.get("result", {})


@app.post("/verify")
async def verify(req: VerifyRequest):
    """Verify a single field via external API."""
    from workflows.graphs import get_graph
    graph = get_graph("verification")
    state = graph.invoke({"tool_name": req.tool_name, "args": req.args})
    if state.get("error"):
        raise HTTPException(500, detail=state["error"])
    return state.get("result", {})


@app.post("/verify/batch")
async def verify_batch(req: VerifyBatchRequest):
    """Verify multiple fields at once."""
    from workflows.graphs import get_graph
    # Use pipeline graph's batch verify logic directly
    from tools.server import call_tool
    results = []
    errors = []
    for field in req.fields:
        try:
            r = call_tool(field["tool_name"], field["args"])
            results.append(r)
        except Exception as e:
            errors.append({"tool": field["tool_name"], "error": str(e)})
    return {"results": results, "errors": errors}


@app.post("/chat")
async def chat(req: ChatRequest):
    """Chat about an L/C document."""
    from workflows.graphs import get_graph
    graph = get_graph("chat")
    state = graph.invoke({
        "message": req.message,
        "extracted_data": req.extracted_data,
        "pdf_text": req.pdf_text,
        "history": req.history,
        "language": req.language,
    })
    if state.get("error"):
        raise HTTPException(500, detail=state["error"])
    return state.get("response", {})


@app.post("/pipeline")
async def pipeline(req: PipelineRequest):
    """Full pipeline: Extract → Validate → Verify."""
    from workflows.graphs import get_graph
    graph = get_graph("pipeline")
    state = graph.invoke({
        "pdf_bytes_b64": req.pdf_bytes_b64,
        "method": req.method,
        "llm_provider": req.llm_provider,
        "model_name": req.model_name,
        "language": req.language,
        "verify_fields": req.verify_fields,
    })
    return {
        "extraction": state.get("extraction_result"),
        "validation": state.get("validation_result"),
        "verifications": state.get("verification_results", []),
        "errors": state.get("errors", []),
    }


@app.post("/lookup_customer")
async def lookup_customer(req: CustomerLookupRequest):
    """Lookup customer in NAB_DEMO database (cbl table)."""
    from utils.database import db_lookup_customer
    try:
        result = await db_lookup_customer(req.lookup_value)
        if result is None:
            return {"success": False, "message": "No matching customer found", "data": None}
        return {"success": True, "message": "Customer found", "data": result}
    except Exception as e:
        logger.error(f"Customer lookup failed: {e}")
        raise HTTPException(500, detail=f"Database lookup failed: {str(e)}")
