"""
Princeton University Library catalog client — zero external dependencies.

Searches Princeton's Alma catalog through its public SRU interface (no API key).
Records come back as MARCXML; this module turns them into simple dicts,
pairs romanized fields with their vernacular (880) versions, and reads the
Alma holdings fields (AVA = print, AVE = online).

Usage as a CLI:
    python princeton_api.py search --title 明史 --language chi --limit 5
    python princeton_api.py search --author "Elman, Benjamin A." --sort date_desc
    python princeton_api.py record 9953348843506421 --json
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

BASE_URL = "https://princeton.alma.exlibrisgroup.com/view/sru/01PRI_INST"
RECORD_URL = "https://catalog.princeton.edu/catalog/{mms_id}"
USER_AGENT = (
    "PrincetonCatalogSkill/1.0 (Claude Code skill; research use; "
    "+https://github.com/kltng/humanities-skills)"
)

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


class PrincetonCatalogAPI:
    """Client for the Princeton University Library catalog (Alma SRU)."""

    def __init__(self, min_interval: float = 1.0):
        self._min_interval = min_interval
        self._last_request = 0.0

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.time()

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
        url = f"{BASE_URL}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"
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
        **fields: Optional[str],
    ) -> Dict[str, Any]:
        """
        Search the catalog. Returns {"total", "start", "query", "records"}.

        Args:
            cql: Raw CQL query (optional; combined with any field arguments)
            sort: date_desc, date_asc, title, or author (default: relevance)
            limit: Records to return (1–50)
            start: 1-based position of the first record
            raw: If True, records are MARC dicts instead of summaries
            phrase: Keep only records whose title contains `title` as one
                    connected phrase (SRU `=` matches the words anywhere).
                    `total` stays the server's count; `returned` is the page
                    size before filtering.
            **fields: keyword, title, author, subject, isbn, issn, oclc, lccn,
                      publisher, series, call_number, language, mms_id
        """
        if phrase and (raw or not fields.get("title")):
            raise ValueError("phrase=True needs a title search and summary records (raw=False)")
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
            records.append(marc if raw else summarize(marc))
        returned = len(records)
        if phrase:
            records = [r for r in records if title_matches(r, fields["title"])]
        return {"total": total, "start": start, "query": query, "returned": returned, "records": records}

    def search_all(self, max_results: int = 100, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Page through results (50 per request) up to max_results.

        If a later page still fails after retries, raises IncompleteResults
        with the records fetched so far in `.records`.
        """
        records: List[Dict[str, Any]] = []
        start = 1
        while len(records) < max_results:
            # with phrase filtering, fetch full pages because some records are dropped
            size = MAX_PAGE_SIZE if kwargs.get("phrase") else min(MAX_PAGE_SIZE, max_results - len(records))
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
    if first.get("vernacular"):
        return f"{first['vernacular']} ({first['romanized']})"
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


def subject_headings(marc: Dict[str, Any]) -> List[Dict[str, str]]:
    """Subject headings with their vocabulary (lcsh, csht, fast, ...)."""
    out = []
    for f in _fields(marc, "600", "610", "611", "630", "648", "650", "651", "655"):
        parts = [v.strip(" .") for c, v in f["subfields"] if c in "abcdtvxyz" and v.strip()]
        if not parts:
            continue
        source = SUBJECT_SOURCES.get(f["ind2"]) or next(iter(_sub(f, "2")), "") or "unspecified"
        out.append({"heading": " -- ".join(parts), "source": source, "tag": f["tag"]})
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


def summarize(marc: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize a parsed MARC record into a clean dict."""
    ctrl = marc["control"]
    mms_id = ctrl.get("001", "")
    f008 = ctrl.get("008", "")

    titles = _paired(marc, ("245",), "abnp")
    authors = _paired(marc, ("100", "110", "111"), "abcdq")
    contributors = _paired(marc, ("700", "710", "711"), "abcdq")
    publication = _paired(marc, ("264", "260"), "abc")
    edition = _paired(marc, ("250",), "ab")
    series = _paired(marc, ("490", "830"), "av")

    subjects = []
    for f in _fields(marc, "600", "610", "611", "630", "650", "651"):
        parts = [v.strip(" .") for c, v in f["subfields"] if c in "abcdtvxyz" and v.strip()]
        if parts:
            subjects.append(" -- ".join(parts))

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
        "url": RECORD_URL.format(mms_id=mms_id) if mms_id else "",
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
    parser = argparse.ArgumentParser(description="Search the Princeton University Library catalog (Alma SRU).")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="Search the catalog")
    for name in FIELD_INDEXES:
        s.add_argument(f"--{name.replace('_', '-')}", dest=name)
    s.add_argument("--cql", help="Raw CQL query, e.g. 'alma.title=明史 and alma.main_pub_date<1900'")
    s.add_argument("--sort", choices=sorted(SORT_KEYS))
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--start", type=int, default=1)
    s.add_argument("--phrase", action="store_true", help="Keep only titles containing --title as one connected phrase")
    s.add_argument("--json", action="store_true", help="Print JSON instead of a short list")

    r = sub.add_parser("record", help="Fetch one record by MMS ID")
    r.add_argument("mms_id")
    r.add_argument("--json", action="store_true")
    r.add_argument("--raw", action="store_true", help="Print the full MARC fields as JSON")

    args = parser.parse_args(argv)
    api = PrincetonCatalogAPI()

    if args.command == "search":
        fields = {name: getattr(args, name) for name in FIELD_INDEXES}
        result = api.search(cql=args.cql, sort=args.sort, limit=args.limit, start=args.start,
                            phrase=args.phrase, **fields)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            shown = result["returned"]
            if args.phrase:
                print(f"{len(result['records'])} of {shown} records on this page contain the phrase")
            if shown:
                print(f"{result['total']} results (showing {args.start}–{args.start + shown - 1})\n")
            else:
                print(f"{result['total']} results")
            for rec in result["records"]:
                _print_summary(rec)
                print()
        return 0

    rec = api.get_record(args.mms_id, raw=args.raw)
    if rec is None:
        print(f"No record found for MMS ID {args.mms_id}", file=sys.stderr)
        return 1
    if args.json or args.raw:
        print(json.dumps(rec, ensure_ascii=False, indent=2))
    else:
        _print_summary(rec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
