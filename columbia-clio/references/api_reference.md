# Columbia CLIO Catalog API Reference

## Base URL

`https://clio.columbia.edu/catalog`

This is an undocumented Blacklight (Solr) JSON API. Append `.json` to URLs.

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/catalog.json?q=...` | Search catalog |
| `/catalog/{id}.json` | Get single record |

## Search Parameters

| Param | Description | Example |
|-------|-------------|---------|
| `q` | Search query | `q=hamlet` |
| `search_field` | Field to search: `title`, `author` | `search_field=title` |
| `per_page` | Results per page | `per_page=25` |
| `page` | Page number | `page=2` |
| `sort` | Sort order | `sort=pub_date_sort+desc` |
| `f[facet][]` | Facet filter (array syntax) | `f[format][]=Book` |

## Available Facets

| Facet | Example Values |
|-------|---------------|
| `format` | Book, Online, Music - Recording, Music - Score, Journal/Periodical |
| `language_facet` | English, Chinese, French, German, Spanish |
| `location_facet` | Butler Stacks, Starr East Asian, Avery |
| `subject_topic_facet` | History, Philosophy, Chinese poetry |
| `subject_geo_facet` | China, United States, Japan |
| `subject_era_facet` | 20th century, 19th century |
| `subject_form_facet` | Biography, Fiction, Periodicals |
| `author_facet` | Author names |

## Document Fields

### Search Results

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Record ID |
| `title_display` | string | Title |
| `author_display` | string | Primary author |
| `author_facet` | array | All authors |
| `format` | array | Format types |
| `pub_year_display` | array | Publication year(s) |
| `pub_name_display` | array | Publisher |
| `pub_place_display` | array | Place of publication |
| `language_facet` | array | Languages |
| `isbn_display` | array | ISBNs |
| `oclc_display` | array | OCLC numbers |
| `lccn_display` | array | LCCNs |
| `subject_topic_facet` | array | Subject terms |
| `location_call_number_id_display` | array | Location + call number |
| `physical_description_display` | array | Physical description |
| `holdings_ss` | array | Holdings data (JSON strings) |

### Single Record (additional fields)

`author_variant_display`, `subject_variant_display`, `filing_title_display`, `notes_display`, `url_display`

## Pagination

```json
{
  "pages": {
    "current_page": 1,
    "total_pages": 5330,
    "total_count": 10659,
    "next_page": 2,
    "limit_value": 10
  }
}
```

## Authentication & Rate Limits

- No authentication required
- No documented rate limits (undocumented API — be conservative, max 1 req/sec)
- Official bulk data: `https://lito.cul.columbia.edu/extracts/ColumbiaLibraryCatalog/full/` (MARCXML, CC0)
