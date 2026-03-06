# Europeana Collections API Reference

## Base URL

`https://api.europeana.eu/record/v2`

## Authentication

Required: `wskey` parameter on every request.
- Demo key: `api2demo` (testing only)
- Free production key: https://www.europeana.eu/en/account/api-keys

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/search.json` | Search across all collections |
| `/{record_id}.json` | Get single record by Europeana ID |

## Search Parameters

| Param | Description | Example |
|-------|-------------|---------|
| `query` | Search query (Lucene syntax) | `query=vermeer` |
| `qf` | Query filter (repeatable) | `qf=TYPE:IMAGE` |
| `reusability` | License: `open`, `restricted`, `permission` | `reusability=open` |
| `media` | Has media: `true`/`false` | `media=true` |
| `rows` | Results per page (max 100) | `rows=20` |
| `start` | Offset (1-based) | `start=21` |
| `sort` | Sort field | `sort=score+desc` |
| `profile` | Detail level: `minimal`, `standard`, `rich` | `profile=rich` |
| `wskey` | API key (required) | `wskey=api2demo` |

## Query Filters (`qf=`)

| Filter | Example Values |
|--------|---------------|
| `TYPE` | `IMAGE`, `TEXT`, `SOUND`, `VIDEO`, `3D` |
| `COUNTRY` | `Netherlands`, `France`, `Germany` |
| `LANGUAGE` | `en`, `nl`, `de`, `fr` |
| `PROVIDER` | Provider name |
| `DATA_PROVIDER` | Institution name (e.g., `Rijksmuseum`) |
| `RIGHTS` | License URL |
| `what` | Subject/keyword |
| `where` | Place name |
| `when` | Time period |

## Response Fields

### Search Result Item

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Europeana record ID (e.g., `/90402/SK_A_2344`) |
| `title` | array | Title strings |
| `dcTitleLangAware` | object | Titles by language code |
| `dcCreator` | array | Creator names (may include URIs) |
| `dcCreatorLangAware` | object | Creators by language |
| `dcDescription` | array | Descriptions |
| `dcDescriptionLangAware` | object | Descriptions by language |
| `year` | array | Year strings |
| `country` | array | Country of holding institution |
| `dataProvider` | array | Institution name |
| `provider` | array | Aggregator name |
| `type` | string | `IMAGE`, `TEXT`, `SOUND`, `VIDEO`, `3D` |
| `rights` | array | License URL(s) |
| `edmPreview` | array | Thumbnail URL(s) |
| `edmIsShownAt` | array | Item on provider's website |
| `edmIsShownBy` | array | Direct media URL |
| `edmPlaceLabel` | array | Place labels |
| `edmPlaceLatitude` | array | Latitude |
| `edmPlaceLongitude` | array | Longitude |
| `edmTimespanLabel` | array | Time period labels |
| `edmConceptLabel` | array | Concept/subject labels |
| `language` | array | Language codes |
| `score` | float | Relevance score |

### Reusability Values

| Value | Licenses included |
|-------|-------------------|
| `open` | Public Domain, CC0, CC BY, CC BY-SA |
| `restricted` | CC BY-NC, CC BY-NC-SA, CC BY-NC-ND, CC BY-ND |
| `permission` | Rights reserved, in-copyright |

## Pagination

- `rows`: max 100 per page
- `start`: 1-based offset
- `totalResults` in response gives total count

## Rate Limits

- No published limit for free keys
- Project keys available for higher throughput
- Be respectful: 1 request/second recommended
