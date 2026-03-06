---
name: loc-catalog
description: Search the Library of Congress digital collections via the loc.gov JSON API. Use this skill whenever the user wants to search LOC's digitized books, photos, maps, manuscripts, newspapers, audio, or film/video, look up items by LCCN, browse LOC collections, find primary sources with date range filters, or retrieve citations and download links for LOC materials. Also triggers when cross-referencing items found in other library catalogs against LOC holdings.
version: 1.0.0
---

# Library of Congress API Skill

Search and retrieve items from LOC's digitized collections — books, photos, maps, manuscripts, newspapers, audio, and more.

## Critical: Things Claude Won't Know Without This Skill

### This API covers digitized collections, NOT the full library catalog

The loc.gov JSON API searches LOC's **digitized and online collections** — not the full OPAC. By default, only digitized items are returned. Add `all=true` to include non-digitized catalog records.

### JSON requires `fo=json` parameter, NOT a URL extension

Unlike LibraryCloud (`.json` extension), LOC uses a query parameter:

```
CORRECT: https://www.loc.gov/search/?q=hamlet&fo=json
WRONG:   https://www.loc.gov/search.json?q=hamlet
```

### Facet filters use `fa=` with pipe separators

```
Single:   ?fa=subject:physics
Multiple: ?fa=subject:wildlife|location:yellowstone
```

Available facet fields: `subject`, `contributor`, `location`, `language`, `original-format`, `online-format`, `partof`, `digitized`, `access-restricted`.

### Format-specific endpoints are shortcuts

`/books/`, `/photos/`, `/maps/`, `/audio/`, `/newspapers/`, `/manuscripts/`, `/film-and-videos/`, `/notated-music/` all accept the same params as `/search/`.

## Key Search Parameters

| Param | Description | Example |
|-------|-------------|---------|
| `q` | Keyword search | `q=hamlet+shakespeare` |
| `fa` | Facet filter | `fa=subject:physics\|language:english` |
| `dates` | Date range (YYYY/YYYY) | `dates=1920/1940` |
| `c` | Results per page (25, 50, 100, 150) | `c=50` |
| `sp` | Page number (starts at 1) | `sp=2` |
| `sb` | Sort: `date`, `date_desc`, `title_s`, `title_s_desc` | `sb=date_desc` |
| `all` | Include non-digitized (`true`/`false`) | `all=true` |
| `at` | Select attributes (comma-sep) | `at=item,resources` |
| `fo` | Format: `json` or `yaml` | `fo=json` |

## Item Lookup by LCCN/ID

```
https://www.loc.gov/item/{LCCN}/?fo=json
```

Returns full item detail including `cite_this` (APA/Chicago/MLA citations), `resources` (download links), `other_formats` (MARCXML, MODS, Dublin Core).

## Response Structure

### Search Results

```json
{
  "results": [
    {
      "id": "http://www.loc.gov/item/95521789/",
      "title": "Item title",
      "date": "1796-01-01",
      "contributor": ["Name"],
      "subject": ["Subject term"],
      "language": ["English"],
      "original_format": ["book"],
      "description": ["..."],
      "image_url": ["//tile.loc.gov/..."],
      "digitized": true,
      "number_lccn": ["95521789"]
    }
  ],
  "pagination": {
    "of": 85604,
    "total": 17121,
    "perpage": 5,
    "current": 1
  },
  "facets": { ... }
}
```

### Item Detail

The `item` object adds: `call_number`, `created_published`, `rights`, `summary`, `stmt_of_responsibility`, `genre`, and `cite_this` with pre-formatted citations.

## Python Script

```python
from scripts.loc_api import LocAPI
loc = LocAPI()

# Keyword search
results = loc.search("hamlet shakespeare", limit=10)

# Format-specific
photos = loc.search("civil war", format="photos", dates="1860/1865")

# Faceted search
results = loc.search("wildlife", facets={"subject": "birds", "location": "yellowstone"})

# Item lookup
item = loc.get_item("95521789")
citation = loc.get_citation(item, style="apa")

# Browse collections
collections = loc.list_collections()
items = loc.browse_collection("civil-war-maps", limit=20)

# Summarize
for r in results[:5]:
    print(loc.summarize(r))
```

## Pagination

- Max 150 results per page (`c=150`)
- Hard limit: cannot paginate past 100,000th result
- Use facets/date ranges to narrow large result sets

## API Etiquette

- No authentication required
- Rate limiting is enforced (exact limits unpublished) — add 0.5-1s between requests
- Include a User-Agent header

## Related Skills

- **harvard-library-catalog**: Cross-reference Harvard holdings with LOC items
- **hathitrust-catalog**: Use LCCNs from LOC to check HathiTrust for digital full-text
- **wikidata-search**: LOC authority IDs (P244) link Wikidata entities to LOC records

## Resources

- `references/api_reference.md` — Complete parameter and response field reference
- `scripts/loc_api.py` — Python client with search, item lookup, collection browsing, and citation extraction
