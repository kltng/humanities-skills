# Northwestern Digital Collections API (v2) Reference

Official docs: https://api.dc.library.northwestern.edu/docs/v2/index.html
OpenAPI spec: https://github.com/nulib/dc-api-v2/blob/main/docs/docs/spec/openapi.yaml

## Base URL

```
https://api.dc.library.northwestern.edu/api/v2
```

No key for public items. Institution-only items need Northwestern login (`/auth/login`).

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/search` or `/search/{models}` | Keyword search (`models` = `works`, `collections`, `file-sets`) |
| POST | `/search` or `/search/{models}` | OpenSearch DSL search (JSON body) |
| GET | `/works/{id}` | One work |
| GET | `/works/{id}?as=iiif` | IIIF Presentation manifest |
| GET | `/works/{id}/similar` | Visually/semantically similar works |
| GET | `/works/{id}/thumbnail` | Thumbnail image (`aspect`, `size`) |
| GET | `/collections`, `/collections/{id}` | Collections |
| GET | `/file-sets/{id}` | One file (image, audio, video) |
| GET | `/oai` | OAI-PMH harvesting |

## Search Parameters

| Param | Meaning |
|-------|---------|
| `query` | OpenSearch query string. **Not `q`**: `q` is ignored and returns everything. |
| `page` | 1-based page |
| `size` | Results per page |
| `sort` | e.g. `date_created:asc`, `create_date:desc`, `title.keyword:asc` |
| `_source_includes` / `_source_excludes` | Comma list of fields to include/exclude |
| `as` | `iiif` or `opensearch` output |
| `searchToken` | Continue a previous search |

Response: `{"data": [...], "pagination": {"total_hits", "current_page", "next_url", ...}, "info": {...}}`.

## Query String Syntax

```
Yungang
"Juyong Guan"
title:Beijing
work_type:Image                      (Image, Audio, Video)
subject.label:"China"
contributor.label:"Linrothe, Robert N., 1951-"
contributor.label:Linrothe*
collection.title:"Rob Linrothe Image Collection" AND Yungang
Shanghai AND work_type:Image
China NOT Japan
```

Label fields (`subject.label`, `contributor.label`, `collection.title`) are exact-match; use the full label or `*`.

**Quote CJK terms.** Unquoted CJK text is split into single characters joined with OR: `孔廟` matches 1,794 unrelated items; `"孔廟"` matches only the whole term (0 hits).

## DSL Search (POST)

```json
{"query": {"bool": {"must": [{"match": {"title": "Shanghai"}}],
                    "filter": [{"term": {"work_type": "Image"}}]}}}
```

## Work Fields (main)

`id`, `title`, `alternate_title`, `work_type`, `date_created`, `creator[]`, `contributor[]` (`label`, `role`, `label_with_role`, `id`), `subject[]`, `genre[]`, `language[]`, `location[]`, `style_period[]`, `technique[]`, `physical_description_material`, `physical_description_size`, `description`, `abstract`, `collection {id, title}`, `library_unit`, `accession_number`, `rights_statement {id, label}`, `terms_of_use`, `visibility`, `canonical_link`, `iiif_manifest`, `thumbnail`, `file_sets[]`, `embedding` (large vector; excluded by the script).

Controlled terms carry `id` URIs (e.g. Getty AAT and ULAN) and `variants` (other name forms).

## Hosted MCP Server

```
https://api.dc.library.northwestern.edu/api/v2/mcp     (streamable HTTP, no login)
claude mcp add --transport http dc-api https://api.dc.library.northwestern.edu/api/v2/mcp
```

Tools: `search`, `similarity-search`, `get-work`, `view-work`, `list-collections`, `view-collection`, `view-search-results`, `view-similar-works`.

## Etiquette

- Keep to about 2 requests per second; back off on HTTP 429/503.
- Set a descriptive `User-Agent`.
