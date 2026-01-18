"""
CLI entry point for Crossref journal scraping.

This is the imperative shell: it handles all concrete decisions, side effects,
and dependency wiring. It parses arguments, loads configurations, sets up
infrastructure, and calls the abstract orchestration layer.

Specifically implements journal scraping using the Crossref API adapter.
"""

import os
import csv
import argparse
from typing import Iterable
from dotenv import load_dotenv

from aletk.utils import get_logger, lginf, remove_extra_whitespace
from pydantic import BaseModel
from philoch_bib_sdk.logic.models import BibItem
from philoch_bib_sdk.converters.plaintext.bibitem.formatter import format_bibitem, FormattedBibItem
from philoch_bib_sdk.adapters.tabular_data.read_journal_volume_number_index import ColumnNames, hof_read_from_ods

from philoch_bib_enhancer.adapters.crossref.crossref_client import CrossrefClient
from philoch_bib_enhancer.adapters.crossref import crossref_bibitem_gateway
from philoch_bib_enhancer.domain.bibkey_matching import match_bibkey_to_article
from philoch_bib_enhancer.domain.parsing_result import ParsedResult
from philoch_bib_enhancer.ports.journal_scraping import (
    main,
    JournalScraperMainIN,
    JournalScraperIN,
    JournalScraperBibkeyMatchingTabular,
    TBibkeyMatcher,
)

# Load .env file at module import
load_dotenv()

lgr = get_logger(__file__)


# ============================================================================
# Configuration Models (Pydantic at boundary)
# ============================================================================


class InitConfig(BaseModel):
    """Environment configuration validation."""

    CROSSREF_EMAIL: str

    @classmethod
    def validate_str_var(cls, var_name: str, value: str) -> str:
        stripped = remove_extra_whitespace(value)
        if not value or stripped == "":
            raise ValueError(f"Config string variable '{var_name}' is not set or is empty.")
        return stripped

    def __init__(self, **data: object) -> None:
        super().__init__(**data)
        if hasattr(self, "CROSSREF_EMAIL"):
            self.CROSSREF_EMAIL = self.validate_str_var("CROSSREF_EMAIL", self.CROSSREF_EMAIL)


# ============================================================================
# Infrastructure Setup (Imperative)
# ============================================================================


def load_env_vars() -> InitConfig:
    """Load environment variables from the environment directly."""
    crossref_email = os.getenv("CROSSREF_EMAIL", None)
    return InitConfig(CROSSREF_EMAIL=crossref_email)


def setup_crossref_client(v: InitConfig) -> CrossrefClient:
    """Setup Crossref client with validated configuration."""
    return CrossrefClient(email=v.CROSSREF_EMAIL)


# ============================================================================
# Concrete Implementations (Imperative)
# ============================================================================


def write_articles_to_csv(
    articles: Iterable[ParsedResult[BibItem]],
    output_path: str,
) -> None:
    """
    Concrete CSV writer implementation.

    Imperative implementation is fine here - it's clear, straightforward,
    and easy to maintain.
    """
    flat_res = (
        {
            **(
                format_bibitem(parsed["out"])
                if parsed["parsing_status"] == "success"
                else {k: "" for k in FormattedBibItem.__required_keys__}
            ),
            "parsing_status": parsed["parsing_status"],
            "message": parsed.get("message", ""),
            "context": parsed.get("context", ""),
        }
        for parsed in articles
    )

    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        first = next(flat_res, None)
        if first is None:
            lgr.warning("No articles found for the given ISSN and year range.")
            return

        fieldnames = list(first.keys())
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(first)
        for row in flat_res:
            writer.writerow(row)


def create_bibkey_matcher(
    bibliography_path: str,
    column_names: ColumnNames,
) -> TBibkeyMatcher:
    """
    Create a bibkey matcher function by loading an ODS index.

    Imperative implementation: loads file, creates closure over index.
    """
    lgr.info(f"Loading bibkey index from {bibliography_path}...")
    index = hof_read_from_ods(column_names)(bibliography_path)
    lgr.info(f"Index loaded with {len(index)} entries.")

    # Return a matcher function (closure over index)
    def matcher(parsed: ParsedResult[BibItem]) -> ParsedResult[BibItem]:
        result = match_bibkey_to_article(index, parsed)
        # Log only if bibkey was not found (optional logging in shell)
        if result["parsing_status"] == "success":
            bibitem = result["out"]
            if not bibitem.bibkey and parsed["parsing_status"] == "success":
                lgr.warning(f"Bibkey not found for: {bibitem.journal}, vol {bibitem.volume}, num {bibitem.number}")
        return result

    return matcher


# ============================================================================
# CLI Argument Parsing
# ============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Scrape a journal by ISSN and year range.")

    parser.add_argument(
        "--issn",
        "-i",
        type=str,
        required=True,
        help="The ISSN of the journal to scrape.",
    )

    parser.add_argument(
        "--start-year",
        "-s",
        type=int,
        required=True,
        help="The start year of the range to scrape.",
    )

    parser.add_argument(
        "--end-year",
        "-e",
        type=int,
        required=True,
        help="The end year of the range to scrape.",
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
# Main CLI Entry Point (Imperative Shell)
# ============================================================================


def cli() -> None:
    """
    Main CLI entry point - the imperative shell.

    This function:
    1. Parses CLI arguments
    2. Validates input with Pydantic (boundary)
    3. Sets up infrastructure (imperative)
    4. Wires concrete implementations (imperative)
    5. Calls the abstract orchestration layer
    """
    frame = "cli"
    args = parse_args()

    # === VALIDATE INPUT (Pydantic at boundary) ===
    issn = args.issn
    year_range = (args.start_year, args.end_year)

    journal_scraper_in: JournalScraperIN
    bibkey_matching_config = None

    if args.bibliography_path:
        column_names = ColumnNames(
            bibkey=args.column_name_bibkey,
            journal=args.column_name_journal,
            volume=args.column_name_volume,
            number=args.column_name_number,
        )

        lginf(
            frame,
            f"Using tabular bibliography for bibkey matching with path '{args.bibliography_path}' and columns {column_names}",
            lgr,
        )

        bibkey_matching_config = JournalScraperBibkeyMatchingTabular(
            bibliography_path=args.bibliography_path,
            bibliography_format="ods",
            column_names=column_names,
        )

        journal_scraper_in = JournalScraperIN(
            issn=issn,
            year_range=year_range,
            with_bibkey_matching=bibkey_matching_config,
        )
    else:
        journal_scraper_in = JournalScraperIN(
            issn=issn,
            year_range=year_range,
        )

    # === SETUP INFRASTRUCTURE (Imperative) ===
    env_config = load_env_vars()
    crossref_client = setup_crossref_client(env_config)

    cr_gtw_cfg = crossref_bibitem_gateway.CrossrefGatewayConfig(client=crossref_client)
    cr_gtw = crossref_bibitem_gateway.configure(cr_gtw_cfg)

    # === CREATE CONCRETE IMPLEMENTATIONS (Imperative) ===
    bibkey_matcher: TBibkeyMatcher | None = None
    if bibkey_matching_config:
        bibkey_matcher = create_bibkey_matcher(
            bibliography_path=bibkey_matching_config.bibliography_path,
            column_names=bibkey_matching_config.column_names,
        )

    # === SETUP OUTPUT DIRECTORY ===
    output_dir = os.getenv("SCRAPE_JOURNAL_OUTPUT_DIR", ".")
    # Ensure output directory exists
    if output_dir != ".":
        os.makedirs(output_dir, exist_ok=True)
        lgr.info(f"Output directory: {output_dir}")

    # === WIRE DEPENDENCIES AND CALL ORCHESTRATOR ===
    main_in = JournalScraperMainIN(
        journal_scraper_in=journal_scraper_in,
        get_journal_articles=cr_gtw.get_journal_articles,
        match_bibkey=bibkey_matcher,
        write_articles=write_articles_to_csv,
        output_dir=output_dir,
    )

    main(main_in)


if __name__ == "__main__":
    cli()
