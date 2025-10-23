"""
Converter from RawWebTextBibitem (LLM-extracted data) to BibItem.
"""

from typing import Tuple, Literal
from philoch_bib_sdk.logic.models import BibItem
from philoch_bib_sdk.logic.default_models import (
    AuthorArgs,
    BibStringArgs,
    JournalArgs,
    BibItemArgs,
    BibItemDateArgs,
    PageArgs,
    default_bib_item,
)

from philoch_bib_enhancer.domain.parsing_result import ParsedResult
from philoch_bib_enhancer.adapters.raw_web_text.raw_web_text_models import RawWebTextBibitem


def _convert_raw_web_text_bibitem_to_bibitem(raw_bibitem: RawWebTextBibitem) -> BibItem:
    """
    Convert a RawWebTextBibitem object into a BibItem instance.

    Raises:
        ValueError: If required fields are missing or invalid.
    """

    # Authors
    authors: Tuple[AuthorArgs, ...] = tuple()
    if raw_bibitem.authors:
        authors = tuple(
            {
                "given_name": {"latex": author.given or ""},
                "family_name": {"latex": author.family or ""},
            }
            for author in raw_bibitem.authors
        )

    # Editors (if no authors, use editors as authors)
    editors: Tuple[AuthorArgs, ...] = tuple()
    if raw_bibitem.editors:
        editors = tuple(
            {
                "given_name": {"latex": editor.given or ""},
                "family_name": {"latex": editor.family or ""},
            }
            for editor in raw_bibitem.editors
        )

    # If no authors but we have editors, use editors as authors
    if not authors and editors:
        authors = editors

    # Title (required)
    if not raw_bibitem.title:
        raise ValueError("Title is required but was not found in the raw web text")

    title: BibStringArgs = {"latex": raw_bibitem.title}

    # Date
    date_parts: BibItemDateArgs | Literal["no date"] = "no date"
    if raw_bibitem.year:
        date_parts = {"year": raw_bibitem.year}

    # Journal (optional)
    journal: JournalArgs | None = None
    if raw_bibitem.journal:
        journal = {
            "name": {"latex": raw_bibitem.journal},
            "issn_print": "",
            "issn_electronic": "",
        }

    # Pages
    pages: Tuple[PageArgs, ...] = tuple()
    if raw_bibitem.start_page:
        pages = (
            {
                "start": raw_bibitem.start_page,
                "end": raw_bibitem.end_page or "",
            },
        )

    # Publisher
    publisher: BibStringArgs = {"latex": raw_bibitem.publisher} if raw_bibitem.publisher else {}

    # Build BibItem
    bibitem_data: BibItemArgs = {
        "author": authors,
        "date": date_parts,
        "title": title,
        "volume": raw_bibitem.number or "",
        "number": raw_bibitem.issue or "",
        "pages": pages,
        "publisher": publisher,
        "doi": raw_bibitem.doi or "",
        "url": raw_bibitem.url or "",
        "_bib_info_source": "RawWebText (LLM)",
    }

    # Add journal if present
    if journal:
        bibitem_data["journal"] = journal

    result = default_bib_item(**bibitem_data)

    return result


def convert_raw_web_text_to_bibitem(raw_bibitem: RawWebTextBibitem) -> ParsedResult[BibItem]:
    """
    Convert a RawWebTextBibitem to a BibItem instance with error handling.

    Args:
        raw_bibitem: The RawWebTextBibitem extracted by LLM

    Returns:
        A ParsedResult containing either a BibItem or an error
    """
    try:
        bibitem = _convert_raw_web_text_bibitem_to_bibitem(raw_bibitem)
        return {
            "out": bibitem,
            "parsing_status": "success",
        }

    except Exception as e:
        return {
            "parsing_status": "error",
            "message": f"Failed to convert RawWebTextBibitem to BibItem: {e}",
            "context": raw_bibitem.model_dump_json(),
        }
