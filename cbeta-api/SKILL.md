---
name: cbeta-api
description: Search and read the CBETA Chinese Buddhist canon (大正藏, 卍續藏, 嘉興藏 and 20+ other collections) and look up Buddhist monks, authors, translators, places and dates in the DILA authority database (法鼓文理學院 規範資料庫). Use when the user asks about Buddhist texts or sutras, wants to find where a phrase or quotation occurs in the canon, resolve a CBETA/Taishō citation (e.g. "T08, no. 235, p. 748c17"), list the works of a monk or translator, identify a Buddhist person (Chinese, Japanese or Korean) and get a DILA person ID (A000759), or link a Buddhist name to Wikidata (P1187). Also for checking variant characters (錬/鍊) that make a name search fail.
version: 1.0.0
license: MIT
creator: AI
author: Kwok-leong Tang
contributors:
  - Claude (AI Assistant)
---

# CBETA API

Two free web services run by the Dharma Drum Institute of Liberal Arts (DILA, 法鼓文理學院), no key needed:

1. **CBETA API** — full text and metadata of the CBETA canon: works, fascicles (卷), lines, citations, full-text search.
2. **DILA authority database** — persons (A-IDs), places (PL-IDs) and Chinese calendar dates. The same A-IDs appear in CBETA as creator IDs, and in Wikidata as property **P1187**.

Together they let an agent go from a name in a table to a person ID, from the ID to that person's works in the canon, and from the ID to Wikidata.

## Critical: Things Claude Won't Know Without This Skill

**Base URLs (checked 2026-11-09):**
```
https://cbdata.dila.edu.tw/stable/                       # CBETA API 4.6
https://authority.dila.edu.tw/webwidget/getAuthorityData.php   # DILA authority
```
The old host `api.cbetaonline.cn` no longer resolves. Older blog posts and code still use it.

**Person search goes through `id=`.** The authority API has no `term` or `q` parameter for persons. Put either an ID or a name in `id`:
```
getAuthorityData.php?type=person&id=A000759     → one record
getAuthorityData.php?type=person&id=空海         → every person whose name or other names contain 空海 (7 records)
```
The answer is `{"data1": {...}, "data2": {...}}`. "Not found" comes back in two shapes: `null` or `{"data1": ""}`. The content type is `text/html` even though the body is JSON.

**Variant characters break name search.** Japanese forms often differ from those in CBETA. `師錬` finds nothing, `師鍊` finds 虎關師鍊 (A000919). When a name fails, call `search/variants` first:
```
https://cbdata.dila.edu.tw/stable/search/variants?q=師錬   → 師鍊 (75 hits), 師煉 (2 hits)
```
Then search the authority database again with the variant. "Not found" is not "does not exist".

**Query length limit:** every CBETA search `q` must be 40 characters or fewer, or the API returns an error.

**Errors come as HTTP 200** with `{"success": false, "error": "..."}` (the message is in Chinese, e.g. 缺少必要參數).

**Line IDs (linehead)** are the stable address of a line: `T08n0235_p0748c17` = Taishō vol. 8, no. 235, page 748, column c, line 17. The standard citation form is `CBETA, T08, no. 235, p. 748c17`. Cite with these, not with page numbers of the HTML.

**Creator IDs in CBETA are DILA person IDs.** `creators_with_id` looks like `鳩摩羅什(A001583)`. Use `works?creator_id=A001583` to list someone's works.

## Python Script

`scripts/cbeta_api.py` (standard library only; rate limit, retries, `User-Agent`, UTF-8).

```python
from scripts.cbeta_api import CBETAAPI
api = CBETAAPI()

# Persons (DILA authority)
people = api.person("空海")                 # list of records; [] if none
print(api.summarize_person(people[0]))     # name, ID, dates, school, other names, note
api.person("A000919")                      # by ID
api.wikidata_for_person("A000759")         # [{'qid': 'Q222227', 'label': '空海'}]
api.place("嵩山")                          # lat/long and modern district
api.date(when="+0835-04-26")               # Chinese calendar for a CE date

# Variant characters, when a name or term finds nothing
api.search_variants("師錬")                 # [{'q': '師鍊', 'hits': 75}, ...]

# Works
api.work("T0235")                          # metadata: title, byline, creators_with_id, time_from/to, places
api.works_by_creator(creator_id="A000919") # 元亨釋書 B0173, 八海含藏 B0179
api.works_by_creator(name="空海")           # name contains 空海
api.works_by_time(dynasty="唐")
api.toc("T0001")

# Text
api.goto("CBETA, T08, no. 235, p. 748c17")  # → work, juan, linehead
api.lines("T08n0235_p0748c17", after=3)     # line text with collation notes
api.juan_text("T0251", 1)                   # plain text of one fascicle (reading copy)
CBETAAPI.cite(api.work("T0235"), "0748c17") # 'CBETA, T08, no. 235, p. 748c17'

# Search
api.search("如是我聞", canon="T", order="time_from+")
api.search_all_in_one('"法鼓" NEAR/7 "迦葉"')   # with KWIC snippets
api.search_kwic("T0235", 1, "如是我聞")        # hits inside one fascicle, with line numbers
api.search_title("心經")
api.search_similar("一切有為法如夢幻泡影")     # find a loose quotation
api.search_simplified("金刚经")
```

Command line (good for a quick check):
```bash
python3 scripts/cbeta_api.py person 虎關師鍊
python3 scripts/cbeta_api.py works-by A000919
python3 scripts/cbeta_api.py variants 師錬
python3 scripts/cbeta_api.py goto "CBETA, T08, no. 235, p. 748c17"
python3 scripts/cbeta_api.py wikidata A000759
python3 scripts/cbeta_api.py search 元亨釋書
```

## Workflow: link a Buddhist name from a table

1. `person(name)`. If several records come back, compare dates, dynasty/country (`日本`, `唐`…) and `note` with your source. Show the candidates to the user if more than one fits.
2. Nothing found? `search_variants(name)`, then `person(variant)`. Also try a shorter name: DILA often stores the dharma name only (`師鍊`, not `虎關師鍊`; `周信`, not `義堂周信`). The longer name is usually in `names`.
3. Record the A-ID. Then `works_by_creator(creator_id=...)` for works in the canon, and `wikidata_for_person(...)` for the Wikidata item.
4. Check one result by hand: open `https://authority.dila.edu.tw/person/?fromInner=<ID>` or the CBETA reader `https://cbetaonline.dila.edu.tw/<linehead>`.

**Coverage:** DILA is a Buddhist database. Lay scholars (for example the Confucian 林羅山) are usually not in it. For them use `jbdb-api`, `cbdb-local` or `wikidata-search`.

## Best Practices

- **ID > exact name > partial name.** A name match is a candidate, not an identification.
- **Rate limit** (the client waits 1 s between calls). For hundreds of names, run them in a batch and cache results; or use the open-content downloads (see the reference).
- **Use line IDs for citations.** `juan_text()` is a reading copy; quote from `lines()` so the notes and line numbers stay with the text.
- **Collation notes matter.** `lines()` returns `notes` (e.g. `〔長安〕－【宋】`: the Song edition lacks 長安).
- **Dates:** `time_from`/`time_to` on a work are the CE years of composition or translation, often a range. `bornDateBegin`/`diedDateBegin` on persons are ISO strings or `unknown`.

## Related Skills

- **cbdb-local / cbdb-api** — Chinese officials and literati; many monks are there too.
- **jbdb-api** — Japanese persons, including lay scholars DILA lacks.
- **wikidata-search** — P1187 joins DILA IDs to Wikidata, and from there to CBDB (P497) and other IDs.
- **cjk-calendar** — Japanese, Chinese and Korean era dates (DILA's date service covers Chinese dynasties).
- **archival-entity-linking** — linking many names in a table at once.

## Resources

- `references/api_reference.md` — endpoints, parameters, response fields, quirks.
- `scripts/cbeta_api.py` — the client and command line.
- CBETA API documentation: https://cbdata.dila.edu.tw/stable/
- DILA authority database: https://authority.dila.edu.tw/ (services: https://authority.dila.edu.tw/docs/services/)
- CBETA Online reader: https://cbetaonline.dila.edu.tw/

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "cbeta-api"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[cbeta-api] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: cbeta-api* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
