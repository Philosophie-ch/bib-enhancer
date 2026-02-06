"""High-performance fuzzy matching for BibItems using blocking indexes.

This module provides efficient fuzzy matching against large bibliographies (100k+ items)
by using multi-index blocking to reduce the search space before applying detailed scoring.

Uses a Rust-based batch scorer for parallel processing, providing 10-100x speedup.
"""

import pickle
import time
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, DefaultDict, FrozenSet, Iterator, Sequence, Tuple

from aletk.utils import remove_extra_whitespace

from philoch_bib_sdk.converters.plaintext.bibitem.bibkey_formatter import format_bibkey
from philoch_bib_sdk.logic.models import BibItem, BibItemDateAttr
from philoch_bib_enhancer.fuzzy_matching.models import (
    DEFAULT_FUZZY_MATCH_WEIGHTS,
    BibItemStaged,
    FuzzyMatchWeights,
    Match,
    SearchMetadata,
)

from philoch_bib_sdk.converters.plaintext.author.formatter import format_author
from philoch_bib_sdk.logic.models import Author, BibStringAttr
from philoch_bib_enhancer.fuzzy_matching.models import PartialScore, ScoreComponent


if TYPE_CHECKING:
    from philoch_bib_enhancer._rust import BibItemData, IndexData, ItemData

# Try to import Rust scorer for batch processing
try:
    from philoch_bib_enhancer import _rust as rust_scorer

    _RUST_SCORER_AVAILABLE = True
except ImportError:
    _RUST_SCORER_AVAILABLE = False


class BibItemBlockIndex:
    """Multi-index structure for fast candidate retrieval.

    Uses multiple overlapping indexes (DOI, title n-grams, author surnames, year decades,
    journal names) to quickly find potential matches without excluding items due to dirty data.

    Attributes:
        doi_index: Exact DOI lookup for instant matches
        title_trigrams: Title n-gram index for fuzzy title matching
        author_surnames: Author surname index for author matching
        year_decades: Year grouped by decade (with None for missing)
        journals: Journal name index
        all_items: Complete tuple of all items (fallback)
    """

    def __init__(
        self,
        doi_index: dict[str, BibItem],
        title_trigrams: dict[str, FrozenSet[BibItem]],
        author_surnames: dict[str, FrozenSet[BibItem]],
        year_decades: dict[int | None, FrozenSet[BibItem]],
        journals: dict[str, FrozenSet[BibItem]],
        all_items: Tuple[BibItem, ...],
    ) -> None:
        self.doi_index = doi_index
        self.title_trigrams = title_trigrams
        self.author_surnames = author_surnames
        self.year_decades = year_decades
        self.journals = journals
        self.all_items = all_items


def _extract_trigrams(text: str) -> FrozenSet[str]:
    """Extract 3-character n-grams from text for fuzzy matching.

    Args:
        text: Input text to extract trigrams from

    Returns:
        Frozen set of trigrams (immutable for hashing)
    """
    normalized = remove_extra_whitespace(text).lower()
    if len(normalized) < 3:
        return frozenset()
    return frozenset(normalized[i : i + 3] for i in range(len(normalized) - 2))


def _extract_author_surnames(authors: Tuple["Author", ...]) -> FrozenSet[str]:
    """Extract author surnames for indexing.

    Args:
        authors: Tuple of Author objects

    Returns:
        Frozen set of normalized surnames
    """

    if not authors:
        return frozenset()

    surnames: list[str] = []
    for author in authors:
        family_name_attr = author.family_name
        if family_name_attr.simplified:
            surnames.append(remove_extra_whitespace(family_name_attr.simplified).lower())

    return frozenset(surnames)


def _get_decade(date: BibItemDateAttr | str) -> int | None:
    """Get the decade from a date attribute.

    Args:
        date: BibItemDateAttr or "no date"

    Returns:
        Decade as integer (e.g., 1990) or None if no date
    """
    if date == "no date":
        return None
    if isinstance(date, BibItemDateAttr):
        return (date.year // 10) * 10
    return None


def _prepare_items_for_rust(bibitems: Sequence[BibItem]) -> "list[ItemData]":
    """Extract minimal data needed by Rust build_index_rust.

    Args:
        bibitems: Sequence of BibItems to prepare

    Returns:
        List of dicts with minimal data for Rust
    """

    items_data: list[ItemData] = []
    for i, item in enumerate(bibitems):
        # Extract title string
        title_attr = item.title
        if isinstance(title_attr, BibStringAttr):
            title = title_attr.simplified
        else:
            title = ""

        # Extract author surnames
        author_surnames = list(_extract_author_surnames(item.author))

        # Extract year
        decade = _get_decade(item.date)
        year = decade if decade is not None else None

        # Extract journal name
        journal_name = None
        if item.journal:
            journal_name = remove_extra_whitespace(item.journal.name.simplified).lower()

        items_data.append(
            {
                "item_index": i,
                "doi": item.doi if item.doi else None,
                "title": title,
                "author_surnames": author_surnames,
                "year": year,
                "journal_name": journal_name,
            }
        )

    return items_data


def _reconstruct_index_from_rust(index_data: "IndexData", items: Tuple[BibItem, ...]) -> BibItemBlockIndex:
    """Reconstruct BibItemBlockIndex from Rust IndexData.

    Args:
        index_data: IndexData object from Rust
        items: Tuple of original BibItems

    Returns:
        BibItemBlockIndex with all indexes built
    """
    # Convert Rust index mappings back to Python objects using original BibItems
    doi_index = {doi: items[idx] for doi, idx in index_data.doi_to_index.items()}

    title_trigrams = {
        trigram: frozenset(items[idx] for idx in indices) for trigram, indices in index_data.trigram_to_indices.items()
    }

    author_surnames = {
        surname: frozenset(items[idx] for idx in indices) for surname, indices in index_data.surname_to_indices.items()
    }

    year_decades = {
        decade: frozenset(items[idx] for idx in indices) for decade, indices in index_data.decade_to_indices.items()
    }

    journals = {
        name: frozenset(items[idx] for idx in indices) for name, indices in index_data.journal_to_indices.items()
    }

    return BibItemBlockIndex(
        doi_index=doi_index,
        title_trigrams=title_trigrams,
        author_surnames=author_surnames,
        year_decades=year_decades,
        journals=journals,
        all_items=items,
    )


def _build_index_python(bibitems: Tuple[BibItem, ...]) -> BibItemBlockIndex:
    """Pure Python implementation of build_index (fallback).

    Creates overlapping indexes to handle dirty data gracefully while maintaining
    fast lookup performance. No pre-filtering means no data loss.

    Optimized for performance:
    - Single-pass indexing (one loop instead of 5)
    - Deferred frozenset conversion (only at the end)
    - Reduced memory allocations

    Args:
        bibitems: Tuple of BibItems to index

    Returns:
        BibItemBlockIndex with all indexes built
    """

    # Initialize all index structures
    doi_index: dict[str, BibItem] = {}
    title_trigram_map: DefaultDict[str, set[BibItem]] = defaultdict(set)
    author_surname_map: DefaultDict[str, set[BibItem]] = defaultdict(set)
    year_decade_map: DefaultDict[int | None, set[BibItem]] = defaultdict(set)
    journal_map: DefaultDict[str, set[BibItem]] = defaultdict(set)

    # Single pass over all items - build all indexes at once
    for item in bibitems:
        # DOI index
        if item.doi:
            doi_index[item.doi] = item

        # Title trigram index
        title_attr = item.title
        if isinstance(title_attr, BibStringAttr):
            trigrams = _extract_trigrams(title_attr.simplified)
            for trigram in trigrams:
                title_trigram_map[trigram].add(item)

        # Author surname index
        surnames = _extract_author_surnames(item.author)
        for surname in surnames:
            author_surname_map[surname].add(item)

        # Year decade index
        decade = _get_decade(item.date)
        year_decade_map[decade].add(item)

        # Journal index
        if item.journal:
            journal_name_attr = item.journal.name
            if isinstance(journal_name_attr, BibStringAttr):
                journal_name = remove_extra_whitespace(journal_name_attr.simplified).lower()
                if journal_name:
                    journal_map[journal_name].add(item)

    # Convert sets to frozensets only at the end (single pass per index)
    title_trigrams = {trigram: frozenset(items) for trigram, items in title_trigram_map.items()}
    author_surnames = {surname: frozenset(items) for surname, items in author_surname_map.items()}
    year_decades = {decade: frozenset(items) for decade, items in year_decade_map.items()}
    journals = {name: frozenset(items) for name, items in journal_map.items()}

    return BibItemBlockIndex(
        doi_index=doi_index,
        title_trigrams=title_trigrams,
        author_surnames=author_surnames,
        year_decades=year_decades,
        journals=journals,
        all_items=bibitems,
    )


def build_index(bibitems: Sequence[BibItem]) -> BibItemBlockIndex:
    """Build multi-index structure for fast fuzzy matching.

    Creates overlapping indexes to handle dirty data gracefully while maintaining
    fast lookup performance. No pre-filtering means no data loss.

    Uses Rust implementation when available (100x faster), falls back to Python.

    Args:
        bibitems: Sequence of BibItems to index

    Returns:
        BibItemBlockIndex with all indexes built
    """
    # Convert to tuple for immutability
    items_tuple = tuple(bibitems)

    # Try to use Rust implementation
    try:
        from philoch_bib_enhancer._rust import build_index_rust

        items_data = _prepare_items_for_rust(items_tuple)
        index_data = build_index_rust(items_data)
        return _reconstruct_index_from_rust(index_data, items_tuple)
    except ImportError:
        pass

    # Fallback: pure Python
    return _build_index_python(items_tuple)


# --- Rust Scorer Integration ---


def _prepare_bibitem_for_rust_scorer(item: BibItem, idx: int) -> "BibItemData":
    """Prepare a BibItem for Rust scorer.

    Extracts simplified string fields needed for fuzzy matching.

    Args:
        item: BibItem to prepare
        idx: Index of item in the source list (for result reconstruction)

    Returns:
        Dict with fields for Rust BibItemData struct
    """

    # Title
    if isinstance(item.title, BibStringAttr):
        title = item.title.simplified
    else:
        title = ""

    # Author
    author = format_author(item.author, "simplified")

    # Year
    year = None
    if isinstance(item.date, BibItemDateAttr):
        year = item.date.year

    # Journal
    journal = None
    if item.journal:
        journal = item.journal.name.simplified

    # Volume, Number, Pages (volume and number are on BibItem, not Journal)
    volume = item.volume if item.volume else None
    number = item.number if item.number else None
    pages = None
    if item.pages and len(item.pages) > 0:
        # pages is a tuple of PageAttr objects, take the first one
        first_page = item.pages[0]
        if first_page.end:
            pages = f"{first_page.start}--{first_page.end}"
        else:
            pages = first_page.start

    # Publisher
    publisher = None
    if item.publisher and isinstance(item.publisher, BibStringAttr):
        publisher = item.publisher.simplified

    return {
        "index": idx,
        "title": title,
        "author": author,
        "year": year,
        "doi": item.doi,
        "journal": journal,
        "volume": volume,
        "number": number,
        "pages": pages,
        "publisher": publisher,
    }


def _find_similar_batch_rust(
    subjects: Sequence[BibItem],
    candidates: Sequence[BibItem],
    top_n: int,
    min_score: float,
    weights: FuzzyMatchWeights | None = None,
) -> list[Tuple[Match, ...]]:
    """Batch find similar items using Rust scorer.

    Scores all subjects against all candidates in parallel using Rust.

    Args:
        subjects: Sequence of BibItems to find matches for
        candidates: Sequence of candidate BibItems to match against
        top_n: Number of top matches per subject
        min_score: Minimum score threshold
        weights: Weights for scoring components (default: title=0.5, author=0.3, date=0.1, bonus=0.1)

    Returns:
        List of Match tuples, one per subject
    """

    if not _RUST_SCORER_AVAILABLE:
        raise RuntimeError("Rust scorer not available")

    resolved_weights = weights if weights is not None else DEFAULT_FUZZY_MATCH_WEIGHTS
    w_title = resolved_weights["title"]
    w_author = resolved_weights["author"]
    w_date = resolved_weights["date"]
    w_bonus = resolved_weights["bonus"]

    # Prepare data for Rust
    subjects_data = [_prepare_bibitem_for_rust_scorer(s, i) for i, s in enumerate(subjects)]
    candidates_data = [_prepare_bibitem_for_rust_scorer(c, i) for i, c in enumerate(candidates)]

    # Call Rust batch scorer — pass weights as dict (matches Rust Weights struct via FromPyObject)
    results = rust_scorer.score_batch(subjects_data, candidates_data, top_n, min_score, resolved_weights)

    # Reconstruct Match objects
    all_matches: list[Tuple[Match, ...]] = []

    for result in results:
        matches: list[Match] = []
        result_matches = result["matches"]
        for rank, match_result in enumerate(result_matches, start=1):
            cand_idx = match_result["candidate_index"]
            title_score = match_result["title_score"]
            author_score = match_result["author_score"]
            date_score = match_result["date_score"]
            bonus_score = match_result["bonus_score"]
            total_score = match_result["total_score"]

            candidate = candidates[cand_idx]

            # Create PartialScore objects from Rust scores
            partial_scores = (
                PartialScore(
                    component=ScoreComponent.TITLE,
                    score=int(title_score / w_title) if title_score > 0 and w_title > 0 else 0,
                    weight=w_title,
                    weighted_score=title_score,
                    details="[rust]",
                ),
                PartialScore(
                    component=ScoreComponent.AUTHOR,
                    score=int(author_score / w_author) if author_score > 0 and w_author > 0 else 0,
                    weight=w_author,
                    weighted_score=author_score,
                    details="[rust]",
                ),
                PartialScore(
                    component=ScoreComponent.DATE,
                    score=int(date_score / w_date) if date_score > 0 and w_date > 0 else 0,
                    weight=w_date,
                    weighted_score=date_score,
                    details="[rust]",
                ),
                PartialScore(
                    component=ScoreComponent.PUBLISHER,  # Using PUBLISHER as generic bonus component
                    score=int(bonus_score / w_bonus) if bonus_score > 0 and w_bonus > 0 else 0,
                    weight=w_bonus,
                    weighted_score=bonus_score,
                    details="[rust]",
                ),
            )

            matches.append(
                Match(
                    bibkey=format_bibkey(candidate.bibkey),
                    matched_bibitem=candidate,
                    total_score=total_score,
                    partial_scores=partial_scores,
                    rank=rank,
                )
            )

        all_matches.append(tuple(matches))

    return all_matches


def _get_candidate_set(subject: BibItem, index: BibItemBlockIndex) -> FrozenSet[BibItem]:
    """Get candidate items from index using multiple lookup strategies.

    Combines results from multiple indexes to create a candidate set that's
    much smaller than the full bibliography but still comprehensive.

    Args:
        subject: BibItem to find candidates for
        index: BibItemBlockIndex to search

    Returns:
        Frozen set of candidate BibItems (typically 0.5-2% of total)
    """
    candidates: set[BibItem] = set()

    # Check DOI first (instant exact match)
    if subject.doi and subject.doi in index.doi_index:
        return frozenset([index.doi_index[subject.doi]])

    # Title trigrams
    title_attr = subject.title
    if isinstance(title_attr, BibStringAttr):
        subject_trigrams = _extract_trigrams(title_attr.simplified)
        for trigram in subject_trigrams:
            if trigram in index.title_trigrams:
                candidates.update(index.title_trigrams[trigram])

    # Author surnames
    subject_surnames = _extract_author_surnames(subject.author)
    for surname in subject_surnames:
        if surname in index.author_surnames:
            candidates.update(index.author_surnames[surname])

    # Year decades (±5 decades = ±50 years for safety)
    subject_decade = _get_decade(subject.date)
    if subject_decade is not None:
        for offset in range(-5, 6):
            decade = subject_decade + (offset * 10)
            if decade in index.year_decades:
                candidates.update(index.year_decades[decade])
    else:
        # No date: include all items with no date
        if None in index.year_decades:
            candidates.update(index.year_decades[None])

    # Journal
    if subject.journal:
        journal_name_attr = subject.journal.name
        if isinstance(journal_name_attr, BibStringAttr):
            journal_name = remove_extra_whitespace(journal_name_attr.simplified).lower()
            if journal_name and journal_name in index.journals:
                candidates.update(index.journals[journal_name])

    # Fallback: if no candidates found, use all items (rare but safe)
    if not candidates:
        return frozenset(index.all_items)

    return frozenset(candidates)


def stage_bibitems_batch(
    bibitems: Sequence[BibItem],
    index: BibItemBlockIndex,
    top_n: int = 5,
    min_score: float = 0.0,
    weights: FuzzyMatchWeights | None = None,
) -> Tuple[BibItemStaged, ...]:
    """Stage multiple BibItems in batch using Rust parallel scorer.

    Processes all items in parallel for significant speedup (10-100x on large batches).

    Args:
        bibitems: Sequence of BibItems to stage
        index: Pre-built BibItemBlockIndex
        top_n: Number of top matches per item (default: 5)
        min_score: Minimum score threshold (default: 0.0)
        weights: Weights for scoring components (default: title=0.4, author=0.3, date=0.05, bonus=0.25)

    Returns:
        Tuple of BibItemStaged objects

    Raises:
        RuntimeError: If Rust scorer is not available
    """
    if not _RUST_SCORER_AVAILABLE:
        raise RuntimeError("Rust scorer not available. Rebuild with: maturin develop --release")

    start_time = time.perf_counter()
    all_matches = _find_similar_batch_rust(bibitems, index.all_items, top_n, min_score, weights=weights)
    end_time = time.perf_counter()

    # Create BibItemStaged objects
    total_time_ms = int((end_time - start_time) * 1000)
    time_per_item = total_time_ms // len(bibitems) if bibitems else 0

    return tuple(
        BibItemStaged(
            bibitem=bibitem,
            top_matches=matches,
            search_metadata={
                "search_time_ms": time_per_item,
                "candidates_searched": len(index.all_items),
                "scorer": "rust",
            },
        )
        for bibitem, matches in zip(bibitems, all_matches)
    )


def stage_bibitems_streaming(
    bibitems: Sequence[BibItem],
    index: BibItemBlockIndex,
    top_n: int = 5,
    min_score: float = 0.0,
    weights: FuzzyMatchWeights | None = None,
    batch_size: int = 100,
) -> Iterator[BibItemStaged]:
    """Stage multiple BibItems with streaming results.

    Yields BibItemStaged objects as they're processed in batches,
    enabling real-time progress monitoring and immediate CSV output.

    Args:
        bibitems: Sequence of BibItems to stage
        index: Pre-built BibItemBlockIndex
        top_n: Number of top matches per item (default: 5)
        min_score: Minimum score threshold (default: 0.0)
        weights: Weights for scoring components (default: title=0.4, author=0.3, date=0.05, bonus=0.25)
        batch_size: Number of items to process per batch (default: 100)

    Yields:
        BibItemStaged objects as they're processed
    """
    # Convert to list for slicing
    items_list = list(bibitems)

    # Process in batches and yield individual results
    for i in range(0, len(items_list), batch_size):
        batch = items_list[i : i + batch_size]
        batch_results = stage_bibitems_batch(batch, index, top_n, min_score, weights=weights)
        yield from batch_results


# --- Index Caching ---


def save_index(index: BibItemBlockIndex, cache_path: Path) -> None:
    """Save index to pickle file for later reuse.

    Args:
        index: BibItemBlockIndex to save
        cache_path: Path to save the pickle file
    """
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump(index, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_index(cache_path: Path) -> BibItemBlockIndex | None:
    """Load index from pickle file if exists and valid.

    Args:
        cache_path: Path to the pickle file

    Returns:
        BibItemBlockIndex if successfully loaded, None otherwise
    """
    if not cache_path.exists():
        return None
    try:
        with open(cache_path, "rb") as f:
            loaded = pickle.load(f)
        if not isinstance(loaded, BibItemBlockIndex):
            raise TypeError(
                f"Cached index at {cache_path} contains {type(loaded).__name__}, " f"expected BibItemBlockIndex"
            )
        return loaded
    except TypeError:
        raise
    except Exception:
        return None


def build_index_cached(
    bibitems: Sequence[BibItem],
    cache_path: Path | None = None,
    force_rebuild: bool = False,
) -> BibItemBlockIndex:
    """Build index with optional caching to avoid rebuilding.

    If cache_path is provided and a valid cached index exists, it will be loaded
    instead of rebuilding. Otherwise, builds the index and optionally saves it.

    Args:
        bibitems: Sequence of BibItems to index
        cache_path: Optional path to cache the index (pickle file)
        force_rebuild: If True, rebuild index even if cache exists

    Returns:
        BibItemBlockIndex (either from cache or freshly built)
    """
    # Try loading from cache first
    if cache_path and not force_rebuild:
        cached = load_index(cache_path)
        if cached is not None:
            return cached

    # Build fresh index
    index = build_index(bibitems)

    # Save to cache if path provided
    if cache_path:
        save_index(index, cache_path)

    return index
