"""
Scrapes an entire journal by ISSN and year ranges.
"""

import os
import csv
import attrs
from typing_extensions import Literal
from philoch_bib_sdk.logic.models import BibItem
from philoch_bib_sdk.converters.plaintext.bibitem.formatter import format_bibitem, FormattedBibItem
from aletk.ResultMonad import main_try_except_wrapper
from aletk.utils import get_logger, lginf

from philoch_bib_enhancer.adapters.crossref.crossref_client import CrossrefClient
from philoch_bib_enhancer.adapters.crossref.crossref_models import ParsedResult, ParsingSuccess, is_parsing_success
from philoch_bib_enhancer.adapters.crossref import crossref_bibitem_gateway

from philoch_bib_sdk.adapters.tabular_data.read_journal_volume_number_index import ColumnNames, hof_read_from_ods
from philoch_bib_sdk.logic.functions.journal_article_matcher import (
    TJournalBibkeyIndex,
    get_bibkey_by_journal_volume_number,
)

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

TSupportedTabularBibliographyFormat = Literal["ods"]


class JournalScraperBibkeyMatchingTabular(BaseModel):
    bibliography_path: str
    bibliography_format: TSupportedTabularBibliographyFormat
    column_names: ColumnNames

    @classmethod
    def validate_bibliography_path(cls, raw_path: str) -> str:
        path = remove_extra_whitespace(raw_path)
        if not path:
            raise ValueError("Bibliography path cannot be empty.")
        return path

    @classmethod
    def validate_column_names(cls, column_names: ColumnNames) -> ColumnNames:
        """
        Validates that none of the column names are empty.
        """
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


def jvn_match_parsing_result(
    index: TJournalBibkeyIndex,
    parsed_result: ParsedResult[BibItem],
) -> ParsedResult[BibItem]:
    """
    Matches the parsed result with the journal volume number index.
    """
    if not is_parsing_success(parsed_result):
        return parsed_result

    bibitem = parsed_result["out"]

    try:
        bibkey = get_bibkey_by_journal_volume_number(index, bibitem)
        if bibkey is None:
            lgr.warning(
                f"Bibkey not found for journal volume number: {bibitem.journal}, {bibitem.volume}, {bibitem.number}"
            )
            return {
                "parsing_status": "success",
                "out": bibitem,
            }

        updated = attrs.evolve(
            bibitem,
            bibkey=bibkey,
        )
        return {
            "parsing_status": "success",
            "out": updated,
        }

    except KeyError as e:
        lgr.warning(f"Bibkey not found for journal volume number: {e}")

    return {
        "parsing_status": "success",
        "out": bibitem,
    }


@main_try_except_wrapper(lgr)
def main(
    main_in: JournalScraperMainIN,
) -> None:

    journal_scraper_in, get_journal_articles = main_in.journal_scraper_in, main_in.get_journal_articles

    lgr.info(f"Scraping journal with ISSN {journal_scraper_in.issn} for years {journal_scraper_in.year_range}...")

    articles: Generator[ParsedResult[BibItem], None, None] = get_journal_articles(journal_scraper_in)

    bibkey_matching = journal_scraper_in.with_bibkey_matching

    match bibkey_matching:

        case JournalScraperBibkeyMatchingTabular(
            bibliography_path=path,
            bibliography_format=bib_format,
            column_names=column_names,
        ):

            lgr.info(f"Matching bibkeys using tabular data from {path} with format {bib_format}...")
            if bib_format != "ods":
                raise ValueError(
                    f"Unsupported bibliography format: {bib_format}. Only 'ods' is supported at the moment."
                )

            index = hof_read_from_ods(column_names)(path)
            lgr.info(f"Index loaded with {len(index)} entries.")
            articles = (jvn_match_parsing_result(index, parsed) for parsed in articles)
            lgr.info("Bibkey matching completed.")

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

    # TODO: Move write logic to a separate function
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

    frame = "cli"

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

    args = parser.parse_args()

    issn = args.issn
    year_range = (args.start_year, args.end_year)

    journal_scraper_in: JournalScraperIN

    CROSSREF_EMAIL = os.getenv("CROSSREF_EMAIL", None)

    crossref_client = setup_crossref_client(InitConfig(CROSSREF_EMAIL=CROSSREF_EMAIL))

    cr_gtw_cfg = crossref_bibitem_gateway.CrossrefGatewayConfig(client=crossref_client)
    cr_gtw = crossref_bibitem_gateway.configure(cr_gtw_cfg)

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

        journal_scraper_in = JournalScraperIN(
            issn=issn,
            year_range=year_range,
            with_bibkey_matching=JournalScraperBibkeyMatchingTabular(
                bibliography_path=args.bibliography_path,
                bibliography_format="ods",
                column_names=column_names,
            ),
        )

    else:
        journal_scraper_in = JournalScraperIN(
            issn=issn,
            year_range=year_range,
        )

    main_in = JournalScraperMainIN(
        journal_scraper_in=journal_scraper_in,
        get_journal_articles=cr_gtw.get_journal_articles,
    )

    main(main_in)


if __name__ == "__main__":
    cli()
