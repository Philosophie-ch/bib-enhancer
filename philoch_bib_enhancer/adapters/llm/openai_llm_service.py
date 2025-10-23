"""
OpenAI LLM service implementation.

Installation required:
    pip install openai

Environment variables:
    OPENAI_API_KEY: Your OpenAI API key
"""

from typing import TypeVar, Any
from pydantic import BaseModel

try:
    import openai
except ImportError:
    raise ImportError("The 'openai' package is required for OpenAI LLM service. " "Install it with: pip install openai")

from philoch_bib_enhancer.ports.llm_service import LLMServiceError


T = TypeVar('T', bound=BaseModel)


# Define proper Pydantic models for OpenAI's response structure
# (since they're too lazy to type their own API responses)


class OpenAIMessage(BaseModel):
    """OpenAI message in completion response."""

    role: str
    content: str | None = None
    parsed: Any | None = None  # The structured output (untyped by OpenAI)


class OpenAIChoice(BaseModel):
    """OpenAI choice in completion response."""

    index: int
    message: OpenAIMessage
    finish_reason: str | None = None


class OpenAICompletion(BaseModel):
    """OpenAI completion response structure."""

    id: str
    object: str
    created: int
    model: str
    choices: list[OpenAIChoice]


class OpenAILLMService:
    """
    LLM service implementation using OpenAI's API.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-2024-08-06"):
        """
        Initialize OpenAI LLM service.

        Args:
            api_key: OpenAI API key
            model: OpenAI model to use (default: gpt-4o-2024-08-06, supports structured outputs)
        """
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def parse_to_model(self, text: str, model_class: type[T], system_prompt: str) -> T:
        """
        Parse text into a Pydantic model using OpenAI with structured outputs.

        Args:
            text: The raw text to parse
            model_class: The Pydantic model class to parse into
            system_prompt: Instructions for OpenAI on how to extract data

        Returns:
            An instance of model_class populated with extracted data

        Raises:
            LLMServiceError: If the API call fails or returns invalid data
        """
        try:
            # Use OpenAI's structured outputs feature (returns untyped response)
            completion_raw = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                response_format=model_class,
            )

            # Validate OpenAI's response structure with our Pydantic model
            completion = OpenAICompletion.model_validate(completion_raw.model_dump())

            # Extract the parsed message
            if not completion.choices:
                raise LLMServiceError("OpenAI returned no choices in response")

            parsed_any = completion.choices[0].message.parsed
            if parsed_any is None:
                raise LLMServiceError("OpenAI returned no parsed output")

            # Don't trust OpenAI's untyped parsed field - re-validate with our model
            # Convert to dict if it has dict-like attributes, otherwise treat as dict
            if hasattr(parsed_any, 'model_dump'):
                parsed_dict = parsed_any.model_dump()
            elif hasattr(parsed_any, '__dict__'):
                parsed_dict = vars(parsed_any)
            else:
                parsed_dict = dict(parsed_any)

            # Parse and validate with our Pydantic model
            return model_class.model_validate(parsed_dict)

        except openai.APIError as e:
            raise LLMServiceError(f"OpenAI API error: {e}") from e
        except Exception as e:
            raise LLMServiceError(f"Failed to parse with OpenAI: {e}") from e
