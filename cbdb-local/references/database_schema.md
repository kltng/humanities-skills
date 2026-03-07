# CBDB SQLite Database Schema

656K+ biographical records of historical Chinese figures (7th c. BCE — 19th c. CE).

## Core Table: BIOG_MAIN

| Column | Type | Description |
|---|---|---|
| `c_personid` | INTEGER PK | Unique person identifier |
| `c_name` | varchar | Pinyin name |
| `c_name_chn` | varchar | Chinese name |
| `c_surname_chn` | varchar | Chinese surname |
| `c_mingzi_chn` | varchar | Chinese given name |
| `c_surname_rm` | varchar | Romanized surname |
| `c_mingzi_rm` | varchar | Romanized given name |
| `c_dy` | smallint | Dynasty code (FK → DYNASTIES) |
| `c_birthyear` | smallint | Birth year |
| `c_deathyear` | smallint | Death year |
| `c_index_year` | INTEGER | Index year (for sorting) |
| `c_female` | smallint | 1 = female |
| `c_ethnicity_code` | smallint | Ethnicity code |
| `c_index_addr_id` | INTEGER | Primary address (FK → ADDR_CODES) |
| `c_notes` | TEXT | Biographical notes |

## Relationship Tables

### ALTNAME_DATA — Alternative Names

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_alt_name_chn` | Alt name (Chinese) |
| `c_alt_name` | Alt name (pinyin) |
| `c_alt_name_type_code` | Type (FK → ALTNAME_CODES: 字 courtesy, 號 style, 諡號 posthumous, etc.) |

### KIN_DATA — Kinship/Family

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_kin_id` | Related person ID |
| `c_kin_code` | Relationship type (FK → KINSHIP_CODES: F=father, M=mother, S=son, etc.) |

### POSTING_DATA + POSTED_TO_OFFICE_DATA — Official Postings

`POSTING_DATA` links persons to postings. `POSTED_TO_OFFICE_DATA` links postings to offices.

| Column (POSTED_TO_OFFICE_DATA) | Description |
|---|---|
| `c_personid` | Person ID |
| `c_posting_id` | Posting record ID |
| `c_office_id` | Office (FK → OFFICE_CODES) |
| `c_firstyear` / `c_lastyear` | Year range |
| `c_dy` | Dynasty of posting |

### ASSOC_DATA — Social Associations

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_assoc_id` | Associated person ID |
| `c_assoc_code` | Association type (FK → ASSOC_CODES) |
| `c_assoc_first_year` | Start year (-9999 = unknown) |

### ENTRY_DATA — Examination/Entry

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_entry_code` | Entry type (FK → ENTRY_CODES: 進士 jinshi, 舉人 juren, etc.) |
| `c_year` | Year of entry |
| `c_exam_rank` | Exam rank/result |
| `c_exam_field` | Exam field/subject |

### BIOG_ADDR_DATA — Person-Place Associations

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_addr_id` | Address (FK → ADDR_CODES) |
| `c_addr_type` | Address type (FK → BIOG_ADDR_CODES: 籍貫 native place, etc.) |
| `c_firstyear` / `c_lastyear` | Year range |

### STATUS_DATA — Social Status

| Column | Description |
|---|---|
| `c_personid` | Person ID |
| `c_status_code` | Status type (FK → STATUS_CODES) |
| `c_firstyear` / `c_lastyear` | Year range |

## Lookup/Code Tables

| Table | Description | Key Columns |
|---|---|---|
| `DYNASTIES` | Dynasty list (85) | `c_dy`, `c_dynasty`, `c_dynasty_chn`, `c_start`, `c_end` |
| `OFFICE_CODES` | Office titles (34K) | `c_office_id`, `c_office_chn`, `c_office_pinyin`, `c_office_trans` |
| `ADDR_CODES` | Place names (30K) | `c_addr_id`, `c_name_chn`, `c_name`, `x_coord`, `y_coord` |
| `KINSHIP_CODES` | Kinship relations | `c_kincode`, `c_kinrel_chn`, `c_kinrel` |
| `ASSOC_CODES` | Association types | `c_assoc_code`, `c_assoc_desc_chn`, `c_assoc_desc` |
| `ENTRY_CODES` | Entry/exam types | `c_entry_code`, `c_entry_desc_chn`, `c_entry_desc` |
| `ALTNAME_CODES` | Name types | `c_name_type_code`, `c_name_type_desc_chn`, `c_name_type_desc` |
| `BIOG_ADDR_CODES` | Address types | `c_addr_type`, `c_addr_desc_chn`, `c_addr_desc` |
| `STATUS_CODES` | Status types | `c_status_code`, `c_status_desc_chn`, `c_status_desc` |

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
SELECT b2.c_name_chn, kc.c_kinrel_chn, kc.c_kinrel
FROM KIN_DATA k
JOIN BIOG_MAIN b2 ON b2.c_personid = k.c_kin_id
JOIN KINSHIP_CODES kc ON kc.c_kincode = k.c_kin_code
WHERE k.c_personid = 3767
ORDER BY kc.c_kincode;
```

### Find all jinshi degree holders in Song dynasty

```sql
SELECT b.c_name_chn, b.c_name, e.c_year, e.c_exam_rank
FROM ENTRY_DATA e
JOIN BIOG_MAIN b ON b.c_personid = e.c_personid
JOIN ENTRY_CODES ec ON ec.c_entry_code = e.c_entry_code
WHERE ec.c_entry_desc_chn LIKE '%進士%' AND b.c_dy = 15
ORDER BY e.c_year
LIMIT 50;
```

### Dynasty codes (commonly used)

| Code | Dynasty |
|---|---|
| 4 | 漢 Han |
| 10 | 唐 Tang |
| 15 | 宋 Song (Northern) |
| 20 | 宋 Song (Southern) |
| 28 | 元 Yuan |
| 30 | 明 Ming |
| 36 | 清 Qing |

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

### Persons associated with a place

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

## Indexes (Created by Setup)

The setup script creates these indexes for fast queries:

- `idx_biog_name_chn` on `BIOG_MAIN(c_name_chn)` — Chinese name search
- `idx_biog_name` on `BIOG_MAIN(c_name)` — Pinyin name search
- `idx_biog_dy` on `BIOG_MAIN(c_dy)` — Dynasty filter
- `idx_altname_personid` on `ALTNAME_DATA(c_personid)` — Alt name lookup by person
- `idx_altname_chn` on `ALTNAME_DATA(c_alt_name_chn)` — Search by alt name
- `idx_kin_personid` on `KIN_DATA(c_personid)` — Kinship lookup
- `idx_posting_personid` on `POSTING_DATA(c_personid)` — Posting lookup
- `idx_posted_office_personid` on `POSTED_TO_OFFICE_DATA(c_personid)` — Office lookup
- `idx_assoc_personid` on `ASSOC_DATA(c_personid)` — Association lookup
- `idx_entry_personid` on `ENTRY_DATA(c_personid)` — Entry lookup
- `idx_biog_addr_personid` on `BIOG_ADDR_DATA(c_personid)` — Address lookup
- `idx_status_personid` on `STATUS_DATA(c_personid)` — Status lookup
