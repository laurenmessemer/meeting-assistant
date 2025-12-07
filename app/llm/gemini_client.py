"""Gemini LLM client wrapper (backward compatibility).

This module provides backward compatibility by importing from llm_client.
The LLMClient supports multiple providers including Gemini and OpenRouter.
"""

# Import from the generic LLM client for backward compatibility
from app.llm.llm_client import LLMClient

# Alias for backward compatibility
GeminiClient = LLMClient

