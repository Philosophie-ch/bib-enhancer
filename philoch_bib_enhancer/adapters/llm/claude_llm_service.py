"""
Claude/Anthropic LLM service implementation.

Installation required:
    pip install anthropic

Environment variables:
    ANTHROPIC_API_KEY: Your Anthropic API key
"""

from typing import TypeVar
from pydantic import BaseModel

try:
    import anthropic
except ImportError:
    raise ImportError(
        "The 'anthropic' package is required for Claude LLM service. " "Install it with: pip install anthropic"
    )

from philoch_bib_enhancer.ports.llm_service import LLMServiceError


T = TypeVar('T', bound=BaseModel)


class ClaudeLLMService:
    """
    LLM service implementation using Anthropic's Claude API.
    """

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize Claude LLM service.

        Args:
            api_key: Anthropic API key
            model: Claude model to use (default: claude-3-5-sonnet-20241022)
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def parse_to_model(self, text: str, model_class: type[T], system_prompt: str) -> T:
        """
        Parse text into a Pydantic model using Claude with structured outputs.

        Args:
            text: The raw text to parse
            model_class: The Pydantic model class to parse into
            system_prompt: Instructions for Claude on how to extract data

        Returns:
            An instance of model_class populated with extracted data

        Raises:
            LLMServiceError: If the API call fails or returns invalid data
        """
        try:
            # Use Claude's tool calling feature with structured outputs
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": text,
                    }
                ],
                tools=[
                    {
                        "name": "extract_bibliography",
                        "description": "Extract bibliographic information from the provided text",
                        "input_schema": model_class.model_json_schema(),
                    }
                ],
                tool_choice={"type": "tool", "name": "extract_bibliography"},
            )

            # Extract the tool use result
            for block in response.content:
                if block.type == "tool_use" and block.name == "extract_bibliography":
                    # Parse the tool input using the Pydantic model
                    return model_class.model_validate(block.input)

            raise LLMServiceError("No tool use found in Claude's response")

        except anthropic.APIError as e:
            raise LLMServiceError(f"Claude API error: {e}") from e
        except Exception as e:
            raise LLMServiceError(f"Failed to parse with Claude: {e}") from e
