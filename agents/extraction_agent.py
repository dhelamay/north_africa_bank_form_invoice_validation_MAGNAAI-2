"""
Extraction Agent — converts PDF documents into structured JSON.
MCP Tool: extract_lc_document
"""

from __future__ import annotations
import json
import logging
from typing import Any

from agents.base_agent import BaseAgent
from schemas.models import ExtractionRequest, ExtractionResult, ExtractionMethod
from schemas.lc_fields import build_extraction_json_keys, build_field_hints
from utils.llm_clients import (
    call_gemini, call_openai, call_gemini_vision, call_openai_vision,
    parse_json_response,
)
from utils.pdf_utils import extract_text_pypdf2, extract_text_ocr, pdf_to_base64_images, is_scanned_pdf
from config.constants import MAX_PDF_TEXT_FOR_LLM, MAX_VISION_PAGES

logger = logging.getLogger(__name__)


class ExtractionAgent(BaseAgent):
    name = "extraction_agent"
    description = "Extracts structured data from L/C PDF documents"

    def _register_tools(self):
        self.register_tool(
            "extract_lc_document",
            self.extract,
            "Extract all fields from an L/C PDF document into structured JSON",
        )

    def _build_prompt(self, lang: str = "en") -> str:
        """Build the extraction prompt from the schema."""
        field_hints = build_field_hints(lang)
        json_keys = json.dumps(build_extraction_json_keys(), indent=2)

        return f"""You are an expert trade-finance and Letter of Credit (L/C) document analyst.
You can read documents in English, Arabic (العربية), Spanish (Español), and Italian (Italiano).

TASK: Extract ALL information from the document into the JSON structure below.

FIELD REFERENCE (key → English label / Arabic label):
{field_hints}

CRITICAL RULES:
1. Read the ENTIRE document — every line, header, footer, stamp, annotation, in ALL languages.
2. Extract EVERY value you can find. NEVER return null if the data exists ANYWHERE.
3. Document numbers may appear as "No.", "رقم", "Ref:", "Nº", "#", or adjacent to a label.
4. Convert ALL dates to DD/MM/YYYY format.
5. For checkboxes (required documents, compliance), return "true" if mentioned/required, "false" otherwise.
6. For select fields, return the closest matching option value.
7. For amounts, include currency code + number (e.g., "USD 150,000.00").
8. Look for Arabic labels: "اسم فاتح الإعتماد" = Applicant Name, "المستفيد" = Beneficiary.
9. If a field truly cannot be found, use null.

Return ONLY a raw JSON object — NO markdown fences, NO backticks, NO explanation:

{json_keys}"""

    @BaseAgent.timed
    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        """Main extraction entry point."""
        try:
            method = request.method
            pdf_bytes = request.pdf_bytes

            # Auto-detect: if scanned, force Vision
            if method == ExtractionMethod.TEXT and is_scanned_pdf(pdf_bytes):
                logger.info("Scanned PDF detected, switching to Vision AI")
                method = ExtractionMethod.VISION

            base_prompt = self._build_prompt(request.language)

            if method == ExtractionMethod.VISION:
                raw = self._extract_vision(pdf_bytes, base_prompt, request)
            elif method == ExtractionMethod.OCR:
                raw = self._extract_ocr(pdf_bytes, base_prompt, request)
            else:
                raw = self._extract_text(pdf_bytes, base_prompt, request)

            if not raw:
                return ExtractionResult(success=False, error="LLM returned empty response")

            parsed = parse_json_response(raw)
            found = sum(1 for v in parsed.values() if v is not None)

            return ExtractionResult(
                success=True,
                extracted_data=parsed,
                raw_llm_response=raw,
                fields_found=found,
                fields_total=len(parsed),
                method_used=method,
            )

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return ExtractionResult(success=False, error=str(e))

    def _extract_vision(self, pdf_bytes: bytes, base_prompt: str, req: ExtractionRequest) -> str | None:
        """Extract using Vision AI (send PDF directly)."""
        vision_prompt = base_prompt + "\n\nThe document pages are provided as images above. Read every page carefully and extract the JSON. ONLY the JSON object."

        if req.llm_provider == "gemini":
            return call_gemini_vision(pdf_bytes, vision_prompt, model_name=req.model_name)
        else:
            images = pdf_to_base64_images(pdf_bytes, max_pages=MAX_VISION_PAGES)
            if not images:
                raise RuntimeError("Cannot convert PDF to images. Install pdf2image + poppler.")
            return call_openai_vision(images, vision_prompt, model_name=req.model_name)

    def _extract_text(self, pdf_bytes: bytes, base_prompt: str, req: ExtractionRequest) -> str | None:
        """Extract using text-based approach."""
        text = extract_text_pypdf2(pdf_bytes)
        if len(text) < 50:
            raise RuntimeError("Not enough text extracted from PDF. Try Vision AI instead.")

        prompt = base_prompt + f"\n\nDOCUMENT TEXT:\n===\n{text[:MAX_PDF_TEXT_FOR_LLM]}\n===\n\nExtract the JSON now. ONLY the JSON object."

        if req.llm_provider == "gemini":
            return call_gemini(prompt, model_name=req.model_name)
        else:
            return call_openai(prompt, model_name=req.model_name)

    def _extract_ocr(self, pdf_bytes: bytes, base_prompt: str, req: ExtractionRequest) -> str | None:
        """Extract using OCR then LLM."""
        text = extract_text_ocr(pdf_bytes)
        if not text:
            raise RuntimeError("OCR produced no text.")

        prompt = base_prompt + f"\n\nDOCUMENT TEXT (from OCR):\n===\n{text[:MAX_PDF_TEXT_FOR_LLM]}\n===\n\nExtract the JSON now. ONLY the JSON object."

        if req.llm_provider == "gemini":
            return call_gemini(prompt, model_name=req.model_name)
        else:
            return call_openai(prompt, model_name=req.model_name)
