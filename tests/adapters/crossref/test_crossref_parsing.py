from typing import Any, List, Tuple

from philoch_bib_enhancer.adapters.crossref.crossref_converter import _convert_crossref_article_to_bibitem
from philoch_bib_enhancer.adapters.crossref.crossref_models import CrossrefArticle


def test_crossref_article_model_validation(raw_crossref_articles: List[dict[Any, Any]]) -> None:

    try:
        raw_articles = raw_crossref_articles
        for raw_article in raw_articles:
            CrossrefArticle.model_validate(raw_article)

    except Exception as e:
        assert False, f"Exception: {e}"


def test_crossref_article_conversion(raw_crossref_articles: List[dict[Any, Any]]) -> None:

    raw_articles = raw_crossref_articles

    for raw_article in raw_articles:
        cr_article = CrossrefArticle(**raw_article)
        bib_item = _convert_crossref_article_to_bibitem(cr_article)
        assert bib_item is not None, "BibItem conversion failed"


def test_crossref_article_conversion_to_bibitem(raw_crossref_article: Tuple[List[str], Any]) -> None:

    correct_title, raw_article = raw_crossref_article

    cr_article = CrossrefArticle(**raw_article)

    assert (
        cr_article.title == correct_title
    ), f"Title does not match expected value. Expected: {correct_title}, Got: {cr_article.title}"
    assert cr_article.publisher != "", "Publisher should not be empty"
    assert cr_article.DOI != "", "DOI should not be empty"
    assert cr_article.author != [], "Author list should not be empty"
