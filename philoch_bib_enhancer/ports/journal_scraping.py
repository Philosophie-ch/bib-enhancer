"""
Abstract orchestration for journal scraping.

This module contains the core orchestration logic for scraping journals.
It defines abstract function signatures and coordinates the workflow,
but doesn't know about concrete implementations (no I/O details, no CSV format, etc.).

Concrete implementations are injected from the outside via function parameters.
"""

from typing import Callable, Generator, Tuple, Iterable, Literal
from pydantic import BaseModel
from aletk.ResultMonad import main_try_except_wrapper
from aletk.utils import get_logger, remove_extra_whitespace

from philoch_bib_sdk.logic.models import BibItem
from philoch_bib_sdk.adapters.tabular_data.read_journal_volume_number_index import ColumnNames
from philoch_bib_enhancer.adapters.crossref.crossref_models import ParsedResult

lgr = get_logger(__file__)


# ============================================================================
# Type Definitions
# ============================================================================

type TYearRange = Tuple[int, int]
type TJournalScraperOUT = Generator[ParsedResult[BibItem], None, None]
type TJournalScraperFunction = Callable[["JournalScraperIN"], TJournalScraperOUT]
type TBibkeyMatcher = Callable[[ParsedResult[BibItem]], ParsedResult[BibItem]]
type TArticleWriter = Callable[[Iterable[ParsedResult[BibItem]], str], None]


# ============================================================================
# Input Validation Models (Pydantic at boundary)
# ============================================================================


class JournalScraperBibkeyMatchingTabular(BaseModel):
    """
    Configuration for bibkey matching using tabular bibliography files.
    Validates input at the boundary.
    """

    bibliography_path: str
    bibliography_format: Literal["ods"]
    column_names: ColumnNames

    @classmethod
    def validate_bibliography_path(cls, raw_path: str) -> str:
        path = remove_extra_whitespace(raw_path)
        if not path:
            raise ValueError("Bibliography path cannot be empty.")
        return path

    @classmethod
    def validate_column_names(cls, column_names: ColumnNames) -> ColumnNames:
        """Validates that none of the column names are empty."""
        for name in column_names:
            if not name or remove_extra_whitespace(name) == "":
                raise ValueError(f"Column name '{name}' cannot be empty.")
        return column_names

    def __init__(self, **data: object) -> None:
        super().__init__(**data)
        if hasattr(self, "bibliography_path"):
            self.bibliography_path = self.validate_bibliography_path(self.bibliography_path)


class JournalScraperIN(BaseModel):
    """
    Input model for the journal scraper.
    Validates input at the boundary.
    """

    issn: str
    year_range: TYearRange
    with_bibkey_matching: JournalScraperBibkeyMatchingTabular | None = None

    @classmethod
    def validate_issn_not_empty(cls, raw_issn: str) -> str:
        issn = remove_extra_whitespace(raw_issn)
        if not issn:
            raise ValueError("ISSN cannot be empty.")
        return issn

    @classmethod
    def validate_year_range(cls, year_range: TYearRange) -> TYearRange:
        start_year, end_year = year_range
        if start_year > end_year:
            raise ValueError("Start year cannot be greater than end year.")
        return year_range

    def __init__(self, **data: object) -> None:
        super().__init__(**data)
        if hasattr(self, "issn"):
            self.issn = self.validate_issn_not_empty(self.issn)


class JournalScraperMainIN(BaseModel):
    """
    Main input model for the journal scraper.

    This model defines all the dependencies that the orchestration layer needs.
    All side-effectful operations are abstracted behind function signatures.
    """

    journal_scraper_in: JournalScraperIN
    get_journal_articles: TJournalScraperFunction
    match_bibkey: TBibkeyMatcher | None = None
    write_articles: TArticleWriter

    class Config:
        arbitrary_types_allowed = True


# ============================================================================
# Abstract Orchestration (Imperative but Abstract)
# ============================================================================


@main_try_except_wrapper(lgr)
def main(main_in: JournalScraperMainIN) -> None:
    """
    Main orchestration function for journal scraping.

    This function coordinates the workflow but doesn't know about concrete
    implementations. It's imperative for clarity, but abstract - it delegates
    all side effects to injected functions.

    Workflow:
    1. Fetch articles from external source (via injected function)
    2. Optionally match bibkeys (via injected function)
    3. Write results (via injected function)

    :param main_in: All dependencies injected via this parameter
    """
    journal_scraper_in = main_in.journal_scraper_in
    get_journal_articles = main_in.get_journal_articles
    match_bibkey = main_in.match_bibkey
    write_articles = main_in.write_articles

    lgr.info(f"Scraping journal with ISSN {journal_scraper_in.issn} " f"for years {journal_scraper_in.year_range}...")

    # Step 1: Fetch articles (delegated to injected function)
    articles = get_journal_articles(journal_scraper_in)

    # Step 2: Optionally match bibkeys (delegated to injected function)
    if match_bibkey:
        lgr.info("Matching bibkeys against bibliography index...")
        articles = (match_bibkey(parsed) for parsed in articles)
        lgr.info("Bibkey matching completed.")

    # Step 3: Write results (delegated to injected function)
    output_path = f"{journal_scraper_in.issn}_articles.csv"
    lgr.info(f"Writing articles to {output_path}...")
    write_articles(articles, output_path)

    lgr.info(f"✓ Successfully wrote articles to {output_path}")
