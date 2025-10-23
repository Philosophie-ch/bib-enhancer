"""
RawWebText adapter - Extract bibliographic data from web pages using LLMs.
"""

from philoch_bib_enhancer.adapters.raw_web_text.raw_web_text_gateway import (
    RawWebTextGatewayConfig,
    configure,
    get_bibitem_from_url,
)
from philoch_bib_enhancer.adapters.raw_web_text.raw_web_text_models import (
    RawWebTextBibitem,
    RawWebTextAuthor,
)
from philoch_bib_enhancer.adapters.raw_web_text.raw_web_text_converter import (
    convert_raw_web_text_to_bibitem,
)
from philoch_bib_enhancer.adapters.raw_web_text.web_scraper import (
    fetch_url_text,
    fetch_url_html,
    WebScraperError,
)

__all__ = [
    "RawWebTextGatewayConfig",
    "configure",
    "get_bibitem_from_url",
    "RawWebTextBibitem",
    "RawWebTextAuthor",
    "convert_raw_web_text_to_bibitem",
    "fetch_url_text",
    "fetch_url_html",
    "WebScraperError",
]
