#!/usr/bin/env python3
"""Extract bibliography from osborn.pdf and append to out.csv."""

from pathlib import Path
from pypdf import PdfReader
from philoch_bib_enhancer.adapters.raw_text.extractors.parse_pdf_bibliography import (
    parse_bibliography_file,
    append_to_csv,
)


def extract_pdf_text(pdf_path: str, output_txt: str) -> None:
    """Extract text from PDF and save to file."""
    reader = PdfReader(pdf_path)

    text_lines = []
    for page in reader.pages:
        text = page.extract_text()
        text_lines.append(text)

    full_text = '\n'.join(text_lines)

    # Find the bibliography section
    # Look for common markers
    bib_markers = ['References', 'REFERENCES', 'Bibliography', 'BIBLIOGRAPHY', 'Works Cited', 'Literature']

    bib_start = -1
    for marker in bib_markers:
        idx = full_text.find(marker)
        if idx != -1:
            bib_start = idx
            print(f"Found bibliography section starting at position {idx} with marker: {marker}")
            break

    if bib_start == -1:
        print("Warning: Could not find bibliography section, using full text")
        bib_text = full_text
    else:
        bib_text = full_text[bib_start:]

    # Write to file
    Path(output_txt).write_text(bib_text, encoding='utf-8')
    print(f"Extracted text saved to: {output_txt}")
    print(f"Text length: {len(bib_text)} characters")


def main() -> None:
    pdf_path = "/home/alebg/philosophie-ch/Dropbox/philosophie-ch/biblio/biblio-training/new-ones-for-Claude/osborn.pdf"
    txt_path = "/home/alebg/philosophie-ch/bibliography/bib-enhancer/osborn_refs.txt"
    output_csv = "/home/alebg/philosophie-ch/Dropbox/philosophie-ch/biblio/biblio-training/out.csv"

    # Step 1: Extract text from PDF
    print(f"Extracting text from: {pdf_path}")
    extract_pdf_text(pdf_path, txt_path)

    # Step 2: Parse bibliography
    print(f"\nParsing bibliography from: {txt_path}")
    bibitems = parse_bibliography_file(txt_path)
    print(f"Parsed {len(bibitems)} entries")

    # Show first few entries
    for i, item in enumerate(bibitems[:3]):
        print(f"\nEntry {i+1}:")
        print(f"  Type: {item.type}")
        print(f"  Title: {repr(item.title)}")
        print(f"  Year: {item.year}")
        print(f"  Authors: {[f'{a.family}, {a.given}' for a in item.authors] if item.authors else 'None'}")

    # Step 3: Append to CSV
    print(f"\nAppending to CSV: {output_csv}")
    append_to_csv(bibitems, output_csv)

    print(f"✓ Successfully appended {len(bibitems)} entries to {output_csv}")


if __name__ == "__main__":
    main()
