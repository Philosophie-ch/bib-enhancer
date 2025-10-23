# RawWebText Gateway Usage Guide

The RawWebText gateway enables extraction of bibliographic data from web pages using LLM services (Claude or OpenAI) or manual extraction.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     TWO WORKFLOWS AVAILABLE                      │
├─────────────────────────────────────────────────────────────────┤
│  1. Automated: CLI → LLM Service → BibItem → CSV               │
│  2. Manual: Python/JSON → RawWebTextBibitem → BibItem → CSV    │
└─────────────────────────────────────────────────────────────────┘
```

## Workflow 1: Automated LLM Extraction

Use this when you want to fully automate the extraction process using Claude or OpenAI.

### Prerequisites

Set up environment variables in `.env`:

```bash
# Choose LLM service
LLM_SERVICE=claude  # or "openai"

# API keys (only one needed based on LLM_SERVICE)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

### Usage

#### CLI with URL arguments

```bash
python -m philoch_bib_enhancer.cli.raw_web_text_scraping_cli \
  --urls https://example.com/article1 https://example.com/article2 \
  --output results.csv
```

#### CLI with URL file

Create a file with URLs (one per line):

```text
https://example.com/article1
https://example.com/article2
https://example.com/article3
```

Then run:

```bash
python -m philoch_bib_enhancer.cli.raw_web_text_scraping_cli \
  --urls-file urls.txt \
  --output results.csv
```

#### With bibkey matching

If you have an existing bibliography in ODS format, you can match bibkeys:

```bash
python -m philoch_bib_enhancer.cli.raw_web_text_scraping_cli \
  --urls-file urls.txt \
  --output results.csv \
  --bibliography-path /path/to/bibliography.ods \
  --column-name-bibkey bibkey \
  --column-name-journal journal \
  --column-name-volume volume \
  --column-name-number number
```

### Programmatic Usage

```python
from philoch_bib_enhancer.adapters.llm.claude_llm_service import ClaudeLLMService
from philoch_bib_enhancer.adapters.raw_web_text import raw_web_text_gateway

# Setup LLM service
llm = ClaudeLLMService(api_key="sk-ant-...")

# Configure gateway
config = raw_web_text_gateway.RawWebTextGatewayConfig(llm_service=llm)
gateway = raw_web_text_gateway.configure(config)

# Process URLs
urls = ["https://example.com/article1", "https://example.com/article2"]
results = gateway.get_bibitems_from_urls(urls)

# Results is a generator of ParsedResult[BibItem]
for result in results:
    if result["parsing_status"] == "success":
        bibitem = result["out"]
        print(bibitem.title)
    else:
        print(f"Error: {result['message']}")
```

## Workflow 2: Manual Extraction

Use this when:
- You want to manually extract bibliographic data
- You're using Claude Code to act as the LLM
- You want more control over the extraction process
- You're using an external LLM tool

### Direct Python Usage (Recommended)

Create `RawWebTextBibitem` objects directly in Python:

```python
from philoch_bib_enhancer.cli.manual_raw_web_text_to_csv import process_raw_bibitems
from philoch_bib_enhancer.adapters.raw_web_text.raw_web_text_models import (
    RawWebTextBibitem,
    RawWebTextAuthor,
)

# Create RawWebTextBibitem objects
raw_bibitems = [
    RawWebTextBibitem(
        raw_text="Doe, John (2024). 'Understanding Architecture', Journal of Software, 15(3), pp. 45-67.",
        type="article",
        title="Understanding Architecture",
        year=2024,
        authors=[
            RawWebTextAuthor(given="John", family="Doe"),
        ],
        journal="Journal of Software",
        volume="15",
        number="3",
        start_page="45",
        end_page="67",
    ),
]

# Convert to CSV
process_raw_bibitems(
    raw_bibitems=raw_bibitems,
    output_path="output.csv",
)
```

### CLI with JSON Input

If you prefer working with JSON files:

1. Create a JSON file with `RawWebTextBibitem` objects:

```json
[
  {
    "raw_text": "Doe, John (2024). 'Understanding Architecture'...",
    "type": "article",
    "title": "Understanding Architecture",
    "year": 2024,
    "authors": [
      {
        "given": "John",
        "family": "Doe"
      }
    ],
    "journal": "Journal of Software",
    "volume": "15",
    "number": "3",
    "start_page": "45",
    "end_page": "67"
  }
]
```

2. Convert to CSV:

```bash
python -m philoch_bib_enhancer.cli.manual_raw_web_text_to_csv \
  --input bibitems.json \
  --output results.csv
```

### With Bibkey Matching

```python
from philoch_bib_sdk.adapters.tabular_data.read_journal_volume_number_index import ColumnNames

process_raw_bibitems(
    raw_bibitems=raw_bibitems,
    output_path="output.csv",
    bibliography_path="/path/to/bibliography.ods",
    column_names=ColumnNames(
        bibkey="bibkey",
        journal="journal",
        volume="volume",
        number="number",
    ),
)
```

## RawWebTextBibitem Model

The intermediate Pydantic model has these fields (all optional):

```python
class RawWebTextBibitem(BaseModel):
    raw_text: Optional[str] = None          # Original text snippet
    type: Optional[str] = None              # "article", "book", "incollection", etc.
    title: Optional[str] = None
    year: Optional[int] = None
    authors: Optional[list[RawWebTextAuthor]] = Field(default_factory=list)
    editors: Optional[list[RawWebTextAuthor]] = Field(default_factory=list)
    journal: Optional[str] = None
    volume: Optional[str] = None
    number: Optional[str] = None
    start_page: Optional[str] = None
    end_page: Optional[str] = None
    publisher: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None

class RawWebTextAuthor(BaseModel):
    given: str = ""
    family: str = ""
```

## CSV Output Format

Both workflows produce the same CSV format with these key columns:

### BibItem Columns
- `entry_type`, `bibkey`, `author`, `editor`, `date`, `title`, `journal`, `volume`, `number`, `pages`, `publisher`, `doi`, `url`, etc.

### Report Columns
- `parsing_status`: "success" or "error"
- `message`: Error message (if any)
- `context`: Raw data for debugging (if error)

Example:

```csv
entry_type,bibkey,author,title,journal,volume,number,pages,doi,parsing_status,message,context
UNKNOWN,,"Doe, John",Understanding Architecture,Journal of Software,15,3,45--67,10.1234/js.2024,success,,
```

## Error Handling

Both workflows use the `ParsedResult` pattern:

```python
# Success case
{
    "parsing_status": "success",
    "out": BibItem(...)
}

# Error case
{
    "parsing_status": "error",
    "message": "Failed to fetch URL: ...",
    "context": "https://example.com/..."
}
```

All results (success and error) are written to CSV with status indicators.

## Examples

See:
- [examples/raw_web_text_example.py](../examples/raw_web_text_example.py) - Automated LLM workflow
- [examples/manual_workflow_example.py](../examples/manual_workflow_example.py) - Manual workflow

## Comparison with Crossref Gateway

| Feature | Crossref Gateway | RawWebText Gateway |
|---------|------------------|-------------------|
| Input | ISSN + year range | URLs or Python objects |
| Data source | Crossref API | Web pages or manual |
| Parsing | Structured JSON | LLM or manual |
| Output | CSV with BibItems | CSV with BibItems |
| Bibkey matching | ✓ | ✓ |
| Error tracking | ✓ | ✓ |

Both gateways:
- Follow the same architecture pattern
- Return `Generator[ParsedResult[BibItem]]`
- Use the same CSV writer and bibkey matcher
- Support the orchestration layer abstraction
