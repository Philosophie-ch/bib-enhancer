"""
Abstract LLM service interface for text parsing.

This module defines the protocol for LLM services that can extract
structured bibliographic data from unstructured text.
"""

from typing import Protocol, TypeVar
from pydantic import BaseModel


T = TypeVar('T', bound=BaseModel)


class LLMService(Protocol):
    """
    Protocol for LLM services that can parse text into structured Pydantic models.

    Concrete implementations should handle API calls to Claude, OpenAI, etc.
    """

    def parse_to_model(self, text: str, model_class: type[T], system_prompt: str) -> T:
        """
        Parse unstructured text into a structured Pydantic model.

        Args:
            text: The raw text to parse (e.g., web page content)
            model_class: The Pydantic model class to parse into
            system_prompt: Instructions for the LLM on how to extract data

        Returns:
            An instance of model_class populated with extracted data

        Raises:
            LLMServiceError: If the LLM service fails or returns invalid data
        """
        ...


class LLMServiceError(Exception):
    """Raised when an LLM service operation fails."""
