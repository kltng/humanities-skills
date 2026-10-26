# Crossref REST API Reference

Base URL: `https://api.crossref.org`. All responses are JSON: `{"status": "ok", "message-type": ..., "message": {...}}`. No API key. Tested October 2026.

## Etiquette and limits

| Pool | How to join | Rate | Concurrency |
|---|---|---|---|
| Public | default | 1 request/s | 1 |
| Polite | add `mailto=you@example.org` (query param) or put it in the User-Agent | 3 requests/s | 3 |

The response headers `x-rate-limit-limit`, `x-rate-limit-interval`, `x-concurrency-limit`, and `x-api-pool` show the current limits. On 429, wait and retry.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /works` | Search all works |
| `GET /works/{doi}` | One work. 404 `Resource not found.` if the DOI is not a Crossref DOI |
| `GET /works/{doi}/agency` | Registration agency (Crossref, DataCite, ...). 404 for DOIs Crossref does not know |
| `GET /works/{doi}/transform` | Formatted citation; choose the format with the `Accept` header |
| `GET /journals?query=` | Find journals by title |
| `GET /journals/{issn}` | One journal, with DOI counts |
| `GET /journals/{issn}/works` | Search inside one journal (same parameters as `/works`) |
| `GET /prefixes/{prefix}/works` | Works under one DOI prefix (e.g. 10.2307 = JSTOR) |
| `GET /members`, `/members/{id}/works` | Publishers |
| `GET /types` | Work types |

Outside Crossref: `GET https://doi.org/ra/{doi or prefix}` (several separated by commas) returns `[{"DOI": "10.13471", "RA": "CNKI"}]`, or `"status": "DOI does not exist"`.

Put the DOI in the path as is, keeping `/`; percent-encode characters such as `<>;#()`.

## Search parameters (`/works`)

| Parameter | Meaning |
|---|---|
| `query` / `query.bibliographic` | Free text over title, authors, venue, year. Best for whole references |
| `query.title`, `query.author`, `query.editor`, `query.translator`, `query.contributor`, `query.container-title`, `query.publisher-name`, `query.affiliation` | Field queries. Several together must all match. Whole words, no stemming |
| Also accepted: `query.chair`, `query.degree`, `query.description`, `query.event-name`, `query.event-location`, `query.funder-name`, `query.publisher-location`, ... | |
| `filter` | `name:value,name:value` (see below) |
| `rows` | 0–1000 (default 20). `rows=0` gives only the count |
| `offset` | offset + rows ≤ 10,000 |
| `cursor` | `*` to start; then `message.next-cursor`. Stop when `items` is empty |
| `sort` | `relevance`/`score`, `published`, `issued`, `published-print`, `published-online`, `is-referenced-by-count`, `references-count`, `created`, `updated`, `indexed`, `deposited` |
| `order` | `asc` or `desc` |
| `select` | Comma-separated fields, e.g. `DOI,title,author,issued` |
| `facet` | `name:count`, e.g. `type-name:10,publisher-name:10,container-title:10,published:*` |
| `sample` | N random works |
| `mailto` | Contact email (polite pool) |

Errors are 400 with `"status": "failed"` and a list of messages, e.g. `Filter 'x' specified but there is no such filter for this route. Valid filters for this route are: ...` (the list of valid names follows).

Quirks:

- `cursor` with a date sort fails: `Sorting by [issued, published, published-print, published-online] is not supported when using a cursor`.
- `offset=10000` fails: `offset must be ... less than or equal to 9997. Use the cursor parameter`.
- Words are ORed. `total-results` counts every loose match (330,847 for "Ming dynasty examination").
- CJK text is matched by single characters, so recall for CJK terms is poor and can be zero (see SKILL.md, "CJK searches"). Many CJK titles are only in `alternate_titles`; search the English title form as well.

## Useful filters

| Filter | Example |
|---|---|
| `type` | `type:journal-article`, `book`, `book-chapter`, `monograph`, `edited-book`, `reference-entry`, `dissertation`, `proceedings-article`, `posted-content`, `dataset` |
| `from-pub-date`, `until-pub-date` | `from-pub-date:2000`, `until-pub-date:2010-06-30` (also `from-print-pub-date`, `from-online-pub-date`, `from-issued-date`) |
| `prefix` | `prefix:10.2307` (JSTOR) |
| `member` | Crossref member ID |
| `issn`, `isbn` | `issn:1086-3257` |
| `container-title` | exact journal title |
| `doi` | `doi:10.2307/2057472` |
| `has-abstract`, `has-references`, `has-full-text`, `has-orcid`, `has-license`, `has-funder` | `has-abstract:true` |
| `orcid` | `orcid:0000-0002-...` |
| `gte-citation`, `lte-citation` | citation count bounds |
| `is-update`, `update-type` | corrections, retractions |

Work types (from `/types`): book-section, monograph, report-component, report, peer-review, book-track, journal-article, book-part, other, book, journal-volume, book-set, reference-entry, proceedings-article, journal, component, book-chapter, proceedings-series, report-series, proceedings, database, standard, reference-book, posted-content, journal-issue, dissertation, grant, dataset, book-series, edited-book.

Facets: affiliation, license, container-title, publisher-name, link-application, orcid, update-type, published, funder-name, archive, type-name, relation-type, ror-id, issn, source, journal-issue, category-name, assertion, assertion-group, journal-volume, funder-doi.

## Work record fields

| Field | Notes |
|---|---|
| `DOI`, `URL`, `type`, `prefix`, `member`, `publisher` | |
| `title`, `subtitle`, `original-title`, `short-title` | lists |
| `author`, `editor`, `translator` | `[{"given", "family", "sequence", "affiliation", "ORCID"}]`; organizations use `name`. CJK names often repeat the full name in both `given` and `family` |
| `container-title`, `short-container-title` | journal or book title (list) |
| `issued`, `published`, `published-print`, `published-online` | `{"date-parts": [[2024, 12]]}` |
| `volume`, `issue`, `page`, `article-number` | strings |
| `ISSN`, `issn-type`, `ISBN`, `isbn-type` | |
| `abstract` | JATS XML, e.g. `<jats:p>...</jats:p>` |
| `language`, `subject` | often missing |
| `is-referenced-by-count` | citations from other Crossref works |
| `reference-count`, `references-count` | size of the deposited reference list |
| `reference` | list of `{"key", "DOI", "doi-asserted-by", "author", "year", "article-title", "volume-title", "journal-title", "unstructured"}`, only when the publisher made references open |
| `resource.primary.URL` | publisher landing page |
| `link` | full-text links (often for text mining or similarity checking only) |
| `relation` | e.g. `is-preprint-of`, `has-review` |
| `score` | relevance score (search results only) |

## Citation formatting (`/works/{doi}/transform`)

| `Accept` header | Output |
|---|---|
| `text/x-bibliography; style=chicago-author-date; locale=en-US` | formatted text in any CSL style (apa, modern-language-association, harvard-cite-them-right, ...). Unknown style → 406 `style-not-found` |
| `application/x-bibtex` | BibTeX |
| `application/x-research-info-systems` | RIS |
| `application/vnd.citationstyles.csl+json` | CSL-JSON |

The same works through `https://doi.org/{doi}` with the `Accept` header (content negotiation), which redirects to this endpoint.

## Examples

```bash
curl -G "https://api.crossref.org/works" \
  --data-urlencode "query.title=civil service examinations" \
  --data-urlencode "query.author=Elman" \
  --data-urlencode "rows=5" --data-urlencode "mailto=you@example.org"

curl "https://api.crossref.org/works?filter=prefix:10.2307,from-pub-date:2000&query.bibliographic=Wang+Yangming&rows=5"

curl -H "Accept: text/x-bibliography; style=apa" \
  "https://api.crossref.org/works/10.2307/2057472/transform"

curl "https://doi.org/ra/10.13471,10.3969,10.6163"   # CNKI, ISTIC, Airiti
```
