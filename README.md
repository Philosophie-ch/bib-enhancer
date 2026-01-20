# Philosophie.ch Bibliography enhancer scripts

This repository contains scripts to enhance the bibliography of the [Philosophie.ch](https://philosophie.ch) website, by scraping different APIs and websites, and assuring the quality and consistency of the data.

## Installation

```bash
# Install dependencies with Poetry
poetry install
```

## CLI Tools

All commands should be run with `poetry run` or after activating the shell with `poetry shell`.

| Command | Description | How to run |
|---------|-------------|------------|
| `scrape-journal` | Scrape journal articles by ISSN via Crossref API | `poetry run scrape-journal --help` |
| `fuzzy-matcher` | Fuzzy match BibItems against bibliography | `poetry run fuzzy-matcher --help` |
| `raw_text_scraping_cli` | LLM-based web scraping for bibliographic data | `poetry run python -m philoch_bib_enhancer.cli.raw_text_scraping_cli --help` |
| `manual_raw_text_to_csv` | Convert RawTextBibitem JSON to CSV | `poetry run python -m philoch_bib_enhancer.cli.manual_raw_text_to_csv --help` |

### scrape-journal

Scrape journal articles from Crossref by ISSN and year range.

```bash
poetry run scrape-journal --issn 0031-8019 --start-year 2020 --end-year 2023
```

**Options:**
- `--issn, -i` (required): Journal ISSN
- `--start-year, -s` (required): Start year
- `--end-year, -e` (required): End year
- `--bibliography-path, -b`: Path to bibliography file (.ods)
- `--column-name-bibkey, -cb`: Column name for bibkey
- `--column-name-journal, -cj`: Column name for journal
- `--column-name-volume, -cv`: Column name for volume
- `--column-name-number, -cn`: Column name for issue number

### fuzzy-matcher

Match extracted BibItems against an existing bibliography using fuzzy string matching.

```bash
poetry run fuzzy-matcher \
  --input scraped_items.csv \
  --bibliography bibliography.ods \
  --output matched_results.csv
```

**Options:**
- `--input, -i` (required): Input file with BibItems (.csv or .ods)
- `--bibliography, -b` (required): Bibliography file (.ods)
- `--output, -o` (required): Output CSV path
- `--cache-dir, -c`: Cache directory (default: `data/cache`)
- `--top-n, -n`: Number of top matches (default: 5)
- `--min-score, -m`: Minimum score threshold (default: 0.0)
- `--force-rebuild`: Force rebuild of index cache
- `--force-python`: Use Python scorer instead of Rust

### raw_text_scraping_cli

Extract bibliographic data from web pages using LLMs.

```bash
poetry run python -m philoch_bib_enhancer.cli.raw_text_scraping_cli \
  --urls https://example.com/journal/issue/1 \
  --output scraped_items.csv
```

**Options:**
- `--urls, -u`: URLs to scrape (space-separated)
- `--urls-file, -f`: File containing URLs (one per line)
- `--output, -o` (required): Output CSV path
- `--bibliography-path, -b`: Path to bibliography file (.ods)
- `--column-name-*`: Column name configuration (same as scrape-journal)

### manual_raw_text_to_csv

Convert manually created RawTextBibitem JSON files to CSV format.

```bash
poetry run python -m philoch_bib_enhancer.cli.manual_raw_text_to_csv \
  --input raw_items.json \
  --output converted_items.csv
```

**Options:**
- `--input, -i` (required): Input JSON file
- `--output, -o` (required): Output CSV path
- `--bibliography-path, -b`: Path to bibliography file (.ods)
- `--column-name-*`: Column name configuration (same as scrape-journal)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CROSSREF_EMAIL` | Yes (for `scrape-journal`) | Email for Crossref API polite pool |
| `ANTHROPIC_API_KEY` | Yes (for `raw_text_scraping_cli` with Claude) | Anthropic API key |
| `OPENAI_API_KEY` | Yes (for `raw_text_scraping_cli` with OpenAI) | OpenAI API key |
| `LLM_SERVICE` | No | LLM provider: `claude` (default) or `openai` |
| `SCRAPE_JOURNAL_OUTPUT_DIR` | No | Output directory for scrape-journal (default: `.`) |

## Quick Examples

### Scrape a journal and match against bibliography

```bash
# Set required env vars
export CROSSREF_EMAIL="your.email@example.com"

# Scrape journal articles
poetry run scrape-journal \
  --issn 0031-8019 \
  --start-year 2020 \
  --end-year 2023 \
  --bibliography-path data/bibliography.ods

# Match results against bibliography
poetry run fuzzy-matcher \
  --input output.csv \
  --bibliography data/bibliography.ods \
  --output matched.csv
```

### LLM-based web scraping

```bash
# Set required env vars
export ANTHROPIC_API_KEY="sk-ant-..."

# Scrape from URLs
poetry run python -m philoch_bib_enhancer.cli.raw_text_scraping_cli \
  --urls-file urls.txt \
  --output scraped.csv \
  --bibliography-path data/bibliography.ods
```
