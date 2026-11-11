#!/usr/bin/env python3
"""
CBETA API client: the Chinese Buddhist canon (CBETA) and the DILA authority
database of Buddhist persons, places and dates.

Zero external dependencies; uses only the Python standard library.

    python3 cbeta_api.py person 空海          # DILA person authority (name or A-ID)
    python3 cbeta_api.py place 嵩山
    python3 cbeta_api.py works-by A000759     # CBETA works by a creator ID
    python3 cbeta_api.py work T0235
    python3 cbeta_api.py search 如是我聞
    python3 cbeta_api.py variants 師錬        # variant forms that do occur in CBETA
    python3 cbeta_api.py line T08n0235_p0748c17
    python3 cbeta_api.py goto "CBETA, T08, no. 235, p. 748c17"
    python3 cbeta_api.py wikidata A000759     # Wikidata item(s) with P1187 = A000759
"""

from __future__ import annotations

import html
import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Optional
from urllib.error import HTTPError, URLError


class CBETAAPI:
    """Client for the CBETA API (cbdata.dila.edu.tw) and the DILA authority API."""

    # The old host api.cbetaonline.cn no longer resolves (checked 2026-11-09).
    BASE_URL = "https://cbdata.dila.edu.tw/stable"
    AUTHORITY_URL = "https://authority.dila.edu.tw/webwidget/getAuthorityData.php"
    WDQS_URL = "https://query.wikidata.org/sparql"
    DEFAULT_USER_AGENT = "CBETAAPISkill/1.0 (https://github.com/kltng/humanities-skills)"
    MAX_QUERY_CHARS = 40  # the CBETA API rejects longer q values

    def __init__(self, min_request_interval: float = 1.0, max_retries: int = 3,
                 user_agent: str = DEFAULT_USER_AGENT):
        self._last_request_time = 0.0
        self._min_request_interval = min_request_interval
        self._max_retries = max_retries
        self._user_agent = user_agent
        # authority.dila.edu.tw's certificate has no Subject Key Identifier. Python
        # 3.13+ (with some OpenSSL builds) rejects that under VERIFY_X509_STRICT.
        # Drop only that flag: the chain and the hostname are still verified.
        self._ssl = ssl.create_default_context()
        self._ssl.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)

    # ── HTTP ────────────────────────────────────────────────────

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    @staticmethod
    def _retry_after(e: HTTPError, default: float) -> float:
        value = e.headers.get("Retry-After") if e.headers else None
        try:
            return min(60.0, max(default, float(value)))
        except (TypeError, ValueError):
            return default

    def _get(self, url: str, params: Optional[dict] = None, accept: str = "application/json",
             timeout: int = 30) -> str:
        if params:
            clean = {k: v for k, v in params.items() if v is not None and v != ""}
            url += "?" + urllib.parse.urlencode(clean, safe=",")
        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            self._rate_limit()
            req = urllib.request.Request(url)
            req.add_header("Accept", accept)
            req.add_header("User-Agent", self._user_agent)
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=self._ssl) as resp:
                    return resp.read().decode("utf-8")
            except HTTPError as e:
                backoff = min(8.0, 0.5 * (2 ** attempt))
                if e.code == 404:
                    raise RuntimeError(f"CBETA/DILA endpoint not found (404): {url}") from e
                if e.code in (429, 503):
                    last_error = e
                    time.sleep(self._retry_after(e, backoff))
                    continue
                if 400 <= e.code < 500:
                    raise
                last_error = e
                time.sleep(backoff)
            except URLError as e:
                last_error = e
                time.sleep(min(8.0, 0.5 * (2 ** attempt)))
        if last_error:
            raise last_error
        raise RuntimeError("Request failed")

    def _cbeta(self, path: str, params: Optional[dict] = None) -> Any:
        text = self._get(f"{self.BASE_URL}/{path}", params)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"CBETA API did not return JSON for {path}: {text[:200]!r}") from e
        if isinstance(data, dict) and data.get("success") is False:
            raise ValueError(f"CBETA API error: {data.get('error')}")
        return data

    def _check_q(self, q: str) -> str:
        q = (q or "").strip()
        if not q:
            raise ValueError("Empty query")
        if len(q) > self.MAX_QUERY_CHARS:
            raise ValueError(f"Query is {len(q)} characters; the CBETA API allows at most "
                             f"{self.MAX_QUERY_CHARS}. Shorten it.")
        return q

    # ── CBETA: works (佛典) ──────────────────────────────────────

    def work(self, work_id: str) -> Optional[dict]:
        """Metadata for one work, e.g. 'T0235'. Returns None if unknown."""
        data = self._cbeta("works", {"work": work_id})
        results = data.get("results") or []
        return results[0] if results else None

    def works_by_creator(self, creator_id: Optional[str] = None, name: Optional[str] = None,
                         unconfirmed_only: bool = False) -> list[dict]:
        """Works by a creator. Prefer the DILA ID (e.g. 'A000759').

        `name` matches any creator whose name contains it (all records);
        with unconfirmed_only=True, only records whose creator has no ID yet."""
        if creator_id:
            params = {"creator_id": creator_id}
        elif name:
            params = {"creator_name" if unconfirmed_only else "creator": name}
        else:
            raise ValueError("Give creator_id or name")
        return self._cbeta("works", params).get("results") or []

    def works_by_time(self, dynasty: Optional[str] = None, time_start: Optional[int] = None,
                      time_end: Optional[int] = None) -> list[dict]:
        """Works by dynasty name ('唐', or '符秦,前秦') or by CE year range."""
        params = {"dynasty": dynasty, "time_start": time_start, "time_end": time_end}
        return self._cbeta("works", params).get("results") or []

    def toc(self, work_id: str) -> Any:
        """Table of contents (目次) of a work."""
        return self._cbeta("works/toc", {"work": work_id})

    def juan_html(self, work_id: str, juan: int = 1) -> str:
        """The HTML of one fascicle (卷)."""
        data = self._cbeta("juans", {"work": work_id, "juan": juan})
        results = data.get("results") or []
        return results[0] if results else ""

    def juan_text(self, work_id: str, juan: int = 1) -> str:
        """Plain text of one fascicle: HTML tags, line numbers and notes removed.

        A rough reading copy. Cite by line number (from lines()/goto()), not from this."""
        raw = self.juan_html(work_id, juan)
        raw = re.sub(r'(?s)<span class="lb"[^>]*>.*?</span>', "", raw)
        raw = re.sub(r'(?s)<div id="back".*', "", raw)
        raw = re.sub(r"(?s)<(script|style|head)[^>]*>.*?</\1>", "", raw)
        raw = re.sub(r"<br\s*/?>|</p>|</div>", "\n", raw)
        text = html.unescape(re.sub(r"<[^>]+>", "", raw))
        return re.sub(r"\n\s*\n+", "\n", text).strip()

    # ── CBETA: lines and citations ───────────────────────────────

    def lines(self, linehead: Optional[str] = None, before: int = 0, after: int = 0,
              start: Optional[str] = None, end: Optional[str] = None) -> list[dict]:
        """Text of lines by line ID, e.g. 'T08n0235_p0748c17'.

        Either one linehead (with before/after lines) or a start/end range.
        Each result has 'linehead', 'html' and 'notes' (collation notes)."""
        if start and end:
            params = {"linehead_start": start, "linehead_end": end}
        elif linehead:
            params = {"linehead": linehead, "before": before or None, "after": after or None}
        else:
            raise ValueError("Give linehead, or start and end")
        return self._cbeta("lines", params).get("results") or []

    def goto(self, citation: str) -> Optional[dict]:
        """Resolve a citation or line ID to a location.

        Accepts 'T08n0235_p0748c17', 'CBETA, T08, no. 235, p. 748c17',
        'T51, no. 2087, pp. 868-888', 《大正藏》冊47，第1969 號, or a quick
        code such as 'SA1' (雜阿含). Returns {work, juan, vol, lb, linehead, title}."""
        data = self._cbeta("juans/goto", {"linehead": citation})
        results = data.get("results") or [] if isinstance(data, dict) else []
        return results[0] if results else None

    @staticmethod
    def cite(work: dict, lb: Optional[str] = None) -> str:
        """CBETA citation, e.g. 'CBETA, T08, no. 235, p. 748c17'."""
        vol = work.get("vol") or ""
        num = re.sub(r"^[A-Z]+0*", "", work.get("work", "")) or work.get("work", "")
        out = f"CBETA, {vol}, no. {num}"
        if lb:
            page = lb.lstrip("0") if lb[:4].isdigit() else lb
            out += f", p. {page}"
        return out

    # ── CBETA: search ────────────────────────────────────────────

    def search(self, q: str, rows: int = 20, start: int = 0, order: Optional[str] = None,
               **filters: Any) -> dict:
        """Full-text search. Returns num_found, total_term_hits, results (one per juan).

        Filters: canon='T' or 'T,X', category='禪宗部類', work='T0235',
        works='T0026,T0099', creator='A000439', dynasty='唐', time='800..900',
        work_type='textbody'. order='time_from+' sorts oldest first."""
        params = {"q": self._check_q(q), "rows": rows, "start": start, "order": order, **filters}
        return self._cbeta("search", params)

    def search_all_in_one(self, q: str, rows: int = 20, start: int = 0, around: int = 10,
                          facet: bool = False, **filters: Any) -> dict:
        """Full-text search with keyword-in-context snippets for each juan.

        q may use extended syntax: '"法鼓" "迦葉"' (AND), '"波羅蜜" | "波羅密"' (OR),
        '"迦葉" !"迦葉佛"' (NOT), '"法鼓" NEAR/7 "迦葉"'."""
        params = {"q": self._check_q(q), "rows": rows, "start": start, "around": around,
                  "facet": 1 if facet else None, **filters}
        return self._cbeta("search/all_in_one", params)

    def search_kwic(self, work_id: str, juan: int, q: str, mark: bool = True) -> list[dict]:
        """Keyword in context inside one juan. Each hit has 'lb' (page-column-line)."""
        params = {"work": work_id, "juan": juan, "q": self._check_q(q), "mark": 1 if mark else 0}
        return self._cbeta("search/kwic", params).get("results") or []

    def search_title(self, q: str, rows: int = 20) -> list[dict]:
        """Fuzzy search in work titles (經名); needs at least 3 matching characters."""
        return self._cbeta("search/title", {"q": self._check_q(q), "rows": rows}).get("results") or []

    def search_toc(self, q: str) -> list[dict]:
        """Search catalogs, titles and internal tables of contents. Each result has a 'type'."""
        return self._cbeta("search/toc", {"q": self._check_q(q)}).get("results") or []

    def search_variants(self, q: str, scope: Optional[str] = None) -> list[dict]:
        """Variant-character forms of q that occur in CBETA, with hit counts.

        Use this when a name or term finds nothing: Japanese forms such as 錬
        are often written 鍊 in CBETA. scope='title' limits to titles."""
        params = {"q": self._check_q(q), "scope": scope}
        return self._cbeta("search/variants", params).get("results") or []

    def search_similar(self, q: str, **filters: Any) -> list[dict]:
        """Find passages similar to q (6–40 characters, no punctuation), e.g. a quotation."""
        return self._cbeta("search/similar", {"q": self._check_q(q), **filters}).get("results") or []

    def search_simplified(self, q: str, **filters: Any) -> dict:
        """Search with simplified characters (converted with OpenCC). Returns {'q', 'hits'}."""
        return self._cbeta("search/sc", {"q": q, **filters})

    def sc2tc(self, text: str) -> str:
        """Simplified → traditional Chinese, CBETA's converter."""
        return self._get(f"{self.BASE_URL}/chinese_tools/sc2tc", {"q": text}, accept="text/plain")

    # ── DILA authority database ─────────────────────────────────

    def _authority(self, params: dict) -> Any:
        text = self._get(self.AUTHORITY_URL, params).strip()
        if not text or text == "null":
            return None
        m = re.match(r"^[\w$]+\((.*)\)\s*;?$", text, re.S)  # strip a JSONP wrapper if present
        if m:
            text = m.group(1)
        return json.loads(text)

    @staticmethod
    def _records(data: Any) -> list[dict]:
        """Turn {'data1': {...}, 'data2': {...}} (or a list) into a list of records."""
        if not data:
            return []
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict):
            keys = sorted((k for k in data if re.fullmatch(r"data\d+", k)), key=lambda k: int(k[4:]))
            return [data[k] for k in keys if isinstance(data[k], dict)]
        return []

    def person(self, id_or_name: str) -> list[dict]:
        """DILA person authority. An ID ('A000759') gives one record; a name
        ('空海') gives every person whose name or other names contain it."""
        return self._records(self._authority({"type": "person", "id": id_or_name}))

    def place(self, id_or_name: str) -> list[dict]:
        """DILA place authority ('PL000000023253' or '嵩山'). Has lat/long and modern district."""
        return self._records(self._authority({"type": "place", "id": id_or_name}))

    def date(self, when: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None,
             fmt: str = "s") -> Any:
        """DILA date authority (Chinese calendar). fmt 's' = ISO date '+1592-05-29',
        'j' = Julian Day Number, 'd' = DILA date ID. Returns the raw JSON
        ('W' for when; 'F' and 'T' for a from-to query)."""
        if when:
            params = {"type": "time", "when": when, "format": fmt}
        elif start and end:
            params = {"type": "time", "from": start, "to": end, "format": fmt}
        else:
            raise ValueError("Give when, or start and end")
        return self._authority(params)

    def wikidata_for_person(self, authority_id: str) -> list[dict]:
        """Wikidata items whose P1187 (DILA person ID) equals authority_id.

        Returns [{'qid', 'label'}]. Empty list = no Wikidata link yet (not 'no such person')."""
        if not re.fullmatch(r"A\d{6}", authority_id or ""):
            raise ValueError("authority_id must look like A000759")
        query = ('SELECT ?item ?itemLabel WHERE { ?item wdt:P1187 "%s" . '
                 'SERVICE wikibase:label { bd:serviceParam wikibase:language "zh,ja,en". } }'
                 % authority_id)
        text = self._get(self.WDQS_URL, {"query": query, "format": "json"},
                         accept="application/sparql-results+json")
        out = []
        for b in json.loads(text).get("results", {}).get("bindings", []):
            out.append({"qid": b["item"]["value"].rsplit("/", 1)[-1],
                        "label": b.get("itemLabel", {}).get("value", "")})
        return out

    @staticmethod
    def summarize_person(p: dict) -> str:
        """One readable paragraph for a DILA person record."""
        def clean(s: Any) -> str:
            return re.sub(r"<[^>]+>", "", html.unescape(str(s or ""))).strip()
        born = p.get("bornDateBegin") or "unknown"
        died = p.get("diedDateBegin") or "unknown"
        lines = [f"{p.get('name', '?')} ({p.get('authorityID', '?')})",
                 f"  dynasty/country: {clean(p.get('dynasty')) or '-'}; monk: {p.get('monk') or '-'}",
                 f"  born: {born}  died: {died}"]
        if p.get("zenSchool") or p.get("zenSect"):
            lines.append(f"  school: {clean(p.get('zenSchool'))} {clean(p.get('zenSect'))}".rstrip())
        if p.get("birthPlaceName"):
            lines.append(f"  birthplace: {clean(p.get('birthPlaceName'))} ({p.get('birthPlaceCode')})")
        if p.get("names"):
            lines.append("  other names: " + " ".join(clean(p["names"]).split()))
        if p.get("note"):
            lines.append("  note: " + clean(p["note"])[:300])
        return "\n".join(lines)


def _main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 1
    cmd, arg = argv[1], " ".join(argv[2:])
    api = CBETAAPI()
    dump = lambda x: print(json.dumps(x, ensure_ascii=False, indent=1))
    if cmd == "person":
        recs = api.person(arg)
        print("\n\n".join(api.summarize_person(r) for r in recs) or "No match. Try variants or another name.")
    elif cmd == "place":
        dump(api.place(arg))
    elif cmd == "works-by":
        rows = api.works_by_creator(creator_id=arg) if re.fullmatch(r"A\d{6}", arg) else api.works_by_creator(name=arg)
        for w in rows:
            print(w.get("work"), w.get("title"), "|", w.get("byline", ""), "|", w.get("time_from", ""))
    elif cmd == "work":
        dump(api.work(arg))
    elif cmd == "search":
        d = api.search(arg, rows=10)
        print(f"{d.get('num_found')} juan, {d.get('total_term_hits')} hits")
        for r in d.get("results", []):
            print(r.get("work"), f"juan {r.get('juan')}", r.get("title"), "|", r.get("byline", ""), "|", r.get("term_hits"))
    elif cmd == "variants":
        dump(api.search_variants(arg))
    elif cmd == "line":
        dump(api.lines(arg))
    elif cmd == "goto":
        dump(api.goto(arg))
    elif cmd == "wikidata":
        dump(api.wikidata_for_person(arg))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
