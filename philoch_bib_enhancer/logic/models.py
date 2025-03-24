from __future__ import annotations
from typing import List, Tuple
import attrs

from philoch_bib_enhancer.logic.enums import BibInfoSourceEnum, BibTeXEntryTypeEnum, EpochEnum, LanguageIDEnum


############
# Author
############


@attrs.define(frozen=True, slots=True)
class Author:
    """
    An author of a publication.

    Args:
        given_name: str
        family_name: str
    """

    given_name: str
    family_name: str | None = None
    publications: List[BibItem] | None = None


############
# Journal
############


@attrs.define(frozen=True, slots=True)
class Journal:
    """
    A journal that publishes publications.

    Args:
        name: str
        issn_print: str | None = None
        issn_electronic: str | None = None
    """

    name: str
    issn_print: str | None = None
    issn_electronic: str | None = None


############
# Publisher
############


@attrs.define(frozen=True, slots=True)
class Publisher:
    """
    A publisher of publications.

    Args:
        name: str
    """

    name: str


############
# Note
############


@attrs.define(frozen=True, slots=True)
class Notes:
    """
    Notes (metadata) about a publication.

    Args:
        general: str | None = None
        perso: str | None = None
        status: str | None = None
        stock: str | None = None
        kw: str
    """

    general: str | None = None
    perso: str | None = None
    status: str | None = None
    stock: str | None = None
    kw: str | None = None


############
# BibItem
############


@attrs.define(frozen=True, slots=True)
class BibItem:
    """
    Bibliographic item type. All attributes are optional.

    Args:
        address: str
        authors: List[Author]
        bib_info_source: BibInfoSourceEnum
        bibkey: str
        bibtype: BibTeXEntryTypeEnum
        blumbib_version: int
        contained_in: BibItem
        chapter: int
        crossref_bibkey: str
        dltc_num: int
        doi: str
        edition: str
        editors: List[Author]
        eid: str
        epoch: EpochEnum
        institution: str
        journal: Journal
        keywords: Tuple[str, ...]
        lang_der: str  # TODO: what is this?
        lang_id: LanguageIDEnum
        notes: Notes
        num_coll: int
        num_inwork: str
        num_sort: int
        number: str
        organization: str
        pages: str
        person: Author
        publisher: Publisher
        pubstate: str
        school: str
        series: str
        spec_interest: str
        title: str
        type: str
        volume: str
        url: str
        forthcoming: bool
        day: int
        month: int
        year: int
    """

    address: str | None = None
    authors: List[Author] | None = None
    bib_info_source: BibInfoSourceEnum | None = None
    bibkey: str | None = None
    bibtype: BibTeXEntryTypeEnum | None = None
    blumbib_version: int | None = None
    contained_in: BibItem | None = None
    chapter: int | None = None
    crossref_bibkey: str | None = None
    dltc_num: int | None = None
    doi: str | None = None
    edition: str | None = None
    editors: List[Author] | None = None
    eid: str | None = None
    epoch: EpochEnum | None = None
    institution: str | None = None
    journal: Journal | None = None
    keywords: Tuple[str, ...] | None = None
    lang_der: str | None = None
    lang_id: LanguageIDEnum | None = None
    notes: Notes | None = None
    num_coll: int | None = None
    num_inwork: str | None = None
    num_sort: int | None = None
    number: str | None = None
    organization: str | None = None
    pages: str | None = None
    person: Author | None = None
    publisher: Publisher | None = None
    pubstate: str | None = None
    school: str | None = None
    series: str | None = None
    spec_interest: str | None = None
    title: str | None = None
    type: str | None = None
    volume: str | None = None
    url: str | None = None
    forthcoming: bool | None = None
    day: int | None = None
    month: int | None = None
    year: int | None = None
