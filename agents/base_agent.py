"""
Base agent class — all agents inherit from this.
Provides: logging, LLM access, tool registration pattern.
"""

from __future__ import annotations
import time
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all agents in the platform."""

    name: str = "base_agent"
    description: str = "Base agent"

    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._register_tools()

    def _register_tools(self):
        """Override in subclasses to register MCP tools."""
        pass

    def register_tool(self, name: str, func: Callable, description: str = ""):
        """Register a tool function."""
        self._tools[name] = {
            "func": func,
            "description": description,
        }
        logger.info(f"[{self.name}] Registered tool: {name}")

    def get_tools(self) -> dict[str, dict]:
        """Return all registered tools for MCP server registration."""
        return self._tools

    @staticmethod
    def timed(func):
        """Decorator to measure execution time in ms."""
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            if hasattr(result, "processing_time_ms"):
                result.processing_time_ms = elapsed_ms
            logger.info(f"[{func.__qualname__}] completed in {elapsed_ms}ms")
            return result
        return wrapper
