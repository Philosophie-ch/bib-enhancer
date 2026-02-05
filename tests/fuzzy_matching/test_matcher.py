"""Tests for fuzzy matching matcher internals."""

from typing import Tuple


from philoch_bib_sdk.logic.default_models import default_bib_item
from philoch_bib_sdk.logic.models import BibItem, BibItemDateAttr

from philoch_bib_enhancer.fuzzy_matching.matcher import (
    BibItemBlockIndex,
    _extract_author_surnames,
    _extract_trigrams,
    _get_candidate_set,
    _get_decade,
    build_index,
    find_similar_bibitems,
    stage_bibitem,
    stage_bibitems_batch,
)
from philoch_bib_enhancer.fuzzy_matching.models import (
    BibItemStaged,
    FuzzyMatchWeights,
    Match,
)


# ============================================================================
# Helper function tests
# ============================================================================


class TestExtractTrigrams:
    def test_basic(self) -> None:
        trigrams = _extract_trigrams("hello")
        assert "hel" in trigrams
        assert "ell" in trigrams
        assert "llo" in trigrams
        assert len(trigrams) == 3

    def test_short_text(self) -> None:
        assert _extract_trigrams("hi") == frozenset()
        assert _extract_trigrams("ab") == frozenset()

    def test_exact_three_chars(self) -> None:
        trigrams = _extract_trigrams("abc")
        assert trigrams == frozenset({"abc"})

    def test_empty(self) -> None:
        assert _extract_trigrams("") == frozenset()

    def test_normalization(self) -> None:
        trigrams_upper = _extract_trigrams("HELLO")
        trigrams_lower = _extract_trigrams("hello")
        assert trigrams_upper == trigrams_lower

    def test_whitespace_normalization(self) -> None:
        trigrams = _extract_trigrams("a  b  c  d")
        # After whitespace normalization: "a b c d"
        assert "a b" in trigrams


class TestExtractAuthorSurnames:
    def test_single_author(self) -> None:
        item = default_bib_item(
            bibkey={"first_author": "Smith", "date": 2024},
            entry_type="article",
            author=({"family_name": {"simplified": "Smith"}},),
        )
        surnames = _extract_author_surnames(item.author)
        assert "smith" in surnames

    def test_multiple_authors(self) -> None:
        item = default_bib_item(
            bibkey={"first_author": "Smith", "date": 2024},
            entry_type="article",
            author=(
                {"family_name": {"simplified": "Smith"}},
                {"family_name": {"simplified": "Doe"}},
            ),
        )
        surnames = _extract_author_surnames(item.author)
        assert "smith" in surnames
        assert "doe" in surnames

    def test_no_authors(self) -> None:
        assert _extract_author_surnames(()) == frozenset()

    def test_normalized_lowercase(self) -> None:
        item = default_bib_item(
            bibkey={"first_author": "SMITH", "date": 2024},
            entry_type="article",
            author=({"family_name": {"simplified": "SMITH"}},),
        )
        surnames = _extract_author_surnames(item.author)
        assert "smith" in surnames
        assert "SMITH" not in surnames


class TestGetDecade:
    def test_1990s(self) -> None:
        assert _get_decade(BibItemDateAttr(year=1995)) == 1990

    def test_2000(self) -> None:
        assert _get_decade(BibItemDateAttr(year=2000)) == 2000

    def test_2025(self) -> None:
        assert _get_decade(BibItemDateAttr(year=2025)) == 2020

    def test_no_date(self) -> None:
        assert _get_decade("no date") is None


# ============================================================================
# Index building tests
# ============================================================================


class TestBuildIndex:
    def test_creates_index(self, sample_bibliography: Tuple[BibItem, ...]) -> None:
        index = build_index(sample_bibliography)
        assert isinstance(index, BibItemBlockIndex)
        assert len(index.all_items) == len(sample_bibliography)

    def test_doi_index_populated(self, bib_smith_philosophy: BibItem) -> None:
        index = build_index((bib_smith_philosophy,))
        assert "10.1234/phil.2024.001" in index.doi_index
        assert index.doi_index["10.1234/phil.2024.001"] is bib_smith_philosophy

    def test_title_trigrams_populated(self, bib_smith_philosophy: BibItem) -> None:
        index = build_index((bib_smith_philosophy,))
        assert len(index.title_trigrams) > 0
        # "Introduction to Philosophy" should generate trigrams containing "int", "ntr", etc.
        assert "int" in index.title_trigrams

    def test_author_surnames_populated(self, bib_smith_philosophy: BibItem) -> None:
        index = build_index((bib_smith_philosophy,))
        assert "smith" in index.author_surnames
        assert bib_smith_philosophy in index.author_surnames["smith"]

    def test_year_decades_populated(self, bib_smith_philosophy: BibItem) -> None:
        index = build_index((bib_smith_philosophy,))
        assert 2020 in index.year_decades
        assert bib_smith_philosophy in index.year_decades[2020]

    def test_journal_index_populated(self, bib_smith_philosophy: BibItem) -> None:
        index = build_index((bib_smith_philosophy,))
        assert len(index.journals) > 0

    def test_empty_bibliography(self) -> None:
        index = build_index(())
        assert len(index.all_items) == 0
        assert len(index.doi_index) == 0


# ============================================================================
# _get_candidate_set tests
# ============================================================================


class TestGetCandidateSet:
    def test_doi_returns_single_match(
        self,
        sample_bibliography: Tuple[BibItem, ...],
        subject_exact_match: BibItem,
        bib_smith_philosophy: BibItem,
    ) -> None:
        index = build_index(sample_bibliography)
        candidates = _get_candidate_set(subject_exact_match, index)
        assert len(candidates) == 1
        assert bib_smith_philosophy in candidates

    def test_no_doi_returns_multiple_candidates(
        self,
        sample_bibliography: Tuple[BibItem, ...],
        subject_close_match: BibItem,
    ) -> None:
        index = build_index(sample_bibliography)
        candidates = _get_candidate_set(subject_close_match, index)
        # Should find candidates via trigrams/author/decade
        assert len(candidates) >= 1

    def test_unknown_item_falls_back_to_all(self) -> None:
        bib = (
            default_bib_item(
                bibkey={"first_author": "X", "date": 2020},
                title={"simplified": "AAA BBB CCC"},
                entry_type="article",
                date={"year": 2020},
                author=({"family_name": {"simplified": "X"}},),
            ),
        )
        index = build_index(bib)

        # A completely unrelated subject
        subject = default_bib_item(
            bibkey={"first_author": "Z", "date": 1800},
            title={"simplified": "ZZZ YYY WWW"},
            entry_type="article",
            date={"year": 1800},
            author=({"family_name": {"simplified": "Z"}},),
        )
        candidates = _get_candidate_set(subject, index)
        # With no overlapping indexes, should fall back to all items
        assert len(candidates) >= 1


# ============================================================================
# find_similar_bibitems tests
# ============================================================================


class TestFindSimilarBibitems:
    def test_returns_sorted_matches(
        self,
        sample_bibliography: Tuple[BibItem, ...],
        subject_close_match: BibItem,
    ) -> None:
        index = build_index(sample_bibliography)
        matches = find_similar_bibitems(subject_close_match, index, top_n=3)
        assert all(isinstance(m, Match) for m in matches)
        # Verify descending order
        for i in range(len(matches) - 1):
            assert matches[i].total_score >= matches[i + 1].total_score

    def test_top_n_limits_results(
        self,
        sample_bibliography: Tuple[BibItem, ...],
        subject_close_match: BibItem,
    ) -> None:
        index = build_index(sample_bibliography)
        matches = find_similar_bibitems(subject_close_match, index, top_n=1)
        assert len(matches) <= 1

    def test_min_score_filters(
        self,
        sample_bibliography: Tuple[BibItem, ...],
        subject_close_match: BibItem,
    ) -> None:
        index = build_index(sample_bibliography)
        # Very high min_score should filter most results
        matches = find_similar_bibitems(subject_close_match, index, min_score=9999.0)
        assert len(matches) == 0

    def test_ranks_are_sequential(
        self,
        sample_bibliography: Tuple[BibItem, ...],
        subject_close_match: BibItem,
    ) -> None:
        index = build_index(sample_bibliography)
        matches = find_similar_bibitems(subject_close_match, index, top_n=3)
        for i, match in enumerate(matches, start=1):
            assert match.rank == i

    def test_custom_weights(
        self,
        sample_bibliography: Tuple[BibItem, ...],
        subject_close_match: BibItem,
    ) -> None:
        index = build_index(sample_bibliography)
        # All weight on title
        weights: FuzzyMatchWeights = {"title": 1.0, "author": 0.0, "date": 0.0, "bonus": 0.0}
        matches = find_similar_bibitems(subject_close_match, index, top_n=3, weights=weights)
        # Should still work and return results
        assert len(matches) >= 1


# ============================================================================
# stage_bibitem tests
# ============================================================================


class TestStageBibitem:
    def test_returns_staged_item(
        self,
        sample_bibliography: Tuple[BibItem, ...],
        subject_close_match: BibItem,
    ) -> None:
        index = build_index(sample_bibliography)
        staged = stage_bibitem(subject_close_match, index)
        assert isinstance(staged, BibItemStaged)
        assert staged.bibitem is subject_close_match

    def test_has_search_metadata(
        self,
        sample_bibliography: Tuple[BibItem, ...],
        subject_close_match: BibItem,
    ) -> None:
        index = build_index(sample_bibliography)
        staged = stage_bibitem(subject_close_match, index)
        assert "search_time_ms" in staged.search_metadata
        assert "candidates_searched" in staged.search_metadata
        assert staged.search_metadata["candidates_searched"] >= 1

    def test_has_top_matches(
        self,
        sample_bibliography: Tuple[BibItem, ...],
        subject_close_match: BibItem,
    ) -> None:
        index = build_index(sample_bibliography)
        staged = stage_bibitem(subject_close_match, index, top_n=2)
        assert len(staged.top_matches) <= 2
        assert all(isinstance(m, Match) for m in staged.top_matches)


# ============================================================================
# stage_bibitems_batch tests (Python path)
# ============================================================================


class TestStageBibitemsBatch:
    def test_batch_returns_correct_count(
        self,
        sample_bibliography: Tuple[BibItem, ...],
        subject_close_match: BibItem,
        subject_partial_match: BibItem,
    ) -> None:
        index = build_index(sample_bibliography)
        subjects = (subject_close_match, subject_partial_match)
        staged = stage_bibitems_batch(subjects, index, top_n=2, use_rust=False)
        assert len(staged) == 2

    def test_batch_python_results(
        self,
        sample_bibliography: Tuple[BibItem, ...],
        subject_close_match: BibItem,
    ) -> None:
        index = build_index(sample_bibliography)
        staged = stage_bibitems_batch((subject_close_match,), index, top_n=3, use_rust=False)
        assert len(staged) == 1
        assert isinstance(staged[0], BibItemStaged)
        assert len(staged[0].top_matches) <= 3

    def test_batch_with_custom_weights(
        self,
        sample_bibliography: Tuple[BibItem, ...],
        subject_close_match: BibItem,
    ) -> None:
        index = build_index(sample_bibliography)
        weights: FuzzyMatchWeights = {"title": 0.7, "author": 0.1, "date": 0.1, "bonus": 0.1}
        staged = stage_bibitems_batch((subject_close_match,), index, top_n=2, use_rust=False, weights=weights)
        assert len(staged) == 1
