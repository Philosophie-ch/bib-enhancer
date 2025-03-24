from philoch_bib_enhancer.logic.functions import author_full_name
from philoch_bib_enhancer.logic.models import Author


def test_slotted_classes_are_slotted() -> None:
    author = Author(given_name="John", family_name="Doe")
    assert "__dict__" not in author.__slots__

    try:
        author.random_attribute = "random"  # type: ignore
    except AttributeError:
        assert True


def test_frozen_classes_are_frozen() -> None:
    author = Author(given_name="John", family_name="Doe")
    try:
        author.given_name = "Jane"  # type: ignore
    except AttributeError:
        assert True


def test_author_full_name() -> None:
    author = Author(given_name="John", family_name="Doe")
    full_name = author_full_name(author)

    assert full_name == "Doe, John"
