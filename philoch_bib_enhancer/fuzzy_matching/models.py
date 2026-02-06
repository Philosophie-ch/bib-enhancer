"""Data models for staged bibliography matching.

This module provides models for tracking fuzzy matching results when comparing
new BibItems against an existing bibliography.
"""

import json
from enum import StrEnum
from typing import Tuple, TypedDict

import attrs


class FuzzyMatchWeights(TypedDict):
    """Weights for the four scoring components in fuzzy matching.

    All weights should sum to 1.0 for normalized scoring.

    Attributes:
        title: Weight for title similarity (default 0.5)
        author: Weight for author similarity (default 0.3)
        date: Weight for date similarity (default 0.1)
        bonus: Weight for bonus fields like DOI, journal, pages, publisher (default 0.1)
    """

    title: float
    author: float
    date: float
    bonus: float


# Tuned on PhilStudies benchmark (2026-02-06) with grid search after algorithmic improvements:
# - Academic prefix gate, author initials matching, wider date tolerance
# Results: 96.72% P@1, 98.09% R@5, 0.9738 MRR
# See tests/fuzzy_matching/test_benchmark.py for full results and reasoning
DEFAULT_FUZZY_MATCH_WEIGHTS: FuzzyMatchWeights = {
    "title": 0.25,
    "author": 0.25,
    "date": 0.2,
    "bonus": 0.3,
}


def weights_to_tuple(weights: FuzzyMatchWeights) -> tuple[float, float, float, float]:
    """Convert FuzzyMatchWeights TypedDict to a tuple for internal scoring functions."""
    return (weights["title"], weights["author"], weights["date"], weights["bonus"])


class SearchMetadata(TypedDict, total=False):
    """Metadata about a fuzzy matching search operation.

    Attributes:
        search_time_ms: Time taken for the search in milliseconds
        candidates_searched: Number of candidates evaluated
        scorer: Which scorer was used ("rust" or "python")
    """

    search_time_ms: int
    candidates_searched: int
    scorer: str


from philoch_bib_sdk.converters.plaintext.author.formatter import format_author
from philoch_bib_sdk.logic.models import BibItem


class ScoreComponent(StrEnum):
    """Components used in calculating similarity scores between BibItems."""

    TITLE = "title"
    AUTHOR = "author"
    DATE = "date"
    DOI = "doi"
    JOURNAL_VOLUME_NUMBER = "journal_volume_number"
    PAGES = "pages"
    PUBLISHER = "publisher"


@attrs.define(frozen=True, slots=True)
class PartialScore:
    """Individual score component with weight and explanation.

    Attributes:
        component: The type of comparison (title, author, etc.)
        score: Raw score value (before weighting)
        weight: Weight factor applied to this component (0.0-1.0)
        weighted_score: Final score after applying weight (score * weight)
        details: Human-readable explanation of the score
    """

    component: ScoreComponent
    score: int
    weight: float
    weighted_score: float
    details: str


@attrs.define(frozen=True, slots=True)
class Match:
    """A candidate match with full scoring breakdown.

    Attributes:
        bibkey: The bibliography key of the matched item
        matched_bibitem: The full BibItem that was matched
        total_score: Sum of all weighted partial scores
        partial_scores: Detailed breakdown of each score component
        rank: Position in the results (1-based, 1 = best match)
    """

    bibkey: str
    matched_bibitem: BibItem
    total_score: float
    partial_scores: Tuple[PartialScore, ...]
    rank: int

    def to_json_summary(self) -> dict[str, object]:
        """Convert match to a JSON-serializable summary.

        Returns:
            Dictionary with bibkey, rank, scores, and breakdown details
        """
        # Truncate long strings for readability in CSV
        from philoch_bib_sdk.logic.models import BibStringAttr

        title_attr = self.matched_bibitem.title
        title = title_attr.simplified if isinstance(title_attr, BibStringAttr) else ""
        title_truncated = title[:100] + "..." if len(title) > 100 else title

        author_formatted = format_author(self.matched_bibitem.author, "simplified")
        author_truncated = author_formatted[:100] + "..." if len(author_formatted) > 100 else author_formatted

        return {
            "bibkey": self.bibkey,
            "rank": self.rank,
            "total_score": round(self.total_score, 2),
            "title": title_truncated,
            "author": author_truncated,
            "score_breakdown": {
                ps.component.value: {
                    "score": ps.score,
                    "weight": ps.weight,
                    "weighted": round(ps.weighted_score, 2),
                    "details": ps.details,
                }
                for ps in self.partial_scores
            },
        }


@attrs.define(frozen=True, slots=True)
class BibItemStaged:
    """A BibItem being matched against a bibliography.

    Used for processing new/incoming bibliographic entries and comparing them
    against an existing bibliography to find potential matches or duplicates.

    Attributes:
        bibitem: The new/incoming item to match
        top_matches: Top N best matches found in the bibliography
        search_metadata: Performance and search statistics
    """

    bibitem: BibItem
    top_matches: Tuple[Match, ...]
    search_metadata: SearchMetadata

    def to_csv_row(self) -> dict[str, str | int | float]:
        """Export as a flat CSV row with nested JSON for match details.

        Returns:
            Dictionary suitable for CSV writing with json-encoded top_matches
        """
        from philoch_bib_sdk.converters.plaintext.bibitem.bibkey_formatter import format_bibkey
        from philoch_bib_sdk.logic.models import BibItemDateAttr, BibStringAttr

        # Handle date formatting
        date_str = ""
        if self.bibitem.date != "no date":
            date_obj = self.bibitem.date
            if isinstance(date_obj, BibItemDateAttr):
                date_str = str(date_obj.year)

        # Get best match info if available
        best_match_score = 0.0
        best_match_bibkey = ""
        if self.top_matches:
            best_match_score = self.top_matches[0].total_score
            best_match_bibkey = self.top_matches[0].bibkey

        # Handle bibkey using formatter
        bibkey_str = format_bibkey(self.bibitem.bibkey)

        # Handle title
        title_attr = self.bibitem.title
        title_str = title_attr.simplified if isinstance(title_attr, BibStringAttr) else ""

        return {
            "staged_bibkey": bibkey_str,
            "staged_title": title_str,
            "staged_author": format_author(self.bibitem.author, "simplified"),
            "staged_year": date_str,
            "num_matches": len(self.top_matches),
            "best_match_score": round(best_match_score, 2),
            "best_match_bibkey": best_match_bibkey,
            "top_matches_json": json.dumps(tuple(m.to_json_summary() for m in self.top_matches)),
            "search_time_ms": self.search_metadata.get("search_time_ms", 0),
            "candidates_searched": self.search_metadata.get("candidates_searched", 0),
        }
