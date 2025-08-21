"""
Scrapes an entire journal by ISSN and year ranges.
"""

import os
import csv
from philoch_bib_sdk.logic.models import BibItem
from philoch_bib_sdk.converters.plaintext.bibitem.formatter import format_bibitem, FormattedBibItem
from aletk.ResultMonad import main_try_except_wrapper
from aletk.utils import get_logger

from philoch_bib_enhancer.adapters.crossref.crossref_client import CrossrefClient
from philoch_bib_enhancer.adapters.crossref.crossref_models import ParsedResult
from philoch_bib_enhancer.adapters.crossref import crossref_bibitem_gateway

lgr = get_logger(__file__)


### Put in a setup function on initialization
from typing import Callable, Generator, Tuple
from pydantic import BaseModel
from aletk.utils import remove_extra_whitespace


class InitConfig(BaseModel):
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


def load_env_vars() -> InitConfig:
    """
    Load environment variables from the environment directly.
    """
    import os

    crossref_email = os.getenv("CROSSREF_EMAIL", None)

    return InitConfig(CROSSREF_EMAIL=crossref_email)


###


### In another file where we setup cr infrastructure
def setup_crossref_client(v: InitConfig) -> CrossrefClient:
    return CrossrefClient(
        email=v.CROSSREF_EMAIL,
    )


###


type TYearRange = Tuple[int, int]


class JournalScraperIN(BaseModel):
    """
    Input model for the journal scraper.
    """

    issn: str
    year_range: TYearRange

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


type TJournalScraperOUT = Generator[
    ParsedResult[BibItem],
    None,
    None,
]

type TJournalScraperFunction = Callable[[JournalScraperIN], TJournalScraperOUT]


class JournalScraperMainIN(BaseModel):
    """
    Main input model for the journal scraper.
    """

    journal_scraper_in: JournalScraperIN
    get_journal_articles: TJournalScraperFunction


@main_try_except_wrapper(lgr)
def main(
    main_in: JournalScraperMainIN,
) -> None:

    journal_scraper_in, get_journal_articles = main_in.journal_scraper_in, main_in.get_journal_articles

    lgr.info(f"Scraping journal with ISSN {journal_scraper_in.issn} for years {journal_scraper_in.year_range}...")

    articles = get_journal_articles(journal_scraper_in)

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

    with open(f"{journal_scraper_in.issn}_articles.csv", "w", newline="", encoding="utf-8") as csvfile:
        first = next(flat_res, None)
        if first is None:
            lgr.warning("No articles found for the given ISSN and year range.")
            return

        fieldnames = list(first.keys()) if first else []
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(first)
        for row in flat_res:
            writer.writerow(row)


def cli() -> None:
    import argparse

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

    args = parser.parse_args()

    issn = args.issn
    year_range = (args.start_year, args.end_year)

    journal_scraper_in = JournalScraperIN(issn=issn, year_range=year_range)

    CROSSREF_EMAIL = os.getenv("CROSSREF_EMAIL", None)

    crossref_client = setup_crossref_client(InitConfig(CROSSREF_EMAIL=CROSSREF_EMAIL))

    cr_gtw_cfg = crossref_bibitem_gateway.CrossrefGatewayConfig(client=crossref_client)
    cr_gtw = crossref_bibitem_gateway.configure(cr_gtw_cfg)

    main_in = JournalScraperMainIN(
        journal_scraper_in=journal_scraper_in,
        get_journal_articles=cr_gtw.get_journal_articles,
    )

    main(main_in)


if __name__ == "__main__":
    cli()
