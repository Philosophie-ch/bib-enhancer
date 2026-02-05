"""Type stubs for philoch_bib_enhancer._rust - Rust extension module.

This module provides high-performance Rust implementations for:
- Building search indexes for fuzzy matching
- Batch fuzzy scoring of bibliographic items
"""

from typing import TypedDict

# === Index Building Types ===

class ItemData(TypedDict):
    """Input data for a single bibliographic item (for index building)."""

    item_index: int
    doi: str | None
    title: str
    author_surnames: list[str]
    year: int | None
    journal_name: str | None

class IndexData:
    """Output index data structure from build_index_rust."""

    doi_to_index: dict[str, int]
    trigram_to_indices: dict[str, list[int]]
    surname_to_indices: dict[str, list[int]]
    decade_to_indices: dict[int | None, list[int]]
    journal_to_indices: dict[str, list[int]]

def build_index_rust(items_data: list[ItemData]) -> IndexData:
    """Build index for fuzzy matching.

    Args:
        items_data: List of ItemData dicts with bibliographic info

    Returns:
        IndexData with all indexes built for fast lookup
    """
    ...

def hello_rust() -> str:
    """A simple test function to verify Rust integration works.

    Returns:
        A greeting string from Rust
    """
    ...

# === Scorer Types ===

class BibItemData(TypedDict):
    """Input data for a single BibItem (for scoring)."""

    index: int
    title: str
    author: str
    year: int | None
    doi: str | None
    journal: str | None
    volume: str | None
    number: str | None
    pages: str | None
    publisher: str | None

class MatchResult(TypedDict):
    """Result of scoring a candidate against a subject."""

    candidate_index: int
    total_score: float
    title_score: float
    author_score: float
    date_score: float
    bonus_score: float

class SubjectMatchResult(TypedDict):
    """Result for a single subject with its top matches."""

    subject_index: int
    matches: list[MatchResult]
    candidates_searched: int

def token_sort_ratio(s1: str, s2: str) -> float:
    """Token sort ratio using Jaro-Winkler similarity.

    Args:
        s1: First string to compare
        s2: Second string to compare

    Returns:
        Similarity score from 0.0 to 100.0
    """
    ...

class Weights(TypedDict):
    """Scoring weights for the four matching components.

    Mirrors FuzzyMatchWeights — passed as a dict from Python.
    """

    title: float
    author: float
    date: float
    bonus: float

def score_batch(
    subjects: list[BibItemData],
    candidates: list[BibItemData],
    top_n: int,
    min_score: float,
    weights: Weights,
) -> list[SubjectMatchResult]:
    """Batch score multiple subjects against candidates in parallel.

    Args:
        subjects: List of BibItems to find matches for
        candidates: List of BibItems to match against
        top_n: Maximum number of matches to return per subject
        min_score: Minimum score threshold for matches
        weights: Dict with title, author, date, bonus weight floats

    Returns:
        List of results, one per subject, containing top matches
    """
    ...
