from functools import partial
import inspect
import sys
from types import SimpleNamespace
from typing import NamedTuple

from philoch_bib_enhancer.adapters.crossref.crossref_client import CrossrefClient
from philoch_bib_enhancer.adapters.crossref.crossref_converter import convert_crossref_response_to_bibitem
from philoch_bib_enhancer.ports.bibitem_by_doi import TBibItemByDoiOUT
from philoch_bib_enhancer.ports.journal_scraping import JournalScraperIN, TJournalScraperOUT


class CrossrefGatewayConfig(NamedTuple):
    """
    Configuration for the Crossref BibItem Gateway.
    """

    client: CrossrefClient


# --- Gateway functions ---
def get_journal_articles(
    config: CrossrefGatewayConfig,
    main_in: JournalScraperIN,
) -> TJournalScraperOUT:
    """
    Create a Crossref BibItem Gateway using the provided configuration.

    :param config: Configuration for the Crossref BibItem Gateway.
    :return: An instance of CrossrefClient configured with the provided settings.
    """
    cr = config.client
    issn, (start_year, end_year) = main_in.issn, main_in.year_range

    cr_raw_nested_list = (
        cr.journal_articles_by_issn_year(
            issn=issn,
            year=year,
        )[
            'message'
        ]['items']
        for year in range(start_year, end_year + 1)
    )

    cr_raw = (item for sublist in cr_raw_nested_list for item in sublist)

    cr_articles = (convert_crossref_response_to_bibitem(raw_article) for raw_article in cr_raw)

    return cr_articles


def get_bibitem_by_doi(
    config: CrossrefGatewayConfig,
    doi: str,
) -> TBibItemByDoiOUT:
    """
    Get a BibItem by its DOI using the Crossref API.

    :param config: Configuration for the Crossref BibItem Gateway.
    :param doi: The DOI of the article to retrieve.
    :return: A dictionary containing the BibItem and parsing status.
    """
    cr = config.client
    raw_article = cr.raw_client.works(ids=doi)

    if 'message' not in raw_article:
        raise ValueError(f"Could not find article with DOI {doi}. Response: {raw_article}")

    bibitem_result = convert_crossref_response_to_bibitem(raw_article['message'])

    return bibitem_result


# --- Auto-configure ---
def configure(config: CrossrefGatewayConfig) -> SimpleNamespace:
    """Return a namespace with all gateway funcs bound to `config`."""
    current_module = sys.modules[__name__]
    bound_funcs = {}

    for name, obj in inspect.getmembers(current_module, inspect.isfunction):
        if name == "configure":
            continue

        sig = inspect.signature(obj)
        params = list(sig.parameters.values())
        if not params or params[0].name != "config":
            continue  # only wrap funcs with config as first param

        bound_funcs[name] = partial(obj, config)

    return SimpleNamespace(**bound_funcs)
