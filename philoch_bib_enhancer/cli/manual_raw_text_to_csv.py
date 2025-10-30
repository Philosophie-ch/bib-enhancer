"""
Manual workflow for converting RawTextBibitem objects to CSV.

This script enables a workflow where:
1. Text is extracted from web pages (manually or via web_scraper)
2. User (e.g., Claude) manually creates RawTextBibitem objects in Python
3. This script converts them to BibItem and outputs to CSV

This bypasses the LLM service entirely, allowing for manual data extraction
or using external LLM tools.

Usage as a library:
    from philoch_bib_enhancer.cli.manual_raw_text_to_csv import process_raw_bibitems
    from philoch_bib_enhancer.adapters.raw_text.raw_text_models import RawTextBibitem

    # Create RawTextBibitem objects directly
    raw_bibitems = [
        RawTextBibitem(
            title="Some Article",
            authors=[{"given": "John", "family": "Doe"}],
            year=2024,
            ...
        ),
        ...
    ]

    # Convert to CSV
    process_raw_bibitems(
        raw_bibitems=raw_bibitems,
        output_path="output.csv",
        bibliography_path=None,  # Optional
    )

Usage as a CLI (with JSON file):
    python -m philoch_bib_enhancer.cli.manual_raw_text_to_csv -i input.json -o output.csv
"""

import json
import argparse
from typing import Iterable

from aletk.utils import get_logger
from philoch_bib_sdk.logic.models import BibItem
from philoch_bib_sdk.adapters.tabular_data.read_journal_volume_number_index import ColumnNames

from philoch_bib_enhancer.adapters.raw_text.raw_text_models import RawTextBibitem
from philoch_bib_enhancer.adapters.raw_text.raw_text_converter import convert_raw_text_to_bibitem
from philoch_bib_enhancer.domain.parsing_result import ParsedResult

# Reuse CSV writer from Crossref CLI
from philoch_bib_enhancer.cli.crossref_journal_scraping_cli import (
    write_articles_to_csv,
    create_bibkey_matcher,
)

lgr = get_logger(__file__)


# ============================================================================
# Core Logic
# ============================================================================


def load_raw_bibitems_from_json(file_path: str) -> list[RawTextBibitem]:
    """
    Load RawTextBibitem objects from a JSON file.

    The JSON file should contain either:
    - A single RawTextBibitem object
    - An array of RawTextBibitem objects

    Returns:
        List of RawTextBibitem objects (validated with Pydantic)
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle both single object and array
    if isinstance(data, list):
        return [RawTextBibitem.model_validate(item) for item in data]
    else:
        return [RawTextBibitem.model_validate(data)]


def convert_raw_bibitems_to_parsed_results(
    raw_bibitems: list[RawTextBibitem],
) -> Iterable[ParsedResult[BibItem]]:
    """
    Convert a list of RawTextBibitem objects to ParsedResult[BibItem].

    This is a generator for consistency with the gateway pattern.

    Args:
        raw_bibitems: List of RawTextBibitem objects

    Yields:
        ParsedResult[BibItem] for each input (either success or error)
    """
    for raw_bibitem in raw_bibitems:
        yield convert_raw_text_to_bibitem(raw_bibitem)


# ============================================================================
# Main Processing Function (Can be used as library)
# ============================================================================


def process_raw_bibitems(
    raw_bibitems: list[RawTextBibitem],
    output_path: str,
    bibliography_path: str | None = None,
    column_names: ColumnNames | None = None,
) -> None:
    """
    Process RawTextBibitem objects and write to CSV.

    This function can be used directly as a library, bypassing the CLI.
    Useful for programmatic usage where RawTextBibitem objects are
    created directly in Python code.

    Args:
        raw_bibitems: List of RawTextBibitem objects to process
        output_path: Path to output CSV file
        bibliography_path: Optional path to ODS file for bibkey matching
        column_names: Optional column names for bibkey matching (required if bibliography_path is set)
    """
    lgr.info(f"Processing {len(raw_bibitems)} RawTextBibitem object(s)...")

    # === CONVERT TO BIBITEMS ===
    lgr.info("Converting to BibItem objects...")
    articles = convert_raw_bibitems_to_parsed_results(raw_bibitems)

    # === CREATE BIBKEY MATCHER IF NEEDED ===
    if bibliography_path:
        if not column_names:
            # Use defaults
            column_names = ColumnNames(
                bibkey="bibkey",
                journal="journal",
                volume="volume",
                number="number",
            )

        lgr.info(f"Using tabular bibliography for bibkey matching: {bibliography_path}")

        bibkey_matcher = create_bibkey_matcher(
            bibliography_path=bibliography_path,
            column_names=column_names,
        )

        lgr.info("Matching bibkeys against bibliography index...")
        articles = (bibkey_matcher(parsed) for parsed in articles)
        lgr.info("Bibkey matching completed.")

    # === WRITE OUTPUT ===
    lgr.info(f"Writing results to {output_path}...")
    write_articles_to_csv(articles, output_path)
    lgr.info(f"✓ Successfully wrote results to {output_path}")


# ============================================================================
# CLI Argument Parsing
# ============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Convert RawTextBibitem JSON to CSV (manual workflow).")

    parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Path to JSON file containing RawTextBibitem object(s).",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        required=True,
        help="Output CSV file path.",
    )

    parser.add_argument(
        "--column-name-bibkey",
        "-cb",
        type=str,
        default="bibkey",
        help="The name of the column containing the bibkey in the tabular bibliography file.",
    )

    parser.add_argument(
        "--column-name-journal",
        "-cj",
        type=str,
        default="journal",
        help="The name of the column containing the journal name in the tabular bibliography file.",
    )

    parser.add_argument(
        "--column-name-volume",
        "-cv",
        type=str,
        default="volume",
        help="The name of the column containing the volume in the tabular bibliography file.",
    )

    parser.add_argument(
        "--column-name-number",
        "-cn",
        type=str,
        default="number",
        help="The name of the column containing the number in the tabular bibliography file.",
    )

    parser.add_argument(
        "--bibliography-path",
        "-b",
        type=str,
        help="The path to the tabular bibliography file in ODS format.",
        required=False,
    )

    return parser.parse_args()


# ============================================================================
# Main CLI Entry Point
# ============================================================================


def cli() -> None:
    """
    Main CLI entry point for manual workflow.

    This function:
    1. Loads RawTextBibitem objects from JSON
    2. Calls process_raw_bibitems() to handle the rest
    """
    args = parse_args()

    # === LOAD INPUT ===
    lgr.info(f"Loading RawTextBibitem objects from {args.input}...")
    raw_bibitems = load_raw_bibitems_from_json(args.input)
    lgr.info(f"Loaded {len(raw_bibitems)} item(s)")

    # === SETUP COLUMN NAMES ===
    column_names = None
    if args.bibliography_path:
        column_names = ColumnNames(
            bibkey=args.column_name_bibkey,
            journal=args.column_name_journal,
            volume=args.column_name_volume,
            number=args.column_name_number,
        )

    # === PROCESS ===
    process_raw_bibitems(
        raw_bibitems=raw_bibitems,
        output_path=args.output,
        bibliography_path=args.bibliography_path,
        column_names=column_names,
    )


if __name__ == "__main__":
    cli()
