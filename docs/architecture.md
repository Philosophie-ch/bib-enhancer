# Architecture Overview

**Project**: Philosophie.ch Bibliography Enhancer
**Version**: 0.1.0
**Last Updated**: 2025-10-23

---

## Executive Summary

This project enhances bibliographic data for Philosophie.ch by fetching article metadata from external APIs (primarily Crossref) and converting it into structured `BibItem` objects. The architecture follows a **functional core / imperative shell** pattern with strict separation between pure domain logic, abstract orchestration, and concrete I/O implementations.

### Core Principles

1. **Pydantic at boundaries only** - External data is validated with Pydantic models at entry points, then plain types are used internally
2. **Functional core** - Domain logic is pure (no I/O, no side effects, deterministic, testable)
3. **Imperative shell** - Concrete implementations of side-effectful operations use clear imperative code
4. **Function-based dependency injection** - Abstract logic receives concrete implementations via function parameters (no classes, no DI containers)

---

## Architecture Layers

```
philoch_bib_enhancer/
├── domain/              # Pure business logic (no I/O, no side effects)
├── ports/               # Abstract orchestration (delegates to injected functions)
├── adapters/            # Concrete I/O implementations (APIs, file readers, etc.)
└── cli/                 # Imperative shell (wires everything together)
```

### Layer Responsibilities

| Layer | Purpose | Constraints | Examples |
|-------|---------|-------------|----------|
| **domain/** | Pure domain logic | No I/O, no logging, no mutations | `match_bibkey_to_article()` |
| **ports/** | Workflow orchestration | Abstract only - delegates all I/O to injected functions | `main()` in `journal_scraping.py` |
| **adapters/** | Concrete I/O | Imperative implementations are acceptable | `CrossrefClient`, `crossref_bibitem_gateway` |
| **cli/** | Entry points | Pydantic validation, wires dependencies, handles all setup | `crossref_journal_scraping_cli.py` |

**Note**: Shared utilities and model factories (e.g., `default_bib_item()`, `BibItem` models) come from the external `philoch-bib-sdk` package.

---

## Data Flow Architecture

### Example: Journal Scraping Workflow

```
CLI Entry Point (cli/crossref_journal_scraping_cli.py)
    ↓
    1. Load .env file (dotenv)
    2. Parse CLI arguments (argparse)
    3. Validate with Pydantic models (boundary validation)
    4. Setup infrastructure (Crossref client, gateways)
    5. Create concrete implementations:
       - Article fetcher (Crossref gateway function)
       - Bibkey matcher (optional, loads ODS index)
       - CSV writer (imperative file writer)
    ↓
Abstract Orchestration (ports/journal_scraping.py)
    ↓
    main(JournalScraperMainIN):
        1. Call get_journal_articles() → Generator[ParsedResult[BibItem]]
        2. Optionally call match_bibkey() on each result
        3. Call write_articles() to persist results
    ↓
Concrete Implementations (injected functions)
    ↓
    - get_journal_articles: crossref_bibitem_gateway.get_journal_articles()
    - match_bibkey: closure over ODS index → domain.match_bibkey_to_article()
    - write_articles: imperative CSV writer
```

---

## Key Design Patterns

### 1. Gateway Pattern with Partial Application

**File**: `adapters/crossref/crossref_bibitem_gateway.py`

```python
# Configuration (plain NamedTuple, not Pydantic)
class CrossrefGatewayConfig(NamedTuple):
    client: CrossrefClient

# Gateway functions (config as first param)
def get_journal_articles(
    config: CrossrefGatewayConfig,
    main_in: JournalScraperIN,
) -> TJournalScraperOUT:
    # Implementation...

# Auto-configuration using partial application
def configure(config: CrossrefGatewayConfig) -> SimpleNamespace:
    """Binds all gateway functions to config using functools.partial"""
    # Uses inspect to find all functions with 'config' as first param
    # Returns namespace with partially-applied functions
```

**Usage**:
```python
cr_gtw_cfg = CrossrefGatewayConfig(client=crossref_client)
cr_gtw = crossref_bibitem_gateway.configure(cr_gtw_cfg)

# Now cr_gtw.get_journal_articles only needs main_in parameter
articles = cr_gtw.get_journal_articles(journal_scraper_in)
```

### 2. Function Signature-Based Dependency Injection

**File**: `ports/journal_scraping.py`

```python
# Abstract function signatures (type aliases)
type TJournalScraperFunction = Callable[[JournalScraperIN], TJournalScraperOUT]
type TBibkeyMatcher = Callable[[ParsedResult[BibItem]], ParsedResult[BibItem]]
type TArticleWriter = Callable[[Iterable[ParsedResult[BibItem]], str], None]

# Orchestration receives dependencies via Pydantic model
class JournalScraperMainIN(BaseModel):
    journal_scraper_in: JournalScraperIN
    get_journal_articles: TJournalScraperFunction
    match_bibkey: TBibkeyMatcher | None
    write_articles: TArticleWriter

    class Config:
        arbitrary_types_allowed = True  # Allow function types

# Abstract orchestration
def main(main_in: JournalScraperMainIN) -> None:
    articles = main_in.get_journal_articles(main_in.journal_scraper_in)
    if main_in.match_bibkey:
        articles = (main_in.match_bibkey(parsed) for parsed in articles)
    main_in.write_articles(articles, output_path)
```

### 3. Pure Domain Logic (Functional Core)

**File**: `domain/bibkey_matching.py`

```python
def match_bibkey_to_article(
    index: TJournalBibkeyIndex,
    parsed_result: ParsedResult[BibItem],
) -> ParsedResult[BibItem]:
    """
    Pure function: no I/O, no logging, no side effects.
    Given an index and a parsed article, returns the article
    with bibkey populated if found, unchanged otherwise.
    """
    # Pure data transformation only
    # Uses attrs.evolve for immutable updates
```

**Characteristics**:
- No I/O operations (no file reads, no API calls)
- No logging
- No mutations (uses `attrs.evolve` for immutable updates)
- Deterministic (same inputs → same outputs)
- Easily testable in isolation

### 4. Imperative Shell (CLI Layer)

**File**: `cli/crossref_journal_scraping_cli.py`

```python
def cli() -> None:
    """
    Imperative shell: handles all concrete decisions and side effects.
    """
    # 1. Load environment (side effect)
    load_dotenv()

    # 2. Parse arguments (side effect)
    args = parse_args()

    # 3. Validate at boundary (Pydantic)
    journal_scraper_in = JournalScraperIN(issn=args.issn, ...)

    # 4. Setup infrastructure (imperative, side effects)
    crossref_client = setup_crossref_client(load_env_vars())

    # 5. Create concrete implementations (imperative)
    if args.bibliography_path:
        # Load ODS file (side effect)
        index = hof_read_from_ods(column_names)(args.bibliography_path)
        # Create matcher closure
        bibkey_matcher = lambda p: match_bibkey_to_article(index, p)

    # 6. Wire everything and call orchestration
    main_in = JournalScraperMainIN(
        get_journal_articles=cr_gtw.get_journal_articles,
        match_bibkey=bibkey_matcher,
        write_articles=write_articles_to_csv,
    )
    main(main_in)
```

---

## Data Models

### Validation Strategy

| Context | Model Type | Purpose | Example |
|---------|-----------|---------|---------|
| **External input** | Pydantic `BaseModel` | Validate untrusted data at boundaries | `JournalScraperIN`, `JournalScraperBibkeyMatchingTabular` |
| **Internal config** | `NamedTuple` | Lightweight immutable config after validation | `CrossrefGatewayConfig` |
| **Type aliases** | `type` statements | Document function signatures | `TBibkeyMatcher`, `TArticleWriter` |
| **Domain models** | `@attrs` classes (from SDK) | Immutable business entities | `BibItem`, `Author`, `Journal` |

### Key Type Definitions

```python
# Generator-based streaming (memory efficient)
type TJournalScraperOUT = Generator[ParsedResult[BibItem], None, None]

# Result type for error handling
type ParsedResult[T] = ParsingSuccess[T] | ParsingError

ParsingSuccess = TypedDict with keys: "out", "parsing_status"
ParsingError = TypedDict with keys: "parsing_status", "message", "context"

# Function signatures for dependency injection
type TJournalScraperFunction = Callable[[JournalScraperIN], TJournalScraperOUT]
type TBibkeyMatcher = Callable[[ParsedResult[BibItem]], ParsedResult[BibItem]]
type TArticleWriter = Callable[[Iterable[ParsedResult[BibItem]], str], None]
```

---

## External Dependencies

### API Adapters

| Adapter | Purpose | Client Library |
|---------|---------|----------------|
| **Crossref** | Fetch article metadata by DOI, ISSN, year | `habanero` (Crossref API wrapper) |

### Data Processing

| Library | Purpose |
|---------|---------|
| `philoch-bib-sdk` | Core bibliographic models, parsers, formatters |
| `pydantic` | Input validation at boundaries |
| `attrs` | Immutable domain models |
| `polars` | Fast dataframe operations for CSV/ODS |
| `fastexcel` | ODS file reading |

### Utilities

| Library | Purpose |
|---------|---------|
| `aletk` | Custom utilities (logging, result monad) |
| `python-dotenv` | Environment variable loading |

---

## Testing Strategy

### Unit Tests

- **Domain logic**: Test pure functions in `domain/` with no mocking required
- **Converters**: Test data transformations in `adapters/crossref/crossref_converter.py`
- **Validators**: Test Pydantic models with invalid inputs

### Integration Tests

- **External APIs**: Marked with `@pytest.mark.external`, require real API access
- **Gateway pattern**: Test with real Crossref client (rate-limited)

### Test Configuration

```toml
[tool.pytest.ini_options]
markers = [
    "external: mark tests that require external API calls",
]
```

---

## Extension Points

### Adding a New Data Source

1. **Create adapter** in `adapters/<source_name>/`
   - Client wrapper (if API-based)
   - Models (Pydantic for validation)
   - Converter (raw data → `BibItem`)
   - Gateway with `configure()` pattern

2. **Create port** in `ports/`
   - Define input validation models (Pydantic)
   - Define function type aliases
   - Implement abstract orchestration

3. **Create CLI entry point** in `cli/<source_name>_<workflow>_cli.py`
   - Argument parsing
   - Environment setup
   - Dependency wiring
   - Call orchestration

4. **Add entry point** to `pyproject.toml`

### Adding a New Output Format

1. **Create writer adapter** in `adapters/writers/<format>.py`
   - Implement function matching `TArticleWriter` signature
   - Use imperative style (acceptable in adapter layer)

2. **Wire in CLI** - inject the writer function when calling orchestration

### Adding Business Logic

1. **Pure logic** → `domain/<feature>.py`
2. **Orchestration** → `ports/<workflow>.py`
3. **Concrete implementations** → `adapters/` or `cli/`

---

## File Organization

```
bib-enhancer/
├── docs/
│   ├── architecture.md              # This file
│   └── unstructured_data.md         # Data parsing documentation
├── philoch_bib_enhancer/
│   ├── domain/                      # Pure business logic
│   │   ├── __init__.py
│   │   └── bibkey_matching.py       # Pure bibkey matching function
│   ├── ports/                       # Abstract orchestration
│   │   ├── journal_scraping.py      # Main workflow coordination
│   │   └── bibitem_by_doi.py        # Type definitions for DOI lookup
│   ├── adapters/                    # Concrete I/O implementations
│   │   ├── crossref/
│   │   │   ├── crossref_client.py   # Habanero wrapper
│   │   │   ├── crossref_models.py   # Pydantic models for Crossref data
│   │   │   ├── crossref_converter.py # Raw JSON → BibItem conversion
│   │   │   └── crossref_bibitem_gateway.py # Gateway pattern implementation
│   │   └── blumbib/
│   │       └── blumbib_models.py    # Legacy bibliography format
│   └── cli/                         # Entry points (imperative shell)
│       ├── __init__.py
│       └── crossref_journal_scraping_cli.py  # CLI for Crossref journal scraping
├── tests/
│   ├── adapters/
│   ├── external/                    # Tests requiring API access
│   └── conftest.py
├── pyproject.toml                   # Dependencies and CLI entry points
└── README.md
```

---

## CLI Entry Points

Defined in `pyproject.toml`:

```toml
[tool.poetry.scripts]
scrape-journal = "philoch_bib_enhancer.cli.crossref_journal_scraping_cli:cli"
```

**Usage**:
```bash
# After installation
scrape-journal --issn "0012-2017" --start-year 2020 --end-year 2024

# During development
python -m philoch_bib_enhancer.cli.crossref_journal_scraping_cli \
  --issn "0012-2017" \
  --start-year 2020 \
  --end-year 2024 \
  --bibliography-path "path/to/biblio.ods"
```

---

## Environment Configuration

Required environment variables (loaded from `.env` file):

```bash
CROSSREF_EMAIL=your.email@example.com
```

The CLI automatically loads `.env` from the project root using `python-dotenv`.

---

## Error Handling

### Result Type Pattern

All data parsing operations return a `ParsedResult[T]` type:

```python
type ParsedResult[T] = ParsingSuccess[T] | ParsingError

# Success case
{"parsing_status": "success", "out": <BibItem>}

# Error case
{"parsing_status": "error", "message": "...", "context": "<raw data>"}
```

### Type Guard Helper

```python
def is_parsing_success[T](result: ParsedResult[T]) -> TypeGuard[ParsingSuccess[T]]:
    return result.get("parsing_status") == "success"
```

This allows batch processing to continue on partial failures while preserving error context.

---

## Performance Considerations

1. **Generator-based streaming** - Articles are processed lazily, reducing memory footprint
2. **Rate limiting** - Crossref API calls include `sleep(0.1)` to respect rate limits
3. **Batch processing** - CSV writing buffers results in memory before writing
4. **Polite pool access** - Crossref client uses email-based polite pool for faster access

---

## Version History

### 0.1.0 (2025-10-23)
- Refactored to functional core / imperative shell architecture
- Extracted pure domain logic to `domain/bibkey_matching.py`
- Created abstract orchestration in `ports/journal_scraping.py` (renamed from `procedures/`)
- Moved CLI wiring to `cli/crossref_journal_scraping_cli.py` with explicit adapter naming
- Added function-based dependency injection
- Improved separation of concerns across layers
- Established naming convention: adapter-specific files prefixed with adapter name (e.g., `crossref_*`)

---

## References

- **Crossref API**: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- **Habanero Documentation**: https://habanero.readthedocs.io/
- **Functional Core / Imperative Shell**: https://www.destroyallsoftware.com/screencasts/catalog/functional-core-imperative-shell
