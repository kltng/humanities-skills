#!/usr/bin/env python3
"""
Convert the TGAZ MySQL dump to SQLite, preserving the full relational schema.
Then create denormalized views and FTS5 indexes for easy querying.
"""

import re
import sqlite3
import sys
import time

MYSQL_DUMP = "/tmp/tgaz_repo/mysql-init/02-tgaz-dev-2018.sql"
DB_PATH = "tgaz.db"

# Hand-written SQLite schema from the MySQL definitions
SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_seat (
    id INTEGER PRIMARY KEY,
    placename_id INTEGER NOT NULL,
    seat_id INTEGER NOT NULL,
    begin_date TEXT,
    end_date TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS alt_name3 (
    order_id INTEGER PRIMARY KEY,
    name_py TEXT,
    name_utf TEXT,
    name_utf_alt TEXT,
    type_py TEXT,
    type_utf TEXT,
    type_id TEXT,
    type_eng TEXT,
    beg_yr INTEGER,
    end_yr INTEGER,
    pgn_id TEXT,
    pt_id TEXT,
    line_id TEXT,
    data_src TEXT,
    parent_utf TEXT,
    parent_py TEXT
);

CREATE TABLE IF NOT EXISTS citation_ref (
    ref_handle TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    uri TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS ck1 (
    id INTEGER PRIMARY KEY,
    name_id TEXT,
    y TEXT,
    x TEXT
);

CREATE TABLE IF NOT EXISTS data_src (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    org TEXT,
    uri TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS drule (
    id INTEGER PRIMARY KEY,
    name TEXT,
    rule TEXT,
    ld_vocab TEXT,
    ld_uri TEXT
);

CREATE TABLE IF NOT EXISTS f2 (
    name TEXT,
    sys_id TEXT NOT NULL,
    x_coord TEXT,
    y_coord TEXT,
    auto_id INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS ftype (
    id INTEGER PRIMARY KEY,
    name_vn TEXT,
    name_alt TEXT,
    name_tr TEXT,
    name_en TEXT,
    period TEXT,
    adl_class TEXT,
    cit_src TEXT,
    citation TEXT,
    note TEXT,
    ld_uri TEXT,
    added_on TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ftype_xx (
    order_id INTEGER PRIMARY KEY,
    lang TEXT,
    name_py TEXT,
    name_ch TEXT,
    id TEXT,
    name_en TEXT,
    name_alt TEXT,
    adl_class TEXT,
    period TEXT,
    cit_src TEXT,
    note TEXT,
    status TEXT,
    ts_added TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS geom (
    id INTEGER PRIMARY KEY,
    placename_id INTEGER NOT NULL,
    g TEXT,
    src TEXT,
    updated_on TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gis_xx (
    order_id INTEGER PRIMARY KEY,
    name_py TEXT,
    name_utf TEXT,
    name_utf_alt TEXT,
    sys_id TEXT NOT NULL DEFAULT '',
    xy_type TEXT,
    x_coord TEXT,
    y_coord TEXT,
    pres_loc TEXT,
    type_py TEXT,
    type_utf TEXT,
    lev_rank TEXT,
    beg_yr INTEGER,
    beg_rule TEXT,
    beg_chg_type TEXT,
    end_yr INTEGER,
    end_rule TEXT,
    end_chg_type TEXT,
    note_id TEXT,
    obj_type TEXT,
    geo_src TEXT,
    compiler TEXT,
    geocompiler TEXT,
    checker TEXT,
    filename TEXT,
    src TEXT
);

CREATE TABLE IF NOT EXISTS link (
    id INTEGER PRIMARY KEY,
    placename_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    source TEXT NOT NULL,
    uri TEXT NOT NULL,
    lang TEXT
);

CREATE TABLE IF NOT EXISTS main_xx (
    sys_id TEXT NOT NULL,
    nm_py TEXT,
    nm_simp TEXT,
    name_trad TEXT,
    orig_ID TEXT,
    beg_yr INTEGER,
    end_yr INTEGER,
    xy_type TEXT,
    x_coord TEXT,
    y_coord TEXT,
    pres_loc TEXT,
    type_py TEXT,
    type_utf TEXT,
    type_id TEXT,
    type_eng TEXT,
    lev_rank TEXT,
    note_id TEXT,
    nt_auto TEXT,
    obj_type TEXT,
    data_src TEXT,
    auto_id INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS mv_pn_srch (
    id INTEGER PRIMARY KEY,
    sys_id TEXT NOT NULL,
    data_src TEXT NOT NULL,
    name TEXT,
    transcription TEXT,
    beg_yr INTEGER,
    end_yr INTEGER,
    obj_type TEXT,
    x_coord TEXT,
    y_coord TEXT,
    ftype_vn TEXT,
    ftype_tr TEXT,
    parent_id INTEGER,
    parent_sys_id TEXT,
    parent_vn TEXT,
    parent_tr TEXT
);

CREATE TABLE IF NOT EXISTS mv_pn_srch_new_test (
    id INTEGER PRIMARY KEY,
    sys_id TEXT NOT NULL,
    data_src TEXT NOT NULL,
    name TEXT,
    transcription TEXT,
    beg_yr INTEGER,
    end_yr INTEGER,
    x_coord TEXT,
    y_coord TEXT,
    ftype_vn TEXT,
    ftype_tr TEXT,
    parent_id INTEGER,
    parent_sys_id TEXT,
    parent_vn TEXT,
    parent_tr TEXT
);

CREATE TABLE IF NOT EXISTS mv_pn_srch_old (
    id INTEGER,
    sys_id TEXT NOT NULL,
    data_src TEXT NOT NULL,
    name TEXT,
    transcription TEXT,
    beg_yr INTEGER,
    end_yr INTEGER,
    x_coord TEXT,
    y_coord TEXT,
    ftype_vn TEXT,
    ftype_tr TEXT,
    parent_id INTEGER,
    parent_sys_id TEXT,
    parent_vn TEXT,
    parent_tr TEXT,
    counter_id INTEGER
);

CREATE TABLE IF NOT EXISTS part_of (
    id INTEGER PRIMARY KEY,
    child_id INTEGER NOT NULL,
    parent_id INTEGER NOT NULL,
    begin_year INTEGER,
    end_year INTEGER
);

CREATE TABLE IF NOT EXISTS partof_xx (
    order_id INTEGER NOT NULL,
    child_id TEXT,
    parent_id TEXT,
    beg_yr TEXT,
    end_yr TEXT
);

CREATE TABLE IF NOT EXISTS placename (
    id INTEGER PRIMARY KEY,
    sys_id TEXT NOT NULL,
    ftype_id INTEGER NOT NULL,
    data_src TEXT NOT NULL,
    data_src_ref TEXT,
    snote_id INTEGER,
    alt_of_id INTEGER,
    lev_rank TEXT,
    beg_yr INTEGER,
    beg_rule_id INTEGER,
    end_yr INTEGER,
    end_rule_id INTEGER,
    obj_type TEXT,
    xy_type TEXT,
    x_coord TEXT,
    y_coord TEXT,
    geo_src TEXT,
    added_on TEXT DEFAULT CURRENT_TIMESTAMP,
    default_parent_id INTEGER,
    parent_status TEXT DEFAULT 'earliest'
);

CREATE TABLE IF NOT EXISTS prec_by (
    id INTEGER PRIMARY KEY,
    placename_id INTEGER NOT NULL,
    prec_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS precby_xx (
    pby_id TEXT NOT NULL DEFAULT '',
    pby_nmpy TEXT,
    pby_nmch TEXT,
    pby_nmft TEXT,
    pby_obj_type TEXT,
    pby_prev_id TEXT,
    pby_prev_nmpy TEXT,
    pby_prev_nmch TEXT,
    pby_prev_nmft TEXT,
    pby_uniq_id INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS present_loc (
    id INTEGER PRIMARY KEY,
    placename_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    country_code TEXT NOT NULL,
    text_value TEXT NOT NULL,
    source TEXT,
    attestation TEXT,
    source_uri TEXT
);

CREATE TABLE IF NOT EXISTS script (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    lang TEXT NOT NULL,
    dialect TEXT,
    default_per_lang INTEGER DEFAULT 0,
    note TEXT
);

CREATE TABLE IF NOT EXISTS snote (
    id INTEGER PRIMARY KEY,
    src_note_ref TEXT,
    source TEXT,
    compiler TEXT,
    lang TEXT,
    topic TEXT,
    uri TEXT,
    full_text TEXT,
    added_on TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS snote_xx (
    nts_comp TEXT,
    nts_noteid TEXT,
    nts_nmpy TEXT,
    nts_nmch TEXT,
    nts_nmft TEXT,
    nts_fullnote TEXT,
    nts_autoid INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS spatial_system_ref (
    id INTEGER PRIMARY KEY,
    placename_id INTEGER NOT NULL,
    system_name TEXT NOT NULL,
    level INTEGER,
    location_uri TEXT,
    location_id TEXT
);

CREATE TABLE IF NOT EXISTS spelling (
    id INTEGER PRIMARY KEY,
    placename_id INTEGER NOT NULL,
    script_id INTEGER NOT NULL,
    written_form TEXT NOT NULL,
    exonym_lang TEXT,
    trsys_id TEXT NOT NULL,
    default_per_type INTEGER DEFAULT 0,
    attested_by TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS tbt_rev (
    id INTEGER PRIMARY KEY,
    name_id TEXT,
    y TEXT,
    x TEXT
);

CREATE TABLE IF NOT EXISTS temporal_annotation (
    id INTEGER PRIMARY KEY,
    placename_id INTEGER NOT NULL,
    temporal_type TEXT,
    calendar_standard TEXT,
    rule_id INTEGER,
    attested_by TEXT,
    equivalent TEXT,
    lang TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS trsys (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lang TEXT NOT NULL,
    lang_subtype TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS v5_id (
    id INTEGER PRIMARY KEY,
    flag TEXT,
    sys_id TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS v6_id (
    id INTEGER PRIMARY KEY,
    flag TEXT,
    sys_id TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS wkt_definition (
    id INTEGER PRIMARY KEY,
    placename_id INTEGER NOT NULL,
    object_type TEXT NOT NULL,
    object_text_value TEXT
);
"""


def process_inserts(conn, dump_path):
    """Parse INSERT statements from MySQL dump and execute them in SQLite."""
    table_rows = {}
    insert_buffer = ""

    with open(dump_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()

            # Skip non-INSERT lines
            if not insert_buffer:
                if not line.startswith("INSERT INTO"):
                    continue
                insert_buffer = raw_line
                if line.endswith(";"):
                    _exec_insert(conn, insert_buffer, table_rows)
                    insert_buffer = ""
            else:
                insert_buffer += raw_line
                if line.endswith(";"):
                    _exec_insert(conn, insert_buffer, table_rows)
                    insert_buffer = ""

    conn.commit()
    return table_rows


def _exec_insert(conn, sql, table_rows):
    """Execute a single INSERT statement, converting MySQL syntax to SQLite."""
    m = re.match(r"INSERT INTO `(\w+)`", sql)
    if not m:
        return
    table = m.group(1)

    # Convert MySQL to SQLite syntax
    sql = sql.replace("`", "")

    # Replace hex geometry data with NULL
    sql = re.sub(r"0x[0-9A-Fa-f]+", "NULL", sql)

    # Fix MySQL string escaping for SQLite
    # We need to be careful: replace \' with '' but NOT inside already-doubled quotes
    sql = sql.replace("\\'", "''")
    sql = sql.replace('\\"', '"')
    sql = sql.replace("\\r\\n", "\n")
    sql = sql.replace("\\n", "\n")
    sql = sql.replace("\\r", "\r")
    sql = sql.replace("\\t", "\t")
    sql = sql.replace("\\\\", "\\")

    try:
        conn.executescript(sql)
        count = sql.count("),(") + 1
        table_rows[table] = table_rows.get(table, 0) + count
    except sqlite3.Error as e:
        # Try with OR IGNORE
        try:
            sql2 = sql.replace(f"INSERT INTO {table}", f"INSERT OR IGNORE INTO {table}", 1)
            conn.executescript(sql2)
            count = sql2.count("),(") + 1
            table_rows[table] = table_rows.get(table, 0) + count
        except sqlite3.Error as e2:
            print(f"  WARNING: {table}: {str(e2)[:80]}")


def create_indexes(conn):
    print("Creating indexes...")
    indexes = """
        CREATE INDEX IF NOT EXISTS idx_pn_sys_id ON placename(sys_id);
        CREATE INDEX IF NOT EXISTS idx_pn_ftype ON placename(ftype_id);
        CREATE INDEX IF NOT EXISTS idx_pn_datasrc ON placename(data_src);
        CREATE INDEX IF NOT EXISTS idx_pn_years ON placename(beg_yr, end_yr);
        CREATE INDEX IF NOT EXISTS idx_pn_coords ON placename(x_coord, y_coord);
        CREATE INDEX IF NOT EXISTS idx_pn_parent ON placename(default_parent_id);
        CREATE INDEX IF NOT EXISTS idx_sp_pn ON spelling(placename_id);
        CREATE INDEX IF NOT EXISTS idx_sp_form ON spelling(written_form);
        CREATE INDEX IF NOT EXISTS idx_sp_script ON spelling(script_id);
        CREATE INDEX IF NOT EXISTS idx_partof_child ON part_of(child_id);
        CREATE INDEX IF NOT EXISTS idx_partof_parent ON part_of(parent_id);
        CREATE INDEX IF NOT EXISTS idx_presloc_pn ON present_loc(placename_id);
        CREATE INDEX IF NOT EXISTS idx_snote_ref ON snote(src_note_ref);
        CREATE INDEX IF NOT EXISTS idx_precby_pn ON prec_by(placename_id);
        CREATE INDEX IF NOT EXISTS idx_precby_prec ON prec_by(prec_id);
        CREATE INDEX IF NOT EXISTS idx_link_pn ON link(placename_id);
        CREATE INDEX IF NOT EXISTS idx_mv_sysid ON mv_pn_srch(sys_id);
        CREATE INDEX IF NOT EXISTS idx_mv_name ON mv_pn_srch(name);
        CREATE INDEX IF NOT EXISTS idx_mv_trans ON mv_pn_srch(transcription);
        CREATE INDEX IF NOT EXISTS idx_mv_years ON mv_pn_srch(beg_yr, end_yr);
        CREATE INDEX IF NOT EXISTS idx_mv_datasrc ON mv_pn_srch(data_src);
        CREATE INDEX IF NOT EXISTS idx_mv_parent ON mv_pn_srch(parent_sys_id);
        CREATE INDEX IF NOT EXISTS idx_mainxx_sysid ON main_xx(sys_id);
        CREATE INDEX IF NOT EXISTS idx_gisxx_sysid ON gis_xx(sys_id);
        CREATE INDEX IF NOT EXISTS idx_wkt_pn ON wkt_definition(placename_id);
        CREATE INDEX IF NOT EXISTS idx_adminseat_pn ON admin_seat(placename_id);
    """
    conn.executescript(indexes)


def create_views(conn):
    print("Creating views...")
    conn.executescript("""
        DROP VIEW IF EXISTS v_placename;
        CREATE VIEW v_placename AS
        SELECT
            p.id,
            p.sys_id,
            p.beg_yr,
            p.end_yr,
            p.obj_type,
            CAST(p.x_coord AS REAL) AS longitude,
            CAST(p.y_coord AS REAL) AS latitude,
            p.xy_type,
            p.geo_src,
            p.lev_rank,
            ds.name AS data_source,
            ds.org AS data_source_org,
            ft.name_vn AS feature_type_native,
            ft.name_tr AS feature_type_transcribed,
            ft.name_en AS feature_type_english,
            ft.adl_class,
            ft.period AS feature_period
        FROM placename p
        LEFT JOIN data_src ds ON p.data_src = ds.id
        LEFT JOIN ftype ft ON p.ftype_id = ft.id;

        DROP VIEW IF EXISTS v_placename_names;
        CREATE VIEW v_placename_names AS
        SELECT
            p.id AS placename_id,
            p.sys_id,
            s.written_form,
            s.exonym_lang,
            s.default_per_type,
            sc.name AS script_name,
            sc.lang,
            tr.name AS transcription_system
        FROM placename p
        JOIN spelling s ON s.placename_id = p.id
        LEFT JOIN script sc ON s.script_id = sc.id
        LEFT JOIN trsys tr ON s.trsys_id = tr.id;

        DROP VIEW IF EXISTS v_placename_parents;
        CREATE VIEW v_placename_parents AS
        SELECT
            po.child_id,
            child.sys_id AS child_sys_id,
            po.parent_id,
            parent.sys_id AS parent_sys_id,
            po.begin_year,
            po.end_year
        FROM part_of po
        JOIN placename child ON po.child_id = child.id
        JOIN placename parent ON po.parent_id = parent.id;

        DROP VIEW IF EXISTS v_present_location;
        CREATE VIEW v_present_location AS
        SELECT
            p.sys_id,
            pl.type,
            pl.country_code,
            pl.text_value,
            pl.source
        FROM present_loc pl
        JOIN placename p ON pl.placename_id = p.id;

        DROP VIEW IF EXISTS v_search;
        CREATE VIEW v_search AS
        SELECT
            m.sys_id,
            m.name,
            m.transcription,
            m.beg_yr,
            m.end_yr,
            m.obj_type,
            m.x_coord AS longitude,
            m.y_coord AS latitude,
            m.ftype_vn AS feature_type_native,
            m.ftype_tr AS feature_type_transcribed,
            m.parent_sys_id,
            m.parent_vn AS parent_name_native,
            m.parent_tr AS parent_name_transcribed,
            ds.name AS data_source
        FROM mv_pn_srch m
        LEFT JOIN data_src ds ON m.data_src = ds.id;

        -- Comprehensive search: placename + default spelling + feature type
        DROP VIEW IF EXISTS v_full;
        CREATE VIEW v_full AS
        SELECT
            p.id,
            p.sys_id,
            p.beg_yr,
            p.end_yr,
            p.obj_type,
            CAST(p.x_coord AS REAL) AS longitude,
            CAST(p.y_coord AS REAL) AS latitude,
            ds.name AS data_source,
            ft.name_vn AS ftype_native,
            ft.name_tr AS ftype_transcribed,
            ft.name_en AS ftype_english,
            sn.full_text AS note,
            pl.text_value AS present_location
        FROM placename p
        LEFT JOIN data_src ds ON p.data_src = ds.id
        LEFT JOIN ftype ft ON p.ftype_id = ft.id
        LEFT JOIN snote sn ON p.snote_id = sn.id
        LEFT JOIN present_loc pl ON pl.placename_id = p.id AND pl.type = 'location';
    """)


def create_fts(conn):
    print("Creating full-text search indexes...")
    conn.executescript("""
        DROP TABLE IF EXISTS search_fts;
        CREATE VIRTUAL TABLE search_fts USING fts5(
            sys_id UNINDEXED,
            name,
            transcription,
            ftype_vn,
            ftype_tr,
            parent_vn,
            parent_tr,
            data_src UNINDEXED,
            beg_yr UNINDEXED,
            end_yr UNINDEXED
        );
        INSERT INTO search_fts
        SELECT sys_id, name, transcription, ftype_vn, ftype_tr,
               parent_vn, parent_tr, data_src, beg_yr, end_yr
        FROM mv_pn_srch;

        DROP TABLE IF EXISTS spelling_fts;
        CREATE VIRTUAL TABLE spelling_fts USING fts5(
            placename_id UNINDEXED,
            written_form
        );
        INSERT INTO spelling_fts
        SELECT placename_id, written_form FROM spelling;

        DROP TABLE IF EXISTS notes_fts;
        CREATE VIRTUAL TABLE notes_fts USING fts5(
            id UNINDEXED,
            topic,
            full_text
        );
        INSERT INTO notes_fts
        SELECT id, topic, full_text FROM snote WHERE full_text IS NOT NULL;
    """)


def print_stats(conn):
    print(f"\n{'='*60}")
    print("DATABASE STATISTICS")
    print(f"{'='*60}")

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%' "
        "ORDER BY name"
    ).fetchall()

    for (table,) in tables:
        try:
            count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            if count > 0:
                print(f"  {table}: {count:,}")
        except:
            pass

    pn = conn.execute("SELECT COUNT(*) FROM placename").fetchone()[0]
    sp = conn.execute("SELECT COUNT(*) FROM spelling").fetchone()[0]
    mv = conn.execute("SELECT COUNT(*) FROM mv_pn_srch").fetchone()[0]

    yr = conn.execute(
        "SELECT MIN(beg_yr), MAX(end_yr) FROM placename WHERE beg_yr IS NOT NULL"
    ).fetchone()

    sources = conn.execute(
        "SELECT ds.name, COUNT(*) FROM placename p "
        "JOIN data_src ds ON p.data_src = ds.id "
        "GROUP BY ds.name ORDER BY COUNT(*) DESC"
    ).fetchall()

    ftypes = conn.execute(
        "SELECT COALESCE(ft.name_en, ft.name_tr), COUNT(*) "
        "FROM placename p JOIN ftype ft ON p.ftype_id = ft.id "
        "GROUP BY ft.id ORDER BY COUNT(*) DESC LIMIT 15"
    ).fetchall()

    print(f"\nKey counts:")
    print(f"  Placenames: {pn:,}")
    print(f"  Spellings: {sp:,}")
    print(f"  Search records: {mv:,}")
    if yr[0]:
        print(f"  Year range: {yr[0]} to {yr[1]}")

    print(f"\nData sources:")
    for src, cnt in sources:
        print(f"  {src}: {cnt:,}")

    print(f"\nTop feature types:")
    for ft, cnt in ftypes:
        print(f"  {ft}: {cnt:,}")


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    dump_path = sys.argv[2] if len(sys.argv) > 2 else MYSQL_DUMP

    print(f"Converting MySQL dump to SQLite...")
    print(f"  Source: {dump_path}")
    print(f"  Target: {db_path}\n")

    start = time.time()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache

    print("Creating schema...")
    conn.executescript(SCHEMA)

    print("Importing data...")
    table_rows = process_inserts(conn, dump_path)

    print(f"\nImported in {time.time()-start:.1f}s:")
    for table, count in sorted(table_rows.items(), key=lambda x: -x[1]):
        if count > 0:
            print(f"  {table}: {count:,}")

    create_indexes(conn)
    create_views(conn)
    create_fts(conn)
    print_stats(conn)

    # Reset pragmas for normal use
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.close()

    import os
    size_mb = os.path.getsize(db_path) / (1024 * 1024)
    print(f"\nDatabase saved to: {db_path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
