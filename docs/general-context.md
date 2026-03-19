# General Context

## What This Project Is

This is a **bibliography enhancement toolkit** for [Philosophie.ch](https://philosophie.ch), a Swiss philosophy portal. It automates the acquisition, parsing, matching, and quality assurance of bibliographic data (articles, books, chapters, theses, etc.) drawn from external APIs, web pages, and manual input.

The central data object is a **BibItem** -- a structured representation of a bibliographic entry (author, title, date, journal, volume, pages, DOI, etc.). Everything in this project either *produces* BibItems, *enriches* them, or *matches* them against an existing bibliography.

## What Problem It Solves

Philosophie.ch maintains a large bibliography (~209K entries) in ODS/CSV format. New entries arrive from heterogeneous sources: structured APIs (Crossref), unstructured web pages, and manual curation. This project provides tooling to:

1. **Scrape** article metadata from the Crossref API by journal ISSN and year range.
2. **Extract** bibliographic references from arbitrary web pages using LLMs (Claude or OpenAI) or manual input.
3. **Fuzzy-match** newly acquired entries against the existing bibliography to detect duplicates and assign bibkeys.
4. **Convert** between formats (JSON, CSV, ODS) and produce structured output for downstream use on the portal.

## Core Workflows

### 1. Journal Scraping (Crossref)

Input: journal ISSN + year range. Output: CSV of BibItems.

The system queries Crossref for all articles in the given journal/year window, converts raw API responses into BibItems, optionally matches them against an existing bibliography for bibkey assignment, and writes results to CSV.

CLI: `poetry run scrape-journal`

### 2. Web Page Extraction (RawText)

Input: one or more URLs. Output: CSV of BibItems.

An LLM service fetches and reads web pages, extracts bibliographic references into an intermediate `RawTextBibitem` model, then converts them to BibItems. A manual variant accepts JSON input instead of URLs.

CLI: `poetry run python -m philoch_bib_enhancer.cli.raw_text_scraping_cli`

### 3. Fuzzy Matching

Input: CSV/ODS of BibItems + the full bibliography. Output: CSV with top-N match candidates per entry.

Uses blocking indexes (DOI, title trigrams, author surnames, year decades, journals) to narrow the search space, then scores candidates using weighted fuzzy comparison of title, author, date, and bonus fields. An optional Rust extension (PyO3 + rayon) provides ~12x speedup over pure Python.

CLI: `poetry run fuzzy-matcher`

## Architecture

The codebase follows a **functional core / imperative shell** pattern organized as hexagonal (ports & adapters) architecture:

```
philoch_bib_enhancer/
  domain/       Pure business logic (no I/O, no side effects, deterministic)
  ports/        Abstract orchestration (delegates all I/O to injected functions)
  adapters/     Concrete I/O implementations (API clients, file readers, LLM services)
  cli/          Entry points (argument parsing, environment setup, dependency wiring)
```

Key design choices:

- **Pydantic at boundaries only** -- external data is validated with Pydantic models at entry points; internally the code uses lightweight types (NamedTuples, attrs classes, type aliases).
- **Function-based dependency injection** -- abstract orchestration functions receive concrete implementations as parameters (no classes, no DI containers). Type aliases (`Callable[[X], Y]`) serve as interfaces.
- **Generator-based streaming** -- data flows through lazy generator chains for constant memory usage regardless of input size.
- **Result type pattern** -- all parsing operations return `ParsedResult[T] = ParsingSuccess[T] | ParsingError`, allowing batch processing to continue on partial failures while preserving error context.

## Key Dependencies

| Dependency | Role |
|---|---|
| `philoch-bib-sdk` | Core bibliographic models (`BibItem`, `Author`, `Journal`), parsers, formatters, and fuzzy matching logic |
| `aletk` | Custom utility library (logging, result monad) |
| `habanero` | Python wrapper for the Crossref API |
| `polars` | Dataframe operations for CSV/ODS processing |
| `pydantic` | Input validation at system boundaries |
| `attrs` | Immutable domain models |
| `rust_scorer` (optional) | PyO3+rayon Rust extension for parallel fuzzy scoring |

## Code Style

- **Python 3.13**, strict mypy with `disallow_any_explicit`, `disallow_any_unimported`, `disallow_any_decorated`.
- No `Any`, no `cast()`, no `# type: ignore` without justification.
- Immutability preferred: tuples over lists, frozensets over sets, `frozen=True` on data classes.
- Comprehensions and generators over explicit loops.
- `logging` module instead of `print`.
- Conventional commits (`feat`, `fix`, `refactor`, `test`, `docs`, `chore`).

## Environment

The project uses **Poetry** for dependency management. CLI tools are run via `poetry run <command>`. Environment variables (loaded from `.env` via `python-dotenv`) configure API keys and paths:

- `CROSSREF_EMAIL` -- email for Crossref polite pool access
- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` -- LLM API keys for web extraction
- `LLM_SERVICE` -- LLM provider selection (`claude` or `openai`)

## Further Documentation

| Document | Content |
|---|---|
| `architecture.md` | Detailed layer responsibilities, data flow diagrams, extension points |
| `crossref_flow_analysis.md` | Step-by-step data transformation from Crossref API to CSV |
| `fuzzy_matcher.md` | Matching algorithm, scoring weights, Rust setup, CLI/API usage |
| `raw_text_usage.md` | LLM-based and manual extraction workflows, `RawTextBibitem` model |
| `unstructured_data.md` | Parsing patterns for authors, dates, pages, HTML bibliographies |
| `generic_style_guide.md` | Full Python style guide (typing, architecture, testing, formatting) |
| `todo/` | Planned features (HTML bibliography renderer, weight optimization) |
