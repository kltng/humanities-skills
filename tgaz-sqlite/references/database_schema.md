# TGAZ SQLite Database Schema

## Overview

SQLite conversion of the TGAZ (Temporal Gazetteer) — the China Historical GIS placename database from Harvard & Fudan University. Contains 82,117 historical placenames with 245,042 spellings spanning 763 BCE to 1911 CE.

**Data sources**: China Historical GIS (77K), Tibetan Buddhist Resource Center (3.6K), Historical Gazetteer of Russia (761).

**Upstream**: MySQL dump from [fccs-dci/containerized_tgaz](https://github.com/fccs-dci/containerized_tgaz). Live API at `https://chgis.hudci.org/tgaz/`.

## Tables

### `mv_pn_srch` — Primary Search Table

Pre-joined materialized view. **Start here for most queries.** 82K rows.

| Column | Description |
|--------|-------------|
| `sys_id` | Unique ID (e.g., `hvd_70621`) |
| `name` | Place name (Chinese) |
| `transcription` | Romanized name |
| `beg_yr` / `end_yr` | Temporal range (negative = BCE) |
| `x_coord` / `y_coord` | Longitude / Latitude (TEXT — cast to REAL for math) |
| `ftype_vn` | Feature type in Chinese (e.g., 县) |
| `ftype_tr` | Feature type romanized (e.g., xian) |
| `parent_sys_id` | Parent jurisdiction ID |
| `parent_vn` / `parent_tr` | Parent name (Chinese / romanized) |
| `data_src` | Source code (CHGIS, TBRC, HGR) |

### `placename`

Core table. 82K records with `sys_id` (e.g. `hvd_70621`), coordinates (`x_coord`/`y_coord`), temporal range (`beg_yr`/`end_yr`), feature type FK, data source FK.

### `spelling`

245K name forms (simplified Chinese, traditional Chinese, pinyin, Tibetan, etc.) linked to placenames via `placename_id`. Joined through `script` and `trsys` tables.

### `part_of`

83K jurisdictional parent-child relationships (`child_id` → `parent_id`) with temporal bounds.

### `ftype`

Feature type lookup (1,147 types). Fields: `name_vn` (native), `name_tr` (transcribed), `name_en` (English).

### `data_src`

Data source lookup. Join key is short code (e.g. `CHGIS`).

### `snote`

Historical notes (25K). Linked from `placename.snote_id`.

### `present_loc`

Present-day location mappings.

### `prec_by`

Predecessor relationships between placenames.

## Views

| View | What it joins |
|------|---------------|
| `v_search` | `mv_pn_srch` + `data_src` names. Best for LLM context serialization. |
| `v_placename` | `placename` + `data_src` + `ftype` joined. |
| `v_placename_names` | `placename` + `spelling` + `script` + `trsys`. |
| `v_full` | `placename` + `data_src` + `ftype` + `snote` + `present_loc`. |

## FTS5 Indexes

| Index | Content |
|-------|---------|
| `search_fts` | Names, transcriptions, feature types, parent names from `mv_pn_srch` |
| `spelling_fts` | All 245K written forms from `spelling` |
| `notes_fts` | Topics and full text from `snote` |

## Data Conventions

- **`sys_id`** is the universal identifier. Format: `hvd_NNNNN` (CHGIS), `TBRC_GNNNN` (Tibetan), `rgaz_NNNNNN` (Russian).
- **Coordinates**: Stored as TEXT in `placename` (`x_coord` = longitude, `y_coord` = latitude). Use `CAST(x_coord AS REAL)` for numeric comparisons. Views already do this.
- **Years**: Negative integers for BCE (`-202` = 202 BCE). `9999` means "still existing."
- **Feature types**: Three name columns: `name_vn` (Chinese/native), `name_tr` (romanized), `name_en` (English).

## Common Feature Types

| `ftype_tr` | `ftype_vn` | `name_en` |
|------------|------------|-----------|
| `xian` | 县 | county |
| `fu` | 府 | prefecture |
| `jun` | 郡 | commandery |
| `sheng` | 省 | province |
| `lu` | 路 | circuit |
| `dao` | 道 | circuit/route |
| `zhou` | 州 | prefecture |
| `guo` | 国 | kingdom/state |
| `dgon pa` | དགོན་པ། | monastery |
