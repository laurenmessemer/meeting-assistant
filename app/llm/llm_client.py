"""Generic LLM client supporting multiple providers (OpenRouter, Gemini, etc.)."""

import json
import httpx
from typing import Optional, Dict, Any
from app.config import settings

# Try to import Gemini for backward compatibility
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class LLMClient:
    """Generic LLM client supporting multiple providers."""
    
    def __init__(self):
        self.provider = settings.llm_provider.lower()
        self.api_key = settings.llm_api_key
        
        if self.provider == "gemini":
            if not GEMINI_AVAILABLE:
                raise ImportError(
                    "google-generativeai package is not installed. "
                    "Install it with: pip install google-generativeai"
                )
            genai.configure(api_key=self.api_key)
            # Use available Gemini models - try latest first, then fallback
            # Model names should be without the "models/" prefix
            model_names = [
                'gemini-2.5-flash',      # Latest fast model
                'gemini-2.5-pro',        # Latest pro model
                'gemini-flash-latest',    # Latest flash (aliased)
                'gemini-pro-latest',      # Latest pro (aliased)
                'gemini-2.0-flash',       # Stable 2.0 flash
            ]
            self.model = None
            for model_name in model_names:
                try:
                    self.model = genai.GenerativeModel(model_name)
                    # Model created successfully
                    break
                except Exception:
                    continue
            if self.model is None:
                # Final fallback - try to get any available model
                try:
                    models = list(genai.list_models())
                    for model in models:
                        if 'generateContent' in model.supported_generation_methods:
                            # Extract model name without "models/" prefix
                            model_name = model.name.replace('models/', '')
                            self.model = genai.GenerativeModel(model_name)
                            break
                except Exception:
                    raise Exception("No available Gemini models found. Please check your API key.")
        elif self.provider == "openrouter":
            self.base_url = "https://openrouter.ai/api/v1"
            self.default_model = "openai/gpt-3.5-turbo"  # Free tier option
        else:
            # Default to Gemini if provider not recognized
            if GEMINI_AVAILABLE:
                self.provider = "gemini"
                genai.configure(api_key=self.api_key)
                try:
                    self.model = genai.GenerativeModel('gemini-1.5-flash')
                except Exception:
                    self.model = genai.GenerativeModel('gemini-pro')
            else:
                # Fallback to OpenRouter if Gemini is not available
                self.provider = "openrouter"
                self.base_url = "https://openrouter.ai/api/v1"
                self.default_model = "openai/gpt-3.5-turbo"
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model: Optional model override
        
        Returns:
            Generated text response
        """
        if self.provider == "gemini":
            return self._generate_gemini(prompt, system_prompt, temperature)
        elif self.provider == "openrouter":
            return self._generate_openrouter(prompt, system_prompt, temperature, max_tokens, model)
        else:
            # Fallback based on what's available
            if GEMINI_AVAILABLE:
                return self._generate_gemini(prompt, system_prompt, temperature)
            else:
                return self._generate_openrouter(prompt, system_prompt, temperature, max_tokens, model)
    
    def _generate_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float
    ) -> str:
        """Generate using Gemini API."""
        # Gemini supports system instructions in newer models
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
        )
        
        try:
            # For gemini-1.5 models, we can use system_instruction parameter
            if hasattr(self.model, 'generate_content') and system_prompt:
                # Try using system_instruction if available (for newer models)
                try:
                    response = self.model.generate_content(
                        prompt,
                        generation_config=generation_config,
                        system_instruction=system_prompt
                    )
                except TypeError:
                    # Fallback to prepending system prompt if system_instruction not supported
                    full_prompt = f"{system_prompt}\n\n{prompt}"
                    response = self.model.generate_content(
                        full_prompt,
                        generation_config=generation_config,
                    )
            else:
                # Fallback for older models
                full_prompt = prompt
                if system_prompt:
                    full_prompt = f"{system_prompt}\n\n{prompt}"
                response = self.model.generate_content(
                    full_prompt,
                    generation_config=generation_config,
                )
            
            if hasattr(response, 'text') and response.text:
                return response.text
            else:
                raise Exception("Empty response from Gemini API")
        except Exception as e:
            raise Exception(f"Error generating response from Gemini: {str(e)}")
    
    def _generate_openrouter(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        model: Optional[str]
    ) -> str:
        """Generate using OpenRouter API."""
        model_name = model or self.default_model
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/meeting-assistant",  # Optional: for OpenRouter analytics
        }
        
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract content from response
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                raise Exception("Unexpected response format from OpenRouter")
        except httpx.HTTPError as e:
            raise Exception(f"Error generating response from OpenRouter: {str(e)}")
    
    def generate_structured(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        response_format: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a structured response (JSON).
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            response_format: Expected format description (e.g., "JSON")
            model: Optional model override
        
        Returns:
            Parsed response as dictionary
        """
        format_instruction = ""
        if response_format:
            format_instruction = f"\n\nPlease respond in {response_format} format."
        
        full_prompt = f"{prompt}{format_instruction}"
        
        response_text = self.generate(
            full_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            model=model,
        )
        
        # Try to parse as JSON if response_format is JSON
        if response_format and "json" in response_format.lower():
            try:
                # Extract JSON from response if it's wrapped in markdown code blocks
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    response_text = response_text[json_start:json_end].strip()
                
                return json.loads(response_text)
            except json.JSONDecodeError:
                # If parsing fails, return as text
                return {"response": response_text}
        
        return {"response": response_text}


# For backward compatibility, create GeminiClient alias
# This allows existing code to import GeminiClient and it will work with any provider
GeminiClient = LLMClient

