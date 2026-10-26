---
name: northwestern-digital-collections
description: Search Northwestern University Libraries' Digital Collections (digitized photographs, art, architecture slides, manuscripts, maps, posters, audio, and video) through its official public API or its official hosted MCP server, with IIIF manifests for every item. Use this skill whenever the user wants digitized images or primary sources from Northwestern, Asian art and architecture photographs (e.g. the Rob Linrothe collection of Chinese, Tibetan, and Indian monuments), African studies materials, or IIIF images for teaching or research.
version: 1.0.1
license: MIT
author: Kwok-leong Tang
contributors:
  - Claude
---

# Northwestern Digital Collections Skill

Search Northwestern University Libraries' digitized collections. No API key needed for public items.

## Overview

Northwestern publishes its **Digital Collections API (v2)** and a **hosted MCP server** for AI assistants. Both are official and public. The collections are digitized objects, not the full library catalog: over 100,000 works in about 186 collections.

```
Search:  GET  https://api.dc.library.northwestern.edu/api/v2/search/works?query=Yungang&size=10
DSL:     POST https://api.dc.library.northwestern.edu/api/v2/search/works   (OpenSearch JSON body)
Work:    GET  https://api.dc.library.northwestern.edu/api/v2/works/{id}
IIIF:    GET  https://api.dc.library.northwestern.edu/api/v2/works/{id}?as=iiif
MCP:     https://api.dc.library.northwestern.edu/api/v2/mcp   (streamable HTTP)
```

## Option 1: Add Northwestern's MCP server

If MCP tools are welcome, this is the simplest route. It gives tools such as `search`, `similarity-search`, `get-work`, `view-work`, and `list-collections`.

```bash
claude mcp add --transport http dc-api https://api.dc.library.northwestern.edu/api/v2/mcp
```

Tested on 2026-10-25: it answers without login. Ask the user before adding it, because it changes their Claude Code settings.

## Option 2: Use the script (no setup)

```bash
python scripts/northwestern_dc.py search Yungang --limit 5
python scripts/northwestern_dc.py search 'subject.label:"China" AND work_type:Image' --sort date_created:asc
python scripts/northwestern_dc.py search 'collection.title:"Rob Linrothe Image Collection" AND Yungang'
python scripts/northwestern_dc.py search --dsl '{"query": {"match": {"title": "Shanghai"}}}'
python scripts/northwestern_dc.py work a84ea83c-bf11-4c4f-89ac-87a951b9ce58
python scripts/northwestern_dc.py collections --limit 50
```

```python
from scripts.northwestern_dc import NorthwesternDC

dc = NorthwesternDC()
result = dc.search('subject.label:"China" AND work_type:Image', limit=20, sort="date_created:asc")
for w in result["records"]:
    print(w["title"], w["dates"], w["url"], w["iiif_manifest"])
dc.get_work("a84ea83c-bf11-4c4f-89ac-87a951b9ce58")
dc.collections(limit=200)
```

Each work summary has `id`, `title`, `alternate_titles`, `work_type`, `dates`, `creators` (with roles), `subjects`, `genres`, `languages`, `places`, `materials`, `description`, `collection`, `library_unit`, `accession_number`, `rights`, `visibility`, `url` (public page), `iiif_manifest`, and `thumbnail`.

## Critical: Things Claude Won't Know Without This Skill

### The keyword parameter is `query`, not `q`

`?q=...` is silently ignored and returns every item (over 130,000 hits). The script uses `query`.

### Query-string syntax

`query` takes OpenSearch query-string syntax:

- Words: `Yungang` · phrase: `"Juyong Guan"` · CJK: always quoted, `"雲岡"`
- Fields: `title:Beijing`, `work_type:Image` (Image, Audio, Video), `subject.label:"China"`, `collection.title:"..."`
- Label fields (`subject.label`, `contributor.label`, `collection.title`) match the **whole** label: use the exact form (`contributor.label:"Linrothe, Robert N., 1951-"`) or a wildcard (`contributor.label:Linrothe*`)
- Boolean: `Shanghai AND work_type:Image`, `China NOT Japan`
- Sort: `date_created:asc`, `create_date:desc`, `title.keyword:asc`

For anything more complex, send a full OpenSearch body with `--dsl`.

### Quote CJK terms

The search splits CJK text into single characters and ORs them, so an **unquoted** CJK query matches any one character: `孔廟` returns 1,794 unrelated items (a Sgt. Pepper insert, a blimp cutout, a gurdwara). Always quote CJK terms: a quoted term matches only the whole term (`"孔廟"` returns 0). The same applies to fields: `title:"北京"`.

### Chinese text is sparse

Most records are in English with romanized names. Search `Yungang`, `Shanxi`, `Juyong Guan`, not only characters.

### Records are large

Full records include vector embeddings and file lists. The script leaves those out of searches (`_source_excludes`). Use `work --raw` for the complete record.

## Best Practices

1. **Prefer the MCP** for interactive browsing (it can show IIIF images); use the script for scripted searches and exports.
2. **Search by collection** once you find a relevant one; collection titles are exact-match.
3. **Cite the item URL and rights statement.** Check `rights` before reusing images.
4. **Wait between requests.** The script waits 0.5 s, and retries dropped connections, timeouts, and HTTP 429/5xx.

## Not Included: Minnesota UMedia

University of Minnesota's UMedia has a `search.json` endpoint, but its `robots.txt` explicitly disallows `/search.json` for automated clients, item pages return 403 to scripts, and its ContentDM host disallows everything. Do not build on it without the library's permission.

## Related Skills

- **europeana-collections**, **loc-catalog**: other digitized cultural heritage
- **yale-library-catalog**: Yale LUX covers Yale's museums and archives
- **mit-timdex**: MIT digital collections (images) and archives

## Resources

- `references/api_reference.md` — endpoints, parameters, query syntax, record fields, MCP tools
- `scripts/northwestern_dc.py` — client and CLI (zero dependencies)
- `tests/test_northwestern_dc.py` — offline tests
- API docs: https://api.dc.library.northwestern.edu/docs/v2/index.html
- MCP source: https://github.com/nulib/dc-api-v2/tree/main/mcp

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "northwestern-digital-collections"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[northwestern-digital-collections] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: northwestern-digital-collections* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
