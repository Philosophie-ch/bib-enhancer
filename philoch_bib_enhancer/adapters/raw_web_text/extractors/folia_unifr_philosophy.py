#!/usr/bin/env python3
"""
Extract detailed bibliographic records from UNIFR Philosophy pages using structured metadata.
This version uses JSON-LD and Dublin Core meta tags for accurate extraction.
"""

from bs4 import BeautifulSoup, Tag
import re
import requests
import time
import json
from philoch_bib_enhancer.adapters.raw_web_text.raw_web_text_models import (
    RawWebTextBibitem,
    RawWebTextAuthor,
)
from philoch_bib_enhancer.cli.manual_raw_web_text_to_csv import process_raw_bibitems

html_path = "data/unifr-philo.html"

print(f"Reading: {html_path}")
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

# Find all links to individual documents
print("Finding document links...")
record_links: list[str] = []
for link_elem in soup.find_all('a', href=re.compile(r'/unifr/documents/\d+')):
    if isinstance(link_elem, Tag):
        href = link_elem.get('href')
        if isinstance(href, str) and href not in record_links:
            record_links.append(href)

print(f"Found {len(record_links)} unique document links\n")

# For each document link, fetch and parse the page
bibitems = []

for idx, link in enumerate(record_links, 1):
    print(f"[{idx}/{len(record_links)}] {link}")

    if not link.startswith('http'):
        url = f"https://folia.unifr.ch{link}"
    else:
        url = link

    try:
        # Add a small delay to be polite
        if idx > 1:
            time.sleep(1)

        response = requests.get(url, timeout=30)

        if response.status_code != 200:
            print(f"  ✗ Error: HTTP {response.status_code}")
            continue

        # Parse the individual record page
        record_soup = BeautifulSoup(response.content, 'html.parser')

        # Initialize fields
        title = None
        authors = []
        year = None
        pub_type = "article"
        journal = None
        volume = None
        number = None
        start_page = None
        end_page = None
        doi = None
        publisher = None

        # === METHOD 1: Try JSON-LD first (most reliable) ===
        json_ld_script = record_soup.find('script', type='application/ld+json')
        if json_ld_script and isinstance(json_ld_script, Tag):
            try:
                script_string = json_ld_script.string
                if script_string:
                    json_data = json.loads(script_string)
                else:
                    json_data = {}

                # Extract title
                if 'name' in json_data:
                    title = json_data['name']

                # Extract authors
                if 'creator' in json_data:
                    creators = json_data['creator']
                    if isinstance(creators, list):
                        for creator in creators:
                            if isinstance(creator, dict) and 'name' in creator:
                                name = creator['name']
                                # Try to parse "Family, Given" or "Given Family"
                                if ',' in name:
                                    family, given = name.split(',', 1)
                                    authors.append(RawWebTextAuthor(given=given.strip(), family=family.strip()))
                                else:
                                    # Assume "Given Family" format
                                    parts = name.strip().split()
                                    if len(parts) >= 2:
                                        given = ' '.join(parts[:-1])
                                        family = parts[-1]
                                        authors.append(RawWebTextAuthor(given=given, family=family))
                                    else:
                                        authors.append(RawWebTextAuthor(family=name))

                # Extract year
                if 'datePublished' in json_data:
                    year_str = json_data['datePublished']
                    year_match = re.search(r'\b(19|20)\d{2}\b', str(year_str))
                    if year_match:
                        year = int(year_match.group())

            except Exception as e:
                print(f"  Warning: Could not parse JSON-LD: {e}")

        # === METHOD 2: Use Dublin Core meta tags ===
        if not title:
            title_meta = record_soup.find('meta', attrs={'name': 'citation_title'})
            if title_meta and isinstance(title_meta, Tag):
                content = title_meta.get('content')
                if isinstance(content, str):
                    title = content

        if not authors:
            author_metas = record_soup.find_all('meta', attrs={'name': 'citation_author'})
            for meta in author_metas:
                if isinstance(meta, Tag):
                    content = meta.get('content', '')
                    name = content.strip() if isinstance(content, str) else ''
                    if name:
                        # Try to parse "Family, Given" format
                        if ',' in name:
                            family, given = name.split(',', 1)
                            authors.append(RawWebTextAuthor(given=given.strip(), family=family.strip()))
                        else:
                            # Assume "Given Family" format
                            parts = name.split()
                            if len(parts) >= 2:
                                given = ' '.join(parts[:-1])
                                family = parts[-1]
                                authors.append(RawWebTextAuthor(given=given, family=family))
                            else:
                                authors.append(RawWebTextAuthor(family=name))

        if not year:
            year_meta = record_soup.find('meta', attrs={'name': 'citation_publication_date'})
            if year_meta and isinstance(year_meta, Tag):
                content = year_meta.get('content', '')
                year_str = content if isinstance(content, str) else ''
                year_match = re.search(r'\b(19|20)\d{2}\b', year_str)
                if year_match:
                    year = int(year_match.group())

        # Extract DOI
        doi_meta = record_soup.find('meta', attrs={'name': 'citation_doi'})
        if doi_meta and isinstance(doi_meta, Tag):
            content = doi_meta.get('content')
            if isinstance(content, str):
                doi = content

        # Extract journal
        journal_meta = record_soup.find('meta', attrs={'name': 'citation_journal_title'})
        if journal_meta and isinstance(journal_meta, Tag):
            content = journal_meta.get('content')
            if isinstance(content, str):
                journal = content

        # Extract volume
        volume_meta = record_soup.find('meta', attrs={'name': 'citation_volume'})
        if volume_meta and isinstance(volume_meta, Tag):
            content = volume_meta.get('content')
            if isinstance(content, str):
                volume = content

        # Extract issue/number
        issue_meta = record_soup.find('meta', attrs={'name': 'citation_issue'})
        if issue_meta and isinstance(issue_meta, Tag):
            content = issue_meta.get('content')
            if isinstance(content, str):
                number = content

        # Extract pages
        firstpage_meta = record_soup.find('meta', attrs={'name': 'citation_firstpage'})
        if firstpage_meta and isinstance(firstpage_meta, Tag):
            content = firstpage_meta.get('content')
            if isinstance(content, str):
                start_page = content

        lastpage_meta = record_soup.find('meta', attrs={'name': 'citation_lastpage'})
        if lastpage_meta and isinstance(lastpage_meta, Tag):
            content = lastpage_meta.get('content')
            if isinstance(content, str):
                end_page = content

        # Extract publisher
        publisher_meta = record_soup.find('meta', attrs={'name': 'citation_publisher'})
        if publisher_meta and isinstance(publisher_meta, Tag):
            content = publisher_meta.get('content')
            if isinstance(content, str):
                publisher = content

        # Print extracted info
        if title:
            print(f"  ✓ {title[:60]}...")
        if authors:
            author_str = ', '.join([f"{a.family}" for a in authors[:3]])
            if len(authors) > 3:
                author_str += f" et al. ({len(authors)} total)"
            print(f"    Authors: {author_str}")
        if year:
            print(f"    Year: {year}")
        if journal:
            print(f"    Journal: {journal}")
            if volume:
                print(f"    Volume: {volume}", end="")
                if number:
                    print(f"({number})", end="")
                if start_page:
                    print(f", pp. {start_page}", end="")
                    if end_page:
                        print(f"-{end_page}", end="")
                print()
        if doi:
            print(f"    DOI: {doi}")

        # Get raw text for context
        main_content = record_soup.find('ng-core-record-detail-view')
        if main_content:
            raw_text = main_content.get_text(separator=' ', strip=True)[:1000]
        else:
            raw_text = record_soup.get_text(separator=' ', strip=True)[:1000]

        # Create bibitem
        bibitem = RawWebTextBibitem(
            raw_text=raw_text,
            type=pub_type,
            title=title,
            year=year,
            authors=authors,
            journal=journal,
            volume=volume,
            issue_number=number,
            start_page=start_page,
            end_page=end_page,
            doi=doi,
            publisher=publisher,
            url=url,
        )

        bibitems.append(bibitem)

    except Exception as e:
        print(f"  ✗ Error: {e}")
        continue

print(f"\n{'='*80}")
print(f"Successfully extracted {len(bibitems)}/{len(record_links)} bibliographic items")
print(f"{'='*80}")

if bibitems:
    # Save to output
    import os

    os.makedirs("./data/test-2", exist_ok=True)
    output_path = "./data/test-2/folia_unifr_references.csv"

    print(f"\nProcessing bibitems to CSV: {output_path}")
    process_raw_bibitems(
        raw_bibitems=bibitems,
        output_path=output_path,
    )

    print(f"\n✓ Complete! CSV saved to: {output_path}")
    print(f"  Total records: {len(bibitems)}")

    # Summary statistics
    with_authors = sum(1 for b in bibitems if b.authors)
    with_doi = sum(1 for b in bibitems if b.doi)
    with_journal = sum(1 for b in bibitems if b.journal)

    print(f"\nMetadata coverage:")
    print(f"  - With authors: {with_authors}/{len(bibitems)}")
    print(f"  - With DOI: {with_doi}/{len(bibitems)}")
    print(f"  - With journal: {with_journal}/{len(bibitems)}")
else:
    print("\nNo bibitems extracted.")
