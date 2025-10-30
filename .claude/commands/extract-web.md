---
description: Extract bibliographic references from a URL using RawText workflow
argument-hint: <url> [output-path]
---

Extract bibliographic references from the provided URL using the RawText manual workflow.

## IMPORTANT: Check Registry First!

**Before starting extraction, check if this URL or domain is in the registry:**
`philoch_bib_enhancer/adapters/raw_text/extractors/registry.json`

The registry contains:
- Past extraction experiences for specific sites
- Site characteristics (static HTML, dynamic JS, API endpoints)
- What methods worked (GET, POST, form parameters, etc.)
- Common pitfalls and solutions
- Expected entry counts
- Parameter formats required

If the site is in the registry, **follow the documented approach** rather than starting from scratch.

## RawText Manual Workflow

### 1. Fetch the Page
Use `fetch_url_text()` from `philoch_bib_enhancer.adapters.raw_text.web_scraper`

**Note:** If the site uses JavaScript rendering or API calls, check the registry for the correct approach.

### 2. Identify Bibliographic References
Read through the content and identify all bibliographic references:
- Articles
- Books
- Theses
- Book chapters (incollection)
- Conference papers
- etc.

### 3. Create RawTextBibitem Objects
For each reference, create a `RawTextBibitem` object with all extractable fields:

Required fields:
- `raw_text` - The exact text snippet with the reference
- `type` - Entry type: "article", "book", "incollection", "thesis", "mastersthesis", "phdthesis", etc.
- `title` - Publication title

Optional fields (extract when available):
- `year` - Publication year (int)
- `authors` - List of `RawTextAuthor` objects with `given` and `family` names
- `editors` - List of `RawTextAuthor` objects (for edited volumes)
- `journal` - Journal name
- `volume` - Volume number
- `number` - Issue number
- `start_page` - Starting page
- `end_page` - Ending page
- `publisher` - Publisher name
- `doi` - DOI identifier
- `url` - URL to publication

### 4. Convert to CSV
Use `process_raw_bibitems()` from `philoch_bib_enhancer.cli.manual_raw_text_to_csv` to convert to CSV format.

### Example Reference
See `examples/manual_workflow_example.py` for `RawTextBibitem` structure examples.

## Output

Default output path: `./data/test-2/`
Custom output path: $2 (if provided)

## Task

URL to extract: $1
Output path: ${2:-./data/test-2/}

**Steps:**
1. Check `philoch_bib_enhancer/adapters/raw_text/extractors/registry.json` for this URL/domain
2. If found in registry, follow the documented extraction method
3. If not in registry, use the standard RawText workflow above
4. Extract all bibliographic references
5. Create `RawTextBibitem` objects
6. Convert to CSV using `process_raw_bibitems()`
7. If this is a new site with unique characteristics, consider adding it to the registry
