"""
Extract exactly 587 philosophy master's theses (mémoires de licence) using server-side filtering.
Uses POST requests with form parameters to get pre-filtered results.
"""

import requests
import re
import time
from typing import Optional, TypedDict
from bs4 import BeautifulSoup, Tag
from philoch_bib_enhancer.adapters.raw_text.raw_text_models import RawTextBibitem, RawTextAuthor


class FilteredPageResponse(TypedDict):
    html: str


class ParsedPageItem(TypedDict):
    id: str | list[str] | None
    title: str | None
    year: int | None
    authors: list[RawTextAuthor]
    raw_text: str
    classification: str | None
    publisher: str | None


from philoch_bib_enhancer.cli.manual_raw_text_to_csv import process_raw_bibitems


def parse_author_string(author_str: Optional[str]) -> list[RawTextAuthor]:
    """Parse author string into RawTextAuthor."""
    if not author_str:
        return []
    author_str = author_str.strip()
    if ',' in author_str:
        parts = [p.strip() for p in author_str.split(',', 1)]
        return [RawTextAuthor(family=parts[0], given=parts[1] if len(parts) > 1 else None)]
    else:
        parts = author_str.rsplit(' ', 1)
        if len(parts) == 2:
            return [RawTextAuthor(given=parts[0], family=parts[1])]
        else:
            return [RawTextAuthor(family=author_str)]


def fetch_filtered_page(page_num: int) -> FilteredPageResponse:
    """Fetch a page using POST with form parameters (as browser does)."""
    url = 'https://www.fr.ch/app/master_cat/get_results'

    # POST data with form parameters - exactly as the browser sends
    data = {
        'form[f_faculty]': '2',  # Faculty of Letters
        'form[f_document]': '3',  # Mémoires de licence (master's theses)
        'form[f_subject_category]': '40',  # Philosophie
        'page': str(page_num),
    }

    response = requests.post(url, data=data, timeout=15)
    result: FilteredPageResponse = response.json()
    return result


def extract_total_count(html: str) -> Optional[int]:
    """Extract total count from HTML."""
    soup = BeautifulSoup(html, 'html.parser')
    results_span = soup.find('span', class_='filter-results__item')
    if results_span and isinstance(results_span, Tag):
        text = results_span.get_text(strip=True)
        match = re.search(r'(\d+)', text)
        if match:
            return int(match.group(1))
    return None


def parse_page_items(html: str) -> list[ParsedPageItem]:
    """Parse items from HTML response."""
    soup = BeautifulSoup(html, 'html.parser')
    items: list[ParsedPageItem] = []

    list_items = soup.find_all('li', class_='element-list')

    for li in list_items:
        # Get item ID
        hidden_input = li.find('input', {'name': 'id-item'})
        if not hidden_input or not isinstance(hidden_input, Tag):
            continue

        item_id = hidden_input.get('value')

        # Extract title
        title_elem = li.find('h2', class_='h3')
        full_title = title_elem.get_text(strip=True) if title_elem and isinstance(title_elem, Tag) else None

        # Extract author
        author_elem = li.find('p', class_='list__item__description')
        author_str = author_elem.get_text(strip=True) if author_elem and isinstance(author_elem, Tag) else None

        # Extract metadata
        meta_dl = li.find('dl', class_='list__item__meta')
        classification = None
        year: Optional[int] = None
        publisher = None

        if meta_dl and isinstance(meta_dl, Tag):
            for dt, dd in zip(meta_dl.find_all('dt'), meta_dl.find_all('dd')):
                dt_text = dt.get_text(strip=True)
                dd_text = dd.get_text(strip=True)

                if 'Classification' in dt_text:
                    classification = dd_text
                    # Extract year from "MEMFR FACLET YYYY" format
                    year_match = re.search(r'MEMFR\s+FACLET\s+(\d{4})', classification)
                    if year_match:
                        year = int(year_match.group(1))
                    else:
                        # Fallback: just look for any 4-digit year
                        year_match = re.search(r'(\d{4})', classification)
                        if year_match:
                            year = int(year_match.group(1))
                elif 'Lieu, Année' in dt_text or 'Lieu, année' in dt_text:
                    if ':' in dd_text:
                        parts = dd_text.split(':', 1)
                        if len(parts) == 2:
                            publisher = parts[1].strip()
                            publisher = re.sub(r',?\s*\d{4}\s*$', '', publisher).strip()

        # Parse title/author
        title: Optional[str]
        if full_title and ' / ' in full_title:
            title_parts = full_title.split(' / ', 1)
            title = title_parts[0].strip()
            if not author_str and len(title_parts) > 1:
                author_str = title_parts[1].strip()
        else:
            title = full_title

        authors = parse_author_string(author_str) if author_str else []
        raw_text = li.get_text(separator='\n', strip=True)

        items.append(
            {
                'id': item_id,
                'title': title,
                'year': year,
                'authors': authors,
                'raw_text': raw_text,
                'classification': classification,
                'publisher': publisher,
            }
        )

    return items


# Main execution
print("=" * 80)
print("EXTRACTING 587 PHILOSOPHY MASTER'S THESES (MÉMOIRES) USING SERVER-SIDE FILTERING")
print("=" * 80)
print("\nUsing POST with form parameters to get pre-filtered results...")
print("This should take 2-3 minutes.\n")

all_items = []

# First, get page 1 to see total count
print("Fetching page 1 to check total count...")
page1_data = fetch_filtered_page(1)
page1_html = page1_data.get('html', '')

total_count = extract_total_count(page1_html)
print(f"Total results found: {total_count}")

# Parse page 1 items
page1_items = parse_page_items(page1_html)
all_items.extend(page1_items)
print(f"Page 1: {len(page1_items)} items")

# Calculate total pages needed (10 items per page)
if total_count:
    total_pages = (total_count + 9) // 10  # Round up
    print(f"Total pages to fetch: {total_pages}\n")

    # Fetch remaining pages
    for page_num in range(2, total_pages + 1):
        try:
            data = fetch_filtered_page(page_num)
            html = data.get('html', '')
            items = parse_page_items(html)

            if items:
                all_items.extend(items)
                if page_num % 5 == 0:
                    print(f"Page {page_num}/{total_pages}: {len(all_items)} items collected so far...")
            else:
                print(f"No items on page {page_num}. Stopping.")
                break

            time.sleep(0.2)  # Be polite

        except Exception as e:
            print(f"Error on page {page_num}: {e}")
            continue

print(f"\n{'=' * 80}")
print(f"EXTRACTION COMPLETE")
print(f"{'=' * 80}")
print(f"Total items collected: {len(all_items)}")
print(f"{'=' * 80}\n")

# Show some sample years to verify extraction
print("Sample entries with years extracted:")
for i, item in enumerate(all_items[:5]):
    print(
        f"  {i+1}. {(item['title'] or 'N/A')[:50]}... -> Year: {item['year'] or 'N/A'} (from: {item['classification'] or 'N/A'})"
    )
print()

# Convert to RawTextBibitem
print("Converting to RawTextBibitem objects...")
raw_bibitems = []
for item in all_items:
    bibitem = RawTextBibitem(
        raw_text=item['raw_text'],
        type='mastersthesis',  # Changed from 'thesis' to 'mastersthesis'
        title=item['title'],
        year=item['year'],
        authors=item['authors'],
        publisher=item.get('publisher'),
    )
    raw_bibitems.append(bibitem)

# Save to CSV
output_path = "./data/test-2/philosophy_masters_587.csv"
print(f"\nWriting {len(raw_bibitems)} items to {output_path}...")

process_raw_bibitems(
    raw_bibitems=raw_bibitems,
    output_path=output_path,
    bibliography_path=None,
)

print(f"\n{'=' * 80}")
print(f"✓ SUCCESS!")
print(f"{'=' * 80}")
print(f"  Output: {output_path}")
print(f"  Total:  {len(raw_bibitems)} philosophy master's theses")
print(f"{'=' * 80}")
