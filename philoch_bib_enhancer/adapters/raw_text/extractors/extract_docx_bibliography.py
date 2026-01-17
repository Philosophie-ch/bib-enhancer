#!/usr/bin/env python3
"""
Extract bibliographic references from Word (.docx) files.

This script extracts text from .docx files and parses bibliographic references
from the bibliography section, creating RawTextBibitem objects for conversion to CSV.
"""

import re
import sys
from pathlib import Path
from typing import List, Optional
from docx import Document

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from philoch_bib_enhancer.adapters.raw_text.raw_text_models import (
    RawTextBibitem,
    RawTextAuthor,
)
from philoch_bib_enhancer.cli.manual_raw_text_to_csv import process_raw_bibitems


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from a Word document."""
    doc = Document(file_path)
    return '\n'.join([para.text for para in doc.paragraphs if para.text.strip()])


def find_bibliography_section(text: str) -> Optional[str]:
    """Find and extract the bibliography section from the text."""
    # Look for common bibliography markers
    patterns = [
        r'\nReferences\s*\n',
        r'\nBibliography\s*\n',
        r'\nWorks Cited\s*\n',
        r'\nLiterature\s*\n',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Extract everything after the marker
            return text[match.end() :]

    # If no header found, look for where bibliography entries start
    # They typically follow a pattern: Author, Name (Year) 'Title'
    # Look for first occurrence of this pattern near the end of document
    # Find the last 40% of the document (where bibliography usually is)
    doc_length = len(text)
    search_start = int(doc_length * 0.6)
    search_text = text[search_start:]

    # Look for bibliography entry pattern: Name (YYYY)
    match = re.search(r'\n([A-Z][a-z]+,\s+[A-Z][a-z]+.*?\(\d{4}\))', search_text)
    if match:
        # Found a likely bibliography entry, return from here
        return text[search_start + match.start() :]

    return None


def parse_author_string(author_str: str) -> List[RawTextAuthor]:
    """Parse author string into list of RawTextAuthor objects."""
    authors = []

    # Split by 'and' or '&'
    author_parts = re.split(r'\s+and\s+|\s+&\s+', author_str)

    for part in author_parts:
        part = part.strip().rstrip('.,;')
        if not part:
            continue

        # Check for "Last, First" format
        if ',' in part:
            parts = part.split(',', 1)
            family = parts[0].strip()
            given = parts[1].strip() if len(parts) > 1 else ""
        else:
            # Assume "First Last" format - take last word as family name
            words = part.split()
            if len(words) > 1:
                given = ' '.join(words[:-1])
                family = words[-1]
            else:
                given = ""
                family = words[0]

        authors.append(RawTextAuthor(given=given, family=family))

    return authors


def extract_year(text: str) -> Optional[int]:
    """Extract year from text (YYYY) pattern."""
    # Try (YYYY) or (YYYYa), (YYYYb), etc. for multiple publications in same year
    match = re.search(r'\((\d{4})[a-z]?\)', text)
    if match:
        return int(match.group(1))

    # Try standalone year (just year followed by period or space)
    match = re.search(r'\b(19\d{2}|20\d{2})[\.\s]', text)
    if match:
        return int(match.group(1))

    return None


def extract_pages(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract page range from text."""
    # Look for pp. X--Y or pp. X-Y or p. X
    match = re.search(r'pp?\.\s*(\d+)[-–—]+(\d+)', text)
    if match:
        return match.group(1), match.group(2)

    match = re.search(r'pp?\.\s*(\d+)', text)
    if match:
        return match.group(1), None

    # Look for standalone page ranges
    match = re.search(r'\b(\d+)[-–—]+(\d+)\b', text)
    if match:
        return match.group(1), match.group(2)

    return None, None


def extract_doi(text: str) -> Optional[str]:
    """Extract DOI from text."""
    match = re.search(r'doi:\s*([^\s,]+)', text, re.IGNORECASE)
    if match:
        doi = match.group(1).rstrip('.,;')
        return doi

    # Look for DOI pattern without 'doi:' prefix
    match = re.search(r'\b10\.\d{4,}/[^\s,]+', text)
    if match:
        return match.group(0).rstrip('.,;')

    return None


def extract_title_from_entry(text: str, year: Optional[int] = None) -> Optional[str]:
    """Extract title from entry (quoted or unquoted)."""
    # First try to extract from quotes (straight, curly, single/double)
    # U+0022 = " (straight double quote)
    # U+0027 = ' (straight single quote)
    # U+2018 = ' (left single quote)
    # U+2019 = ' (right single quote)
    # U+201C = " (left double quote)
    # U+201D = " (right double quote)
    # Pattern: opening quote, content (excluding ALL quote types), closing quote
    match = re.search(r'["\u201C\'\u2018]([^"\u201D\'\u2019\']+)["\u201D\'\u2019]', text)
    if match:
        title = match.group(1).strip()
        # Clean up any trailing punctuation or commas inside the quotes
        title = title.rstrip('.,;:')
        return title

    # If no quotes, try to extract text after (YYYY) or (YYYYa) up to period or colon
    if year:
        # Try with period after year: (YYYY). Title.
        pattern = rf'\({year}[a-z]?\)\.\s+([^.]+?)\.'
        match = re.search(pattern, text)
        if match:
            title_candidate = match.group(1).strip()
            # Remove any remaining trailing punctuation and quotes
            title_candidate = title_candidate.strip('.,;:"\'\u201c\u201d\u2018\u2019 ')
            if len(title_candidate) > 10:  # Reasonable minimum length
                return title_candidate

        # Try without period after year: (YYYY) Title: or (YYYY) Title.
        pattern = rf'\({year}[a-z]?\)\s+([^:.]+)'
        match = re.search(pattern, text)
        if match:
            title_candidate = match.group(1).strip()
            title_candidate = title_candidate.strip('.,;:"\'\u201c\u201d\u2018\u2019 ')
            if len(title_candidate) > 10:
                return title_candidate

        # Try with standalone year format "Author YYYY. Title."
        pattern = rf'\s{year}\.\s+([^.]+?)\.'
        match = re.search(pattern, text)
        if match:
            title_candidate = match.group(1).strip()
            title_candidate = title_candidate.strip('.,;:"\'\u201c\u201d\u2018\u2019 ')
            if len(title_candidate) > 10:
                return title_candidate

    return None


def parse_bibliography_entries(bib_text: str) -> List[RawTextBibitem]:
    """Parse bibliography text into RawTextBibitem objects."""
    items = []

    # Split into individual entries
    # Entries typically start with author name (capital letter) after a newline
    # Or with em-dash for same author
    lines = bib_text.split('\n')

    current_entry = ""
    entries = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if this is a new entry
        # New entries start with: Author, Initial (YYYY) or Author, Initial & Author2, Initial (YYYY)
        # This pattern is more robust than just checking for capital letters
        is_new_entry = False

        # Pattern 1: Starts with "LastName, Initial(s)" (author name format)
        if re.match(r'^[A-Z][a-z]+,\s+[A-Z]\.', line):
            is_new_entry = True
        # Pattern 2: Starts with em-dash (same author as previous)
        elif re.match(r'^[—–]', line):
            is_new_entry = True
        # Pattern 3: Starts with capital letter and contains (YYYY) in first 80 chars
        elif re.match(r'^[A-Z][a-z]+', line) and re.search(r'\(\d{4}[a-z]?\)', line[:80]):
            is_new_entry = True

        if is_new_entry:
            if current_entry:
                entries.append(current_entry)
            current_entry = line
        else:
            # Continuation of previous entry
            if current_entry:
                current_entry += " " + line

    # Add last entry
    if current_entry:
        entries.append(current_entry)

    # Parse each entry
    for entry in entries:
        if not entry.strip():
            continue

        # Extract components
        year = extract_year(entry)
        title = extract_title_from_entry(entry, year)
        start_page, end_page = extract_pages(entry)
        doi = extract_doi(entry)

        # Try to extract authors (before year)
        authors = []
        if year:
            # Find text before (year) or (yeara), (yearb), etc.
            match = re.search(r'^(.+?)\s*\(' + str(year) + r'[a-z]?\)', entry)
            if match:
                author_str = match.group(1).strip()
                # Remove em-dash if present (means same author)
                author_str = re.sub(r'^[—–]\s*', '', author_str)
                authors = parse_author_string(author_str)
            else:
                # Try standalone year format "Author YYYY."
                match = re.search(r'^(.+?)\s+' + str(year) + r'\.', entry)
                if match:
                    author_str = match.group(1).strip()
                    author_str = re.sub(r'^[—–]\s*', '', author_str)
                    authors = parse_author_string(author_str)

        # Determine entry type
        entry_type = "article"  # default
        if "In:" in entry or "In " in entry:
            entry_type = "incollection"
        elif re.search(r'\bvol\.\s*\d+', entry, re.IGNORECASE):
            entry_type = "book"

        # Extract journal name (for articles)
        journal = None
        if entry_type == "article":
            # Look for italicized text or text after title
            if title and title in entry:
                after_title = entry.split(title, 1)[1]
                # Look for text before volume/page numbers
                match = re.search(r'^[^.\d]+', after_title)
                if match:
                    journal_candidate = match.group(0).strip()
                    journal_candidate = re.sub(r'^\s*[,.]?\s*', '', journal_candidate)
                    journal_candidate = re.sub(r'\s*\d+.*$', '', journal_candidate)
                    if journal_candidate and len(journal_candidate) > 2:
                        journal = journal_candidate.strip('.,;: ')

        # Extract volume and issue
        volume = None
        issue_number = None
        match = re.search(r'\b(\d+)\s*\((\d+)\)', entry)
        if match:
            volume = match.group(1)
            issue_number = match.group(2)
        else:
            match = re.search(r'\bvol\.\s*(\d+)', entry, re.IGNORECASE)
            if match:
                volume = match.group(1)

        # Quality checks - only add if we have minimum required data
        if not title or not year or not authors:
            # Skip entries without essential information
            continue

        # Additional validation: check title isn't just junk
        if len(title) < 5 or title.startswith("In:"):
            continue

        # Create RawTextBibitem
        bibitem = RawTextBibitem(
            raw_text=entry,
            type=entry_type,
            title=title,
            year=year,
            authors=authors,
            journal=journal,
            volume=volume,
            issue_number=issue_number,
            start_page=start_page,
            end_page=end_page,
            doi=doi,
        )
        items.append(bibitem)

    return items


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python extract_docx_bibliography.py <input.docx> <output.csv>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    # Check if we should append
    append = len(sys.argv) > 3 and sys.argv[3] == "--append"

    print(f"Extracting text from {input_file}...")
    text = extract_text_from_docx(input_file)

    print("Finding bibliography section...")
    bib_text = find_bibliography_section(text)

    if not bib_text:
        print("ERROR: Could not find bibliography section in the document.")
        print("Looking for markers: References, Bibliography, Works Cited, Literature")
        sys.exit(1)

    print("Parsing bibliography entries...")
    bibitems = parse_bibliography_entries(bib_text)

    print(f"Found {len(bibitems)} bibliographic entries")

    if append and Path(output_file).exists():
        print(f"Appending to existing file: {output_file}")
        # Process to temporary file
        temp_file = output_file + ".tmp"
        process_raw_bibitems(bibitems, temp_file)

        # Read the new entries (skip header)
        with open(temp_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            new_entries = lines[1:]  # Skip header

        # Append to existing file
        with open(output_file, 'a', encoding='utf-8') as f:
            f.writelines(new_entries)

        # Remove temp file
        Path(temp_file).unlink()
        print(f"Successfully appended {len(bibitems)} entries to {output_file}")
    else:
        print(f"Writing to {output_file}...")
        process_raw_bibitems(bibitems, output_file)
        print(f"Successfully wrote {len(bibitems)} entries to {output_file}")


if __name__ == "__main__":
    main()
