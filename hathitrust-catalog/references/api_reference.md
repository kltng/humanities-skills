# HathiTrust Bibliographic API Reference

## Base URL

`https://catalog.hathitrust.org/api/volumes/`

## Endpoints

### Single-ID Lookup

```
GET /api/volumes/brief/<id_type>/<id_value>.json
GET /api/volumes/full/<id_type>/<id_value>.json
```

`brief` returns metadata + items. `full` adds complete MARC-XML.

### Multi-ID Lookup (max 20)

```
GET /api/volumes/brief/json/<spec1>|<spec2>|...|<specN>
GET /api/volumes/full/json/<spec1>|<spec2>|...|<specN>
```

Each spec: `id:<id_type>:<id_value>` (pipe-separated).

For multi-identifier matching: `id:<type1>:<val1>;<type2>:<val2>` (semicolon-separated within a spec).

## Identifier Types

| Type | Description | Normalization |
|------|-------------|---------------|
| `isbn` | ISBN-10 or ISBN-13 | Stripped to digits (+ trailing X) |
| `oclc` | OCLC number | Stripped to digits |
| `lccn` | Library of Congress Control Number | URL-encode spaces/slashes |
| `issn` | ISSN | Stripped to digits |
| `htid` | HathiTrust volume ID | e.g., `mdp.39015058510069` |
| `recordnumber` | 9-digit HathiTrust record number | e.g., `009058846` |

## Response Format

JSON only. JSONP via `?callback=functionName`. CORS enabled.

### Response Structure

```json
{
  "records": {
    "<record_number>": {
      "recordURL": "https://catalog.hathitrust.org/Record/<number>",
      "titles": ["Title string"],
      "isbns": ["0140268863", "9780140268867"],
      "issns": [],
      "oclcs": ["34228839"],
      "lccns": ["96017900"],
      "publishDates": ["1997"],
      "marc-xml": "<MARC-XML string>"
    }
  },
  "items": [
    {
      "orig": "University of Michigan",
      "fromRecord": "009058846",
      "htid": "mdp.39015042182054",
      "itemURL": "https://babel.hathitrust.org/cgi/pt?id=mdp.39015042182054",
      "rightsCode": "ic",
      "lastUpdate": "20240115",
      "enumcron": false,
      "usRightsString": "Limited (search-only)"
    }
  ]
}
```

### Empty Results

Returns HTTP 200 with `{"records": {}, "items": []}`.

## Rights Codes

| Code | Meaning |
|------|---------|
| `pd` | Public domain — full text available |
| `ic` | In-copyright — search only |
| `op` | Out of print (as determined by rightsholders) |
| `orph` | Orphaned work |
| `und` | Undetermined copyright |
| `cc-by`, `cc-by-sa`, etc. | Creative Commons licenses |

`usRightsString` values: `"Full View"` or `"Limited (search-only)"`.

## Authentication & Rate Limits

- **Auth**: None required
- **Rate limits**: No documented limits, but intended for small-batch lookups
- **Bulk data**: Use HathiFiles or OAI-PMH instead
- **CORS**: Fully open (`access-control-allow-origin: *`)

## Other HathiTrust APIs

| API | Purpose | Auth |
|-----|---------|------|
| Bibliographic API (this) | Identifier-based record lookup | None |
| Data API | Page images, OCR text | OAuth 1.0a |
| OAI-PMH | Bulk metadata harvesting | None |
| HathiFiles | Full inventory (tab-delimited) | None (download) |
