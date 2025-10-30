"""
RawText adapter - Extract bibliographic data from web pages using LLMs.
"""

from philoch_bib_enhancer.adapters.raw_text.raw_text_gateway import (
    RawTextGatewayConfig,
    configure,
    get_bibitem_from_url,
)
from philoch_bib_enhancer.adapters.raw_text.raw_text_models import (
    RawTextBibitem,
    RawTextAuthor,
)
from philoch_bib_enhancer.adapters.raw_text.raw_text_converter import (
    convert_raw_text_to_bibitem,
)
from philoch_bib_enhancer.adapters.raw_text.web_scraper import (
    fetch_url_text,
    fetch_url_html,
    WebScraperError,
)

__all__ = [
    "RawTextGatewayConfig",
    "configure",
    "get_bibitem_from_url",
    "RawTextBibitem",
    "RawTextAuthor",
    "convert_raw_text_to_bibitem",
    "fetch_url_text",
    "fetch_url_html",
    "WebScraperError",
]
