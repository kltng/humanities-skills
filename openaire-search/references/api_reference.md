# OpenAIRE Graph API Reference (v3)

Base URL: `https://api.openaire.eu/graph/v3`. JSON responses. No API key. Tested October 2026.

Versions: v1 and v2 are deprecated; v4 (`/graph/v4/...`, "unified filters") is in beta and has no fetch-by-ID route. This skill uses v3. OpenAPI spec: `https://api.openaire.eu/graph/v3/api-docs/OpenAIRE%20Graph%20API%20V3`.

## Limits and terms

- Anonymous: up to 60 requests/hour (terms of use). Authenticated: up to 7,200/hour.
- Response headers `x-ratelimit-limit` and `x-ratelimit-used` show the current count. In October 2026 anonymous calls showed `x-ratelimit-limit: 7199`.
- Token: register at https://develop.openaire.eu, create a personal access token (valid one hour), send `Authorization: Bearer <token>`.
- Data license: CC-BY. Credit OpenAIRE as the source.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /research-products` | Search publications, datasets, software, other |
| `GET /research-products/{id}` | One product. 404 `Research product with id: ... not found` |
| `GET /projects`, `/projects/{id}` | Funded projects |
| `GET /organizations`, `/organizations/{id}` | Organizations |
| `GET /datasources`, `/datasources/{id}` | Repositories, journals, archives |
| `GET /persons`, `/persons/{id}` | Authors |
| `GET /research-products/links` | Scholix citation/relation links (returned 503 "Upstream service is currently unavailable" in October 2026) |

## Common parameters

| Parameter | Meaning |
|---|---|
| `search` | Keywords. `AND`, `OR`, `NOT` in uppercase; `"exact phrase"`; parentheses |
| `page`, `pageSize` | 1-based page; pageSize default 10, max 100; `page * pageSize <= 10000` (else 400 `Page * pageSize must be less than or equal to 10000`) |
| `cursor` | `*` to start, then `header.nextCursor` |
| `sortBy` | `field ASC|DESC`; fields: relevance, publicationDate, dateOfCollection, influence, popularity, citationCount, impulse |
| `logicalOperator` | how field parameters combine: `AND` (default), `OR`, `NOT` |

Filter values with spaces or parentheses must be in double quotes: `accessRightLabel="Open Access"`. Without quotes: 400 `Values containing spaces, parentheses or logical operators must be wrapped in double quotes`. Most filters accept `AND`/`OR`/`NOT`: `type=("publication" OR "dataset") AND NOT "other"`.

## Research-product filters

| Parameter | Values / notes |
|---|---|
| `mainTitle`, `description` | text, operators allowed |
| `authorFullName`, `authorId` | name (phrase in quotes), ORCID |
| `type` | `publication`, `dataset`, `software`, `other` |
| `instanceType` | `"Doctoral thesis"`, `"Master thesis"`, `Article`, `Book`, `"Part of book or chapter of book"`, `"Conference object"`, `Preprint`, `Dataset`, ... (vocabulary: https://api.openaire.eu/vocabularies/dnet:publication_resource) |
| `accessRightLabel` | `Open Access`, `Closed Access`, `Restricted`, `Open Source`, `Embargo`, `Unknown` |
| `openAccessColor` | `bronze`, `gold`, `hybrid` (publications only) |
| `isPeerReviewed`, `isGreen`, `isInDiamondJournal`, `isPubliclyFunded`, `hasLicense` | `true` / `false` |
| `fromPublicationDate`, `toPublicationDate` | `YYYY` or `YYYY-MM-DD` |
| `publicationYear`, `fromPublicationYear`, `toPublicationYear` | years |
| `language` | e.g. `Chinese`, `English`, `("German" OR "French")` |
| `countryCode` | e.g. `TW`, `HK`, `CN` |
| `subjects`, `fos`, `sdgLabel` | subject text; Field of Science label or id |
| `publisher` | text |
| `pid`, `originalId`, `id` | DOI or other identifier; OpenAIRE id |
| `relOrganization`, `relOrganizationId`, `rorId` | organization name, OpenAIRE id, ROR. For The University of Hong Kong both name and id returned 0 results with `"明代"`; prefer the repository id |
| `relHostingDataSourceId`, `relCollectedFromDatasourceId` | repository OpenAIRE id (find it via `/datasources`). The name forms `relHostingDataSource` and `source` returned 0 results in tests |
| `relProject`, `relProjectId`, `relProjectCode`, `relFunder`, `hasProjectRel` | projects and funders |
| `relCommunityId`, `relCommunityName` | OpenAIRE research communities |
| `influenceClass`, `popularityClass`, `impulseClass`, `citationCountClass` | `C1` (top 0.01%) … `C5` (average) |
| `includeStats` | `true` adds result statistics to the response headers |

Other entities take their own parameters, e.g. organizations: `legalName`, `legalShortName`, `countryCode`, `pid`; datasources: `officialName`, `englishName`, `dataSourceTypeName`, `country`, `subjects`; projects: `title`, `keywords`, `code`, `acronym`, `fundingShortName`, `fromStartDate`, `relOrganizationName`.

## Response

```json
{"header": {"numFound": 49, "maxScore": 9.5, "queryTime": 202, "page": 1, "pageSize": 4, "nextCursor": "..."},
 "results": [ ... ]}
```

Errors: `{"message": "...", "error": "Bad Request", "code": 400, ...}`.

## Research-product fields

| Field | Notes |
|---|---|
| `id` | e.g. `doi_dedup___::5619fd1b...` (merged record) or `od_______961::...` |
| `type` | publication, dataset, software, other |
| `mainTitle`, `subTitle`, `otherTitles` | |
| `authors` | `[{"fullName", "name", "surname", "rank", "pid"}]` |
| `publicationDate`, `publisher`, `language` (`{"code", "label"}`), `countries` | |
| `descriptions` | list; may contain JATS tags |
| `subjects` | `[{"subject": {"scheme": "FOS", "value": "0601 history and archaeology"}}]` |
| `pids` | `[{"scheme": "doi", "value": "..."}]`, also handle, pmid, arXiv |
| `bestAccessRight` | `{"code": "c_abf2", "label": "OPEN"}` |
| `openAccessColor`, `isGreen`, `isInDiamondJournal`, `publiclyFunded` | |
| `container` | journal: `name`, `issnPrinted`, `issnOnline`, `vol`, `iss`, `sp`, `ep` |
| `indicators.citationImpact` | `citationCount`, `influence`, `popularity`, `impulse`, and their classes |
| `instances` | each copy: `type`, `urls`, `hostedBy` (`{"key", "value"}`), `accessRight` (`label`, `openAccessRoute`), `license`, `refereed`, `publicationDate`, `collectedFrom` |
| `collectedFrom` | sources merged into this record |
| `projects`, `organizations`, `communities` | related entities |

Instance URLs can be malformed (`https://doi.org/https://doi.org/10.5353/...`) or duplicated with `dx.doi.org`; the script cleans and merges them.

## Examples

```bash
curl -G "https://api.openaire.eu/graph/v3/research-products" \
  --data-urlencode 'search="Ming dynasty"' \
  --data-urlencode 'instanceType="Doctoral thesis"' \
  --data-urlencode 'accessRightLabel="Open Access"' \
  --data-urlencode pageSize=10

curl -G "https://api.openaire.eu/graph/v3/research-products" --data-urlencode 'pid=10.2307/2057472'

curl -G "https://api.openaire.eu/graph/v3/datasources" --data-urlencode 'search="HKU Scholars Hub"'
```
