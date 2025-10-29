"""
CLI entry point for RawWebText scraping.

This is the imperative shell: it handles all concrete decisions, side effects,
and dependency wiring. It parses arguments, loads configurations, sets up
infrastructure, and calls the abstract orchestration layer.

Specifically implements web text scraping using LLM services (Claude or OpenAI).
"""

import os
import argparse
from dotenv import load_dotenv

from aletk.utils import get_logger, lginf, remove_extra_whitespace
from pydantic import BaseModel
from philoch_bib_sdk.adapters.tabular_data.read_journal_volume_number_index import ColumnNames

from philoch_bib_enhancer.adapters.raw_web_text import raw_web_text_gateway
from philoch_bib_enhancer.ports.llm_service import LLMService

# Reuse CSV writer from Crossref CLI
from philoch_bib_enhancer.cli.crossref_journal_scraping_cli import (
    write_articles_to_csv,
    create_bibkey_matcher,
)

# Load .env file at module import
load_dotenv()

lgr = get_logger(__file__)


# ============================================================================
# Configuration Models (Pydantic at boundary)
# ============================================================================


class InitConfig(BaseModel):
    """Environment configuration validation."""

    LLM_SERVICE: str  # "claude" or "openai"
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None

    @classmethod
    def validate_str_var(cls, var_name: str, value: str) -> str:
        stripped = remove_extra_whitespace(value)
        if not value or stripped == "":
            raise ValueError(f"Config string variable '{var_name}' is not set or is empty.")
        return stripped

    def __init__(self, **data: object) -> None:
        super().__init__(**data)
        if hasattr(self, "LLM_SERVICE"):
            self.LLM_SERVICE = self.validate_str_var("LLM_SERVICE", self.LLM_SERVICE)

        # Validate API keys based on LLM service
        if self.LLM_SERVICE == "claude":
            if not self.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY is required when LLM_SERVICE is 'claude'")
            self.ANTHROPIC_API_KEY = self.validate_str_var("ANTHROPIC_API_KEY", self.ANTHROPIC_API_KEY)
        elif self.LLM_SERVICE == "openai":
            if not self.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is required when LLM_SERVICE is 'openai'")
            self.OPENAI_API_KEY = self.validate_str_var("OPENAI_API_KEY", self.OPENAI_API_KEY)
        else:
            raise ValueError(f"Invalid LLM_SERVICE: {self.LLM_SERVICE}. Must be 'claude' or 'openai'")


# ============================================================================
# Infrastructure Setup (Imperative)
# ============================================================================


def load_env_vars() -> InitConfig:
    """Load environment variables from the environment directly."""
    llm_service = os.getenv("LLM_SERVICE", "claude")  # Default to Claude
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", None)
    openai_api_key = os.getenv("OPENAI_API_KEY", None)
    return InitConfig(
        LLM_SERVICE=llm_service,
        ANTHROPIC_API_KEY=anthropic_api_key,
        OPENAI_API_KEY=openai_api_key,
    )


def setup_llm_service(v: InitConfig) -> LLMService:
    """Setup LLM service with validated configuration."""
    if v.LLM_SERVICE == "claude":
        from philoch_bib_enhancer.adapters.llm.claude_llm_service import ClaudeLLMService

        assert v.ANTHROPIC_API_KEY is not None
        return ClaudeLLMService(api_key=v.ANTHROPIC_API_KEY)
    elif v.LLM_SERVICE == "openai":
        from philoch_bib_enhancer.adapters.llm.openai_llm_service import OpenAILLMService

        assert v.OPENAI_API_KEY is not None
        return OpenAILLMService(api_key=v.OPENAI_API_KEY)
    else:
        raise ValueError(f"Invalid LLM_SERVICE: {v.LLM_SERVICE}")


def load_urls_from_file(file_path: str) -> list[str]:
    """Load URLs from a file (one URL per line)."""
    with open(file_path, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]
    return urls


# ============================================================================
# CLI Argument Parsing
# ============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Scrape bibliographic data from web pages using LLMs.")

    parser.add_argument(
        "--urls",
        "-u",
        type=str,
        nargs="+",
        help="One or more URLs to scrape (space-separated).",
    )

    parser.add_argument(
        "--urls-file",
        "-f",
        type=str,
        help="Path to a file containing URLs (one per line).",
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
# Main CLI Entry Point (Imperative Shell)
# ============================================================================


def cli() -> None:
    """
    Main CLI entry point - the imperative shell.

    This function:
    1. Parses CLI arguments
    2. Validates input with Pydantic (boundary)
    3. Sets up infrastructure (imperative)
    4. Processes URLs and writes output
    """
    frame = "cli"
    args = parse_args()

    # === VALIDATE INPUT ===
    if not args.urls and not args.urls_file:
        raise ValueError("Either --urls or --urls-file must be provided")

    urls: list[str] = []
    if args.urls:
        urls.extend(args.urls)
    if args.urls_file:
        lgr.info(f"Loading URLs from file: {args.urls_file}")
        urls.extend(load_urls_from_file(args.urls_file))

    if not urls:
        raise ValueError("No URLs provided")

    lgr.info(f"Processing {len(urls)} URL(s)...")

    # === SETUP INFRASTRUCTURE (Imperative) ===
    env_config = load_env_vars()
    llm_service = setup_llm_service(env_config)
    lgr.info(f"Using LLM service: {env_config.LLM_SERVICE}")

    rw_gtw_cfg = raw_web_text_gateway.RawWebTextGatewayConfig(llm_service=llm_service)
    rw_gtw = raw_web_text_gateway.configure(rw_gtw_cfg)

    # === CREATE BIBKEY MATCHER IF NEEDED ===
    bibkey_matcher = None
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

        bibkey_matcher = create_bibkey_matcher(
            bibliography_path=args.bibliography_path,
            column_names=column_names,
        )

    # === PROCESS URLS ===
    articles = rw_gtw.get_bibitems_from_urls(urls)

    # Apply bibkey matching if configured
    if bibkey_matcher:
        lgr.info("Matching bibkeys against bibliography index...")
        articles = (bibkey_matcher(parsed) for parsed in articles)
        lgr.info("Bibkey matching completed.")

    # === WRITE OUTPUT ===
    lgr.info(f"Writing results to {args.output}...")
    write_articles_to_csv(articles, args.output)
    lgr.info(f"✓ Successfully wrote results to {args.output}")


if __name__ == "__main__":
    cli()
