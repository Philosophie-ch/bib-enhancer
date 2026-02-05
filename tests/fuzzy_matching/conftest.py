"""Shared fixtures for fuzzy matching tests."""

from typing import Tuple

import pytest

from philoch_bib_sdk.logic.default_models import default_bib_item
from philoch_bib_sdk.logic.models import BibItem


@pytest.fixture
def bib_smith_philosophy() -> BibItem:
    """Article by Smith about Introduction to Philosophy (2024)."""
    return default_bib_item(
        bibkey={"first_author": "Smith", "date": 2024},
        title={"latex": "Introduction to Philosophy", "simplified": "Introduction to Philosophy"},
        author=(
            {
                "given_name": {"latex": "John", "simplified": "John"},
                "family_name": {"latex": "Smith", "simplified": "Smith"},
            },
        ),
        date={"year": 2024},
        entry_type="article",
        journal={"name": {"latex": "Philosophy Today", "simplified": "Philosophy Today"}},
        volume="10",
        number="2",
        pages=({"start": "1", "end": "25"},),
        doi="10.1234/phil.2024.001",
        publisher={"latex": "Academic Press", "simplified": "Academic Press"},
    )


@pytest.fixture
def bib_doe_ethics() -> BibItem:
    """Article by Doe about Ethics and Morality (2023)."""
    return default_bib_item(
        bibkey={"first_author": "Doe", "date": 2023},
        title={"latex": "Ethics and Morality", "simplified": "Ethics and Morality"},
        author=(
            {
                "given_name": {"latex": "Jane", "simplified": "Jane"},
                "family_name": {"latex": "Doe", "simplified": "Doe"},
            },
        ),
        date={"year": 2023},
        entry_type="article",
        journal={"name": {"latex": "Ethics Quarterly", "simplified": "Ethics Quarterly"}},
    )


@pytest.fixture
def bib_johnson_metaphysics() -> BibItem:
    """Book by Johnson & Williams about Metaphysics (2022)."""
    return default_bib_item(
        bibkey={"first_author": "Johnson", "date": 2022},
        title={"latex": "Metaphysics Revisited", "simplified": "Metaphysics Revisited"},
        author=(
            {
                "given_name": {"latex": "Robert", "simplified": "Robert"},
                "family_name": {"latex": "Johnson", "simplified": "Johnson"},
            },
            {
                "given_name": {"latex": "Alice", "simplified": "Alice"},
                "family_name": {"latex": "Williams", "simplified": "Williams"},
            },
        ),
        date={"year": 2022},
        entry_type="book",
        publisher={"latex": "Academic Press", "simplified": "Academic Press"},
    )


@pytest.fixture
def bib_errata_item() -> BibItem:
    """Article with 'errata' in the title."""
    return default_bib_item(
        bibkey={"first_author": "Smith", "date": 2024},
        title={"latex": "Errata for Introduction to Philosophy", "simplified": "Errata for Introduction to Philosophy"},
        author=(
            {
                "given_name": {"latex": "John", "simplified": "John"},
                "family_name": {"latex": "Smith", "simplified": "Smith"},
            },
        ),
        date={"year": 2024},
        entry_type="article",
    )


@pytest.fixture
def bib_review_item() -> BibItem:
    """Article with 'review' in the title."""
    return default_bib_item(
        bibkey={"first_author": "Brown", "date": 2024},
        title={"latex": "A Review of Modern Ethics", "simplified": "A Review of Modern Ethics"},
        author=(
            {
                "given_name": {"latex": "Tom", "simplified": "Tom"},
                "family_name": {"latex": "Brown", "simplified": "Brown"},
            },
        ),
        date={"year": 2024},
        entry_type="article",
    )


@pytest.fixture
def bib_no_date_item() -> BibItem:
    """Item with no date."""
    return default_bib_item(
        bibkey={"first_author": "Anon", "date": 0},
        title={"latex": "Some Undated Work", "simplified": "Some Undated Work"},
        author=(
            {
                "given_name": {"latex": "Anonymous", "simplified": "Anonymous"},
                "family_name": {"latex": "Anon", "simplified": "Anon"},
            },
        ),
        entry_type="misc",
    )


@pytest.fixture
def sample_bibliography(
    bib_smith_philosophy: BibItem,
    bib_doe_ethics: BibItem,
    bib_johnson_metaphysics: BibItem,
) -> Tuple[BibItem, ...]:
    """Small bibliography with 3 items for testing."""
    return (bib_smith_philosophy, bib_doe_ethics, bib_johnson_metaphysics)


@pytest.fixture
def subject_exact_match() -> BibItem:
    """Subject that should match Smith's philosophy article exactly (same DOI)."""
    return default_bib_item(
        bibkey={"first_author": "Unknown", "date": 2024},
        title={"latex": "Introduction to Philosophy", "simplified": "Introduction to Philosophy"},
        author=(
            {
                "given_name": {"latex": "John", "simplified": "John"},
                "family_name": {"latex": "Smith", "simplified": "Smith"},
            },
        ),
        date={"year": 2024},
        entry_type="article",
        doi="10.1234/phil.2024.001",
    )


@pytest.fixture
def subject_close_match() -> BibItem:
    """Subject that should closely match Smith's article (same title, no DOI)."""
    return default_bib_item(
        bibkey={"first_author": "Unknown", "date": 2024},
        title={"latex": "Introduction to Philosophy", "simplified": "Introduction to Philosophy"},
        author=(
            {
                "given_name": {"latex": "J.", "simplified": "J."},
                "family_name": {"latex": "Smith", "simplified": "Smith"},
            },
        ),
        date={"year": 2024},
        entry_type="article",
    )


@pytest.fixture
def subject_partial_match() -> BibItem:
    """Subject with only partial title match to Ethics article."""
    return default_bib_item(
        bibkey={"first_author": "Unknown", "date": 2023},
        title={"latex": "Ethics", "simplified": "Ethics"},
        author=(
            {
                "given_name": {"latex": "Jane", "simplified": "Jane"},
                "family_name": {"latex": "Doe", "simplified": "Doe"},
            },
        ),
        date={"year": 2023},
        entry_type="article",
    )
