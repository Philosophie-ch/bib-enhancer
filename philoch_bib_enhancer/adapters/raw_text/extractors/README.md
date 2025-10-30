# Web Extractors Registry

This directory contains site-specific bibliographic data extractors and a registry documenting past extraction experiences.

## Quick Start

Use the `/extract-web` slash command in Claude Code:

```
/extract-web https://www.unifr.ch/philosophie/de/forschung/habilitationen.html
```

Claude will:
1. Check the registry for this URL
2. Follow the documented extraction method
3. Extract bibliographic references
4. Convert to CSV

## Registry Structure

The [`registry.json`](registry.json) file documents:

### Site Characteristics
- **Type**: `static_html`, `dynamic_api`, `javascript_spa`, etc.
- **Structure**: How the site organizes data
- **JavaScript requirements**: Whether JS rendering is needed
- **Pagination**: How many items per page, pagination mechanism

### Extraction Method
- **Approach**: GET, POST, form parameters, API endpoints
- **Steps**: Detailed extraction workflow
- **Challenges**: Problems encountered and solutions
- **Notes**: Key insights and gotchas

### Discovery Process
- **Attempts**: What we tried and why it didn't work
- **Key insights**: The breakthrough that made it work

### Sample Entry
Example of extracted data structure for validation

## Common Patterns

### Pattern 1: Static HTML Page
**Example**: unifr.ch/philosophie habilitationen

**Characteristics**:
- Simple HTML structure
- No JavaScript required
- Data in page source

**Approach**:
```python
from philoch_bib_enhancer.adapters.raw_text.web_scraper import fetch_url_text

text = fetch_url_text(url)
# Parse HTML, create RawTextBibitem objects
```

### Pattern 2: API with Form Parameters
**Example**: fr.ch/bcu master catalogue

**Characteristics**:
- Dynamic AJAX loading
- POST required with specific parameter format
- Server-side filtering
- Pagination

**Gotcha**: URL parameters ignored! Must use `form[parameter]` format in POST data.

**Approach**:
```python
import requests

data = {
    'form[f_faculty]': '2',
    'form[f_document]': '1',
    'form[f_subject_category]': '40',
    'page': '1'
}
response = requests.post('https://www.fr.ch/app/master_cat/get_results', data=data)
```

### Pattern 3: JavaScript-Rendered SPA
**Characteristics**:
- Data loaded after page load
- May require browser automation
- Often has API endpoints

**Approach**:
1. Inspect browser Network tab to find API calls
2. Replicate API requests directly (preferred)
3. Use Selenium/Playwright only as last resort

## Adding New Sites

When you extract from a new site:

1. **Document the discovery process**:
   - What did you try first?
   - What didn't work and why?
   - What was the breakthrough?

2. **Add to registry.json**:
```json
{
  "https://example.com/path": {
    "site_name": "Example Site",
    "description": "What data this contains",
    "expected_count": 123,
    "last_extraction": "2025-10-29",
    "site_characteristics": {
      "type": "static_html|dynamic_api|javascript_spa",
      "structure": "Describe structure",
      "javascript_required": false,
      "pagination": true
    },
    "extraction_method": {
      "approach": "Describe method",
      "steps": ["Step 1", "Step 2"],
      "challenges": [
        {
          "issue": "What went wrong",
          "solution": "How you fixed it"
        }
      ],
      "notes": ["Important insights"]
    },
    "sample_entry": {
      "raw_text": "...",
      "type": "article",
      "title": "..."
    }
  }
}
```

3. **Save extraction script** (optional):
   - If the site has complex logic, save the script here
   - Name it after the site: `example_com.py`
   - Keep it standalone and documented

## Extraction Scripts

This directory contains working extraction scripts for complex sites:

- [`unifr_master_cat.py`](unifr_master_cat.py) - Fribourg master catalogue (POST with form params)

These scripts are examples and can be run directly:
```bash
python philoch_bib_enhancer/extractors/unifr_master_cat.py
```

## Best Practices

### 1. Check Registry First
Before starting extraction, **always check the registry**. Don't waste time rediscovering what we already know.

### 2. Be Nice to Servers
- Add delays between requests (0.2-0.5s)
- Don't parallelize requests unnecessarily
- Cache responses when testing

### 3. Document Gotchas
The registry's value is in documenting what **didn't** work and why:
- "Tried GET with URL params → ignored by server"
- "Thought we needed detail pages → server filters work"
- "Browser shows 466 but API returns 31k → wrong parameter format"

### 4. Test Extraction Methods
Before processing thousands of items:
1. Test on first page/item
2. Verify data structure
3. Check expected count matches
4. Then scale up

### 5. Handle Errors Gracefully
- URLs change
- APIs evolve
- Sites go down
- Document these when they happen

## RawText Workflow

All extractors follow the RawText manual workflow:

1. **Fetch**: Get page/API content
2. **Parse**: Identify bibliographic references
3. **Model**: Create `RawTextBibitem` objects
4. **Convert**: Use `process_raw_bibitems()` → CSV

See [`manual_raw_text_to_csv.py`](../cli/manual_raw_text_to_csv.py) for the conversion function.

## Registry Maintenance

### When to Update
- Site structure changes
- API parameters change
- Expected counts change significantly
- New extraction patterns discovered

### Version Control
The registry is version-controlled. When making changes:
1. Update `last_extraction` date
2. Add notes about what changed
3. Keep old methods in "legacy" section if useful

## Need Help?

The registry is designed to help Claude Code (and humans) extract data efficiently by learning from past experiences. If Claude encounters a site in the registry, it should follow the documented approach rather than starting from scratch.

For new patterns or issues, update the registry so future extractions benefit from your experience!
