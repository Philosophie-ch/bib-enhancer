import ast
import os

import pytest

from philoch_bib_enhancer.adapters.crossref.crossref_client import CrossrefClient
from tests.adapters.crossref.example_journals_response import EXAMPLE_JOURNALS_RESPONSE, EXAMPLE_ARTICLE_RESPONSE

from dotenv import load_dotenv


TEST_ENV_FILE = os.getenv("TEST_ENV_FILE", None)

if not TEST_ENV_FILE:
    raise ValueError(
        "TEST_ENV_FILE environment variable is not set. Please set it to the path of your test environment file."
    )

load_dotenv(
    dotenv_path=TEST_ENV_FILE,
)

CROSSREF_EMAIL = os.getenv("CROSSREF_EMAIL", "")

env_vars = [
    {"name": "CROSSREF_EMAIL", "value": CROSSREF_EMAIL},
]

if not all([var["value"] for var in env_vars]):
    raise ValueError(
        f"Missing environment variables. Please check your environment. Found the following environment variables: {env_vars}"
    )


@pytest.fixture
def crossref_client() -> CrossrefClient:
    return CrossrefClient(email=CROSSREF_EMAIL)


@pytest.fixture
def raw_crossref_articles() -> list[dict[str, object]]:
    return EXAMPLE_JOURNALS_RESPONSE['message']['items']  # type: ignore


@pytest.fixture
def raw_crossref_article() -> tuple[list[str], dict[str, object]]:
    correct_title = ['ÊTRE ET PENSÉE']
    raw = ast.literal_eval(EXAMPLE_ARTICLE_RESPONSE)
    return correct_title, raw
