---
name: nlb-singapore
description: Search the National Library Board (NLB) Singapore catalog for books, audiovisual materials, and digital resources via the official Catalogue API. Use this skill whenever the user wants to search Singapore's national library holdings, check book availability across NLB branches, look up titles by ISBN/BRN, find new arrivals, browse checkout trends, or retrieve detailed bibliographic records from NLB. Triggers when referencing Singapore library collections, Southeast Asian library holdings, or NLB resources.
version: 1.0.0
---

# NLB Singapore Catalogue API Skill

Search and retrieve bibliographic records from Singapore's National Library Board catalog.

## Critical: Things Claude Won't Know Without This Skill

### API key is required — two headers on every request

The NLB API requires both an API key and an app code:

```
X-API-KEY: your-api-key
X-APP-Code: your-app-code
```

Without these, all endpoints return 401. Apply for free keys at https://go.gov.sg/nlblabs-form (contact: nlblabs@nlb.gov.sg).

Set environment variables `NLB_API_KEY` and `NLB_APP_CODE`, or pass them to the Python client constructor.

### Two search endpoints with different strengths

| Endpoint | Best for | Returns |
|----------|----------|---------|
| `SearchTitles` | Keyword search with facets and filters | Title summaries + facets |
| `GetTitles` | Field-specific search (title, author, subject, ISBN) | Full title records |

```
SearchTitles: ?Keywords=singapore+history&Limit=10
GetTitles:    ?Title=singapore&Author=lee&Limit=10
```

### BRN is the primary record identifier

BRN (Bibliographic Record Number) is NLB's internal ID. Use it for `GetTitleDetails` and `GetAvailabilityInfo` lookups. Found in search results under `records[].brn` or `brn`.

### Native language fields for CJK content

Most text fields have native-language variants: `title`/`nativeTitle`, `author`/`nativeAuthor`, `seriesTitle`/`nativeSeriesTitle`. Always check both for Chinese, Malay, and Tamil titles.

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /SearchTitles` | Keyword search with facets and filters |
| `GET /GetTitles` | Field-specific search (title, author, subject, ISBN) |
| `GET /GetTitleDetails` | Full record by BRN or ISBN |
| `GET /GetAvailabilityInfo` | Check availability across branches |
| `GET /GetNewTitles` | Browse new arrivals |
| `GET /GetMostCheckoutsTrendsTitles` | Checkout trends by branch |

## Key Search Parameters

### SearchTitles

| Param | Description | Example |
|-------|-------------|---------|
| `Keywords` | Search keywords (required) | `Keywords=singapore+history` |
| `Limit` | Results per page (default 20, max 100) | `Limit=20` |
| `Offset` | Pagination offset | `Offset=20` |
| `MaterialTypes` | Filter by material type | `MaterialTypes=BOOK` |
| `Languages` | Filter by language | `Languages=Chinese` |
| `Locations` | Filter by library branch | `Locations=TRL` |
| `DateFrom` / `DateTo` | Publication year range | `DateFrom=2020&DateTo=2025` |
| `Availability` | Only available items | `Availability=true` |
| `Fiction` | Fiction filter | `Fiction=true` |

### GetTitles

| Param | Description |
|-------|-------------|
| `Keywords` | General keywords |
| `Title` | Title-specific search |
| `Author` | Author-specific search |
| `Subject` | Subject-specific search |
| `ISBN` | ISBN lookup |
| `Limit` / `Offset` | Pagination |

## Response Structure

### Search Results
```json
{
  "totalRecords": 999,
  "count": 20,
  "hasMoreRecords": true,
  "nextRecordsOffset": 20,
  "titles": [
    {
      "title": "Singapore: A Biography",
      "nativeTitle": "",
      "author": "Frost, Mark Ravinder",
      "nativeAuthor": "",
      "records": [
        {
          "brn": 13737742,
          "isbns": ["9789814385169"],
          "publisher": ["Editions Didier Millet"],
          "publishDate": "2009",
          "subjects": ["Singapore -- History"],
          "format": {"code": "BK", "name": "Books"}
        }
      ]
    }
  ],
  "facets": [...]
}
```

### Title Detail Fields

Full records include 50+ fields: `brn`, `title`, `nativeTitle`, `author`, `nativeAuthor`, `publisher`, `publishDate`, `isbns`, `subjects`, `summary`, `contents`, `edition`, `physicalDescription`, `language`, `format`, `allowReservation`, `availability`, `activeReservationsCount`.

### Availability Info
```json
{
  "items": [
    {
      "brn": 13737742,
      "callNumber": "959.57 FRO",
      "location": {"code": "TRL", "name": "Lee Kong Chian Reference Library"},
      "transactionStatus": {"code": "S", "name": "Available on Shelf"},
      "media": {"code": "BOOK", "name": "Book"}
    }
  ]
}
```

Transaction status codes: `S` (on shelf), `L` (on loan), `H` (on hold), `I` (in transit), `T` (transferred).

## Python Script

```python
from scripts.nlb_api import NlbAPI
nlb = NlbAPI()  # reads NLB_API_KEY and NLB_APP_CODE from env

# Keyword search
results = nlb.search("singapore history", limit=10)

# Field-specific search
results = nlb.get_titles(title="dream of the red chamber", language="Chinese")

# Title details by BRN
detail = nlb.get_title_details(brn=13737742)

# Check availability
avail = nlb.get_availability(brn=13737742)
for item in avail:
    print(f"{item['location']['name']}: {item['transactionStatus']['name']}")

# New arrivals
new = nlb.get_new_titles(date_range="Weekly", limit=20)

# Summarize
for r in results:
    print(nlb.summarize(r))
```

## Library Branch Codes

Key locations: `TRL` (Lee Kong Chian Reference Library), `WRL` (Woodlands Regional Library), `CMPL` (Chinatown Public Library), `AMKPL` (Ang Mo Kio), `BIPL` (Bishan), `JWPL` (Jurong West), `TPPL` (Tampines).

## API Etiquette

- Free API key required (apply at https://go.gov.sg/nlblabs-form)
- Rate limits enforced (429 on excess) — exact thresholds undocumented
- Data licensed under [Singapore Open Data Licence](https://data.gov.sg/open-data-licence)

## Related Skills

- **hathitrust-catalog**: Use ISBNs from NLB to check HathiTrust for digitized versions
- **wikidata-search**: Cross-reference NLB subjects with Wikidata entities

## Resources

- `references/api_reference.md` — Complete endpoint, parameter, and response field reference
- `scripts/nlb_api.py` — Python client with search, lookup, availability checking, and pagination
