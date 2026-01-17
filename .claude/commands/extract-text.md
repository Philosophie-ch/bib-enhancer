---
description: Extract bibliographic references from text files using RawText workflow
argument-hint: <file-path> [output-path]
---

Extract bibliographic references from the provided text file using the RawText manual workflow.

## Supported File Formats

**All text-based formats are supported**, including but not limited to:
- Plain text (.txt)
- PDF (.pdf)
- Word documents (.docx)
- BibTeX (.bib)
- Markdown (.md)
- HTML (.html)
- XML (.xml)
- Any other text-extractable format

If the format is not directly readable, determine the appropriate extraction method or library.

## Important: Check the Registry First!

**Before starting extraction**, check the extractors registry for documented experience with similar formats:

**Registry location:** `philoch_bib_enhancer/adapters/raw_text/extractors/registry.json`

The registry documents:
- ✅ **Proven extraction methods** - Libraries and approaches that work
- ✅ **Common challenges & solutions** - Text cleaning, quote handling, OCR fixes
- ✅ **Reference implementations** - Working scripts you can adapt

**Known formats in registry:**
- `.bib` files → `extract_bibtex.py` (LaTeX cleaning, author parsing)
- `.pdf` files → `parse_pdf_bibliography.py` (curly quotes, line-break hyphens, OCR artifacts)

**If format is NOT in registry:**
- Analyze the file structure
- Choose appropriate extraction library
- Apply similar text cleaning techniques from related formats
- Document your approach for future reference

## RawText Manual Workflow

### 1. Read the File Content

Depending on the file type:
- **Plain text**: Use standard file reading
- **PDF**: Use appropriate PDF extraction library (e.g., `pypdf`, `pdfplumber`, or `pymupdf`)
- **.docx**: Use `python-docx` library

Extract the text content from the file.

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

File to extract: $1
Output path: ${2:-./data/test-2/}

**Steps:**

### 0. Environment Setup (CRITICAL)
**FORBIDDEN: Never use plain `python` or `python3` directly!**

Always use the virtual environment:
```bash
source .venv/bin/activate && python <your_script.py>
```

If `.venv` doesn't exist, create it first:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # or install needed packages
```

### 1. Check Registry
- Read `philoch_bib_enhancer/adapters/raw_text/extractors/registry.json`
- Look for matching file format (`.bib`, `.pdf`, `.docx`, etc.)
- If found: use documented approach and reference scripts

### 2. Read File Content
- Use appropriate method based on file extension
- For known formats, use proven libraries from registry

### 3. Extract Bibliographic References
- Parse and identify all bibliographic entries
- Create `RawTextBibitem` objects for each reference
- Apply text cleaning (see registry for common issues):
  - Remove line-break hyphens (preserve real compounds)
  - Fix OCR artifacts (accented characters)
  - Handle curly/typographic quotes
  - Clean DOI trailing punctuation
  - Strip unnecessary quotes from titles

### 4. Convert to CSV
- Use `process_raw_bibitems()` from `philoch_bib_enhancer.cli.manual_raw_text_to_csv`
- This ensures proper SDK conversion and formatting

### 5. Quality Assurance (MANDATORY)
**You MUST QA the resulting CSV before finishing!**

Check for:
- ✅ **No unnecessary quotes** in titles (quotes in CSV delimiters are OK, but data itself shouldn't have extra quotes)
- ✅ **Proper encoding** of accented characters (Alchourrón not Alchourr´ on)
- ✅ **No line-break artifacts** (Understanding not Understand- ing)
- ✅ **Clean DOIs** (no trailing dots or commas)
- ✅ **Entry types** properly formatted (@article, @book, etc.)
- ✅ **Authors** properly parsed (no weird quote marks)

**QA Commands:**
```bash
# Check sample entries
head -10 output.csv | cut -d',' -f3,5,12,14

# Check for common issues
grep "- " output.csv | head -5  # Line-break hyphens
grep "´\|¨\|`" output.csv | head -5  # OCR artifacts
tail -20 output.csv | cut -d',' -f14  # Check titles

# Count entries
wc -l output.csv
```

If issues found, fix them before declaring success!
