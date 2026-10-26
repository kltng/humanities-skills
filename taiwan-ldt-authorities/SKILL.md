---
name: taiwan-ldt-authorities
description: Look up Taiwan's library authority data in LDT@Library (臺灣鏈結資源系統, National Central Library + National Taiwan University) — Chinese personal name authorities with variant names and sources, Taiwan's Chinese Subject Headings (中文主題詞), and the Chinese classification (中文圖書分類法) — through its public reconciliation API and SPARQL endpoint (no API key). Use this skill when the user wants the authorized Chinese form of a person's name, all name variants (字, 號, romanizations), the sources a name was established from, Taiwan subject headings to compare with LCSH, or class numbers from the Chinese classification; or when reconciling names in a dataset (OpenRefine).
version: 1.0.1
license: MIT
author: Kwok-leong Tang
contributors:
  - Claude
---

# Taiwan LDT@Library Authorities Skill

Look up Taiwan's name authorities, Chinese subject headings, and Chinese classification. No API key needed.

## Overview

**LDT@Library** (臺灣鏈結資源系統, https://ld.ncl.edu.tw) publishes the authority files used by Taiwan's libraries as linked data (MADS/RDF and SKOS). It has three kinds of records:

| Kind | URI pattern | Example |
|------|-------------|---------|
| Personal names (and corporate names) | `/authority/{id}` | `王守仁, 1472-1528` with 29 variants (王陽明, 伯安, Wang Yang-ming, …) and 7 sources with page numbers |
| Subject headings (Chinese Subject Headings, csht) | `/subject/{id}` | `孔廟` (local id `(ChTaNC)sh01473`) |
| Chinese classification (中文圖書分類法) | `/classification/{id}` | `王守仁` with notation `T中國作家時代區分表…--6.6` |

These are the authorities behind the Taiwan records in **alma-sru-catalogs** (subjects with `$2 csht`, call numbers with `$2 ncsclt`).

Two public interfaces:

- **Reconciliation API** (OpenRefine protocol 0.2): `https://ld.ncl.edu.tw/reconcile`. Ranked fuzzy matches.
- **SPARQL**: `https://ld.ncl.edu.tw/fuseki/lod/query`. Exact data.

## Critical: Things Claude Won't Know Without This Skill

### Reconciliation ranking is loose; check the names

For `王守仁` the reconciliation API ranks a modern scholar who wrote about him (`張祥浩, 1945-`) above `王守仁, 1472-1528`, and `match` is usually `false`. The right record is normally in the top few. Read the `name` and `uri`, or confirm with `lookup`/`get`. The service still calls itself "(Test)".

### Name labels include dates

Personal-name labels look like `王守仁, 1472-1528`. An **exact** lookup for `王守仁` finds only the classification entry. Use `--mode prefix` for names. Subject headings have no dates, so exact works (`孔廟`).

### Labels carry a language tag, which matters for speed

Labels are stored as `"孔廟"@en` (tagged English even when Chinese). Matching the tagged literal takes under 1 second; `FILTER(STR(?label) = "孔廟")` takes 5+ seconds. The script's exact mode does this for you.

| `lookup` mode | What it matches | Time |
|---|---|---|
| `exact` | preferred label equals the text | < 1 s |
| `prefix` | preferred label starts with the text | 1–2 s |
| `variant` | a variant name starts with the text (e.g. 王陽明 → 王守仁) | ~15 s |

Queries that scan the whole store (counts over all records, unrestricted `CONTAINS`) time out. Keep queries anchored to a label or URI.

### Related headings are blank nodes

Subject records link related headings (`hasReciprocalAuthority`) through blank nodes; the script returns their labels with an empty `uri`. Look them up by label to get their records.

## Quick Start

### CLI

```bash
python scripts/ldt_api.py reconcile 王守仁 --type authority --limit 5
python scripts/ldt_api.py lookup 孔廟                       # subject heading, exact
python scripts/ldt_api.py lookup 王守仁 --mode prefix        # names: use prefix
python scripts/ldt_api.py lookup 王陽明 --mode variant       # find the authorized form from a variant
python scripts/ldt_api.py get https://ld.ncl.edu.tw/authority/114743
python scripts/ldt_api.py get subject/89443
python scripts/ldt_api.py sparql 'SELECT ?s ?l WHERE { ?s madsrdf:authoritativeLabel "孔廟"@en }'
```

### Python

```python
from scripts.ldt_api import LDTAPI

ldt = LDTAPI()
hits = ldt.lookup("王陽明", mode="variant")          # -> 王守仁, 1472-1528
person = ldt.get(hits[0]["uri"])
print(person["label"], person["variants"], person["sources"])

ldt.lookup("孔廟")                                   # Taiwan subject heading
ldt.reconcile("金庸", type="authority", limit=5)
ldt.sparql('SELECT ?v WHERE { <https://ld.ncl.edu.tw/authority/114743> madsrdf:hasVariant/madsrdf:variantLabel ?v }')
```

`get()` returns `uri`, `label`, `kind` (`PersonalName`, `CorporateName`, `Topic`, `Classification`, …), `variants`, `sources` (`source`, `note` = page, `status`), `notes`, `notation` (class number), `local_id`, `lccn`, `marc_key` (the MARC heading, e.g. `1001 $a王守仁,$d1472-1528`), `related`, and `url`.

Reconciliation types: `authority` (personal names; sub-types `authority>prefname`, `authority>altname`, …), `topic`, `classification`.

## Workflows

**Authorized form of a name from any variant:** `lookup(variant, mode="variant")`, then `get()` for dates, variants, and sources. Cross-check with **cbdb-local** for biography.

**Compare subject headings across traditions:** find a book in **alma-sru-catalogs** at a Taiwan library and at a US library; compare `subject_headings` (`csht` vs `lcsh`); look up the csht heading here.

**Reconcile a column of names in OpenRefine:** add `https://ld.ncl.edu.tw/reconcile` as a standard reconciliation service.

## Best Practices

1. **Confirm reconciliation hits** with `get()` before trusting them.
2. **Use prefix mode for names**, exact mode for subjects.
3. **Wait 1 second between requests** (the script does this). Avoid whole-store queries.
4. **Cite the record URI** (`https://ld.ncl.edu.tw/authority/…`) when you report an authority.

## Not Included: Hong Kong HKCAN

The HKCAN Chinese name authority linked-data service (hkcan.julac.org) is valuable but its `robots.txt` says `Disallow: /` and its documented SPARQL endpoint (http://hkcan.julac.org/lod/sparql) did not respond on 2026-10-26. Ask JULAC before building on it.

## Related Skills

- **alma-sru-catalogs**: Taiwan university catalogs whose records use these authorities
- **cbdb-local**, **cbdb-api**: biographical data on Chinese historical figures
- **wikidata-search**: link names to Wikidata, VIAF, and LC

## Resources

- `references/api_reference.md` — endpoints, data model (MADS/RDF, SKOS), SPARQL patterns, reconciliation protocol
- `scripts/ldt_api.py` — client and CLI (zero dependencies)
- `tests/test_ldt_api.py` — offline tests
- LDT@Library: https://ld.ncl.edu.tw

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "taiwan-ldt-authorities"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[taiwan-ldt-authorities] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: taiwan-ldt-authorities* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
