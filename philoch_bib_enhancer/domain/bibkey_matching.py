"""
Pure domain logic for matching bibkeys to bibliographic items.

This module contains pure functions with no I/O, no logging, and no side effects.
All functions are deterministic and testable.
"""

import attrs
from philoch_bib_sdk.logic.functions.journal_article_matcher import (
    TJournalBibkeyIndex,
    get_bibkey_by_journal_volume_number,
)
from philoch_bib_sdk.logic.models import BibItem

from philoch_bib_enhancer.domain.parsing_result import ParsedResult, is_parsing_success


def match_bibkey_to_article(
    index: TJournalBibkeyIndex,
    parsed_result: ParsedResult[BibItem],
) -> ParsedResult[BibItem]:
    """
    Pure function: matches a parsed article to a bibkey from an index.

    Given an index of (journal, volume, number) -> bibkey mappings, attempts to
    find a matching bibkey for the article. If found, returns the article with
    the bibkey field populated. If not found or if there's an error, returns
    the article unchanged.

    No side effects: no I/O, no logging, no mutations (uses attrs.evolve).

    :param index: Index mapping (journal, volume, number) to bibkeys
    :param parsed_result: A parsed article result (may be success or error)
    :return: The same article with bibkey populated if found, unchanged otherwise
    """
    if not is_parsing_success(parsed_result):
        return parsed_result

    bibitem = parsed_result["out"]

    try:
        bibkey = get_bibkey_by_journal_volume_number(index, bibitem)
        if bibkey is None:
            # No match found - return article unchanged
            return {
                "parsing_status": "success",
                "out": bibitem,
            }

        # Match found - return new article with bibkey
        updated = attrs.evolve(
            bibitem,
            bibkey=bibkey,
        )
        return {
            "parsing_status": "success",
            "out": updated,
        }

    except KeyError:
        # Index lookup failed - return article unchanged
        return {
            "parsing_status": "success",
            "out": bibitem,
        }
