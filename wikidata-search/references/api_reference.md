# Wikidata API Reference

Detailed documentation for Wikidata API endpoints.

## wbsearchentities

Search for entities by label or alias.

### Endpoint
```
GET https://www.wikidata.org/w/api.php?action=wbsearchentities
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| search | Yes | - | Search term |
| language | Yes | - | Language code for search and results |
| type | No | item | Entity type: `item`, `property`, `lexeme` |
| limit | No | 7 | Max results (1-50) |
| continue | No | 0 | Pagination offset |
| strictlanguage | No | false | Only return results in exact language |
| uselang | No | language | Language for result labels/descriptions |
| profile | No | default | Search profile: `default`, `language` |

### Response

```json
{
  "searchinfo": {"search": "query_string"},
  "search": [
    {
      "id": "Q42",
      "title": "Q42",
      "pageid": 138,
      "repository": "wikidata",
      "url": "//www.wikidata.org/wiki/Q42",
      "concepturi": "http://www.wikidata.org/entity/Q42",
      "label": "Douglas Adams",
      "description": "English writer and humorist",
      "match": {
        "type": "label",
        "language": "en",
        "text": "Douglas Adams"
      },
      "aliases": ["Douglas Noël Adams"]
    }
  ],
  "search-continue": 7,
  "success": 1
}
```

## wbgetentities

Get full data for one or more entities.

### Endpoint
```
GET https://www.wikidata.org/w/api.php?action=wbgetentities
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| ids | Yes* | - | Pipe-separated entity IDs (max 50) |
| sites | Yes* | - | Site identifier (use with titles) |
| titles | Yes* | - | Page titles (use with sites) |
| props | No | all | Pipe-separated: `info`, `sitelinks`, `sitelinks/urls`, `aliases`, `labels`, `descriptions`, `claims`, `datatype` |
| languages | No | all | Filter languages (pipe-separated) |
| languagefallback | No | false | Use fallback languages |
| normalize | No | false | Normalize titles |
| sitefilter | No | - | Filter sitelinks by site |
| redirects | No | yes | Resolve redirects |

*One of `ids` or `sites+titles` is required.

### Response

```json
{
  "entities": {
    "Q42": {
      "type": "item",
      "id": "Q42",
      "labels": {
        "en": {"language": "en", "value": "Douglas Adams"}
      },
      "descriptions": {
        "en": {"language": "en", "value": "English writer and humorist"}
      },
      "aliases": {
        "en": [
          {"language": "en", "value": "Douglas Noël Adams"}
        ]
      },
      "claims": {
        "P31": [{
          "mainsnak": {
            "snaktype": "value",
            "property": "P31",
            "datatype": "wikibase-item",
            "datavalue": {
              "value": {"entity-type": "item", "numeric-id": 5, "id": "Q5"},
              "type": "wikibase-entityid"
            }
          },
          "type": "statement",
          "rank": "normal"
        }],
        "P214": [{
          "mainsnak": {
            "snaktype": "value",
            "property": "P214",
            "datatype": "external-id",
            "datavalue": {"value": "113230702", "type": "string"}
          },
          "type": "statement",
          "rank": "normal"
        }]
      },
      "sitelinks": {
        "enwiki": {
          "site": "enwiki",
          "title": "Douglas Adams",
          "badges": [],
          "url": "https://en.wikipedia.org/wiki/Douglas_Adams"
        }
      }
    }
  },
  "success": 1
}
```

## wbgetclaims

Get claims for a specific entity.

### Endpoint
```
GET https://www.wikidata.org/w/api.php?action=wbgetclaims
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| entity | Yes* | - | Entity ID |
| claim | Yes* | - | Claim GUID |
| property | No | - | Filter by property ID |
| props | No | references | Include: `references` |
| rank | No | - | Filter by rank: `deprecated`, `normal`, `preferred` |

*One of `entity` or `claim` is required.

## Common External Identifier Properties

### Authority Control

| P-ID | Name | Format Example |
|------|------|----------------|
| P214 | VIAF | 75121530 |
| P227 | GND | 118529579 |
| P244 | LCCN | n79023811 |
| P213 | ISNI | 0000 0001 2144 9326 |
| P268 | BnF | 11888092r |
| P269 | IdRef | 026927608 |
| P349 | NDL | 00621256 |
| P396 | SBN | IT\\ICCU\\CFIV\\000163 |
| P409 | NLA | 35010584 |
| P691 | NKC | jn19981000476 |
| P906 | SELIBR | 182099 |
| P950 | BNE | XX854145 |
| P1006 | NTA | 068370741 |
| P1015 | BIBSYS | 90052631 |
| P1017 | BAV | ADV10171026 |
| P1273 | CANTIC | a10468504 |

### Arts & Media

| P-ID | Name | Format Example |
|------|------|----------------|
| P345 | IMDb | nm0001354 |
| P434 | MusicBrainz artist | 0383dadf-2a4e-4d10-a46a-e9e041da8eb3 |
| P1728 | AllMusic artist | mn0000928942 |
| P1953 | Discogs artist | 29977 |
| P2019 | AllMovie artist | p6629 |

### Academic & Research

| P-ID | Name | Format Example |
|------|------|----------------|
| P496 | ORCID | 0000-0002-1825-0097 |
| P2163 | FAST | 68759 |
| P3430 | SNAC Ark | w6988027 |

### Geographic

| P-ID | Name | Format Example |
|------|------|----------------|
| P1566 | GeoNames | 2643743 |
| P402 | OSM relation | 65606 |

## Claim Structure

Claims follow this nested structure:

```
claims[PROPERTY_ID][INDEX]
  ├── mainsnak
  │   ├── snaktype: "value" | "somevalue" | "novalue"
  │   ├── property: "P31"
  │   ├── datatype: "wikibase-item" | "external-id" | "string" | ...
  │   └── datavalue
  │       ├── type: "wikibase-entityid" | "string" | "time" | ...
  │       └── value: <varies by type>
  ├── type: "statement"
  ├── rank: "preferred" | "normal" | "deprecated"
  ├── qualifiers: {...}  (optional)
  └── references: [...]  (optional)
```

### Datavalue Types

| datatype | datavalue.type | datavalue.value structure |
|----------|----------------|---------------------------|
| wikibase-item | wikibase-entityid | `{"entity-type": "item", "id": "Q5"}` |
| external-id | string | `"identifier_string"` |
| string | string | `"text_value"` |
| time | time | `{"time": "+1952-03-11T00:00:00Z", "precision": 11, ...}` |
| quantity | quantity | `{"amount": "+42", "unit": "1"}` |
| monolingualtext | monolingualtext | `{"text": "value", "language": "en"}` |
| url | string | `"https://example.com"` |
| globe-coordinate | globecoordinate | `{"latitude": 51.5, "longitude": -0.1, ...}` |

## Error Handling

Common error codes:

| Code | Message |
|------|---------|
| no-such-entity | Could not find an entity with the ID |
| param-missing | Required parameter missing |
| param-invalid | Invalid parameter value |
| too-many-entities | Too many entity IDs (max 50) |
