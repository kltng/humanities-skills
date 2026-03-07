#!/usr/bin/env python3
"""
Harvest all placename records from the TGAZ (Temporal Gazetteer) API
and store them in a SQLite database.

Source: https://chgis.hudci.org/tgaz/
Data: China Historical GIS placename database (Harvard & Fudan University)

Strategy: The API caps at 200 results per query. We query by single-character
name prefixes. When a prefix is truncated, we extract the actual second
characters from returned results and subdivide further.
"""

import json
import sqlite3
import time
import re
import sys
import urllib.request
import urllib.parse
import urllib.error

API_BASE = "https://chgis.hudci.org/tgaz/placename"
DB_PATH = "tgaz.db"
MAX_RESULTS = 200
DELAY = 0.35


def create_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS placenames (
            sys_id TEXT PRIMARY KEY,
            uri TEXT,
            name TEXT,
            transcription TEXT,
            year_begin INTEGER,
            year_end INTEGER,
            years_raw TEXT,
            parent_sys_id TEXT,
            parent_name TEXT,
            feature_type TEXT,
            feature_type_raw TEXT,
            object_type TEXT,
            longitude REAL,
            latitude REAL,
            xy_raw TEXT,
            data_source TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_name ON placenames(name);
        CREATE INDEX IF NOT EXISTS idx_transcription ON placenames(transcription);
        CREATE INDEX IF NOT EXISTS idx_years ON placenames(year_begin, year_end);
        CREATE INDEX IF NOT EXISTS idx_feature_type ON placenames(feature_type);
        CREATE INDEX IF NOT EXISTS idx_parent ON placenames(parent_sys_id);
        CREATE INDEX IF NOT EXISTS idx_source ON placenames(data_source);
        CREATE INDEX IF NOT EXISTS idx_coords ON placenames(longitude, latitude);
    """)
    conn.commit()
    return conn


def create_fts(conn):
    c = conn.cursor()
    c.executescript("""
        DROP TABLE IF EXISTS placenames_fts;
        CREATE VIRTUAL TABLE placenames_fts USING fts5(
            sys_id UNINDEXED,
            name,
            transcription,
            feature_type,
            parent_name,
            data_source,
            content='placenames',
            content_rowid='rowid'
        );
        INSERT INTO placenames_fts(placenames_fts) VALUES('rebuild');
    """)
    conn.commit()


def parse_years(s):
    if not s: return None, None
    m = re.match(r'(-?\d+)\s*~\s*(-?\d+)', s.strip())
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def parse_coords(s):
    if not s: return None, None
    parts = s.split(",")
    if len(parts) == 2:
        try: return float(parts[0].strip()), float(parts[1].strip())
        except ValueError: pass
    return None, None


def parse_feature_type(s):
    if not s: return s
    m = re.match(r'.*\(([^)]+)\)', s)
    return m.group(1).strip() if m else s.strip()


def fetch_json(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
            else:
                print(f"  FAILED: {url} -> {e}")
                return None


def insert_placenames(conn, placenames):
    c = conn.cursor()
    inserted = 0
    for p in placenames:
        sys_id = p.get("sys_id", "")
        if not sys_id: continue
        yb, ye = parse_years(p.get("years", ""))
        lon, lat = parse_coords(p.get("xy coordinates", ""))
        ft_raw = p.get("feature type", "")
        try:
            c.execute("""INSERT OR IGNORE INTO placenames
                (sys_id, uri, name, transcription, year_begin, year_end, years_raw,
                 parent_sys_id, parent_name, feature_type, feature_type_raw,
                 object_type, longitude, latitude, xy_raw, data_source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (sys_id, p.get("uri",""), p.get("name",""), p.get("transcription",""),
                 yb, ye, p.get("years",""), p.get("parent sys_id",""),
                 p.get("parent name",""), parse_feature_type(ft_raw), ft_raw,
                 p.get("object type",""), lon, lat, p.get("xy coordinates",""),
                 p.get("data source","")))
            if c.rowcount > 0: inserted += 1
        except sqlite3.Error:
            pass
    conn.commit()
    return inserted


def query_prefix(prefix):
    """Query the API for a name prefix. Returns (placenames, total_count, displayed_count)."""
    url = f"{API_BASE}?n={urllib.parse.quote(prefix)}&fmt=json"
    data = fetch_json(url)
    time.sleep(DELAY)
    if not data or "placenames" not in data:
        return [], 0, 0
    return (data["placenames"],
            int(data.get("count of total results", 0)),
            int(data.get("count of displayed results", 0)))


def get_subdivision_chars(placenames, prefix):
    """Extract unique next characters from returned placename names to guide subdivision."""
    chars = set()
    plen = len(prefix)
    for p in placenames:
        name = p.get("name", "")
        if len(name) > plen:
            chars.add(name[plen])
        # Also check transcription
        trans = p.get("transcription", "")
        if len(trans) > plen:
            chars.add(trans[plen])
    return sorted(chars)


def harvest(db_path):
    conn = create_db(db_path)
    api_calls = 0
    total_inserted = 0

    def do_prefix(prefix, depth=0):
        nonlocal api_calls, total_inserted
        placenames, total, displayed = query_prefix(prefix)
        api_calls += 1
        inserted = insert_placenames(conn, placenames)
        total_inserted += inserted

        db_total = conn.execute("SELECT COUNT(*) FROM placenames").fetchone()[0]
        indent = "  " * depth
        tag = " [TRUNCATED]" if total > displayed else ""
        print(f"{indent}[{api_calls}] '{prefix}': {displayed}/{total} ret, "
              f"+{inserted} new (DB: {db_total:,}){tag}")

        if total > displayed and depth < 3:
            # Get actual next chars from returned data
            next_chars = get_subdivision_chars(placenames, prefix)
            if not next_chars:
                # Fallback: try common characters
                next_chars = list("一二三四五六七八九十大小上下中东西南北")
            for ch in next_chars:
                do_prefix(prefix + ch, depth + 1)

    # ---- Phase 1: Common CJK first characters ----
    # These cover the vast majority of Chinese place names
    cjk_first = sorted(set(
        "一丁七万三上下不东两中丰临丹主丽乃久乌义乐九云五井亚京人仁今仙代令仪伊会伟传伯佛佳"
        "使侯保信修倒儿元光克兔入全八公六兰关兴兵典养兼内册冠冬冰冲决净凉凌凤凯出刘列初别利到制前力"
        "功加务动助劳化北十千升午半华南博卢卫危即卷厂原去县参又口古只召台史右叶司吉同名向吕吴告周和"
        "品唐善嘉四回国土圣在地坊城基堂堡塔塘壁壤夏外多大天太夷奉女好如威子孔孙宁安宋宏宗官宜宝"
        "宣宫家容密富寒察寨寺封小尖尧居山岑岔岗岘岚岛岩岭岳岷峡峨峰崇崎崔崖嵊嵩巍巢巨巩巫巴市布"
        "师常平广庄庆庐库应底店府度建开张归当彝彭德徐心志忠怀思恒恩惠慈成戎扬招拱振授控搜故文新方施"
        "旌旧昆昌明易星春昭晋景智曲曹曾望朝木朱李杜杨杭松板林果柏柘柱柳栅标栋栖栗桂桃桐桑桥桦梁梅"
        "梓梧梨梭棉棠楚楼榆榕槐槽横橘檀欧正武永汉汝江池汤汶汾沁沂沃沅沈沙沟没河沿泉泊泌泗泡泰泸"
        "泽洋洛洞津洪洮洲浇浈浉济浔浙浚浦浩浪浮海涂涉涌涞涡涤润涧涪涯液涿淄淅淇淑淖淡淤淮深淳混"
        "淹清渊渌渎渐渑渔渝渠温渡渭港游湄湖湘湛湟湾源溆溧溪滁滇滋滑滕满漂漓演漠漳潘潜潞潢潭潮澄"
        "澎澜澧灌灵火炉照熊燕爱牛特犍玄玉王玛环现玲珊珍珠珲琅琊琛琢琼瑞瑰瑶璧瓜甘生田甲电留略番"
        "盆盈益盐监盘盛目直相省眉真石砀砂研碌磁磐社祁祈祖祝神祥禄禅福禹秀科秦积移程穆立竹笔等筑简"
        "管米粉精素索紫红约纯纳纵绍经绘绛绥绿缅罗美义羊群翁翔翠老肃肇肥胡腊舒舟良艾芒花芦苍苏苗英"
        "茂范茅茶荆荒荡莒莱莲营萍萧落蒙蒲蓝藏虎虞蛟行衡衢西覃观角解言许论设诏诗诚谢谷豫象貌贞贡财"
        "贵赣赤走起越足路车辉辰辽达迁连通逢道遥邓邕邛邢那邯邱邳邵邹郁郃郊郎郏郑郓郝郡部郸都鄂鄄鄞"
        "鄠鄢鄱酉醴金钟钦铁铅铜银锡锦镇长门闵间闻闽阁阜阡阮阳阴阿陀附陆陈降陕陵陶隆隋随隐雄雅雍"
        "雷霍霞青静靖靳鞍韩韶音顺顾颍风飞馆首香马驻驿骆高魏鱼鲁鲤鳌鸡鸣鹅鹤鹿麒麓麟黄黎黑黔龙龟"
    ))

    print(f"Phase 1: {len(cjk_first)} CJK prefixes")
    print("=" * 60)

    for i, ch in enumerate(cjk_first):
        do_prefix(ch)
        if (i + 1) % 100 == 0:
            db_total = conn.execute("SELECT COUNT(*) FROM placenames").fetchone()[0]
            print(f"\n--- {i+1}/{len(cjk_first)} done, {db_total:,} records, {api_calls} calls ---\n")

    # ---- Phase 2: Latin letters (upper+lower) ----
    print(f"\nPhase 2: Latin prefixes")
    print("=" * 60)

    for ch in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ":
        do_prefix(ch)

    # ---- Phase 3: Digits and special ----
    print(f"\nPhase 3: Digits")
    print("=" * 60)

    for ch in "0123456789":
        do_prefix(ch)

    # ---- Phase 4: Additional CJK ranges for completeness ----
    # Try less common first characters by sampling the CJK block
    print(f"\nPhase 4: CJK block sweep (sampling)")
    print("=" * 60)

    existing_chars = set(cjk_first)
    for cp in range(0x4E00, 0x9FFF, 3):  # Sample every 3rd character
        ch = chr(cp)
        if ch not in existing_chars:
            do_prefix(ch)

    # ---- Build FTS ----
    print(f"\nBuilding full-text search index...")
    create_fts(conn)

    # ---- Stats ----
    final = conn.execute("SELECT COUNT(*) FROM placenames").fetchone()[0]
    sources = conn.execute(
        "SELECT data_source, COUNT(*) FROM placenames GROUP BY data_source ORDER BY COUNT(*) DESC"
    ).fetchall()
    yr = conn.execute(
        "SELECT MIN(year_begin), MAX(year_end) FROM placenames WHERE year_begin IS NOT NULL"
    ).fetchone()
    ftypes = conn.execute(
        "SELECT feature_type, COUNT(*) FROM placenames GROUP BY feature_type ORDER BY COUNT(*) DESC LIMIT 15"
    ).fetchall()

    print(f"\n{'='*60}")
    print(f"HARVEST COMPLETE")
    print(f"{'='*60}")
    print(f"Total records: {final:,}")
    print(f"API calls: {api_calls:,}")
    print(f"\nSources:")
    for src, cnt in sources: print(f"  {src}: {cnt:,}")
    if yr[0]: print(f"\nYear range: {yr[0]} to {yr[1]}")
    print(f"\nTop feature types:")
    for ft, cnt in ftypes: print(f"  {ft}: {cnt:,}")
    print(f"\nSaved to: {db_path}")

    conn.close()


if __name__ == "__main__":
    harvest(sys.argv[1] if len(sys.argv) > 1 else DB_PATH)
