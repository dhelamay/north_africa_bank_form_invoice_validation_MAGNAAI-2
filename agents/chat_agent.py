"""
Chat Agent — document Q&A with ability to route to other agents.
MCP Tool: chat_with_document
"""

from __future__ import annotations
import json
import logging
from typing import Any

from agents.base_agent import BaseAgent
from schemas.models import ChatRequest, ChatResponse
from utils.llm_clients import call_llm

logger = logging.getLogger(__name__)


class ChatAgent(BaseAgent):
    name = "chat_agent"
    description = "Answers questions about L/C documents and routes complex tasks to specialized agents"

    def _register_tools(self):
        self.register_tool(
            "chat_with_document",
            self.chat,
            "Answer questions about uploaded L/C documents",
        )

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Process a chat message about the document."""
        try:
            # Detect if the user wants to trigger an action
            intent = self._detect_intent(request.message)

            if intent in ("extract", "validate", "verify"):
                return ChatResponse(
                    message=f"I'll route this to the {intent} agent.",
                    agent_used=f"{intent}_agent",
                    action_taken=intent,
                    language=request.language,
                )

            # Build context-aware prompt
            context = json.dumps(request.extracted_data, indent=2, ensure_ascii=False, default=str)
            pdf_excerpt = request.pdf_text[:8000] if request.pdf_text else ""

            # Build chat history
            history_str = ""
            for msg in request.history[-10:]:  # Last 10 messages
                history_str += f"{msg.role}: {msg.content}\n"

            lang_instruction = {
                "en": "Respond in English.",
                "ar": "أجب بالعربية. Respond in Arabic.",
                "es": "Responde en español. Respond in Spanish.",
                "it": "Rispondi in italiano. Respond in Italian.",
            }.get(request.language, "Respond in English.")

            prompt = f"""You are a helpful trade-finance document review assistant.
{lang_instruction}

Extracted L/C application data:
{context}

Raw PDF text (excerpt):
{pdf_excerpt}

Conversation history:
{history_str}

User question: {request.message}

Answer concisely and accurately based on the document data. If you cannot answer from the available data, say so."""

            response_text = call_llm(prompt)

            return ChatResponse(
                message=response_text or "Sorry, I couldn't generate a response.",
                language=request.language,
            )

        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return ChatResponse(
                message=f"An error occurred: {str(e)}",
                language=request.language,
            )

    def _detect_intent(self, message: str) -> str | None:
        """Simple intent detection from user message."""
        msg = message.lower().strip()

        extract_keywords = ["extract", "استخرج", "extraer", "estrarre", "read the pdf", "process the document"]
        validate_keywords = ["validate", "تحقق", "validar", "validare", "check consistency", "compare documents"]
        verify_keywords = ["verify hs", "check swift", "sanctions", "track shipment", "verify company",
                          "تحقق من", "verificar", "verificare"]

        for kw in extract_keywords:
            if kw in msg:
                return "extract"
        for kw in validate_keywords:
            if kw in msg:
                return "validate"
        for kw in verify_keywords:
            if kw in msg:
                return "verify"

        return None
