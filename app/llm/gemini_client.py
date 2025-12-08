"""Gemini LLM client."""

import google.generativeai as genai
from typing import Optional, Dict, Any
from app.config import settings


class GeminiClient:
    """Client for interacting with Google's Gemini API."""
    
    def __init__(self):
        genai.configure(api_key=settings.llm_api_key)
        # Try to use the latest model, with fallbacks
        self.model_name = "gemini-2.0-flash-exp"
        try:
            # Test if model is available
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            if "models/gemini-2.0-flash-exp" in models:
                self.model_name = "gemini-2.0-flash-exp"
            elif "models/gemini-2.5-flash" in models:
                self.model_name = "gemini-2.5-flash"
            elif "models/gemini-2.5-pro" in models:
                self.model_name = "gemini-2.5-pro"
            elif "models/gemini-flash-latest" in models:
                self.model_name = "gemini-flash-latest"
            elif "models/gemini-pro-latest" in models:
                self.model_name = "gemini-pro-latest"
        except Exception:
            # Use default if listing fails
            pass
        
        self.model = genai.GenerativeModel(self.model_name)
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Generate text using Gemini.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Temperature for generation (0.0-1.0)
        
        Returns:
            Generated text
        """
        try:
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            response = self.model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature
                )
            )
            
            return response.text
        except Exception as e:
            raise Exception(f"Error generating response from Gemini: {str(e)}")
    
    def generate_structured(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: str = "JSON",
        temperature: float = 0.3
    ) -> Any:
        """
        Generate structured output (JSON) using Gemini.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            response_format: Expected format (default: "JSON")
            temperature: Temperature for generation
        
        Returns:
            Parsed JSON response or dict
        """
        import json
        
        format_instruction = ""
        if response_format == "JSON":
            format_instruction = "\n\nRespond ONLY with valid JSON. Do not include any markdown formatting, code blocks, or explanatory text."
        
        full_prompt = f"{prompt}{format_instruction}"
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{full_prompt}"
        
        try:
            response = self.model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature
                )
            )
            
            text = response.text.strip()
            # Remove markdown code blocks if present
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            return json.loads(text)
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract JSON from the response
            try:
                import re
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            except:
                pass
            raise Exception(f"Failed to parse JSON response: {text[:200]}")
        except Exception as e:
            raise Exception(f"Error generating structured response from Gemini: {str(e)}")

