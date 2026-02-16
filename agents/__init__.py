from .base_agent import BaseAgent
from .extraction_agent import ExtractionAgent
from .validation_agent import ValidationAgent
from .external_api_agent import ExternalAPIAgent
from .chat_agent import ChatAgent

# Registry of all available agents
AGENT_REGISTRY = {
    "extraction_agent": ExtractionAgent,
    "validation_agent": ValidationAgent,
    "external_api_agent": ExternalAPIAgent,
    "chat_agent": ChatAgent,
}

__all__ = [
    "BaseAgent",
    "ExtractionAgent",
    "ValidationAgent",
    "ExternalAPIAgent",
    "ChatAgent",
    "AGENT_REGISTRY",
]
