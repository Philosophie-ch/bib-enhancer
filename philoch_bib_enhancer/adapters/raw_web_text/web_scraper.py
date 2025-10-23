"""
Web scraping utility to fetch and clean text content from URLs.
"""

import requests
from typing import Optional

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise ImportError(
        "The 'beautifulsoup4' package is required for web scraping. " "Install it with: pip install beautifulsoup4"
    )


class WebScraperError(Exception):
    """Raised when web scraping fails."""

    pass


def fetch_url_text(url: str, timeout: int = 30) -> str:
    """
    Fetch text content from a URL.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds (default: 30)

    Returns:
        Cleaned text content from the page

    Raises:
        WebScraperError: If the request fails or content cannot be extracted
    """
    try:
        # Fetch the URL
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove script and style elements
        for script in soup(['script', 'style']):
            script.decompose()

        # Get text
        text = soup.get_text(separator='\n', strip=True)

        if not text:
            raise WebScraperError(f"No text content found at {url}")

        return text

    except requests.RequestException as e:
        raise WebScraperError(f"Failed to fetch URL {url}: {e}") from e
    except Exception as e:
        raise WebScraperError(f"Failed to extract text from {url}: {e}") from e


def fetch_url_html(url: str, timeout: int = 30) -> str:
    """
    Fetch raw HTML content from a URL.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds (default: 30)

    Returns:
        Raw HTML content from the page

    Raises:
        WebScraperError: If the request fails
    """
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        text: str = response.text
        return text

    except requests.RequestException as e:
        raise WebScraperError(f"Failed to fetch URL {url}: {e}") from e
