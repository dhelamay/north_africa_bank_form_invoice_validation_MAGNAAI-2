"""
Unified LLM client wrappers for Gemini and OpenAI.
All agents use these — never call LLM APIs directly.
"""

from __future__ import annotations
import re
import json
import io
import base64
from typing import Optional, Any
from config.settings import get_settings

# ── Lazy imports (only load what's configured) ──
_gemini_client = None
_openai_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        settings = get_settings()
        if settings.has_gemini:
            from google import genai
            _gemini_client = genai.Client(api_key=settings.google_gemini_api_key)
    return _gemini_client


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        if settings.has_openai:
            from openai import OpenAI
            _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


# ══════════════════════════════════════════════════════════════════════════════
#  TEXT-ONLY CALLS
# ══════════════════════════════════════════════════════════════════════════════

def call_gemini(prompt: str, model_name: str | None = None) -> str | None:
    """Call Gemini with a text prompt."""
    client = _get_gemini_client()
    if not client:
        return None
    model = model_name or get_settings().gemini_model
    try:
        response = client.models.generate_content(model=model, contents=prompt)
        return response.text
    except Exception as e:
        raise RuntimeError(f"Gemini error: {e}") from e


def call_openai(prompt: str, model_name: str | None = None) -> str | None:
    """Call OpenAI with a text prompt."""
    client = _get_openai_client()
    if not client:
        return None
    model = model_name or get_settings().openai_model
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"OpenAI error: {e}") from e


def call_llm(prompt: str, provider: str | None = None, model_name: str | None = None) -> str | None:
    """Unified LLM call — routes to the correct provider."""
    provider = provider or get_settings().default_llm_provider
    if provider == "gemini":
        return call_gemini(prompt, model_name)
    elif provider == "openai":
        return call_openai(prompt, model_name)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


# ══════════════════════════════════════════════════════════════════════════════
#  VISION CALLS (PDF/image input)
# ══════════════════════════════════════════════════════════════════════════════

def call_gemini_vision(pdf_bytes: bytes, prompt: str, model_name: str | None = None) -> str | None:
    """Send a PDF directly to Gemini Vision."""
    client = _get_gemini_client()
    if not client:
        return None
    model = model_name or get_settings().gemini_vision_model

    try:
        from google.genai import types as genai_types
        pdf_part = genai_types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        response = client.models.generate_content(model=model, contents=[pdf_part, prompt])
        return response.text
    except Exception as e:
        raise RuntimeError(f"Gemini Vision error: {e}") from e


def call_openai_vision(images_b64: list[str], prompt: str, model_name: str | None = None) -> str | None:
    """Send images to OpenAI GPT-4o Vision."""
    client = _get_openai_client()
    if not client:
        return None
    model = model_name or get_settings().openai_model

    try:
        content = []
        for b64 in images_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })
        content.append({"type": "text", "text": prompt})

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            max_tokens=4000,
        )
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"OpenAI Vision error: {e}") from e


# ══════════════════════════════════════════════════════════════════════════════
#  RESPONSE PARSING
# ══════════════════════════════════════════════════════════════════════════════

def parse_json_response(raw_text: str) -> dict[str, Any]:
    """Parse LLM response as JSON, handling markdown fences and noise."""
    if not raw_text:
        return {}

    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
    cleaned = re.sub(r"\n?\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # Find JSON object in the response
    json_match = re.search(r"\{[\s\S]*\}", cleaned)
    if json_match:
        cleaned = json_match.group(0)

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            # Normalize null-like strings
            for k, v in data.items():
                if isinstance(v, str) and v.strip().lower() in (
                    "null", "n/a", "none", "not found", "not available", "not specified", ""
                ):
                    data[k] = None
            return data
        return {}
    except json.JSONDecodeError:
        return {}
