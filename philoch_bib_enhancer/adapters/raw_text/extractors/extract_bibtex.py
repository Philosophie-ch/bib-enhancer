#!/usr/bin/env python3
"""Extract bibliographic references from a .bib file and convert to CSV using RawText workflow."""

import re
from typing import List

from philoch_bib_enhancer.cli.manual_raw_text_to_csv import process_raw_bibitems
from philoch_bib_enhancer.adapters.raw_text.raw_text_models import RawTextAuthor, RawTextBibitem


def parse_bib_file(file_path: str) -> List[RawTextBibitem]:
    """Parse a BibTeX file and extract all entries as RawTextBibitem objects."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into individual entries
    entries = re.split(r'\n@', content)

    bibitems = []

    for entry in entries:
        if not entry.strip():
            continue

        # Add back the @ if it was removed by split
        if not entry.startswith('@'):
            entry = '@' + entry

        bibitem = parse_entry(entry)
        if bibitem:
            bibitems.append(bibitem)

    return bibitems


def parse_entry(entry: str) -> RawTextBibitem | None:
    """Parse a single BibTeX entry into a RawTextBibitem object."""
    # Extract entry type (without the @ prefix)
    type_match = re.match(r'@(\w+)\{', entry)
    if not type_match:
        return None

    entry_type = type_match.group(1).lower()  # Gets just "article", not "@article"

    # Map BibTeX types to standard types
    type_mapping = {
        'article': 'article',
        'book': 'book',
        'incollection': 'incollection',
        'inbook': 'incollection',
        'mastersthesis': 'mastersthesis',
        'phdthesis': 'phdthesis',
        'thesis': 'thesis',
        'inproceedings': 'inproceedings',
        'conference': 'inproceedings',
    }

    normalized_type = type_mapping.get(entry_type, entry_type)

    # Extract fields
    title = extract_field(entry, 'title')
    if not title:
        return None

    year_str = extract_field(entry, 'year')
    # Handle year and pubstate
    year = None
    pubstate = None
    if year_str:
        year_str = year_str.strip()
        year_lower = year_str.lower()

        # Check if it's a publication state
        if year_lower in ['forthcoming', 'in press', 'inpress']:
            pubstate = 'forthcoming'
        elif year_lower in ['no date', 'n.d.']:
            # "no date" is not a pubstate, just leave year as None
            pass
        elif year_str.isdigit():
            year = int(year_str)
        else:
            # Try to extract a year from the string (e.g., "2024a" -> 2024)
            year_match = re.search(r'\b(\d{4})\b', year_str)
            if year_match:
                year = int(year_match.group(1))

    # Parse authors
    authors_str = extract_field(entry, 'author')
    authors = parse_authors(authors_str) if authors_str else []

    # Parse editors
    editors_str = extract_field(entry, 'editor')
    editors = parse_authors(editors_str) if editors_str else []

    # Extract other fields
    journal = extract_field(entry, 'journal')
    volume = extract_field(entry, 'volume')
    issue_number = extract_field(entry, 'number')
    publisher = extract_field(entry, 'publisher')
    doi = extract_field(entry, 'doi')
    url = extract_field(entry, 'url')

    # Extract pages
    pages_str = extract_field(entry, 'pages')
    start_page = None
    end_page = None
    if pages_str:
        # Handle various page formats: 123-456, 123--456, 123
        pages_match = re.match(r'(\d+)\s*[-–—]+\s*(\d+)', pages_str)
        if pages_match:
            start_page = pages_match.group(1)
            end_page = pages_match.group(2)
        elif pages_str.isdigit():
            start_page = pages_str

    # Create RawTextBibitem
    return RawTextBibitem(
        raw_text=entry.strip(),
        type=normalized_type,
        title=clean_tex_string(title),
        year=year,
        pubstate=pubstate,
        authors=authors if authors else None,
        editors=editors if editors else None,
        journal=clean_tex_string(journal) if journal else None,
        volume=volume,
        issue_number=issue_number,
        start_page=start_page,
        end_page=end_page,
        publisher=clean_tex_string(publisher) if publisher else None,
        doi=doi,
        url=url,
    )


def extract_field(entry: str, field_name: str) -> str | None:
    """Extract a field value from a BibTeX entry."""
    # Match field = {value} or field = "value"
    pattern = rf'{field_name}\s*=\s*[{{"]([^}}"]*)[\}}""]'
    match = re.search(pattern, entry, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def parse_authors(authors_str: str) -> List[RawTextAuthor]:
    """Parse author string into list of RawTextAuthor objects."""
    # Split by 'and'
    author_parts = re.split(r'\s+and\s+', authors_str, flags=re.IGNORECASE)

    authors = []
    for part in author_parts:
        part = part.strip()
        if not part:
            continue

        # Handle "Last, First" format
        if ',' in part:
            parts = part.split(',', 1)
            family = parts[0].strip()
            given = parts[1].strip() if len(parts) > 1 else ''
        else:
            # Handle "First Last" format
            parts = part.rsplit(None, 1)
            if len(parts) == 2:
                given = parts[0].strip()
                family = parts[1].strip()
            else:
                family = part
                given = ''

        # Clean up curly braces
        family = clean_tex_string(family)
        given = clean_tex_string(given)

        authors.append(RawTextAuthor(family=family, given=given))

    return authors


def clean_tex_string(s: str) -> str:
    """Clean up LaTeX formatting from strings."""
    if not s:
        return s

    # Remove all curly braces (both single and double)
    # In BibTeX, {{ }} is used to protect capitalization, but we don't need it in plain text
    s = s.replace('{{', '').replace('}}', '').replace('{', '').replace('}', '')

    # Clean up whitespace
    s = re.sub(r'\s+', ' ', s).strip()

    return s


def main() -> None:
    """Main function to extract bibliographic references from .bib file."""
    input_file = "data/biblio/biblio-training/new-ones-for-Claude/blumson-joaquin.bib"
    output_file = "data/biblio/biblio-training/out.csv"

    print(f"Reading .bib file: {input_file}")
    bibitems = parse_bib_file(input_file)

    print(f"Found {len(bibitems)} bibliographic entries")

    print(f"Converting to CSV format...")
    process_raw_bibitems(bibitems, output_file)

    print(f"✓ Output saved to: {output_file}")


if __name__ == "__main__":
    main()
