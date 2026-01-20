"""
CLI entry point for fuzzy matching BibItems against a bibliography.

This is the imperative shell: it handles all concrete decisions, side effects,
and dependency wiring. It parses arguments, loads data, sets up infrastructure,
and calls the fuzzy matching functions.

Uses Rust-accelerated scoring when available (12x faster than Python).
"""

import argparse
import csv
import time
from pathlib import Path

from aletk.ResultMonad import Err
from aletk.utils import get_logger, lginf

from philoch_bib_sdk.adapters.io.csv import load_staged_csv_allow_empty_bibkeys
from philoch_bib_sdk.adapters.io.ods import load_bibliography_ods, load_staged_ods
from philoch_bib_sdk.logic.functions.fuzzy_matcher import (
    build_index_cached,
    stage_bibitems_streaming,
    _RUST_SCORER_AVAILABLE,
)
from philoch_bib_sdk.logic.models import BibItem, BibStringAttr
from philoch_bib_sdk.logic.models_staging import BibItemStaged

lgr = get_logger(__file__)


# ============================================================================
# Constants
# ============================================================================

# Canonical column order (from ParsedBibItemData + extras)
BIBLIOGRAPHY_COLUMNS = [
    "_to_do_general",
    "_change_request",
    "entry_type",
    "bibkey",
    "author",
    "_author_ids",
    "editor",
    "_editor_ids",
    "author_ids",
    "options",
    "shorthand",
    "date",
    "pubstate",
    "title",
    "_title_unicode",
    "booktitle",
    "crossref",
    "journal",
    "journal_id",
    "volume",
    "number",
    "pages",
    "eid",
    "series",
    "address",
    "institution",
    "school",
    "publisher",
    "publisher_id",
    "type",
    "edition",
    "note",
    "_issuetitle",
    "_guesteditor",
    "_extra_note",
    "urn",
    "eprint",
    "doi",
    "url",
    "_kw_level1",
    "_kw_level2",
    "_kw_level3",
    "_epoch",
    "_person",
    "_comm_for_profile_bib",
    "_langid",
    "_lang_der",
    "_further_refs",
    "_depends_on",
    "_dltc_num",
    "_spec_interest",
    "_note_perso",
    "_note_stock",
    "_note_status",
    "_num_inwork_coll",
    "_num_inwork",
    "_num_coll",
    "_dltc_copyediting_note",
    "_note_missing",
    "_num_sort",
    "parsing_status",
    "message",
    "context",
]


# ============================================================================
# Infrastructure Setup (Imperative)
# ============================================================================


def _get_str(attr: BibStringAttr | str | None) -> str:
    """Helper to extract string from BibStringAttr or return empty string."""
    if isinstance(attr, BibStringAttr):
        return attr.simplified
    return str(attr) if attr else ""


def build_plaintext_citation(bibitem: BibItem) -> str:
    """Convert BibItem to human-readable citation string.

    Format: Author (Date). Title. Journal(Volume): Number, Pages. Publisher.
    """
    parts: list[str] = []

    # Author (Date) - include both family and given names
    author_str = ""
    if bibitem.author:
        author_names = []
        for auth in bibitem.author:
            family = _get_str(auth.family_name)
            given = _get_str(auth.given_name)
            if family and given:
                author_names.append(f"{family}, {given}")
            elif family:
                author_names.append(family)
        author_str = " and ".join(author_names) if author_names else ""

    date_str = ""
    if bibitem.date != "no date" and hasattr(bibitem.date, "year"):
        date_str = str(bibitem.date.year)

    if author_str and date_str:
        parts.append(f"{author_str} ({date_str})")
    elif author_str:
        parts.append(author_str)
    elif date_str:
        parts.append(f"({date_str})")

    # Title
    title_str = _get_str(bibitem.title)
    if title_str:
        parts.append(title_str)

    # Journal(Volume): Number, Pages
    journal_part: list[str] = []
    if bibitem.journal:
        journal_str = _get_str(bibitem.journal.name)
        if bibitem.volume:
            journal_str += f"({bibitem.volume})"
        if bibitem.number:
            journal_str += f": {bibitem.number}"
        if journal_str:
            journal_part.append(journal_str)

    if bibitem.pages:
        page_parts = []
        for page in bibitem.pages:
            if page.start and page.end:
                page_parts.append(f"{page.start}--{page.end}")
            elif page.start:
                page_parts.append(page.start)
        if page_parts:
            journal_part.append(", ".join(page_parts))

    if journal_part:
        parts.append(", ".join(journal_part))

    # Publisher
    publisher_str = _get_str(bibitem.publisher)
    if publisher_str:
        parts.append(publisher_str)

    return ". ".join(parts) + "." if parts else ""


def load_input_rows(file_path: Path) -> list[dict[str, str]]:
    """Load input CSV as raw dicts preserving all values."""
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_staged_from_file(file_path: Path) -> tuple[BibItem, ...]:
    """Load staged BibItems from CSV or ODS file."""
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        result = load_staged_csv_allow_empty_bibkeys(str(file_path))
        if isinstance(result, Err):
            raise ValueError(f"Failed to load CSV: {result.message}")
        return result.out
    elif suffix == ".ods":
        result = load_staged_ods(str(file_path))
        if isinstance(result, Err):
            raise ValueError(f"Failed to load ODS: {result.message}")
        return result.out
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Use .csv or .ods")


def load_bibliography_as_dict(file_path: Path) -> dict[str, BibItem]:
    """Load bibliography from ODS file as dict keyed by bibkey."""
    suffix = file_path.suffix.lower()
    if suffix != ".ods":
        raise ValueError(f"Bibliography must be .ods file, got: {suffix}")
    result = load_bibliography_ods(str(file_path))
    if isinstance(result, Err):
        raise ValueError(f"Failed to load ODS: {result.message}")
    return result.out


def build_output_row(
    input_row: dict[str, str],
    staged_item: BibItemStaged,
    plaintext_citations: dict[str, str],
    top_n: int,
) -> dict[str, str]:
    """Build a single output row from input row and staged match result."""
    output_row: dict[str, str] = {}

    # Start with bibliography columns from input (fill missing with empty)
    for col in BIBLIOGRAPHY_COLUMNS:
        output_row[col] = input_row.get(col, "")

    # Add match columns
    for j, match in enumerate(staged_item.top_matches[:top_n], start=1):
        output_row[f"match_{j}_bibkey"] = match.bibkey
        output_row[f"match_{j}_score"] = str(round(match.total_score, 2))
        output_row[f"match_{j}_full_entry"] = plaintext_citations.get(match.bibkey, "")

    # Fill remaining match slots with empty
    for j in range(len(staged_item.top_matches) + 1, top_n + 1):
        output_row[f"match_{j}_bibkey"] = ""
        output_row[f"match_{j}_score"] = ""
        output_row[f"match_{j}_full_entry"] = ""

    output_row["candidates_searched"] = str(staged_item.search_metadata.get("candidates_searched", 0))
    output_row["search_time_ms"] = str(round(staged_item.search_metadata.get("search_time_ms", 0), 1))

    return output_row


def get_output_columns(top_n: int) -> list[str]:
    """Get the full list of output columns including match columns."""
    match_columns: list[str] = []
    for i in range(1, top_n + 1):
        match_columns.extend([f"match_{i}_bibkey", f"match_{i}_score", f"match_{i}_full_entry"])
    match_columns.extend(["candidates_searched", "search_time_ms"])
    return BIBLIOGRAPHY_COLUMNS + match_columns


# ============================================================================
# CLI Argument Parsing
# ============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Fuzzy match BibItems against a bibliography using Rust-accelerated scoring."
    )

    parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Input file with BibItems to match (.csv or .ods).",
    )

    parser.add_argument(
        "--bibliography",
        "-b",
        type=str,
        required=True,
        help="Bibliography file to match against (.ods).",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        required=True,
        help="Output CSV file path for merged results.",
    )

    parser.add_argument(
        "--cache-dir",
        "-c",
        type=str,
        default="data/cache",
        help="Directory for index cache (default: data/cache).",
    )

    parser.add_argument(
        "--top-n",
        "-n",
        type=int,
        default=5,
        help="Number of top matches per item (default: 5).",
    )

    parser.add_argument(
        "--min-score",
        "-m",
        type=float,
        default=0.0,
        help="Minimum score threshold (default: 0.0).",
    )

    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Force rebuild of index cache.",
    )

    parser.add_argument(
        "--force-python",
        action="store_true",
        help="Force Python scorer (skip Rust even if available).",
    )

    return parser.parse_args()


# ============================================================================
# Main CLI Entry Point (Imperative Shell)
# ============================================================================


def cli() -> None:
    """
    Main CLI entry point - the imperative shell.

    This function:
    1. Parses CLI arguments
    2. Loads input BibItems (as raw rows and parsed BibItems)
    3. Loads bibliography as dict (for plaintext citations)
    4. Builds/loads index (cached)
    5. Runs fuzzy matching (Rust or Python)
    6. Writes merged CSV with all input columns + match results
    """
    frame = "cli"
    args = parse_args()

    # === VALIDATE PATHS ===
    input_path = Path(args.input)
    bib_path = Path(args.bibliography)
    output_path = Path(args.output)
    cache_dir = Path(args.cache_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not bib_path.exists():
        raise FileNotFoundError(f"Bibliography file not found: {bib_path}")

    # Create cache directory if needed
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{bib_path.stem}-index.pkl"

    # === REPORT CONFIGURATION ===
    use_rust = _RUST_SCORER_AVAILABLE and not args.force_python
    lginf(frame, f"Rust scorer: {'available' if _RUST_SCORER_AVAILABLE else 'not available'}", lgr)
    lginf(frame, f"Using: {'Rust' if use_rust else 'Python'} scorer", lgr)

    # === LOAD INPUT (raw rows + parsed BibItems) ===
    lginf(frame, f"Loading input from {input_path}...", lgr)
    start = time.perf_counter()
    input_rows = load_input_rows(input_path)
    subjects = load_staged_from_file(input_path)
    lginf(frame, f"Loaded {len(subjects)} items in {time.perf_counter() - start:.1f}s", lgr)

    # === LOAD BIBLIOGRAPHY (as dict for plaintext lookup) ===
    lginf(frame, f"Loading bibliography from {bib_path}...", lgr)
    start = time.perf_counter()
    bibliography_dict = load_bibliography_as_dict(bib_path)
    bibliography = tuple(bibliography_dict.values())
    lginf(frame, f"Loaded {len(bibliography)} bibliography items in {time.perf_counter() - start:.1f}s", lgr)

    # === BUILD/LOAD INDEX ===
    lginf(frame, f"Building/loading index (cache: {cache_path})...", lgr)
    start = time.perf_counter()
    index = build_index_cached(bibliography, cache_path=cache_path, force_rebuild=args.force_rebuild)
    lginf(frame, f"Index ready in {time.perf_counter() - start:.1f}s", lgr)

    # === BUILD PLAINTEXT CITATION LOOKUP ===
    plaintext_citations: dict[str, str] = {}
    for bibkey, bibitem in bibliography_dict.items():
        plaintext_citations[bibkey] = build_plaintext_citation(bibitem)

    # === RUN FUZZY MATCHING (STREAMING) ===
    total = len(subjects)
    lginf(frame, f"Running fuzzy matching ({total} subjects vs {len(index.all_items)} candidates)...", lgr)
    lginf(frame, f"Streaming results to {output_path} (use 'tail -f {output_path}' to monitor)", lgr)

    all_columns = get_output_columns(args.top_n)
    start = time.perf_counter()

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns)
        writer.writeheader()
        f.flush()

        for i, staged_item in enumerate(
            stage_bibitems_streaming(
                subjects,
                index,
                top_n=args.top_n,
                min_score=args.min_score,
            )
        ):
            output_row = build_output_row(input_rows[i], staged_item, plaintext_citations, args.top_n)
            writer.writerow(output_row)
            f.flush()  # Ensure immediate write to disk for tail -f

            # Progress logging every 10 items
            if (i + 1) % 10 == 0 or (i + 1) == total:
                elapsed = time.perf_counter() - start
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                lginf(frame, f"Processed {i + 1}/{total} items ({rate:.1f} items/s)", lgr)

    elapsed = time.perf_counter() - start
    lginf(frame, f"Done. Wrote {total} rows to {output_path} in {elapsed:.1f}s", lgr)


if __name__ == "__main__":
    cli()
