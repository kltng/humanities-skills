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
    python3 cbdb_query.py texts 3767                   # Texts/writings
    python3 cbdb_query.py institutions 3767            # Social institutions
    python3 cbdb_query.py postaddr 3767                # Places of service
    python3 cbdb_query.py sql "SELECT ..."             # Run raw SQL

    # Kinship tree visualization:
    python3 cbdb_query.py tree 3767 -d 2 -f dot -o su_shi.dot
    python3 cbdb_query.py tree 3767 -d 2 -f mermaid -o su_shi.md
    python3 cbdb_query.py tree 3767 -d 2 -f svg -o su_shi.svg

    # Network export for Gephi / graph analysis:
    python3 cbdb_query.py export-kinship 3767 -d 2 -o kin.gexf
    python3 cbdb_query.py export-associations 3767 -d 1 -f csv -o assoc.csv
    python3 cbdb_query.py export-network 3767 -d 2 -o combined.gexf
    python3 cbdb_query.py export-office "知州" --dynasty 15 -o co_office.gexf
    python3 cbdb_query.py export-place "眉山" -o place.gexf

    Export options: --format/-f gexf|csv|json  --depth/-d N  --output/-o FILE
                    --dynasty N  --year-from N  --year-to N  --addr-type N
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_biog_text_personid ON BIOG_TEXT_DATA(c_personid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_biog_inst_personid ON BIOG_INST_DATA(c_personid)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_posted_addr_personid ON POSTED_TO_ADDR_DATA(c_personid)")
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


def get_texts(conn: sqlite3.Connection, person_id: int) -> list[dict]:
    """Get texts (writings) associated with a person."""
    rows = conn.execute("""
        SELECT bt.c_textid, tc.c_title_chn, tc.c_title, tc.c_title_alt_chn,
               trc.c_role_desc_chn, trc.c_role_desc,
               bt.c_year, bt.c_notes
        FROM BIOG_TEXT_DATA bt
        JOIN TEXT_CODES tc ON tc.c_textid = bt.c_textid
        LEFT JOIN TEXT_ROLE_CODES trc ON trc.c_role_id = bt.c_role_id
        WHERE bt.c_personid = ?
        ORDER BY bt.c_year
    """, (person_id,)).fetchall()

    return [{
        "text_id": row["c_textid"],
        "title_chn": row["c_title_chn"],
        "title": row["c_title"],
        "title_alt": row["c_title_alt_chn"],
        "role_chn": row["c_role_desc_chn"],
        "role": row["c_role_desc"],
        "year": row["c_year"] if row["c_year"] and row["c_year"] != 0 else None,
        "notes": row["c_notes"],
    } for row in rows]


def get_institutions(conn: sqlite3.Connection, person_id: int) -> list[dict]:
    """Get social institutions (academies, temples, etc.) associated with a person."""
    rows = conn.execute("""
        SELECT bi.c_inst_code, sinc.c_inst_name_hz, sinc.c_inst_name_py,
               bic.c_bi_role_chn, bic.c_bi_role_desc,
               bi.c_bi_begin_year, bi.c_bi_end_year, bi.c_notes
        FROM BIOG_INST_DATA bi
        JOIN SOCIAL_INSTITUTION_CODES sic ON sic.c_inst_code = bi.c_inst_code
        JOIN SOCIAL_INSTITUTION_NAME_CODES sinc ON sinc.c_inst_name_code = sic.c_inst_name_code
        LEFT JOIN BIOG_INST_CODES bic ON bic.c_bi_role_code = bi.c_bi_role_code
        WHERE bi.c_personid = ?
        ORDER BY bi.c_bi_begin_year
    """, (person_id,)).fetchall()

    return [{
        "inst_code": row["c_inst_code"],
        "name_chn": row["c_inst_name_hz"],
        "name": row["c_inst_name_py"],
        "role_chn": row["c_bi_role_chn"],
        "role": row["c_bi_role_desc"],
        "first_year": row["c_bi_begin_year"] if row["c_bi_begin_year"] and row["c_bi_begin_year"] != 0 else None,
        "last_year": row["c_bi_end_year"] if row["c_bi_end_year"] and row["c_bi_end_year"] != 0 else None,
        "notes": row["c_notes"],
    } for row in rows]


def get_posted_addresses(conn: sqlite3.Connection, person_id: int) -> list[dict]:
    """Get places of official service for a person."""
    rows = conn.execute("""
        SELECT pa.c_addr_id, ac.c_name_chn as addr_chn, ac.c_name as addr_pinyin,
               oc.c_office_chn, oc.c_office_pinyin,
               ac.x_coord, ac.y_coord
        FROM POSTED_TO_ADDR_DATA pa
        JOIN ADDR_CODES ac ON ac.c_addr_id = pa.c_addr_id
        LEFT JOIN OFFICE_CODES oc ON oc.c_office_id = pa.c_office_id
        WHERE pa.c_personid = ?
        ORDER BY pa.c_posting_id
    """, (person_id,)).fetchall()

    return [{
        "addr_id": row["c_addr_id"],
        "place_chn": row["addr_chn"],
        "place_pinyin": row["addr_pinyin"],
        "office_chn": row["c_office_chn"],
        "office_pinyin": row["c_office_pinyin"],
        "longitude": row["x_coord"],
        "latitude": row["y_coord"],
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
        "texts": get_texts(conn, person_id),
        "institutions": get_institutions(conn, person_id),
        "posted_addresses": get_posted_addresses(conn, person_id),
    }


# ---------------------------------------------------------------------------
# Network export for Gephi / graph analysis
# ---------------------------------------------------------------------------

def _get_person_node(conn: sqlite3.Connection, person_id: int) -> Optional[dict]:
    """Get node attributes for a person."""
    row = conn.execute("""
        SELECT b.c_personid, b.c_name_chn, b.c_name, b.c_female,
               b.c_birthyear, b.c_deathyear, b.c_index_year,
               d.c_dynasty_chn, d.c_dynasty,
               b.c_index_addr_id
        FROM BIOG_MAIN b
        LEFT JOIN DYNASTIES d ON d.c_dy = b.c_dy
        WHERE b.c_personid = ?
    """, (person_id,)).fetchone()
    if not row:
        return None
    return {
        "id": str(row["c_personid"]),
        "label": row["c_name_chn"] or row["c_name"] or str(row["c_personid"]),
        "name_chn": row["c_name_chn"] or "",
        "name_pinyin": row["c_name"] or "",
        "gender": "F" if row["c_female"] else "M",
        "dynasty_chn": row["c_dynasty_chn"] or "",
        "dynasty": row["c_dynasty"] or "",
        "birth_year": row["c_birthyear"] or 0,
        "death_year": row["c_deathyear"] or 0,
        "index_year": row["c_index_year"] or 0,
    }


def build_kinship_network(
    conn: sqlite3.Connection,
    seed_ids: list[int],
    depth: int = 1,
) -> dict:
    """Build a kinship network starting from seed persons, expanding to given depth.

    Returns {"nodes": [...], "edges": [...]}.
    """
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    edge_set: set[tuple] = set()
    frontier = set(seed_ids)
    visited: set[int] = set()

    for _ in range(depth):
        next_frontier: set[int] = set()
        for pid in frontier:
            if pid in visited:
                continue
            visited.add(pid)

            # Ensure node exists
            if str(pid) not in nodes:
                node = _get_person_node(conn, pid)
                if node:
                    nodes[node["id"]] = node

            rows = conn.execute("""
                SELECT k.c_personid, k.c_kin_id, kc.c_kinrel_chn, kc.c_kinrel
                FROM KIN_DATA k
                JOIN KINSHIP_CODES kc ON kc.c_kincode = k.c_kin_code
                WHERE k.c_personid = ?
            """, (pid,)).fetchall()

            for row in rows:
                kin_id = row["c_kin_id"]
                if str(kin_id) not in nodes:
                    node = _get_person_node(conn, kin_id)
                    if node:
                        nodes[node["id"]] = node

                edge_key = (min(pid, kin_id), max(pid, kin_id), row["c_kinrel"])
                if edge_key not in edge_set:
                    edge_set.add(edge_key)
                    edges.append({
                        "source": str(pid),
                        "target": str(kin_id),
                        "type": "kinship",
                        "relation_chn": row["c_kinrel_chn"],
                        "relation": row["c_kinrel"],
                    })

                next_frontier.add(kin_id)

        frontier = next_frontier - visited

    return {"nodes": list(nodes.values()), "edges": edges}


def build_association_network(
    conn: sqlite3.Connection,
    seed_ids: list[int],
    depth: int = 1,
    assoc_types: Optional[list[int]] = None,
) -> dict:
    """Build a social association network starting from seed persons.

    Args:
        assoc_types: Optional list of ASSOC_TYPES.c_assoc_type_id to filter by
                     (e.g., friendship only, scholarship only).
    Returns {"nodes": [...], "edges": [...]}.
    """
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    edge_set: set[tuple] = set()
    frontier = set(seed_ids)
    visited: set[int] = set()

    type_filter = ""
    type_params: list = []
    if assoc_types:
        placeholders = ",".join("?" * len(assoc_types))
        type_filter = f"""
            AND a.c_assoc_code IN (
                SELECT c_assoc_code FROM ASSOC_CODE_TYPE_REL
                WHERE c_assoc_type_id IN ({placeholders})
            )
        """
        type_params = list(assoc_types)

    for _ in range(depth):
        next_frontier: set[int] = set()
        for pid in frontier:
            if pid in visited:
                continue
            visited.add(pid)

            if str(pid) not in nodes:
                node = _get_person_node(conn, pid)
                if node:
                    nodes[node["id"]] = node

            rows = conn.execute(f"""
                SELECT a.c_personid, a.c_assoc_id,
                       ac.c_assoc_desc_chn, ac.c_assoc_desc
                FROM ASSOC_DATA a
                JOIN ASSOC_CODES ac ON ac.c_assoc_code = a.c_assoc_code
                WHERE a.c_personid = ?
                {type_filter}
            """, [pid] + type_params).fetchall()

            for row in rows:
                assoc_id = row["c_assoc_id"]
                if str(assoc_id) not in nodes:
                    node = _get_person_node(conn, assoc_id)
                    if node:
                        nodes[node["id"]] = node

                edge_key = (pid, assoc_id, row["c_assoc_desc"])
                if edge_key not in edge_set:
                    edge_set.add(edge_key)
                    edges.append({
                        "source": str(pid),
                        "target": str(assoc_id),
                        "type": "association",
                        "relation_chn": row["c_assoc_desc_chn"],
                        "relation": row["c_assoc_desc"],
                    })

                next_frontier.add(assoc_id)

        frontier = next_frontier - visited

    return {"nodes": list(nodes.values()), "edges": edges}


def build_combined_network(
    conn: sqlite3.Connection,
    seed_ids: list[int],
    depth: int = 1,
    include_kin: bool = True,
    include_assoc: bool = True,
) -> dict:
    """Build a combined kinship + association network."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    if include_kin:
        kin = build_kinship_network(conn, seed_ids, depth)
        for n in kin["nodes"]:
            nodes[n["id"]] = n
        edges.extend(kin["edges"])

    if include_assoc:
        assoc = build_association_network(conn, seed_ids, depth)
        for n in assoc["nodes"]:
            nodes[n["id"]] = n
        edges.extend(assoc["edges"])

    return {"nodes": list(nodes.values()), "edges": edges}


def build_office_network(
    conn: sqlite3.Connection,
    office_query: str,
    dynasty: Optional[int] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
) -> dict:
    """Build a co-office network: people who held the same or similar offices.

    Nodes are persons, edges connect people who shared the same office_id.
    """
    dy_filter = "AND oc.c_dy = ?" if dynasty else ""
    year_filter = ""
    params: list = [f"%{office_query}%"]
    if dynasty:
        params.append(dynasty)
    if year_from:
        year_filter += " AND po.c_firstyear >= ?"
        params.append(year_from)
    if year_to:
        year_filter += " AND (po.c_lastyear <= ? OR po.c_lastyear = 0)"
        params.append(year_to)

    # Find all postings matching the office query
    rows = conn.execute(f"""
        SELECT po.c_personid, po.c_office_id,
               oc.c_office_chn, oc.c_office_pinyin,
               po.c_firstyear, po.c_lastyear
        FROM POSTED_TO_OFFICE_DATA po
        JOIN OFFICE_CODES oc ON oc.c_office_id = po.c_office_id
        WHERE oc.c_office_chn LIKE ?
        {dy_filter}
        {year_filter}
        ORDER BY po.c_firstyear
    """, params).fetchall()

    # Group by office_id
    from collections import defaultdict
    office_groups: dict[int, list] = defaultdict(list)
    for row in rows:
        office_groups[row["c_office_id"]].append(row)

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    edge_set: set[tuple] = set()

    for office_id, holders in office_groups.items():
        if len(holders) < 2:
            continue
        office_name = holders[0]["c_office_chn"]

        for h in holders:
            pid = h["c_personid"]
            if str(pid) not in nodes:
                node = _get_person_node(conn, pid)
                if node:
                    nodes[node["id"]] = node

        # Create edges between all co-holders of the same office
        for i in range(len(holders)):
            for j in range(i + 1, len(holders)):
                pid_a = holders[i]["c_personid"]
                pid_b = holders[j]["c_personid"]
                edge_key = (min(pid_a, pid_b), max(pid_a, pid_b), office_id)
                if edge_key not in edge_set:
                    edge_set.add(edge_key)
                    edges.append({
                        "source": str(pid_a),
                        "target": str(pid_b),
                        "type": "co-office",
                        "relation_chn": office_name,
                        "relation": holders[0]["c_office_pinyin"] or office_name,
                    })

    return {"nodes": list(nodes.values()), "edges": edges}


def build_place_network(
    conn: sqlite3.Connection,
    addr_query: str,
    addr_type: Optional[int] = None,
) -> dict:
    """Build a bipartite person-place network for a given place.

    Nodes are persons + places, edges are affiliations.
    """
    type_filter = "AND ba.c_addr_type = ?" if addr_type else ""
    params: list = [f"%{addr_query}%"]
    if addr_type:
        params.append(addr_type)

    rows = conn.execute(f"""
        SELECT ba.c_personid, ba.c_addr_id,
               ac.c_name_chn as addr_chn, ac.c_name as addr_pinyin,
               bac.c_addr_desc_chn, bac.c_addr_desc,
               ac.x_coord, ac.y_coord
        FROM BIOG_ADDR_DATA ba
        JOIN ADDR_CODES ac ON ac.c_addr_id = ba.c_addr_id
        JOIN BIOG_ADDR_CODES bac ON bac.c_addr_type = ba.c_addr_type
        WHERE ac.c_name_chn LIKE ?
        {type_filter}
        LIMIT 5000
    """, params).fetchall()

    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    for row in rows:
        pid = row["c_personid"]
        addr_id = row["c_addr_id"]
        addr_node_id = f"place_{addr_id}"

        if str(pid) not in nodes:
            node = _get_person_node(conn, pid)
            if node:
                node["node_type"] = "person"
                nodes[node["id"]] = node

        if addr_node_id not in nodes:
            nodes[addr_node_id] = {
                "id": addr_node_id,
                "label": row["addr_chn"] or row["addr_pinyin"],
                "name_chn": row["addr_chn"] or "",
                "name_pinyin": row["addr_pinyin"] or "",
                "node_type": "place",
                "longitude": row["x_coord"] or 0,
                "latitude": row["y_coord"] or 0,
            }

        edges.append({
            "source": str(pid),
            "target": addr_node_id,
            "type": "person-place",
            "relation_chn": row["c_addr_desc_chn"],
            "relation": row["c_addr_desc"],
        })

    return {"nodes": list(nodes.values()), "edges": edges}


# ---------------------------------------------------------------------------
# Kinship tree visualization (DOT / Mermaid)
# ---------------------------------------------------------------------------

def build_kinship_tree(
    conn: sqlite3.Connection,
    person_id: int,
    depth: int = 2,
    max_gen_up: int = 3,
    max_gen_down: int = 3,
) -> dict:
    """Build kinship tree data for visualization.

    Assigns each person a generation relative to ego (0).
    Returns {"nodes": [...], "edges": [...], "ego_id": str}.
    Nodes have "generation" and "is_ego" fields.
    Edges have "edge_type": parent-child | marriage | sibling | affinal.
    """
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    edge_set: set[tuple] = set()

    ego = _get_person_node(conn, person_id)
    if not ego:
        return {"nodes": [], "edges": [], "ego_id": str(person_id)}
    ego["generation"] = 0
    ego["is_ego"] = True
    nodes[ego["id"]] = ego

    # BFS: frontier maps person_id -> generation
    frontier: dict[int, int] = {person_id: 0}
    visited: set[int] = set()

    for _ in range(depth):
        next_frontier: dict[int, int] = {}
        for pid, gen in frontier.items():
            if pid in visited:
                continue
            visited.add(pid)

            rows = conn.execute("""
                SELECT k.c_kin_id, kc.c_kinrel_chn, kc.c_kinrel,
                       kc.c_upstep, kc.c_dwnstep, kc.c_colstep, kc.c_marstep
                FROM KIN_DATA k
                JOIN KINSHIP_CODES kc ON kc.c_kincode = k.c_kin_code
                WHERE k.c_personid = ?
            """, (pid,)).fetchall()

            for row in rows:
                kin_id = row["c_kin_id"]
                up = row["c_upstep"] or 0
                dn = row["c_dwnstep"] or 0
                col = row["c_colstep"] or 0
                mar = row["c_marstep"] or 0

                # Generation offset: descendants are positive, ancestors negative
                kin_gen = gen + dn - up

                # Skip kin outside generation bounds
                if kin_gen < -max_gen_up or kin_gen > max_gen_down:
                    continue

                # Add node
                if str(kin_id) not in nodes:
                    node = _get_person_node(conn, kin_id)
                    if not node:
                        continue
                    node["generation"] = kin_gen
                    node["is_ego"] = False
                    nodes[node["id"]] = node

                # Classify edge type and determine direction
                if mar > 0 and up == 0 and dn == 0 and col == 0:
                    edge_type = "marriage"
                    source, target = str(pid), str(kin_id)
                elif up > dn:
                    # Kin is an ancestor → edge from kin (parent) to person (child)
                    edge_type = "parent-child"
                    source, target = str(kin_id), str(pid)
                elif dn > up:
                    # Kin is a descendant → edge from person (parent) to kin (child)
                    edge_type = "parent-child"
                    source, target = str(pid), str(kin_id)
                elif col > 0 and mar == 0:
                    edge_type = "sibling"
                    source, target = str(pid), str(kin_id)
                else:
                    edge_type = "affinal"
                    source, target = str(pid), str(kin_id)

                edge_key = (min(int(source), int(target)),
                            max(int(source), int(target)))
                if edge_key not in edge_set:
                    edge_set.add(edge_key)
                    edges.append({
                        "source": source,
                        "target": target,
                        "relation_chn": row["c_kinrel_chn"],
                        "relation": row["c_kinrel"],
                        "edge_type": edge_type,
                    })

                if kin_id not in visited:
                    next_frontier[kin_id] = kin_gen

        frontier = next_frontier

    return {"nodes": list(nodes.values()), "edges": edges, "ego_id": str(person_id)}


def render_tree_dot(tree: dict) -> str:
    """Render kinship tree as Graphviz DOT."""
    from collections import defaultdict

    lines = [
        'digraph kinship {',
        '  rankdir=TB;',
        '  splines=polyline;',
        '  nodesep=0.6;',
        '  ranksep=0.8;',
        '  node [shape=box, style="filled,rounded", fontname="Noto Sans CJK SC,Arial,sans-serif", fontsize=11, margin="0.15,0.08"];',
        '  edge [fontname="Noto Sans CJK SC,Arial,sans-serif", fontsize=9, color="#666666"];',
    ]

    # Group nodes by generation
    gen_groups: dict[int, list] = defaultdict(list)
    for node in tree["nodes"]:
        gen_groups[node["generation"]].append(node)

    gen_names = {
        -4: "高祖", -3: "曾祖", -2: "祖", -1: "親",
        0: "本人", 1: "子女", 2: "孫", 3: "曾孫", 4: "玄孫",
    }

    for gen in sorted(gen_groups.keys()):
        gen_label = gen_names.get(gen, f"Gen {gen:+d}")
        lines.append(f'  subgraph gen_{gen + 100} {{')
        lines.append(f'    rank=same;')
        for node in gen_groups[gen]:
            is_ego = node.get("is_ego", False)
            gender = node.get("gender", "M")

            if is_ego:
                fill = "#FFD700"
            elif gender == "F":
                fill = "#FFB6C1"
            else:
                fill = "#ADD8E6"

            penwidth = "3" if is_ego else "1"
            label = node.get("name_chn") or node.get("name_pinyin") or node["id"]
            by = node.get("birth_year", 0)
            dy = node.get("death_year", 0)
            if by and by != 0:
                label += f'\\n{by}'
                if dy and dy != 0:
                    label += f'–{dy}'

            lines.append(
                f'    "{node["id"]}" [label="{label}", '
                f'fillcolor="{fill}", penwidth={penwidth}];'
            )
        lines.append('  }')

    # Edges
    for edge in tree["edges"]:
        src = f'"{edge["source"]}"'
        tgt = f'"{edge["target"]}"'
        rel = edge["relation_chn"].replace('"', '\\"')

        if edge["edge_type"] == "marriage":
            lines.append(
                f'  {src} -> {tgt} [dir=none, style=dashed, '
                f'color="#CC0000", label="{rel}"];'
            )
        elif edge["edge_type"] == "parent-child":
            lines.append(f'  {src} -> {tgt} [label="{rel}"];')
        elif edge["edge_type"] == "sibling":
            lines.append(
                f'  {src} -> {tgt} [dir=none, style=dotted, label="{rel}"];'
            )
        else:  # affinal
            lines.append(
                f'  {src} -> {tgt} [dir=none, style=dashed, '
                f'color="#996633", label="{rel}"];'
            )

    lines.append('}')
    return '\n'.join(lines)


def render_tree_mermaid(tree: dict) -> str:
    """Render kinship tree as Mermaid flowchart."""
    lines = ['graph TD']

    # Node definitions (prefix IDs with 'p' since Mermaid can't start with digits)
    for node in tree["nodes"]:
        nid = f'p{node["id"]}'
        label = node.get("name_chn") or node.get("name_pinyin") or node["id"]
        by = node.get("birth_year", 0)
        dy = node.get("death_year", 0)
        if by and by != 0:
            label += f'<br>{by}'
            if dy and dy != 0:
                label += f'–{dy}'

        # Escape quotes in label
        label = label.replace('"', '#quot;')

        cls = "ego" if node.get("is_ego") else (
            "female" if node.get("gender") == "F" else "male"
        )
        lines.append(f'  {nid}["{label}"]:::{cls}')

    lines.append('')

    # Edges
    for edge in tree["edges"]:
        src = f'p{edge["source"]}'
        tgt = f'p{edge["target"]}'
        rel = edge["relation_chn"]

        if edge["edge_type"] == "marriage":
            lines.append(f'  {src} -.-|"{rel}"| {tgt}')
        elif edge["edge_type"] == "parent-child":
            lines.append(f'  {src} -->|"{rel}"| {tgt}')
        elif edge["edge_type"] == "sibling":
            lines.append(f'  {src} ---|"{rel}"| {tgt}')
        else:
            lines.append(f'  {src} -.-|"{rel}"| {tgt}')

    lines.append('')
    lines.append('  classDef male fill:#ADD8E6,stroke:#333,color:#000')
    lines.append('  classDef female fill:#FFB6C1,stroke:#333,color:#000')
    lines.append('  classDef ego fill:#FFD700,stroke:#333,stroke-width:3px,color:#000')

    return '\n'.join(lines)


def export_tree(tree: dict, output: str, fmt: str = "dot") -> None:
    """Export kinship tree to DOT or Mermaid format."""
    if fmt == "dot":
        content = render_tree_dot(tree)
        with open(output, "w", encoding="utf-8") as f:
            f.write(content)
        n = len(tree["nodes"])
        e = len(tree["edges"])
        print(f"Written: {output} ({n} nodes, {e} edges)")
        print(f"Render:  dot -Tsvg {output} -o {output.rsplit('.', 1)[0]}.svg")
        print(f"    or:  dot -Tpng {output} -o {output.rsplit('.', 1)[0]}.png")
    elif fmt == "mermaid":
        content = render_tree_mermaid(tree)
        with open(output, "w", encoding="utf-8") as f:
            f.write(content)
        n = len(tree["nodes"])
        e = len(tree["edges"])
        print(f"Written: {output} ({n} nodes, {e} edges)")
        print(f"Render:  paste into any Mermaid-compatible viewer (GitHub, Obsidian, etc.)")
    elif fmt == "svg":
        dot_content = render_tree_dot(tree)
        try:
            result = subprocess.run(
                ["dot", "-Tsvg"],
                input=dot_content, capture_output=True, text=True, check=True,
            )
            with open(output, "w", encoding="utf-8") as f:
                f.write(result.stdout)
            print(f"Written: {output} ({len(tree['nodes'])} nodes, {len(tree['edges'])} edges)")
        except FileNotFoundError:
            print("ERROR: Graphviz 'dot' not found.", file=sys.stderr)
            print("  macOS:   brew install graphviz", file=sys.stderr)
            print("  Windows: winget install graphviz", file=sys.stderr)
            print("  Linux:   sudo apt install graphviz", file=sys.stderr)
            # Fall back to writing DOT
            fallback = output.rsplit(".", 1)[0] + ".dot"
            with open(fallback, "w", encoding="utf-8") as f:
                f.write(dot_content)
            print(f"Wrote DOT instead: {fallback}", file=sys.stderr)
    else:
        print(f"Unknown format: {fmt}. Use dot, mermaid, or svg.", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Export formats: GEXF, CSV
# ---------------------------------------------------------------------------

def _write_gexf(network: dict, output: str) -> str:
    """Write network to GEXF (Gephi native XML format)."""
    import xml.etree.ElementTree as ET

    gexf = ET.Element("gexf", xmlns="http://gexf.net/1.3", version="1.3")
    graph = ET.SubElement(gexf, "graph", defaultedgetype="directed", mode="static")

    # Node attributes
    node_attrs = ET.SubElement(graph, "attributes", {"class": "node"})
    attr_defs = [
        ("name_chn", "string"), ("name_pinyin", "string"),
        ("gender", "string"), ("dynasty_chn", "string"), ("dynasty", "string"),
        ("birth_year", "integer"), ("death_year", "integer"), ("index_year", "integer"),
        ("node_type", "string"),
        ("longitude", "float"), ("latitude", "float"),
    ]
    for i, (name, atype) in enumerate(attr_defs):
        ET.SubElement(node_attrs, "attribute", id=str(i), title=name, type=atype)

    # Edge attributes
    edge_attrs = ET.SubElement(graph, "attributes", {"class": "edge"})
    edge_attr_defs = [
        ("type", "string"), ("relation_chn", "string"), ("relation", "string"),
    ]
    for i, (name, atype) in enumerate(edge_attr_defs):
        ET.SubElement(edge_attrs, "attribute", id=str(100 + i), title=name, type=atype)

    # Nodes
    nodes_el = ET.SubElement(graph, "nodes")
    attr_name_to_id = {name: str(i) for i, (name, _) in enumerate(attr_defs)}
    for node in network["nodes"]:
        n = ET.SubElement(nodes_el, "node", id=node["id"], label=node.get("label", node["id"]))
        attvals = ET.SubElement(n, "attvalues")
        for attr_name, attr_id in attr_name_to_id.items():
            val = node.get(attr_name)
            if val is not None and val != "" and val != 0:
                ET.SubElement(attvals, "attvalue", {"for": attr_id, "value": str(val)})

    # Edges
    edges_el = ET.SubElement(graph, "edges")
    edge_attr_name_to_id = {name: str(100 + i) for i, (name, _) in enumerate(edge_attr_defs)}
    for i, edge in enumerate(network["edges"]):
        e = ET.SubElement(edges_el, "edge", id=str(i),
                          source=edge["source"], target=edge["target"])
        attvals = ET.SubElement(e, "attvalues")
        for attr_name, attr_id in edge_attr_name_to_id.items():
            val = edge.get(attr_name)
            if val is not None and val != "":
                ET.SubElement(attvals, "attvalue", {"for": attr_id, "value": str(val)})

    tree = ET.ElementTree(gexf)
    ET.indent(tree, space="  ")
    tree.write(output, encoding="unicode", xml_declaration=True)

    return output


def _write_csv(network: dict, output: str) -> tuple[str, str]:
    """Write network to CSV (nodes.csv + edges.csv).

    If output is 'network.csv', creates 'network_nodes.csv' and 'network_edges.csv'.
    """
    import csv

    base = output.rsplit(".", 1)[0] if "." in output else output
    nodes_file = f"{base}_nodes.csv"
    edges_file = f"{base}_edges.csv"

    # Determine all node attribute keys
    node_keys = ["id", "label"]
    extra_keys: list[str] = []
    for node in network["nodes"]:
        for k in node:
            if k not in node_keys and k not in extra_keys:
                extra_keys.append(k)
    all_node_keys = node_keys + extra_keys

    with open(nodes_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_node_keys, extrasaction="ignore")
        writer.writeheader()
        for node in network["nodes"]:
            writer.writerow(node)

    # Edges
    edge_keys = ["source", "target"]
    extra_edge_keys: list[str] = []
    for edge in network["edges"]:
        for k in edge:
            if k not in edge_keys and k not in extra_edge_keys:
                extra_edge_keys.append(k)
    all_edge_keys = edge_keys + extra_edge_keys

    with open(edges_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_edge_keys, extrasaction="ignore")
        writer.writeheader()
        for edge in network["edges"]:
            writer.writerow(edge)

    return nodes_file, edges_file


def export_network(network: dict, output: str, fmt: str = "gexf") -> None:
    """Export a network to a file in the specified format."""
    if fmt == "gexf":
        path = _write_gexf(network, output)
        print(f"Written: {path} ({len(network['nodes'])} nodes, {len(network['edges'])} edges)")
    elif fmt == "csv":
        nodes_f, edges_f = _write_csv(network, output)
        print(f"Written: {nodes_f} ({len(network['nodes'])} nodes)")
        print(f"Written: {edges_f} ({len(network['edges'])} edges)")
    elif fmt == "json":
        with open(output, "w", encoding="utf-8") as f:
            json.dump(network, f, ensure_ascii=False, indent=2, default=str)
        print(f"Written: {output} ({len(network['nodes'])} nodes, {len(network['edges'])} edges)")
    else:
        print(f"Unknown format: {fmt}. Use gexf, csv, or json.", file=sys.stderr)
        sys.exit(1)


def _parse_export_args(args: list[str]) -> dict:
    """Parse common export CLI arguments: --format, --depth, -o, --dynasty, etc."""
    opts: dict[str, Any] = {
        "format": "gexf",
        "depth": 1,
        "output": None,
        "dynasty": None,
        "year_from": None,
        "year_to": None,
        "addr_type": None,
    }
    i = 0
    positional: list[str] = []
    while i < len(args):
        if args[i] in ("--format", "-f"):
            opts["format"] = args[i + 1]
            i += 2
        elif args[i] in ("--depth", "-d"):
            opts["depth"] = int(args[i + 1])
            i += 2
        elif args[i] in ("--output", "-o"):
            opts["output"] = args[i + 1]
            i += 2
        elif args[i] == "--dynasty":
            opts["dynasty"] = int(args[i + 1])
            i += 2
        elif args[i] == "--year-from":
            opts["year_from"] = int(args[i + 1])
            i += 2
        elif args[i] == "--year-to":
            opts["year_to"] = int(args[i + 1])
            i += 2
        elif args[i] == "--addr-type":
            opts["addr_type"] = int(args[i + 1])
            i += 2
        else:
            positional.append(args[i])
            i += 1
    opts["positional"] = positional
    return opts


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

    elif cmd == "texts":
        pid = int(sys.argv[2])
        _print_json(get_texts(conn, pid))

    elif cmd == "institutions":
        pid = int(sys.argv[2])
        _print_json(get_institutions(conn, pid))

    elif cmd == "postaddr":
        pid = int(sys.argv[2])
        _print_json(get_posted_addresses(conn, pid))

    elif cmd == "tree":
        opts = _parse_export_args(sys.argv[2:])
        if not opts["positional"]:
            print("Usage: cbdb_query.py tree <person_id> [--depth/-d N] [--format/-f dot|mermaid|svg] [-o FILE]", file=sys.stderr)
            sys.exit(1)
        pid = int(opts["positional"][0])
        tree = build_kinship_tree(conn, pid, depth=opts["depth"])
        fmt = opts["format"] if opts["format"] != "gexf" else "dot"
        ext = {"dot": "dot", "mermaid": "md", "svg": "svg"}.get(fmt, fmt)
        out = opts["output"] or f"tree_{opts['positional'][0]}.{ext}"
        export_tree(tree, out, fmt)

    elif cmd == "export-kinship":
        opts = _parse_export_args(sys.argv[2:])
        if not opts["positional"]:
            print("Usage: cbdb_query.py export-kinship <person_id> [options]", file=sys.stderr)
            sys.exit(1)
        seed_ids = [int(x) for x in opts["positional"]]
        network = build_kinship_network(conn, seed_ids, depth=opts["depth"])
        out = opts["output"] or f"kinship_{'_'.join(opts['positional'])}.{opts['format']}"
        export_network(network, out, opts["format"])

    elif cmd == "export-associations":
        opts = _parse_export_args(sys.argv[2:])
        if not opts["positional"]:
            print("Usage: cbdb_query.py export-associations <person_id> [options]", file=sys.stderr)
            sys.exit(1)
        seed_ids = [int(x) for x in opts["positional"]]
        network = build_association_network(conn, seed_ids, depth=opts["depth"])
        out = opts["output"] or f"associations_{'_'.join(opts['positional'])}.{opts['format']}"
        export_network(network, out, opts["format"])

    elif cmd == "export-network":
        opts = _parse_export_args(sys.argv[2:])
        if not opts["positional"]:
            print("Usage: cbdb_query.py export-network <person_id> [options]", file=sys.stderr)
            sys.exit(1)
        seed_ids = [int(x) for x in opts["positional"]]
        network = build_combined_network(conn, seed_ids, depth=opts["depth"])
        out = opts["output"] or f"network_{'_'.join(opts['positional'])}.{opts['format']}"
        export_network(network, out, opts["format"])

    elif cmd == "export-office":
        opts = _parse_export_args(sys.argv[2:])
        if not opts["positional"]:
            print("Usage: cbdb_query.py export-office <office_name> [--dynasty N] [options]", file=sys.stderr)
            sys.exit(1)
        query = opts["positional"][0]
        network = build_office_network(conn, query,
                                       dynasty=opts["dynasty"],
                                       year_from=opts["year_from"],
                                       year_to=opts["year_to"])
        out = opts["output"] or f"office_{query}.{opts['format']}"
        export_network(network, out, opts["format"])

    elif cmd == "export-place":
        opts = _parse_export_args(sys.argv[2:])
        if not opts["positional"]:
            print("Usage: cbdb_query.py export-place <place_name> [--addr-type N] [options]", file=sys.stderr)
            sys.exit(1)
        query = opts["positional"][0]
        network = build_place_network(conn, query, addr_type=opts["addr_type"])
        out = opts["output"] or f"place_{query}.{opts['format']}"
        export_network(network, out, opts["format"])

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
