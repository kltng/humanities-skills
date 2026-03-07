# CBDB SQLite Database Schema

656K+ biographical records of historical Chinese figures (7th c. BCE — 19th c. CE).
Over 90% of data pertains to Tang through early Qing dynasties.

## Core Table: BIOG_MAIN

| Column | Type | Description |
|---|---|---|
| `c_personid` | INTEGER PK | Unique person identifier — the universal join key |
| `c_name` | varchar | Pinyin name |
| `c_name_chn` | varchar | Chinese name |
| `c_surname_chn` | varchar | Chinese surname |
| `c_mingzi_chn` | varchar | Chinese given name |
| `c_surname_rm` | varchar | Romanized surname |
| `c_mingzi_rm` | varchar | Romanized given name |
| `c_dy` | smallint | Dynasty code (FK → DYNASTIES) |
| `c_birthyear` | smallint | Birth year (Western calendar) |
| `c_deathyear` | smallint | Death year (Western calendar) |
| `c_index_year` | INTEGER | Index year — algorithmically derived birth year estimate (see below) |
| `c_index_addr_id` | INTEGER | Index place — derived primary address (FK → ADDR_CODES) |
| `c_female` | smallint | 0 = male, 1 = female |
| `c_ethnicity_code` | smallint | Ethnicity (FK → ETHNICITY_TRIBE_CODES) |
| `c_choression_code` | smallint | Choronym/junwang for medieval clans (FK → CHORONYM_CODES) |
| `c_notes` | TEXT | Biographical notes |

### Index Year — How It's Calculated

The index year is an **artificial computed value** representing estimated birth year. Derivation priority:

1. Birth year directly known
2. Death year minus assumed age at death (male=60, female=55)
3. Degree year minus assumed age (jinshi=30, juren=25, xiucai=20)
4. Birth year of kin with offsets (father, children, brothers)
5. Index year of kin (iterative, less accurate each step)

**Caveat**: Many people have index_year = 0 (unknown). Filtering by index year silently excludes them. The `c_index_year_type` field indicates derivation method and reliability.

### Index Place — How It's Derived

Derived from a hierarchy of person-place association types (BIOG_ADDR_CODES):
1. Basic affiliation (籍贯)
2. Household address (户籍地) — Ming dynasty
3. Actual residence (落籍)
4. Last known address
5. Moved to
6. Eight Banners — Qing dynasty

## Relationship Data Tables

### ALTNAME_DATA — Alternative Names

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_alt_name_chn` | Alt name (Chinese) |
| `c_alt_name` | Alt name (pinyin) |
| `c_alt_name_type_code` | Type (FK → ALTNAME_CODES: 字 courtesy, 號 style, 諡號 posthumous, etc.) |
| `c_sequence` | Ordering within type |

### KIN_DATA — Kinship/Family

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_kin_id` | Related person ID |
| `c_kin_code` | Relationship type (FK → KINSHIP_CODES) |

**Kinship notation**: `F`=Father, `M`=Mother, `B`=Brother, `Z`=Sister, `S`=Son, `D`=Daughter, `H`=Husband, `W`=Wife, `C`=Concubine. Modifiers: `+`=elder, `-`=younger, `°`=adopted heir, `!`=adopted, `~`=half, `1/2`=step. `G-#`/`G+#` = lineal ancestor/descendant #th generation. `K`=lineage kin, `P`=biao (表) kin, `A`=affinal.

**Distance metrics** in KINSHIP_CODES: `c_upstep` (ancestor gen), `c_dwnstep` (descendant gen), `c_colstep` (collateral distance), `c_marstep` (marriage distance). Useful for filtering kinship by closeness.

### POSTING_DATA + POSTED_TO_OFFICE_DATA — Official Postings

`POSTING_DATA` is the container linking persons to postings. `POSTED_TO_OFFICE_DATA` holds office details. One posting may have multiple offices and addresses.

| Column (POSTED_TO_OFFICE_DATA) | Description |
|---|---|
| `c_personid` | Person ID |
| `c_posting_id` | Posting record ID |
| `c_office_id` | Office (FK → OFFICE_CODES) |
| `c_firstyear` / `c_lastyear` | Year range |
| `c_dy` | Dynasty of posting |
| `c_sequence` | Ordering |

### POSTED_TO_ADDR_DATA — Places of Official Service

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_posting_id` | Posting record ID |
| `c_addr_id` | Place of service (FK → ADDR_CODES) |
| `c_firstyear` / `c_lastyear` | Year range |

### ASSOC_DATA — Social Associations

Over 400 association types in 9 major categories (friendship, family, religion, finance, medicine, military, scholarship, politics, writings). Associations are **paired** — each has a converse (e.g., "is student of" / "is teacher of").

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_assoc_id` | Associated person ID |
| `c_assoc_code` | Association type (FK → ASSOC_CODES) |
| `c_assoc_count` | Number of events establishing the association |
| `c_assoc_first_year` | Start year (-9999 = unknown) |
| `c_kin_code` / `c_kin_id` | If association via a kin of the person |
| `c_assoc_kin_code` / `c_assoc_kin_id` | If via a kin of the associate |
| `c_assoc_claimer_id` | Who claimed the association (e.g., son claiming for father) |
| `c_addr_id` | Place of association |
| `c_inst_code` | Institution where association formed |
| `c_occasion_code` | Occasion of association |
| `c_genre_code` | Genre of writing establishing it |

### ENTRY_DATA — Examination/Entry into Government

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_entry_code` | Entry type (FK → ENTRY_CODES: 進士 jinshi, 舉人 juren, etc.) |
| `c_year` | Year of entry (0 = unknown) |
| `c_age` | Age at entry |
| `c_exam_rank` | Exam rank/result |
| `c_exam_field` | Exam field/subject |
| `c_entry_rel_code` | Kinship relation for yin privilege |
| `c_assoc_id` | Non-kin who facilitated entry |
| `c_addr_id` | Place of entry/examination |

### BIOG_ADDR_DATA — Person-Place Associations

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_addr_id` | Address (FK → ADDR_CODES) |
| `c_addr_type` | Address type (FK → BIOG_ADDR_CODES: 1=籍貫 basic affiliation, 4=last known, 5=moved to, etc.) |
| `c_firstyear` / `c_lastyear` | Year range |
| `c_sequence` | Ordering |

### STATUS_DATA — Social Status/Distinction

8 categories: occupation, scholarship, military distinction, imperial clan, artistic distinction, religious distinction, life events, commoner activity.

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_status_code` | Status type (FK → STATUS_CODES) |
| `c_firstyear` / `c_lastyear` | Year range |
| `c_supplement` | Additional info |
| `c_notes` | Notes |

### BIOG_TEXT_DATA — Person-Text Relations

Renamed from TEXT_DATA in the 2020 data release. Connects people to writings via roles (author, editor, annotator, etc.).

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_textid` | Text (FK → TEXT_CODES.c_textid) |
| `c_role_id` | Role (FK → TEXT_ROLE_CODES: author, annotator, compiler, editor, etc.) |
| `c_year` | Year |

### BIOG_INST_DATA — Person-Institution Relations

Links people to social institutions (academies, monasteries, temples) with their role. Institution names are in SOCIAL_INSTITUTION_NAME_CODES (joined via c_inst_name_code in SOCIAL_INSTITUTION_CODES).

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_inst_code` | Institution (FK → SOCIAL_INSTITUTION_CODES.c_inst_code) |
| `c_inst_name_code` | Institution name (FK → SOCIAL_INSTITUTION_NAME_CODES) |
| `c_bi_role_code` | Role (FK → BIOG_INST_CODES.c_bi_role_code) |
| `c_bi_begin_year` / `c_bi_end_year` | Year range |

**Note**: Multiple institutions may share the same name (e.g., 39 temples named 开元寺). When the specific one is unknown, `c_inst_code` = 0.

### BIOG_SOURCE_DATA — Bibliographic Sources

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_textid` | Source text (FK → TEXT_CODES) |
| `c_pages` | Page reference |

## Lookup/Code Tables

| Table | Description | Key Columns |
|---|---|---|
| `DYNASTIES` | Dynasty list (85) | `c_dy`, `c_dynasty`, `c_dynasty_chn`, `c_start`, `c_end` |
| `OFFICE_CODES` | Office titles (6,000+, tied to dynasty) | `c_office_id`, `c_office_chn`, `c_office_pinyin`, `c_office_trans` |
| `ADDR_CODES` | Place names (30K) with coordinates | `c_addr_id`, `c_name_chn`, `c_name`, `x_coord`, `y_coord`, `c_firstyear`, `c_lastyear` |
| `KINSHIP_CODES` | Kinship relations with distance metrics | `c_kincode`, `c_kinrel_chn`, `c_kinrel`, `c_upstep`, `c_dwnstep`, `c_colstep`, `c_marstep` |
| `ASSOC_CODES` | Association types (400+) | `c_assoc_code`, `c_assoc_desc_chn`, `c_assoc_desc` |
| `ENTRY_CODES` | Entry/exam types | `c_entry_code`, `c_entry_desc_chn`, `c_entry_desc` |
| `ALTNAME_CODES` | Name types | `c_name_type_code`, `c_name_type_desc_chn`, `c_name_type_desc` |
| `BIOG_ADDR_CODES` | Address relationship types | `c_addr_type`, `c_addr_desc_chn`, `c_addr_desc` |
| `STATUS_CODES` | Status types | `c_status_code`, `c_status_desc_chn`, `c_status_desc` |
| `TEXT_CODES` | Pre-modern writings + secondary works | `c_textid`, `c_title_chn`, `c_title`, `c_title_alt_chn` |
| `TEXT_ROLE_CODES` | Person-text role types | `c_role_id`, `c_role_desc_chn`, `c_role_desc` |
| `SOCIAL_INSTITUTION_CODES` | Academies, temples, etc. | `c_inst_code`, `c_inst_name_code` (FK → SOCIAL_INSTITUTION_NAME_CODES) |
| `SOCIAL_INSTITUTION_NAME_CODES` | Institution names | `c_inst_name_code`, `c_inst_name_hz`, `c_inst_name_py` |
| `BIOG_INST_CODES` | Person-institution role types | `c_bi_role_code`, `c_bi_role_chn`, `c_bi_role_desc` |
| `NIAN_HAO` | Reign period titles | `c_nianhao_id`, `c_nianhao_chn`, `c_nianhao` |
| `ETHNICITY_TRIBE_CODES` | Ethnic group codes (100+) | `c_ethnicity_code`, `c_name_chn`, `c_name` |
| `CHORONYM_CODES` | Junwang for medieval clans | `c_choression_code`, `c_choronym_chn` |
| `GANZHI_CODES` | 60 sexagenary cycle terms | `c_ganzhi_code`, `c_ganzhi_chn` |
| `APPOINTMENT_TYPE_CODES` | Regular, acting, probationary, etc. | `c_appt_type_code`, `c_appt_type_desc_chn` |
| `ASSUME_OFFICE_CODES` | Whether person accepted/declined posting | `c_assume_code`, `c_assume_desc_chn` |
| `OCCASION_CODES` | Events people participated in | `c_occasion_code`, `c_occasion_desc_chn` |

## Category/Type Tables (for grouping codes)

| Table | Purpose |
|---|---|
| `ASSOC_TYPES` | Groups association codes into categories |
| `ENTRY_TYPES` | Groups entry codes (examination, yin privilege, etc.) |
| `STATUS_TYPES` | Groups status codes (occupation, scholarship, etc.) |
| `OFFICE_CATEGORIES` | Groups offices (ranks, honorary, etc.) |
| `OFFICE_TYPE_TREE` | Hierarchical structure of bureaucracy (exists for Tang, Song, Yuan, Liao) |
| `SOCIAL_INSTITUTION_TYPES` | Groups institution types |
| `TEXT_TYPE` | Groups text types |
| `ASSOC_CODE_TYPE_REL` | Junction: association code → category |
| `ENTRY_CODE_TYPE_REL` | Junction: entry code → category |
| `OFFICE_CODE_TYPE_REL` | Junction: office → hierarchy |
| `STATUS_CODE_TYPE_REL` | Junction: status → category |

## ZZZ_ Denormalized Tables (Recommended for Queries)

These tables pre-join coded IDs with human-readable text strings. **Use these for raw SQL queries** — they simplify joins significantly.

| Table | Description |
|---|---|
| `ZZZ_BIOG_MAIN` | Person table with nianhao, ethnicity filled in — **recommended as primary person table** |
| `ZZZ_ALT_NAME_DATA` | Alt names with type descriptions |
| `ZZZ_BIOG_ADDR_DATA` | Address data with place name and type descriptions |
| `ZZZ_BIOG_TEXT_DATA` | Text data with person name, role, text info |
| `ZZZ_ENTRY_DATA` | Entry data with person name and entry type |
| `ZZZ_KIN_BIOG_ADDR` | Kinship with index place info included |
| `ZZZ_NONKIN_BIOG_ADDR` | Association data with index place info |
| `ZZZ_POSTED_TO_ADDR_DATA` | Postings with person name, office, address |
| `ZZZ_POSTED_TO_OFFICE_DATA` | Postings with person name and office info |
| `ZZZ_STATUS_DATA` | Status with person name and description |
| `ZZZ_BIOG_NAME_OFFICE` | Links surnames to posted office names (for searching) |

## Address / Geography Tables

| Table | Description |
|---|---|
| `ADDRESSES` | Convenience table with `belongs1`..`belongs5` for full hierarchy |
| `ADDR_CODES` | Administrative units with coordinates (`x_coord`/`y_coord` = lon/lat of seat) |
| `ADDR_BELONGS_DATA` | Parent-child hierarchy with temporal validity (`c_beg_yr`/`c_end_yr`) |
| `ADDR_XY` | Separate x-y coordinate table |
| `ADDR_PLACE_DATA` | Longitude/latitude data |
| `COUNTRY_CODES` | Country codes |

**Note**: CBDB uses administrative seat coordinates, not boundaries. An address ID changes only when the unit changes shape or name, NOT when it becomes part of a different parent unit.

## Dynasty Codes (Commonly Used)

| Code | Dynasty | Period |
|---|---|---|
| 4 | 漢 Han | 206 BCE – 220 CE |
| 10 | 唐 Tang | 618–907 |
| 15 | 宋 Song | 960–1279 |
| 28 | 元 Yuan | 1271–1368 |
| 30 | 明 Ming | 1368–1644 |
| 36 | 清 Qing | 1644–1912 |

**Important**: The entire Song dynasty uses a single code (15). It does NOT distinguish Northern from Southern Song. When querying "from Song to Song," CBDB matches the exact code, not temporal overlap.

Query `SELECT c_dy, c_dynasty, c_dynasty_chn FROM DYNASTIES ORDER BY c_dy` for the full list.

## Common Query Patterns

### Find person by name

```sql
-- Exact Chinese name
SELECT * FROM BIOG_MAIN WHERE c_name_chn = '蘇軾';

-- Pinyin (case-insensitive)
SELECT * FROM BIOG_MAIN WHERE c_name = 'Su Shi' COLLATE NOCASE;

-- Fuzzy match
SELECT * FROM BIOG_MAIN WHERE c_name_chn LIKE '%軾%' LIMIT 20;

-- Search via alt names (e.g., find by courtesy name 子瞻)
SELECT b.* FROM ALTNAME_DATA a
JOIN BIOG_MAIN b ON b.c_personid = a.c_personid
WHERE a.c_alt_name_chn = '子瞻';
```

### Get complete kinship network

```sql
SELECT b2.c_name_chn, kc.c_kinrel_chn, kc.c_kinrel,
       kc.c_upstep, kc.c_dwnstep, kc.c_colstep, kc.c_marstep
FROM KIN_DATA k
JOIN BIOG_MAIN b2 ON b2.c_personid = k.c_kin_id
JOIN KINSHIP_CODES kc ON kc.c_kincode = k.c_kin_code
WHERE k.c_personid = 3767
ORDER BY kc.c_kincode;
```

### Find jinshi holders using denormalized table

```sql
-- Much simpler than multi-table joins
SELECT * FROM ZZZ_ENTRY_DATA
WHERE c_entry_code = 36 AND c_year BETWEEN 1050 AND 1100;
```

### Find kin of jinshi holders with their entry modes

```sql
SELECT e1.c_personid, e1.c_person_name_chn,
       k.c_node_id, k.c_node_chn, k.c_link_desc,
       k.c_upstep, k.c_dwnstep, k.c_marstep, k.c_colstep,
       e2.c_entry_desc
FROM ZZZ_ENTRY_DATA e1
JOIN ZZZ_KIN_BIOG_ADDR k ON e1.c_personid = k.c_personid
LEFT JOIN ZZZ_ENTRY_DATA e2 ON k.c_node_id = e2.c_personid
WHERE e1.c_entry_code = 36 AND e1.c_year = 1148
AND k.c_upstep <= 2 AND k.c_dwnstep = 0
AND k.c_marstep = 0 AND k.c_colstep <= 1;
```

### Find all Song dynasty jinshi

```sql
SELECT b.c_name_chn, b.c_name, e.c_year, e.c_exam_rank
FROM ENTRY_DATA e
JOIN BIOG_MAIN b ON b.c_personid = e.c_personid
WHERE e.c_entry_code = 36 AND b.c_dy = 15
ORDER BY e.c_year
LIMIT 50;
```

### Find officials who served in a specific office

```sql
SELECT b.c_name_chn, po.c_firstyear, po.c_lastyear
FROM POSTED_TO_OFFICE_DATA po
JOIN BIOG_MAIN b ON b.c_personid = po.c_personid
JOIN OFFICE_CODES oc ON oc.c_office_id = po.c_office_id
WHERE oc.c_office_chn LIKE '%宰相%'
ORDER BY po.c_firstyear
LIMIT 20;
```

### Find office holders at a place (using denormalized table)

```sql
SELECT * FROM ZZZ_POSTED_TO_ADDR_DATA
WHERE c_addr_id = 101538;
```

### People associated with a place

```sql
SELECT b.c_name_chn, bac.c_addr_desc_chn, ba.c_firstyear
FROM BIOG_ADDR_DATA ba
JOIN BIOG_MAIN b ON b.c_personid = ba.c_personid
JOIN ADDR_CODES ac ON ac.c_addr_id = ba.c_addr_id
JOIN BIOG_ADDR_CODES bac ON bac.c_addr_type = ba.c_addr_type
WHERE ac.c_name_chn LIKE '%眉山%'
ORDER BY b.c_index_year
LIMIT 20;
```

### Texts by a person

```sql
SELECT tc.c_title_chn, trc.c_role_desc_chn, bt.c_year
FROM BIOG_TEXT_DATA bt
JOIN TEXT_CODES tc ON tc.c_textid = bt.c_textid
LEFT JOIN TEXT_ROLE_CODES trc ON trc.c_role_id = bt.c_role_id
WHERE bt.c_personid = 3767;
```

### Cross-dynastic office comparison

```sql
-- Office codes are dynasty-specific. Search by Chinese name to find equivalents:
SELECT c_office_id, c_office_chn, c_office_trans, c_dy
FROM OFFICE_CODES
WHERE c_office_chn LIKE '%知州%'
ORDER BY c_dy;
```

## Join Patterns

### Person → Place
```
BIOG_MAIN.c_personid = BIOG_ADDR_DATA.c_personid
BIOG_ADDR_DATA.c_addr_id = ADDR_CODES.c_addr_id
BIOG_ADDR_DATA.c_addr_type = BIOG_ADDR_CODES.c_addr_type
```

### Person → Office → Place
```
BIOG_MAIN.c_personid = POSTING_DATA.c_personid
POSTING_DATA.c_posting_id = POSTED_TO_OFFICE_DATA.c_posting_id
POSTED_TO_OFFICE_DATA.c_office_id = OFFICE_CODES.c_office_id
POSTING_DATA.c_posting_id = POSTED_TO_ADDR_DATA.c_posting_id
POSTED_TO_ADDR_DATA.c_addr_id = ADDR_CODES.c_addr_id
```

### Person → Text
```
BIOG_MAIN.c_personid = BIOG_TEXT_DATA.c_personid
BIOG_TEXT_DATA.c_textid = TEXT_CODES.c_textid
BIOG_TEXT_DATA.c_role_id = TEXT_ROLE_CODES.c_role_id
```

### Person → Institution
```
BIOG_MAIN.c_personid = BIOG_INST_DATA.c_personid
BIOG_INST_DATA.c_inst_code = SOCIAL_INSTITUTION_CODES.c_inst_code
SOCIAL_INSTITUTION_CODES.c_inst_name_code = SOCIAL_INSTITUTION_NAME_CODES.c_inst_name_code
BIOG_INST_DATA.c_bi_role_code = BIOG_INST_CODES.c_bi_role_code
```

### Code → Category (for filtering by type)
```
ASSOC_CODES.c_assoc_code = ASSOC_CODE_TYPE_REL.c_assoc_code → ASSOC_TYPES.c_assoc_type_id
ENTRY_CODES.c_entry_code = ENTRY_CODE_TYPE_REL.c_entry_code → ENTRY_TYPES.c_entry_type_id
OFFICE_CODES.c_office_id = OFFICE_CODE_TYPE_REL.c_office_id
STATUS_CODES.c_status_code = STATUS_CODE_TYPE_REL.c_status_code
```

## Gotchas and Caveats

1. **Factoids, not facts**: CBDB records assertions from sources, not verified facts. Contradictory assertions may coexist.

2. **Index year = artificial**: It's a derived estimate, not a real date. May be off by a decade for iteratively derived values. Many people have index_year = 0 (unknown) and are silently excluded by year filters.

3. **Song dynasty = one code**: Code 15 covers both Northern and Southern Song. No distinction.

4. **Office codes are dynasty-bound**: A Song office code returns no results when filtered to Ming. Search by Chinese office name for cross-dynasty comparison.

5. **Entry year = 0 means unknown**: Many entry records lack dates. Use index year as fallback for time filtering.

6. **Association dates usually empty**: Filter by index year of the individuals instead.

7. **Place names change across dynasties**: Use XY-coordinate proximity searches to track locations across name changes. Include subordinate administrative units in searches to capture counties under a prefecture.

8. **Extended kinship = large datasets**: Start with conservative distance parameters (e.g., upstep ≤ 2, colstep ≤ 1).

9. **TEXT_DATA renamed**: Now called BIOG_TEXT_DATA since the 2020 data release. Old SQL queries using TEXT_DATA need updating.

10. **Encoding**: All Chinese text is UTF-8. Never URL-encode Chinese characters.

## Indexes (Created by Setup)

- `idx_biog_name_chn` on `BIOG_MAIN(c_name_chn)`
- `idx_biog_name` on `BIOG_MAIN(c_name)`
- `idx_biog_dy` on `BIOG_MAIN(c_dy)`
- `idx_altname_personid` on `ALTNAME_DATA(c_personid)`
- `idx_altname_chn` on `ALTNAME_DATA(c_alt_name_chn)`
- `idx_kin_personid` on `KIN_DATA(c_personid)`
- `idx_kin_id` on `KIN_DATA(c_kin_id)`
- `idx_posting_personid` on `POSTING_DATA(c_personid)`
- `idx_posted_office_personid` on `POSTED_TO_OFFICE_DATA(c_personid)`
- `idx_assoc_personid` on `ASSOC_DATA(c_personid)`
- `idx_assoc_id` on `ASSOC_DATA(c_assoc_id)`
- `idx_entry_personid` on `ENTRY_DATA(c_personid)`
- `idx_biog_addr_personid` on `BIOG_ADDR_DATA(c_personid)`
- `idx_status_personid` on `STATUS_DATA(c_personid)`
- `idx_biog_text_personid` on `BIOG_TEXT_DATA(c_personid)`
- `idx_biog_inst_personid` on `BIOG_INST_DATA(c_personid)`
- `idx_posted_addr_personid` on `POSTED_TO_ADDR_DATA(c_personid)`
