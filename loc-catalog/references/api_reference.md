# Library of Congress API Reference

## Base URL

`https://www.loc.gov`

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/search/?fo=json` | Search across all collections |
| `/item/{id}/?fo=json` | Look up item by LCCN/ID |
| `/collections/?fo=json` | List all collections |
| `/collections/{slug}/?fo=json` | Browse a specific collection |
| `/books/?fo=json` | Format shortcut: books |
| `/photos/?fo=json` | Format shortcut: photos/prints/drawings |
| `/maps/?fo=json` | Format shortcut: maps |
| `/audio/?fo=json` | Format shortcut: sound recordings |
| `/newspapers/?fo=json` | Format shortcut: newspapers |
| `/manuscripts/?fo=json` | Format shortcut: manuscripts |
| `/film-and-videos/?fo=json` | Format shortcut: film/video |
| `/notated-music/?fo=json` | Format shortcut: notated music |

## Query Parameters

| Param | Description | Values |
|-------|-------------|--------|
| `fo` | Response format | `json`, `yaml` |
| `q` | Keyword search | Free text |
| `fa` | Facet filter(s) | `name:value`, pipe-separated for multiple |
| `c` | Results per page | 25, 50, 100, 150 |
| `sp` | Page number | Starts at 1 |
| `sb` | Sort by | `date`, `date_desc`, `title_s`, `title_s_desc`, `shelf_id`, `shelf_id_desc` |
| `dates` | Date range | `YYYY/YYYY` |
| `at` | Select attributes | Comma-separated; `at!=` to exclude |
| `all` | Include non-digitized | `true` |

## Facet Fields

`subject`, `contributor`, `location`, `language`, `original-format`, `online-format`, `partof`, `digitized`, `access-restricted`

## Search Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Item URL |
| `title` | string | Title |
| `date` | string | Date (YYYY-MM-DD or YYYY) |
| `contributor` | array | Contributor names |
| `subject` | array | Subject terms |
| `language` | array | Languages |
| `original_format` | array | Physical format |
| `online_format` | array | Digital format |
| `description` | array | Descriptions |
| `image_url` | array | Thumbnail URLs |
| `url` | string | Canonical API URL |
| `digitized` | bool | Has digital version |
| `number_lccn` | array | LCCN(s) |
| `shelf_id` | string | Call number |

## Item Detail Additional Fields

`call_number`, `created_published`, `rights`, `summary`, `stmt_of_responsibility`, `genre`, `cite_this` (with `apa`, `chicago`, `mla` sub-fields), `other_formats` (MARCXML, MODS, Dublin Core links), `resources` (download links).

## Pagination

| Field | Description |
|-------|-------------|
| `of` | Total results |
| `total` | Total pages |
| `perpage` | Results per page |
| `current` | Current page |
| `next` | URL of next page |
| `previous` | URL of previous page |

Hard limit: 100,000 results. Use facets to narrow.

## Authentication & Rate Limits

- No authentication required
- Rate limiting enforced (exact limits unpublished)
- Add User-Agent header and 0.5-1s delay between requests
