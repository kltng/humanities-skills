# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Claude Code skill marketplace** for academic research on Chinese historical and geographical data. Each skill wraps an external API and is primarily documentation-driven. Skills are registered in `.claude-plugin/marketplace.json`.

## Repository Structure

Each skill follows a consistent layout:

```
<skill-name>/
├── SKILL.md                  # Main documentation (YAML frontmatter + usage guide)
└── references/
    └── api_reference.md      # Technical API spec (endpoints, params, responses)
```

Optional: a `scripts/` directory for utility code (see `wikidata-search/scripts/wikidata_api.py`).

### Current Skills

- **cbdb-api** — China Biographical Database (500K+ historical figures, 7th c. BCE–19th c. CE)
- **chgis-tgaz** — China Historical GIS Temporal Gazetteer (placenames, 222 BCE–1911 CE)
- **wikidata-search** — Wikidata integration (keyword, vector, SPARQL, entity retrieval)

## Build & Development

There is no build system, package manager, test suite, or CI pipeline. This is a documentation-first project. The only code is `wikidata-search/scripts/wikidata_api.py` (Python 3, zero external dependencies).

## Conventions

### Adding a New Skill

1. Create a directory with a hyphenated name (e.g., `new-skill-name/`)
2. Add `SKILL.md` with YAML frontmatter (name, description, version, license, author, contributors)
3. Add `references/api_reference.md` with endpoint details, parameters, and examples
4. Register in `.claude-plugin/marketplace.json` under `plugins`

### SKILL.md Structure

Each SKILL.md follows this pattern: Overview → When to Use → Quick Start / Workflow → Best Practices → Example Code → Resources.

### API Etiquette (enforced across all skills)

- Rate-limit requests (0.5–1s minimum between calls)
- Set `User-Agent` headers with contact info (required by Wikidata Vector DB and WDQS)
- Respect HTTP 429 / `Retry-After` headers
- Use `maxlag` parameter for Wikidata Action API queries

### Text Encoding

- UTF-8 for all Chinese characters — do **not** URL-encode Chinese text into hex
- URL-encode spaces and special characters normally

### API Quirks

- **CHGIS TGAZ ID lookups**: Format is in the URL path (`/placename/json/{id}`), NOT a query param. The `?fmt=json` param only works for faceted search.
- **CHGIS TGAZ search**: Uses prefix/wildcard matching (`beijing` matches 北京路, 北井县, etc.)
- **CBDB JSON path**: Response data is deeply nested under `Package.PersonAuthority.PersonInfo.Person`
- **Wikidata Vector DB**: Requires a descriptive `User-Agent` header or returns 403

### Python Style (wikidata_api.py)

- Type hints on all signatures
- Private methods prefixed with `_`
- Rate limiting and retry with exponential backoff built in
- Environment variable `WIKIDATA_VECTORDB_API_SECRET` for vector DB auth
