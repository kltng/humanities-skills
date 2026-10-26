"""
Yale LUX client — zero external dependencies.

LUX (https://lux.collections.yale.edu) searches across Yale's libraries,
museums, and archives. Its public API returns Linked Art JSON-LD. A search
returns only entity URIs; this module fetches each entity and summarizes it.

Usage as a CLI:
    python lux_api.py search "明史" --scope work --limit 5
    python lux_api.py search "Wang, Yangming" --scope agent --field name
    python lux_api.py search --query '{"AND":[{"text":"Ming"},{"producedBy":{"name":"Wen Zhengming"}}]}'
    python lux_api.py get https://lux.collections.yale.edu/data/person/762fbf1b-f30f-4b23-a882-6664ebc0cc06
"""

import argparse
import email.utils
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

BASE_URL = "https://lux.collections.yale.edu"
USER_AGENT = (
    "YaleLuxSkill/1.0 (Claude Code skill; research use; "
    "+https://github.com/kltng/humanities-skills)"
)

# item = physical/digital objects, work = texts/images/works, agent = people
# and groups, place, concept, event, set = collections/archives
SCOPES = ("item", "work", "agent", "place", "concept", "event", "set")


class LuxAPI:
    """Client for the Yale LUX search API."""

    def __init__(self, min_interval: float = 0.5):
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

    def _get_json(self, url: str) -> Dict[str, Any]:
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })
        for attempt in range(3):
            self._rate_limit()
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code not in (429, 503) or attempt == 2:
                    raise
                time.sleep(self._retry_after_seconds(e, 5.0 * (attempt + 1)))
        raise RuntimeError("unreachable")

    # ── Search ──

    @staticmethod
    def build_query(text: Optional[str] = None, field: str = "text",
                    query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build a LUX JSON query: either {field: text} or a raw query dict."""
        if query is not None:
            return query
        if not text:
            raise ValueError("Give search text or a raw query")
        return {field: text}

    def search(
        self,
        text: Optional[str] = None,
        scope: str = "item",
        field: str = "text",
        query: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        page: int = 1,
        details: bool = True,
    ) -> Dict[str, Any]:
        """
        Search LUX. Returns {"total", "page", "query", "results"}.

        Args:
            text: Search words (matched against `field`)
            scope: item, work, agent, place, concept, event, or set
            field: Search term for `text`, e.g. text (anywhere), name, identifier
            query: Raw LUX JSON query (overrides text/field)
            limit: Results per page (LUX allows up to 100)
            page: 1-based page number
            details: Fetch and summarize each result (one extra request each)
        """
        if scope not in SCOPES:
            raise ValueError(f"Unknown scope: {scope}. Use one of {SCOPES}")
        q = self.build_query(text, field, query)
        params = urllib.parse.urlencode({
            "q": json.dumps(q, ensure_ascii=False),
            "page": str(page),
            "pageLength": str(max(1, min(limit, 100))),
        }, quote_via=urllib.parse.quote)
        data = self._get_json(f"{BASE_URL}/api/search/{scope}?{params}")
        total = 0
        for part in data.get("partOf", []):
            total = part.get("totalItems", total)
        items = data.get("orderedItems", [])
        if details:
            results = [summarize(self._get_json(i["id"])) for i in items]
        else:
            results = [{"id": i["id"], "type": i.get("type", "")} for i in items]
        return {"total": total, "page": page, "query": q, "results": results}

    def get(self, uri: str, raw: bool = False) -> Dict[str, Any]:
        """Fetch one LUX entity by URI (or by 'person/<uuid>' style path)."""
        if not uri.startswith("http"):
            uri = f"{BASE_URL}/data/{uri.lstrip('/')}"
        doc = self._get_json(uri)
        return doc if raw else summarize(doc)


# ── Linked Art summarizing ──

def _labels(values: Any) -> List[str]:
    return [v.get("_label", "") for v in values or [] if isinstance(v, dict) and v.get("_label")]


def _timespan(event: Any) -> str:
    """Return 'begin – end' from an event's timespan, or its display label."""
    if not isinstance(event, dict):
        return ""
    ts = event.get("timespan") or {}
    for name in ts.get("identified_by", []):
        if name.get("content"):
            return name["content"]
    begin = (ts.get("begin_of_the_begin") or "")[:10]
    end = (ts.get("end_of_the_end") or "")[:10]
    if begin or end:
        return f"{begin} – {end}" if begin != end else begin
    return ""


def _catalog_links(doc: Dict[str, Any]) -> List[str]:
    """Collect web pages for this entity (e.g. its Yale catalog record)."""
    links = []
    for subj in doc.get("subject_of", []):
        for carrier in subj.get("digitally_carried_by", []):
            for ap in carrier.get("access_point", []):
                if ap.get("id"):
                    links.append(ap["id"])
    return list(dict.fromkeys(links))


def summarize(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize a Linked Art document into a clean dict."""
    names, identifiers = [], []
    for ident in doc.get("identified_by", []):
        content = ident.get("content", "")
        if not content:
            continue
        (identifiers if ident.get("type") == "Identifier" else names).append(content)

    notes = []
    for ref in doc.get("referred_to_by", []):
        content = (ref.get("content") or "").strip()
        if content:
            kind = ", ".join(_labels(ref.get("classified_as")))
            notes.append(f"{kind}: {content}" if kind else content)

    dates = {}
    for key in ("born", "died", "formed_by", "dissolved_by", "produced_by", "created_by", "timespan"):
        value = doc.get(key)
        span = _timespan(value) if key != "timespan" else _timespan({"timespan": value})
        if span:
            dates[key] = span

    makers = []
    for key in ("produced_by", "created_by"):
        event = doc.get(key) or {}
        for part in [event] + event.get("part", []):
            makers.extend(_labels(part.get("carried_out_by")))

    return {
        "id": doc.get("id", ""),
        "type": doc.get("type", ""),
        "label": doc.get("_label", ""),
        "names": list(dict.fromkeys(names)),
        "identifiers": list(dict.fromkeys(identifiers)),
        "classified_as": _labels(doc.get("classified_as")),
        "languages": _labels(doc.get("language")),
        "makers": list(dict.fromkeys(makers)),
        "dates": dates,
        "member_of": _labels(doc.get("member_of")),
        "notes": notes[:5],
        "equivalent": [e["id"] for e in doc.get("equivalent", []) if e.get("id")],
        "links": _catalog_links(doc),
    }


# ── CLI ──

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Search Yale LUX (libraries, museums, archives).")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="Search LUX")
    s.add_argument("text", nargs="?", help="Search words")
    s.add_argument("--scope", choices=SCOPES, default="item")
    s.add_argument("--field", default="text", help="Search term for the text: text, name, identifier, ...")
    s.add_argument("--query", help="Raw LUX JSON query, e.g. '{\"name\":\"王守仁\"}'")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--page", type=int, default=1)
    s.add_argument("--ids-only", action="store_true", help="Skip fetching each result")

    g = sub.add_parser("get", help="Fetch one entity by URI")
    g.add_argument("uri")
    g.add_argument("--raw", action="store_true", help="Print the full Linked Art JSON")

    args = parser.parse_args(argv)
    api = LuxAPI()

    if args.command == "search":
        query = json.loads(args.query) if args.query else None
        result = api.search(text=args.text, scope=args.scope, field=args.field, query=query,
                            limit=args.limit, page=args.page, details=not args.ids_only)
    else:
        result = api.get(args.uri, raw=args.raw)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
