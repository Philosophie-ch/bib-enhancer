# Crossref Flow Analysis

Understanding how Crossref processes bibliographic data from API to CSV output.

## Flow Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLI LAYER (Imperative Shell)                │
│              crossref_journal_scraping_cli.py                   │
├─────────────────────────────────────────────────────────────────┤
│  1. Parse CLI args (ISSN, year range, bibkey matching config)  │
│  2. Load env vars (CROSSREF_EMAIL)                             │
│  3. Setup infrastructure                                        │
│  4. Wire concrete implementations                               │
│  5. Call orchestrator                                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  ORCHESTRATION LAYER (Abstract)                 │
│                   ports/journal_scraping.py                     │
├─────────────────────────────────────────────────────────────────┤
│  main(main_in):                                                 │
│    1. Call get_journal_articles() → Generator[ParsedResult]    │
│    2. Optionally call match_bibkey() on each result            │
│    3. Call write_articles() to output                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    GATEWAY LAYER (Adapter)                      │
│            crossref_bibitem_gateway.py                          │
├─────────────────────────────────────────────────────────────────┤
│  get_journal_articles(config, journal_scraper_in):             │
│    1. Fetch raw data from Crossref API                         │
│    2. Convert each raw response → ParsedResult[BibItem]        │
│    3. Return generator of ParsedResult[BibItem]                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    CONVERTER LAYER                              │
│              crossref_converter.py                              │
├─────────────────────────────────────────────────────────────────┤
│  convert_crossref_response_to_bibitem(raw_object):             │
│    1. Parse raw dict → CrossrefArticle (Pydantic)              │
│    2. Convert CrossrefArticle → BibItem                        │
│    3. Return ParsedResult[BibItem] (success or error)          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   DOMAIN LAYER (Optional)                       │
│              domain/bibkey_matching.py                          │
├─────────────────────────────────────────────────────────────────┤
│  match_bibkey_to_article(index, parsed_result):                │
│    - If parsing succeeded, match bibkey from index             │
│    - Update BibItem with bibkey                                │
│    - Return ParsedResult[BibItem]                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     OUTPUT LAYER                                │
│            write_articles_to_csv()                              │
├─────────────────────────────────────────────────────────────────┤
│  1. Format each BibItem using format_bibitem()                 │
│  2. Add parsing_status, message, context columns               │
│  3. Write to CSV file                                          │
└─────────────────────────────────────────────────────────────────┘
```

## Data Transformations

### Step 1: Raw Crossref Response → CrossrefArticle

**Input:** `Dict[Any, Any]` from Crossref API
```python
{
    "DOI": "10.1234/example",
    "title": ["Article Title"],
    "author": [{"given": "John", "family": "Doe"}],
    "published": {"date-parts": [[2024]]},
    ...
}
```

**Output:** `CrossrefArticle` (Pydantic model)
```python
CrossrefArticle(
    DOI="10.1234/example",
    title=["Article Title"],
    author=[CrossrefAuthor(given="John", family="Doe")],
    issued=CrossrefDateParts(date_parts=[[2024]]),
    ...
)
```

### Step 2: CrossrefArticle → BibItem

**Input:** `CrossrefArticle`

**Output:** `ParsedResult[BibItem]`
```python
{
    "parsing_status": "success",
    "out": BibItem(
        title=BibString(latex="Article Title"),
        author=(Author(...), ),
        date={"year": 2024},
        ...
    )
}
```

OR (on error):
```python
{
    "parsing_status": "error",
    "message": "Failed to convert: ...",
    "context": "raw data..."
}
```

### Step 3: BibItem → BibItem with Bibkey (Optional)

**Input:** `ParsedResult[BibItem]` (no bibkey)

**Process:** Match against ODS index by journal + volume + number

**Output:** `ParsedResult[BibItem]` (with bibkey if found)

### Step 4: ParsedResult[BibItem] → CSV Row

**Input:** `ParsedResult[BibItem]`

**Output:** CSV row with columns:
```
bibkey, title, author, year, journal, volume, number, pages, doi, url,
parsing_status, message, context, ...
```

## Key Abstractions

### 1. Gateway Functions

```python
def get_journal_articles(
    config: CrossrefGatewayConfig,
    main_in: JournalScraperIN,
) -> TJournalScraperOUT:
    """
    Returns: Generator[ParsedResult[BibItem], None, None]
    """
```

- Takes config + input params
- Returns **generator** of `ParsedResult[BibItem]`
- Lazy evaluation (doesn't fetch all at once)

### 2. ParsedResult Type

```python
type ParsedResult[T] = ParsingSuccess[T] | ParsingError

# Success:
{
    "parsing_status": "success",
    "out": T  # The actual BibItem
}

# Error:
{
    "parsing_status": "error",
    "message": str,  # Error description
    "context": str   # Raw data for debugging
}
```

### 3. Dependency Injection

All concrete implementations injected via `JournalScraperMainIN`:

```python
JournalScraperMainIN(
    journal_scraper_in=...,           # Input params
    get_journal_articles=...,         # Gateway function
    match_bibkey=...,                 # Optional bibkey matcher
    write_articles=...,               # CSV writer
    output_dir=...                    # Output location
)
```

## Configuration Pattern

### Gateway Config (NamedTuple)

```python
class CrossrefGatewayConfig(NamedTuple):
    client: CrossrefClient
```

### Configure Function (Partial Application)

```python
def configure(config: CrossrefGatewayConfig) -> SimpleNamespace:
    """Bind all gateway functions to config."""
    # Returns namespace with partially applied functions
    # e.g., gateway.get_journal_articles(journal_scraper_in)
```

Usage:
```python
config = CrossrefGatewayConfig(client=CrossrefClient(...))
gateway = crossref_bibitem_gateway.configure(config)
gateway.get_journal_articles(...)  # config already bound
```

## Error Handling Strategy

1. **At conversion level:** Try/catch → return `ParsingError`
2. **At orchestration level:** Accept both success and error results
3. **At output level:** Write both successful and failed items to CSV with status

This means:
- **No exceptions bubble up** from data processing
- **All items tracked** (success or failure)
- **Easy debugging** via context field

## For RawText Gateway

We need to mirror this pattern:

1. **Gateway function** that returns `Generator[ParsedResult[BibItem], None, None]`
2. **Input model** that specifies what to scrape (e.g., list of URLs)
3. **Converter** from `RawTextBibitem → BibItem` (already done!)
4. **CSV writer** (can reuse Crossref's `write_articles_to_csv`)
5. **CLI** that wires everything together
6. **Optionally:** Bibkey matching (can reuse existing)

### Key Differences for RawText:

- **Input:** List of URLs instead of ISSN + year range
- **Fetching:** Web scraping instead of API calls
- **Parsing:** LLM step instead of structured JSON
- **Output:** Same CSV format (reuse!)

### What We Already Have:

✅ `RawTextBibitem` model (intermediate)
✅ `convert_raw_text_to_bibitem()` converter
✅ `get_bibitem_from_url()` gateway function

### What We Need:

🔲 Gateway function that accepts **multiple URLs** and returns generator
🔲 CLI for batch URL processing
🔲 Integration with existing orchestration layer
🔲 (Optional) Claude Code slash command for manual LLM step
