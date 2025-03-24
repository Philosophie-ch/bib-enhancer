from typing import Any, List
from philoch_bib_enhancer.adapters.crossref.crossref_models import CrossrefArticle


def test_crossref_article_model_validation(raw_crossref_articles: List[dict[Any, Any]]) -> None:

    try:
        raw_articles = raw_crossref_articles
        for raw_article in raw_articles:
            CrossrefArticle.model_validate(raw_article)

    except Exception as e:
        assert False, f"Exception: {e}"
