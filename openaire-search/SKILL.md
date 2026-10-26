---
name: openaire-search
description: Search the OpenAIRE Graph, Europe's open scholarly knowledge graph, through its free public API (no key needed). It merges Crossref, DataCite, ORCID, arXiv, Zenodo, and thousands of institutional repositories into one index of publications, theses, datasets, software, projects, organizations, and repositories. Use this skill whenever the user wants doctoral theses or repository copies (HKU Scholars Hub, Oxford ORA, Ghent, ...), open-access versions of an article, datasets or Zenodo deposits on a topic, outputs of one repository or funded project, or a check of which repositories hold a DOI. Use it alongside crossref-search for literature searches.
version: 1.0.0
license: MIT
author: Kwok-leong Tang
contributors:
  - Claude
---

# OpenAIRE Search Skill

Search publications, theses, datasets, and repository copies across thousands of sources. No API key needed.

## Overview

The **OpenAIRE Graph** (https://graph.openaire.eu) links research outputs from publishers (through Crossref), DataCite (Zenodo, Dataverse, figshare), and institutional repositories worldwide. The same work found in several places is merged into one record, and every copy is listed with its access right. The API is at `https://api.openaire.eu/graph/v3`.

Use it **with crossref-search**. Crossref has publisher metadata. OpenAIRE adds theses, repository copies, datasets, open-access links, and some Chinese articles whose DOIs Crossref does not hold (e.g. ISTIC DOIs from 地理研究).

| Entity | What it holds |
|---|---|
| `research-products` | publications (articles, books, chapters, theses, conference papers, preprints), datasets, software, other |
| `datasources` | repositories, journals, archives (HKU Scholars Hub, Zenodo, ...) |
| `organizations` | universities and institutes, with ROR IDs |
| `projects` | funded grants (EC, NSF, Wellcome, ...) |
| `persons` | authors with ORCID |

## Critical: Things Claude Won't Know Without This Skill

### Use a quoted phrase, especially for CJK

Unquoted words are matched loosely. CJK text is matched character by character: `明代科舉` gives 104 results, `"明代科舉"` gives 4, all on the topic. Use `--phrase` (or put double quotes in the query) for any CJK term and for multi-word names. `"Ming dynasty"` still gives 4,396, so add filters.

`search` accepts `AND`, `OR`, `NOT` (uppercase only; lowercase words are searched as words) and parentheses: `'"Ming dynasty" AND examination NOT medicine'`.

### Filter values with spaces need double quotes

OpenAIRE rejects `instanceType=Doctoral thesis`. It needs `instanceType="Doctoral thesis"`. The script adds the quotes for you. Values that already contain quotes or AND/OR/NOT are sent as they are.

### Two kinds of "type"

- `--type`: `publication`, `dataset`, `software`, `other`.
- `--instance-type`: the finer kind of each copy: `"Doctoral thesis"`, `"Master thesis"`, `Article`, `"Part of book or chapter of book"`, `Book`, `"Conference object"`, `Preprint`, `Dataset`, ... (full list: https://api.openaire.eu/vocabularies/dnet:publication_resource).

`--instance-type "Doctoral thesis" --open` with `"Ming dynasty"` → 49 open-access theses (HKU, Lingnan, Ghent, Oxford, ...).

### Access rights

`--access` takes `Open Access`, `Closed Access`, `Restricted`, `Open Source`, `Embargo`, `Unknown` (`--open` is a shortcut). In the result, `access` is the best access over all copies (`OPEN`, `CLOSED`, ...). `copies` lists each URL with its host and access, and `open_urls` lists only the open ones. Many publisher copies show no access label at all; that means unknown, not closed.

### Sorting and paging

- `--sort` takes `relevance`, `publicationDate`, `citationCount`, `influence`, `popularity`, `impulse`, or `dateOfCollection`. Sorting a loose query by citations brings up unrelated famous papers: `"Wang Yangming" --sort citationCount` returned stem-cell papers by an author named Wang Yangming. Use a phrase and filters first.
- `page` × `rows` must be ≤ 10,000; `rows` ≤ 100. For more, use `--cursor '*'` and pass back `next_cursor`. With a cursor the results come in a fixed internal order, and `--sort` had no effect in tests (the script refuses the combination).

### Rate limits

The OpenAIRE terms say anonymous use is limited to **60 requests per hour**, and 7,200 per hour with a token. In October 2026 the response headers showed `x-ratelimit-limit: 7199` even for anonymous calls. The script keeps the latest headers in `api.rate_limit`, waits 1 s between calls, and retries 429, 5xx, timeouts, and dropped connections (5, 10, 20 s). For heavy use, register at https://develop.openaire.eu, create a personal access token (valid for one hour), and set `OPENAIRE_ACCESS_TOKEN`.

### Search one repository by its ID, not its name

`--datasource "HKU Scholars Hub"` (relHostingDataSource) and `source` returned 0 results in tests. So did the organization filters (`--organization "The University of Hong Kong"`, or `relOrganizationId` with the HKU organization IDs): links between products and organizations are sparse for the humanities. Find the ID with `datasources "HKU Scholars Hub"`, then pass `--datasource-id`: `"明代"` in HKU Scholars Hub → 22 results. A repository can have several records (the OpenDOAR one `opendoar____::...` is usually the one that hosts the copies).

### Metadata quality

Records are merged from many sources, so expect `Unknown Repository` hosts, `Undetermined` languages, missing abstracts, and author names in several forms (`Kwok-leong Tang`, `Kwok Leong Tang`). `--author` matches the full name as a phrase; try the name forms the person uses.

## Quick Start

### CLI

```bash
python scripts/openaire_api.py search "Ming dynasty" --phrase --type publication --from-date 2015
python scripts/openaire_api.py search 明代科舉 --phrase
python scripts/openaire_api.py search "Ming dynasty" --phrase --instance-type "Doctoral thesis" --open
python scripts/openaire_api.py search --author "Kwok-leong Tang"
python scripts/openaire_api.py search 明代 --phrase --language Chinese
python scripts/openaire_api.py search '"Ming dynasty" AND examination' --type dataset
python scripts/openaire_api.py doi 10.5353/th_b3123394           # all copies of a DOI
python scripts/openaire_api.py datasources "HKU Scholars Hub"
python scripts/openaire_api.py search 明代 --phrase --datasource-id "opendoar____::d707329bece455a462b58ce00d1194c9"
python scripts/openaire_api.py organizations "Academia Sinica"
python scripts/openaire_api.py get doi_dedup___::5619fd1bdb39d6549898d1c1583fcdea
```

### Python

```python
from scripts.openaire_api import OpenAIREAPI

oa = OpenAIREAPI()                      # reads OPENAIRE_ACCESS_TOKEN if set
res = oa.search("Ming dynasty", phrase=True, instance_type="Doctoral thesis", open_access=True, page_size=20)
for r in res["items"]:
    print(r["year"], r["authors"], r["title"], r["publisher"], r["open_urls"])

oa.search("明代科舉", phrase=True)
oa.search(author="Kwok-leong Tang")
hub = oa.search("HKU Scholars Hub", entity="datasources")["items"]
oa.search("明代", phrase=True, datasource_id="opendoar____::d707329bece455a462b58ce00d1194c9")  # one repository
oa.search("Ming", phrase=True, type="dataset", sort="publicationDate")
rec = oa.find_doi("10.2307/2057472")    # copies and access of a known DOI
print(rec["access"], rec["copies"])

oa.search("HKU Scholars Hub", entity="datasources")
oa.search("Academia Sinica", entity="organizations", countryCode="TW")
oa.get("doi_dedup___::5619fd1bdb39d6549898d1c1583fcdea")
print(oa.rate_limit)                    # latest x-ratelimit headers
```

Each research-product summary has `id`, `type`, `instance_types`, `title`, `subtitle`, `other_titles`, `authors`, `publication_date`, `year`, `publisher`, `container` (journal), `volume`, `issue`, `pages`, `language`, `pids` (doi, handle, pmid, arXiv, ...), `doi`, `access`, `oa_color`, `is_green`, `subjects`, `description`, `citation_count`, `copies` (url, type, hosted_by, access, license), `open_urls`, and `collected_from`.

Friendly filter names: `title`, `description`, `author`, `author_id` (ORCID), `type`, `instance_type`, `access`, `language`, `country`, `subjects`, `fos` (field of science), `publisher`, `pid`, `organization`, `datasource_id`, `project`, `funder`, `from_date`, `to_date`, `peer_reviewed`, `oa_color`. Any other API parameter can be passed by its own name.

## Best Practices

1. **Start with a quoted phrase and a type**, then add dates, language, or access.
2. **Find an open copy:** look up the DOI with `doi`, then use `open_urls`. Repository copies may be accepted manuscripts, not the published version. Check the `type` and host.
3. **Theses:** filter with `--instance-type "Doctoral thesis"`. Many Hong Kong, UK, and European theses are open.
4. **Combine with Crossref:** use crossref-search for exact citations and reference lists, and OpenAIRE for copies, theses, and datasets.
5. **Keep calls few:** fetch 20–100 rows per call rather than many small pages, in case the 60/hour anonymous limit is enforced.

## Related Skills

- **crossref-search**: publisher metadata, citation formatting, reference lists, JSTOR links
- **arxiv-search**: preprints
- **hathitrust-catalog**, **alma-sru-catalogs**: books in libraries

## Resources

- `references/api_reference.md` — endpoints, parameters, values, record fields
- `scripts/openaire_api.py` — client and CLI (zero dependencies)
- `tests/test_openaire_api.py` — offline tests
- Graph API docs: https://graph.openaire.eu/docs/apis/graph-api/
- Swagger: https://api.openaire.eu/graph/swagger-ui/index.html

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "openaire-search"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[openaire-search] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses. OpenAIRE Graph data is under CC-BY and must credit OpenAIRE as the source.

> Tang, Kwok-leong. *humanities-skills: openaire-search* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
