---
name: columbia-clio
description: Search Columbia University Libraries' CLIO catalog for books, journals, manuscripts, and other holdings via its Blacklight JSON API. Use this skill whenever the user wants to look up items in Columbia's library, check availability of books at Columbia, search by title/author/subject with faceted filtering by format/language/location, or retrieve detailed catalog records including call numbers and holdings data. Triggers when referencing Columbia University collections or Ivy League library holdings.
version: 1.0.0
---

# Columbia CLIO Catalog Skill

Search Columbia University Libraries' catalog of books, journals, manuscripts, and more.

## Critical: Things Claude Won't Know Without This Skill

### CLIO has an undocumented but fully functional JSON API

CLIO runs on Blacklight (Solr-based). Append `.json` to catalog URLs for JSON responses. No API key required.

```
Search:  https://clio.columbia.edu/catalog.json?q=hamlet&per_page=10
Record:  https://clio.columbia.edu/catalog/{id}.json
```

### Field-specific search uses `search_field` parameter

```
All fields: ?q=hamlet
Title only: ?q=hamlet&search_field=title
Author:     ?q=shakespeare&search_field=author
```

### Facets use array bracket syntax

```
?f[format][]=Book
?f[language_facet][]=Chinese&f[format][]=Book
```

Available facets: `format`, `language_facet`, `location_facet`, `subject_topic_facet`, `subject_geo_facet`, `subject_era_facet`, `subject_form_facet`, `pub_date_sort`.

### This is undocumented — be a good citizen

No rate limits are documented, but this is an unofficial API. Keep requests to 1/second max. The official bulk data is at `https://lito.cul.columbia.edu/extracts/ColumbiaLibraryCatalog/full/` (MARCXML, CC0).

## Key Search Parameters

| Param | Description | Example |
|-------|-------------|---------|
| `q` | Search query | `q=dream+of+the+red+chamber` |
| `search_field` | Limit to field: `title`, `author`, or all | `search_field=title` |
| `per_page` | Results per page (default ~10) | `per_page=25` |
| `page` | Page number | `page=2` |
| `sort` | Sort: `pub_date_sort+desc`, `pub_date_sort+asc` | `sort=pub_date_sort+desc` |
| `f[facet][]` | Filter by facet value | `f[format][]=Book` |

## Response Structure

```json
{
  "response": {
    "docs": [
      {
        "id": "12345678",
        "title_display": "Hamlet",
        "author_display": "Shakespeare, William, 1564-1616",
        "format": ["Book"],
        "pub_year_display": ["2003"],
        "pub_name_display": ["Cambridge University Press"],
        "language_facet": ["English"],
        "isbn_display": ["9780521532525"],
        "location_call_number_id_display": ["Butler Stacks PR2807 .A2 T48 2003 "]
      }
    ],
    "facets": [ ... ],
    "pages": {
      "current_page": 1,
      "total_pages": 5330,
      "total_count": 10659,
      "next_page": 2
    }
  }
}
```

### Key Document Fields

| Field | Description |
|-------|-------------|
| `id` | Catalog record ID |
| `title_display` | Title |
| `author_display` | Primary author |
| `author_facet` | All authors (array) |
| `format` | Format (Book, Online, Music, etc.) |
| `pub_year_display` | Publication year(s) |
| `pub_name_display` | Publisher |
| `pub_place_display` | Place of publication |
| `language_facet` | Language(s) |
| `isbn_display` | ISBN(s) |
| `oclc_display` | OCLC number(s) |
| `lccn_display` | LCCN(s) |
| `subject_topic_facet` | Subject terms |
| `location_call_number_id_display` | Location + call number |
| `physical_description_display` | Physical description |

## Python Script

```python
from scripts.clio_api import ColumbiaClioAPI
clio = ColumbiaClioAPI()

# Search
results = clio.search("hamlet", search_field="title", per_page=10)

# With facets
results = clio.search("chinese poetry", facets={"format": "Book", "language_facet": "Chinese"})

# Get single record
record = clio.get_record("12345678")

# Summarize
for r in results:
    print(clio.summarize(r))
```

## Related Skills

- **harvard-library-catalog**: Compare holdings across Harvard and Columbia
- **hathitrust-catalog**: Use ISBNs/OCLCs from CLIO to check HathiTrust for digital versions
- **wikidata-search**: Link OCLC numbers to Wikidata entities

## Resources

- `references/api_reference.md` — Complete field and facet reference
- `scripts/clio_api.py` — Python client with search, record lookup, and faceted filtering
