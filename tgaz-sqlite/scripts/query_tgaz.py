#!/usr/bin/env python3
"""
Query the local TGAZ SQLite database.

Usage:
  python query_tgaz.py "北京"                              # Search by name
  python query_tgaz.py "Chang'an" --year -200              # Name + year filter
  python query_tgaz.py --fts "Beijing county"              # Full-text search
  python query_tgaz.py --bbox 108,34,110,35                # Bounding box
  python query_tgaz.py --feature-type xian --year 1820     # Feature type + year
  python query_tgaz.py --parent hvd_9659                   # Children of a jurisdiction
  python query_tgaz.py --spellings hvd_70626               # All spellings for a place
  python query_tgaz.py --history hvd_70626                 # Full history of a place
  python query_tgaz.py --stats                             # Database statistics
  python query_tgaz.py --sql "SELECT ..."                  # Raw SQL
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

# tgaz.db is 228 MB and is not stored in the repo. Keep one copy in the shared
# cache below; everything else finds it from there. See SKILL.md for how to
# download it.
CACHE_DB = Path.home() / ".local" / "share" / "sino-authorities" / "tgaz.db"

DOWNLOAD_HINT = f"""Download it once (requires git-lfs):

  mkdir -p {CACHE_DB.parent}
  git lfs install
  git clone https://github.com/kltng/tgaz-sqlite.git /tmp/tgaz-sqlite
  mv /tmp/tgaz-sqlite/tgaz.db {CACHE_DB}
  rm -rf /tmp/tgaz-sqlite"""


def db_candidates():
    """Places to look for tgaz.db, in order of preference."""
    paths = []
    env = os.environ.get("TGAZ_DB")
    if env:
        paths.append(Path(env).expanduser())
    paths.append(Path.cwd() / "tgaz.db")
    paths.append(Path(__file__).resolve().parent / "tgaz.db")
    paths.append(CACHE_DB)
    return paths


def resolve_db(explicit=None):
    """Return the first tgaz.db that exists, or exit with instructions."""
    if explicit:
        path = Path(explicit).expanduser()
        if not path.exists():
            sys.exit(f"Error: no database at {path}")
        return path

    seen = []
    for path in db_candidates():
        if path.exists():
            return path
        if path not in seen:
            seen.append(path)

    looked = "\n".join(f"  {p}" for p in seen)
    sys.exit(f"Error: tgaz.db not found. Looked in:\n{looked}\n\n{DOWNLOAD_HINT}")


LFS_POINTER_PREFIX = b"version https://git-lfs"
SQLITE_HEADER = b"SQLite format 3\x00"


def check_db_file(db_path):
    """Exit with a clear message when the file is not a SQLite database.

    A clone made without git-lfs leaves a small text "pointer" file in place
    of the 228 MB database. SQLite would only say "file is not a database".
    """
    try:
        with open(db_path, "rb") as f:
            head = f.read(64)
    except OSError as e:
        sys.exit(f"Error: cannot read {db_path}: {e}")
    if head.startswith(LFS_POINTER_PREFIX):
        sys.exit(
            f"Error: {db_path} is a Git LFS pointer file, not the database.\n"
            "The real file was not downloaded (git-lfs was missing, or the LFS\n"
            "quota was used up). Install git-lfs and run `git lfs pull` in that\n"
            f"clone, or download it again.\n\n{DOWNLOAD_HINT}"
        )
    if not head.startswith(SQLITE_HEADER):
        sys.exit(f"Error: {db_path} is not a SQLite database.\n\n{DOWNLOAD_HINT}")


def get_conn(db_path):
    check_db_file(db_path)
    # as_uri() percent-encodes '?', '#' and '%' so odd paths still open read-only.
    conn = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _fts_phrase(query):
    """Quote each word so FTS5 treats punctuation (' - " :) as plain text."""
    return " ".join('"' + w.replace('"', '""') + '"' for w in query.split())


def _like_escape(text):
    """Escape LIKE wildcards so '%' and '_' in user input match literally."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# English words people use that are not an exact ftype.name_en.
FEATURE_TYPE_ALIASES = {"kingdom": "country", "state": "country"}


def english_feature_terms(conn, word):
    """Map an English feature type ("county") to TGAZ terms (xian, gun, uezd).

    Matches ftype.name_en exactly, so "county" does not also pull in
    "autonomous county boundary". Returns [] when the word is not English.
    """
    word = word.strip().strip('"').lower()
    word = FEATURE_TYPE_ALIASES.get(word, word)
    rows = conn.execute(
        "SELECT DISTINCT name_tr FROM ftype WHERE name_en = ? COLLATE NOCASE AND name_tr <> ''",
        (word,),
    ).fetchall()
    return [r["name_tr"] for r in rows]


def _feature_type_filter(conn, feature_type, prefix=""):
    """SQL clause and params for --feature-type.

    English types match their TGAZ terms exactly; anything else (xian, 县)
    keeps the substring match. `prefix` is a table alias such as "m.".
    """
    terms = english_feature_terms(conn, feature_type)
    if terms:
        marks = ", ".join("?" * len(terms))
        return f" AND LOWER({prefix}ftype_tr) IN ({marks})", [t.lower() for t in terms]
    ft = _like_escape(feature_type)
    return (f" AND ({prefix}ftype_tr LIKE ? ESCAPE '\\' OR {prefix}ftype_vn LIKE ? ESCAPE '\\')",
            [f"%{ft}%", f"%{ft}%"])


def bad_coords_sql(prefix=""):
    """SQL test for coordinates that cannot be right.

    About 6,000 POLYGON rows (many with hvd_90xxx ids) repeat a place that
    also has a POINT row, but their longitude is 0 (a few have 1-5). About
    120 other rows are 0,0. On a map these land near Africa. No real TGAZ
    place is within 10 degrees of longitude 0.
    """
    return (f"(ABS(CAST({prefix}x_coord AS REAL)) < 10"
            f" OR CAST({prefix}y_coord AS REAL) = 0)")


def _year_filter(year, prefix=""):
    if year is None:
        return "", []
    return f" AND {prefix}beg_yr <= ? AND {prefix}end_yr >= ?", [year, year]


def _coords_filter(good_coords, prefix=""):
    return f" AND NOT {bad_coords_sql(prefix)}" if good_coords else ""


def _expand_feature_words(conn, query):
    """Rewrite English feature words in an FTS query as TGAZ terms.

    "county Beijing" -> '("xian" OR "gun" OR "uezd") AND Beijing'. Returns
    None when no word is an English feature type.
    """
    operators = {"AND", "OR", "NOT"}
    words, changed = [], False
    for word in query.split():
        terms = english_feature_terms(conn, word)
        if terms:
            # A quoted multi-word term ("di qu") is an FTS5 phrase.
            token = "(" + " OR ".join('"' + t.replace('"', '""') + '"' for t in terms) + ")"
            changed = True
        else:
            token = word
        # FTS5 has no implicit AND next to a (group), so write it out.
        if words and words[-1] not in operators and token not in operators:
            words.append("AND")
        words.append(token)
    return " ".join(words) if changed else None


def search_fts(conn, query, limit=50, year=None, feature_type=None, good_coords=False):
    """Full-text search across names, transcriptions, feature types.

    The query is tried as FTS5 syntax first (so AND/OR/NEAR/prefix* work).
    If that is a syntax error, it is retried as plain quoted words. If it
    finds nothing, English feature words ("county") are retried as TGAZ
    terms ("xian"), since only the TGAZ terms are indexed. The year,
    feature-type and coordinate filters apply to every try.
    """
    filters = (year, feature_type, good_coords)
    try:
        rows = _search_fts(conn, query, limit, *filters)
    except sqlite3.OperationalError:
        query = _fts_phrase(query)
        if not query:
            return []
        rows = _search_fts(conn, query, limit, *filters)
    if rows:
        return rows
    expanded = _expand_feature_words(conn, query)
    return _search_fts(conn, expanded, limit, *filters) if expanded else rows


def _search_fts(conn, query, limit, year=None, feature_type=None, good_coords=False):
    sql = f"""
        SELECT f.sys_id, m.name, m.ftype_vn, m.ftype_tr,
               m.parent_sys_id, m.parent_vn, m.parent_tr, m.data_src, m.beg_yr, m.end_yr,
               m.x_coord AS longitude, m.y_coord AS latitude, m.transcription,
               m.obj_type, {bad_coords_sql("m.")} AS bad_coords
        FROM search_fts f
        JOIN mv_pn_srch m ON m.sys_id = f.sys_id
        WHERE search_fts MATCH ?
    """
    params = [query]
    clause, more = _year_filter(year, "m.")
    sql += clause
    params.extend(more)
    if feature_type:
        clause, more = _feature_type_filter(conn, feature_type, "m.")
        sql += clause
        params.extend(more)
    sql += _coords_filter(good_coords, "m.")
    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)
    return with_parent_at_year(conn, conn.execute(sql, params).fetchall(), year)


def parents_at_year(conn, sys_ids, year):
    """Map child sys_id -> its parent in `year`, from the part_of table.

    mv_pn_srch.parent_* holds only the earliest parent (杭州府 -> 江南行省,
    from 1366). part_of has every parent with its years.
    """
    found = {}
    ids = list(dict.fromkeys(sys_ids))
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        marks = ", ".join("?" * len(chunk))
        for r in conn.execute(f"""
            SELECT c.sys_id AS child, p.sys_id AS parent_sys_id,
                   m.name AS parent_vn, m.transcription AS parent_tr
            FROM part_of po
            JOIN placename c ON po.child_id = c.id
            JOIN placename p ON po.parent_id = p.id
            LEFT JOIN mv_pn_srch m ON m.sys_id = p.sys_id
            WHERE c.sys_id IN ({marks})
              AND po.begin_year <= ? AND po.end_year >= ?
            ORDER BY po.begin_year
        """, (*chunk, year, year)):
            found.setdefault(r["child"], dict(r))
    return found


def with_parent_at_year(conn, rows, year):
    """Replace the earliest parent with the parent in `year`, when known."""
    if year is None or not rows or "parent_sys_id" not in rows[0].keys():
        return rows
    parents = parents_at_year(conn, [r["sys_id"] for r in rows], year)
    out = []
    for r in rows:
        d = dict(r)
        p = parents.get(d["sys_id"])
        if p:
            d["parent_sys_id"] = p["parent_sys_id"]
            d["parent_vn"] = p["parent_vn"]
            d["parent_tr"] = p["parent_tr"]
        out.append(d)
    return out


def _squash(text):
    """Lower-case and drop spaces and apostrophes: "Chang'an" -> "changan".

    TGAZ writes one name as "Su Zhou" and "Suzhou Fu", or as "Changan Xian"
    and "Chang'an Xian", so name search also compares the squashed forms.
    """
    for ch in (" ", "'", "’"):
        text = text.replace(ch, "")
    return text.lower()


SQUASHED_TRANSCRIPTION = (
    "LOWER(REPLACE(REPLACE(REPLACE(transcription, ' ', ''), char(39), ''), char(8217), ''))"
)


def search_name(conn, name, year=None, feature_type=None, limit=50, good_coords=False):
    """Search by name (Chinese or romanized) with optional filters.

    Matches the start of the simplified name, of the romanized name (also
    with spaces and apostrophes ignored), and of every form in the spelling
    table, so traditional characters (蘇州) find the place too.
    """
    prefix = _like_escape(name)
    squashed = _like_escape(_squash(name))
    sql = f"""
        SELECT sys_id, name, transcription, beg_yr, end_yr, obj_type,
               x_coord AS longitude, y_coord AS latitude,
               ftype_vn, ftype_tr, parent_sys_id, parent_vn, parent_tr, data_src,
               {bad_coords_sql()} AS bad_coords
        FROM mv_pn_srch
        WHERE (name LIKE ? ESCAPE '\\' OR transcription LIKE ? ESCAPE '\\'
               OR (? <> '' AND {SQUASHED_TRANSCRIPTION} LIKE ? ESCAPE '\\')
               OR sys_id IN (
                   SELECT p.sys_id FROM spelling s
                   JOIN placename p ON p.id = s.placename_id
                   WHERE s.written_form >= ? AND s.written_form < ?))
    """
    # A range on written_form can use its index. The upper bound is the
    # prefix followed by the highest code point.
    params = [f"{prefix}%", f"{prefix}%", squashed, f"{squashed}%",
              name, name + "\U0010ffff"]
    clause, more = _year_filter(year)
    sql += clause
    params.extend(more)
    if feature_type:
        clause, more = _feature_type_filter(conn, feature_type)
        sql += clause
        params.extend(more)
    sql += _coords_filter(good_coords)
    sql += " ORDER BY beg_yr LIMIT ?"
    params.append(limit)
    return with_parent_at_year(conn, conn.execute(sql, params).fetchall(), year)


def search_by_year(conn, year, feature_type=None, limit=50, good_coords=False):
    """Find all places existing in a given year."""
    sql = (f"SELECT *, {bad_coords_sql()} AS bad_coords FROM mv_pn_srch"
           " WHERE beg_yr <= ? AND end_yr >= ?")
    params = [year, year]
    if feature_type:
        clause, more = _feature_type_filter(conn, feature_type)
        sql += clause
        params.extend(more)
    sql += _coords_filter(good_coords)
    sql += " ORDER BY name LIMIT ?"
    params.append(limit)
    return with_parent_at_year(conn, conn.execute(sql, params).fetchall(), year)


def search_bbox(conn, lon_min, lat_min, lon_max, lat_max, year=None, limit=100):
    """Search within a geographic bounding box."""
    sql = f"""
        SELECT *, {bad_coords_sql()} AS bad_coords FROM mv_pn_srch
        WHERE CAST(x_coord AS REAL) BETWEEN ? AND ?
        AND CAST(y_coord AS REAL) BETWEEN ? AND ?
    """
    params = [lon_min, lon_max, lat_min, lat_max]
    clause, more = _year_filter(year)
    sql += clause
    params.extend(more)
    sql += " ORDER BY name LIMIT ?"
    params.append(limit)
    return with_parent_at_year(conn, conn.execute(sql, params).fetchall(), year)


def search_parent(conn, parent_sys_id, year=None, limit=100, good_coords=False):
    """Find children of a parent jurisdiction.

    Uses the part_of table, which has every parent a place had and when.
    mv_pn_srch.parent_sys_id has only the earliest parent, so it misses
    most children (浙江布政使司 in 1600: 11 prefectures in part_of, 1 there).
    """
    sql = f"""
        SELECT DISTINCT m.*, {bad_coords_sql("m.")} AS bad_coords
        FROM part_of po
        JOIN placename c ON po.child_id = c.id
        JOIN placename p ON po.parent_id = p.id
        JOIN mv_pn_srch m ON m.sys_id = c.sys_id
        WHERE p.sys_id = ?
    """
    params = [parent_sys_id]
    if year is not None:
        sql += " AND po.begin_year <= ? AND po.end_year >= ?"
        params.extend([year, year])
        clause, more = _year_filter(year, "m.")
        sql += clause
        params.extend(more)
    sql += _coords_filter(good_coords, "m.")
    sql += " ORDER BY m.name LIMIT ?"
    params.append(limit)
    return with_parent_at_year(conn, conn.execute(sql, params).fetchall(), year)


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
    parser.add_argument("--db", help="Path to tgaz.db (default: auto-detect)")
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
    parser.add_argument("--good-coords", action="store_true",
                        help="Drop rows with broken coordinates (longitude 0, mostly POLYGON "
                             "duplicates). Results also have a bad_coords column (1 = broken).")

    args = parser.parse_args()
    conn = get_conn(resolve_db(args.db))

    if args.stats:
        print(json.dumps(get_stats(conn), ensure_ascii=False, indent=2))
        return

    if args.sql:
        # The connection is read-only; this check also blocks ATTACH/PRAGMA.
        if not args.sql.strip().upper().startswith(("SELECT", "WITH")):
            sys.exit("Error: only SELECT (or WITH ... SELECT) allowed")
        try:
            rows = conn.execute(args.sql).fetchall()
        except sqlite3.Error as e:
            sys.exit(f"SQL error: {e}")
        format_rows(rows, args.format)
        return

    if args.history:
        print(json.dumps(get_history(conn, args.history), ensure_ascii=False, indent=2))
        return

    if args.spellings:
        format_rows(get_spellings(conn, args.spellings), args.format)
        return

    if args.fts:
        format_rows(search_fts(conn, args.fts, args.limit, args.year, args.feature_type,
                               args.good_coords), args.format)
        return

    if args.parent:
        format_rows(search_parent(conn, args.parent, args.year, args.limit, args.good_coords),
                    args.format)
        return

    if args.bbox:
        try:
            parts = [float(x) for x in args.bbox.split(",")]
        except ValueError:
            parts = []
        if len(parts) != 4:
            sys.exit("Error: --bbox needs 4 numbers: lon_min,lat_min,lon_max,lat_max")
        rows = search_bbox(conn, *parts, args.year, args.limit)
        format_rows(rows, args.format)
        return

    if args.year is not None and not args.search and not args.name:
        format_rows(search_by_year(conn, args.year, args.feature_type, args.limit,
                                   args.good_coords), args.format)
        return

    query = args.search or args.name
    if not query:
        parser.print_help()
        return

    rows = search_name(conn, query, args.year, args.feature_type, args.limit, args.good_coords)
    if not rows:
        # The fallback keeps --year and --feature-type, and says it ran.
        print("No name match; trying full-text search with the same filters.", file=sys.stderr)
        rows = search_fts(conn, query, args.limit, args.year, args.feature_type, args.good_coords)
    format_rows(rows, args.format)


if __name__ == "__main__":
    main()
