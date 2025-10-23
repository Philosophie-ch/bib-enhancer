"""Domain logic module - pure functions with no I/O or side effects."""

from philoch_bib_enhancer.domain.parsing_result import (
    ParsedResult,
    ParsingSuccess,
    ParsingError,
    is_parsing_success,
)
from philoch_bib_enhancer.domain.bibkey_matching import match_bibkey_to_article

__all__ = [
    "ParsedResult",
    "ParsingSuccess",
    "ParsingError",
    "is_parsing_success",
    "match_bibkey_to_article",
]
