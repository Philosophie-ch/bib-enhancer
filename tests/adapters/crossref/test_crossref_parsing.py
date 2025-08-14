from typing import Any, List
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
