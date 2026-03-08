# arXiv API Reference

Detailed documentation for the arXiv Query API.

## Query Endpoint

```
GET http://export.arxiv.org/api/query
```

This is the only API endpoint. All searches and ID lookups go through this URL.

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| search_query | No* | - | Search query string with field prefixes and boolean operators |
| id_list | No* | - | Comma-separated arXiv IDs (e.g., `2301.07041,2303.08774v2`) |
| start | No | 0 | Zero-based index of first result (for pagination) |
| max_results | No | 10 | Number of results to return (max 2000 per request) |
| sortBy | No | relevance | Sort field: `relevance`, `lastUpdatedDate`, `submittedDate` |
| sortOrder | No | descending | Sort direction: `ascending`, `descending` |

*At least one of `search_query` or `id_list` must be provided.

### Query Logic (search_query + id_list)

| search_query | id_list | Result |
|---|---|---|
| Provided | Omitted | All articles matching the query |
| Omitted | Provided | Metadata for the listed article IDs |
| Provided | Provided | Articles in id_list that also match the query (intersection) |

## Search Query Syntax

### Field Prefixes

| Prefix | Field | Example |
|--------|-------|---------|
| `ti` | Title | `ti:attention mechanism` |
| `au` | Author | `au:vaswani` |
| `abs` | Abstract | `abs:reinforcement learning` |
| `co` | Comment | `co:accepted ICML` |
| `jr` | Journal Reference | `jr:nature` |
| `cat` | Subject Category | `cat:cs.CL` |
| `rn` | Report Number | `rn:CERN-PH` |
| `all` | All fields | `all:quantum computing` |

### Boolean Operators

Operators must be **UPPERCASE**:

| Operator | Meaning | Example |
|----------|---------|---------|
| `AND` | Both conditions must match | `ti:attention AND ti:transformer` |
| `OR` | Either condition matches | `cat:cs.AI OR cat:cs.CL` |
| `ANDNOT` | First but not second | `cat:cs.LG ANDNOT cat:stat.ML` |

### Grouping and Phrases

- **Grouping**: Use URL-encoded parentheses `%28` and `%29`
- **Phrase search**: Use URL-encoded quotes `%22`

```
# Papers by Bengio in AI or ML categories
search_query=au:bengio+AND+%28cat:cs.AI+OR+cat:cs.LG%29

# Exact phrase in title
search_query=ti:%22large+language+model%22
```

### Date Filtering

Filter by submission date using `submittedDate` with range syntax:

```
submittedDate:[YYYYMMDDTHHMM TO YYYYMMDDTHHMM]
```

- Format: Year-Month-Day`T`Hour-Minute in GMT, 24-hour clock
- The `T` is a literal character in the timestamp
- URL-encode spaces as `+`

```
# Papers submitted in 2024
search_query=submittedDate:[202401010000+TO+202412312359]

# Combine with other queries
search_query=cat:cs.AI+AND+submittedDate:[202401010000+TO+202412312359]
```

### Article Versioning

- Latest version: `id_list=2301.07041`
- Specific version: `id_list=2301.07041v2`
- Old-style IDs: `id_list=cond-mat/0207270`

## Response Format (Atom 1.0 XML)

### Feed-Level Elements

```xml
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>ArXiv Query: ...</title>
  <id>http://arxiv.org/api/...</id>
  <updated>2024-01-15T00:00:00-05:00</updated>
  <opensearch:totalResults>1234</opensearch:totalResults>
  <opensearch:startIndex>0</opensearch:startIndex>
  <opensearch:itemsPerPage>10</opensearch:itemsPerPage>
  <!-- <entry> elements follow -->
</feed>
```

| Element | Description |
|---------|-------------|
| `<title>` | Canonicalized query string |
| `<id>` | Unique feed ID (URL-based) |
| `<updated>` | Midnight of query day (UTC-4) |
| `<opensearch:totalResults>` | Total matching results |
| `<opensearch:startIndex>` | Pagination offset used |
| `<opensearch:itemsPerPage>` | Number of items returned |

### Entry-Level Elements (per article)

```xml
<entry>
  <id>http://arxiv.org/abs/2301.07041v1</id>
  <title>Paper Title Here</title>
  <summary>Abstract text here...</summary>
  <published>2023-01-17T18:58:46Z</published>
  <updated>2023-06-12T14:30:00Z</updated>

  <author><name>Author One</name></author>
  <author>
    <name>Author Two</name>
    <arxiv:affiliation>MIT</arxiv:affiliation>
  </author>

  <category term="cs.CL" scheme="http://arxiv.org/schemas/atom"/>
  <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
  <arxiv:primary_category term="cs.CL" scheme="http://arxiv.org/schemas/atom"/>

  <link href="http://arxiv.org/abs/2301.07041v1" rel="alternate" type="text/html"/>
  <link href="http://arxiv.org/pdf/2301.07041v1" rel="related" type="application/pdf" title="pdf"/>
  <link href="http://dx.doi.org/10.1234/example" rel="related" type="text/html" title="doi"/>

  <arxiv:comment>15 pages, 5 figures. Accepted at ACL 2023</arxiv:comment>
  <arxiv:journal_ref>Nature 2023</arxiv:journal_ref>
  <arxiv:doi>10.1234/example</arxiv:doi>
</entry>
```

| Element | Description |
|---------|-------------|
| `<id>` | Canonical URL: `http://arxiv.org/abs/{id}` |
| `<title>` | Article title (may contain newlines — normalize whitespace) |
| `<summary>` | Abstract text (may contain newlines — normalize whitespace) |
| `<published>` | First version (v1) submission timestamp |
| `<updated>` | This version's submission timestamp |
| `<author><name>` | One element per author |
| `<arxiv:affiliation>` | Author affiliation (optional, subelement of `<author>`) |
| `<category term="...">` | All arXiv categories |
| `<arxiv:primary_category>` | Primary classification |
| `<link rel="alternate">` | Abstract page URL |
| `<link rel="related" title="pdf">` | PDF download URL |
| `<link rel="related" title="doi">` | DOI resolver URL (if published) |
| `<arxiv:comment>` | Author-provided comments (pages, figures, conference) |
| `<arxiv:journal_ref>` | Journal publication reference (if published) |
| `<arxiv:doi>` | DOI (if published) |

## Extracting the arXiv ID from `<id>`

The `<id>` element contains a full URL. Extract the ID portion:

```
http://arxiv.org/abs/2301.07041v1  →  2301.07041v1
http://arxiv.org/abs/cond-mat/0207270v1  →  cond-mat/0207270v1
```

Strip the version suffix (`v1`, `v2`, ...) to get the base ID.

## Pagination

Use `start` and `max_results` for pagination:

```
# First 100 results
?search_query=cat:cs.AI&start=0&max_results=100

# Next 100
?search_query=cat:cs.AI&start=100&max_results=100
```

**Hard limits:**
- `max_results` ≤ 2000 per request
- `start + max_results` ≤ 30,000 total
- Exceeding 30,000 returns HTTP 400

## Error Handling

Errors are returned as Atom feeds with a single entry where `<summary>` contains the error message:

```xml
<entry>
  <id>http://arxiv.org/api/errors#...</id>
  <title>Error</title>
  <summary>incorrect id format for ...</summary>
</entry>
```

Common errors:

| Cause | Error |
|-------|-------|
| Non-integer `start` or `max_results` | `incorrect value for start/max_results` |
| Negative `start` or `max_results` | `incorrect value for start/max_results` |
| `start + max_results` > 30,000 | HTTP 400 |
| Malformed arXiv ID | `incorrect id format for ...` |

## Rate Limiting

- **Minimum 3-second delay** between consecutive requests
- Results are updated once daily — no need to repeat the same query within a day
- Large queries (30,000 results) take ~2+ minutes and return ~15 MB of XML
- No authentication or API key required

## Example Queries

```bash
# Search for "attention" in titles
curl 'http://export.arxiv.org/api/query?search_query=ti:attention&max_results=5'

# Author search with category filter
curl 'http://export.arxiv.org/api/query?search_query=au:lecun+AND+cat:cs.CV&max_results=10'

# Fetch specific papers by ID
curl 'http://export.arxiv.org/api/query?id_list=2301.07041,2303.08774'

# Recent CS papers sorted by date
curl 'http://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results=20'

# Phrase search in abstract
curl 'http://export.arxiv.org/api/query?search_query=abs:%22graph+neural+network%22&max_results=10'

# Date range filter
curl 'http://export.arxiv.org/api/query?search_query=cat:cs.CL+AND+submittedDate:%5B202401010000+TO+202412312359%5D&max_results=50'
```
