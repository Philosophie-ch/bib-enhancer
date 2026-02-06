"""PhilStudies benchmark tests for fuzzy matching accuracy.

This module provides:
1. Session-scoped fixtures for loading benchmark data
2. Metrics functions for computing precision, recall, MRR
3. Tests that validate fuzzy matching accuracy against human-annotated ground truth

Run with: pytest -m slow tests/fuzzy_matching/test_benchmark.py -v

================================================================================
BENCHMARK RESULTS (2026-02-06)
================================================================================

Ground truth: 4,972 annotated cases from PhilStudies CrossRef data (1950-2017)
- RIGHT_KEY: 3,037 (match_1 correct)
- WRONG_KEY: 313 (match_1 wrong, correct bibkey annotated)
- NOT_IN_BIBLIO: 1,622 (no match exists in bibliography)

Weight configuration comparison:

| Config       | Title | Author | Date | Bonus | P@1    | R@5    | MRR    |
|--------------|-------|--------|------|-------|--------|--------|--------|
| default      | 0.5   | 0.3    | 0.1  | 0.1   | 90.77% | 98.36% | 0.9386 |
| title_heavy  | 0.7   | 0.2    | 0.05 | 0.05  | 87.58% | 94.98% | 0.8983 |
| author_heavy | 0.3   | 0.5    | 0.1  | 0.1   | 94.80% | 98.66% | 0.9650 |
| balanced     | 0.4   | 0.4    | 0.1  | 0.1   | 95.46% | 98.93% | 0.9703 |
| date_boost   | 0.45  | 0.3    | 0.2  | 0.05  | 91.85% | 98.75% | 0.9473 |
| bonus_boost  | 0.4   | 0.3    | 0.05 | 0.25  | 95.49% | 98.98% | 0.9711 |

WINNER: bonus_boost (0.4/0.3/0.05/0.25) with 95.49% P@1

Why bonus_boost works best for PhilStudies:
- Title 0.5→0.4: Many articles have short/generic titles ("Reply to X", "'Ought' again")
- Bonus 0.1→0.25: DOI and journal+vol+num matches are highly reliable when present
- Date 0.1→0.05: CrossRef often has wrong dates (online-early vs issue date)

Score statistics by annotation type:
- RIGHT_KEY: median=176.00, min=79.22, max=187.00
- WRONG_KEY: median=120.22, min=86.19, max=176.00
- NOT_IN_BIBLIO: median=105.24, min=41.52, max=186.00

METRICS GLOSSARY
----------------
- P@1 (Precision@1): Percentage of queries where the correct answer is ranked #1.
  This is the key metric — if users trust the first result, it must be right.

- R@5 (Recall@5): Percentage of queries where the correct answer appears in top 5.
  Even if rank 1 is wrong, a human reviewer can quickly scan 5 options.

- MRR (Mean Reciprocal Rank): Average of 1/rank for each query.
  - Rank 1 → 1.0, Rank 2 → 0.5, Rank 3 → 0.33, Not found → 0
  - MRR of 0.97 means correct answer is almost always at rank 1.

To re-run: pytest -m slow tests/fuzzy_matching/test_benchmark.py -v -s
================================================================================
"""

import json
from pathlib import Path
from typing import TypedDict

import pytest

from aletk.ResultMonad import Err
from philoch_bib_sdk.adapters.io.csv import load_bibliography_csv
from philoch_bib_sdk.converters.plaintext.bibitem.parser import parse_bibitem
from philoch_bib_sdk.logic.models import BibItem

from philoch_bib_enhancer.fuzzy_matching.matcher import (
    build_index,
    stage_bibitems_batch,
    BibItemBlockIndex,
)
from philoch_bib_enhancer.fuzzy_matching.models import FuzzyMatchWeights, Match


# ============================================================================
# Types
# ============================================================================


class GroundTruthCase(TypedDict):
    """A single ground truth test case."""

    annotation_type: str  # RIGHT_KEY, WRONG_KEY, NOT_IN_BIBLIO
    expected_bibkey: str  # Empty for NOT_IN_BIBLIO
    entry_type: str
    title: str
    author: str
    date: str
    doi: str
    journal: str
    volume: str
    number: str
    pages: str
    original_match_1_bibkey: str
    original_match_1_score: str


class BenchmarkResult(TypedDict):
    """Result for a single benchmark case."""

    case: GroundTruthCase
    subject: BibItem
    matches: tuple[Match, ...]
    rank_of_correct: int | None  # None if not found, 1-indexed if found


# ============================================================================
# Paths
# ============================================================================

BENCHMARK_DATA_DIR = Path(__file__).parent / "benchmark_data"
BIBLIOGRAPHY_CSV = BENCHMARK_DATA_DIR / "philstudies_bibliography.csv"
GROUND_TRUTH_JSON = BENCHMARK_DATA_DIR / "philstudies_ground_truth.json"


# ============================================================================
# Session-scoped fixtures
# ============================================================================


@pytest.fixture(scope="session")
def philstudies_bibliography() -> tuple[BibItem, ...]:
    """Load PhilStudies bibliography from benchmark CSV."""
    if not BIBLIOGRAPHY_CSV.exists():
        pytest.skip(f"Benchmark data not found: {BIBLIOGRAPHY_CSV}. Run scripts/generate_philstudies_benchmark.py")

    result = load_bibliography_csv(str(BIBLIOGRAPHY_CSV))
    if isinstance(result, Err):
        pytest.fail(f"Failed to load bibliography: {result.message}")

    return tuple(result.out.values())


@pytest.fixture(scope="session")
def philstudies_bibkey_map() -> dict[str, BibItem]:
    """Load PhilStudies bibliography as bibkey -> BibItem map."""
    if not BIBLIOGRAPHY_CSV.exists():
        pytest.skip(f"Benchmark data not found: {BIBLIOGRAPHY_CSV}")

    result = load_bibliography_csv(str(BIBLIOGRAPHY_CSV))
    if isinstance(result, Err):
        pytest.fail(f"Failed to load bibliography: {result.message}")

    return result.out


@pytest.fixture(scope="session")
def philstudies_index(philstudies_bibliography: tuple[BibItem, ...]) -> BibItemBlockIndex:
    """Build index from PhilStudies bibliography."""
    return build_index(philstudies_bibliography)


@pytest.fixture(scope="session")
def philstudies_ground_truth() -> list[GroundTruthCase]:
    """Load ground truth cases from JSON."""
    if not GROUND_TRUTH_JSON.exists():
        pytest.skip(f"Benchmark data not found: {GROUND_TRUTH_JSON}")

    with open(GROUND_TRUTH_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate structure
    cases: list[GroundTruthCase] = []
    for item in data:
        case: GroundTruthCase = {
            "annotation_type": item["annotation_type"],
            "expected_bibkey": item["expected_bibkey"],
            "entry_type": item["entry_type"],
            "title": item["title"],
            "author": item["author"],
            "date": item["date"],
            "doi": item["doi"],
            "journal": item["journal"],
            "volume": item["volume"],
            "number": item["number"],
            "pages": item["pages"],
            "original_match_1_bibkey": item["original_match_1_bibkey"],
            "original_match_1_score": item["original_match_1_score"],
        }
        cases.append(case)

    return cases


# ============================================================================
# Helper functions
# ============================================================================


def case_to_bibitem(case: GroundTruthCase, row_num: int) -> BibItem | None:
    """Convert a ground truth case to a BibItem for matching."""
    parsed_data = {
        "entry_type": case["entry_type"] or "article",
        "title": case["title"],
        "author": case["author"],
        "date": case["date"],
        "doi": case["doi"],
        "journal": case["journal"],
        "volume": case["volume"],
        "number": case["number"],
        "pages": case["pages"],
        "bibkey": f"subject:{row_num}",  # Temporary bibkey
    }
    # Filter empty values
    parsed_data = {k: v for k, v in parsed_data.items() if v}
    if "bibkey" not in parsed_data:
        parsed_data["bibkey"] = f"subject:{row_num}"

    result = parse_bibitem(parsed_data, bibstring_type="simplified")
    if isinstance(result, Err):
        return None
    return result.out


def run_benchmark(
    ground_truth: list[GroundTruthCase],
    index: BibItemBlockIndex,
    weights: FuzzyMatchWeights | None = None,
    top_n: int = 5,
) -> list[BenchmarkResult]:
    """Run fuzzy matching on all ground truth cases.

    Args:
        ground_truth: List of ground truth cases
        index: Pre-built bibliography index
        weights: Weight configuration (None for defaults)
        top_n: Number of matches to retrieve per subject

    Returns:
        List of benchmark results with match info
    """
    # Convert cases to BibItems, tracking which cases were parseable
    subjects: list[BibItem] = []
    case_indices: list[int] = []  # Maps subject index -> ground_truth index

    for i, case in enumerate(ground_truth):
        subject = case_to_bibitem(case, i)
        if subject is not None:
            subjects.append(subject)
            case_indices.append(i)

    # Run batch matching with Rust scorer
    staged_results = stage_bibitems_batch(
        tuple(subjects),
        index,
        top_n=top_n,
        weights=weights,
    )

    # Build results
    results: list[BenchmarkResult] = []
    for staged, case_idx in zip(staged_results, case_indices):
        case = ground_truth[case_idx]
        matches = staged.top_matches

        # Find rank of correct answer (if this is RIGHT_KEY or WRONG_KEY)
        rank_of_correct: int | None = None
        expected = case["expected_bibkey"]
        if expected:
            for match in matches:
                if match.bibkey == expected:
                    rank_of_correct = match.rank
                    break

        results.append(
            {
                "case": case,
                "subject": staged.bibitem,
                "matches": matches,
                "rank_of_correct": rank_of_correct,
            }
        )

    return results


# ============================================================================
# Metrics functions
# ============================================================================


def compute_precision_at_1(results: list[BenchmarkResult]) -> float:
    """Compute precision@1: % of RIGHT_KEY/WRONG_KEY cases where rank-1 is correct."""
    relevant_results = [r for r in results if r["case"]["annotation_type"] in ("RIGHT_KEY", "WRONG_KEY")]

    if not relevant_results:
        return 0.0

    correct = sum(1 for r in relevant_results if r["rank_of_correct"] == 1)
    return correct / len(relevant_results)


def compute_recall_at_k(results: list[BenchmarkResult], k: int) -> float:
    """Compute recall@k: % of RIGHT_KEY/WRONG_KEY cases where correct is in top-k."""
    relevant_results = [r for r in results if r["case"]["annotation_type"] in ("RIGHT_KEY", "WRONG_KEY")]

    if not relevant_results:
        return 0.0

    found = sum(1 for r in relevant_results if r["rank_of_correct"] is not None and r["rank_of_correct"] <= k)
    return found / len(relevant_results)


def compute_mrr(results: list[BenchmarkResult]) -> float:
    """Compute Mean Reciprocal Rank for RIGHT_KEY/WRONG_KEY cases."""
    relevant_results = [r for r in results if r["case"]["annotation_type"] in ("RIGHT_KEY", "WRONG_KEY")]

    if not relevant_results:
        return 0.0

    reciprocal_ranks = []
    for r in relevant_results:
        if r["rank_of_correct"] is not None:
            reciprocal_ranks.append(1.0 / r["rank_of_correct"])
        else:
            reciprocal_ranks.append(0.0)

    return sum(reciprocal_ranks) / len(reciprocal_ranks)


def compute_score_stats(results: list[BenchmarkResult]) -> dict[str, dict[str, float]]:
    """Compute score statistics by annotation type."""
    stats: dict[str, list[float]] = {"RIGHT_KEY": [], "WRONG_KEY": [], "NOT_IN_BIBLIO": []}

    for r in results:
        annotation = r["case"]["annotation_type"]
        if r["matches"] and annotation in stats:
            stats[annotation].append(r["matches"][0].total_score)

    output: dict[str, dict[str, float]] = {}
    for annotation, scores in stats.items():
        if scores:
            sorted_scores = sorted(scores)
            n = len(sorted_scores)
            output[annotation] = {
                "count": float(n),
                "min": sorted_scores[0],
                "median": sorted_scores[n // 2],
                "max": sorted_scores[-1],
            }

    return output


# ============================================================================
# Tests
# ============================================================================


@pytest.mark.slow
class TestPhilStudiesBenchmark:
    """Benchmark tests for PhilStudies fuzzy matching accuracy."""

    def test_default_weights_precision(
        self,
        philstudies_ground_truth: list[GroundTruthCase],
        philstudies_index: BibItemBlockIndex,
    ) -> None:
        """Test that default weights achieve baseline precision@1."""
        results = run_benchmark(philstudies_ground_truth, philstudies_index)
        precision = compute_precision_at_1(results)

        print(f"\nPrecision@1 (default weights): {precision:.2%}")
        print(
            f"  Correct at rank 1: {int(precision * len([r for r in results if r['case']['annotation_type'] in ('RIGHT_KEY', 'WRONG_KEY')]))}"
        )

        # Baseline: 95% (tuned defaults achieve 95.49% on benchmark)
        assert precision >= 0.95, f"Precision@1 {precision:.2%} below baseline 95%"

    def test_default_weights_recall_at_5(
        self,
        philstudies_ground_truth: list[GroundTruthCase],
        philstudies_index: BibItemBlockIndex,
    ) -> None:
        """Test that default weights achieve baseline recall@5."""
        results = run_benchmark(philstudies_ground_truth, philstudies_index, top_n=5)
        recall = compute_recall_at_k(results, k=5)

        print(f"\nRecall@5 (default weights): {recall:.2%}")

        # Baseline: 93% (estimated from original data showing 115/313 WRONG_KEY in top 2-5)
        assert recall >= 0.93, f"Recall@5 {recall:.2%} below baseline 93%"

    def test_score_separation(
        self,
        philstudies_ground_truth: list[GroundTruthCase],
        philstudies_index: BibItemBlockIndex,
    ) -> None:
        """Test that RIGHT_KEY scores are higher than NOT_IN_BIBLIO scores."""
        results = run_benchmark(philstudies_ground_truth, philstudies_index)
        stats = compute_score_stats(results)

        print("\nScore statistics by annotation type:")
        for annotation, s in stats.items():
            print(f"  {annotation}: median={s['median']:.2f}, min={s['min']:.2f}, max={s['max']:.2f}")

        right_median = stats.get("RIGHT_KEY", {}).get("median", 0)
        not_in_median = stats.get("NOT_IN_BIBLIO", {}).get("median", 0)

        assert (
            right_median > not_in_median
        ), f"RIGHT_KEY median ({right_median:.2f}) should be > NOT_IN_BIBLIO median ({not_in_median:.2f})"

    def test_mrr(
        self,
        philstudies_ground_truth: list[GroundTruthCase],
        philstudies_index: BibItemBlockIndex,
    ) -> None:
        """Test Mean Reciprocal Rank."""
        results = run_benchmark(philstudies_ground_truth, philstudies_index, top_n=5)
        mrr = compute_mrr(results)

        print(f"\nMRR (default weights): {mrr:.4f}")

        # Baseline: 0.92 (estimated from precision@1 ≈ 90.7%)
        assert mrr >= 0.92, f"MRR {mrr:.4f} below baseline 0.92"


@pytest.mark.slow
class TestWeightComparison:
    """Compare different weight configurations."""

    WEIGHT_CONFIGS: list[tuple[str, FuzzyMatchWeights]] = [
        ("default", {"title": 0.5, "author": 0.3, "date": 0.1, "bonus": 0.1}),
        ("title_heavy", {"title": 0.7, "author": 0.2, "date": 0.05, "bonus": 0.05}),
        ("author_heavy", {"title": 0.3, "author": 0.5, "date": 0.1, "bonus": 0.1}),
        ("balanced", {"title": 0.4, "author": 0.4, "date": 0.1, "bonus": 0.1}),
        ("date_boost", {"title": 0.45, "author": 0.3, "date": 0.2, "bonus": 0.05}),
        ("bonus_boost", {"title": 0.4, "author": 0.3, "date": 0.05, "bonus": 0.25}),
    ]

    @pytest.mark.parametrize("name,weights", WEIGHT_CONFIGS, ids=[c[0] for c in WEIGHT_CONFIGS])
    def test_weight_config(
        self,
        name: str,
        weights: FuzzyMatchWeights,
        philstudies_ground_truth: list[GroundTruthCase],
        philstudies_index: BibItemBlockIndex,
    ) -> None:
        """Test a specific weight configuration and report metrics."""
        results = run_benchmark(philstudies_ground_truth, philstudies_index, weights=weights, top_n=5)

        precision = compute_precision_at_1(results)
        recall = compute_recall_at_k(results, k=5)
        mrr = compute_mrr(results)

        print(f"\n{name}: P@1={precision:.2%}, R@5={recall:.2%}, MRR={mrr:.4f}")
        print(
            f"  Weights: title={weights['title']}, author={weights['author']}, date={weights['date']}, bonus={weights['bonus']}"
        )

        # Just report, don't assert (this is for comparison)
        assert True
