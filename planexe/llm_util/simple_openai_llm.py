"""
Author: Claude Code using Sonnet 4
Date: 2025-09-22
PURPOSE: Simple OpenAI client wrapper to replace complex llama-index LLM system
SRP and DRY check: Pass - Single responsibility for OpenAI API calls with minimal dependencies
"""

import os
from typing import Any, Optional
from openai import OpenAI
from llama_index.core.llms.llm import LLM
from pydantic import Field, PrivateAttr, ValidationError


class SimpleOpenAILLM(LLM):
    """
    Simple wrapper around OpenAI client that supports both direct OpenAI and OpenRouter.
    Maintains compatibility with existing LlamaIndex LLM interface methods.
    """

    model: str = Field(description="The model name")
    provider: str = Field(description="Either 'openai' or 'openrouter'")
    _client: OpenAI = PrivateAttr()

    def __init__(self, model: str, provider: str, **kwargs):
        """
        Initialize the LLM with OpenAI client.
        Args:
            model: The model name (e.g., "gpt-5-mini-2025-08-07", "google/gemini-2.0-flash-001")
            provider: Either "openai" or "openrouter"
            **kwargs: Additional parameters (maintained for compatibility)
        """
        super().__init__(model=model, provider=provider, **kwargs)

        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                error_msg = (
                    "OPENAI_API_KEY environment variable not set! "
                    "Cannot create OpenAI client. "
                    "Check Railway environment variables."
                )
                print(f"ERROR LLM: {error_msg}")
                raise ValueError(error_msg)
            
            print(f"DEBUG LLM: Creating OpenAI client (key length: {len(api_key)})")
            self._client = OpenAI(api_key=api_key)
            
        elif provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                error_msg = (
                    "OPENROUTER_API_KEY environment variable not set! "
                    "Cannot create OpenRouter client. "
                    "Check Railway environment variables."
                )
                print(f"ERROR LLM: {error_msg}")
                raise ValueError(error_msg)
            
            print(f"DEBUG LLM: Creating OpenRouter client (key length: {len(api_key)})")
            self._client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def complete(self, prompt: str, **kwargs) -> str:
        """
        Complete a prompt using the configured model.
{{ ... }}
        Maintains LlamaIndex LLM interface compatibility.
        Uses standard chat completions API for all models (simpler).

        Args:
            prompt: The input prompt text
            **kwargs: Additional parameters (maintained for compatibility)

        Returns:
            The completion text
        """
        try:
            # Use standard chat completions for ALL models (simpler approach)
            extra_headers = {}
            if self.provider == "openrouter":
                extra_headers = {
                    "HTTP-Referer": "https://github.com/neoneye/PlanExe",
                    "X-Title": "PlanExe"
                }

            completion = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                extra_headers=extra_headers
            )
            return completion.choices[0].message.content

        except Exception as e:
            raise Exception(f"LLM completion failed for model {self.model}: {str(e)}")

    def chat(self, messages, **kwargs) -> str:
        """
        Chat completion with message history.
        Maintains LlamaIndex LLM interface compatibility.

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional parameters

        Returns:
            The response text
        """
        try:
            extra_headers = {}
            if self.provider == "openrouter":
                extra_headers = {
                    "HTTP-Referer": "https://github.com/neoneye/PlanExe",
                    "X-Title": "PlanExe"
                }

            completion = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                extra_headers=extra_headers
            )
            return completion.choices[0].message.content

        except Exception as e:
            raise Exception(f"LLM chat failed for model {self.model}: {str(e)}")

    def complete(self, prompt: str, **kwargs):
        """
        Complete a text prompt using the LLM.

        Args:
            prompt: The input prompt text
            **kwargs: Additional parameters

        Returns:
            Completion response text
        """
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, **kwargs)

    # Additional compatibility methods for LlamaIndex interface
    @property
    def model_name(self) -> str:
        """Return the model name for compatibility."""
        return self.model

    @property
    def metadata(self) -> dict:
        """Return metadata dict for compatibility with LlamaIndex."""
        return {
            "model": self.model,
            "provider": self.provider,
            "model_name": self.model,
            "max_tokens": None,  # We don't have this info in simplified implementation
            "temperature": None,  # We don't have this info in simplified implementation
        }

    def class_name(self) -> str:
        """Return class name for compatibility with LlamaIndex."""
        return self.__class__.__name__

    def __str__(self) -> str:
        return f"SimpleOpenAILLM(model={self.model}, provider={self.provider})"

    def __repr__(self) -> str:
        return self.__str__()

    def as_structured_llm(self, output_cls):
        """
        Return a structured LLM that can parse responses into Pydantic models.
        This maintains compatibility with LlamaIndex structured output interface.
        """
        return StructuredSimpleOpenAILLM(self, output_cls)

    # Abstract methods required by LlamaIndex LLM base class
    def stream_chat(self, messages, **kwargs):
        """Stream chat completion (required abstract method)."""
        # For now, just return non-streaming result as single chunk
        response = self.chat(messages, **kwargs)
        yield response

    def stream_complete(self, prompt: str, **kwargs):
        """Stream text completion (required abstract method)."""
        # For now, just return non-streaming result as single chunk
        response = self.complete(prompt, **kwargs)
        yield response

    async def achat(self, messages, **kwargs):
        """Async chat completion (required abstract method)."""
        # For now, just call sync version
        return self.chat(messages, **kwargs)

    async def acomplete(self, prompt: str, **kwargs):
        """Async text completion (required abstract method)."""
        # For now, just call sync version
        return self.complete(prompt, **kwargs)

    async def astream_chat(self, messages, **kwargs):
        """Async stream chat completion (required abstract method)."""
        # For now, just yield sync result
        response = self.chat(messages, **kwargs)
        yield response

    async def astream_complete(self, prompt: str, **kwargs):
        """Async stream text completion (required abstract method)."""
        # For now, just yield sync result
        response = self.complete(prompt, **kwargs)
        yield response


class StructuredLLMResponse:
    """
    LlamaIndex-compatible structured LLM response object.
    """

    def __init__(self, parsed_model, raw_text: str):
        self.raw = parsed_model  # This is what the pipeline expects
        self.text = raw_text
        self.message = type('Message', (), {'content': raw_text})()

    def __str__(self) -> str:
        return str(self.raw)

    def __repr__(self) -> str:
        return f"StructuredLLMResponse(raw={self.raw})"


class StructuredSimpleOpenAILLM:
    """
    Wrapper that provides structured output capabilities for SimpleOpenAILLM.
    Compatible with LlamaIndex structured LLM interface.
    """

    def __init__(self, base_llm: SimpleOpenAILLM, output_cls):
        self.base_llm = base_llm
        self.output_cls = output_cls

    def chat(self, messages, **kwargs):
        """
        Chat with structured output parsing.

        Args:
            messages: List of ChatMessage objects or message dicts
            **kwargs: Additional parameters

        Returns:
            Parsed Pydantic model instance
        """
        # Convert ChatMessage objects to standard format if needed
        if hasattr(messages[0], 'role') and hasattr(messages[0], 'content'):
            # LlamaIndex ChatMessage format
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    "role": msg.role.lower() if hasattr(msg.role, 'lower') else str(msg.role).lower(),
                    "content": msg.content
                })
        else:
            # Already in dict format
            formatted_messages = messages

        # Build structured prompt
        schema_prompt = f"""
You must respond with valid JSON that matches this exact schema:
{self.output_cls.model_json_schema()}

Your response must be valid JSON only, no other text.
"""

        # Add schema instruction to the last user message
        if formatted_messages and formatted_messages[-1]["role"] == "user":
            formatted_messages[-1]["content"] += f"\n\n{schema_prompt}"
        else:
            formatted_messages.append({"role": "user", "content": schema_prompt})

        try:
            # Get response from base LLM
            if self.base_llm.provider == "openai":
                completion = self.base_llm._client.chat.completions.create(
                    model=self.base_llm.model,
                    messages=formatted_messages,
                    response_format={"type": "json_object"}  # Force JSON mode
                )
                response_text = completion.choices[0].message.content
            else:
                # OpenRouter doesn't always support response_format
                completion = self.base_llm._client.chat.completions.create(
                    model=self.base_llm.model,
                    messages=formatted_messages,
                    extra_headers={
                        "HTTP-Referer": "https://github.com/neoneye/PlanExe",
                        "X-Title": "PlanExe"
                    }
                )
                response_text = completion.choices[0].message.content

            # Parse JSON response into Pydantic model
            import json
            try:
                response_data = json.loads(response_text)
                parsed_model = self.output_cls.model_validate(response_data)

                # Create LlamaIndex-compatible response object
                return StructuredLLMResponse(parsed_model, response_text)
            except json.JSONDecodeError as e:
                # Fallback: try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    response_data = json.loads(json_match.group())
                    parsed_model = self.output_cls.model_validate(response_data)
                    return StructuredLLMResponse(parsed_model, response_text)
                else:
                    raise ValueError(f"Could not parse JSON response: {response_text}") from e
            except ValidationError:
                # Fallback attempt: remind model to return data, not schema
                fallback_messages = list(formatted_messages) + [{
                    "role": "user",
                    "content": "Respond again with ONLY a JSON object matching the requested fields. Do not include JSON schema definitions or comments."
                }]
                fallback_text = self.base_llm.chat(fallback_messages)
                response_text = fallback_text if isinstance(fallback_text, str) else str(fallback_text)
                response_data = json.loads(response_text)
                parsed_model = self.output_cls.model_validate(response_data)
                return StructuredLLMResponse(parsed_model, response_text)

        except Exception as e:
            raise Exception(f"Structured LLM completion failed for model {self.base_llm.model}: {str(e)}")

    def complete(self, prompt: str, **kwargs):
        """
        Complete a prompt with structured output parsing.

        Args:
            prompt: The input prompt text
            **kwargs: Additional parameters

        Returns:
            Parsed Pydantic model instance
        """
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, **kwargs)