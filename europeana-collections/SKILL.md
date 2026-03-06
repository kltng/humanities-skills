---
name: europeana-collections
description: Search Europeana's 50M+ cultural heritage items from 4,000+ European museums, galleries, libraries, and archives. Use this skill whenever the user wants to find European art, manuscripts, photographs, maps, 3D objects, audio, or video from institutions like the Rijksmuseum, British Library, Louvre, or Gallica. Also triggers when searching for open-access European cultural heritage, IIIF resources, or cross-referencing European collections with other library catalogs.
version: 1.0.0
---

# Europeana Collections API Skill

Search 50M+ cultural heritage items from 4,000+ European institutions.

## Critical: Things Claude Won't Know Without This Skill

### API key is required — use `api2demo` for testing

Every request needs a `wskey` parameter. The demo key `api2demo` works for development/testing. For production use, register for a free key at https://www.europeana.eu/en/account/api-keys.

```
https://api.europeana.eu/record/v2/search.json?query=vermeer&wskey=api2demo
```

### Response fields use Dublin Core / EDM naming

Fields are prefixed with `dc` (Dublin Core) or `edm` (Europeana Data Model):
- `title` — array of title strings
- `dcCreator` — creator names
- `dcDescription` — descriptions
- `year` — year(s) as strings
- `country` — country of holding institution
- `dataProvider` — institution name (e.g., "Rijksmuseum")
- `rights` — license URL
- `edmPreview` — thumbnail URL
- `edmIsShownAt` — link to item on provider's site
- `type` — `IMAGE`, `TEXT`, `SOUND`, `VIDEO`, `3D`

### Filter for open-access with `reusability=open`

```
?query=vermeer&reusability=open
```

Returns only items with open licenses (Public Domain, CC0, CC BY, CC BY-SA).

### Multilingual titles use `LangAware` suffix

`dcTitleLangAware` contains titles keyed by language code:
```json
{"en": ["The Milkmaid"], "nl": ["Het melkmeisje"]}
```

## Key Search Parameters

| Param | Description | Example |
|-------|-------------|---------|
| `query` | Search query (Lucene syntax) | `query=vermeer` |
| `qf` | Query filter (field:value) | `qf=TYPE:IMAGE` |
| `reusability` | License filter: `open`, `restricted`, `permission` | `reusability=open` |
| `media` | Has media (`true`/`false`) | `media=true` |
| `rows` | Results per page (max 100) | `rows=20` |
| `start` | Result offset (1-based) | `start=21` |
| `sort` | Sort field | `sort=score+desc` |
| `wskey` | API key (required) | `wskey=api2demo` |
| `profile` | Response detail: `minimal`, `standard`, `rich` | `profile=rich` |

### Query Filters (`qf=`)

| Filter | Values |
|--------|--------|
| `TYPE` | `IMAGE`, `TEXT`, `SOUND`, `VIDEO`, `3D` |
| `COUNTRY` | Country name (e.g., `Netherlands`) |
| `LANGUAGE` | ISO code (e.g., `en`, `nl`, `de`) |
| `PROVIDER` | Provider name |
| `DATA_PROVIDER` | Institution name |
| `RIGHTS` | License URL |
| `what` | Subject/keyword |
| `where` | Place |
| `when` | Time period |

Multiple filters: repeat `qf=` parameter.

## Record Lookup

```
https://api.europeana.eu/record/v2/{RECORD_ID}.json?wskey=api2demo
```

Record IDs look like `/15502/GG_9128` (from the `id` field in search results).

## Response Structure

```json
{
  "success": true,
  "totalResults": 1573,
  "items": [
    {
      "id": "/90402/SK_A_2344",
      "title": ["The Milkmaid", "Het melkmeisje"],
      "dcCreator": ["Johannes Vermeer"],
      "year": ["1660"],
      "country": ["Netherlands"],
      "dataProvider": ["Rijksmuseum"],
      "type": "IMAGE",
      "rights": ["http://creativecommons.org/publicdomain/mark/1.0/"],
      "edmPreview": ["https://api.europeana.eu/thumbnail/v2/..."],
      "edmIsShownAt": ["http://hdl.handle.net/..."],
      "edmIsShownBy": ["https://lh3.googleusercontent.com/..."],
      "score": 20.9
    }
  ]
}
```

## Python Script

```python
from scripts.europeana_api import EuropeanaAPI
eu = EuropeanaAPI()  # uses api2demo key by default

# Basic search
results = eu.search("vermeer")

# Filtered search
results = eu.search("medieval manuscript", type="TEXT", country="France", reusability="open")

# Get single record
record = eu.get_record("/15502/GG_9128")

# Summarize
for r in results:
    print(eu.summarize(r))
```

## API Etiquette

- Free API key required (register at europeana.eu)
- Demo key `api2demo` for testing only
- No published rate limit for free keys; project keys available for higher throughput
- Include descriptive User-Agent header

## Related Skills

- **wikidata-search**: Cross-reference Europeana items with Wikidata entities
- **harvard-library-catalog**: Compare European holdings with Harvard's collection
- **loc-catalog**: Cross-reference with Library of Congress digitized collections

## Resources

- `references/api_reference.md` — Complete query filter and response field reference
- `scripts/europeana_api.py` — Python client with search, record lookup, and open-access filtering
