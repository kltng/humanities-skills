---
name: wikidata-search
description: Search for items and properties on Wikidata and retrieve entity details, claims, and external identifiers. Supports both keyword search (Wikidata Action API) and semantic/hybrid search (Wikidata Vector Database), plus direct entity retrieval (Special:EntityData) and structured querying (WDQS SPARQL).
version: 1.1.2
license: MIT
author: Kwok-leong Tang
contributors:
  - Claude (AI Assistant)
---

# Wikidata Search Skill

Search and retrieve data from Wikidata, the free knowledge base.

## Critical: Things Claude Won't Know Without This Skill

### Wikidata Vector Database (semantic search)

This is the highest-value feature of this skill. The **Wikidata Vector Database** at `wd-vectordb.wmcloud.org` provides semantic/hybrid search over all Wikidata items — something you can't do with the standard Action API or SPARQL.

**A descriptive `User-Agent` header is required or you get 403.**

```bash
curl -H 'User-Agent: WikidataSearchSkill/1.0 (contact: you@example.com)' \
  'https://wd-vectordb.wmcloud.org/item/query/?query=historical+Chinese+cartography&lang=all&K=20'
```

Response includes `QID`, `similarity_score`, `rrf_score`, and `source` (vector vs keyword).

Property search: replace `/item/query/` with `/property/query/`.

Optional params: `lang`, `K` (result count), `instanceof` (comma-separated QIDs), `rerank`.

**When the Vector DB is down.** It is a small research service on Wikimedia Cloud, not a core Wikidata service. It can return 503 or time out (on 2026-10-26 it timed out for 20+ seconds). Do not wait on it. Fall back to:

1. `wbsearchentities` (`wd.search(...)`) with several wordings, in English and in Chinese (e.g. `朱熹`, `Zhu Xi`, `Chu Hsi`).
2. `action=query&list=search` (full-text search; supports `haswbstatement:P31=Q5` filters). See `references/api_reference.md`.
3. SPARQL with a type filter (e.g. `?item wdt:P31 wd:Q5`) once you know the kind of item you want.

Tell the user that semantic search was not available and keyword search was used instead.

### WDQS SPARQL also requires User-Agent

```bash
curl -G 'https://query.wikidata.org/sparql' \
  --data-urlencode 'query=SELECT ?item ?label WHERE { ?item wdt:P31 wd:Q12857432 . ?item rdfs:label ?label . FILTER(LANG(?label)="en") }' \
  -H 'Accept: application/sparql-results+json' \
  -H 'User-Agent: WikidataSearchSkill/1.0 (contact: you@example.com)'
```

### Set your own User-Agent

The script's default User-Agent has a placeholder contact (`example@example.com`). Wikimedia asks every client to give real contact info. Set your own:

```python
wd = WikidataAPI(user_agent="MyProject/1.0 (https://my.site; me@my-university.edu)")
```

or set the environment variable `WIKIDATA_USER_AGENT`. In the `curl` examples, replace `you@example.com` too.

### SPARQL dates are Gregorian

WDQS converts every date to the Gregorian calendar. Wikidata often stores pre-1582 dates in the Julian calendar. Example: 朱熹 (Q9397) is stored as born 1130-10-18 (Julian). WDQS `wdt:P569` returns `1130-10-25` (Gregorian). Both are the same day. If you compare with a source that uses Julian dates, or with Chinese calendar conversions that output Julian dates, the WDQS date will look 7–10 days off.

- To see the stored value and its calendar, read the entity JSON (`wd.get_entity(...)` or `Special:EntityData`): `claims.P569[0].mainsnak.datavalue.value` has `time` and `calendarmodel` (`Q1985786` = Julian, `Q1985727` = Gregorian).
- In SPARQL, `?item p:P569/psv:P569/wikibase:timeCalendarModel ?cal` tells you which calendar the editor used. The date value itself is still Gregorian.

### External identifiers live in claims

```python
# claims[property_id][0]["mainsnak"]["datavalue"]["value"] → identifier string
# Common: P214 (VIAF), P244 (LoC), P227 (GND), P213 (ISNI), P268 (BnF)
```

## Choosing an Access Method

| Need | Method |
|------|--------|
| Keyword search by label/alias | Action API `wbsearchentities` |
| Semantic / fuzzy concept discovery | **Vector Database** (hybrid vector + keyword) |
| Fetch a known entity's JSON | `Special:EntityData/{ID}.json` |
| Complex graph queries / reporting | WDQS SPARQL |

## Python Script

Use `scripts/wikidata_api.py` for programmatic access (zero dependencies):

```python
from scripts.wikidata_api import WikidataAPI
wd = WikidataAPI(user_agent="MyProject/1.0 (me@my-university.edu)")

# Keyword search
results = wd.search("Zhu Xi", language="en", limit=5)

# Semantic search (Vector DB) — the key differentiator
candidates = wd.vector_search_items("historical Chinese cartography", lang="all", k=20)

# Entity retrieval
entity = wd.get_entity("Q9397", props=["labels", "descriptions", "claims"])

# External identifiers (labels are fetched for all properties, 50 per call)
ids = wd.get_identifiers("Q9397", include_labels=True)
# → {'VIAF ID (P214)': '46768804', 'Library of Congress ID (P244)': 'n81008179', ...}

# SPARQL
results = wd.sparql_json("SELECT ?item ?label WHERE { ?item wdt:P31 wd:Q12857432 . ?item rdfs:label ?label . FILTER(LANG(?label)='en') }")

# Direct entity JSON (fast for current state)
data = wd.get_entitydata("Q42", flavor="simple")
```

## API Endpoints Quick Reference

| Endpoint | URL |
|----------|-----|
| Action API | `https://www.wikidata.org/w/api.php` |
| Entity JSON | `https://www.wikidata.org/wiki/Special:EntityData/{ID}.json` |
| SPARQL | `https://query.wikidata.org/sparql` |
| Vector DB | `https://wd-vectordb.wmcloud.org` |

## API Etiquette

- **Rate limit**: 0.5–1s between requests
- **User-Agent**: Required for Vector DB and WDQS (include contact info)
- **Respect 429**: Honor `Retry-After` headers
- **Action API**: Use `maxlag` parameter; batch with pipe-separated IDs (max 50)
- **maxlag errors**: `maxlag=5` tells Wikidata "if your servers are more than 5 seconds behind, refuse my request". Wikidata then returns HTTP 200 with `{"error": {"code": "maxlag"}}` and a `Retry-After` header. The lag includes query-service lag, which can stay above 5 seconds for hours (on 2026-10-26 it was about 11 seconds).
- **What the script does**: it sends `maxlag=5` first, as Wikidata asks. On a maxlag error it waits (the `Retry-After` value, growing each time, at most 10 s) and retries twice. If Wikidata is still lagged, it sends the same request once more **without** `maxlag`. This is safe because every Action API call in this script is a read. `maxlag` mainly exists to slow down bots that edit. So by default reads still work during lag, but each call can take about 15 seconds.
- **Options**: `WikidataAPI(maxlag_fallback=False)` raises `MaxlagError` instead of the fallback. `WikidataAPI(maxlag=None)` skips the check from the start; use it for a batch of many read calls while lag is high, and keep the rate limit. If you write your own code that **edits** Wikidata, always keep `maxlag` and never use the fallback.
- **SPARQL**: Request only needed fields; use `LIMIT`

## Related Skills

- **cbdb-api**: Cross-reference Wikidata entities with CBDB biographical data for Chinese historical figures
- **chgis-tgaz**: Look up historical places found via Wikidata in the CHGIS Temporal Gazetteer for detailed administrative history

## Resources

- `references/api_reference.md` — Complete API specs for all four access methods
- `scripts/wikidata_api.py` — Full-featured Python client with rate limiting, retries, and identifier extraction

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "wikidata-search"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[wikidata-search] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: wikidata-search* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
