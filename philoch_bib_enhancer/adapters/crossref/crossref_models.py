from typing import Dict, List
from pydantic import BaseModel, HttpUrl, Field


class CrossrefDateTime(BaseModel):
    date_parts: List[List[int]] = Field(..., alias="date-parts")
    date_time: str = Field(..., alias="date-time")
    timestamp: int


class CrossrefDateParts(BaseModel):
    date_parts: List[List[int]] = Field(..., alias="date-parts")


class CrossrefAuthor(BaseModel):
    given: str
    family: str
    sequence: str
    affiliation: List[Dict[str, str]]


class CrossrefLink(BaseModel):
    URL: str
    content_type: str = Field(..., alias="content-type")
    content_version: str = Field(..., alias="content-version")
    intended_application: str = Field(..., alias="intended-application")


class CrossrefISSNType(BaseModel):
    value: str
    type: str


class CrossrefArticle(BaseModel):
    indexed: CrossrefDateTime | None = None
    publisher: str | None = None
    issue: str | None = None
    short_container_title: List[str] | None = Field(None, alias="short-container-title")
    published_print: CrossrefDateParts | None = Field(None, alias="published-print")
    DOI: str | None = None
    type: str | None = None
    created: CrossrefDateTime | None = None
    page: str | None = None
    source: str | None = None
    title: List[str] | None = None
    prefix: str | None = None
    volume: str | None = None
    author: List[CrossrefAuthor] | None = None
    published_online: CrossrefDateParts | None = Field(None, alias="published-online")
    container_title: List[str] | None = Field(None, alias="container-title")
    language: str | None = None
    link: List[CrossrefLink] | None = None
    deposited: CrossrefDateTime | None = None
    issued: CrossrefDateParts | None = None
    references_count: int | None = Field(None, alias="references-count")
    alternative_id: List[str] | None = Field(None, alias="alternative-id")
    URL: str | None = None
    ISSN: List[str] | None = None
    issn_type: List[CrossrefISSNType] | None = Field(None, alias="issn-type")
    published: CrossrefDateParts | None = None
