# Plan: Dialectica HTML Bibliography Renderer

## Context

The Dialectica compilation machine (dltc-make/citeproc) produces HTML references as flat strings with no semantic markup. Post-processing for the philosophie.ch website (reformatting, linked data, cross-linking) requires structured access to author, year, title, journal, volume, pages, etc.

This project adds a **renderer module to `philoch-bib-sdk`** that takes `BibItem` objects and produces structured HTML with `data-field` attributes. It's a single-style renderer hardcoded to Dialectica's house style (Chicago author-date variant).

**IO is out of scope.** Getting `BibItem` instances (from .bib files, API, CSL-JSON, etc.) is handled elsewhere in the SDK. This plan covers only `BibItem → HTML` business logic.

## Input: BibItem (from philoch-bib-sdk)

Key fields used for rendering (from `philoch_bib_sdk.logic.models`):

```python
@attrs.define(frozen=True, slots=True)
class BibItem:
    entry_type: TBibTeXEntryType          # "article", "book", "incollection", etc.
    bibkey: MaybeStr[BibKeyAttr]          # structured bibkey
    author: Tuple[Author, ...]            # Author.given_name, .family_name as BibStringAttr
    editor: Tuple[Author, ...]
    date: BibItemDateAttr | "no date"     # .year, .month, .day
    title: MaybeStr[BibStringAttr]        # .latex, .unicode, .simplified
    booktitle: MaybeStr[BibStringAttr]
    crossref: MaybeStr[CrossrefBibItemAttr]
    journal: Maybe[Journal]               # .name as BibStringAttr, .issn_print, .issn_electronic
    volume: str
    number: str
    pages: Tuple[PageAttr, ...]           # .start, .end
    eid: str
    series: MaybeStr[BaseNamedRenderable] # .name as BibStringAttr
    address: MaybeStr[BibStringAttr]
    publisher: MaybeStr[BibStringAttr]
    edition: Maybe[int]
    note: MaybeStr[BibStringAttr]
    doi: str
    url: str
    type: MaybeStr[BibStringAttr]         # thesis type
    school: MaybeStr[BibStringAttr]       # thesis institution
```

`BibStringAttr` has `.latex`, `.unicode`, `.simplified` — the renderer uses `.unicode` for HTML output.

## Output format

```html
<div class="csl-entry" data-type="article" data-bibkey="smith:2024">
  <span data-field="author">
    <span data-field="family" class="smallcaps">Smith</span>,
    <span data-field="given">Jane</span>
  </span>.
  <span data-field="date">2024</span>.
  <span data-field="title">"Some Title."</span>
  <span data-field="journal"><em>Dialectica</em></span>
  <span data-field="volume">78</span>(<span data-field="number">1</span>):
  <span data-field="pages">1–25</span>.
  <span data-field="doi">doi:<a href="https://doi.org/10.48106/...">10.48106/...</a></span>
</div>
```

Every meaningful component wrapped in `data-field` spans. The outer div has `data-type` and `data-bibkey`.

## Dialectica bibliography style rules

Decoded from `dialectica.csl`. The layout is:

```
{contributors}. {date}. {title}. {description}. {secondary-contributors}.
{container-title}, {container-contributors}, {edition}, {locators-chapter},
{collection-title-journal}, {locators}. {collection-title}. {issue}.
{locators-article}. {note}. {access}
```

### Per entry type:

**article** (`entry_type == "article"`):
```
AUTHOR. YEAR. "TITLE." JOURNAL VOLUME(NUMBER): PAGES. doi:DOI
```

**book** (`entry_type == "book"`, with author):
```
AUTHOR. YEAR. TITLE. [EDITION.] [SERIES.] ADDRESS: PUBLISHER. doi:DOI
```

**book** (edited, no author):
```
EDITOR, ed[s]. YEAR. TITLE. [SERIES.] ADDRESS: PUBLISHER. doi:DOI
```

**incollection** (`entry_type == "incollection"`):
```
AUTHOR. YEAR. "TITLE." In BOOKTITLE, [volume VOL,] [edited by EDITOR,] pp. PAGES. ADDRESS: PUBLISHER. doi:DOI
```

**thesis** (`entry_type in ("mastersthesis", "phdthesis")`):
```
AUTHOR. YEAR. "TITLE." TYPE, SCHOOL.
```

**unpublished**:
```
AUTHOR. YEAR. "TITLE." NOTE.
```

**misc / techreport / other**:
```
AUTHOR. YEAR. TITLE. [NOTE.] [doi:DOI]
```

### Author formatting:
- All names: `Family, Given and Family, Given`
- Family names in small caps
- 11+ authors: first 7 then "et al."
- Editors: append `, ed.` (1 editor) or `, eds.` (2+)
- No author/editor: skip the contributor line

### Title formatting:
- Articles/chapters/unpublished: quoted `"Title"`
- Books/theses: italicized `<em>Title</em>`

### Date:
- Year only for most: `2024`
- `"no date"` → `n.d.`

### Pages:
- `start–end` (en-dash)
- Single page: just `start`

### Edition:
- Number → ordinal: `2` → `2nd ed.`

### DOI/URL:
- DOI: `doi:<a href="https://doi.org/{DOI}">{DOI}</a>`
- URL (no DOI): `<a href="{URL}">{URL}</a>`

### Consecutive author suppression:
- When rendering a full bibliography (sorted), repeated author → em-dash `—`

## Implementation

### Location in bib-sdk

New module: `philoch_bib_sdk/converters/html/`

```
philoch_bib_sdk/converters/html/
├── __init__.py
├── renderer.py          # Main public API: render_bibitem(), render_bibliography()
├── entry_types.py       # Per-type rendering: article, book, incollection, thesis, etc.
├── components.py        # Reusable: render_authors(), render_date(), render_title(),
│                        #   render_pages(), render_doi(), render_publisher()
└── constants.py         # data-field names, CSS classes, HTML escaping
```

### Public API

```python
from philoch_bib_sdk.converters.html.renderer import render_bibitem, render_bibliography

# Single entry → HTML string
html: str = render_bibitem(bibitem)

# Sorted list → full bibliography HTML (handles consecutive-author em-dash)
html: str = render_bibliography(bibitems)
```

### Core functions

```python
# renderer.py

def render_bibitem(item: BibItem) -> str:
    """Render a single BibItem to structured HTML."""
    match item.entry_type:
        case "article":
            return _render_article(item)
        case "book":
            return _render_book(item)
        case "incollection" | "inproceedings":
            return _render_chapter(item)
        case "mastersthesis" | "phdthesis":
            return _render_thesis(item)
        case "unpublished":
            return _render_unpublished(item)
        case _:
            return _render_generic(item)


def render_bibliography(items: Sequence[BibItem]) -> str:
    """Render a sorted bibliography. Handles consecutive-author em-dash."""
    # Sort by: author family name, then date, then bibkey
    sorted_items = sort_bibliography(items)
    parts: list[str] = []
    prev_authors: str | None = None
    for item in sorted_items:
        current_authors = _author_sort_key(item)
        suppress = (current_authors == prev_authors) and prev_authors is not None
        parts.append(render_bibitem(item, suppress_author=suppress))
        prev_authors = current_authors
    return '\n'.join(parts)
```

```python
# components.py

def render_authors(
    authors: Tuple[Author, ...],
    role: str = "author",          # "author" or "editor"
    suppress: bool = False,        # consecutive-author em-dash
) -> str:
    """Render author list with smallcaps family names."""
    if suppress:
        return '<span data-field="author">—</span>'
    if not authors:
        return ""
    # Use .unicode for HTML output
    parts = []
    for author in authors[:7] if len(authors) >= 11 else authors:
        family = _bib_str(author.family_name)
        given = _bib_str(author.given_name)
        mononym = _bib_str(author.mononym)
        if mononym:
            parts.append(f'<span data-field="author-name">{_esc(mononym)}</span>')
        else:
            parts.append(
                f'<span data-field="family" class="smallcaps">{_esc(family)}</span>, '
                f'<span data-field="given">{_esc(given)}</span>'
            )
    joined = _join_names(parts)  # "A, B and C" — no Oxford comma per Dialectica style
    if len(authors) >= 11:
        joined += " et al."
    result = f'<span data-field="{role}">{joined}</span>'
    if role == "editor":
        result += ", ed." if len(authors) == 1 else ", eds."
    return result


def render_date(date: BibItemDateAttr | Literal["no date"]) -> str:
    if date == "no date":
        return '<span data-field="date">n.d.</span>'
    return f'<span data-field="date">{date.year}</span>'


def render_title(title: MaybeStr[BibStringAttr], quoted: bool = True) -> str:
    text = _bib_str(title)
    if not text:
        return ""
    if quoted:
        return f'<span data-field="title">"{_esc(text)}."</span>'
    else:
        return f'<span data-field="title"><em>{_esc(text)}</em></span>'


def render_pages(pages: Tuple[PageAttr, ...]) -> str:
    if not pages:
        return ""
    parts = []
    for p in pages:
        if p.end:
            parts.append(f"{p.start}–{p.end}")
        else:
            parts.append(p.start)
    return f'<span data-field="pages">{", ".join(parts)}</span>'


def render_doi(doi: str, url: str) -> str:
    if doi:
        clean = doi.strip()
        return f'<span data-field="doi">doi:<a href="https://doi.org/{_esc(clean)}">{_esc(clean)}</a></span>'
    if url:
        return f'<span data-field="url"><a href="{_esc(url)}">{_esc(url)}</a></span>'
    return ""


def render_publisher(address: MaybeStr[BibStringAttr], publisher: MaybeStr[BibStringAttr]) -> str:
    addr = _bib_str(address)
    pub = _bib_str(publisher)
    parts = [x for x in [addr, pub] if x]
    if not parts:
        return ""
    text = ": ".join(parts)
    return f'<span data-field="publisher">{_esc(text)}</span>'


def render_journal(journal: Maybe[Journal]) -> str:
    if not journal:
        return ""
    name = _bib_str(journal.name)
    return f'<span data-field="journal"><em>{_esc(name)}</em></span>'


def _bib_str(attr: MaybeStr[BibStringAttr]) -> str:
    """Extract unicode string from BibStringAttr, handling empty/None."""
    if not attr or isinstance(attr, str):
        return attr or ""
    return attr.unicode or attr.latex or ""


def _esc(text: str) -> str:
    """HTML-escape."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _join_names(parts: list[str]) -> str:
    """Join with commas and 'and': 'A, B and C'."""
    if len(parts) <= 1:
        return parts[0] if parts else ""
    return ", ".join(parts[:-1]) + " and " + parts[-1]
```

### Entry type renderers

```python
# entry_types.py

def _render_article(item: BibItem) -> str:
    bibkey = _format_bibkey(item.bibkey)
    parts = [
        render_authors(item.author),
        render_date(item.date),
        render_title(item.title, quoted=True),
    ]
    # Journal + locators
    journal_part = render_journal(item.journal)
    if item.volume:
        journal_part += f' <span data-field="volume">{item.volume}</span>'
    if item.number:
        journal_part += f'(<span data-field="number">{item.number}</span>)'
    pages = render_pages(item.pages)
    if pages:
        journal_part += f': {pages}'
    parts.append(journal_part)
    access = render_doi(item.doi, item.url)
    if access:
        parts.append(access)
    inner = ". ".join(p for p in parts if p)
    return f'<div class="csl-entry" data-type="article" data-bibkey="{bibkey}">{inner}.</div>'

# Similar for _render_book, _render_chapter, _render_thesis, _render_unpublished, _render_generic
```

### Edge cases to handle

From actual dialectica.bib data:

| Case | Example | How to handle |
|------|---------|---------------|
| Name particles | `Dutilh Novaes` | `family_name` includes particle in bib-sdk |
| Name suffixes | `Belnap, Jr.` | Check if bib-sdk stores this in `family_name` |
| Mononyms | `Aristotle` | `author.mononym` field — render without comma |
| Multiple editors | `Wellman and Frey, eds.` | Plural `, eds.` |
| Edition numbers | `2` | Ordinal: `2nd ed.` |
| Series | `Blackwell Companions` | After publisher |
| Notes with citations | `Reprinted in Author (Year)` | Render as plain text from `.unicode` |
| No DOI, has URL | Various | Fall back to URL link |
| No author, has editor | Edited books | Editor with `, ed.` replaces author |
| eid instead of pages | `e1489` | Render eid if no pages |
| `"no date"` | Forthcoming | Render as `n.d.` or `forthcoming` based on `pubstate` |

## Testing

```python
# tests/converters/html/test_renderer.py

def test_render_article():
    item = default_bib_item(
        entry_type="article",
        author=({"given_name": {"unicode": "Jane"}, "family_name": {"unicode": "Smith"}},),
        date={"year": 2024},
        title={"unicode": "Some Title"},
        journal={"name": {"unicode": "Dialectica"}},
        volume="78",
        number="1",
        pages=({"start": "1", "end": "25"},),
        doi="10.48106/dial.v78.i1.1234",
    )
    html = render_bibitem(item)
    assert 'data-field="author"' in html
    assert 'class="smallcaps"' in html
    assert 'data-field="date">2024</span>' in html
    assert 'data-field="journal"><em>Dialectica</em></span>' in html
    assert 'data-field="pages">1–25</span>' in html
    assert 'doi:' in html

def test_render_book_edited(): ...
def test_render_incollection(): ...
def test_render_thesis(): ...
def test_render_consecutive_author_suppression(): ...
def test_render_mononym(): ...
def test_render_no_date(): ...
def test_render_11_plus_authors(): ...
```

## Estimated effort

| Component | Lines | Notes |
|-----------|-------|-------|
| `components.py` | ~120 | render_authors, render_date, render_title, render_pages, render_doi, render_publisher, render_journal, helpers |
| `entry_types.py` | ~150 | 6 entry types × ~25 lines each |
| `renderer.py` | ~40 | Public API, dispatch, bibliography sorting |
| `constants.py` | ~15 | CSS classes, field names |
| Tests | ~200 | One test per entry type + edge cases |
| **Total** | **~525** | |
