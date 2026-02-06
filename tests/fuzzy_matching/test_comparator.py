"""Tests for fuzzy matching comparator scoring functions."""

import pytest

from philoch_bib_sdk.logic.default_models import default_bib_item
from philoch_bib_sdk.logic.models import BibItem, BibItemDateAttr

from philoch_bib_enhancer.fuzzy_matching.comparator import (
    _score_author,
    _score_author_detailed,
    _score_bonus_fields,
    _score_date_detailed,
    _score_title,
    _score_title_detailed,
    _score_year,
    compare_bibitems_detailed,
)
from philoch_bib_enhancer.fuzzy_matching.models import (
    FuzzyMatchWeights,
    PartialScore,
    ScoreComponent,
)


# ============================================================================
# _score_title tests
# ============================================================================


class TestScoreTitle:
    def test_identical_titles_get_bonus(self) -> None:
        score = _score_title("Introduction to Philosophy", "Introduction to Philosophy")
        # fuzzy score of 100 > 85 → +100 bonus
        assert score > 100

    def test_similar_titles_above_threshold(self) -> None:
        score = _score_title("Introduction to Philosophy", "Intro to Philosophy")
        # Should be reasonably high but depends on fuzzy matcher
        assert score > 0

    def test_completely_different_titles(self) -> None:
        score = _score_title("Introduction to Philosophy", "Quantum Mechanics and Relativity")
        assert score < 100  # No bonus

    def test_one_contains_other_triggers_bonus(self) -> None:
        score = _score_title("Ethics", "Ethics and Morality in Modern Society")
        # "Ethics" is contained in the longer title → bonus
        assert score > 100

    def test_errata_mismatch_penalty(self) -> None:
        score_normal = _score_title("Introduction to Philosophy", "Introduction to Philosophy")
        score_errata = _score_title("Errata for Introduction to Philosophy", "Introduction to Philosophy")
        # Errata mismatch should penalize
        assert score_errata < score_normal

    def test_review_mismatch_penalty(self) -> None:
        score_normal = _score_title("Ethics and Morality", "Ethics and Morality")
        score_review = _score_title("A Review of Ethics and Morality", "Ethics and Morality")
        assert score_review < score_normal

    def test_both_have_errata_no_penalty(self) -> None:
        """If both titles contain 'errata', symmetric difference is empty → no penalty."""
        score = _score_title(
            "Errata for Introduction to Philosophy",
            "Errata for Introduction to Philosophy",
        )
        # Identical titles with same keywords → should get bonus
        assert score > 100

    def test_empty_title_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            _score_title("", "Some Title")

    def test_empty_second_title_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            _score_title("Some Title", "")


# ============================================================================
# _score_author tests
# ============================================================================


class TestScoreAuthor:
    def test_identical_authors_get_bonus(self) -> None:
        score = _score_author("Smith, John", "Smith, John")
        assert score > 100  # 100 from fuzzy + 100 bonus

    def test_similar_authors(self) -> None:
        score = _score_author("Smith, John", "Smith, J.")
        assert score > 0

    def test_different_authors(self) -> None:
        score = _score_author("Smith, John", "Doe, Jane")
        assert score < 100  # No bonus

    def test_empty_author_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            _score_author("", "Smith, John")


# ============================================================================
# _score_year tests
# ============================================================================


class TestScoreYear:
    def test_exact_match(self) -> None:
        assert _score_year(2024, 2024) == 100

    def test_within_range(self) -> None:
        assert _score_year(2024, 2025) == 100
        assert _score_year(2024, 2023) == 100

    def test_outside_range(self) -> None:
        assert _score_year(2024, 2020) == 0

    def test_custom_range(self) -> None:
        assert _score_year(2024, 2022, range_offset=2) == 100
        assert _score_year(2024, 2021, range_offset=2) == 0


# ============================================================================
# _score_title_detailed tests
# ============================================================================


class TestScoreTitleDetailed:
    def test_default_weight(self) -> None:
        result = _score_title_detailed("Introduction to Philosophy", "Introduction to Philosophy")
        assert isinstance(result, PartialScore)
        assert result.component == ScoreComponent.TITLE
        assert result.weight == 0.5
        # score > 100 (fuzzy 100 + bonus 100), weighted = score * 0.5
        assert result.weighted_score == result.score * 0.5

    def test_custom_weight(self) -> None:
        result = _score_title_detailed("Introduction to Philosophy", "Introduction to Philosophy", weight=0.8)
        assert result.weight == 0.8
        assert result.weighted_score == result.score * 0.8

    def test_empty_titles(self) -> None:
        result = _score_title_detailed("", "Some Title")
        assert result.score == 0
        assert result.weighted_score == 0.0
        assert "Empty title" in result.details

    def test_bonus_appears_in_details(self) -> None:
        result = _score_title_detailed("Introduction to Philosophy", "Introduction to Philosophy")
        assert "bonus" in result.details.lower() or "Fuzzy" in result.details

    def test_keyword_mismatch_appears_in_details(self) -> None:
        result = _score_title_detailed("Errata for Philosophy", "Philosophy")
        assert "mismatch" in result.details.lower() or result.score < 200


# ============================================================================
# _score_author_detailed tests
# ============================================================================


class TestScoreAuthorDetailed:
    def test_default_weight(self) -> None:
        result = _score_author_detailed("Smith, John", "Smith, John")
        assert result.component == ScoreComponent.AUTHOR
        assert result.weight == 0.3
        assert result.weighted_score == result.score * 0.3

    def test_custom_weight(self) -> None:
        result = _score_author_detailed("Smith, John", "Smith, John", weight=0.6)
        assert result.weight == 0.6
        assert result.weighted_score == result.score * 0.6

    def test_empty_authors(self) -> None:
        result = _score_author_detailed("", "Smith, John")
        assert result.score == 0
        assert "Empty author" in result.details


# ============================================================================
# _score_date_detailed tests
# ============================================================================


class TestScoreDateDetailed:
    def test_exact_year_match(self) -> None:
        date1 = BibItemDateAttr(year=2024)
        date2 = BibItemDateAttr(year=2024)
        result = _score_date_detailed(date1, date2)
        assert result.score == 100
        assert result.component == ScoreComponent.DATE
        assert "Exact year" in result.details

    def test_one_year_diff(self) -> None:
        date1 = BibItemDateAttr(year=2024)
        date2 = BibItemDateAttr(year=2025)
        result = _score_date_detailed(date1, date2)
        assert result.score == 95  # wider tolerance for CrossRef date discrepancies

    def test_two_year_diff(self) -> None:
        date1 = BibItemDateAttr(year=2024)
        date2 = BibItemDateAttr(year=2022)
        result = _score_date_detailed(date1, date2)
        assert result.score == 90

    def test_three_year_diff(self) -> None:
        date1 = BibItemDateAttr(year=2024)
        date2 = BibItemDateAttr(year=2021)
        result = _score_date_detailed(date1, date2)
        assert result.score == 85

    def test_four_year_diff(self) -> None:
        date1 = BibItemDateAttr(year=2024)
        date2 = BibItemDateAttr(year=2020)
        result = _score_date_detailed(date1, date2)
        assert result.score == 75

    def test_five_year_diff(self) -> None:
        date1 = BibItemDateAttr(year=2024)
        date2 = BibItemDateAttr(year=2019)
        result = _score_date_detailed(date1, date2)
        assert result.score == 65

    def test_same_decade(self) -> None:
        date1 = BibItemDateAttr(year=2020)
        date2 = BibItemDateAttr(year=2028)
        result = _score_date_detailed(date1, date2)
        assert result.score == 40
        assert "decade" in result.details.lower()

    def test_different_decades(self) -> None:
        date1 = BibItemDateAttr(year=2024)
        date2 = BibItemDateAttr(year=1990)
        result = _score_date_detailed(date1, date2)
        assert result.score == 0

    def test_no_date(self) -> None:
        result = _score_date_detailed("no date", BibItemDateAttr(year=2024))
        assert result.score == 0
        assert "Missing date" in result.details

    def test_both_no_date(self) -> None:
        result = _score_date_detailed("no date", "no date")
        assert result.score == 0

    def test_custom_weight(self) -> None:
        date1 = BibItemDateAttr(year=2024)
        date2 = BibItemDateAttr(year=2024)
        result = _score_date_detailed(date1, date2, weight=0.2)
        assert result.weight == 0.2
        assert result.weighted_score == 100.0 * 0.2


# ============================================================================
# _score_bonus_fields tests
# ============================================================================


class TestScoreBonusFields:
    def test_doi_exact_match(self, bib_smith_philosophy: BibItem) -> None:
        subject = default_bib_item(
            bibkey={"first_author": "X", "date": 2024},
            title={"latex": "Anything"},
            entry_type="article",
            doi="10.1234/phil.2024.001",
        )
        result = _score_bonus_fields(bib_smith_philosophy, subject)
        assert result.score >= 100
        assert "DOI" in result.details

    def test_journal_volume_number_match(self, bib_smith_philosophy: BibItem) -> None:
        subject = default_bib_item(
            bibkey={"first_author": "X", "date": 2024},
            title={"latex": "Anything"},
            entry_type="article",
            journal={"name": {"simplified": "Philosophy Today"}},
            volume="10",
            number="2",
        )
        result = _score_bonus_fields(bib_smith_philosophy, subject)
        assert result.score >= 50
        assert "Journal" in result.details or "Vol" in result.details

    def test_pages_match(self, bib_smith_philosophy: BibItem) -> None:
        subject = default_bib_item(
            bibkey={"first_author": "X", "date": 2024},
            title={"latex": "Anything"},
            entry_type="article",
            pages=({"start": "1", "end": "25"},),
        )
        result = _score_bonus_fields(bib_smith_philosophy, subject)
        assert result.score >= 20
        assert "Page" in result.details or "page" in result.details

    def test_publisher_match(self, bib_smith_philosophy: BibItem) -> None:
        subject = default_bib_item(
            bibkey={"first_author": "X", "date": 2024},
            title={"latex": "Anything"},
            entry_type="article",
            publisher={"simplified": "Academic Press"},
        )
        result = _score_bonus_fields(bib_smith_philosophy, subject)
        assert result.score >= 10
        assert "Publisher" in result.details or "publisher" in result.details

    def test_no_bonus_matches(self) -> None:
        ref = default_bib_item(bibkey={"first_author": "A", "date": 2024}, title={"latex": "T1"}, entry_type="misc")
        subj = default_bib_item(bibkey={"first_author": "B", "date": 2024}, title={"latex": "T2"}, entry_type="misc")
        result = _score_bonus_fields(ref, subj)
        assert result.score == 0
        assert "No bonus" in result.details

    def test_combined_bonuses(self, bib_smith_philosophy: BibItem) -> None:
        """Subject matching on DOI + pages + publisher should accumulate."""
        subject = default_bib_item(
            bibkey={"first_author": "X", "date": 2024},
            title={"latex": "Anything"},
            entry_type="article",
            doi="10.1234/phil.2024.001",
            pages=({"start": "1", "end": "25"},),
            publisher={"simplified": "Academic Press"},
        )
        result = _score_bonus_fields(bib_smith_philosophy, subject)
        # DOI(100) + Pages(20) + Publisher(10) = 130
        assert result.score >= 130


# ============================================================================
# compare_bibitems_detailed tests
# ============================================================================


class TestCompareBibitemsDetailed:
    def test_returns_four_partial_scores(self, bib_smith_philosophy: BibItem, subject_close_match: BibItem) -> None:
        result = compare_bibitems_detailed(bib_smith_philosophy, subject_close_match)
        assert len(result) == 4
        assert all(isinstance(ps, PartialScore) for ps in result)

    def test_component_order(self, bib_smith_philosophy: BibItem, subject_close_match: BibItem) -> None:
        result = compare_bibitems_detailed(bib_smith_philosophy, subject_close_match)
        assert result[0].component == ScoreComponent.TITLE
        assert result[1].component == ScoreComponent.AUTHOR
        assert result[2].component == ScoreComponent.DATE
        assert result[3].component == ScoreComponent.PUBLISHER  # bonus uses PUBLISHER

    def test_default_weights_applied(self, bib_smith_philosophy: BibItem, subject_close_match: BibItem) -> None:
        """Test that tuned default weights are applied (optimized for PhilStudies benchmark)."""
        result = compare_bibitems_detailed(bib_smith_philosophy, subject_close_match)
        assert result[0].weight == 0.4  # title (reduced from 0.5 - generic titles)
        assert result[1].weight == 0.3  # author
        assert result[2].weight == 0.05  # date (reduced from 0.1 - CrossRef discrepancies)
        assert result[3].weight == 0.25  # bonus (increased from 0.1 - DOI reliable)

    def test_custom_weights_applied(self, bib_smith_philosophy: BibItem, subject_close_match: BibItem) -> None:
        custom_weights: FuzzyMatchWeights = {
            "title": 0.4,
            "author": 0.4,
            "date": 0.1,
            "bonus": 0.1,
        }
        result = compare_bibitems_detailed(bib_smith_philosophy, subject_close_match, weights=custom_weights)
        assert result[0].weight == 0.4
        assert result[1].weight == 0.4

    def test_identical_items_high_total(self, bib_smith_philosophy: BibItem) -> None:
        result = compare_bibitems_detailed(bib_smith_philosophy, bib_smith_philosophy)
        total = sum(ps.weighted_score for ps in result)
        # Identical items should have a very high total score
        assert total > 50


# ============================================================================
# Weight behavior tests (verify weights actually change outcomes)
# ============================================================================


class TestWeightsBehavior:
    """Tests that different weight configurations produce meaningfully different results."""

    def test_total_score_changes_with_weights(
        self, bib_smith_philosophy: BibItem, subject_close_match: BibItem
    ) -> None:
        """Same pair compared under two different weight configs must yield different totals."""
        title_heavy: FuzzyMatchWeights = {"title": 0.9, "author": 0.05, "date": 0.025, "bonus": 0.025}
        author_heavy: FuzzyMatchWeights = {"title": 0.05, "author": 0.9, "date": 0.025, "bonus": 0.025}

        result_title = compare_bibitems_detailed(bib_smith_philosophy, subject_close_match, weights=title_heavy)
        result_author = compare_bibitems_detailed(bib_smith_philosophy, subject_close_match, weights=author_heavy)

        total_title = sum(ps.weighted_score for ps in result_title)
        total_author = sum(ps.weighted_score for ps in result_author)

        assert total_title != total_author

    def test_title_heavy_weights_favor_title_match(
        self,
        bib_title_strong: BibItem,
        bib_author_strong: BibItem,
        subject_close_match: BibItem,
    ) -> None:
        """With title-heavy weights, the item with a matching title should score higher."""
        title_heavy: FuzzyMatchWeights = {"title": 0.9, "author": 0.05, "date": 0.025, "bonus": 0.025}

        scores_title_strong = compare_bibitems_detailed(bib_title_strong, subject_close_match, weights=title_heavy)
        scores_author_strong = compare_bibitems_detailed(bib_author_strong, subject_close_match, weights=title_heavy)

        total_title_strong = sum(ps.weighted_score for ps in scores_title_strong)
        total_author_strong = sum(ps.weighted_score for ps in scores_author_strong)

        assert total_title_strong > total_author_strong

    def test_author_heavy_weights_favor_author_match(
        self,
        bib_title_strong: BibItem,
        bib_author_strong: BibItem,
        subject_close_match: BibItem,
    ) -> None:
        """With author-heavy weights, the item with a matching author should score higher."""
        author_heavy: FuzzyMatchWeights = {"title": 0.05, "author": 0.9, "date": 0.025, "bonus": 0.025}

        scores_title_strong = compare_bibitems_detailed(bib_title_strong, subject_close_match, weights=author_heavy)
        scores_author_strong = compare_bibitems_detailed(bib_author_strong, subject_close_match, weights=author_heavy)

        total_title_strong = sum(ps.weighted_score for ps in scores_title_strong)
        total_author_strong = sum(ps.weighted_score for ps in scores_author_strong)

        assert total_author_strong > total_title_strong


# ============================================================================
# Academic prefix gate tests
# ============================================================================


class TestAcademicPrefixGate:
    """Tests for the academic review/response prefix gate.

    The gate ensures that items like "Reply to X" cannot match "X" -
    one is a response to the other, not the same work.
    """

    def test_has_academic_prefix_reply_to(self) -> None:
        from philoch_bib_enhancer.fuzzy_matching.comparator import _has_academic_prefix

        assert _has_academic_prefix("Reply to Smith on Knowledge")
        assert _has_academic_prefix("reply to smith")  # case insensitive

    def test_has_academic_prefix_various_prefixes(self) -> None:
        from philoch_bib_enhancer.fuzzy_matching.comparator import _has_academic_prefix

        assert _has_academic_prefix("Comments on Smith's paper")
        assert _has_academic_prefix("Précis of my book")
        assert _has_academic_prefix("Review of Recent Philosophy")
        assert _has_academic_prefix("Critical Notice: A New Theory")
        assert _has_academic_prefix("Discussion of Davidson's Work")
        assert _has_academic_prefix("Response to critics")

    def test_has_academic_prefix_no_prefix(self) -> None:
        from philoch_bib_enhancer.fuzzy_matching.comparator import _has_academic_prefix

        assert not _has_academic_prefix("On the Nature of Knowledge")
        assert not _has_academic_prefix("Knowledge and Belief")
        assert not _has_academic_prefix("")

    def test_prefix_mismatch_yields_zero_scores(self) -> None:
        """If one title has prefix and other doesn't, all scores should be zero."""
        from philoch_bib_sdk.logic.default_models import default_bib_item

        original = default_bib_item(
            bibkey={"first_author": "Smith", "date": 2020},
            title={"simplified": "On Knowledge"},
            entry_type="article",
        )
        reply = default_bib_item(
            bibkey={"first_author": "Jones", "date": 2021},
            title={"simplified": "Reply to Smith on Knowledge"},
            entry_type="article",
        )

        result = compare_bibitems_detailed(original, reply)
        total = sum(ps.weighted_score for ps in result)

        assert total == 0.0
        assert "prefix mismatch" in result[0].details.lower()

    def test_both_have_prefix_normal_scoring(self) -> None:
        """If both titles have prefixes, normal scoring applies."""
        from philoch_bib_sdk.logic.default_models import default_bib_item

        reply1 = default_bib_item(
            bibkey={"first_author": "Jones", "date": 2021},
            title={"simplified": "Reply to Smith on Knowledge"},
            entry_type="article",
        )
        reply2 = default_bib_item(
            bibkey={"first_author": "Jones", "date": 2021},
            title={"simplified": "Reply to Smith on Knowledge"},  # identical
            entry_type="article",
        )

        result = compare_bibitems_detailed(reply1, reply2)
        total = sum(ps.weighted_score for ps in result)

        # Should have positive score since both are replies
        assert total > 0

    def test_neither_has_prefix_normal_scoring(self) -> None:
        """If neither title has prefix, normal scoring applies."""
        from philoch_bib_sdk.logic.default_models import default_bib_item

        item1 = default_bib_item(
            bibkey={"first_author": "Smith", "date": 2020},
            title={"simplified": "On Knowledge"},
            entry_type="article",
        )
        item2 = default_bib_item(
            bibkey={"first_author": "Smith", "date": 2020},
            title={"simplified": "On Knowledge"},
            entry_type="article",
        )

        result = compare_bibitems_detailed(item1, item2)
        total = sum(ps.weighted_score for ps in result)

        assert total > 0
