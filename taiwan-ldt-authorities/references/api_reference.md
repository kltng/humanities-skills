# LDT@Library API Reference

Site: https://ld.ncl.edu.tw (National Central Library of Taiwan with National Taiwan University Library)

No API key. No `robots.txt` restrictions (tested 2026-10-26).

## Reconciliation API

OpenRefine reconciliation protocol, version 0.2.

```
GET  https://ld.ncl.edu.tw/reconcile                 service manifest (types, preview, suggest)
POST https://ld.ncl.edu.tw/reconcile
     queries={"q0": {"query": "王守仁", "type": "authority", "limit": 5}}
```

Response:

```json
{"q0": {"result": [
  {"id": "/authority/114743", "name": "王守仁, 1472-1528", "score": 7.5, "match": false,
   "type": [{"name": "Personal Name", "id": "authority"}, ...]}
]}}
```

`id` is a path; prefix `https://ld.ncl.edu.tw`. Results can repeat. Types:

| Type id | Meaning |
|---------|---------|
| `authority` | Personal name |
| `authority>name`, `authority>prefname`, `authority>altname`, `authority>note` | Match only that part of the record |
| `topic` | Chinese subject heading |
| `classification` | Chinese classification entry |

Suggest and flyout services: `/suggest/entity`, `/suggest/type`, `/suggest/property`, `/flyout/entity?id=...`.

## SPARQL Endpoint

```
POST https://ld.ncl.edu.tw/fuseki/lod/query
     query=<SPARQL SELECT>
Accept: application/sparql-results+json
```

### Data model

Names and subjects use MADS/RDF (`http://www.loc.gov/mads/rdf/v1#`); classification uses SKOS.

| Property | Meaning |
|----------|---------|
| `rdf:type` | `madsrdf:Authority` plus `madsrdf:PersonalName`, `CorporateName`, `Topic`, …; `skos:Concept` for classification |
| `madsrdf:authoritativeLabel` | Preferred label, e.g. `"王守仁, 1472-1528"@en` (language tag is `@en` even for Chinese) |
| `madsrdf:hasVariant` / `madsrdf:variantLabel` | Variant names (blank nodes) |
| `madsrdf:hasSource` → `citationSource`, `citationNote`, `citationStatus` | Sources the heading was established from, with page |
| `madsrdf:note`, `madsrdf:historyNote` | Notes (often a Wikipedia URL and date) |
| `madsrdf:hasReciprocalAuthority` | Related headings (blank nodes with labels) |
| `identifiers:local` | Local id, e.g. `(ChTaNC)sh01473`, `(CYT)AC000207896` |
| `identifiers:lccn` | LCCN (usually empty) |
| `bflc:marcKey` | MARC heading, e.g. `1001 $a王守仁,$d1472-1528`, `150  $a孔廟` |
| `skos:prefLabel`, `skos:notation`, `skos:inScheme` | Classification caption, number, scheme |

### Query patterns

```sparql
PREFIX madsrdf: <http://www.loc.gov/mads/rdf/v1#>

# exact preferred label (fast: match the tagged literal)
SELECT ?s WHERE { VALUES ?l { "孔廟"@en "孔廟"@zh "孔廟" } ?s madsrdf:authoritativeLabel ?l }

# label prefix (~1-2 s)
SELECT ?s ?l WHERE { ?s madsrdf:authoritativeLabel ?l . FILTER(STRSTARTS(STR(?l), "王守仁")) } LIMIT 20

# from a variant to the authorized form (~15 s)
SELECT ?s ?l WHERE { ?s madsrdf:hasVariant/madsrdf:variantLabel ?v .
                     FILTER(STRSTARTS(STR(?v), "王陽明")) ?s madsrdf:authoritativeLabel ?l } LIMIT 5

# all variants of one record
SELECT ?v WHERE { <https://ld.ncl.edu.tw/authority/114743> madsrdf:hasVariant/madsrdf:variantLabel ?v }

# sources
SELECT ?src ?page WHERE { <https://ld.ncl.edu.tw/authority/114743> madsrdf:hasSource ?s .
                          ?s madsrdf:citationSource ?src . OPTIONAL { ?s madsrdf:citationNote ?page } }
```

Slow or failing: `FILTER(STR(?l) = "...")` over all labels (5+ s), `GROUP BY` counts over all records (time out).

## Record Pages

Each URI opens an HTML page: `https://ld.ncl.edu.tw/authority/114743`.

## Etiquette

- One request per second; back off on HTTP 429/503.
- Set a descriptive `User-Agent`.
