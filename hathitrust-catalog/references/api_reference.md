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

Each spec: `<id_type>:<id_value>` (pipe-separated). The response is keyed by the spec string, e.g. `"isbn:0140268863"`.

Optional label and multi-identifier matching: `id:<label>;<type1>:<val1>;<type2>:<val2>` (semicolon-separated within a spec). The response is then keyed by `<label>`.

Do not percent-encode `/` in identifiers (the server returns 404 for `%2F`). Ark-style htids such as `ucbk.ark:/28722/h28s4k694` must keep their slashes.

## Identifier Types

| Type | Description | Normalization |
|------|-------------|---------------|
| `isbn` | ISBN-10 or ISBN-13 | Stripped to digits (+ trailing X) |
| `oclc` | OCLC number | Stripped to digits |
| `lccn` | Library of Congress Control Number | URL-encode spaces; do not encode `/` (404) |
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

Source: HathiTrust's catalog indexer, which maps each code to full view or search only
(github.com/hathitrust/hathitrust_catalog_indexer, `availability_map_ht.rb` for the US and
`availability_map_ht_intl.rb` for other countries). Checked 2026-10-26.

| Code | Meaning | Full view in US | Full view outside US |
|------|---------|-----------------|----------------------|
| `pd` | Public domain | yes | yes |
| `pdus` | Public domain in the US only | yes | no |
| `icus` | In copyright in the US only | no | yes |
| `ic-world` | In copyright, opened worldwide by the rights holder | yes | yes |
| `und-world` | Undetermined status, opened worldwide | yes | yes |
| `cc-*` (`cc-by-3.0`, `cc-by-4.0`, `cc-zero`, ...) | Creative Commons licenses | yes | yes |
| `ic` | In copyright | no | no |
| `op` | Out of print (as determined by rightsholders) | no | no |
| `orph`, `orphcand` | Orphan work / orphan candidate | no | no |
| `und` | Undetermined copyright | no | no |
| `umall`, `nobody`, `pd-pvt`, `supp` | Restricted, private, or suppressed | no | no |

`usRightsString` values: `"Full view"` (the live API uses a lowercase v) or `"Limited (search-only)"`.
It is computed for US readers, so `pdus` shows as `"Full view"`. Compare it case-insensitively.

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
