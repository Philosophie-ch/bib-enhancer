#!/usr/bin/env python3
"""Parse bibliography from Freivogel PDF and append to CSV."""

import re
from pathlib import Path
from philoch_bib_enhancer.adapters.raw_text.raw_text_models import RawTextAuthor, RawTextBibitem


def clean_ocr_text(text: str) -> str:
    """Fix common OCR artifacts in text."""
    # Fix line-break hyphens, but preserve real compound words
    # Line-break pattern: lowercase + hyphen + space + lowercase
    # Real compound: lowercase + hyphen + lowercase (no space)
    # We look for the pattern where there's a space after the hyphen
    # This indicates it was a line break that got joined with a space
    text = re.sub(r'([a-z])-\s+([a-z])', r'\1\2', text)

    # Fix common OCR issues with accented characters
    text = text.replace('´ o', 'ó')  # Alchourr´ on -> Alchourró́n
    text = text.replace('¨ a', 'ä')  # G¨ ardenfors -> Gärdenfors
    text = text.replace('¨ o', 'ö')
    text = text.replace('¨ u', 'ü')
    text = text.replace('´ a', 'á')
    text = text.replace('´ e', 'é')
    text = text.replace('´ i', 'í')
    text = text.replace('´ u', 'ú')
    text = text.replace('` a', 'à')
    text = text.replace('` e', 'è')
    text = text.replace('` o', 'ò')
    text = text.replace('ˆ o', 'ô')  # Noˆ us -> Noûs

    return text


def parse_bibliography_entry(entry_text: str) -> RawTextBibitem | None:
    """
    Parse a single bibliography entry.

    Example formats:
    - Journal article: Author (year). "Title". In: Journal vol.issue, pp. pages. doi: xxx.
    - Book chapter: Author (year). "Title". In: Book Title. Ed. by Editor. Publisher, pp. pages.
    - Book: Author (year). Title. Publisher.
    """
    entry_text = entry_text.strip()
    if not entry_text or entry_text == "—":
        return None

    # Clean OCR artifacts
    entry_text = clean_ocr_text(entry_text)

    raw_text = entry_text

    # Extract year
    year_match = re.search(r'\((\d{4}[a-z]?)\)', entry_text)
    year = None
    if year_match:
        year_str = year_match.group(1)
        # Extract just the numeric year
        year_num = re.match(r'(\d{4})', year_str)
        if year_num:
            year = int(year_num.group(1))

    # Extract title (usually in quotes, but we'll strip the quotes)
    # Handle both straight quotes ("") and curly/typographic quotes ("")
    # Use Unicode escapes to be explicit: \u201C (") and \u201D (")
    title_match = re.search(r'["\u201C]([^"\u201D]+)["\u201D]', entry_text)
    if title_match:
        title = title_match.group(1)  # Get text inside quotes, without the quotes
    else:
        # If no quoted title, might be a book (title after year, before period or "In:")
        title = None
        if year_match:
            after_year = entry_text[year_match.end() :].strip()
            # Remove leading dot if present
            if after_year.startswith('.'):
                after_year = after_year[1:].strip()
            # Extract until first period or "In:"
            title_match = re.match(r'([^.]+?)(?:\.|In:)', after_year)
            if title_match:
                title = title_match.group(1).strip()

    if not title:
        print(f"Warning: Could not extract title from: {entry_text[:100]}")
        return None

    # Extract authors (before the year)
    authors = []
    if year_match:
        author_text = entry_text[: year_match.start()].strip()

        # Handle em-dash for "same author as previous"
        if author_text == "—" or not author_text:
            # We'll leave authors empty - calling code should fill in from previous entry
            pass
        else:
            # Parse authors: "Last, First and Last, First"
            # Or: "Last, First, Last2, First2, and Last3, First3"
            author_text = author_text.rstrip('.')

            # Split by " and "
            author_parts = re.split(r'\s+and\s+', author_text)

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
                    # "First Last" format
                    name_parts = part.rsplit(None, 1)
                    if len(name_parts) == 2:
                        given = name_parts[0].strip()
                        family = name_parts[1].strip()
                    else:
                        family = part
                        given = ""

                authors.append(RawTextAuthor(family=family, given=given))

    # Extract journal
    journal_match = re.search(r'In:\s*([^.]+?)\s+\d+\.', entry_text)
    journal = journal_match.group(1).strip() if journal_match else None

    # Extract volume and issue
    vol_issue_match = re.search(r'(\d+)\.(\d+)', entry_text)
    volume = vol_issue_match.group(1) if vol_issue_match else None
    issue_number = vol_issue_match.group(2) if vol_issue_match else None

    # Extract pages
    pages_match = re.search(r'pp\.\s*(\d+)(?:[-–—](\d+))?', entry_text)
    start_page = None
    end_page = None
    if pages_match:
        start_page = pages_match.group(1)
        end_page = pages_match.group(2) if pages_match.group(2) else None

    # Extract DOI
    doi_match = re.search(r'doi:\s*(https?://[^\s.]+|10\.[^\s.]+)', entry_text)
    doi = None
    if doi_match:
        doi = doi_match.group(1)
        if doi.startswith('https://doi.org/'):
            doi = doi.replace('https://doi.org/', '')
        # Remove trailing dots and other punctuation
        doi = doi.rstrip('.,')

    # Extract publisher (for books)
    publisher = None
    if not journal:
        # Look for publisher after location or directly
        pub_match = re.search(
            r'(?::\s*)?([A-Z][^.]+?(?:Press|Publisher|University|House|Books|Springer|Routledge|MIT|Cambridge|Oxford))',
            entry_text,
        )
        if pub_match:
            publisher = pub_match.group(1).strip().rstrip('.')

    # Determine entry type
    entry_type = "article" if journal else "book"
    if "In:" in entry_text and not journal:
        entry_type = "incollection"

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

    # Remove "References" header
    text = text.replace('References\n', '').replace('REFERENCES\n', '')

    # Split into entries
    # Entries start with uppercase letter or em-dash at beginning of line
    entries: list[RawTextBibitem] = []
    current_entry = ""
    prev_authors: list[RawTextAuthor] = []

    for line in text.split('\n'):
        line = line.strip()

        # Check if this is the start of a new entry
        # (Uppercase letter or em-dash followed by year pattern)
        if re.match(r'^[A-Z—]', line) and (re.search(r'\(\d{4}[a-z]?\)', line) or line.startswith('—')):
            # Save previous entry
            if current_entry:
                bibitem = parse_bibliography_entry(current_entry)
                if bibitem:
                    # If authors are empty and we have previous authors, use them (em-dash case)
                    if not bibitem.authors and prev_authors:
                        bibitem.authors = prev_authors
                    else:
                        prev_authors = bibitem.authors or []
                    entries.append(bibitem)
            current_entry = line
        else:
            # Continue current entry
            if current_entry:
                current_entry += " " + line

    # Don't forget the last entry
    if current_entry:
        bibitem = parse_bibliography_entry(current_entry)
        if bibitem:
            if not bibitem.authors and prev_authors:
                bibitem.authors = prev_authors
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
    """Main function."""
    bib_file = "data/biblio/biblio-training/freivogel_extracted_refs.txt"
    output_csv = "data/biblio/biblio-training/out.csv"

    print(f"Parsing bibliography from: {bib_file}")
    bibitems = parse_bibliography_file(bib_file)

    print(f"Parsed {len(bibitems)} entries")

    # Show first few entries
    for i, item in enumerate(bibitems[:3]):
        print(f"\nEntry {i+1}:")
        print(f"  Type: {item.type}")
        print(f"  Title: {repr(item.title)}")  # Use repr to see actual content
        print(f"  Year: {item.year}")
        print(f"  Authors: {[f'{a.family}, {a.given}' for a in item.authors] if item.authors else 'None'}")

    print(f"\nAppending to CSV: {output_csv}")
    append_to_csv(bibitems, output_csv)

    print(f"✓ Successfully appended {len(bibitems)} entries to {output_csv}")


if __name__ == "__main__":
    main()
