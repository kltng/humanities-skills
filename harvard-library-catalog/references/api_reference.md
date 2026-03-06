# Harvard Library API Reference

## LibraryCloud Item API

**Base URL**: `https://api.lib.harvard.edu/v2/items`

### Query Syntax

Field-based search uses **query parameters** (NOT Solr `field:value` syntax):

```
https://api.lib.harvard.edu/v2/items.json?title=hamlet&name=shakespeare
```

The `q=` parameter searches across all fields:

```
https://api.lib.harvard.edu/v2/items.json?q=Chinese+porcelain+Ming+dynasty
```

Combine `q=` with field params:

```
https://api.lib.harvard.edu/v2/items.json?q=university+AND+choir&sort=source
```

### Boolean Operators

- `AND`, `OR`, `NOT` (uppercase) within `q=` parameter
- Parentheses for grouping: `q=(electronic finding aid available) OR (container list)`

### Wildcards

- `*` for wildcard: `title=peanut*`, `title=p*nut`

### Exact Match

Append `_exact` to field name (case-sensitive):

```
https://api.lib.harvard.edu/v2/items.json?title_exact=Peanuts
```

### Response Format

| Extension | Format |
|-----------|--------|
| (none) | MODS XML (default) |
| `.json` | MODS JSON |
| `.dc` | Dublin Core XML |
| `.dc.json` | Dublin Core JSON |

### Pagination

| Parameter | Description | Default |
|-----------|-------------|---------|
| `limit` | Results per page (0-250) | 10 |
| `start` | Offset for start-based pagination | 0 |
| `cursor` | Use `*` for first page, then `nextCursor` value | — |

Start-based: scales to ~30K results. Cursor-based: scales to 100K.

### Sorting

| Parameter | Description |
|-----------|-------------|
| `sort` or `sort.asc` | Ascending sort by field |
| `sort.desc` | Descending sort by field |

Default: relevancy. See field reference for sortable fields.

### Facets

| Parameter | Description |
|-----------|-------------|
| `facets` | Comma-separated field names |
| `facet_size` | Max facet values per field (1-100, default 10) |

### Rate Limit

300 requests per 5 minutes, max 1/second. Exceeding triggers 5-minute lockout.

---

## Complete Field Reference

### Core Search Fields

| Field | Exact Match | Can Facet | Alpha Sort | Notes |
|-------|:-----------:|:---------:|:----------:|-------|
| `q` | — | — | — | Keyword search across all fields |
| `title` | Yes | No | No | titleInfo: title, subtitle, partName, partNumber |
| `name` | No | Yes | No | All name fields (author, editor, contributor) |
| `subject` | Yes | Yes | No | All subject fields (topic, geographic, temporal, name) |
| `identifier` | Yes | No | No | ISBN, LCCN, other system IDs |
| `genre` | Yes | Yes | No | Genre/form terms |
| `languageCode` | Yes | Yes | No | ISO 639-2 code (e.g., `chi`, `eng`, `ger`) |
| `languageText` | Yes | Yes | No | Language name text (e.g., "Chinese") |
| `dateIssued` | Yes | Yes | No | Publication date (YYYY) |
| `dateCreated` | Yes | Yes | No | Creation date |
| `copyrightDate` | Yes | Yes | No | Copyright date (YYYY) |
| `originDate` | Yes | Yes | No | Any origin date field |
| `originPlace` | Yes | Yes | No | Place of publication |
| `publisher` | Yes | Yes | No | Publisher name |
| `edition` | Yes | Yes | No | Edition statement |
| `dates.start` | — | — | — | Filter: items from this date forward |
| `dates.end` | — | — | — | Filter: items up to this date |

### Subject Sub-fields

| Field | Exact Match | Can Facet |
|-------|:-----------:|:---------:|
| `subject.topic` | Yes | Yes |
| `subject.geographic` | Yes | Yes |
| `subject.temporal` | Yes | Yes |
| `subject.name` | Yes | Yes |
| `subject.genre` | Yes | Yes |
| `subject.titleInfo` | Yes | Yes |
| `subject.hierarchicalGeographic` | Yes | No |
| `subject.hierarchicalGeographic.country` | Yes | Yes |
| `subject.hierarchicalGeographic.state` | Yes | Yes |
| `subject.hierarchicalGeographic.city` | Yes | Yes |
| `subject.hierarchicalGeographic.continent` | Yes | Yes |
| `subject.hierarchicalGeographic.region` | Yes | Yes |
| `subject.hierarchicalGeographic.province` | Yes | Yes |

### Access & Location Fields

| Field | Exact Match | Can Facet | Notes |
|-------|:-----------:|:---------:|-------|
| `recordIdentifier` | Yes | No | HOLLIS/Alma/OASIS record ID |
| `repository` | Yes | Yes | Harvard library name |
| `physicalLocation` | No | Yes | Location including non-Harvard |
| `shelfLocator` | Yes | Yes | Call number / shelf location |
| `source` | No | Yes | `MH:ALMA`, `MH:VIA`, `MH:OASIS` |
| `classification` | Yes | Yes | Bibliographic classification |
| `isOnline` | No | Yes | `true`/`false` — has digital version |
| `isCollection` | Yes | Yes | `true`/`false` — describes a collection |
| `isManuscript` | Yes | Yes | `true`/`false` — manuscript/archival |
| `resourceType` | Yes | Yes | Type of resource |
| `issuance` | Yes | Yes | e.g., `serial`, `monographic` |
| `role` | Yes | Yes | Name role (e.g., `publisher`, `editor`) |
| `url` | Yes | No | URLs/URNs in record |
| `urn` | No | No | NRS URN lookup |

### Collection Fields

| Field | Can Facet | Notes |
|-------|:---------:|-------|
| `collectionId` | Yes | Digital collection system ID |
| `collectionTitle` | Yes | Digital collection title |
| `seriesTitle` | Yes | Series title (facet as `relatedItem`) |
| `setName` | Yes | Curated set name |
| `setSpec` | Yes | Curated set code |

### DRS (Digital Repository) Extensions

Only valid when `inDRS=true`:

| Field | Notes |
|-------|-------|
| `inDRS` | `true`/`false` |
| `accessFlag` | `P` (public), `R` (Harvard), `N` (unavailable) |
| `availableTo` | `Everyone` or `Harvard only` |
| `contentModel` | `AUDIO`, `DOCUMENT`, `STILL IMAGE`, `TEXT`, `VIDEO`, etc. |
| `digitalFormat` | `audio`, `books and documents`, `images`, `video` |
| `drsFileId` | DRS file identifier |
| `drsObjectId` | DRS object identifier |
| `ownerCode` | e.g., `FHCL.HOUGH` |
| `uriType` | `FDS`, `IDS`, `PDS`, `SDS`, `SDS_VIDEO` |
| `modified.after` | YYYY-MM-DD |
| `modified.before` | YYYY-MM-DD |

---

## LibraryCloud Collections API

**Base URL**: `https://api.lib.harvard.edu/v2/collections`

Browse curated collections. Returns set metadata (title, description, item count).

---

## PRESTO Data Lookup

**Base URL**: `https://webservices.lib.harvard.edu/rest`

Direct record lookup by HOLLIS ID. Returns XML only.

### Endpoints

| Format | URL Pattern |
|--------|-------------|
| MARC XML | `/rest/marc/hollis/{HOLLIS_ID}` |
| MODS XML | `/rest/mods/hollis/{HOLLIS_ID}` |
| Dublin Core | `/rest/dc/hollis/{HOLLIS_ID}` |

### HOLLIS ID Formats

- Legacy Aleph format: `011557057` (9 digits)
- Alma format: `990115570570203941` (18 digits)

Both formats work with PRESTO.

### Notes

- PRESTO returns XML only (no JSON option)
- ISBN and barcode lookups (`/rest/marc/isbn/{isbn}`) may not work for all records
- Use LibraryCloud `identifier=` search for more reliable ISBN lookups
