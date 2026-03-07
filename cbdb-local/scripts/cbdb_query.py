#!/usr/bin/env python3
"""
CBDB Local Query Tool — query the China Biographical Database locally via SQLite.

Requires: Python 3.9+, CBDB SQLite database (latest.db).
Zero external dependencies — stdlib only (except 7z for initial setup).

Usage:
    python3 cbdb_query.py setup                        # Download & extract database
    python3 cbdb_query.py person "蘇軾"                # Search by Chinese name
    python3 cbdb_query.py person "Su Shi"              # Search by pinyin name
    python3 cbdb_query.py person --id 3767             # Look up by person ID
    python3 cbdb_query.py kinship 3767                 # Family/kinship network
    python3 cbdb_query.py offices 3767                 # Official postings
    python3 cbdb_query.py associations 3767            # Social associations
    python3 cbdb_query.py addresses 3767               # Addresses/places
    python3 cbdb_query.py entries 3767                 # Entry/exam data
    python3 cbdb_query.py status 3767                  # Social status
    python3 cbdb_query.py altnames 3767                # Alternative names
    python3 cbdb_query.py sql "SELECT ..."             # Run raw SQL
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Database location & download
# ---------------------------------------------------------------------------

DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "cbdb.db"

DB_DOWNLOAD_URL = (
    "https://media.githubusercontent.com/media/cbdb-project/cbdb_sqlite/master/latest.7z"
)


def _find_7z() -> Optional[str]:
    """Find 7z executable on macOS, Windows, or Linux."""
    candidates = ["7z", "7zz"]

    # Windows common install paths
    if platform.system() == "Windows":
        candidates.extend([
            r"C:\Program Files\7-Zip\7z.exe",
            r"C:\Program Files (x86)\7-Zip\7z.exe",
        ])

    for cmd in candidates:
        if shutil.which(cmd):
            return cmd
        # Check full path directly (Windows)
        if os.path.isfile(cmd):
            return cmd

    return None


def download_db(dest: Optional[Path] = None) -> Path:
    """Download and extract CBDB SQLite database."""
    dest = dest or DB_PATH
    if dest.exists():
        print(f"Database already exists: {dest}")
        return dest

    # Check for 7z
    sevenz = _find_7z()
    if not sevenz:
        print("ERROR: 7z/7zz not found.", file=sys.stderr)
        print("", file=sys.stderr)
        if platform.system() == "Darwin":
            print("  macOS:   brew install 7zip", file=sys.stderr)
        elif platform.system() == "Windows":
            print("  Windows: winget install 7zip.7zip", file=sys.stderr)
            print("       or: choco install 7zip", file=sys.stderr)
            print("       or: download from https://www.7-zip.org/", file=sys.stderr)
        else:
            print("  Linux:   sudo apt install p7zip-full  (Debian/Ubuntu)", file=sys.stderr)
            print("       or: sudo dnf install p7zip-plugins  (Fedora)", file=sys.stderr)
        sys.exit(1)

    archive_path = dest.parent / "latest.7z"

    # Download
    print(f"Downloading CBDB database (~69 MB compressed) ...")
    req = urllib.request.Request(
        DB_DOWNLOAD_URL,
        headers={"User-Agent": "cbdb-local-skill/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            dest.parent.mkdir(parents=True, exist_ok=True)
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(archive_path, "wb") as f:
                while True:
                    chunk = resp.read(131072)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded * 100 // total
                        print(f"\r  {downloaded // 1048576} / {total // 1048576} MB ({pct}%)", end="", flush=True)
            print()
    except urllib.error.URLError as e:
        print(f"\nDownload failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Extract
    print(f"Extracting (expands to ~556 MB) ...")
    try:
        subprocess.run(
            [sevenz, "x", str(archive_path), f"-o{dest.parent}", "-y"],
            check=True, capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Extraction failed: {e.stderr.decode()}", file=sys.stderr)
        sys.exit(1)

    # Rename extracted file
    extracted = dest.parent / "latest.db"
    if extracted.exists():
        extracted.rename(dest)

    # Clean up archive
    archive_path.unlink(missing_ok=True)

    # Create indexes for fast name lookups
    print("Creating indexes for fast queries ...")
    conn = sqlite3.connect(str(dest))
    conn.execute("CREATE INDEX IF NOT EXISTS idx_biog_name_chn ON BIOG_MAIN(c_name_chn)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_biog_name ON BIOG_MAIN(c_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_biog_dy ON BIOG_MAIN(c_dy)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_altname_personid ON ALTNAME_DATA(c_personid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_altname_chn ON ALTNAME_DATA(c_alt_name_chn)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_kin_personid ON KIN_DATA(c_personid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_kin_id ON KIN_DATA(c_kin_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_posting_personid ON POSTING_DATA(c_personid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_posted_office_personid ON POSTED_TO_OFFICE_DATA(c_personid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assoc_personid ON ASSOC_DATA(c_personid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assoc_id ON ASSOC_DATA(c_assoc_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_entry_personid ON ENTRY_DATA(c_personid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_biog_addr_personid ON BIOG_ADDR_DATA(c_personid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_status_personid ON STATUS_DATA(c_personid)")
    conn.commit()
    conn.close()

    print(f"Ready: {dest}")
    return dest


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Get a SQLite connection with row factory."""
    path = db_path or DB_PATH
    if not path.exists():
        print(f"Database not found: {path}", file=sys.stderr)
        print("Run: python3 cbdb_query.py setup", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

def search_person(conn: sqlite3.Connection, query: str) -> list[dict]:
    """Search for a person by Chinese name, pinyin, or partial match."""
    results = []

    # Exact match on Chinese name
    rows = conn.execute("""
        SELECT b.c_personid, b.c_name_chn, b.c_name, d.c_dynasty_chn, d.c_dynasty,
               b.c_birthyear, b.c_deathyear, b.c_surname_chn, b.c_mingzi_chn,
               b.c_female, b.c_index_year, b.c_notes
        FROM BIOG_MAIN b
        LEFT JOIN DYNASTIES d ON d.c_dy = b.c_dy
        WHERE b.c_name_chn = ?
        ORDER BY b.c_index_year
    """, (query,)).fetchall()

    if not rows:
        # Try pinyin (case-insensitive)
        rows = conn.execute("""
            SELECT b.c_personid, b.c_name_chn, b.c_name, d.c_dynasty_chn, d.c_dynasty,
                   b.c_birthyear, b.c_deathyear, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_female, b.c_index_year, b.c_notes
            FROM BIOG_MAIN b
            LEFT JOIN DYNASTIES d ON d.c_dy = b.c_dy
            WHERE b.c_name = ? COLLATE NOCASE
            ORDER BY b.c_index_year
        """, (query,)).fetchall()

    if not rows:
        # Try alt names (Chinese)
        rows = conn.execute("""
            SELECT DISTINCT b.c_personid, b.c_name_chn, b.c_name, d.c_dynasty_chn, d.c_dynasty,
                   b.c_birthyear, b.c_deathyear, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_female, b.c_index_year, b.c_notes
            FROM ALTNAME_DATA a
            JOIN BIOG_MAIN b ON b.c_personid = a.c_personid
            LEFT JOIN DYNASTIES d ON d.c_dy = b.c_dy
            WHERE a.c_alt_name_chn = ?
            ORDER BY b.c_index_year
        """, (query,)).fetchall()

    if not rows:
        # Try alt names (fuzzy)
        rows = conn.execute("""
            SELECT DISTINCT b.c_personid, b.c_name_chn, b.c_name, d.c_dynasty_chn, d.c_dynasty,
                   b.c_birthyear, b.c_deathyear, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_female, b.c_index_year, b.c_notes
            FROM ALTNAME_DATA a
            JOIN BIOG_MAIN b ON b.c_personid = a.c_personid
            LEFT JOIN DYNASTIES d ON d.c_dy = b.c_dy
            WHERE a.c_alt_name_chn LIKE ? OR a.c_alt_name LIKE ? COLLATE NOCASE
            ORDER BY b.c_index_year
            LIMIT 50
        """, (f"%{query}%", f"%{query}%")).fetchall()

    if not rows:
        # Fuzzy match (LIKE) on main Chinese name
        rows = conn.execute("""
            SELECT b.c_personid, b.c_name_chn, b.c_name, d.c_dynasty_chn, d.c_dynasty,
                   b.c_birthyear, b.c_deathyear, b.c_surname_chn, b.c_mingzi_chn,
                   b.c_female, b.c_index_year, b.c_notes
            FROM BIOG_MAIN b
            LEFT JOIN DYNASTIES d ON d.c_dy = b.c_dy
            WHERE b.c_name_chn LIKE ? OR b.c_name LIKE ? COLLATE NOCASE
            ORDER BY b.c_index_year
            LIMIT 50
        """, (f"%{query}%", f"%{query}%")).fetchall()

    for row in rows:
        results.append({
            "person_id": row["c_personid"],
            "name_chn": row["c_name_chn"],
            "name_pinyin": row["c_name"],
            "dynasty_chn": row["c_dynasty_chn"],
            "dynasty": row["c_dynasty"],
            "birth_year": row["c_birthyear"],
            "death_year": row["c_deathyear"],
            "surname_chn": row["c_surname_chn"],
            "mingzi_chn": row["c_mingzi_chn"],
            "female": bool(row["c_female"]) if row["c_female"] else None,
            "index_year": row["c_index_year"],
            "notes": row["c_notes"],
        })

    return results


def get_person_by_id(conn: sqlite3.Connection, person_id: int) -> Optional[dict]:
    """Get a person by their CBDB person ID."""
    results = search_person_by_id(conn, person_id)
    return results[0] if results else None


def search_person_by_id(conn: sqlite3.Connection, person_id: int) -> list[dict]:
    """Look up a person by ID."""
    rows = conn.execute("""
        SELECT b.c_personid, b.c_name_chn, b.c_name, d.c_dynasty_chn, d.c_dynasty,
               b.c_birthyear, b.c_deathyear, b.c_surname_chn, b.c_mingzi_chn,
               b.c_female, b.c_index_year, b.c_notes
        FROM BIOG_MAIN b
        LEFT JOIN DYNASTIES d ON d.c_dy = b.c_dy
        WHERE b.c_personid = ?
    """, (person_id,)).fetchall()

    return [{
        "person_id": row["c_personid"],
        "name_chn": row["c_name_chn"],
        "name_pinyin": row["c_name"],
        "dynasty_chn": row["c_dynasty_chn"],
        "dynasty": row["c_dynasty"],
        "birth_year": row["c_birthyear"],
        "death_year": row["c_deathyear"],
        "surname_chn": row["c_surname_chn"],
        "mingzi_chn": row["c_mingzi_chn"],
        "female": bool(row["c_female"]) if row["c_female"] else None,
        "index_year": row["c_index_year"],
        "notes": row["c_notes"],
    } for row in rows]


def get_altnames(conn: sqlite3.Connection, person_id: int) -> list[dict]:
    """Get alternative names for a person."""
    rows = conn.execute("""
        SELECT a.c_alt_name_chn, a.c_alt_name, ac.c_name_type_desc_chn, ac.c_name_type_desc
        FROM ALTNAME_DATA a
        JOIN ALTNAME_CODES ac ON ac.c_name_type_code = a.c_alt_name_type_code
        WHERE a.c_personid = ?
        ORDER BY a.c_alt_name_type_code, a.c_sequence
    """, (person_id,)).fetchall()

    return [{
        "name_chn": row["c_alt_name_chn"],
        "name_pinyin": row["c_alt_name"],
        "type_chn": row["c_name_type_desc_chn"],
        "type": row["c_name_type_desc"],
    } for row in rows]


def get_kinship(conn: sqlite3.Connection, person_id: int) -> list[dict]:
    """Get kinship/family relationships for a person."""
    rows = conn.execute("""
        SELECT k.c_kin_id, b2.c_name_chn, b2.c_name, kc.c_kinrel_chn, kc.c_kinrel,
               d.c_dynasty_chn, b2.c_birthyear, b2.c_deathyear
        FROM KIN_DATA k
        JOIN BIOG_MAIN b2 ON b2.c_personid = k.c_kin_id
        JOIN KINSHIP_CODES kc ON kc.c_kincode = k.c_kin_code
        LEFT JOIN DYNASTIES d ON d.c_dy = b2.c_dy
        WHERE k.c_personid = ?
        ORDER BY kc.c_kincode
    """, (person_id,)).fetchall()

    return [{
        "kin_person_id": row["c_kin_id"],
        "name_chn": row["c_name_chn"],
        "name_pinyin": row["c_name"],
        "relation_chn": row["c_kinrel_chn"],
        "relation": row["c_kinrel"],
        "dynasty_chn": row["c_dynasty_chn"],
        "birth_year": row["c_birthyear"],
        "death_year": row["c_deathyear"],
    } for row in rows]


def get_offices(conn: sqlite3.Connection, person_id: int) -> list[dict]:
    """Get official postings for a person."""
    rows = conn.execute("""
        SELECT po.c_office_id, oc.c_office_chn, oc.c_office_pinyin,
               oc.c_office_trans, po.c_firstyear, po.c_lastyear,
               d.c_dynasty_chn, d.c_dynasty,
               po.c_notes
        FROM POSTED_TO_OFFICE_DATA po
        JOIN OFFICE_CODES oc ON oc.c_office_id = po.c_office_id
        LEFT JOIN DYNASTIES d ON d.c_dy = po.c_dy
        WHERE po.c_personid = ?
        ORDER BY po.c_firstyear, po.c_sequence
    """, (person_id,)).fetchall()

    return [{
        "office_id": row["c_office_id"],
        "office_chn": row["c_office_chn"],
        "office_pinyin": row["c_office_pinyin"],
        "office_translation": row["c_office_trans"],
        "first_year": row["c_firstyear"],
        "last_year": row["c_lastyear"],
        "dynasty_chn": row["c_dynasty_chn"],
        "dynasty": row["c_dynasty"],
        "notes": row["c_notes"],
    } for row in rows]


def get_associations(conn: sqlite3.Connection, person_id: int) -> list[dict]:
    """Get social associations for a person."""
    rows = conn.execute("""
        SELECT a.c_assoc_id, b2.c_name_chn, b2.c_name,
               ac.c_assoc_desc_chn, ac.c_assoc_desc,
               a.c_assoc_first_year, a.c_assoc_last_year,
               d.c_dynasty_chn
        FROM ASSOC_DATA a
        JOIN BIOG_MAIN b2 ON b2.c_personid = a.c_assoc_id
        JOIN ASSOC_CODES ac ON ac.c_assoc_code = a.c_assoc_code
        LEFT JOIN DYNASTIES d ON d.c_dy = b2.c_dy
        WHERE a.c_personid = ?
        ORDER BY a.c_assoc_first_year
        LIMIT 100
    """, (person_id,)).fetchall()

    return [{
        "assoc_person_id": row["c_assoc_id"],
        "name_chn": row["c_name_chn"],
        "name_pinyin": row["c_name"],
        "association_chn": row["c_assoc_desc_chn"],
        "association": row["c_assoc_desc"],
        "first_year": row["c_assoc_first_year"] if row["c_assoc_first_year"] != -9999 else None,
        "last_year": row["c_assoc_last_year"],
        "dynasty_chn": row["c_dynasty_chn"],
    } for row in rows]


def get_addresses(conn: sqlite3.Connection, person_id: int) -> list[dict]:
    """Get addresses/places associated with a person."""
    rows = conn.execute("""
        SELECT ba.c_addr_id, ac.c_name_chn as addr_chn, ac.c_name as addr_pinyin,
               bac.c_addr_desc_chn, bac.c_addr_desc,
               ba.c_firstyear, ba.c_lastyear,
               ac.x_coord, ac.y_coord
        FROM BIOG_ADDR_DATA ba
        JOIN ADDR_CODES ac ON ac.c_addr_id = ba.c_addr_id
        JOIN BIOG_ADDR_CODES bac ON bac.c_addr_type = ba.c_addr_type
        WHERE ba.c_personid = ?
        ORDER BY ba.c_sequence
    """, (person_id,)).fetchall()

    return [{
        "addr_id": row["c_addr_id"],
        "place_chn": row["addr_chn"],
        "place_pinyin": row["addr_pinyin"],
        "addr_type_chn": row["c_addr_desc_chn"],
        "addr_type": row["c_addr_desc"],
        "first_year": row["c_firstyear"],
        "last_year": row["c_lastyear"],
        "longitude": row["x_coord"],
        "latitude": row["y_coord"],
    } for row in rows]


def get_entries(conn: sqlite3.Connection, person_id: int) -> list[dict]:
    """Get entry/examination data for a person."""
    rows = conn.execute("""
        SELECT e.c_entry_code, ec.c_entry_desc_chn, ec.c_entry_desc,
               e.c_year, e.c_age, e.c_exam_rank, e.c_exam_field,
               e.c_notes
        FROM ENTRY_DATA e
        JOIN ENTRY_CODES ec ON ec.c_entry_code = e.c_entry_code
        WHERE e.c_personid = ?
        ORDER BY e.c_year, e.c_sequence
    """, (person_id,)).fetchall()

    return [{
        "entry_code": row["c_entry_code"],
        "entry_type_chn": row["c_entry_desc_chn"],
        "entry_type": row["c_entry_desc"],
        "year": row["c_year"] if row["c_year"] != 0 else None,
        "age": row["c_age"],
        "exam_rank": row["c_exam_rank"],
        "exam_field": row["c_exam_field"],
        "notes": row["c_notes"],
    } for row in rows]


def get_status(conn: sqlite3.Connection, person_id: int) -> list[dict]:
    """Get social status data for a person."""
    rows = conn.execute("""
        SELECT s.c_status_code, sc.c_status_desc_chn, sc.c_status_desc,
               s.c_firstyear, s.c_lastyear, s.c_supplement, s.c_notes
        FROM STATUS_DATA s
        JOIN STATUS_CODES sc ON sc.c_status_code = s.c_status_code
        WHERE s.c_personid = ?
        ORDER BY s.c_firstyear
    """, (person_id,)).fetchall()

    return [{
        "status_code": row["c_status_code"],
        "status_chn": row["c_status_desc_chn"],
        "status": row["c_status_desc"],
        "first_year": row["c_firstyear"],
        "last_year": row["c_lastyear"],
        "supplement": row["c_supplement"],
        "notes": row["c_notes"],
    } for row in rows]


def get_full_profile(conn: sqlite3.Connection, person_id: int) -> Optional[dict]:
    """Get complete profile for a person: bio + all relationships."""
    person = get_person_by_id(conn, person_id)
    if not person:
        return None

    return {
        "basic_info": person,
        "alt_names": get_altnames(conn, person_id),
        "kinship": get_kinship(conn, person_id),
        "offices": get_offices(conn, person_id),
        "associations": get_associations(conn, person_id),
        "addresses": get_addresses(conn, person_id),
        "entries": get_entries(conn, person_id),
        "status": get_status(conn, person_id),
    }


def run_sql(conn: sqlite3.Connection, sql: str) -> list[dict]:
    """Run arbitrary read-only SQL."""
    sql_stripped = sql.strip().rstrip(";")
    # Safety: only allow SELECT
    if not sql_stripped.upper().startswith("SELECT"):
        return [{"error": "Only SELECT queries are allowed"}]
    rows = conn.execute(sql_stripped).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _usage() -> None:
    print(__doc__.strip())
    sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        _usage()

    cmd = sys.argv[1]

    if cmd == "setup":
        download_db()
        return

    conn = get_connection()

    if cmd == "person":
        if len(sys.argv) < 3:
            print("Usage: cbdb_query.py person <name> | cbdb_query.py person --id <ID>", file=sys.stderr)
            sys.exit(1)
        if sys.argv[2] == "--id":
            if len(sys.argv) < 4:
                print("Usage: cbdb_query.py person --id <ID>", file=sys.stderr)
                sys.exit(1)
            pid = int(sys.argv[3])
            profile = get_full_profile(conn, pid)
            if profile:
                _print_json(profile)
            else:
                print(f"No person found with ID: {pid}", file=sys.stderr)
                sys.exit(1)
        else:
            query = sys.argv[2]
            results = search_person(conn, query)
            if not results:
                print(f"No results for: {query}", file=sys.stderr)
                sys.exit(1)
            if len(results) == 1:
                # Single result: show full profile
                profile = get_full_profile(conn, results[0]["person_id"])
                _print_json(profile)
            else:
                # Multiple results: show list
                _print_json(results)

    elif cmd == "kinship":
        pid = int(sys.argv[2])
        _print_json(get_kinship(conn, pid))

    elif cmd == "offices":
        pid = int(sys.argv[2])
        _print_json(get_offices(conn, pid))

    elif cmd == "associations":
        pid = int(sys.argv[2])
        _print_json(get_associations(conn, pid))

    elif cmd == "addresses":
        pid = int(sys.argv[2])
        _print_json(get_addresses(conn, pid))

    elif cmd == "entries":
        pid = int(sys.argv[2])
        _print_json(get_entries(conn, pid))

    elif cmd == "altnames":
        pid = int(sys.argv[2])
        _print_json(get_altnames(conn, pid))

    elif cmd == "status":
        pid = int(sys.argv[2])
        _print_json(get_status(conn, pid))

    elif cmd == "sql":
        if len(sys.argv) < 3:
            print("Usage: cbdb_query.py sql \"SELECT ...\"", file=sys.stderr)
            sys.exit(1)
        _print_json(run_sql(conn, sys.argv[2]))

    else:
        _usage()

    conn.close()


if __name__ == "__main__":
    main()
