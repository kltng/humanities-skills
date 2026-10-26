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
| [columbia-clio](columbia-clio/) | Search Columbia University Libraries' CLIO catalog via Blacklight JSON API |
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
| [europeana-collections](europeana-collections/) | Search Europeana's 50M+ cultural heritage items from 4,000+ European institutions |
| [wikidata-search](wikidata-search/) | Search Wikidata via keyword, semantic/hybrid search, SPARQL, and direct entity retrieval |
| [zotero-local](zotero-local/) | Interact with local Zotero 8 desktop via HTTP API — search, fetch, add, organize references |

### Research & Evaluation Tools

| Skill | Description |
|-------|-------------|
| [human-eval-review](human-eval-review/) | Generate a single self-contained HTML file for human-in-the-loop evaluation — confirm candidate matches, pick, rate, judge, or correct model output, then export decisions as JSON |
| [argue-against-me](argue-against-me/) | Structured academic debate — Claude challenges your thesis from a chosen historiographical school, producing a scorecard, revised thesis, and bibliography gaps |

## Setup

Install as a Claude Code skill marketplace:

```json
{
  "skills": [
    "$HOME/skill-hub/humanities-skills/cbdb-api/SKILL.md"
  ]
}
```

Or use the [skill-router](https://github.com/kltng/application-skills) to auto-discover and install skills as needed.

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
