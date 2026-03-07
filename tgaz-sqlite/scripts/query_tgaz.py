#!/usr/bin/env python3
"""
Query the local TGAZ SQLite database.

Usage:
  python query_tgaz.py "北京"                              # Search by name
  python query_tgaz.py "Chang'an" --year -200              # Name + year filter
  python query_tgaz.py --fts "Beijing county"              # Full-text search
  python query_tgaz.py --bbox 108,34,110,35                # Bounding box
  python query_tgaz.py --feature-type county --year 1820   # Feature type + year
  python query_tgaz.py --parent hvd_9659                   # Children of a jurisdiction
  python query_tgaz.py --spellings hvd_70626               # All spellings for a place
  python query_tgaz.py --history hvd_70626                 # Full history of a place
  python query_tgaz.py --stats                             # Database statistics
  python query_tgaz.py --sql "SELECT ..."                  # Raw SQL
"""

import argparse
import json
import sqlite3
import sys

DB_PATH = "tgaz.db"


def get_conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def search_fts(conn, query, limit=50):
    """Full-text search across names, transcriptions, feature types."""
    return conn.execute("""
        SELECT f.sys_id, f.name, f.ftype_vn, f.ftype_tr,
               f.parent_vn, f.parent_tr, f.data_src, f.beg_yr, f.end_yr,
               m.x_coord AS longitude, m.y_coord AS latitude, m.transcription
        FROM search_fts f
        JOIN mv_pn_srch m ON m.sys_id = f.sys_id
        WHERE search_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """, (query, limit)).fetchall()


def search_name(conn, name, year=None, feature_type=None, limit=50):
    """Search by name (Chinese or romanized) with optional filters."""
    sql = """
        SELECT sys_id, name, transcription, beg_yr, end_yr, obj_type,
               x_coord AS longitude, y_coord AS latitude,
               ftype_vn, ftype_tr, parent_sys_id, parent_vn, parent_tr, data_src
        FROM mv_pn_srch
        WHERE (name LIKE ? OR transcription LIKE ?)
    """
    params = [f"{name}%", f"{name}%"]
    if year is not None:
        sql += " AND beg_yr <= ? AND end_yr >= ?"
        params.extend([year, year])
    if feature_type:
        sql += " AND (ftype_tr LIKE ? OR ftype_vn LIKE ?)"
        params.extend([f"%{feature_type}%", f"%{feature_type}%"])
    sql += " ORDER BY beg_yr LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def search_by_year(conn, year, feature_type=None, limit=50):
    """Find all places existing in a given year."""
    sql = "SELECT * FROM mv_pn_srch WHERE beg_yr <= ? AND end_yr >= ?"
    params = [year, year]
    if feature_type:
        sql += " AND (ftype_tr LIKE ? OR ftype_vn LIKE ?)"
        params.extend([f"%{feature_type}%", f"%{feature_type}%"])
    sql += " ORDER BY name LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def search_bbox(conn, lon_min, lat_min, lon_max, lat_max, year=None, limit=100):
    """Search within a geographic bounding box."""
    sql = """
        SELECT * FROM mv_pn_srch
        WHERE CAST(x_coord AS REAL) BETWEEN ? AND ?
        AND CAST(y_coord AS REAL) BETWEEN ? AND ?
    """
    params = [lon_min, lon_max, lat_min, lat_max]
    if year is not None:
        sql += " AND beg_yr <= ? AND end_yr >= ?"
        params.extend([year, year])
    sql += " ORDER BY name LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def search_parent(conn, parent_sys_id, year=None, limit=100):
    """Find children of a parent jurisdiction."""
    sql = "SELECT * FROM mv_pn_srch WHERE parent_sys_id = ?"
    params = [parent_sys_id]
    if year is not None:
        sql += " AND beg_yr <= ? AND end_yr >= ?"
        params.extend([year, year])
    sql += " ORDER BY name LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def get_spellings(conn, sys_id):
    """Get all spellings/names for a placename."""
    return conn.execute("""
        SELECT s.written_form, sc.name AS script, sc.lang, tr.name AS trsys,
               s.default_per_type, s.exonym_lang, s.attested_by
        FROM spelling s
        JOIN placename p ON s.placename_id = p.id
        LEFT JOIN script sc ON s.script_id = sc.id
        LEFT JOIN trsys tr ON s.trsys_id = tr.id
        WHERE p.sys_id = ?
        ORDER BY s.default_per_type DESC, sc.lang
    """, (sys_id,)).fetchall()


def get_history(conn, sys_id):
    """Get full history of a place: details, parents, predecessors, present location."""
    result = {}

    # Basic info
    place = conn.execute("""
        SELECT p.*, ds.name AS source_name, ft.name_en AS ftype_en,
               ft.name_vn AS ftype_vn, ft.name_tr AS ftype_tr
        FROM placename p
        LEFT JOIN data_src ds ON p.data_src = ds.id
        LEFT JOIN ftype ft ON p.ftype_id = ft.id
        WHERE p.sys_id = ?
    """, (sys_id,)).fetchone()
    if place:
        result["place"] = dict(place)

    # Spellings
    result["spellings"] = [dict(r) for r in get_spellings(conn, sys_id)]

    # Parent jurisdictions
    result["parents"] = [dict(r) for r in conn.execute("""
        SELECT parent.sys_id AS parent_sys_id, po.begin_year, po.end_year,
               m.name AS parent_name, m.transcription AS parent_transcription
        FROM part_of po
        JOIN placename child ON po.child_id = child.id
        JOIN placename parent ON po.parent_id = parent.id
        LEFT JOIN mv_pn_srch m ON m.sys_id = parent.sys_id
        WHERE child.sys_id = ?
        ORDER BY po.begin_year
    """, (sys_id,)).fetchall()]

    # Predecessors
    result["predecessors"] = [dict(r) for r in conn.execute("""
        SELECT prev.sys_id, m.name, m.transcription, m.beg_yr, m.end_yr
        FROM prec_by pb
        JOIN placename curr ON pb.placename_id = curr.id
        JOIN placename prev ON pb.prec_id = prev.id
        LEFT JOIN mv_pn_srch m ON m.sys_id = prev.sys_id
        WHERE curr.sys_id = ?
    """, (sys_id,)).fetchall()]

    # Present-day location
    result["present_location"] = [dict(r) for r in conn.execute("""
        SELECT pl.type, pl.country_code, pl.text_value, pl.source
        FROM present_loc pl
        JOIN placename p ON pl.placename_id = p.id
        WHERE p.sys_id = ?
    """, (sys_id,)).fetchall()]

    # Note
    note = conn.execute("""
        SELECT sn.full_text, sn.topic, sn.compiler
        FROM snote sn
        JOIN placename p ON p.snote_id = sn.id
        WHERE p.sys_id = ?
    """, (sys_id,)).fetchone()
    if note:
        result["note"] = dict(note)

    return result


def get_stats(conn):
    stats = {}
    stats["total_placenames"] = conn.execute("SELECT COUNT(*) FROM placename").fetchone()[0]
    stats["total_spellings"] = conn.execute("SELECT COUNT(*) FROM spelling").fetchone()[0]
    stats["total_relationships"] = conn.execute("SELECT COUNT(*) FROM part_of").fetchone()[0]

    yr = conn.execute(
        "SELECT MIN(beg_yr), MAX(end_yr) FROM placename WHERE beg_yr IS NOT NULL"
    ).fetchone()
    stats["year_range"] = {"earliest": yr[0], "latest": yr[1]}

    stats["sources"] = [dict(r) for r in conn.execute(
        "SELECT ds.name as source, COUNT(*) as count FROM placename p "
        "JOIN data_src ds ON p.data_src = ds.id GROUP BY ds.name ORDER BY count DESC"
    ).fetchall()]

    stats["feature_types"] = [dict(r) for r in conn.execute(
        "SELECT COALESCE(ft.name_en, ft.name_tr) as type, COUNT(*) as count "
        "FROM placename p JOIN ftype ft ON p.ftype_id = ft.id "
        "GROUP BY ft.id ORDER BY count DESC LIMIT 20"
    ).fetchall()]

    return stats


def format_rows(rows, fmt="table"):
    if not rows:
        print("No results found.")
        return

    if fmt == "json":
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
        return

    if fmt == "jsonl":
        for r in rows:
            print(json.dumps(dict(r), ensure_ascii=False))
        return

    # Table format - select most useful columns
    all_cols = rows[0].keys()
    # Prioritize readable columns
    priority = ["sys_id", "name", "transcription", "written_form", "beg_yr", "end_yr",
                "ftype_vn", "ftype_tr", "ftype_en", "parent_vn", "parent_tr",
                "longitude", "latitude", "x_coord", "y_coord", "data_src",
                "script", "lang", "trsys", "text_value", "source"]
    cols = [c for c in priority if c in all_cols]
    # Add remaining
    cols += [c for c in all_cols if c not in cols]

    widths = {}
    for col in cols:
        vals = [str(r[col]) if r[col] is not None else "" for r in rows]
        widths[col] = min(max(len(col), max((len(v) for v in vals), default=0)), 35)

    header = " | ".join(col.ljust(widths[col])[:widths[col]] for col in cols)
    sep = "-+-".join("-" * widths[col] for col in cols)
    print(header)
    print(sep)
    for r in rows:
        line = " | ".join(
            (str(r[col]) if r[col] is not None else "").ljust(widths[col])[:widths[col]]
            for col in cols
        )
        print(line)
    print(f"\n({len(rows)} results)")


def main():
    parser = argparse.ArgumentParser(description="Query the TGAZ SQLite database")
    parser.add_argument("search", nargs="?", help="Quick search (name or FTS)")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--name", help="Search by name prefix")
    parser.add_argument("--fts", help="Full-text search")
    parser.add_argument("--year", type=int, help="Filter to places existing in this year")
    parser.add_argument("--bbox", help="Bounding box: lon_min,lat_min,lon_max,lat_max")
    parser.add_argument("--feature-type", help="Filter by feature type")
    parser.add_argument("--parent", help="Children of parent sys_id")
    parser.add_argument("--spellings", help="All spellings for sys_id")
    parser.add_argument("--history", help="Full history for sys_id")
    parser.add_argument("--sql", help="Run SELECT query")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--format", choices=["table", "json", "jsonl"], default="table")
    parser.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()
    conn = get_conn(args.db)

    if args.stats:
        print(json.dumps(get_stats(conn), ensure_ascii=False, indent=2))
        return

    if args.sql:
        if not args.sql.strip().upper().startswith("SELECT"):
            print("Error: only SELECT allowed")
            return
        format_rows(conn.execute(args.sql).fetchall(), args.format)
        return

    if args.history:
        print(json.dumps(get_history(conn, args.history), ensure_ascii=False, indent=2))
        return

    if args.spellings:
        format_rows(get_spellings(conn, args.spellings), args.format)
        return

    if args.fts:
        format_rows(search_fts(conn, args.fts, args.limit), args.format)
        return

    if args.parent:
        format_rows(search_parent(conn, args.parent, args.year, args.limit), args.format)
        return

    if args.bbox:
        parts = [float(x) for x in args.bbox.split(",")]
        format_rows(search_bbox(conn, *parts, args.year, args.limit), args.format)
        return

    if args.year and not args.search and not args.name:
        format_rows(search_by_year(conn, args.year, args.feature_type, args.limit), args.format)
        return

    query = args.search or args.name
    if not query:
        parser.print_help()
        return

    rows = search_name(conn, query, args.year, args.feature_type, args.limit)
    if not rows:
        rows = search_fts(conn, query, args.limit)
    format_rows(rows, args.format)


if __name__ == "__main__":
    main()
