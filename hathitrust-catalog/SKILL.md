---
name: hathitrust-catalog
description: Look up bibliographic records and digitized volumes in HathiTrust's 17M+ volume collection by ISBN, OCLC, LCCN, ISSN, or HathiTrust ID. Use this skill whenever the user wants to check if a book has been digitized, find which libraries hold a copy, get MARC metadata for a known identifier, or link a bibliographic reference to its HathiTrust digital version. Also triggers when cross-referencing identifiers from other library catalogs (Harvard, Library of Congress) against HathiTrust holdings.
version: 1.0.0
---

# HathiTrust Bibliographic API Skill

Look up records and digitized volumes in HathiTrust's collection of 17M+ volumes from major research libraries.

## Critical: Things Claude Won't Know Without This Skill

### This is a lookup API, NOT a search API

HathiTrust's Bibliographic API retrieves records by **known identifiers** only. There is no keyword or title search. You must have an ISBN, OCLC number, LCCN, ISSN, or HathiTrust ID.

```
WORKS:     https://catalog.hathitrust.org/api/volumes/brief/isbn/0140449264.json
NOT POSSIBLE: https://catalog.hathitrust.org/api/volumes/brief/search?q=hamlet
```

If you only have a title/author, search another catalog first (LibraryCloud, Library of Congress) to get an ISBN or OCLC number, then look it up here.

### Two endpoint variants: brief vs full

| Endpoint | Returns | Use when |
|----------|---------|----------|
| `/api/volumes/brief/` | Metadata + items (no MARC) | You just need titles, ISBNs, holdings, digital access links |
| `/api/volumes/full/` | Same + complete MARC-XML | You need full cataloging data |

### Empty results are not errors

When no record matches, the API returns `{"records": {}, "items": []}` with HTTP 200 — not a 404. Always check if `records` is empty.

### Batch up to 20 lookups in one request

Use the multi-ID endpoint to batch lookups:

```
/api/volumes/brief/json/isbn:0140449264|oclc:228668653
```

Pipe-separated as `type:value`. Max 20 per request.

## Identifier Types

| Type | Example | Notes |
|------|---------|-------|
| `isbn` | `0140449264` or `9780140449266` | ISBN-10 or ISBN-13, digits only (+ trailing X) |
| `oclc` | `228668653` | OCLC number, digits only |
| `lccn` | `72081773` | URL-encode spaces/slashes |
| `issn` | `03785955` | Digits only |
| `htid` | `mdp.39015058510069` | HathiTrust volume ID |
| `recordnumber` | `000578050` | 9-digit HathiTrust record number |

## Response Structure

```json
{
  "records": {
    "009058846": {
      "recordURL": "https://catalog.hathitrust.org/Record/009058846",
      "titles": ["The Odyssey / Homer ; translated by Robert Fagles."],
      "isbns": ["0140268863", "9780140268867"],
      "oclcs": ["34228839"],
      "lccns": ["96017900"],
      "publishDates": ["1997"]
    }
  },
  "items": [
    {
      "orig": "University of Michigan",
      "htid": "mdp.39015042182054",
      "itemURL": "https://babel.hathitrust.org/cgi/pt?id=mdp.39015042182054",
      "rightsCode": "ic",
      "usRightsString": "Limited (search-only)",
      "lastUpdate": "20240115",
      "enumcron": false
    }
  ]
}
```

Key fields:
- **`rightsCode`**: `pd` = public domain (full text available), `ic` = in-copyright (search only)
- **`usRightsString`**: `"Full View"` or `"Limited (search-only)"`
- **`itemURL`**: Direct link to the HathiTrust page-turner viewer
- **`enumcron`**: Volume/issue info (e.g., `"vol. 3"`) or `false`

## Python Script

Use `scripts/hathitrust_api.py` for programmatic access (zero dependencies):

```python
from scripts.hathitrust_api import HathiTrustAPI
ht = HathiTrustAPI()

# Single lookup
record = ht.lookup_isbn("0140449264")

# Multiple identifiers at once
results = ht.batch_lookup([
    ("isbn", "0140449264"),
    ("oclc", "228668653"),
    ("lccn", "96017900"),
])

# Get full MARC-XML
record = ht.lookup_isbn("0140449264", full=True)
marc = ht.get_marc_xml(record)

# Check if digitized and accessible
for item in ht.get_items(record):
    print(f"{item['orig']}: {item['usRightsString']} — {item['itemURL']}")

# Summarize
print(ht.summarize(record))
```

## Typical Workflow: Cross-Reference with Other Catalogs

```python
# 1. Search Harvard for a title
from harvard_api import HarvardLibraryAPI
harvard = HarvardLibraryAPI()
results = harvard.search(title="dream of the red chamber")
isbn = harvard.get_identifiers(results[0]).get("isbn")

# 2. Check HathiTrust for digital version
from hathitrust_api import HathiTrustAPI
ht = HathiTrustAPI()
record = ht.lookup_isbn(isbn)
if record and ht.has_full_view(record):
    print("Full text available:", ht.get_items(record)[0]["itemURL"])
```

## API Etiquette

- No authentication required
- No documented rate limit, but the API is meant for small-batch lookups (not bulk harvesting)
- Use HathiFiles or OAI-PMH for bulk data
- CORS is fully enabled (`access-control-allow-origin: *`)

## Related Skills

- **harvard-library-catalog**: Search Harvard's catalog to find ISBNs/identifiers, then check HathiTrust for digital versions
- **wikidata-search**: Cross-reference Wikidata identifiers (P243 = OCLC) with HathiTrust holdings

## Resources

- `references/api_reference.md` — Complete API spec with all identifier types and response fields
- `scripts/hathitrust_api.py` — Python client with batch lookups, MARC extraction, and access checking
