"""
Author: Claude Code using Sonnet 4
Date: 2025-09-22
PURPOSE: Simple OpenAI client wrapper to replace complex llama-index LLM system
SRP and DRY check: Pass - Single responsibility for OpenAI API calls with minimal dependencies
"""

import os
from typing import Any, Optional
from openai import OpenAI


class SimpleOpenAILLM:
    """
    Simple wrapper around OpenAI client that supports both direct OpenAI and OpenRouter.
    Maintains compatibility with existing LlamaIndex LLM interface methods.
    """

    def __init__(self, model: str, provider: str, **kwargs):
        """
        Initialize the LLM with OpenAI client.

        Args:
            model: The model name (e.g., "gpt-5-mini-2025-08-07", "google/gemini-2.0-flash-001")
            provider: Either "openai" or "openrouter"
            **kwargs: Additional parameters (maintained for compatibility)
        """
        self.model = model
        self.provider = provider

        if provider == "openai":
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        elif provider == "openrouter":
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY")
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def complete(self, prompt: str, **kwargs) -> str:
        """
        Complete a prompt using the configured model.
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

            completion = self.client.chat.completions.create(
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

            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                extra_headers=extra_headers
            )
            return completion.choices[0].message.content

        except Exception as e:
            raise Exception(f"LLM chat failed for model {self.model}: {str(e)}")

    # Additional compatibility methods for LlamaIndex interface
    @property
    def model_name(self) -> str:
        """Return the model name for compatibility."""
        return self.model

    def __str__(self) -> str:
        return f"SimpleOpenAILLM(model={self.model}, provider={self.provider})"

    def __repr__(self) -> str:
        return self.__str__()