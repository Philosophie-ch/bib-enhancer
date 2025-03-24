from tests.adapters.crossref.example_journals_response import EXAMPLE_JOURNALS_RESPONSE
from bib_enhancer.adapters.crossref.crossref_models import CrossrefArticle


def test_crossref_article_model_validation() -> None:

    try:
        raw_articles = EXAMPLE_JOURNALS_RESPONSE['message']['items']  # type: ignore
        for raw_article in raw_articles:
            CrossrefArticle.model_validate(raw_article)

    except Exception as e:
        assert False, f"Exception: {e}"
