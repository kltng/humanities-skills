# NLB Singapore Catalogue API Reference

## Base URL

`https://openweb.nlb.gov.sg/api/v2/Catalogue`

## Authentication

Two headers required on every request:

```
X-API-KEY: your-api-key
X-APP-Code: your-app-code
```

Apply for free keys: https://go.gov.sg/nlblabs-form

## Endpoints

### GET /SearchTitles

Keyword search with facets and filters.

| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| Keywords | string | Yes | — | BRN, ISBN, title, author, or subject |
| Limit | int | No | 20 | Max 100 |
| Offset | int | No | 0 | Pagination offset |
| SortFields | string | No | — | Sort order |
| MaterialTypes | list | No | — | Code list C002 |
| Languages | list | No | — | Language filter |
| Locations | list | No | — | Library branch code (C005) |
| DateFrom | int | No | — | Publication year min |
| DateTo | int | No | — | Publication year max |
| Availability | bool | No | — | Filter available items |
| Fiction | bool | No | — | Fiction/non-fiction |
| IntendedAudiences | list | No | — | Code list C006 |

### GET /GetTitles

Field-specific search.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| Keywords | string | No* | General keywords |
| Title | string | No* | Title search |
| Author | string | No* | Author search |
| Subject | string | No* | Subject search |
| ISBN | string | No* | ISBN lookup |
| Limit | int | No | Default 20 |
| Offset | int | No | Default 0 |

*At least one search field required.

### GET /GetTitleDetails

Full record by identifier.

| Parameter | Type | Required |
|-----------|------|----------|
| BRN | int | No* |
| ISBN | string | No* |

*One required.

### GET /GetAvailabilityInfo

Check item availability across branches.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| BRN | int | No* | |
| ISBN | string | No* | |
| Limit | int | No | Default 20 |
| Offset | int | No | Default 0 |

### GET /GetNewTitles

Browse new arrivals.

| Parameter | Type | Default |
|-----------|------|---------|
| DateRange | string | "Weekly" |
| Limit | int | 200 |
| Offset | int | 0 |
| MaterialTypes | list | — |
| Languages | list | — |

### GET /GetMostCheckoutsTrendsTitles

Checkout trends by branch.

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| LocationCode | string | Yes | — |
| Duration | string | No | "past30days" |

## Response Models

### TitleSummary (SearchTitles)

```
title, nativeTitle, author, nativeAuthor,
seriesTitle, nativeSeriesTitle,
coverUrl, records[]
```

### Title Record (nested in TitleSummary)

```
brn, isbns[], publisher[], publishDate,
subjects[], format{code, name}
```

### Full Title (GetTitles / GetTitleDetails)

50+ fields including:
```
brn, digitalId, title, nativeTitle, otherTitles,
author, nativeAuthor, otherAuthors,
publisher[], publishDate, isbns[], issns[],
edition, physicalDescription, summary, contents,
subjects[], notes[], language[], audience[],
format{code, name}, serial, volumeNote, frequency,
allowReservation, isRestricted, availability,
activeReservationsCount, source
```

### Item (GetAvailabilityInfo)

```
irn, itemId, brn, callNumber, formattedCallNumber,
volumeName, language, media{code, name},
usageLevel{code, name}, location{code, name},
transactionStatus{code, name, date}
```

## Code Reference Tables

### C001 — BibFormat
BK (Books), CF (Computer Files), MP (Maps), MU (Music), MX (Mixed), VM (Visual Materials), CR (Continuing Resources)

### C002 — MaterialType
BOOK, DVD, CD, etc.

### C003 — TransactionStatus
| Code | Meaning |
|------|---------|
| S | Available on Shelf |
| L | On Loan |
| H | On Hold |
| I | In Transit |
| T | Transferred |
| SP | Shelving in Progress |

### C005 — Location (selected)
| Code | Library |
|------|---------|
| TRL | Lee Kong Chian Reference Library |
| WRL | Woodlands Regional Library |
| CMPL | Chinatown Public Library |
| AMKPL | Ang Mo Kio Public Library |
| BIPL | Bishan Public Library |
| JWPL | Jurong West Public Library |
| TPPL | Tampines Public Library |

### C006 — Audience
adult, children, youth

## Pagination

All list endpoints use:
- Request: `Limit` + `Offset`
- Response: `totalRecords`, `count`, `hasMoreRecords`, `nextRecordsOffset`
- Some endpoints return `setId` for cursor stability

## Error Codes

| Status | Meaning |
|--------|---------|
| 400 | Bad request |
| 401 | Unauthorized (missing/invalid API key) |
| 404 | Not found |
| 429 | Rate limited |
| 500 | Internal server error |

## Licensing

Free under [Singapore Open Data Licence](https://data.gov.sg/open-data-licence).
