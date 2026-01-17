#!/usr/bin/env python3
"""Extract bibliographic references from a PDF file and append to CSV."""

import sys
from pathlib import Path

# Try different PDF libraries
try:
    import pymupdf as fitz  # PyMuPDF

    PDF_LIBRARY = "pymupdf"
except ImportError:
    try:
        from pypdf import PdfReader

        PDF_LIBRARY = "pypdf"
    except ImportError:
        try:
            import PyPDF2

            PDF_LIBRARY = "pypdf2"
        except ImportError:
            print("Error: No PDF library found. Install pymupdf, pypdf, or PyPDF2")
            sys.exit(1)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF using available library."""
    if PDF_LIBRARY == "pymupdf":
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    elif PDF_LIBRARY == "pypdf":
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
        return text
    elif PDF_LIBRARY == "pypdf2":
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)  # type: ignore
            text = ""
            for page in reader.pages:
                text += page.extract_text()
        return text
    else:
        raise RuntimeError("No PDF library available")


def identify_bibliography_section(text: str) -> str:
    """
    Identify and extract the bibliography/references section from the text.

    Common section headers: "References", "Bibliography", "Works Cited"
    """
    # Look for common bibliography section markers
    markers = [
        "References",
        "REFERENCES",
        "Bibliography",
        "BIBLIOGRAPHY",
        "Works Cited",
        "WORKS CITED",
        "Literature",
        "LITERATURE",
    ]

    # Find the start of the bibliography section
    bib_start = -1
    for marker in markers:
        # Look for the marker as a standalone line or section header
        idx = text.find(f"\n{marker}\n")
        if idx == -1:
            idx = text.find(f"\n{marker} \n")
        if idx != -1:
            bib_start = idx
            break

    if bib_start == -1:
        print("Warning: Could not find bibliography section. Will parse entire document.")
        return text

    # Extract from bibliography start to end
    bib_text = text[bib_start:]

    return bib_text


def main() -> None:
    """Main function to extract bibliographic references from PDF."""
    # For this manual workflow, we'll extract the text and let the user
    # manually create RawTextBibitem objects

    pdf_path = "data/biblio/biblio-training/new-ones-for-Claude/freivogel.pdf"
    output_path = "data/biblio/biblio-training/out.csv"

    print(f"Reading PDF: {pdf_path}")
    print(f"Using PDF library: {PDF_LIBRARY}")

    # Extract text
    full_text = extract_text_from_pdf(pdf_path)
    print(f"Extracted {len(full_text)} characters from PDF")

    # Find bibliography section
    bib_text = identify_bibliography_section(full_text)
    print(f"Bibliography section: {len(bib_text)} characters")

    # Save to temporary file for manual review
    temp_output = Path("data/biblio/biblio-training/freivogel_extracted_refs.txt")
    temp_output.write_text(bib_text, encoding='utf-8')
    print(f"\n✓ Extracted text saved to: {temp_output}")
    print(f"\nPlease review the extracted text and manually create RawTextBibitem objects.")
    print(f"The bibliography section starts around character {full_text.find(bib_text[:100])}")

    # Show a preview
    print("\n" + "=" * 80)
    print("PREVIEW OF EXTRACTED BIBLIOGRAPHY:")
    print("=" * 80)
    print(bib_text[:2000])
    print("=" * 80)


if __name__ == "__main__":
    main()
