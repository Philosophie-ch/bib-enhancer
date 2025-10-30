from pydantic import BaseModel, Field
from typing import Optional


class RawTextAuthor(BaseModel):
    """Author extracted from raw text by LLM."""

    given: Optional[str] = None
    family: Optional[str] = None


class RawTextBibitem(BaseModel):
    """
    Intermediate model for bibliographic data extracted from raw text by LLM.
    Supports various publication types: articles, books, chapters, etc.
    All fields are optional to handle partial/incomplete data.
    """

    raw_text: Optional[str] = None  # The raw text identified as bibliographic data (with markup, etc.)
    type: Optional[str] = None  # e.g., "article", "book", "chapter", "inbook", "incollection"
    title: Optional[str] = None
    year: Optional[int] = None
    authors: Optional[list[RawTextAuthor]] = Field(default_factory=list)
    editors: Optional[list[RawTextAuthor]] = Field(default_factory=list)
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue_number: Optional[str] = None
    start_page: Optional[str] = None
    end_page: Optional[str] = None
    publisher: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
