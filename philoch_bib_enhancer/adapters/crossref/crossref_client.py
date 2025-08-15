import logging
from time import sleep
from typing import Any
from habanero import Crossref


class CrossrefClient:
    def __init__(
        self,
        email: str,
    ) -> None:
        self._email = email
        self.logger = logging.getLogger(self.__class__.__name__)
        self._client = self._get_client()

        is_up = self.ping()
        if not is_up:
            raise ConnectionError(
                "Could not connect to Crossref API. Please check your internet connection or the API status."
            )

    @property
    def email(self) -> str:
        return self._email

    @property
    def raw_client(self) -> Crossref:
        return self._client

    def _get_client(self) -> Crossref:
        client = Crossref(
            mailto=self.email,
        )
        return client

    def ping(self) -> bool:
        """
        Check if Crossref is up and running.
        """
        try:
            res = self.raw_client.works(query="*", limit=1)
            if not isinstance(res, dict):
                raise ValueError(f"Unexpected response type from Crossref: {type(res)}. Expected dict.")
            return True

        except Exception as e:
            self.logger.error(f"Could not ping Crossref. {e.__class__.__name__}: {e}")
            return False

    def journal_name_by_issn(self, issn: str) -> str:
        """
        Get the name of a journal by its ISSN.
        """
        response: dict[Any, Any] = self.raw_client.journals(ids=issn)
        journal_name = response["message"]["title"]

        if not isinstance(journal_name, str):
            raise ValueError(f"Could not find journal name for ISSN {issn}. Response: {response}")

        return journal_name

    def journal_articles_by_issn_year(self, issn: str, year: int) -> dict[Any, Any]:
        """
        Get the articles of a journal by its ISSN and a year.
        """
        response: dict[Any, Any] = self.raw_client.journals(
            ids=issn,
            works=True,
            filter={
                "from-pub-date": f"{year}-01-01",
                "until-pub-date": f"{year}-12-31",
            },
            limit=1000,
        )

        sleep(0.1)

        return response
