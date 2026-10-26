# MIT TIMDEX GraphQL API Reference

## Endpoint

```
POST https://timdex.mit.edu/graphql
Content-Type: application/json

{"query": "<GraphQL query>", "variables": {}}
```

- No API key. Public and documented by MIT Libraries: https://mitlibraries.github.io/timdex/
- Errors come back as HTTP 200 with an `errors` array, e.g. `Field 'callNumber' doesn't exist on type 'Holding'`.
- Schema can be explored with GraphQL introspection (`{ __type(name: "Record") { fields { name } } }`).

## Root Queries

| Query | Purpose |
|-------|---------|
| `search(...)` | Search records; returns `hits`, `records`, `aggregations` |
| `recordId(id: "alma:9936111333206761")` | One record by TIMDEX ID |
| `info`, `ping` | Service information |

## search Arguments

### Search (relevance-ranked)

| Argument | Meaning |
|----------|---------|
| `searchterm` | All searchable fields |
| `title` | Title |
| `contributors` | Author, editor, etc. |
| `subjects` | Subject terms |
| `identifiers` | ISBN, ISSN, OCLC number, DOI, etc. |
| `locations` | Place names |
| `citation` | Citation text |
| `fundingInformation` | Funder or award |
| `geobox`, `geodistance` | Geographic search (GIS records) |

### Filters (exact values; see aggregations)

| Argument | Values (examples) |
|----------|-------------------|
| `sourceFilter` | `MIT Alma`, `DSpace@MIT`, `MIT ArchivesSpace`, `Digital Collections`, `MIT GIS Resources`, `Research Databases`, `LibGuides`, `MIT Libraries Website` |
| `contentTypeFilter` | `Language material`, `Image`, `Archival materials`, ... |
| `languagesFilter` | lowercase: `chinese`, `japanese`, `english` |
| `formatFilter`, `subjectsFilter`, `contributorsFilter`, `placesFilter`, `literaryFormFilter`, `accessToFilesFilter` | from the matching aggregation |

Multiple values: sources are ORed; most other filters are ANDed.

### Options

| Argument | Meaning |
|----------|---------|
| `from` | 0-based offset (string) |
| (note) | CJK text in `title` is matched character by character (`title: "文廟"` ≈ 文 OR 廟). Use `searchterm` with `booleanType: AND` and check titles |
| `perPage` | Results per page (default 20) |
| `booleanType` | `OR` (default, any word) or `AND`. **Applies to `searchterm` only**; `title`, `subjects`, etc. ignore it |
| `queryMode` | `keyword` (default), `semantic` (vector), `hybrid` |
| `fulltext` | Include full text in search (default false) |

## Record Fields

`timdexRecordId`, `title`, `alternateTitles {kind value}`, `source`, `sourceLink`, `contentType`, `format`, `languages`, `contributors {kind value identifier affiliation mitAffiliated}`, `dates {kind value range note}`, `publishers {name date location}`, `edition`, `physicalDescription`, `summary`, `subjects {kind value}`, `identifiers {kind value}`, `callNumbers`, `holdings {location collection callnumber format notes summary}`, `links {kind url text restrictions}`, `notes {kind value}`, `citation`, `rights {description kind uri}`, `relatedItems`, `locations {kind value geoshape}`, `fileFormats`, `numbering`, `publicationFrequency`, `literaryForm`, `fundingInformation`.

Note the casing: `holdings.callnumber` (lowercase n), `publishers.location` (not `place`). `subjects.value` and `notes.value` are lists.

## Aggregations

```graphql
aggregations {
  source { key docCount }
  contentType { key docCount }
  languages { key docCount }
  format { key docCount }
  subjects { key docCount }
  contributors { key docCount }
  places { key docCount }
  literaryForm { key docCount }
  accessToFiles { key docCount }
}
```

Keys are lowercase (`mit alma`); filters accept the display form (`MIT Alma`).

## Examples

```graphql
{ search(searchterm: "明史", perPage: 5) { hits records { title sourceLink } } }

{ search(title: "Ming", subjects: "China", sourceFilter: "MIT Alma", languagesFilter: "chinese") {
    hits records { title publishers { name date location } holdings { collection callnumber } } } }

{ search(searchterm: "Ming dynasty painting", queryMode: "semantic") { hits records { title source } } }

{ recordId(id: "alma:9936111333206761") { title identifiers { kind value } } }
```

## Record Links

`sourceLink` points to the public page: Primo (`mit.primo.exlibrisgroup.com`) for Alma records, `dspace.mit.edu/handle/...`, `archivesspace.mit.edu/...`, or `dome.mit.edu/handle/...` for digital collections.

## Etiquette

- One request per second; back off on HTTP 429/503 with `Retry-After`.
- Set a descriptive `User-Agent`.
