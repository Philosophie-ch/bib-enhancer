from typing import Dict, List, TypeGuard, TypedDict
from typing_extensions import Literal
from pydantic import BaseModel, Field


class CrossrefDateTime(BaseModel):
    date_parts: List[List[int]] = Field([], alias="date-parts")
    date_time: str = Field("", alias="date-time")
    timestamp: int | None = None


class CrossrefDateParts(BaseModel):
    date_parts: List[List[int]] = Field([], alias="date-parts")


class CrossrefAuthor(BaseModel):
    given: str = ""
    family: str = ""
    sequence: str = ""
    affiliation: List[Dict[str, str]] = []


class CrossrefLink(BaseModel):
    URL: str = ""
    content_type: str = Field("", alias="content-type")
    content_version: str = Field("", alias="content-version")
    intended_application: str = Field("", alias="intended-application")


class CrossrefISSNType(BaseModel):
    value: str = ""
    type: str = ""


class CrossrefArticle(BaseModel):
    indexed: CrossrefDateTime | None = None
    publisher: str = ""
    issue: str = ""
    short_container_title: List[str] = Field([], alias="short-container-title")
    published_print: CrossrefDateParts | None = Field(None, alias="published-print")
    DOI: str = ""
    type: str = ""
    created: CrossrefDateTime | None = None
    page: str = ""
    source: str = ""
    title: List[str] = []
    prefix: str = ""
    volume: str = ""
    author: List[CrossrefAuthor] = []
    published_online: CrossrefDateParts | None = Field(None, alias="published-online")
    container_title: List[str] = Field([], alias="container-title")
    language: str = ""
    link: List[CrossrefLink] = []
    deposited: CrossrefDateTime | None = None
    issued: CrossrefDateParts | None = None
    references_count: int | None = Field(None, alias="references-count")
    alternative_id: List[str] = Field([], alias="alternative-id")
    URL: str = ""
    ISSN: List[str] = []
    issn_type: List[CrossrefISSNType] = Field([], alias="issn-type")
    published: CrossrefDateParts | None = None


class ParsingSuccess[T](TypedDict, total=True):
    """
    A parsed object with a result and a parsing status.
    """

    out: T
    parsing_status: Literal["success"]


class ParsingError(TypedDict, total=True):
    """
    An error that occurred during parsing.
    """

    parsing_status: Literal["error"]
    message: str
    context: str


type ParsedResult[T] = ParsingSuccess[T] | ParsingError


def is_parsing_success[T](result: ParsedResult[T]) -> TypeGuard[ParsingSuccess[T]]:
    return result.get("parsing_status") == "success"
