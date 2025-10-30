# RawText Gateway

Extract bibliographic data from web pages using Large Language Models (LLMs).

## Overview

The RawTextGateway allows you to extract structured bibliographic information from arbitrary web pages. It uses LLMs (Claude or OpenAI) to parse unstructured text and convert it into `BibItem` objects.

**Supports various publication types:** articles, books, book chapters, edited collections, and more.

## Architecture

Following the project's **functional core / imperative shell** pattern:

```
┌─────────────────────────────────────────────────────┐
│ RawTextGateway (adapters/raw_text/)         │
├─────────────────────────────────────────────────────┤
│                                                      │
│  1. Fetch URL → web_scraper.py                     │
│  2. Parse with LLM → llm_service (port)            │
│  3. LLM returns → RawTextBibitem (Pydantic)     │
│  4. Convert → raw_text_converter.py            │
│  5. Output → BibItem (philoch-bib-sdk)             │
│                                                      │
└─────────────────────────────────────────────────────┘
```

## Components

### 1. Models ([raw_text_models.py](raw_text_models.py))

**`RawTextBibitem`** - Intermediate Pydantic model for LLM-extracted data

All fields are optional to handle partial/incomplete data:

```python
class RawTextBibitem(BaseModel):
    raw_text: Optional[str]       # Raw text snippet identified as bibitem (with markup)
    type: Optional[str]           # "article", "book", "chapter", "inbook", "incollection"
    title: Optional[str]
    year: Optional[int]
    authors: Optional[list[RawTextAuthor]]
    editors: Optional[list[RawTextAuthor]]  # For books, edited collections
    journal: Optional[str]
    issue: Optional[str]
    number: Optional[str]         # volume number
    start_page: Optional[str]
    end_page: Optional[str]
    publisher: Optional[str]
    doi: Optional[str]
    url: Optional[str]
```

### 2. LLM Service Interface ([ports/llm_service.py](../../ports/llm_service.py))

**Abstract protocol** for LLM services:

```python
class LLMService(Protocol):
    def parse_to_model(
        self,
        text: str,
        model_class: type[T],
        system_prompt: str
    ) -> T:
        ...
```

### 3. LLM Adapters ([adapters/llm/](../llm/))

Concrete implementations:

- **[claude_llm_service.py](../llm/claude_llm_service.py)** - Anthropic Claude API
- **[openai_llm_service.py](../llm/openai_llm_service.py)** - OpenAI API

### 4. Web Scraper ([web_scraper.py](web_scraper.py))

Fetches and cleans text from URLs:

```python
def fetch_url_text(url: str, timeout: int = 30) -> str:
    """Fetch cleaned text content from a URL."""
    ...
```

### 5. Converter ([raw_text_converter.py](raw_text_converter.py))

Converts `RawTextBibitem` → `BibItem`:

```python
def convert_raw_text_to_bibitem(
    raw_bibitem: RawTextBibitem
) -> ParsedResult[BibItem]:
    ...
```

Returns `ParsingSuccess[BibItem]` or `ParsingError` with error details.

### 6. Gateway ([raw_text_gateway.py](raw_text_gateway.py))

Main orchestration following the gateway pattern:

```python
class RawTextGatewayConfig(NamedTuple):
    llm_service: LLMService
    timeout: int = 30

def get_bibitem_from_url(
    config: RawTextGatewayConfig,
    url: str,
) -> ParsedResult[BibItem]:
    ...

def configure(config: RawTextGatewayConfig) -> SimpleNamespace:
    """Bind all gateway functions to config."""
    ...
```

## Installation

### 1. Core Dependencies (already in project)

```bash
# Already installed
pip install pydantic requests beautifulsoup4
```

### 2. LLM Service (choose one or both)

**For Claude/Anthropic:**
```bash
pip install anthropic
export ANTHROPIC_API_KEY="your-key-here"
```

**For OpenAI:**
```bash
pip install openai
export OPENAI_API_KEY="your-key-here"
```

## Usage

### Basic Example

```python
import os
from philoch_bib_enhancer.adapters.llm.claude_llm_service import ClaudeLLMService
from philoch_bib_enhancer.adapters.raw_text import (
    RawTextGatewayConfig,
    configure,
)
from philoch_bib_enhancer.adapters.crossref.crossref_models import is_parsing_success

# 1. Initialize LLM service
llm = ClaudeLLMService(api_key=os.getenv("ANTHROPIC_API_KEY"))

# 2. Configure gateway
config = RawTextGatewayConfig(llm_service=llm)
gateway = configure(config)

# 3. Extract from URL
result = gateway.get_bibitem_from_url("https://example.com/article")

# 4. Handle result
if is_parsing_success(result):
    bibitem = result["out"]
    print(f"Title: {bibitem.title.latex}")
    print(f"DOI: {bibitem.doi}")
else:
    print(f"Error: {result['message']}")
```

### Using OpenAI Instead

```python
from philoch_bib_enhancer.adapters.llm.openai_llm_service import OpenAILLMService

llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"))
config = RawTextGatewayConfig(llm_service=llm)
gateway = configure(config)
```

### Batch Processing

```python
urls = [
    "https://example.com/article1",
    "https://example.com/article2",
    "https://example.com/article3",
]

for url in urls:
    result = gateway.get_bibitem_from_url(url)
    if is_parsing_success(result):
        print(f"✅ {result['out'].title.latex}")
    else:
        print(f"❌ {result['message']}")
```

### Error Handling

The gateway returns a `ParsedResult[BibItem]` type:

```python
type ParsedResult[T] = ParsingSuccess[T] | ParsingError

# Success case
{
    "parsing_status": "success",
    "out": <BibItem>
}

# Error case
{
    "parsing_status": "error",
    "message": "Error description",
    "context": "Raw data context"
}
```

**Common error scenarios:**

1. **URL fetch failure** - Network issues, invalid URL
2. **LLM parsing failure** - API errors, rate limits
3. **Conversion failure** - Missing required fields (e.g., title)

## Integration with Existing Workflows

### With Bibkey Matching

Similar to Crossref gateway, you can match bibkeys from an ODS index:

```python
from philoch_bib_enhancer.domain.bibkey_matching import match_bibkey_to_article

# Load bibkey index
index = load_bibkey_index("bibliography.ods")

# Extract from URL
result = gateway.get_bibitem_from_url(url)

# Match bibkey if successful
if is_parsing_success(result):
    matched_result = match_bibkey_to_article(index, result)
    if is_parsing_success(matched_result):
        bibitem = matched_result["out"]
        print(f"Bibkey: {bibitem.bibkey}")
```

### CSV Output

Write results to CSV with status tracking:

```python
import csv

results = []
for url in urls:
    result = gateway.get_bibitem_from_url(url)

    if is_parsing_success(result):
        bibitem = result["out"]
        results.append({
            "url": url,
            "status": "success",
            "title": bibitem.title.latex,
            "doi": bibitem.doi,
            "message": ""
        })
    else:
        results.append({
            "url": url,
            "status": "error",
            "title": "",
            "doi": "",
            "message": result["message"]
        })

# Write to CSV
with open("output.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["url", "status", "title", "doi", "message"])
    writer.writeheader()
    writer.writerows(results)
```

## LLM Prompt

The gateway uses this system prompt to extract data:

```python
BIBLIOGRAPHY_EXTRACTION_PROMPT = """You are a bibliographic data extraction assistant.

Your task is to extract citation or bibliographic information from the provided text.

Extract the following fields when present:
- raw_text: The exact raw text snippet containing the bibliographic data (preserve markup, HTML tags, etc.)
- type: The publication type (e.g., "article", "book", "chapter", "inbook", "incollection")
- title: The title of the work
- year: The publication year
- authors: List of authors with given and family names
- editors: List of editors with given and family names (for books, edited collections, etc.)
- journal: The journal name (for articles)
- issue: The journal issue
- number: The volume number
- start_page: The starting page number
- end_page: The ending page number
- publisher: The publisher name
- doi: The DOI if available
- url: The URL if available

Important notes:
- For raw_text: Copy the exact text snippet where you found the bibliographic information, preserving all formatting
- Extract only information that is clearly stated in the text
- If a field is not present or unclear, leave it as null/empty
- For authors/editors, separate given names from family names when possible
- Be precise and avoid hallucinating information that is not in the source text
"""
```

You can customize this by modifying the prompt in [raw_text_gateway.py](raw_text_gateway.py).

## Design Decisions

### Why an Intermediate Model?

The `RawTextBibitem` model serves as a **validation boundary** between the LLM and BibItem:

1. **Flexible input** - All fields optional to handle partial data from various publication types
2. **LLM-friendly** - Simple structure for structured output
3. **Validation layer** - Pydantic validates LLM output before BibItem conversion
4. **Error isolation** - Conversion errors don't affect LLM parsing

### Why Protocol for LLM Service?

Using a `Protocol` instead of a base class allows:

1. **Duck typing** - Any object with `parse_to_model()` works
2. **No inheritance** - Concrete implementations are independent
3. **Dependency injection** - Gateway receives abstract service via config
4. **Testability** - Easy to mock for testing

## Testing

### Unit Tests

Test the converter with mock data:

```python
def test_convert_raw_text_to_bibitem():
    raw_bibitem = RawTextBibitem(
        type="article",
        title="Test Article",
        year=2024,
        authors=[
            RawTextAuthor(given="John", family="Smith")
        ],
    )

    result = convert_raw_text_to_bibitem(raw_bibitem)

    assert is_parsing_success(result)
    assert result["out"].title.latex == "Test Article"
```

### Integration Tests

Mark as external (requires API access):

```python
import pytest

@pytest.mark.external
def test_extract_from_real_url():
    llm = ClaudeLLMService(api_key=os.getenv("ANTHROPIC_API_KEY"))
    config = RawTextGatewayConfig(llm_service=llm)
    gateway = configure(config)

    result = gateway.get_bibitem_from_url("https://example.com/article")

    assert is_parsing_success(result)
```

## Performance Considerations

1. **Rate limits** - LLM APIs have rate limits; add delays for batch processing
2. **Timeout** - Configure web scraping timeout via `RawTextGatewayConfig(timeout=60)`
3. **Caching** - Consider caching LLM responses for repeated URLs
4. **Cost** - Each URL = 1 LLM API call (text extraction + parsing)

## Future Extensions

Potential improvements:

1. **Retry logic** - Add tenacity retry for transient failures
2. **Caching layer** - Cache LLM responses by URL hash
3. **Multiple LLM fallback** - Try OpenAI if Claude fails
4. **Custom prompts** - Allow user-provided prompts via config
5. **HTML structure hints** - Use HTML structure (meta tags) to improve extraction
6. **Parallel processing** - Process multiple URLs concurrently

## See Also

- [Architecture Overview](../../../docs/architecture.md)
- [Crossref Gateway](../crossref/) - Similar pattern for Crossref API
- [Example Usage](../../../examples/raw_text_example.py)
