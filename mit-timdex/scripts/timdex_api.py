"""
MIT Libraries TIMDEX client — zero external dependencies.

TIMDEX is MIT Libraries' official, public GraphQL discovery API. One index
covers the MIT library catalog (Alma), DSpace@MIT, MIT ArchivesSpace, MIT
digital collections, GIS data, research databases, LibGuides, and the
library website. No API key.

Usage as a CLI:
    python timdex_api.py search 明史 --limit 5
    python timdex_api.py search --title "Ming shi" --source "MIT Alma" --language chinese
    python timdex_api.py search "Ming dynasty painting" --mode semantic
    python timdex_api.py search --subjects "China History" --facets
    python timdex_api.py record alma:9936111333206761
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
import urllib.request
from typing import Any, Dict, List, Optional

ENDPOINT = "https://timdex.mit.edu/graphql"
USER_AGENT = (
    "MitTimdexSkill/1.0 (Claude Code skill; research use; "
    "+https://github.com/kltng/humanities-skills)"
)

# Attempts per request; waits between them are 5, 10, 20 s (or Retry-After)
MAX_ATTEMPTS = 4
RETRY_HTTP_CODES = (429, 500, 502, 503, 504)
NETWORK_ERRORS = (urllib.error.URLError, ConnectionError, TimeoutError, http.client.HTTPException)

# Search arguments accepted by TIMDEX's `search` query (friendly name -> GraphQL arg)
SEARCH_FIELDS = {
    "searchterm": "searchterm",
    "title": "title",
    "contributors": "contributors",
    "subjects": "subjects",
    "identifiers": "identifiers",
    "locations": "locations",
    "citation": "citation",
}

FILTERS = {
    "source": "sourceFilter",
    "content_type": "contentTypeFilter",
    "language": "languagesFilter",
    "format": "formatFilter",
    "subject_filter": "subjectsFilter",
    "contributor_filter": "contributorsFilter",
    "place": "placesFilter",
    "literary_form": "literaryFormFilter",
    "access": "accessToFilesFilter",
}

SOURCES = (
    "MIT Alma", "DSpace@MIT", "MIT ArchivesSpace", "Digital Collections",
    "MIT GIS Resources", "Research Databases", "LibGuides", "MIT Libraries Website",
)

RECORD_FIELDS = """
  timdexRecordId title source sourceLink contentType format languages
  callNumbers edition summary physicalDescription citation
  alternateTitles { kind value }
  contributors { kind value }
  dates { kind value }
  identifiers { kind value }
  subjects { kind value }
  publishers { name date location }
  holdings { location collection callnumber format summary }
  links { kind url text }
  notes { kind value }
"""

AGGREGATIONS = """
  aggregations {
    source { key docCount }
    contentType { key docCount }
    languages { key docCount }
    format { key docCount }
    subjects { key docCount }
  }
"""


class TimdexError(RuntimeError):
    """TIMDEX returned GraphQL errors."""


class TimdexAPI:
    """Client for MIT Libraries' TIMDEX GraphQL API."""

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

    def query(self, graphql: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run a raw GraphQL query and return its `data`."""
        body = json.dumps({"query": graphql, "variables": variables or {}}).encode()
        req = urllib.request.Request(ENDPOINT, data=body, headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        for attempt in range(MAX_ATTEMPTS):
            self._rate_limit()
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    payload = json.loads(resp.read())
                break
            except urllib.error.HTTPError as e:
                if e.code not in RETRY_HTTP_CODES or attempt == MAX_ATTEMPTS - 1:
                    raise
                time.sleep(self._retry_after_seconds(e, 5.0 * 2 ** attempt))
            except NETWORK_ERRORS:
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                time.sleep(5.0 * 2 ** attempt)
        if payload.get("errors"):
            raise TimdexError("; ".join(err.get("message", "") for err in payload["errors"]))
        return payload.get("data") or {}

    # ── Search ──

    @staticmethod
    def build_search_args(
        fields: Dict[str, Optional[str]],
        filters: Dict[str, Optional[str]],
        mode: Optional[str] = None,
        boolean: Optional[str] = None,
        start: int = 0,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Map friendly names to TIMDEX GraphQL arguments, dropping empty ones."""
        args: Dict[str, Any] = {}
        for name, value in fields.items():
            if value:
                if name not in SEARCH_FIELDS:
                    raise ValueError(f"Unknown search field: {name}. Use one of {sorted(SEARCH_FIELDS)}")
                args[SEARCH_FIELDS[name]] = value
        if not args:
            raise ValueError("Give search words or at least one search field")
        for name, value in filters.items():
            if value:
                if name not in FILTERS:
                    raise ValueError(f"Unknown filter: {name}. Use one of {sorted(FILTERS)}")
                args[FILTERS[name]] = value
        if mode:
            if mode not in ("keyword", "semantic", "hybrid"):
                raise ValueError("mode must be keyword, semantic, or hybrid")
            args["queryMode"] = mode
        if boolean:
            if boolean.upper() not in ("AND", "OR"):
                raise ValueError("boolean must be AND or OR")
            args["booleanType"] = boolean.upper()
        args["from"] = str(max(0, start))
        args["perPage"] = max(1, min(limit, 100))
        return args

    def search(
        self,
        searchterm: Optional[str] = None,
        mode: Optional[str] = None,
        boolean: Optional[str] = None,
        start: int = 0,
        limit: int = 20,
        facets: bool = False,
        raw: bool = False,
        phrase: bool = False,
        **kwargs: Optional[str],
    ) -> Dict[str, Any]:
        """
        Search TIMDEX. Returns {"total", "start", "returned", "records", "facets"?}.

        Args:
            searchterm: Words searched across all fields
            mode: keyword (default), semantic (vector), or hybrid
            boolean: OR (default: any word) or AND (all words). Applies to
                     `searchterm` only; field searches (title, subjects) ignore it.
            start: 0-based offset of the first record
            limit: Records per page (TIMDEX default 20)
            facets: Also return counts by source, content type, language, format, subject
            raw: Return TIMDEX records unchanged instead of summaries
            phrase: Keep only records whose title or alternate titles contain
                    the search text (`title`, else `searchterm`) as one connected
                    phrase. `total` stays the server's count; `returned` is the
                    page size before filtering.
            **kwargs: Search fields (title, contributors, subjects, identifiers,
                      locations, citation) and filters (source, content_type,
                      language, format, subject_filter, contributor_filter,
                      place, literary_form, access)
        """
        phrase_text = kwargs.get("title") or searchterm
        if phrase and (raw or not phrase_text):
            raise ValueError("phrase=True needs title or searchterm, and summary records (raw=False)")
        fields = {"searchterm": searchterm}
        filters = {}
        for name, value in kwargs.items():
            (fields if name in SEARCH_FIELDS else filters)[name] = value
        args = self.build_search_args(fields, filters, mode, boolean, start, limit)
        arg_text = ", ".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in args.items())
        graphql = f"{{ search({arg_text}) {{ hits {AGGREGATIONS if facets else ''} records {{ {RECORD_FIELDS} }} }} }}"
        data = self.query(graphql)["search"]
        records = data.get("records") or []
        summaries = records if raw else [summarize(r) for r in records]
        if phrase:
            summaries = [r for r in summaries if title_matches(r, phrase_text)]
        result: Dict[str, Any] = {
            "total": data.get("hits", 0),
            "start": start,
            "returned": len(records),
            "records": summaries,
        }
        if facets:
            result["facets"] = {
                name: [(b["key"], b["docCount"]) for b in (buckets or [])]
                for name, buckets in (data.get("aggregations") or {}).items()
            }
        return result

    def get_record(self, record_id: str, raw: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch one record by its TIMDEX ID (e.g. 'alma:9936111333206761')."""
        try:
            data = self.query(f"{{ recordId(id: {json.dumps(record_id)}) {{ {RECORD_FIELDS} }} }}")
        except TimdexError as e:
            if "not found" in str(e).lower():
                return None
            raise
        rec = data.get("recordId")
        if rec is None:
            return None
        return rec if raw else summarize(rec)


# ── Phrase matching ──

_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uf900-\ufaff]")


def _normalize(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse spaces (CJK kept)."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def title_matches(record: Dict[str, Any], term: str) -> bool:
    """True if `term` is one connected phrase in the title or an alternate title."""
    needle = _normalize(term)
    if not needle:
        return False
    cjk = bool(_CJK.search(needle))
    for text in [record.get("title") or ""] + list(record.get("alternate_titles") or []):
        hay = _normalize(text)
        if cjk and needle.replace(" ", "") in hay.replace(" ", ""):
            return True
        if not cjk and f" {needle} " in f" {hay} ":
            return True
    return False


# ── Summarizing ──

def _values(items: Any, kind: Optional[str] = None) -> List[str]:
    out = []
    for item in items or []:
        if kind and (item.get("kind") or "").lower() != kind.lower():
            continue
        value = item.get("value")
        if isinstance(value, list):
            out.extend(v for v in value if v)
        elif value:
            out.append(value)
    return list(dict.fromkeys(out))


def summarize(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize a TIMDEX record into a clean dict."""
    identifiers: Dict[str, List[str]] = {}
    for ident in rec.get("identifiers") or []:
        identifiers.setdefault(ident.get("kind") or "Other", []).append(ident.get("value", ""))

    publishers = []
    for pub in rec.get("publishers") or []:
        parts = [p for p in (pub.get("location"), pub.get("name"), pub.get("date")) if p]
        if parts:
            publishers.append(", ".join(parts))

    return {
        "id": rec.get("timdexRecordId", ""),
        "title": rec.get("title", ""),
        "alternate_titles": _values(rec.get("alternateTitles")),
        "source": rec.get("source", ""),
        "content_type": rec.get("contentType") or [],
        "format": rec.get("format") or [],
        "languages": rec.get("languages") or [],
        "contributors": _values(rec.get("contributors")),
        "dates": _values(rec.get("dates")),
        "publishers": publishers,
        "edition": rec.get("edition") or "",
        "physical_description": rec.get("physicalDescription") or "",
        "summary": rec.get("summary") or [],
        "subjects": _values(rec.get("subjects")),
        "identifiers": identifiers,
        "call_numbers": rec.get("callNumbers") or [],
        "holdings": [
            {k: h.get(k) for k in ("location", "collection", "callnumber", "format", "summary") if h.get(k)}
            for h in rec.get("holdings") or []
        ],
        "links": [{"kind": l.get("kind"), "url": l.get("url"), "text": l.get("text")} for l in rec.get("links") or []],
        "citation": rec.get("citation") or "",
        "url": rec.get("sourceLink") or "",
    }


# ── CLI ──

def _print_summary(rec: Dict[str, Any]) -> None:
    print(rec["title"])
    if rec["contributors"]:
        print(f"  By: {'; '.join(rec['contributors'][:3])}")
    if rec["publishers"] or rec["dates"]:
        print(f"  Published: {'; '.join(rec['publishers'][:1]) or ', '.join(rec['dates'][:1])}")
    print(f"  Source: {rec['source']}  Type: {', '.join(rec['content_type'])}")
    for h in rec["holdings"][:3]:
        where = h.get("collection") or h.get("location", "")
        print(f"  Holding: {where}" + (f" — {h['callnumber']}" if h.get("callnumber") else ""))
    print(f"  ID: {rec['id']}  {rec['url']}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Search MIT Libraries through the TIMDEX GraphQL API.")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="Search TIMDEX")
    s.add_argument("searchterm", nargs="?", help="Words searched across all fields")
    for name in SEARCH_FIELDS:
        if name != "searchterm":
            s.add_argument(f"--{name}")
    for name in FILTERS:
        s.add_argument(f"--{name.replace('_', '-')}", dest=name,
                       help=f"Filter ({FILTERS[name]})" + ("; one of: " + ", ".join(SOURCES) if name == "source" else ""))
    s.add_argument("--mode", choices=("keyword", "semantic", "hybrid"))
    s.add_argument("--boolean", choices=("AND", "OR"))
    s.add_argument("--start", type=int, default=0)
    s.add_argument("--limit", type=int, default=20, help="Records per page (default 20, max 100)")
    s.add_argument("--facets", action="store_true", help="Show counts by source, type, language, format, subject")
    s.add_argument("--phrase", action="store_true", help="Keep only titles containing the search text as one phrase")
    s.add_argument("--json", action="store_true")

    r = sub.add_parser("record", help="Fetch one record by TIMDEX ID")
    r.add_argument("record_id")
    r.add_argument("--raw", action="store_true", help="Print the TIMDEX record unchanged")

    args = parser.parse_args(argv)
    api = TimdexAPI()

    if args.command == "search":
        extra = {n: getattr(args, n) for n in list(SEARCH_FIELDS)[1:] + list(FILTERS)}
        try:
            result = api.search(args.searchterm, mode=args.mode, boolean=args.boolean, start=args.start,
                                limit=args.limit, facets=args.facets, phrase=args.phrase, **extra)
        except ValueError as e:
            parser.error(str(e))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        print(f"{result['total']} results\n")
        if args.phrase:
            print(f"{len(result['records'])} of {result['returned']} records on this page contain the phrase\n")
        for name, buckets in result.get("facets", {}).items():
            print(f"  {name}: " + ", ".join(f"{k} ({n})" for k, n in buckets[:8]))
        if result.get("facets"):
            print()
        for rec in result["records"]:
            _print_summary(rec)
            print()
        return 0

    rec = api.get_record(args.record_id, raw=args.raw)
    if rec is None:
        print(f"No record found for {args.record_id}", file=sys.stderr)
        return 1
    print(json.dumps(rec, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
