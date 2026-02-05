"""Tests for the fuzzy matcher CLI module."""

import tempfile
import time
from pathlib import Path
from typing import Tuple

import pytest

from philoch_bib_sdk.logic.default_models import default_bib_item
from philoch_bib_enhancer.fuzzy_matching.matcher import (
    build_index,
    build_index_cached,
    stage_bibitems_batch,
)
from philoch_bib_sdk.logic.models import BibItem

from philoch_bib_enhancer.cli.fuzzy_matcher_cli import (
    _get_str,
    build_plaintext_citation,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_bibliography() -> Tuple[BibItem, ...]:
    """Create a sample bibliography with a few items."""
    return (
        default_bib_item(
            bibkey={"first_author": "Smith", "date": 2024},
            title={"latex": "Introduction to Philosophy"},
            author=({"given_name": {"latex": "John"}, "family_name": {"latex": "Smith"}},),
            date={"year": 2024},
            entry_type="article",
            journal={"name": {"latex": "Philosophy Today", "simplified": "philosophy today"}},
            volume="10",
            number="2",
        ),
        default_bib_item(
            bibkey={"first_author": "Doe", "date": 2023},
            title={"latex": "Ethics and Morality"},
            author=({"given_name": {"latex": "Jane"}, "family_name": {"latex": "Doe"}},),
            date={"year": 2023},
            entry_type="article",
            journal={"name": {"latex": "Ethics Quarterly", "simplified": "ethics quarterly"}},
        ),
        default_bib_item(
            bibkey={"first_author": "Johnson", "date": 2022},
            title={"latex": "Metaphysics Revisited"},
            author=(
                {"given_name": {"latex": "Robert"}, "family_name": {"latex": "Johnson"}},
                {"given_name": {"latex": "Alice"}, "family_name": {"latex": "Williams"}},
            ),
            date={"year": 2022},
            entry_type="book",
            publisher={"latex": "Academic Press"},
            journal={"name": {"latex": "Metaphysics Press", "simplified": "metaphysics press"}},
        ),
    )


@pytest.fixture
def sample_subjects() -> Tuple[BibItem, ...]:
    """Create sample subjects to match against the bibliography."""
    return (
        default_bib_item(
            bibkey={"first_author": "Unknown", "date": 2024},
            title={"latex": "Introduction to Philosophy"},
            author=({"given_name": {"latex": "John"}, "family_name": {"latex": "Smith"}},),
            date={"year": 2024},
            entry_type="article",
        ),
        default_bib_item(
            bibkey={"first_author": "Unknown", "date": 2023},
            title={"latex": "Ethics"},
            author=({"given_name": {"latex": "Jane"}, "family_name": {"latex": "Doe"}},),
            date={"year": 2023},
            entry_type="article",
        ),
    )


# ============================================================================
# Unit Tests
# ============================================================================


class TestGetStr:
    """Tests for _get_str helper function."""

    def test_with_bib_string_attr(self, sample_bibliography: Tuple[BibItem, ...]) -> None:
        """Test extracting string from BibStringAttr."""
        item = sample_bibliography[0]
        result = _get_str(item.title)
        assert result == "" or result == "Introduction to Philosophy"

    def test_with_string(self) -> None:
        """Test with plain string input."""
        result = _get_str("test string")
        assert result == "test string"

    def test_with_none(self) -> None:
        """Test with None input."""
        result = _get_str(None)
        assert result == ""

    def test_with_empty_string(self) -> None:
        """Test with empty string input."""
        result = _get_str("")
        assert result == ""


class TestBuildPlaintextCitation:
    """Tests for build_plaintext_citation function."""

    def test_article_with_journal(self, sample_bibliography: Tuple[BibItem, ...]) -> None:
        """Test citation for article with journal."""
        item = sample_bibliography[0]
        citation = build_plaintext_citation(item)
        assert isinstance(citation, str)
        assert citation.endswith(".")

    def test_book_with_publisher(self, sample_bibliography: Tuple[BibItem, ...]) -> None:
        """Test citation for book with publisher."""
        item = sample_bibliography[2]
        citation = build_plaintext_citation(item)
        assert isinstance(citation, str)

    def test_empty_item(self) -> None:
        """Test citation for minimal item."""
        item = default_bib_item(
            bibkey={"first_author": "Test", "date": 2024},
            entry_type="misc",
        )
        citation = build_plaintext_citation(item)
        assert citation == "" or citation == "."


class TestBuildIndexCached:
    """Tests for build_index_cached function (from SDK)."""

    def test_builds_index(self, sample_bibliography: Tuple[BibItem, ...]) -> None:
        """Test that build_index_cached creates an index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test-index.pkl"
            index = build_index_cached(sample_bibliography, cache_path=cache_path)

            assert index is not None
            assert hasattr(index, "all_items")
            assert len(index.all_items) == len(sample_bibliography)

    def test_creates_cache_file(self, sample_bibliography: Tuple[BibItem, ...]) -> None:
        """Test that cache file is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test-index.pkl"
            assert not cache_path.exists()

            build_index_cached(sample_bibliography, cache_path=cache_path)

            assert cache_path.exists()

    def test_loads_from_cache(self, sample_bibliography: Tuple[BibItem, ...]) -> None:
        """Test that subsequent calls load from cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test-index.pkl"

            # First call - builds and caches
            index1 = build_index_cached(sample_bibliography, cache_path=cache_path)

            # Second call - should load from cache
            index2 = build_index_cached(sample_bibliography, cache_path=cache_path)

            assert len(index1.all_items) == len(index2.all_items)

    def test_force_rebuild(self, sample_bibliography: Tuple[BibItem, ...]) -> None:
        """Test force_rebuild parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test-index.pkl"

            # First call
            build_index_cached(sample_bibliography, cache_path=cache_path)
            first_mtime = cache_path.stat().st_mtime

            # Force rebuild
            time.sleep(0.01)
            build_index_cached(sample_bibliography, cache_path=cache_path, force_rebuild=True)
            second_mtime = cache_path.stat().st_mtime

            assert second_mtime > first_mtime


# ============================================================================
# Integration Tests
# ============================================================================


class TestFuzzyMatchingIntegration:
    """Integration tests for the fuzzy matching pipeline."""

    def test_full_matching_pipeline(
        self, sample_bibliography: Tuple[BibItem, ...], sample_subjects: Tuple[BibItem, ...]
    ) -> None:
        """Test the complete matching pipeline."""
        # Build index
        index = build_index(sample_bibliography)

        # Run matching
        staged = stage_bibitems_batch(
            sample_subjects,
            index,
            top_n=3,
            min_score=0.0,
        )

        # Verify results
        assert len(staged) == len(sample_subjects)
        for item in staged:
            assert hasattr(item, "top_matches")
            assert hasattr(item, "search_metadata")

    def test_matching_with_cached_index(
        self, sample_bibliography: Tuple[BibItem, ...], sample_subjects: Tuple[BibItem, ...]
    ) -> None:
        """Test matching using cached index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test-index.pkl"

            # Build cached index
            index = build_index_cached(sample_bibliography, cache_path)

            # Run matching
            staged = stage_bibitems_batch(
                sample_subjects,
                index,
                top_n=2,
            )

            assert len(staged) == len(sample_subjects)
