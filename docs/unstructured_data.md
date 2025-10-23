# Parsing Unstructured Bibliographic Data & Crossref API Integration

This document provides a comprehensive guide to bibliographic data parsing and Crossref DOI metadata retrieval in the `biblioUtils` project.

---

## Table of Contents

1. [Parsing Unstructured Bibliographic Data](#1-parsing-unstructured-bibliographic-data)
2. [Crossref API Integration](#2-crossref-api-integration)
3. [Practical Examples](#3-practical-examples)
4. [Key Libraries and Tools](#4-key-libraries-and-tools)
5. [Common Patterns](#5-common-patterns)

---

## 1. Parsing Unstructured Bibliographic Data

### Overview

The project contains multiple scripts that parse unstructured bibliographic data from local sources (CSV, ODS, HTML) and convert them to structured objects ready for DOI registration or metadata exchange.

### 1.1 Bibliography to Metadata JSON Converter

**File:** [src/utils/bibliography_to_metadata_json.py](src/utils/bibliography_to_metadata_json.py)

**Purpose:** Converts bibliography entries to structured JSON metadata for article publications.

**Input Sources:**
- CSV or ODS files with a `bibkey` column
- Bibliography ODS file (loaded from `BIBLIOGRAPHY_ODS_PATH` environment variable)

**Unstructured Parsing Capabilities:**

1. **Page Range Parsing**
   ```python
   from philoch_bib_sdk.converters.plaintext.bibitem.pages_parser import parse_pages as sdk_parse_pages

   # Handles formats like:
   # "123--145" (LaTeX double dash)
   # "123-145" (single dash)
   # "123" (single page)

   pages_result = sdk_parse_pages("123--145")
   # Returns: Ok with PageAttr(start="123", end="145")
   ```

2. **Date/Year Extraction**
   ```python
   from philoch_bib_sdk.converters.plaintext.bibitem.date_parser import parse_date
   from philoch_bib_sdk.logic.models import TBibString

   # Extracts year from unstructured date strings
   result = parse_date(TBibString("2024-05-15"))
   if isinstance(result, Ok):
       year = result.value.year  # "2024"
   ```

3. **Language ID Parsing**
   ```python
   from philoch_bib_sdk.converters.plaintext.bibitem.parser import _parse_language_id

   # Converts language identifiers to ISO 639-1 codes
   LANGUAGE_ID_TO_ISO_MAP = {
       "english": "en",
       "ngerman": "de",  # new German orthography
       "french": "fr",
       # ... etc
   }

   language_id = _parse_language_id("ngerman")  # Returns "ngerman"
   iso_code = LANGUAGE_ID_TO_ISO_MAP.get(language_id, "en")  # Returns "de"
   ```

4. **Keywords Parsing**
   ```python
   from philoch_bib_sdk.converters.plaintext.bibitem.parser import _parse_keywords

   # Parses hierarchical keyword structures
   kw_level1 = "Philosophy"
   kw_level2 = "Epistemology"
   kw_level3 = "Foundationalism"

   keywords_attr = _parse_keywords(kw_level1, kw_level2, kw_level3)
   # Returns structured keyword hierarchy
   ```

**Output Format:**
```json
{
  "type": "article",
  "year": "2024",
  "issue": "1",
  "pages": "123-145",
  "start_page": "123",
  "end_page": "145",
  "volume": "78",
  "journal": "Dialectica",
  "license": "CC BY 4.0",
  "language": "en",
  "journal_issn": "1746-8361",
  "publication_status": "published",
  "keywords": ["Philosophy", "Epistemology", "Foundationalism"]
}
```

**Usage Example:**
```bash
# Basic usage
python src/utils/bibliography_to_metadata_json.py input.csv output.csv

# With custom bibliography path
python src/utils/bibliography_to_metadata_json.py input.csv output.csv \
    --bibliography /path/to/bib.ods

# Custom bibkey column name
python src/utils/bibliography_to_metadata_json.py input.csv output.csv \
    --bibkey-column my_bibkey
```

**Output CSV Structure:**
```csv
bibkey,metadata_json,status,message
smith-2021,"{\"type\":\"article\",\"year\":\"2021\",...}",success,
jones-2020,"{\"type\":\"article\",\"year\":\"2020\",...}",success,
missing-key,"",error,Bibkey not found in bibliography: missing-key
```

---

### 1.2 Journal Issues to Metadata JSON Converter

**File:** [src/utils/journal_issues_to_metadata_json.py](src/utils/journal_issues_to_metadata_json.py)

**Purpose:** Extracts structured metadata from journal issue titles and descriptions.

**Unstructured Parsing Capabilities:**

1. **Title Pattern Extraction**
   ```python
   import re

   def parse_journal_issue_title(title: str) -> Dict[str, str]:
       """
       Parse journal issue title to extract volume, issue, and year.

       Expected formats:
       - "Dialectica 23(1), 1969"
       - "Dialectica 72(3), 2018"
       - "Journal Name 12(3-4), 2020"
       """
       pattern = r'^(.+?)\s+(\d+)\(([^)]+)\),\s*(\d{4})$'
       match = re.match(pattern, title.strip())

       if match:
           return {
               'journal': match.group(1).strip(),
               'volume': match.group(2),
               'issue': match.group(3),
               'year': match.group(4)
           }
       return {'journal': '', 'volume': '', 'issue': '', 'year': ''}
   ```

2. **Special Issue Title Extraction**
   ```python
   def extract_special_issue_title(lead_text: str) -> str:
       """
       Extract special issue title from lead_text.
       Expected: 'special issue "Title Here", guest ed. ...'
       """
       pattern = r'special issue\s+"([^"]+)"'
       match = re.search(pattern, lead_text, re.IGNORECASE)

       if match:
           return match.group(1).strip()
       return ''
   ```

**Input CSV Example:**
```csv
doi,title,language_code,published,lead_text
10.1111/1746-8361.12345,"Dialectica 78(1), 2024",en,published,"special issue \"Formal Epistemology\", guest ed. Jane Smith"
```

**Output Format:**
```json
{
  "type": "journal_issue",
  "issn": "1746-8361",
  "volume": "78",
  "issue": "1",
  "year": 2024,
  "license": "",
  "language": "en",
  "keywords": [],
  "publication_status": "published",
  "title": "Formal Epistemology"
}
```

**Usage Example:**
```bash
python src/utils/journal_issues_to_metadata_json.py journal_issues.csv output.csv
```

---

### 1.3 Bibliography Enrichment Module

**File:** [src/crossref_doi_api/bibliography_enrichment.py](src/crossref_doi_api/bibliography_enrichment.py)

**Purpose:** Enriches minimal CSV data by looking up full metadata from bibliography ODS files.

**Key Class: `BibliographyEnricher`**

```python
from src.crossref_doi_api.bibliography_enrichment import BibliographyEnricher

# Initialize with bibliography path (or uses BIBLIOGRAPHY_ODS_PATH env var)
enricher = BibliographyEnricher(
    bibliography_path="/path/to/bibliography.ods",
    authors_csv_path="/path/to/authors.csv"  # Optional
)

# Look up a single bibkey
metadata = enricher.enrich_metadata("smith-2024-epistemology")
```

**Author String Parsing**

The most complex unstructured parsing happens here:

```python
def parse_authors(self, author_string: str) -> List[Dict[str, str]]:
    """
    Parse author string using philch-bib-sdk parser.

    Format: "family, given and family, given"
    Example: "Müller, Hans and Schmidt, Anna and Johnson"
    """
    from philoch_bib_sdk.converters.plaintext.author.parser import parse_author

    result = parse_author(author_string, "simplified")

    if isinstance(result, Ok):
        authors = result.out
        parsed_authors = []

        for author in authors:
            given_name = str(author.given_name.simplified) if author.given_name.simplified else ""
            family_name = str(author.family_name.simplified) if author.family_name.simplified else ""
            mononym = str(author.mononym.simplified) if author.mononym.simplified else ""

            if mononym:
                # For mononyms, use as surname
                parsed_authors.append({"given_name": "", "surname": mononym})
            else:
                parsed_authors.append({"given_name": given_name, "surname": family_name})

        return parsed_authors
    else:
        # Fallback to manual parsing
        return self._parse_authors_fallback(author_string)
```

**Fallback Author Parsing** (if SDK not available):

```python
def _parse_authors_fallback(self, author_string: str) -> List[Dict[str, str]]:
    """
    Simple fallback: split on " and ", then split on comma.
    """
    authors = []
    parts = author_string.split(" and ")

    for part in parts:
        part = part.strip()
        if "," in part:
            surname, given = part.split(",", 1)
            authors.append({"given_name": given.strip(), "surname": surname.strip()})
        else:
            # No comma, assume mononym or surname only
            authors.append({"given_name": "", "surname": part.strip()})

    return authors
```

**Page Range Parsing:**

```python
def parse_pages(self, pages_string: Optional[str]) -> Tuple[str, str]:
    """
    Parse page range into first and last page.
    Handles: "123--145", "123-145", "123"
    """
    if not pages_string:
        return ("", "")

    pages_string = str(pages_string).strip()

    # Handle double dash (LaTeX)
    if "--" in pages_string:
        parts = pages_string.split("--", 1)
    elif "-" in pages_string:
        parts = pages_string.split("-", 1)
    else:
        # Single page
        return (pages_string, pages_string)

    if len(parts) == 2:
        return (parts[0].strip(), parts[1].strip())

    return ("", "")
```

**Date Parsing with SDK:**

```python
from philoch_bib_sdk.converters.plaintext.bibitem.date_parser import parse_date

date_result = parse_date(str(date_field))

if isinstance(date_result, Ok):
    date_value = date_result.out
    if isinstance(date_value, BibItemDateAttr):
        enriched["_year"] = date_value.year
```

**Field Mapping:**

| Bibliography Field | Enriched Field | Transformation |
|-------------------|----------------|----------------|
| `bibkey` | `bibkey` | Direct copy |
| `author` | `author_given_name`, `author_surname`, `additional_authors` | Parse with SDK |
| `editor` | `author_given_name`, `author_surname`, `contributor_role` | Parse if no author |
| `title` | `title` | Direct copy |
| `date` | `_year` | Extract year with SDK |
| `journal` | `journal_title` | Direct copy |
| `volume` | `volume` | Direct copy |
| `number` | `issue` | Direct copy (rename) |
| `pages` | `first_page`, `last_page` | Parse range |
| `doi` | `existing_doi` | Direct copy |
| `url` | `url` | Direct copy |
| `publisher` | `publisher` | Direct copy |
| `address` | `publisher_place` | Direct copy |
| `_langid` | `language` | Direct copy |

**Usage Example:**

```python
from src.crossref_doi_api.bibliography_enrichment import enrich_csv_with_bibliography

# Enrich a minimal CSV with just bibkeys
enriched_data = enrich_csv_with_bibliography(
    csv_path="minimal.csv",
    bibliography_path="/path/to/bibliography.ods",
    bibkey_column="bibkey"
)

# enriched_data is a list of dictionaries with full metadata
for entry in enriched_data:
    print(f"{entry['bibkey']}: {entry['title']} by {entry['author_surname']}")
```

---

### 1.4 HTML Bibliography Parsing

**File:** [src/ref_pipe/prep_divs.py](src/ref_pipe/prep_divs.py)

**Purpose:** Parses HTML bibliography entries using BeautifulSoup.

**Key Functionality:**

```python
from bs4 import BeautifulSoup, Tag

def extract_divs(html_bib_file: BibentityHTMLRawFile) -> Generator[BibDiv, None, None]:
    """
    Extract bibliography divs from HTML file.
    """
    with open(html_bib_file.local_path, "r") as f:
        bib_html_content = f.read()

    # Parse with BeautifulSoup
    soup = BeautifulSoup(bib_html_content, features="html.parser")
    divs_all = soup.find_all('div')
    divs = (div for div in divs_all if isinstance(div, Tag))

    # Extract bibkeys from div IDs
    bibdivs = (
        BibDiv(div_id=bs_get_div_bibkey(div), content=div.__str__())
        for div in divs
        if bs_get_div_bibkey(div) != ""
    )

    return bibdivs
```

**Bibkey Extraction from HTML:**

```python
def get_bibkey_from_div_id(div_id: str) -> str:
    """
    Extract bibkey from div ID.

    Assumes IDs of the shape: `ref-<entity_key>-<bibkey>`
    where <bibkey> can contain "-"

    Examples:
    - ref-c1-ashby_n:2002
    - ref-c1-caruso_em-etal:2008
    """
    try:
        bibkey = "-".join(div_id.split('-')[2:])
    except IndexError:
        return ""

    return bibkey

def bs_get_div_bibkey(page_element: Tag) -> str:
    """Get bibkey from BeautifulSoup Tag."""
    bs_getter = page_element.get('id')
    match bs_getter:
        case None:
            return ""
        case _:
            return get_bibkey_from_div_id(bs_getter.__str__())
```

**Usage Example:**

```python
from src.ref_pipe.prep_divs import gen_bib_html_divs

bibdivs_dict = gen_bib_html_divs(
    bibentity=bibentity,
    bibliography=bibliography,
    local_base_dir="/path/to/local",
    container_base_dir="/path/in/container",
    relative_output_dir="output",
    container_name="dltc-container"
)

# bibdivs_dict is {bibkey: html_content}
```

---

## 2. Crossref API Integration

### Overview

The project uses the **Habanero** library (Python wrapper for Crossref API) to fetch existing DOI metadata from Crossref.

### 2.1 Crossref Gateway

**File:** [src/dltc_backcatalog/crossref_gateway.py](src/dltc_backcatalog/crossref_gateway.py)

**Purpose:** Provides a simple interface to initialize Crossref API client.

**Complete Code:**

```python
from typing import Tuple
from habanero import Crossref
from aletk.ResultMonad import Ok, Err

type TEmailAddress = str
type TCrossrefCredentials = Tuple[TEmailAddress,]

def get_crossref_client(crossref_credentials: TCrossrefCredentials) -> Ok[Crossref] | Err:
    """
    Initializes a Crossref client using the "polite" pool.
    For this, you need to provide an email address.

    The polite pool gives you faster API access by identifying yourself.
    """
    try:
        (email_address,) = crossref_credentials

        cr = Crossref(mailto=email_address)

        return Ok(out=cr)

    except Exception as e:
        return Err(
            message=f"Crossref client could not be initialized:\n{e}",
            code=-1,
        )
```

**Usage Example:**

```python
from src.dltc_backcatalog.crossref_gateway import get_crossref_client

# Initialize client
result = get_crossref_client(("your.email@example.com",))

if isinstance(result, Ok):
    cr = result.out

    # Now use the Crossref client
    # ...
else:
    print(f"Error: {result.message}")
```

---

### 2.2 Habanero API Usage Patterns

**Installation:**
```bash
pip install habanero
```

**Common Operations:**

#### 2.2.1 Search for Works by DOI

```python
from habanero import Crossref

cr = Crossref(mailto="your.email@example.com")

# Get metadata for a specific DOI
doi = "10.1111/1746-8361.12000"
work = cr.works(ids=doi)

# Access metadata
metadata = work['message']
title = metadata['title'][0]
authors = metadata['author']
journal = metadata['container-title'][0]
volume = metadata['volume']
issue = metadata['issue']
year = metadata['published']['date-parts'][0][0]

print(f"Title: {title}")
print(f"Journal: {journal} {volume}({issue}), {year}")
```

#### 2.2.2 Search for Works by Title

```python
# Search by title
results = cr.works(query="epistemology dialectica", limit=10)

for item in results['message']['items']:
    doi = item.get('DOI', 'No DOI')
    title = item.get('title', ['No title'])[0]
    print(f"{doi}: {title}")
```

#### 2.2.3 Get Journal Metadata

```python
# Get journal information by ISSN
issn = "1746-8361"  # Dialectica
journal = cr.journals(ids=issn)

metadata = journal['message']
journal_title = metadata['title']
publisher = metadata['publisher']
total_dois = metadata['counts']['total-dois']

print(f"{journal_title} ({publisher})")
print(f"Total DOIs registered: {total_dois}")
```

#### 2.2.4 Get Works for a Specific Journal

```python
# Get all works for a journal
issn = "1746-8361"
works = cr.journals(ids=issn, works=True, limit=100)

for item in works['message']['items']:
    doi = item.get('DOI')
    title = item.get('title', [''])[0]
    year = item.get('published', {}).get('date-parts', [[None]])[0][0]
    print(f"{year}: {title} ({doi})")
```

#### 2.2.5 Filter by Publication Date

```python
# Get works published in a specific year range
results = cr.works(
    filter={'from-pub-date': '2020-01-01', 'until-pub-date': '2024-12-31'},
    limit=100
)

for item in results['message']['items']:
    title = item.get('title', [''])[0]
    doi = item.get('DOI')
    print(f"{title}: {doi}")
```

#### 2.2.6 Pagination

```python
# Paginate through results
cursor = "*"
batch_size = 100
total_fetched = 0

while True:
    results = cr.works(
        filter={'issn': '1746-8361'},
        cursor=cursor,
        limit=batch_size
    )

    items = results['message']['items']
    if not items:
        break

    for item in items:
        # Process each item
        doi = item.get('DOI')
        print(doi)
        total_fetched += 1

    # Get next cursor
    cursor = results['message'].get('next-cursor')
    if not cursor:
        break

print(f"Total fetched: {total_fetched}")
```

---

### 2.3 Example Crossref Metadata Structure

**Sample DOI Metadata:**

```json
{
  "DOI": "10.1111/1746-8361.12000",
  "type": "journal-article",
  "title": ["On the Nature of Truth"],
  "author": [
    {
      "given": "John",
      "family": "Smith",
      "sequence": "first",
      "affiliation": []
    },
    {
      "given": "Jane",
      "family": "Doe",
      "sequence": "additional",
      "affiliation": []
    }
  ],
  "container-title": ["Dialectica"],
  "volume": "78",
  "issue": "1",
  "page": "123-145",
  "published": {
    "date-parts": [[2024, 3, 15]]
  },
  "ISSN": ["1746-8361"],
  "publisher": "Wiley",
  "URL": "https://example.com/article",
  "abstract": "<jats:p>Abstract text here...</jats:p>",
  "license": [
    {
      "URL": "https://creativecommons.org/licenses/by/4.0/",
      "content-version": "vor"
    }
  ],
  "subject": ["Philosophy"]
}
```

---

## 3. Practical Examples

### Example 1: Parse Bibliography and Create DOI Registration CSV

```python
#!/usr/bin/env python3
"""
Example: Parse bibliography entries and create metadata JSON for DOI registration.
"""

from pathlib import Path
from src.utils.bibliography_to_metadata_json import main

# Input CSV with bibkeys
input_csv = Path("articles_to_register.csv")

# Output CSV with metadata JSON
output_csv = Path("articles_metadata.csv")

# Bibliography ODS file
bibliography_path = Path("/path/to/bibliography.ods")

# Run the converter
main(
    input_file=input_csv,
    output_file=output_csv,
    bibliography_path=bibliography_path,
    bibkey_column="bibkey"
)

print(f"✅ Generated metadata JSON CSV: {output_csv}")
```

**Input CSV (`articles_to_register.csv`):**
```csv
bibkey
smith-2024-epistemology
jones-2023-ethics
mueller-2024-metaphysics
```

**Output CSV (`articles_metadata.csv`):**
```csv
bibkey,metadata_json,status,message
smith-2024-epistemology,"{\"type\":\"article\",\"year\":\"2024\",\"issue\":\"1\",\"pages\":\"123-145\",\"start_page\":\"123\",\"end_page\":\"145\",\"volume\":\"78\",\"journal\":\"Dialectica\",\"license\":\"\",\"language\":\"en\",\"journal_issn\":\"1746-8361\",\"publication_status\":\"published\",\"keywords\":[\"Epistemology\",\"Knowledge\"]}",success,
jones-2023-ethics,"{\"type\":\"article\",\"year\":\"2023\",...}",success,
mueller-2024-metaphysics,"{\"type\":\"article\",\"year\":\"2024\",...}",success,
```

---

### Example 2: Fetch DOI Metadata from Crossref

```python
#!/usr/bin/env python3
"""
Example: Fetch metadata for existing DOIs from Crossref API.
"""

from habanero import Crossref
from src.dltc_backcatalog.crossref_gateway import get_crossref_client

# Initialize Crossref client
result = get_crossref_client(("your.email@example.com",))

if isinstance(result, Ok):
    cr = result.out
else:
    print(f"Error initializing client: {result.message}")
    exit(1)

# DOIs to fetch
dois = [
    "10.1111/1746-8361.12000",
    "10.1111/1746-8361.12001",
    "10.1111/1746-8361.12002"
]

# Fetch metadata for each DOI
for doi in dois:
    try:
        work = cr.works(ids=doi)
        metadata = work['message']

        title = metadata.get('title', ['No title'])[0]
        authors = metadata.get('author', [])
        author_names = [f"{a.get('given', '')} {a.get('family', '')}" for a in authors]
        year = metadata.get('published', {}).get('date-parts', [[None]])[0][0]

        print(f"\nDOI: {doi}")
        print(f"Title: {title}")
        print(f"Authors: {', '.join(author_names)}")
        print(f"Year: {year}")

    except Exception as e:
        print(f"Error fetching {doi}: {e}")
```

**Output:**
```
DOI: 10.1111/1746-8361.12000
Title: On the Nature of Truth
Authors: John Smith, Jane Doe
Year: 2024

DOI: 10.1111/1746-8361.12001
Title: Ethics in the Modern Age
Authors: Robert Jones
Year: 2023
...
```

---

### Example 3: Enrich CSV with Bibliography Metadata

```python
#!/usr/bin/env python3
"""
Example: Enrich a minimal CSV with full bibliography metadata.
"""

from src.crossref_doi_api.bibliography_enrichment import BibliographyEnricher

# Initialize enricher
enricher = BibliographyEnricher(
    bibliography_path="/path/to/bibliography.ods"
)

# Minimal bibkeys to enrich
bibkeys = [
    "smith-2024-epistemology",
    "jones-2023-ethics",
    "mueller-2024-metaphysics"
]

# Enrich each bibkey
for bibkey in bibkeys:
    metadata = enricher.enrich_metadata(bibkey)

    if metadata:
        print(f"\n✅ {bibkey}")
        print(f"   Title: {metadata.get('title', 'N/A')}")
        print(f"   Authors: {metadata.get('author_surname', 'N/A')}, {metadata.get('author_given_name', 'N/A')}")
        print(f"   Journal: {metadata.get('journal_title', 'N/A')}")
        print(f"   Year: {metadata.get('_year', 'N/A')}")
        print(f"   Pages: {metadata.get('first_page', '')}-{metadata.get('last_page', '')}")

        # Additional authors
        if metadata.get('additional_authors'):
            print(f"   Additional Authors:")
            for author in metadata['additional_authors']:
                print(f"      - {author['surname']}, {author['given_name']}")
    else:
        print(f"\n❌ {bibkey}: Not found in bibliography")
```

**Output:**
```
✅ smith-2024-epistemology
   Title: On the Nature of Truth
   Authors: Smith, John
   Journal: Dialectica
   Year: 2024
   Pages: 123-145
   Additional Authors:
      - Doe, Jane

✅ jones-2023-ethics
   Title: Ethics in the Modern Age
   Authors: Jones, Robert
   Journal: Dialectica
   Year: 2023
   Pages: 56-78
...
```

---

### Example 4: Parse Journal Issue Titles

```python
#!/usr/bin/env python3
"""
Example: Parse journal issue titles to extract volume, issue, and year.
"""

from src.utils.journal_issues_to_metadata_json import parse_journal_issue_title, extract_special_issue_title

# Sample journal issue titles
titles = [
    "Dialectica 78(1), 2024",
    "Dialectica 72(3), 2018",
    "Dialectica 67(2-3), 2013"
]

lead_texts = [
    'special issue "Formal Epistemology", guest ed. Jane Smith',
    'special issue "Ethics and AI", guest ed. Robert Jones',
    'regular issue'
]

for title, lead_text in zip(titles, lead_texts):
    parsed = parse_journal_issue_title(title)
    special_title = extract_special_issue_title(lead_text)

    print(f"\nOriginal: {title}")
    print(f"Journal: {parsed['journal']}")
    print(f"Volume: {parsed['volume']}")
    print(f"Issue: {parsed['issue']}")
    print(f"Year: {parsed['year']}")

    if special_title:
        print(f"Special Issue Title: {special_title}")
```

**Output:**
```
Original: Dialectica 78(1), 2024
Journal: Dialectica
Volume: 78
Issue: 1
Year: 2024
Special Issue Title: Formal Epistemology

Original: Dialectica 72(3), 2018
Journal: Dialectica
Volume: 72
Issue: 3
Year: 2018
Special Issue Title: Ethics and AI

Original: Dialectica 67(2-3), 2013
Journal: Dialectica
Volume: 67
Issue: 2-3
Year: 2013
```

---

### Example 5: Complete Workflow - Fetch from Crossref and Compare with Local Data

```python
#!/usr/bin/env python3
"""
Example: Fetch DOI metadata from Crossref and compare with local bibliography.
"""

from habanero import Crossref
from src.crossref_doi_api.bibliography_enrichment import BibliographyEnricher

# Initialize clients
cr = Crossref(mailto="your.email@example.com")
enricher = BibliographyEnricher(bibliography_path="/path/to/bibliography.ods")

# DOI to compare
doi = "10.1111/1746-8361.12000"
bibkey = "smith-2024-epistemology"

# Fetch from Crossref
print("📥 Fetching from Crossref API...")
crossref_work = cr.works(ids=doi)
crossref_metadata = crossref_work['message']

crossref_title = crossref_metadata.get('title', [''])[0]
crossref_authors = crossref_metadata.get('author', [])
crossref_year = crossref_metadata.get('published', {}).get('date-parts', [[None]])[0][0]

print(f"Crossref Title: {crossref_title}")
print(f"Crossref Year: {crossref_year}")

# Fetch from local bibliography
print("\n📚 Fetching from local bibliography...")
local_metadata = enricher.enrich_metadata(bibkey)

if local_metadata:
    local_title = local_metadata.get('title', 'N/A')
    local_year = local_metadata.get('_year', 'N/A')

    print(f"Local Title: {local_title}")
    print(f"Local Year: {local_year}")

    # Compare
    print("\n🔍 Comparison:")
    print(f"Titles match: {crossref_title == local_title}")
    print(f"Years match: {str(crossref_year) == str(local_year)}")
else:
    print("❌ Bibkey not found in local bibliography")
```

**Output:**
```
📥 Fetching from Crossref API...
Crossref Title: On the Nature of Truth
Crossref Year: 2024

📚 Fetching from local bibliography...
Local Title: On the Nature of Truth
Local Year: 2024

🔍 Comparison:
Titles match: True
Years match: True
```

---

## 4. Key Libraries and Tools

### 4.1 philch-bib-sdk

**Purpose:** Semantic parsing of bibliography fields.

**Installation:**
```bash
pip install philoch-bib-sdk
```

**Key Modules:**

1. **Author Parser**
   ```python
   from philoch_bib_sdk.converters.plaintext.author.parser import parse_author
   ```

2. **Date Parser**
   ```python
   from philoch_bib_sdk.converters.plaintext.bibitem.date_parser import parse_date
   ```

3. **Pages Parser**
   ```python
   from philoch_bib_sdk.converters.plaintext.bibitem.pages_parser import parse_pages
   ```

4. **Field Parsers**
   ```python
   from philoch_bib_sdk.converters.plaintext.bibitem.parser import (
       _parse_keywords,
       _parse_entry_type,
       _parse_language_id,
       _parse_pubstate,
   )
   ```

### 4.2 Habanero

**Purpose:** Python wrapper for Crossref API.

**Installation:**
```bash
pip install habanero
```

**Key Features:**
- Search by DOI, title, author, etc.
- Get journal metadata by ISSN
- Pagination support
- Polite pool for faster access
- Filter by date, type, publisher, etc.

**Documentation:** https://habanero.readthedocs.io/

### 4.3 Polars

**Purpose:** Fast dataframe operations for CSV/ODS processing.

**Installation:**
```bash
pip install polars
```

**Usage in Project:**
```python
import polars as pl

# Read ODS file
df = pl.read_ods("bibliography.ods", has_header=True, drop_empty_rows=True)

# Read CSV file
df = pl.read_csv("data.csv")

# Filter rows
matches = df.filter(pl.col("bibkey") == "smith-2024")

# Convert to dictionary
row_dict = matches.row(0, named=True)
```

### 4.4 BeautifulSoup

**Purpose:** HTML parsing.

**Installation:**
```bash
pip install beautifulsoup4
```

**Usage in Project:**
```python
from bs4 import BeautifulSoup, Tag

# Parse HTML
soup = BeautifulSoup(html_content, features="html.parser")

# Find all divs
divs = soup.find_all('div')

# Extract attributes
for div in divs:
    if isinstance(div, Tag):
        div_id = div.get('id')
        content = div.__str__()
```

### 4.5 Pydantic

**Purpose:** JSON validation and structure.

**Installation:**
```bash
pip install pydantic
```

**Usage in Project:**
```python
from pydantic import BaseModel, Field
from typing import Optional, List

class ArticleMetadata(BaseModel):
    type: str = "article"
    year: int
    issue: str
    pages: str
    start_page: Optional[str] = ""
    end_page: Optional[str] = ""
    volume: str
    journal: str
    license: str = ""
    language: str = "en"
    journal_issn: str
    publication_status: str = ""
    keywords: List[str] = []
```

---

## 5. Common Patterns

### 5.1 Result Monad Pattern

The project uses a custom Result monad for error handling:

```python
from aletk.ResultMonad import Ok, Err

def some_operation() -> Ok[SomeType] | Err:
    try:
        result = do_something()
        return Ok(out=result)
    except Exception as e:
        return Err(message=str(e), code=-1)

# Usage
result = some_operation()

if isinstance(result, Ok):
    value = result.out
    # Use value
else:
    print(f"Error: {result.message}")
```

### 5.2 Environment Variables Pattern

Configuration is loaded from `.env` file:

```python
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get configuration
bibliography_path = os.getenv("BIBLIOGRAPHY_ODS_PATH")
authors_csv_path = os.getenv("AUTHORS_CSV_PATH")

if not bibliography_path:
    raise ValueError("BIBLIOGRAPHY_ODS_PATH environment variable not set")

# Use as Path object
bib_path = Path(bibliography_path)
```

### 5.3 CSV Processing Pattern

Standard pattern for processing CSV files:

```python
import polars as pl
from pathlib import Path

def process_csv(input_path: Path, output_path: Path):
    # Read input
    if input_path.suffix.lower() == '.ods':
        df = pl.read_ods(str(input_path), has_header=True)
    elif input_path.suffix.lower() == '.csv':
        df = pl.read_csv(str(input_path))
    else:
        raise ValueError(f"Unsupported file format: {input_path.suffix}")

    # Process each row
    results = []
    for row in df.iter_rows(named=True):
        # Process row
        result = process_row(row)
        results.append(result)

    # Write output
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['column1', 'column2'])
        for result in results:
            writer.writerow([result['column1'], result['column2']])
```

### 5.4 Error Handling Pattern

Consistent error handling with status and message:

```python
try:
    metadata = process_entry(entry)
    results.append({
        'id': entry_id,
        'data': metadata,
        'status': 'success',
        'message': ''
    })
except Exception as e:
    results.append({
        'id': entry_id,
        'data': None,
        'status': 'error',
        'message': str(e)
    })
```

---

## Summary

This briefing covers:

1. ✅ **Parsing unstructured bibliographic data** from CSV, ODS, and HTML sources
2. ✅ **Crossref API integration** for fetching DOI metadata
3. ✅ **Practical examples** with real code snippets
4. ✅ **Key libraries** and their usage patterns
5. ✅ **Common patterns** used throughout the project

**Key Takeaways:**

- The project uses **philch-bib-sdk** for semantic parsing of bibliography fields
- **Habanero** library wraps the Crossref API for easy DOI metadata retrieval
- **Polars** provides fast CSV/ODS processing
- **BeautifulSoup** handles HTML parsing
- Multiple converters exist for different data sources (articles, journal issues, bibliography)
- All parsing operations have fallback mechanisms for robustness
- Environment variables configure paths to data sources

**Getting Started:**

1. Install required dependencies: `philoch-bib-sdk`, `habanero`, `polars`, `beautifulsoup4`
2. Set up `.env` file with `BIBLIOGRAPHY_ODS_PATH`
3. Review the example scripts in `src/utils/` and `src/crossref_doi_api/`
4. Run test conversions with sample data
5. Integrate with existing workflows

---

**Document Version:** 1.0
**Date:** 2025-10-23
**Project:** philosophie-ch/bibliography/biblioUtils
