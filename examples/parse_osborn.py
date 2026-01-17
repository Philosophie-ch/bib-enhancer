#!/usr/bin/env python3
"""
Parse osborn.pdf bibliography with unquoted titles.

Citation format:
- Article: Author (year). Title. Journal, volume (issue), pages.
- Book chapter: Author (year). Title. In Editor (ed.), Book Title. Publisher.
- Book: Author (year). Title. Publisher.
"""

import re
from pathlib import Path
from philoch_bib_enhancer.adapters.raw_text.raw_text_models import RawTextAuthor, RawTextBibitem


def clean_ocr_text(text: str) -> str:
    """Fix common OCR artifacts in text."""
    # Fix line-break hyphens
    text = re.sub(r'([a-z])-\s+([a-z])', r'\1\2', text)

    # Fix OCR accented characters
    text = text.replace('´ o', 'ó')
    text = text.replace('¨ a', 'ä')
    text = text.replace('¨ o', 'ö')
    text = text.replace('¨ u', 'ü')
    text = text.replace('´ a', 'á')
    text = text.replace('´ e', 'é')
    text = text.replace('´ i', 'í')
    text = text.replace('´ u', 'ú')
    text = text.replace('` a', 'à')
    text = text.replace('` e', 'è')
    text = text.replace('` o', 'ò')
    text = text.replace('ˆ o', 'ô')

    return text


def parse_authors(author_text: str) -> list[RawTextAuthor]:
    """Parse author names from text before year."""
    authors: list[RawTextAuthor] = []
    author_text = author_text.strip().rstrip('.')

    if not author_text or author_text == "—":
        return authors

    # Split by " and " or " & "
    author_parts = re.split(r'\s+(?:and|&)\s+', author_text)

    for part in author_parts:
        part = part.strip().rstrip(',')
        if not part:
            continue

        # Check if it's "Last, First" format
        if ',' in part:
            name_parts = part.split(',', 1)
            family = name_parts[0].strip()
            given = name_parts[1].strip() if len(name_parts) > 1 else ""
        else:
            # "First Last" or just "Last" format
            name_parts = part.rsplit(None, 1)
            if len(name_parts) == 2:
                given = name_parts[0].strip()
                family = name_parts[1].strip()
            else:
                family = part
                given = ""

        authors.append(RawTextAuthor(family=family, given=given))

    return authors


def parse_bibliography_entry(entry_text: str, prev_authors: list[RawTextAuthor]) -> RawTextBibitem | None:
    """
    Parse a single bibliography entry with unquoted titles.

    Format: Author (year). Title. [Journal/Publisher info].
    """
    entry_text = entry_text.strip()
    if not entry_text or entry_text == "—":
        return None

    # Clean OCR artifacts
    entry_text = clean_ocr_text(entry_text)
    raw_text = entry_text

    # Extract year - must be in parentheses
    # Handle nested parentheses like "(1854 (2016))" - take the last/most recent year
    # Handle year suffixes like "2009a" or "2009a." (with or without trailing period)
    year_match = re.search(r'\((?:\d{4}[a-z]?\.?\s+)?\((\d{4}[a-z]?)\)\)|\((\d{4}[a-z]?)\.?\)', entry_text)
    if not year_match:
        print(f"Warning: No year found in: {entry_text[:80]}")
        return None

    # Get either group 1 (nested) or group 2 (normal)
    year_str = year_match.group(1) if year_match.group(1) else year_match.group(2)
    year_num = re.match(r'(\d{4})', year_str)
    year = int(year_num.group(1)) if year_num else None

    # Extract authors (before the year)
    author_text = entry_text[: year_match.start()].strip()
    if author_text == "—":
        authors = prev_authors
    else:
        authors = parse_authors(author_text)

    # Extract everything after year
    after_year = entry_text[year_match.end() :].strip()
    if after_year.startswith('.'):
        after_year = after_year[1:].strip()

    # Now parse title and publication info
    # Strategy: Look for strong markers that indicate where title ends

    # Check for "In " pattern (book chapter) - very distinctive
    # Pattern: period (optional space) + "In "
    in_match = re.search(r'\.\s*In\s+', after_year, re.IGNORECASE)
    if in_match:
        title = after_year[: in_match.start()].strip()
        rest = after_year[in_match.end() - 3 :].strip()  # Include "In " in rest
    else:
        # Look for journal article pattern: period + Journal Name + comma + Volume
        # Key insight: journal name is followed by comma and volume number
        # Work backwards from ", Volume" to find the period that ends the title
        vol_match = re.search(r',\s*(\d+)\s*(?:\((\d+)\))?,\s*(\d+)', after_year)
        if vol_match:
            # Found volume pattern, now find the last period before it
            before_vol = after_year[: vol_match.start()]
            # Find last period in the before_vol section
            last_period = before_vol.rfind('. ')
            if last_period != -1:
                title = before_vol[:last_period].strip()
                rest = after_year[last_period + 1 :].strip()
            else:
                # No period found, unusual
                title = before_vol.strip()
                rest = after_year[len(title) :].strip()
        else:
            # Book: title ends at period followed by capital letter (publisher)
            # Look for pattern: period + space + capital letter starting a word (not initial)
            period_match = re.search(r'\.\s+(?=[A-Z][a-z]+)', after_year)
            if period_match:
                title = after_year[: period_match.start()].strip()
                rest = after_year[period_match.end() :].strip()
            else:
                # No clear break, take everything
                title = after_year.strip()
                rest = ""

    # Remove any trailing punctuation or quotes from title
    # Handle both straight and curly quotes
    title = title.rstrip('.,;:"\'\u201d')  # Add curly right quote
    title = title.lstrip('"\'\u201c')  # Add curly left quote

    if not title:
        print(f"Warning: No title found in: {entry_text[:80]}")
        return None

    # Determine entry type and extract metadata
    entry_type = "book"
    journal = None
    volume = None
    issue_number = None
    start_page = None
    end_page = None
    publisher = None
    doi = None

    # Check if it's a book chapter (has "In " after title)
    if re.search(r'\bIn\s+', rest, re.IGNORECASE):
        entry_type = "incollection"
        # Extract publisher if present - typically at the end after a period
        # Look for publisher keywords
        pub_match = re.search(
            r'\.?\s*([A-Z][^.]*?(?:Press|Publisher|University|Publishing|House|Books|Springer|Routledge|MIT|Cambridge|Oxford)[^.]*)',
            rest,
        )
        if pub_match:
            publisher = pub_match.group(1).strip().rstrip('.')

    # Check if it's a journal article (has journal, volume, pages pattern)
    # Pattern: Journal, volume (issue), pages
    # or: Journal, volume, pages
    journal_match = re.search(r'^([^,]+),\s*(\d+)(?:\s*\((\d+)\))?,?\s*(\d+)(?:[-–—](\d+))?', rest)
    if journal_match:
        entry_type = "article"
        journal = journal_match.group(1).strip()
        volume = journal_match.group(2)
        issue_number = journal_match.group(3) if journal_match.group(3) else None
        start_page = journal_match.group(4)
        end_page = journal_match.group(5) if journal_match.group(5) else None

    # If not article and not incollection, it's a book - extract publisher
    if entry_type == "book" and rest:
        # Publisher is typically at the end or after location
        pub_match = re.search(
            r'(?::\s*)?([A-Z][^.]+?(?:Press|Publisher|University|House|Books|Springer|Routledge|MIT|Cambridge|Oxford)[^.]*)',
            rest,
        )
        if pub_match:
            publisher = pub_match.group(1).strip().rstrip('.')
        elif rest:
            # If no specific publisher keyword, take the first part before period
            publisher = rest.split('.')[0].strip()

    # Extract DOI if present
    doi_match = re.search(r'doi:\s*(https?://[^\s.]+|10\.[^\s.]+)', entry_text, re.IGNORECASE)
    if doi_match:
        doi = doi_match.group(1)
        if doi.startswith('https://doi.org/'):
            doi = doi.replace('https://doi.org/', '')
        doi = doi.rstrip('.,')

    # Extract pages if not already extracted (for incollection)
    if not start_page and entry_type == "incollection":
        pages_match = re.search(r'pp?\.\s*(\d+)(?:[-–—](\d+))?', rest)
        if pages_match:
            start_page = pages_match.group(1)
            end_page = pages_match.group(2) if pages_match.group(2) else None

    return RawTextBibitem(
        raw_text=raw_text,
        type=entry_type,
        title=title,
        year=year,
        authors=authors if authors else None,
        journal=journal,
        volume=volume,
        issue_number=issue_number,
        start_page=start_page,
        end_page=end_page,
        publisher=publisher,
        doi=doi,
    )


def parse_bibliography_file(file_path: str) -> list[RawTextBibitem]:
    """Parse bibliography file into RawTextBibitem objects."""
    text = Path(file_path).read_text(encoding='utf-8')

    # Remove "References" header if present
    text = text.replace('References\n', '').replace('REFERENCES\n', '')

    # Split into entries
    # Entries start with uppercase letter followed by author pattern
    entries = []
    current_entry = ""
    prev_authors: list[RawTextAuthor] = []

    for line in text.split('\n'):
        line = line.strip()

        # Skip page numbers and empty lines
        if re.match(r'^\d+\s*$', line) or not line:
            continue

        # Check if this is the start of a new entry
        # Pattern: Starts with capital letter and has (year) pattern
        # Include optional period after year suffix (e.g., "2009a.")
        if re.match(r'^[A-Z]', line) and re.search(r'\(\d{4}[a-z]?\.?\)', line):
            # Save previous entry
            if current_entry:
                bibitem = parse_bibliography_entry(current_entry, prev_authors)
                if bibitem:
                    if bibitem.authors:
                        prev_authors = bibitem.authors
                    entries.append(bibitem)
            current_entry = line
        else:
            # Continue current entry
            if current_entry:
                current_entry += " " + line

    # Don't forget the last entry
    if current_entry:
        bibitem = parse_bibliography_entry(current_entry, prev_authors)
        if bibitem:
            entries.append(bibitem)

    return entries


def append_to_csv(bibitems: list[RawTextBibitem], csv_path: str) -> None:
    """Append RawTextBibitem entries to existing CSV using the SDK's proper method."""
    import tempfile
    from philoch_bib_enhancer.cli.manual_raw_text_to_csv import process_raw_bibitems

    # Create a temporary output file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as tmp_file:
        tmp_path = tmp_file.name

    try:
        # Use the SDK's proper method to write to temp file
        process_raw_bibitems(bibitems, tmp_path)

        # Read the new entries (skip header)
        with open(tmp_path, 'r', encoding='utf-8') as tmp_f:
            lines = tmp_f.readlines()[1:]  # Skip header

        # Append to existing CSV
        with open(csv_path, 'a', encoding='utf-8') as out_f:
            out_f.writelines(lines)

    finally:
        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)


def main() -> None:
    bib_file = "/home/alebg/philosophie-ch/bibliography/bib-enhancer/osborn_refs_bib_only.txt"
    output_csv = "/home/alebg/philosophie-ch/Dropbox/philosophie-ch/biblio/biblio-training/out.csv"

    print(f"Parsing osborn bibliography from: {bib_file}")
    bibitems = parse_bibliography_file(bib_file)

    print(f"Parsed {len(bibitems)} entries\n")

    # Show first few entries for verification
    for i, item in enumerate(bibitems[:5]):
        print(f"Entry {i+1}:")
        print(f"  Type: {item.type}")
        print(f"  Title: {item.title}")
        print(f"  Year: {item.year}")
        if item.authors:
            print(f"  Authors: {', '.join([f'{a.family}, {a.given}' for a in item.authors])}")
        if item.journal:
            print(f"  Journal: {item.journal}")
            print(f"  Volume: {item.volume}, Issue: {item.issue_number}, Pages: {item.start_page}-{item.end_page}")
        if item.publisher:
            print(f"  Publisher: {item.publisher}")
        print()

    print(f"Appending to CSV: {output_csv}")
    append_to_csv(bibitems, output_csv)

    print(f"✓ Successfully appended {len(bibitems)} entries to {output_csv}")


if __name__ == "__main__":
    main()
