"""
Gateway-agnostic parsing result types.

These types are used across all gateways (Crossref, RawWebText, etc.) to represent
the result of parsing/converting data into BibItem objects.
"""

from typing import TypedDict, TypeGuard
from typing_extensions import Literal


class ParsingSuccess[T](TypedDict, total=True):
    """
    A successfully parsed object with a result and a parsing status.

    Used when parsing/conversion succeeds and produces a valid output.
    """

    out: T
    parsing_status: Literal["success"]


class ParsingError(TypedDict, total=True):
    """
    An error that occurred during parsing/conversion.

    Used when parsing/conversion fails, capturing the error message
    and context for debugging.
    """

    parsing_status: Literal["error"]
    message: str  # Human-readable error description
    context: str  # Raw data or additional context for debugging


type ParsedResult[T] = ParsingSuccess[T] | ParsingError
"""
Union type representing either a successful parse or an error.

This is the standard return type for all gateway conversion functions.
Allows errors to be captured without throwing exceptions.
"""


def is_parsing_success[T](result: ParsedResult[T]) -> TypeGuard[ParsingSuccess[T]]:
    """
    Type guard to check if a ParsedResult is a success.

    Usage:
        result = convert_something(...)
        if is_parsing_success(result):
            bibitem = result["out"]  # TypeScript knows this is safe
        else:
            print(result["message"])  # TypeScript knows this is an error

    Args:
        result: A ParsedResult to check

    Returns:
        True if parsing succeeded, False otherwise
    """
    return result.get("parsing_status") == "success"
