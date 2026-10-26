"""
Alma SRU catalog client for many research libraries — zero external dependencies.

Many libraries run Ex Libris Alma, and many of them leave Alma's SRU interface
open (no API key). This module searches one or several of them, turns the
MARCXML into simple dicts, pairs romanized fields with their vernacular (880)
versions, and reads the Alma holdings fields (AVA = print, AVE = online).

Usage as a CLI:
    python alma_sru.py libraries
    python alma_sru.py search --library oxford --title 明史 --language chi
    python alma_sru.py search --library oxford,cambridge,toronto --oclc 424023
    python alma_sru.py search --library all --isbn 9787101003277 --limit 3
    python alma_sru.py record --library penn 9960332043503681
"""

import argparse
import email.utils
import http.client
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

USER_AGENT = (
    "AlmaSRUCatalogsSkill/1.0 (Claude Code skill; research use; "
    "+https://github.com/kltng/humanities-skills)"
)

# Each library: SRU base URL, record page template ({mms_id}), and notes.
# All endpoints and record links were tested on 2026-10-25 (Taiwan: 2026-10-26).
LIBRARIES: Dict[str, Dict[str, str]] = {
    "umich": {
        "name": "University of Michigan Library",
        "sru": "https://umich.alma.exlibrisgroup.com/view/sru/01UMICH_INST",
        "record_url": "https://search.lib.umich.edu/catalog/record/{mms_id}",
    },
    "princeton": {
        "name": "Princeton University Library",
        "sru": "https://princeton.alma.exlibrisgroup.com/view/sru/01PRI_INST",
        "record_url": "https://catalog.princeton.edu/catalog/{mms_id}",
    },
    "yale": {
        "name": "Yale University Library",
        "sru": "https://yale.alma.exlibrisgroup.com/view/sru/01YALE_INST",
        "record_url": "https://search.library.yale.edu/catalog/{mms_id}",
    },
    "penn": {
        "name": "University of Pennsylvania Libraries",
        "sru": "https://upenn.alma.exlibrisgroup.com/view/sru/01UPENN_INST",
        "record_url": "https://find.library.upenn.edu/catalog/{mms_id}",
    },
    "mit": {
        "name": "MIT Libraries",
        "sru": "https://mit.alma.exlibrisgroup.com/view/sru/01MIT_INST",
        "record_url": "https://mit.primo.exlibrisgroup.com/discovery/fulldisplay?docid=alma{mms_id}&vid=01MIT_INST:MIT",
        "note": "SRU finds far fewer records than MIT's TIMDEX API (2 vs 591 for 明史); prefer the mit-timdex skill.",
    },
    "duke": {
        "name": "Duke University Libraries",
        "sru": "https://duke.alma.exlibrisgroup.com/view/sru/01DUKE_INST",
        "record_url": "https://duke.primo.exlibrisgroup.com/discovery/fulldisplay?docid=alma{mms_id}&vid=01DUKE_INST:DUKE",
    },
    "pitt": {
        "name": "University of Pittsburgh Library System",
        "sru": "https://pitt.alma.exlibrisgroup.com/view/sru/01PITT_INST",
        "record_url": "https://pitt.primo.exlibrisgroup.com/discovery/fulldisplay?docid=alma{mms_id}&vid=01PITT_INST:01PITT_INST",
    },
    "uiuc": {
        "name": "University of Illinois Urbana-Champaign Library",
        "sru": "https://i-share-uiu.alma.exlibrisgroup.com/view/sru/01CARLI_UIU",
        "record_url": "https://i-share-uiu.primo.exlibrisgroup.com/discovery/fulldisplay?docid=alma{mms_id}&vid=01CARLI_UIU:CARLI_UIU",
    },
    "berkeley": {
        "name": "UC Berkeley Library",
        "sru": "https://berkeley.alma.exlibrisgroup.com/view/sru/01UCS_BER",
        "record_url": "https://search.library.berkeley.edu/discovery/fulldisplay?docid=alma{mms_id}&vid=01UCS_BER:UCB",
    },
    "ucla": {
        "name": "UCLA Library",
        "sru": "https://ucla.alma.exlibrisgroup.com/view/sru/01UCS_LAL",
        "record_url": "https://search.library.ucla.edu/discovery/fulldisplay?docid=alma{mms_id}&vid=01UCS_LAL:UCLA",
    },
    "toronto": {
        "name": "University of Toronto Libraries",
        "sru": "https://utoronto.alma.exlibrisgroup.com/view/sru/01UTORONTO_INST",
        "record_url": "https://librarysearch.library.utoronto.ca/discovery/fulldisplay?docid=alma{mms_id}&vid=01UTORONTO_INST:UTORONTO",
    },
    "oxford": {
        "name": "Bodleian Libraries, University of Oxford",
        "sru": "https://oxford.alma.exlibrisgroup.com/view/sru/44OXF_INST",
        "record_url": "https://oxford.primo.exlibrisgroup.com/discovery/fulldisplay?docid=alma{mms_id}&vid=44OXF_INST:SOLO",
    },
    "cambridge": {
        "name": "Cambridge University Libraries",
        "sru": "https://eu.alma.exlibrisgroup.com/view/sru/44CAM_INST",
        "record_url": "https://idiscover.lib.cam.ac.uk/discovery/fulldisplay?docid=alma{mms_id}&vid=44CAM_INST:44CAM_PROD",
    },
    "edinburgh": {
        "name": "University of Edinburgh Library",
        "sru": "https://ed.alma.exlibrisgroup.com/view/sru/44UOE_INST",
        "record_url": "https://discovered.ed.ac.uk/discovery/fulldisplay?docid=alma{mms_id}&vid=44UOE_INST:44UOE_VU2",
    },
    "sydney": {
        "name": "University of Sydney Library",
        "sru": "https://sydney.alma.exlibrisgroup.com/view/sru/61USYD_INST",
        "record_url": "https://sydney.primo.exlibrisgroup.com/discovery/fulldisplay?docid=alma{mms_id}&vid=61USYD_INST:sydney",
        "note": "SRU records carry no AVA/AVE holdings fields; check availability on the record page. Slow and drops connections; retries handle most failures.",
    },
    "ntu": {
        "name": "National Taiwan University Library 國立臺灣大學圖書館",
        "sru": "https://ap01.alma.exlibrisgroup.com/view/sru/886NTU_INST",
        "record_url": "https://ntu.primo.exlibrisgroup.com/discovery/fulldisplay?docid=alma{mms_id}&vid=886NTU_INST:886NTU_INST",
        "note": "Records are in Chinese without romanized 880 pairs; subjects use Chinese headings (csht), call numbers use the Chinese classification (ncsclt).",
    },
    "nccu": {
        "name": "National Chengchi University Libraries 國立政治大學圖書館",
        "sru": "https://ap01.alma.exlibrisgroup.com/view/sru/886NCCU_INST",
        "record_url": "https://nccu.primo.exlibrisgroup.com/discovery/fulldisplay?docid=alma{mms_id}&vid=886NCCU_INST:886NCCU_INST",
        "note": "Records are in Chinese without romanized 880 pairs; subjects use Chinese headings (csht), call numbers use the Chinese classification (ncsclt).",
    },
    "ncku": {
        "name": "National Cheng Kung University Library 國立成功大學圖書館",
        "sru": "https://ap01.alma.exlibrisgroup.com/view/sru/886NCKU_INST",
        "record_url": "https://ncku.primo.exlibrisgroup.com/discovery/fulldisplay?docid=alma{mms_id}&vid=886NCKU_INST:886NCKU_INST",
        "note": "Records are in Chinese without romanized 880 pairs; subjects use Chinese headings (csht), call numbers use the Chinese classification (ncsclt).",
    },
    "nsysu": {
        "name": "National Sun Yat-sen University Library 國立中山大學圖書館",
        "sru": "https://ap01.alma.exlibrisgroup.com/view/sru/886NSYSU_INST",
        "record_url": "https://nsysu.primo.exlibrisgroup.com/discovery/fulldisplay?docid=alma{mms_id}&vid=886NSYSU_INST:886NSYSU_INST",
        "note": "Records are in Chinese without romanized 880 pairs; subjects use Chinese headings (csht), call numbers use the Chinese classification (ncsclt).",
    },
    "nchu": {
        "name": "National Chung Hsing University Library 國立中興大學圖書館",
        "sru": "https://ap01.alma.exlibrisgroup.com/view/sru/886NCHU_INST",
        "record_url": "https://nchu.primo.exlibrisgroup.com/discovery/fulldisplay?docid=alma{mms_id}&vid=886NCHU_INST:886NCHU_INST",
        "note": "Records are in Chinese without romanized 880 pairs; subjects use Chinese headings (csht), call numbers use the Chinese classification (ncsclt).",
    },
    "ccu": {
        "name": "National Chung Cheng University Library 國立中正大學圖書館",
        "sru": "https://ap01.alma.exlibrisgroup.com/view/sru/886CCU_INST",
        "record_url": "https://ccu.primo.exlibrisgroup.com/discovery/fulldisplay?docid=alma{mms_id}&vid=886CCU_INST:886CCU_INST",
        "note": "Records are in Chinese without romanized 880 pairs; subjects use Chinese headings (csht), call numbers use the Chinese classification (ncsclt).",
    },
}

MAX_PAGE_SIZE = 50  # Alma SRU caps maximumRecords at 50

# Attempts per request; waits between them are 5, 10, 20 s (or Retry-After)
MAX_ATTEMPTS = 4
RETRY_HTTP_CODES = (429, 500, 502, 503, 504)
# Dropped connections and read timeouts (Sydney's SRU does this often)
NETWORK_ERRORS = (urllib.error.URLError, ConnectionError, TimeoutError, http.client.HTTPException)

NS = {
    "srw": "http://www.loc.gov/zing/srw/",
    "marc": "http://www.loc.gov/MARC21/slim",
    "diag": "http://www.loc.gov/zing/srw/diagnostic/",
}

# Friendly names for the most useful Alma SRU indexes.
FIELD_INDEXES = {
    "keyword": "alma.all_for_ui",
    "title": "alma.title",
    "author": "alma.creator",
    "subject": "alma.subjects",
    "isbn": "alma.isbn",
    "issn": "alma.issn",
    "oclc": "alma.oclc_control_number_035_a",
    "lccn": "alma.lccn",
    "publisher": "alma.publisher",
    "series": "alma.series",
    "call_number": "alma.lc_class_number",
    "language": "alma.language",
    "mms_id": "alma.mms_id",
}

SORT_KEYS = {
    "date_desc": "alma.main_pub_date/sort.descending",
    "date_asc": "alma.main_pub_date/sort.ascending",
    "title": "alma.title/sort.ascending",
    "author": "alma.creator/sort.ascending",
}


class SRUError(RuntimeError):
    """The SRU server returned a diagnostic instead of results."""


class IncompleteResults(RuntimeError):
    """A multi-page search failed after some pages; `records` holds what was fetched."""

    def __init__(self, message: str, records: List[Dict[str, Any]]):
        super().__init__(message)
        self.records = records


def resolve_libraries(spec: str) -> List[str]:
    """Turn 'oxford,cambridge' or 'all' into a list of library keys."""
    if spec.strip().lower() == "all":
        return list(LIBRARIES)
    keys = [k.strip().lower() for k in spec.split(",") if k.strip()]
    unknown = [k for k in keys if k not in LIBRARIES]
    if unknown:
        raise ValueError(f"Unknown library: {', '.join(unknown)}. Use one of {sorted(LIBRARIES)} or 'all'")
    return keys


class AlmaSRU:
    """Client for one library's Alma SRU endpoint."""

    # Last request time per server, shared by all clients, so searching several
    # libraries on different servers is fast but each server sees ≤1 request/s.
    _last_request: Dict[str, float] = {}

    def __init__(self, library: str, min_interval: float = 1.0):
        if library not in LIBRARIES:
            raise ValueError(f"Unknown library: {library}. Use one of {sorted(LIBRARIES)}")
        self.library = library
        self.config = LIBRARIES[library]
        self._min_interval = min_interval
        self._host = urllib.parse.urlparse(self.config["sru"]).netloc

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request.get(self._host, 0.0)
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request[self._host] = time.time()

    @staticmethod
    def _retry_after_seconds(e: urllib.error.HTTPError, default: float) -> float:
        """Parse a Retry-After header (seconds or HTTP date), capped at 5 min."""
        value = e.headers.get("Retry-After") if e.headers else None
        if value:
            try:
                return min(300.0, max(0.0, float(value)))
            except ValueError:
                try:
                    when = email.utils.parsedate_to_datetime(value)
                    return min(300.0, max(0.0, when.timestamp() - time.time()))
                except (TypeError, ValueError, AttributeError):
                    pass
        return default

    def _get_xml(self, params: Dict[str, str]) -> ET.Element:
        url = f"{self.config['sru']}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        for attempt in range(MAX_ATTEMPTS):
            self._rate_limit()
            backoff = 5.0 * 2 ** attempt
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    root = ET.fromstring(resp.read())
                    self._raise_diagnostics(root)
                    return root
            except urllib.error.HTTPError as e:
                if e.code == 400:
                    # Alma reports bad CQL as HTTP 400 with an SRU diagnostic body
                    try:
                        self._raise_diagnostics(ET.fromstring(e.read()))
                    except ET.ParseError:
                        pass
                    raise
                if e.code not in RETRY_HTTP_CODES or attempt == MAX_ATTEMPTS - 1:
                    raise
                time.sleep(self._retry_after_seconds(e, backoff))
            except NETWORK_ERRORS:
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                time.sleep(backoff)
        raise RuntimeError("unreachable")

    @staticmethod
    def _raise_diagnostics(root: ET.Element) -> None:
        diag = root.find(".//diag:diagnostic", NS)
        if diag is not None:
            message = diag.findtext("diag:message", default="", namespaces=NS)
            details = diag.findtext("diag:details", default="", namespaces=NS)
            raise SRUError(f"SRU diagnostic: {message} {details}".strip())

    # ── Query building ──

    @staticmethod
    def quote_term(value: str) -> str:
        """Quote a CQL term, escaping backslashes and double quotes."""
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    @classmethod
    def build_cql(
        cls,
        cql: Optional[str] = None,
        sort: Optional[str] = None,
        **fields: Optional[str],
    ) -> str:
        """
        Build a CQL query from friendly field names (AND'd together).

        Pass `cql` for a raw query such as 'alma.title=明史 and alma.main_pub_date<1900'.
        Values ending in `*` are sent unquoted so truncation works (e.g. call_number="DS753*").
        """
        clauses = []
        if cql:
            clauses.append(f"({cql})")
        for name, value in fields.items():
            if value in (None, ""):
                continue
            if name not in FIELD_INDEXES:
                raise ValueError(f"Unknown field: {name}. Use one of {sorted(FIELD_INDEXES)}")
            value = str(value)
            if value.endswith("*") and " " not in value and '"' not in value:
                term = value
            else:
                term = cls.quote_term(value)
            clauses.append(f"{FIELD_INDEXES[name]}={term}")
        if not clauses:
            raise ValueError("Give at least one search field or a raw cql query")
        query = " and ".join(clauses)
        if sort:
            if sort not in SORT_KEYS:
                raise ValueError(f"Unknown sort: {sort}. Use one of {sorted(SORT_KEYS)}")
            query += f" sortBy {SORT_KEYS[sort]}"
        return query

    # ── Search ──

    def search(
        self,
        cql: Optional[str] = None,
        sort: Optional[str] = None,
        limit: int = 10,
        start: int = 1,
        raw: bool = False,
        phrase: bool = False,
        known_dates: bool = False,
        **fields: Optional[str],
    ) -> Dict[str, Any]:
        """
        Search the catalog. Returns {"total", "start", "query", "records"}.

        Args:
            cql: Raw CQL query (optional; combined with any field arguments)
            sort: date_desc, date_asc, title, or author (default: the server's
                  own order, which is not relevance ranking)
            limit: Records to return (1–50)
            start: 1-based position of the first record
            raw: If True, records are MARC dicts instead of summaries
            phrase: Keep only records whose title contains `title` as one
                    connected phrase (SRU `=` matches the words anywhere).
                    `total` stays the server's count; `returned` is the page
                    size before filtering.
            known_dates: Drop records whose year (MARC 008) is not four
                    digits, such as `####`, `19uu`, or blank. Alma still
                    lets these pass date filters and sorts them first.
            **fields: keyword, title, author, subject, isbn, issn, oclc, lccn,
                      publisher, series, call_number, language, mms_id
        """
        if phrase and (raw or not fields.get("title")):
            raise ValueError("phrase=True needs a title search and summary records (raw=False)")
        if known_dates and raw:
            raise ValueError("known_dates=True needs summary records (raw=False)")
        query = self.build_cql(cql=cql, sort=sort, **fields)
        params = {
            "version": "1.2",
            "operation": "searchRetrieve",
            "recordSchema": "marcxml",
            "query": query,
            "maximumRecords": str(max(1, min(limit, MAX_PAGE_SIZE))),
            "startRecord": str(max(1, start)),
        }
        root = self._get_xml(params)
        total = int(root.findtext("srw:numberOfRecords", default="0", namespaces=NS))
        records = []
        for rec in root.findall(".//marc:record", NS):
            marc = parse_marc(rec)
            records.append(marc if raw else summarize(marc, self.config["record_url"]))
        returned = len(records)
        if phrase:
            records = [r for r in records if title_matches(r, fields["title"])]
        if known_dates:
            records = [r for r in records if has_known_year(r)]
        return {"library": self.library, "total": total, "start": start, "query": query, "returned": returned, "records": records}

    def search_all(self, max_results: int = 100, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Page through results (50 per request) up to max_results.

        If a later page still fails after retries, raises IncompleteResults
        with the records fetched so far in `.records`.
        """
        records: List[Dict[str, Any]] = []
        start = 1
        while len(records) < max_results:
            # with filtering, fetch full pages because some records are dropped
            filtering = kwargs.get("phrase") or kwargs.get("known_dates")
            size = MAX_PAGE_SIZE if filtering else min(MAX_PAGE_SIZE, max_results - len(records))
            try:
                page = self.search(limit=size, start=start, **kwargs)
            except (SRUError, ET.ParseError) + NETWORK_ERRORS as e:
                if start == 1:
                    raise
                raise IncompleteResults(
                    f"Stopped at record {start} of {max_results}: {e}", records[:max_results]) from e
            records.extend(page["records"])
            start += page["returned"]
            if not page["returned"] or start > page["total"]:
                break
        return records[:max_results]

    def get_record(self, mms_id: str, raw: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch one record by its MMS ID. Returns None if not found."""
        result = self.search(mms_id=str(mms_id), limit=1, raw=raw)
        return result["records"][0] if result["records"] else None

def search_many(libraries: List[str], **kwargs: Any) -> Dict[str, Dict[str, Any]]:
    """
    Run the same search at several libraries. Returns {library: result}.
    A library that fails gets {"error": "..."} instead of stopping the rest.
    """
    results: Dict[str, Dict[str, Any]] = {}
    for key in libraries:
        try:
            results[key] = AlmaSRU(key).search(**kwargs)
        except (SRUError, ET.ParseError) + NETWORK_ERRORS as e:
            results[key] = {"library": key, "error": str(e), "total": 0, "records": []}
    return results


# ── MARC parsing ──

def parse_marc(record: ET.Element) -> Dict[str, Any]:
    """Turn a MARCXML <record> into {"leader", "control": {tag: value}, "fields": [...]}."""
    control: Dict[str, str] = {}
    fields: List[Dict[str, Any]] = []
    for el in record:
        tag = el.get("tag")
        local = el.tag.split("}")[-1]
        if local == "leader":
            control["leader"] = el.text or ""
        elif local == "controlfield" and tag:
            control[tag] = el.text or ""
        elif local == "datafield" and tag:
            subfields = [(sf.get("code", ""), sf.text or "") for sf in el]
            fields.append({
                "tag": tag,
                "ind1": el.get("ind1", " "),
                "ind2": el.get("ind2", " "),
                "subfields": subfields,
            })
    return {"control": control, "fields": fields}


def _fields(marc: Dict[str, Any], *tags: str) -> List[Dict[str, Any]]:
    return [f for f in marc["fields"] if f["tag"] in tags]


def _sub(field: Dict[str, Any], codes: str) -> List[str]:
    return [v for c, v in field["subfields"] if c in codes]


def _text(field: Dict[str, Any], codes: str) -> str:
    """Join subfields and trim the trailing ISBD punctuation ( / : ; , .)."""
    joined = " ".join(v.strip() for v in _sub(field, codes) if v.strip())
    return re.sub(r"\s*[/:;,=]\s*$", "", joined).rstrip(" .") if joined else ""


def _vernacular(marc: Dict[str, Any], field: Dict[str, Any], codes: str) -> str:
    """Find the 880 field linked to this field (via $6) and return its text."""
    links = _sub(field, "6")
    if not links:
        return ""
    occurrence = links[0].split("-", 1)[-1][:2]
    for alt in _fields(marc, "880"):
        link = (_sub(alt, "6") or [""])[0]
        if link.startswith(f"{field['tag']}-{occurrence}"):
            return _text(alt, codes)
    return ""


def _paired(marc: Dict[str, Any], tags: tuple, codes: str) -> List[Dict[str, str]]:
    out = []
    for f in _fields(marc, *tags):
        text = _text(f, codes)
        if not text:
            continue
        item = {"romanized": text}
        vern = _vernacular(marc, f, codes)
        if vern:
            item["vernacular"] = vern
        out.append(item)
    return out


def _display(items: List[Dict[str, str]]) -> str:
    """'九朝紀事本末 = Jiu chao ji shi ben mo' style display, vernacular first."""
    if not items:
        return ""
    first = items[0]
    vern = first.get("vernacular")
    if vern:
        # Some libraries (e.g. NTU) already put the romanized form inside the 880 field
        if _normalize(first["romanized"]) in _normalize(vern):
            return " ".join(vern.split())
        return f"{vern} ({first['romanized']})"
    return first["romanized"]


_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uf900-\ufaff]")


def _normalize(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse spaces (CJK kept)."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def title_matches(record: Dict[str, Any], term: str) -> bool:
    """True if `term` is one connected phrase in a romanized or vernacular title."""
    needle = _normalize(term)
    if not needle:
        return False
    cjk = bool(_CJK.search(needle))
    for title in record.get("titles", []):
        for text in (title.get("romanized", ""), title.get("vernacular", "")):
            hay = _normalize(text)
            if cjk and needle.replace(" ", "") in hay.replace(" ", ""):
                return True
            if not cjk and f" {needle} " in f" {hay} ":
                return True
    return False


def has_known_year(record: Dict[str, Any]) -> bool:
    """True if the summary's year is four digits (not `####`, `19uu`, or blank)."""
    return bool(re.fullmatch(r"\d{4}", record.get("year", "")))


def holdings(marc: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Read Alma availability fields: AVA (print/physical) and AVE (electronic)."""
    physical = []
    for f in _fields(marc, "AVA"):
        get = dict((c, v) for c, v in f["subfields"])
        physical.append({
            "library": get.get("q") or get.get("b", ""),
            "location": get.get("c", ""),
            "call_number": get.get("d", ""),
            "availability": get.get("e", ""),
            "items_total": get.get("f", ""),
            "items_unavailable": get.get("g", ""),
            "summary": get.get("t", ""),
        })
    electronic = []
    for f in _fields(marc, "AVE"):
        get = dict((c, v) for c, v in f["subfields"])
        electronic.append({
            "collection": get.get("m", ""),
            "interface": get.get("t", ""),
            "availability": get.get("e", ""),
            "note": get.get("n", ""),
            "url": get.get("u", ""),
        })
    return {"physical": physical, "electronic": electronic}


# MARC 6XX second indicator -> subject vocabulary (7 = named in $2)
SUBJECT_SOURCES = {"0": "lcsh", "1": "lcshac", "2": "mesh", "3": "nal", "5": "cash", "6": "rvm"}

# MARC 08X fields -> classification scheme (084 names its scheme in $2)
CLASS_TAGS = {"050": "lcc", "060": "nlm", "080": "udc", "082": "ddc", "084": ""}


# Subfields that belong to the main heading (name, dates, title, parts); only
# $v $x $y $z are subdivisions joined with " -- ".
HEADING_CODES = "abcdfgklmnopqrst"
SUBDIVISION_CODES = "vxyz"


def _heading(field: Dict[str, Any]) -> str:
    """'Song, Yingxing, 1587-approximately 1666. Tian gong kai wu -- Criticism' style."""
    main = " ".join(v.strip() for c, v in field["subfields"] if c in HEADING_CODES and v.strip())
    parts = [main.rstrip(" ,.:;")] if main else []
    parts += [v.strip().rstrip(" .") for c, v in field["subfields"] if c in SUBDIVISION_CODES and v.strip()]
    return " -- ".join(p for p in parts if p)


def subject_headings(marc: Dict[str, Any]) -> List[Dict[str, str]]:
    """Subject headings with their vocabulary (lcsh, csht, fast, ...)."""
    out = []
    for f in _fields(marc, "600", "610", "611", "630", "648", "650", "651", "655"):
        heading = _heading(f)
        if not heading:
            continue
        source = SUBJECT_SOURCES.get(f["ind2"]) or next(iter(_sub(f, "2")), "") or "unspecified"
        out.append({"heading": heading, "source": source, "tag": f["tag"]})
    return out


def classifications(marc: Dict[str, Any]) -> List[Dict[str, str]]:
    """Classification numbers with their scheme (lcc, ddc, ncsclt, ...)."""
    out = []
    for f in _fields(marc, *CLASS_TAGS):
        number = _text(f, "ab")
        if number:
            scheme = CLASS_TAGS[f["tag"]] or next(iter(_sub(f, "2")), "") or "other"
            out.append({"scheme": scheme, "number": number})
    return out


def summarize(marc: Dict[str, Any], record_url: str = "") -> Dict[str, Any]:
    """Summarize a parsed MARC record. `record_url` is a template with {mms_id}."""
    ctrl = marc["control"]
    mms_id = ctrl.get("001", "")
    f008 = ctrl.get("008", "")

    titles = _paired(marc, ("245",), "abnp")
    authors = _paired(marc, ("100", "110", "111"), "abcdq")
    contributors = _paired(marc, ("700", "710", "711"), "abcdq")
    publication = _paired(marc, ("264", "260"), "abc")
    edition = _paired(marc, ("250",), "ab")
    series = _paired(marc, ("490", "830"), "av")

    subjects = [h for h in (_heading(f) for f in _fields(marc, "600", "610", "611", "630", "650", "651")) if h]

    oclc = []
    for f in _fields(marc, "035"):
        for v in _sub(f, "a"):
            if "OCoLC" in v:
                oclc.append(re.sub(r"^\(OCoLC\)\D*", "", v))

    return {
        "mms_id": mms_id,
        "title": _display(titles),
        "titles": titles,
        "author": _display(authors),
        "authors": authors,
        "contributors": contributors,
        "edition": _display(edition),
        "publication": _display(publication),
        "year": f008[7:11].strip() if len(f008) >= 11 else "",
        "language": f008[35:38].strip() if len(f008) >= 38 else "",
        "physical_description": next((_text(f, "abc") for f in _fields(marc, "300")), ""),
        "series": [s.get("vernacular") or s["romanized"] for s in series],
        "subjects": list(dict.fromkeys(subjects)),
        "isbns": [v.split()[0] for f in _fields(marc, "020") for v in _sub(f, "a") if v.strip()],
        "oclc": list(dict.fromkeys(oclc)),
        "lccn": [v.strip() for f in _fields(marc, "010") for v in _sub(f, "a")],
        "lc_call_number": next((_text(f, "ab") for f in _fields(marc, "050")), ""),
        "classifications": classifications(marc),
        "subject_headings": subject_headings(marc),
        "holdings": holdings(marc),
        "url": record_url.format(mms_id=mms_id) if record_url and mms_id else "",
    }


# ── CLI ──

def _print_summary(rec: Dict[str, Any]) -> None:
    print(f"{rec['title']}")
    if rec["author"]:
        print(f"  Author: {rec['author']}")
    if rec["publication"] or rec["year"]:
        print(f"  Published: {rec['publication'] or rec['year']}")
    for h in rec["holdings"]["physical"]:
        print(f"  Print: {h['library']} / {h['location']} — {h['call_number']} [{h['availability']}]"
              + (f" {h['summary']}" if h["summary"] else ""))
    for h in rec["holdings"]["electronic"]:
        print(f"  Online: {h['collection'] or h['interface'] or h['note']} [{h['availability']}]"
              + (f" {h['url']}" if h["url"] else ""))
    print(f"  MMS ID: {rec['mms_id']}  {rec['url']}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Search research library catalogs through Alma SRU.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("libraries", help="List the supported libraries")

    s = sub.add_parser("search", help="Search the catalog")
    s.add_argument("--library", required=True, help="Library key, comma list, or 'all' (see: libraries)")
    for name in FIELD_INDEXES:
        s.add_argument(f"--{name.replace('_', '-')}", dest=name)
    s.add_argument("--cql", help="Raw CQL query, e.g. 'alma.title=明史 and alma.main_pub_date<1900'")
    s.add_argument("--sort", choices=sorted(SORT_KEYS))
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--start", type=int, default=1)
    s.add_argument("--phrase", action="store_true", help="Keep only titles containing --title as one connected phrase")
    s.add_argument("--known-dates", action="store_true",
                   help="Drop records whose year is a placeholder such as #### or 19uu")
    s.add_argument("--json", action="store_true", help="Print JSON instead of a short list")

    r = sub.add_parser("record", help="Fetch one record by MMS ID")
    r.add_argument("--library", required=True, help="Library key (see: libraries)")
    r.add_argument("mms_id")
    r.add_argument("--json", action="store_true")
    r.add_argument("--raw", action="store_true", help="Print the full MARC fields as JSON")

    args = parser.parse_args(argv)

    if args.command == "libraries":
        for key, lib in LIBRARIES.items():
            print(f"{key:10} {lib['name']}" + (f"  — {lib['note']}" if lib.get("note") else ""))
        return 0

    if args.command == "search":
        fields = {name: getattr(args, name) for name in FIELD_INDEXES}
        keys = resolve_libraries(args.library)
        results = search_many(keys, cql=args.cql, sort=args.sort, limit=args.limit, start=args.start,
                              phrase=args.phrase, known_dates=args.known_dates, **fields)
        if args.json:
            out = results[keys[0]] if len(keys) == 1 else results
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0
        for key, result in results.items():
            print(f"=== {LIBRARIES[key]['name']} ({key})")
            if "error" in result:
                print(f"  ERROR: {result['error']}\n")
                continue
            shown = result["returned"]
            if args.phrase or args.known_dates:
                print(f"{len(result['records'])} of {shown} records on this page passed the filter")
            if shown:
                print(f"{result['total']} results (showing {args.start}–{args.start + shown - 1})\n")
            else:
                print(f"{result['total']} results\n")
            for rec in result["records"]:
                _print_summary(rec)
                print()
        return 0

    rec = AlmaSRU(resolve_libraries(args.library)[0]).get_record(args.mms_id, raw=args.raw)
    if rec is None:
        print(f"No record found for MMS ID {args.mms_id} at {args.library}", file=sys.stderr)
        return 1
    if args.json or args.raw:
        print(json.dumps(rec, ensure_ascii=False, indent=2))
    else:
        _print_summary(rec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
