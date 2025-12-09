"""Gemini LLM client."""

import google.generativeai as genai
from typing import Optional, Dict, Any, Union
import time
import json
import re
from app.config import settings


class GeminiClient:
    """Client for interacting with Google's Gemini API."""
    
    def __init__(self):
        genai.configure(api_key=settings.llm_api_key)
        # Prioritize models with higher quota limits (stable releases over experimental)
        # gemini-2.5-flash has much higher quotas than gemini-2.0-flash-exp
        self.model_name = "gemini-2.5-flash"  # Default to stable model with higher quotas
        try:
            # Test if model is available, prioritize stable models with higher quotas
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            # Priority order: stable models with higher quotas first
            if "models/gemini-2.5-flash" in models:
                self.model_name = "gemini-2.5-flash"
            elif "models/gemini-2.5-flash-image" in models:
                self.model_name = "gemini-2.5-flash-image"  # Even higher quotas
            elif "models/gemini-2.5-pro" in models:
                self.model_name = "gemini-2.5-pro"
            elif "models/gemini-flash-latest" in models:
                self.model_name = "gemini-flash-latest"
            elif "models/gemini-pro-latest" in models:
                self.model_name = "gemini-pro-latest"
            elif "models/gemini-2.0-flash-exp" in models:
                self.model_name = "gemini-2.0-flash-exp"  # Last resort - lower quotas
        except Exception:
            # Use default if listing fails
            pass
        
        self.model = genai.GenerativeModel(self.model_name)
        print(f"✅ Using Gemini model: {self.model_name}")
    
    def llm_chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: str = "text",
        temperature: float = 0.7,
        max_retries: int = 3
    ) -> Union[str, Dict[str, Any]]:
        """
        Unified LLM chat interface - single source of truth for all LLM calls.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            response_format: "text" for plain text, "JSON" for structured JSON output
            temperature: Temperature for generation (0.0-1.0)
            max_retries: Maximum number of retry attempts for rate limit errors
        
        Returns:
            Generated text (str) if response_format="text", or parsed JSON (dict) if response_format="JSON"
        """
        # Build format instruction for JSON responses
        format_instruction = ""
        if response_format == "JSON":
            format_instruction = "\n\nRespond ONLY with valid JSON. Do not include any markdown formatting, code blocks, or explanatory text."
        
        # Combine prompt with format instruction
        full_prompt = f"{prompt}{format_instruction}"
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{full_prompt}"
        
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(
                    full_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=temperature
                    )
                )
                
                text = response.text.strip()
                
                # Handle JSON response format
                if response_format == "JSON":
                    # Remove markdown code blocks if present
                    if text.startswith("```json"):
                        text = text[7:]
                    if text.startswith("```"):
                        text = text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()
                    
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        # If JSON parsing fails, try to extract JSON from the response
                        try:
                            json_match = re.search(r'\{.*\}', text, re.DOTALL)
                            if json_match:
                                return json.loads(json_match.group())
                        except:
                            pass
                        raise Exception(f"Failed to parse JSON response: {text[:200]}")
                else:
                    # Return plain text
                    return text
                    
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a rate limit error (429)
                if "429" in error_str or "quota" in error_str.lower() or "rate limit" in error_str.lower():
                    if attempt < max_retries - 1:
                        # Extract retry delay from error if available, otherwise use exponential backoff
                        retry_delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        
                        # Try to extract retry_delay from error message
                        if "retry_delay" in error_str:
                            try:
                                delay_match = re.search(r'seconds:\s*(\d+)', error_str)
                                if delay_match:
                                    retry_delay = int(delay_match.group(1))
                            except:
                                pass
                        
                        print(f"⚠️ Rate limit exceeded. Retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        continue
                    else:
                        raise Exception(
                            f"Rate limit exceeded after {max_retries} attempts. "
                            f"Please wait a few minutes and try again. "
                            f"Consider using gemini-2.5-flash for higher quota limits."
                        )
                else:
                    # Non-rate-limit error, raise immediately
                    format_type = "structured" if response_format == "JSON" else "text"
                    raise Exception(f"Error generating {format_type} response from Gemini: {error_str}")
        
        format_type = "structured" if response_format == "JSON" else "text"
        raise Exception(f"Failed to generate {format_type} response after {max_retries} attempts")
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 3
    ) -> str:
        """
        Generate text using Gemini with retry logic for rate limits.
        DEPRECATED: Use llm_chat() instead.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Temperature for generation (0.0-1.0)
            max_retries: Maximum number of retry attempts for rate limit errors
        
        Returns:
            Generated text
        """
        return self.llm_chat(
            prompt=prompt,
            system_prompt=system_prompt,
            response_format="text",
            temperature=temperature,
            max_retries=max_retries
        )
    
    def generate_structured(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: str = "JSON",
        temperature: float = 0.3,
        max_retries: int = 3
    ) -> Any:
        """
        Generate structured output (JSON) using Gemini with retry logic.
        DEPRECATED: Use llm_chat() instead.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            response_format: Expected format (default: "JSON")
            temperature: Temperature for generation
            max_retries: Maximum number of retry attempts for rate limit errors
        
        Returns:
            Parsed JSON response or dict
        """
        return self.llm_chat(
            prompt=prompt,
            system_prompt=system_prompt,
            response_format=response_format,
            temperature=temperature,
            max_retries=max_retries
        )

