from typing import Literal, Tuple
from philoch_bib_sdk.logic.models import (
    BibItem,
    BibItemDateAttr,
    PageAttr,
)
from philoch_bib_sdk.logic.default_models import (
    default_author,
    default_bib_string,
    default_journal,
)

from philoch_bib_enhancer.adapters.crossref.crossref_models import CrossrefArticle


def _convert_crossref_article_to_bibitem(crossref_article: CrossrefArticle) -> BibItem:
    """
    Convert a CrossrefArticle object into a BibItem instance.

    Raises:
        ValueError: If required Crossref fields are missing or invalid.
    """

    # Authors
    authors = (
        tuple(
            default_author(given_name={"latex": a.given}, family_name={"latex": a.family})
            for a in crossref_article.author
        )
        if crossref_article.author
        else tuple()
    )

    # Title
    title = default_bib_string(latex=" ".join(crossref_article.title) if crossref_article.title else "")

    # Date
    date_parts: BibItemDateAttr | Literal["no date"] = "no date"

    if getattr(crossref_article, "issued", None) and getattr(crossref_article.issued, "date_parts", None):
        parts = (getattr(crossref_article.issued, "date_parts", None) or [[]])[0]
        if parts and parts[0]:
            try:
                date_parts = BibItemDateAttr(
                    year=parts[0],
                    # Ignore month and day
                )
            except Exception as e:
                raise ValueError(f"Invalid date parts for DOI {crossref_article.DOI}: {parts!r} ({e})")

    # Journal
    journal = None
    if (
        crossref_article.container_title
        and crossref_article.container_title != []
        and crossref_article.container_title[0]
    ):
        issn_print = ""
        issn_electronic = ""
        if crossref_article.ISSN:
            for i, issn in enumerate(crossref_article.ISSN):
                if i == 0:
                    issn_print = issn
                elif i == 1:
                    issn_electronic = issn
        journal = default_journal(
            name={"latex": crossref_article.container_title[0]}, issn_print=issn_print, issn_electronic=issn_electronic
        )

    # Pages
    pages: Tuple[PageAttr, ...] = tuple()
    if crossref_article.page:
        if "-" in crossref_article.page:
            start, end = crossref_article.page.split("-", 1)
            pages = (PageAttr(start=start, end=end),)
        else:
            pages = (PageAttr(start=crossref_article.page, end=""),)

    return BibItem(
        to_do_general="",
        change_request="",
        entry_type="UNKNOWN",
        bibkey="",
        author=authors,
        editor=(),
        options=(),
        date=date_parts,
        pubstate="",
        title=title,
        booktitle="",
        crossref="",
        journal=journal,
        volume=crossref_article.volume or "",
        number=crossref_article.issue or "",
        pages=pages,
        eid="",
        series="",
        address="",
        institution="",
        school="",
        publisher=default_bib_string(latex=crossref_article.publisher) if crossref_article.publisher else "",
        type="",
        edition=None,
        note="",
        issuetitle="",
        guesteditor=(),
        extra_note="",
        urn="",
        eprint="",
        doi=crossref_article.DOI if crossref_article.DOI else "",
        url=crossref_article.URL or "",
        kws="",
        epoch="",
        person="",
        comm_for_profile_bib="",
        langid="",
        lang_der="",
        further_refs=(),
        depends_on=(),
        dltc_num=None,
        spec_interest="",
        note_perso="",
        note_stock="",
        note_status="",
        num_inwork_coll=None,
        num_inwork="",
        num_coll=None,
        dltc_copyediting_note="",
        note_missing="",
        num_sort=None,
        id=None,
        bib_info_source="crossref",
    )
