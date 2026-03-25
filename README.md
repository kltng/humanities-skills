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

### Scholarly Resources

| Skill | Description |
|-------|-------------|
| [arxiv-search](arxiv-search/) | Search arXiv preprints — field-specific queries, boolean logic, date filtering, bulk retrieval |
| [europeana-collections](europeana-collections/) | Search Europeana's 50M+ cultural heritage items from 4,000+ European institutions |
| [wikidata-search](wikidata-search/) | Search Wikidata via keyword, semantic/hybrid search, SPARQL, and direct entity retrieval |
| [zotero-local](zotero-local/) | Interact with local Zotero 8 desktop via HTTP API — search, fetch, add, organize references |

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

## Structure

Each skill follows:

```
skill-name/
├── SKILL.md              # YAML frontmatter + instructions
├── references/           # API specs, command references
│   └── api_reference.md
└── scripts/              # Optional utility code
```
