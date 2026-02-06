"""Fuzzy matching for bibliographic items.

This package provides high-performance fuzzy matching of BibItems against
an existing bibliography, using blocking indexes and configurable scoring weights.

Uses Rust-accelerated scoring (required) for 10-100x faster processing.
"""

from philoch_bib_enhancer.fuzzy_matching.comparator import (
    compare_bibitems,
    compare_bibitems_detailed,
)
from philoch_bib_enhancer.fuzzy_matching.matcher import (
    BibItemBlockIndex,
    build_index,
    build_index_cached,
    stage_bibitems_batch,
    stage_bibitems_streaming,
    _RUST_SCORER_AVAILABLE,
)
from philoch_bib_enhancer.fuzzy_matching.models import (
    BibItemStaged,
    DEFAULT_FUZZY_MATCH_WEIGHTS,
    FuzzyMatchWeights,
    Match,
    PartialScore,
    ScoreComponent,
    SearchMetadata,
    weights_to_tuple,
)

__all__ = [
    "BibItemBlockIndex",
    "BibItemStaged",
    "DEFAULT_FUZZY_MATCH_WEIGHTS",
    "FuzzyMatchWeights",
    "Match",
    "PartialScore",
    "ScoreComponent",
    "SearchMetadata",
    "_RUST_SCORER_AVAILABLE",
    "build_index",
    "build_index_cached",
    "compare_bibitems",
    "compare_bibitems_detailed",
    "stage_bibitems_batch",
    "stage_bibitems_streaming",
    "weights_to_tuple",
]
