import pytest
from bib_enhancer.adapters.crossref.crossref_client import CrossrefClient


@pytest.mark.external
def test_ping_crossref_api(crossref_client: CrossrefClient) -> None:

    assert crossref_client.ping() is True
