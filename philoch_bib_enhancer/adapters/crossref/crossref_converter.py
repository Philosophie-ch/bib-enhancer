from typing import Any, Dict, Literal, Tuple
from philoch_bib_sdk.logic.models import (
    BibItem,
)
from philoch_bib_sdk.logic.default_models import (
    AuthorArgs,
    BibStringArgs,
    JournalArgs,
)

from philoch_bib_enhancer.adapters.crossref.crossref_models import CrossrefArticle, ParsedResult
from philoch_bib_sdk.logic.default_models import BibItemArgs, BibItemDateArgs, PageArgs, default_bib_item


def _convert_raw_crossref_response_to_crossref_article(raw_object: Dict[Any, Any]) -> CrossrefArticle:
    """
    Convert a raw Crossref response object to a CrossrefArticle model.

    :param raw_object: The raw response object from Crossref.
    :return: An instance of CrossrefArticle.
    """
    return CrossrefArticle(**raw_object)


def convert_raw_crossref_response_to_crossref_article(raw_object: Dict[Any, Any]) -> ParsedResult[CrossrefArticle]:
    """
    Convert a raw Crossref response object to a ParsedCrossrefArticle model.

    :param raw_object: The raw response object from Crossref.
    :return: An instance of ParsedCrossrefArticle with parsing status.
    """
    try:
        crossref_article = _convert_raw_crossref_response_to_crossref_article(raw_object)
        return {
            "out": crossref_article,
            "parsing_status": "success",
        }

    except Exception as e:
        return {
            "parsing_status": "error",
            "message": f"Failed to parse Crossref article: {e}",
            "context": raw_object.__str__(),
        }


def _convert_crossref_article_to_bibitem(crossref_article: CrossrefArticle) -> BibItem:
    """
    Convert a CrossrefArticle object into a BibItem instance.

    Raises:
        ValueError: If required Crossref fields are missing or invalid.
    """

    # Authors
    authors: Tuple[AuthorArgs, ...] = (
        tuple(
            {"given_name": {"latex": getattr(a, "given", "")}, "family_name": {"latex": getattr(a, "family", "")}}
            for a in crossref_article.author
        )
        if crossref_article.author
        else tuple()
    )

    # Title
    title: BibStringArgs = {"latex": " ".join(crossref_article.title) if crossref_article.title else ""}

    # Date
    date_parts: BibItemDateArgs | Literal["no date"] = "no date"

    if getattr(crossref_article, "issued", None) and getattr(crossref_article.issued, "date_parts", None):
        parts = (getattr(crossref_article.issued, "date_parts", None) or [[]])[0]
        if parts and parts[0]:
            try:
                date_parts = {
                    "year": parts[0],
                    # Ignore month and day
                }
            except Exception as e:
                raise ValueError(f"Invalid date parts for DOI {crossref_article.DOI}: {parts!r} ({e})")

    # Journal
    journal: JournalArgs
    if (
        crossref_article.container_title
        and crossref_article.container_title != []
        and crossref_article.container_title[0]
    ):
        issn_print = ""
        issn_electronic = ""
        if crossref_article.ISSN:
            for i, issn in enumerate(crossref_article.ISSN):
                if i == 0:
                    issn_print = issn
                elif i == 1:
                    issn_electronic = issn
        journal = {
            "name": {"latex": crossref_article.container_title[0]},
            "issn_print": issn_print,
            "issn_electronic": issn_electronic,
        }

    # Pages
    pages: Tuple[PageArgs, ...] = tuple()
    if crossref_article.page:
        if "-" in crossref_article.page:
            start, end = crossref_article.page.split("-", 1)
            pages = ({"start": start, "end": end},)
        else:
            pages = ({"start": crossref_article.page, "end": ""},)

    # Publisher
    publisher: BibStringArgs = {"latex": crossref_article.publisher} if crossref_article.publisher else {}

    bibitem_data: BibItemArgs = {
        "author": authors,
        "date": date_parts,
        "title": title,
        "journal": journal,
        "volume": crossref_article.volume or "",
        "number": crossref_article.issue or "",
        "pages": pages,
        "publisher": publisher,
        "doi": crossref_article.DOI if crossref_article.DOI else "",
        "url": crossref_article.URL or "",
        "_bib_info_source": "Crossref",
    }

    result = default_bib_item(**bibitem_data)

    return result


def convert_crossref_response_to_bibitem(raw_object: Dict[Any, Any]) -> ParsedResult[BibItem]:
    """
    Convert a raw Crossref response object to a BibItem instance.

    :param raw_object: The raw response object from Crossref.
    :return: An instance of ParsedBibItem with parsing status.
    """
    try:
        crossref_article = _convert_raw_crossref_response_to_crossref_article(raw_object)
        bibitem = _convert_crossref_article_to_bibitem(crossref_article)
        return {
            "out": bibitem,
            "parsing_status": "success",
        }

    except Exception as e:
        return {
            "parsing_status": "error",
            "message": f"Failed to convert Crossref article to BibItem: {e}",
            "context": raw_object.__str__(),
        }
