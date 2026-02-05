"""Tests for Rust/Python scorer parity.

These tests verify that the Rust and Python scoring paths produce
consistent results. Note: the algorithms differ slightly (Rust uses
Jaro-Winkler via strsim, Python uses token_sort_ratio from fuzzywuzzy),
so we test for agreement on ranking rather than exact score equality.
"""

from typing import Tuple

import pytest

from philoch_bib_sdk.logic.default_models import default_bib_item
from philoch_bib_sdk.logic.models import BibItem

from philoch_bib_enhancer.fuzzy_matching.matcher import (
    _RUST_SCORER_AVAILABLE,
    build_index,
    stage_bibitems_batch,
)
from philoch_bib_enhancer.fuzzy_matching.models import FuzzyMatchWeights

pytestmark = pytest.mark.skipif(not _RUST_SCORER_AVAILABLE, reason="Rust scorer not available")


# ============================================================================
# token_sort_ratio parity
# ============================================================================


class TestTokenSortRatio:
    def test_identical_strings(self) -> None:
        from philoch_bib_enhancer._rust import token_sort_ratio

        score = token_sort_ratio("hello world", "hello world")
        assert abs(score - 100.0) < 0.001

    def test_reordered_tokens(self) -> None:
        from philoch_bib_enhancer._rust import token_sort_ratio

        score = token_sort_ratio("hello world", "world hello")
        assert abs(score - 100.0) < 0.001

    def test_empty_string(self) -> None:
        from philoch_bib_enhancer._rust import token_sort_ratio

        assert token_sort_ratio("", "hello") == 0.0
        assert token_sort_ratio("hello", "") == 0.0

    def test_similar_strings_nonzero(self) -> None:
        from philoch_bib_enhancer._rust import token_sort_ratio

        score = token_sort_ratio("Introduction to Philosophy", "Intro to Philosophy")
        assert score > 50.0


# ============================================================================
# Rust vs Python batch scoring parity
# ============================================================================


class TestRustPythonParity:
    @pytest.fixture
    def bibliography(self) -> Tuple[BibItem, ...]:
        return (
            default_bib_item(
                bibkey={"first_author": "Smith", "date": 2024},
                title={"latex": "Introduction to Philosophy", "simplified": "Introduction to Philosophy"},
                author=({"given_name": {"simplified": "John"}, "family_name": {"simplified": "Smith"}},),
                date={"year": 2024},
                entry_type="article",
                journal={"name": {"simplified": "Philosophy Today"}},
                volume="10",
                number="2",
            ),
            default_bib_item(
                bibkey={"first_author": "Doe", "date": 2023},
                title={"latex": "Ethics and Morality", "simplified": "Ethics and Morality"},
                author=({"given_name": {"simplified": "Jane"}, "family_name": {"simplified": "Doe"}},),
                date={"year": 2023},
                entry_type="article",
                journal={"name": {"simplified": "Ethics Quarterly"}},
            ),
            default_bib_item(
                bibkey={"first_author": "Johnson", "date": 2022},
                title={"latex": "Metaphysics Revisited", "simplified": "Metaphysics Revisited"},
                author=(
                    {"given_name": {"simplified": "Robert"}, "family_name": {"simplified": "Johnson"}},
                    {"given_name": {"simplified": "Alice"}, "family_name": {"simplified": "Williams"}},
                ),
                date={"year": 2022},
                entry_type="book",
                publisher={"simplified": "Academic Press"},
            ),
        )

    @pytest.fixture
    def subjects(self) -> Tuple[BibItem, ...]:
        return (
            default_bib_item(
                bibkey={"first_author": "Unknown", "date": 2024},
                title={"latex": "Introduction to Philosophy", "simplified": "Introduction to Philosophy"},
                author=({"given_name": {"simplified": "John"}, "family_name": {"simplified": "Smith"}},),
                date={"year": 2024},
                entry_type="article",
            ),
            default_bib_item(
                bibkey={"first_author": "Unknown", "date": 2023},
                title={"latex": "Ethics", "simplified": "Ethics"},
                author=({"given_name": {"simplified": "Jane"}, "family_name": {"simplified": "Doe"}},),
                date={"year": 2023},
                entry_type="article",
            ),
        )

    def test_both_return_same_count(self, bibliography: Tuple[BibItem, ...], subjects: Tuple[BibItem, ...]) -> None:
        index = build_index(bibliography)

        rust_results = stage_bibitems_batch(subjects, index, top_n=3, use_rust=True)
        python_results = stage_bibitems_batch(subjects, index, top_n=3, use_rust=False)

        assert len(rust_results) == len(python_results) == len(subjects)

    def test_top1_match_agrees(self, bibliography: Tuple[BibItem, ...], subjects: Tuple[BibItem, ...]) -> None:
        """Both scorers should agree on the best match for each subject."""
        index = build_index(bibliography)

        rust_results = stage_bibitems_batch(subjects, index, top_n=1, use_rust=True)
        python_results = stage_bibitems_batch(subjects, index, top_n=1, use_rust=False)

        for rust_staged, python_staged in zip(rust_results, python_results):
            if rust_staged.top_matches and python_staged.top_matches:
                rust_best = rust_staged.top_matches[0].bibkey
                python_best = python_staged.top_matches[0].bibkey
                assert rust_best == python_best, f"Top match disagreement: Rust={rust_best}, Python={python_best}"

    def test_scores_have_same_sign(self, bibliography: Tuple[BibItem, ...], subjects: Tuple[BibItem, ...]) -> None:
        """Both scorers should produce non-negative scores."""
        index = build_index(bibliography)

        rust_results = stage_bibitems_batch(subjects, index, top_n=3, use_rust=True)
        python_results = stage_bibitems_batch(subjects, index, top_n=3, use_rust=False)

        for rust_staged in rust_results:
            for match in rust_staged.top_matches:
                assert match.total_score >= 0

        for python_staged in python_results:
            for match in python_staged.top_matches:
                assert match.total_score >= 0

    def test_custom_weights_both_paths(self, bibliography: Tuple[BibItem, ...], subjects: Tuple[BibItem, ...]) -> None:
        """Custom weights should work for both Rust and Python paths."""
        index = build_index(bibliography)
        weights: FuzzyMatchWeights = {"title": 0.7, "author": 0.1, "date": 0.1, "bonus": 0.1}

        rust_results = stage_bibitems_batch(subjects, index, top_n=2, use_rust=True, weights=weights)
        python_results = stage_bibitems_batch(subjects, index, top_n=2, use_rust=False, weights=weights)

        assert len(rust_results) == len(python_results)
        # Both should still agree on best match
        for rust_staged, python_staged in zip(rust_results, python_results):
            if rust_staged.top_matches and python_staged.top_matches:
                assert rust_staged.top_matches[0].bibkey == python_staged.top_matches[0].bibkey

    def test_rust_scorer_metadata(self, bibliography: Tuple[BibItem, ...], subjects: Tuple[BibItem, ...]) -> None:
        """Rust scorer should report 'rust' in metadata."""
        index = build_index(bibliography)
        rust_results = stage_bibitems_batch(subjects, index, top_n=2, use_rust=True)

        for staged in rust_results:
            assert staged.search_metadata.get("scorer") == "rust"
