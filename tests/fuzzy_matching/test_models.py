"""Tests for fuzzy matching data models."""

import json

import attrs
import pytest

from philoch_bib_sdk.logic.default_models import default_bib_item

from philoch_bib_enhancer.fuzzy_matching.models import (
    DEFAULT_FUZZY_MATCH_WEIGHTS,
    BibItemStaged,
    FuzzyMatchWeights,
    Match,
    PartialScore,
    ScoreComponent,
    SearchMetadata,
    weights_to_tuple,
)


# ============================================================================
# FuzzyMatchWeights tests
# ============================================================================


class TestFuzzyMatchWeights:
    def test_default_weights_sum_to_one(self) -> None:
        total = sum(weights_to_tuple(DEFAULT_FUZZY_MATCH_WEIGHTS))
        assert abs(total - 1.0) < 0.001

    def test_weights_to_tuple_order(self) -> None:
        weights: FuzzyMatchWeights = {"title": 0.5, "author": 0.3, "date": 0.1, "bonus": 0.1}
        result = weights_to_tuple(weights)
        assert result == (0.5, 0.3, 0.1, 0.1)

    def test_weights_to_tuple_custom(self) -> None:
        weights: FuzzyMatchWeights = {"title": 0.25, "author": 0.25, "date": 0.25, "bonus": 0.25}
        result = weights_to_tuple(weights)
        assert result == (0.25, 0.25, 0.25, 0.25)


# ============================================================================
# ScoreComponent tests
# ============================================================================


class TestScoreComponent:
    def test_enum_values(self) -> None:
        assert ScoreComponent.TITLE.value == "title"
        assert ScoreComponent.AUTHOR.value == "author"
        assert ScoreComponent.DATE.value == "date"
        assert ScoreComponent.DOI.value == "doi"
        assert ScoreComponent.JOURNAL_VOLUME_NUMBER.value == "journal_volume_number"
        assert ScoreComponent.PAGES.value == "pages"
        assert ScoreComponent.PUBLISHER.value == "publisher"

    def test_is_str_enum(self) -> None:
        assert isinstance(ScoreComponent.TITLE, str)


# ============================================================================
# PartialScore tests
# ============================================================================


class TestPartialScore:
    def test_creation(self) -> None:
        ps = PartialScore(
            component=ScoreComponent.TITLE,
            score=95,
            weight=0.5,
            weighted_score=47.5,
            details="Fuzzy: 95",
        )
        assert ps.component == ScoreComponent.TITLE
        assert ps.score == 95
        assert ps.weight == 0.5
        assert ps.weighted_score == 47.5
        assert ps.details == "Fuzzy: 95"

    def test_frozen(self) -> None:
        ps = PartialScore(
            component=ScoreComponent.TITLE,
            score=95,
            weight=0.5,
            weighted_score=47.5,
            details="Fuzzy: 95",
        )
        with pytest.raises(attrs.exceptions.FrozenInstanceError):
            ps.score = 50  # type: ignore[misc]


# ============================================================================
# Match tests
# ============================================================================


class TestMatch:
    @pytest.fixture
    def sample_match(self) -> Match:
        bibitem = default_bib_item(
            bibkey={"first_author": "Smith", "date": 2024},
            title={"latex": "Introduction to Philosophy", "simplified": "Introduction to Philosophy"},
            author=({"given_name": {"simplified": "John"}, "family_name": {"simplified": "Smith"}},),
            date={"year": 2024},
            entry_type="article",
        )
        return Match(
            bibkey="Smith2024",
            matched_bibitem=bibitem,
            total_score=85.5,
            partial_scores=(
                PartialScore(
                    component=ScoreComponent.TITLE,
                    score=190,
                    weight=0.5,
                    weighted_score=95.0,
                    details="Fuzzy: 100; High similarity bonus: +100",
                ),
                PartialScore(
                    component=ScoreComponent.AUTHOR, score=100, weight=0.3, weighted_score=30.0, details="Fuzzy: 100"
                ),
                PartialScore(
                    component=ScoreComponent.DATE,
                    score=100,
                    weight=0.1,
                    weighted_score=10.0,
                    details="Exact year match: 2024",
                ),
                PartialScore(
                    component=ScoreComponent.PUBLISHER,
                    score=0,
                    weight=0.1,
                    weighted_score=0.0,
                    details="No bonus matches",
                ),
            ),
            rank=1,
        )

    def test_frozen(self, sample_match: Match) -> None:
        with pytest.raises(attrs.exceptions.FrozenInstanceError):
            sample_match.rank = 2  # type: ignore[misc]

    def test_to_json_summary_keys(self, sample_match: Match) -> None:
        summary = sample_match.to_json_summary()
        assert "bibkey" in summary
        assert "rank" in summary
        assert "total_score" in summary
        assert "title" in summary
        assert "author" in summary
        assert "score_breakdown" in summary

    def test_to_json_summary_values(self, sample_match: Match) -> None:
        summary = sample_match.to_json_summary()
        assert summary["bibkey"] == "Smith2024"
        assert summary["rank"] == 1

    def test_to_json_summary_serializable(self, sample_match: Match) -> None:
        summary = sample_match.to_json_summary()
        # Should be JSON-serializable
        json_str = json.dumps(summary)
        assert isinstance(json_str, str)


# ============================================================================
# BibItemStaged tests
# ============================================================================


class TestBibItemStaged:
    @pytest.fixture
    def sample_staged(self) -> BibItemStaged:
        bibitem = default_bib_item(
            bibkey={"first_author": "Doe", "date": 2023},
            title={"latex": "Ethics", "simplified": "Ethics"},
            author=({"given_name": {"simplified": "Jane"}, "family_name": {"simplified": "Doe"}},),
            date={"year": 2023},
            entry_type="article",
        )
        match = Match(
            bibkey="Doe2023",
            matched_bibitem=bibitem,
            total_score=95.0,
            partial_scores=(
                PartialScore(component=ScoreComponent.TITLE, score=190, weight=0.5, weighted_score=95.0, details="d"),
                PartialScore(component=ScoreComponent.AUTHOR, score=190, weight=0.3, weighted_score=57.0, details="d"),
                PartialScore(component=ScoreComponent.DATE, score=100, weight=0.1, weighted_score=10.0, details="d"),
                PartialScore(component=ScoreComponent.PUBLISHER, score=0, weight=0.1, weighted_score=0.0, details="d"),
            ),
            rank=1,
        )
        metadata: SearchMetadata = {"search_time_ms": 42, "candidates_searched": 100}
        return BibItemStaged(bibitem=bibitem, top_matches=(match,), search_metadata=metadata)

    def test_frozen(self, sample_staged: BibItemStaged) -> None:
        with pytest.raises(attrs.exceptions.FrozenInstanceError):
            sample_staged.bibitem = sample_staged.bibitem  # type: ignore[misc]

    def test_to_csv_row_keys(self, sample_staged: BibItemStaged) -> None:
        row = sample_staged.to_csv_row()
        assert "staged_bibkey" in row
        assert "staged_title" in row
        assert "staged_author" in row
        assert "staged_year" in row
        assert "num_matches" in row
        assert "best_match_score" in row
        assert "best_match_bibkey" in row
        assert "top_matches_json" in row
        assert "search_time_ms" in row
        assert "candidates_searched" in row

    def test_to_csv_row_values(self, sample_staged: BibItemStaged) -> None:
        row = sample_staged.to_csv_row()
        assert row["num_matches"] == 1
        assert row["best_match_bibkey"] == "Doe2023"
        assert row["search_time_ms"] == 42
        assert row["candidates_searched"] == 100

    def test_to_csv_row_json_parseable(self, sample_staged: BibItemStaged) -> None:
        row = sample_staged.to_csv_row()
        matches_json = row["top_matches_json"]
        assert isinstance(matches_json, str)
        parsed = json.loads(matches_json)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
