#!/usr/bin/env python3
"""Generate PhilStudies benchmark fixtures from bibliography and annotated CSV.

This script:
1. Loads the full bibliography ODS and filters for PhilStudies entries
2. Parses the team's annotated CSV with ground truth labels
3. Outputs two fixture files for the benchmark test suite

Usage:
    python scripts/generate_philstudies_benchmark.py
"""

import csv
import json
import re
from pathlib import Path

import polars as pl


# Paths
PROJECT_ROOT = Path(__file__).parent.parent
BIBLIOGRAPHY_ODS = PROJECT_ROOT / "data/biblio/biblio-v10-table.ods"
ANNOTATED_CSV = PROJECT_ROOT / "data/biblio/philstudies-1950-2017-PB.csv"
OUTPUT_DIR = PROJECT_ROOT / "tests/fuzzy_matching/benchmark_data"

# Output files
OUTPUT_BIBLIOGRAPHY = OUTPUT_DIR / "philstudies_bibliography.csv"
OUTPUT_GROUND_TRUTH = OUTPUT_DIR / "philstudies_ground_truth.json"


def load_annotated_csv() -> tuple[list[dict[str, str]], set[str]]:
    """Load the annotated CSV and extract ground truth + referenced bibkeys.

    Returns:
        Tuple of (ground_truth_cases, all_referenced_bibkeys)
    """
    ground_truth: list[dict[str, str]] = []
    referenced_bibkeys: set[str] = set()

    with open(ANNOTATED_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            comment = (row.get("comment on update") or "").strip()

            if not comment:
                continue

            # Skip NOT NEEDED entries
            if comment == "NOT NEEDED":
                continue

            # Parse annotation type and expected bibkey
            if comment == "RIGHT KEY":
                annotation_type = "RIGHT_KEY"
                expected_bibkey = (row.get("match_1_bibkey") or "").strip()
                if expected_bibkey:
                    referenced_bibkeys.add(expected_bibkey)
            elif comment == "NOT IN BIBLIO":
                annotation_type = "NOT_IN_BIBLIO"
                expected_bibkey = ""
            elif comment.startswith("WRONG KEY"):
                annotation_type = "WRONG_KEY"
                # Extract correct bibkey from comment: "WRONG KEY, RIGHT ONE IS: xyz"
                match = re.search(r"RIGHT ONE IS:\s*(\S+)", comment)
                expected_bibkey = match.group(1) if match else ""
                if expected_bibkey:
                    referenced_bibkeys.add(expected_bibkey)
                # Also track what the matcher incorrectly chose
                wrong_match = (row.get("match_1_bibkey") or "").strip()
                if wrong_match:
                    referenced_bibkeys.add(wrong_match)
            else:
                # Unknown annotation, skip
                continue

            # Extract subject fields
            case = {
                "annotation_type": annotation_type,
                "expected_bibkey": expected_bibkey,
                "entry_type": row.get("entry_type") or "",
                "title": row.get("title") or "",
                "author": row.get("author") or "",
                "date": row.get("date") or "",
                "doi": row.get("doi") or "",
                "journal": row.get("journal") or "",
                "volume": row.get("volume") or "",
                "number": row.get("number") or "",
                "pages": row.get("pages") or "",
                # Also capture the original match results for analysis
                "original_match_1_bibkey": row.get("match_1_bibkey") or "",
                "original_match_1_score": row.get("match_1_score") or "",
            }
            ground_truth.append(case)

    return ground_truth, referenced_bibkeys


def filter_bibliography(referenced_bibkeys: set[str]) -> pl.DataFrame:
    """Load bibliography ODS and filter for PhilStudies + referenced entries.

    Args:
        referenced_bibkeys: Set of bibkeys referenced in annotations

    Returns:
        Filtered polars DataFrame
    """
    print(f"Loading bibliography from {BIBLIOGRAPHY_ODS}...")
    df = pl.read_ods(source=str(BIBLIOGRAPHY_ODS), has_header=True)
    print(f"  Loaded {len(df)} total entries")

    # Normalize column names (replace hyphens with underscores)
    df = df.rename({col: col.replace("-", "_") for col in df.columns})

    # Filter 1: Journal contains "Philosophical Studies" (case-insensitive)
    journal_col = "journal"
    if journal_col in df.columns:
        philstudies_mask = df[journal_col].str.to_lowercase().str.contains("philosophical studies")
        philstudies_df = df.filter(philstudies_mask)
        print(f"  PhilStudies journal entries: {len(philstudies_df)}")
    else:
        print(f"  Warning: No 'journal' column found")
        philstudies_df = df.head(0)  # Empty

    # Filter 2: Bibkey in referenced set
    bibkey_col = "bibkey"
    if bibkey_col in df.columns:
        referenced_mask = df[bibkey_col].is_in(list(referenced_bibkeys))
        referenced_df = df.filter(referenced_mask)
        print(f"  Referenced bibkey entries: {len(referenced_df)}")
    else:
        print(f"  Warning: No 'bibkey' column found")
        referenced_df = df.head(0)  # Empty

    # Combine both filters (union)
    combined = pl.concat([philstudies_df, referenced_df]).unique(subset=[bibkey_col])
    print(f"  Combined unique entries: {len(combined)}")

    return combined


def main() -> None:
    """Main entry point."""
    print("=" * 70)
    print("GENERATING PHILSTUDIES BENCHMARK FIXTURES")
    print("=" * 70)

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Parse annotated CSV
    print("\nStep 1: Parsing annotated CSV...")
    ground_truth, referenced_bibkeys = load_annotated_csv()

    # Count by annotation type
    counts: dict[str, int] = {}
    for case in ground_truth:
        t = case["annotation_type"]
        counts[t] = counts.get(t, 0) + 1

    print(f"  Ground truth cases: {len(ground_truth)}")
    for t, c in sorted(counts.items()):
        print(f"    {t}: {c}")
    print(f"  Referenced bibkeys: {len(referenced_bibkeys)}")

    # Step 2: Filter bibliography
    print("\nStep 2: Filtering bibliography...")
    filtered_bib = filter_bibliography(referenced_bibkeys)

    # Step 3: Write outputs
    print("\nStep 3: Writing outputs...")

    # Write bibliography CSV
    filtered_bib.write_csv(str(OUTPUT_BIBLIOGRAPHY))
    print(f"  Bibliography CSV: {OUTPUT_BIBLIOGRAPHY}")
    print(f"    {len(filtered_bib)} entries")

    # Write ground truth JSON
    with open(OUTPUT_GROUND_TRUTH, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2, ensure_ascii=False)
    print(f"  Ground truth JSON: {OUTPUT_GROUND_TRUTH}")
    print(f"    {len(ground_truth)} cases")

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
