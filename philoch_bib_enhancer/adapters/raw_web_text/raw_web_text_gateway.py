"""
RawWebTextGateway - Gateway for extracting bibliographic data from web pages using LLMs.

This gateway follows the functional core / imperative shell pattern:
- Configuration is passed as a NamedTuple
- Gateway functions accept config as first parameter
- configure() binds all gateway functions to a config using partial application
"""

from functools import partial
import inspect
import sys
from types import SimpleNamespace
from typing import NamedTuple, Generator

from philoch_bib_enhancer.adapters.raw_web_text.raw_web_text_models import RawWebTextBibitem
from philoch_bib_enhancer.adapters.raw_web_text.raw_web_text_converter import convert_raw_web_text_to_bibitem
from philoch_bib_enhancer.adapters.raw_web_text.web_scraper import fetch_url_text, WebScraperError
from philoch_bib_enhancer.domain.parsing_result import ParsedResult
from philoch_bib_enhancer.ports.llm_service import LLMService, LLMServiceError
from philoch_bib_sdk.logic.models import BibItem


# System prompt for LLM to extract bibliographic data
BIBLIOGRAPHY_EXTRACTION_PROMPT = """You are a bibliographic data extraction assistant.

Your task is to extract citation or bibliographic information from the provided text.

Extract the following fields when present:
- raw_text: The exact raw text snippet you identified as containing bibliographic/citation data. Include it completely as-is, even if it has HTML tags, markdown, or other markup. This is for verification and debugging purposes.
- type: The publication type (e.g., "article", "book", "chapter", "inbook", "incollection")
- title: The title of the work
- year: The publication year
- authors: List of authors with given and family names
- editors: List of editors with given and family names (for books, edited collections, etc.)
- journal: The journal name (for journal articles)
- volume: The volume number
- issue_number: The issue number
- start_page: The starting page number
- end_page: The ending page number
- publisher: The publisher name (for books)
- doi: The DOI if available
- url: The URL if available

Important notes:
- For raw_text: Copy the exact text snippet where you found the bibliographic information, preserving all formatting, markup, HTML tags, etc.
- Extract only information that is clearly stated in the text
- If a field is not present or unclear, leave it as null/empty
- For authors/editors, separate given names from family names when possible
- Be precise and avoid hallucinating information that is not in the source text
- Handle various publication types: articles, books, book chapters, edited collections, etc.
"""


class RawWebTextGatewayConfig(NamedTuple):
    """
    Configuration for the RawWebTextGateway.
    """

    llm_service: LLMService  # Abstract LLM service (Claude, OpenAI, etc.)
    timeout: int = 30  # Web request timeout in seconds


# --- Gateway functions ---


def get_bibitem_from_url(
    config: RawWebTextGatewayConfig,
    url: str,
) -> ParsedResult[BibItem]:
    """
    Extract bibliographic data from a web page URL and convert to BibItem.

    Args:
        config: Gateway configuration with LLM service
        url: The URL to scrape

    Returns:
        A ParsedResult containing either a BibItem or an error
    """
    try:
        # Step 1: Fetch web page text
        try:
            text = fetch_url_text(url, timeout=config.timeout)
        except WebScraperError as e:
            return {
                "parsing_status": "error",
                "message": f"Failed to fetch URL: {e}",
                "context": url,
            }

        # Step 2: Parse text with LLM
        try:
            raw_bibitem = config.llm_service.parse_to_model(
                text=text,
                model_class=RawWebTextBibitem,
                system_prompt=BIBLIOGRAPHY_EXTRACTION_PROMPT,
            )
        except LLMServiceError as e:
            return {
                "parsing_status": "error",
                "message": f"LLM parsing failed: {e}",
                "context": text[:500],  # Include first 500 chars for context
            }

        # Step 3: Convert to BibItem
        bibitem_result = convert_raw_web_text_to_bibitem(raw_bibitem)

        return bibitem_result

    except Exception as e:
        return {
            "parsing_status": "error",
            "message": f"Unexpected error in get_bibitem_from_url: {e}",
            "context": url,
        }


def get_bibitems_from_urls(
    config: RawWebTextGatewayConfig,
    urls: list[str],
) -> Generator[ParsedResult[BibItem], None, None]:
    """
    Extract bibliographic data from multiple URLs and convert to BibItems.

    This is a generator function for lazy evaluation - processes one URL at a time
    and yields results as they become available.

    Args:
        config: Gateway configuration with LLM service
        urls: List of URLs to scrape

    Yields:
        ParsedResult[BibItem] for each URL (either success or error)
    """
    for url in urls:
        yield get_bibitem_from_url(config, url)


# --- Auto-configure ---


def configure(config: RawWebTextGatewayConfig) -> SimpleNamespace:
    """
    Return a namespace with all gateway functions bound to `config`.

    This uses functools.partial to bind the config parameter to all gateway functions,
    following the same pattern as the Crossref gateway.

    Example:
        >>> from adapters.llm.claude_llm_service import ClaudeLLMService
        >>> llm = ClaudeLLMService(api_key="...")
        >>> config = RawWebTextGatewayConfig(llm_service=llm)
        >>> gateway = configure(config)
        >>> result = gateway.get_bibitem_from_url("https://example.com/article")
    """
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
