# Humanities Skills

A Claude Code skill marketplace for academic research, focused on East Asian historical and geographical data, library catalogs, and scholarly resources.

## Skills

### Biographical Databases

| Skill | Description |
|-------|-------------|
| [cbdb-api](cbdb-api/) | Query the China Biographical Database API — 656K+ historical Chinese figures (7th c. BCE – 19th c. CE) |
| [cbdb-local](cbdb-local/) | Query CBDB locally via SQLite — kinship networks, official postings, social associations, examinations |
| [jbdb-api](jbdb-api/) | Query the Japan Biographical Database API — historical Japanese figures, events, occupations |

### Historical Geography

| Skill | Description |
|-------|-------------|
| [chgis-tgaz](chgis-tgaz/) | Query CHGIS Temporal Gazetteer API — historical Chinese placenames (222 BCE – 1911 CE) |
| [tgaz-sqlite](tgaz-sqlite/) | Query TGAZ locally via SQLite — 82K+ placenames with spatial and temporal filtering |
| [historical-map](historical-map/) | Generate interactive Leaflet.js maps with markers, GeoJSON overlays, and historical tile layers |

### Calendar & Chronology

| Skill | Description |
|-------|-------------|
| [cjk-calendar](cjk-calendar/) | Convert between CJK lunisolar calendar dates and Gregorian/Julian dates (~220 BCE – 1945 CE) |
| [historical-timeline](historical-timeline/) | Generate interactive TimelineJS3 timelines with BCE/CE support, eras, and media |

### Library Catalogs

| Skill | Description |
|-------|-------------|
| [harvard-library-catalog](harvard-library-catalog/) | Search Harvard Library's 13M+ records via LibraryCloud and PRESTO |
| [hathitrust-catalog](hathitrust-catalog/) | Look up HathiTrust's 17M+ digitized volumes by ISBN, OCLC, LCCN, or ISSN |
| [loc-catalog](loc-catalog/) | Search Library of Congress digital collections — books, photos, maps, manuscripts, newspapers |
| [nlb-singapore](nlb-singapore/) | Search National Library Board Singapore catalog — availability, new arrivals, checkout trends |
| [umich-library-catalog](umich-library-catalog/) | Search University of Michigan Library via Alma SRU — CJK script fields, call numbers, availability |
| [princeton-library-catalog](princeton-library-catalog/) | Search Princeton University Library via Alma SRU — East Asian Library holdings, CJK script fields |
| [yale-library-catalog](yale-library-catalog/) | Search Yale University Library via Alma SRU, plus Yale LUX across libraries, museums, and archives |
| [pitt-library-catalog](pitt-library-catalog/) | Search University of Pittsburgh Library System (PittCat) via Alma SRU — CJK script fields, call numbers |
| [alma-sru-catalogs](alma-sru-catalogs/) | Search 21 research libraries at once via Alma SRU — US, UK, Canada, Australia, Taiwan; compare holdings, subject vocabularies, and classification |
| [mit-timdex](mit-timdex/) | Search MIT Libraries via TIMDEX GraphQL — catalog, DSpace@MIT theses, ArchivesSpace, digital collections |
| [northwestern-digital-collections](northwestern-digital-collections/) | Search Northwestern's digitized images, manuscripts, and media via its API or hosted MCP, with IIIF |
| [taiwan-ldt-authorities](taiwan-ldt-authorities/) | Taiwan LDT@Library authorities — Chinese name variants and sources, Chinese Subject Headings, Chinese classification |

### Scholarly Resources

| Skill | Description |
|-------|-------------|
| [arxiv-search](arxiv-search/) | Search arXiv preprints — field-specific queries, boolean logic, date filtering, bulk retrieval |
| [crossref-search](crossref-search/) | Search Crossref DOI metadata — articles, books, JSTOR chapters; DOI lookup, reference matching, citation formatting |
| [openaire-search](openaire-search/) | Search the OpenAIRE Graph — theses, repository copies, datasets, open-access versions of a DOI |
| [europeana-collections](europeana-collections/) | Search Europeana's 50M+ cultural heritage items from 4,000+ European institutions |
| [wikidata-search](wikidata-search/) | Search Wikidata via keyword, semantic/hybrid search, SPARQL, and direct entity retrieval |
| [zotero-local](zotero-local/) | Search, read, export, and add references in a local Zotero 8 desktop library via its HTTP API |

### Research & Evaluation Tools

| Skill | Description |
|-------|-------------|
| [human-eval-review](human-eval-review/) | Generate a single self-contained HTML file for human-in-the-loop evaluation — confirm candidate matches, pick, rate, judge, or correct model output, then export decisions as JSON |
| [argue-against-me](argue-against-me/) | Structured academic debate — Claude challenges your thesis from a chosen historiographical school, producing a scorecard, revised thesis, and bibliography gaps |

## Setup

There are two ways to install. Use A for all your projects, or B for one project.

### A. Add the marketplace (Claude Code)

In Claude Code, run:

```
/plugin marketplace add kltng/humanities-skills
/plugin install cbdb-api@humanities-skills
```

Or from the shell:

```bash
claude plugin marketplace add kltng/humanities-skills
claude plugin install cbdb-api@humanities-skills
```

Change `cbdb-api` to the skill you want. The skill names are the folder names in the tables above. New plugins load when you start Claude Code again, or after `/reload-plugins`.

To update later, run `/plugin marketplace update humanities-skills`.

**Pin a version.** Add `#` and a release tag to get a fixed version that will not change:

```
/plugin marketplace add kltng/humanities-skills#v2026-tutorials
```

`v2026-tutorials` is the version used in the 2026 tutorials. See the [releases page](https://github.com/kltng/humanities-skills/releases) for all tags. A commit hash does not work here; use a tag or a branch name.

### B. Copy skill folders into one project

```bash
git clone https://github.com/kltng/humanities-skills.git
mkdir -p .claude/skills
cp -R humanities-skills/cbdb-api .claude/skills/
```

Other agents look in other folders. For example, Codex reads skills from `.agents/skills/` (one project) or `~/.agents/skills/` (all projects).

### One-time setup for some skills

Most skills work right after install. A few need one more step. Each skill's `SKILL.md` explains it.

- **Download a database:** [cbdb-local](cbdb-local/), [tgaz-sqlite](tgaz-sqlite/), [cjk-calendar](cjk-calendar/)
- **Get an API key:** [nlb-singapore](nlb-singapore/) (required), [europeana-collections](europeana-collections/) (a demo key works for testing)
- **Run a desktop app:** [zotero-local](zotero-local/) needs Zotero 8 open on the same computer

You can also use the [skill-router](https://github.com/kltng/application-skills) to find and install skills as you need them.

## Conventions

- **UTF-8** for all Chinese/Japanese characters — never URL-encode CJK text
- **Rate-limit** API requests (0.5–1s between calls)
- **User-Agent** headers with contact info (required by Wikidata)

## Reporting Problems

Found a bug, a changed API, or wrong instructions? Please [open an issue](https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml). AI agents using these skills are welcome to file issues too. Each skill tells its agent to ask the user first and to leave out private data.

With the GitHub CLI:

```bash
gh issue create --repo kltng/humanities-skills --label bug --title "[skill-name] short summary"
```

## How to Cite

If these skills helped work you publish, please cite this repository. Please also cite the data source each skill uses (CBDB, CHGIS, the library catalog, etc.).

> Tang, Kwok-leong. *humanities-skills: Claude Code skills for East Asian and humanities research*. GitHub, 2026. https://github.com/kltng/humanities-skills

To cite one skill, add its name and version, e.g. *humanities-skills: cbdb-local* (version 1.0.1). GitHub's "Cite this repository" button (from `CITATION.cff`) gives APA and BibTeX formats.

## Structure

Each skill follows:

```
skill-name/
├── SKILL.md              # YAML frontmatter + instructions
├── references/           # API specs, command references
│   └── api_reference.md
└── scripts/              # Optional utility code
```
