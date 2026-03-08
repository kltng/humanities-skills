---
name: arxiv-search
description: Search arXiv for preprints and scholarly articles across physics, mathematics, computer science, quantitative biology, quantitative finance, statistics, electrical engineering, systems science, and economics. Supports field-specific queries (title, author, abstract, category), boolean logic, date filtering, and bulk retrieval with pagination.
version: 1.0.0
license: MIT
author: Kwok-leong Tang
contributors:
  - name: Claude
    type: AI Assistant
---

# arXiv Search Skill

Search and retrieve metadata for preprints on arXiv, the open-access repository for scholarly articles.

## Critical: Things Claude Won't Know Without This Skill

### Response format is Atom XML, not JSON

The arXiv API returns **Atom 1.0 XML** — there is no JSON option. You must parse XML to extract results. The Python script handles this automatically.

### The base URL uses `export.arxiv.org`, not `arxiv.org`

```
http://export.arxiv.org/api/query?search_query=all:transformer&max_results=5
```

Using `arxiv.org` directly will not work for API queries.

### Boolean operators must be UPPERCASE

Use `AND`, `OR`, `ANDNOT` — lowercase will not work:

```
search_query=ti:attention AND ti:transformer
search_query=cat:cs.AI ANDNOT cat:cs.CL
```

### Parentheses and quotes must be URL-encoded

- Parentheses: `%28` and `%29`
- Quotes (phrase search): `%22`

```
search_query=ti:%22large+language+model%22
search_query=au:bengio+AND+%28cat:cs.LG+OR+cat:cs.AI%29
```

### Date range filtering uses a special syntax

```
search_query=submittedDate:[202401010000+TO+202412312359]
```

Format: `YYYYMMDDTHHMM` in GMT, 24-hour. The `T` is literal. Combine with other queries using `AND`.

### Rate limiting: 3 seconds between requests

arXiv asks for a minimum 3-second delay between API calls. Results update once daily, so there is no reason to poll frequently.

### Hard limits on results

- `max_results` caps at **2000** per request
- Total retrievable results cap at **30,000** (start + max_results ≤ 30000)
- Exceeding 30,000 returns HTTP 400

## Search Field Prefixes

| Prefix | Field |
|--------|-------|
| `ti` | Title |
| `au` | Author |
| `abs` | Abstract |
| `co` | Comment |
| `jr` | Journal Reference |
| `cat` | Subject Category |
| `rn` | Report Number |
| `id_list` | Specific arXiv IDs (comma-separated, passed as separate param) |
| `all` | All fields simultaneously |

## Python Script

Use `scripts/arxiv_api.py` for programmatic access (zero dependencies):

```python
from scripts.arxiv_api import ArxivAPI
api = ArxivAPI()

# Simple keyword search
results = api.search("all:transformer attention mechanism", max_results=10)

# Field-specific search
results = api.search("ti:diffusion AND cat:cs.CV", max_results=5)

# Author search
results = api.search("au:hinton AND cat:cs.LG", max_results=20)

# Date-filtered search
results = api.search(
    "cat:cs.AI AND submittedDate:[202401010000 TO 202412312359]",
    sort_by="submittedDate",
    sort_order="descending",
    max_results=50
)

# Fetch specific papers by arXiv ID
results = api.fetch_by_ids(["2301.07041", "2303.08774", "2305.10601"])

# Paginated retrieval
page1 = api.search("cat:cs.CL", max_results=100, start=0)
page2 = api.search("cat:cs.CL", max_results=100, start=100)

# Each result is a dict with keys:
# id, title, summary, authors, published, updated,
# categories, primary_category, links, comment, journal_ref, doi
```

## Common Category Codes

| Category | Description |
|----------|-------------|
| `cs.AI` | Artificial Intelligence |
| `cs.CL` | Computation and Language (NLP) |
| `cs.CV` | Computer Vision |
| `cs.LG` | Machine Learning |
| `cs.CR` | Cryptography and Security |
| `cs.DS` | Data Structures and Algorithms |
| `cs.SE` | Software Engineering |
| `math.AG` | Algebraic Geometry |
| `math.CO` | Combinatorics |
| `physics.hep-th` | High Energy Physics - Theory |
| `quant-ph` | Quantum Physics |
| `stat.ML` | Machine Learning (Statistics) |
| `econ.GN` | General Economics |
| `q-bio.GN` | Genomics |

Full list: https://arxiv.org/category_taxonomy

## API Etiquette

- **Rate limit**: 3-second minimum between requests
- **No authentication required**
- **Results update daily** — no need to poll the same query more than once per day
- **Use pagination** for large result sets instead of requesting thousands at once
- **Respect HTTP 429**: Back off if rate-limited

## Related Skills

- **wikidata-search**: Cross-reference arXiv authors with Wikidata entities for authority control identifiers (ORCID, VIAF, etc.)
- **harvard-library-catalog**: Look up published versions of arXiv preprints in Harvard's bibliographic records

## Resources

- `references/api_reference.md` — Complete API specs for query parameters, response fields, and error handling
- `scripts/arxiv_api.py` — Python client with XML parsing, rate limiting, and pagination support
