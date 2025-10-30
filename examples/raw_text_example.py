#!/usr/bin/env python3
"""
Example usage of RawTextGateway to extract bibliographic data from web pages.
Supports various publication types: articles, books, book chapters, edited collections, etc.

Prerequisites:
    1. Install optional dependencies:
       pip install anthropic  # For Claude
       # OR
       pip install openai     # For OpenAI

    2. Set environment variables:
       export ANTHROPIC_API_KEY="your-key-here"
       # OR
       export OPENAI_API_KEY="your-key-here"

    3. Install beautifulsoup4 if not already installed:
       pip install beautifulsoup4
"""

import os
from philoch_bib_enhancer.adapters.raw_text import (
    RawTextGatewayConfig,
    configure,
)
from philoch_bib_enhancer.domain.parsing_result import is_parsing_success


def example_with_claude() -> None:
    """Example using Claude/Anthropic LLM service."""
    from philoch_bib_enhancer.adapters.llm.claude_llm_service import ClaudeLLMService

    # Initialize Claude LLM service
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    llm_service = ClaudeLLMService(api_key=api_key)

    # Configure the gateway
    config = RawTextGatewayConfig(llm_service=llm_service, timeout=30)
    gateway = configure(config)

    # Example URL (replace with actual URL)
    url = "https://example.com/some-article-page"

    print(f"Extracting bibliographic data from: {url}")
    result = gateway.get_bibitem_from_url(url)

    if is_parsing_success(result):
        bibitem = result["out"]
        print("\n✅ Success!")
        print(f"Title: {bibitem.title.latex}")
        print(f"Authors: {', '.join(f'{a.family_name.latex}, {a.given_name.latex}' for a in bibitem.author)}")
        print(f"Year: {bibitem.date.year if hasattr(bibitem.date, 'year') else 'N/A'}")
        print(f"DOI: {bibitem.doi or 'N/A'}")
        print(f"Source: {bibitem._bib_info_source}")
    else:
        print("\n❌ Error:")
        print(f"Message: {result['message']}")
        print(f"Context: {result['context'][:200]}...")


def example_with_openai() -> None:
    """Example using OpenAI LLM service."""
    from philoch_bib_enhancer.adapters.llm.openai_llm_service import OpenAILLMService

    # Initialize OpenAI LLM service
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    llm_service = OpenAILLMService(api_key=api_key)

    # Configure the gateway
    config = RawTextGatewayConfig(llm_service=llm_service, timeout=30)
    gateway = configure(config)

    # Example URL (replace with actual URL)
    url = "https://example.com/some-article-page"

    print(f"Extracting bibliographic data from: {url}")
    result = gateway.get_bibitem_from_url(url)

    if is_parsing_success(result):
        bibitem = result["out"]
        print("\n✅ Success!")
        print(f"Title: {bibitem.title.latex}")
        print(f"Authors: {', '.join(f'{a.family_name.latex}, {a.given_name.latex}' for a in bibitem.author)}")
        print(f"Year: {bibitem.date.year if hasattr(bibitem.date, 'year') else 'N/A'}")
        print(f"DOI: {bibitem.doi or 'N/A'}")
        print(f"Source: {bibitem._bib_info_source}")
    else:
        print("\n❌ Error:")
        print(f"Message: {result['message']}")
        print(f"Context: {result['context'][:200]}...")


def example_batch_processing() -> None:
    """Example of batch processing multiple URLs."""
    from philoch_bib_enhancer.adapters.llm.claude_llm_service import ClaudeLLMService

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    llm_service = ClaudeLLMService(api_key=api_key)
    config = RawTextGatewayConfig(llm_service=llm_service)
    gateway = configure(config)

    # List of URLs to process
    urls = [
        "https://example.com/article1",
        "https://example.com/article2",
        "https://example.com/article3",
    ]

    results = []
    for url in urls:
        print(f"\nProcessing: {url}")
        result = gateway.get_bibitem_from_url(url)
        results.append({"url": url, "result": result})

        if is_parsing_success(result):
            print(f"  ✅ {result['out'].title.latex}")
        else:
            print(f"  ❌ {result['message']}")

    # Summary
    successes = sum(1 for r in results if is_parsing_success(r["result"]))
    print(f"\n📊 Summary: {successes}/{len(results)} successful extractions")


if __name__ == "__main__":
    # Uncomment the example you want to run:

    # example_with_claude()
    # example_with_openai()
    # example_batch_processing()

    print(__doc__)
