"""
LDT@Library (臺灣鏈結資源系統) client — zero external dependencies.

LDT@Library is Taiwan's linked-data service for library authorities, run by
the National Central Library with National Taiwan University Library. It
publishes Chinese name authorities, Chinese subject headings, and the Chinese
classification as MADS/RDF and SKOS. Two public interfaces, no API key:

- OpenRefine reconciliation API: https://ld.ncl.edu.tw/reconcile
- SPARQL endpoint: https://ld.ncl.edu.tw/fuseki/lod/query

Usage as a CLI:
    python ldt_api.py reconcile 王守仁 --type authority
    python ldt_api.py lookup 孔廟
    python ldt_api.py lookup 王守仁 --mode prefix
    python ldt_api.py lookup 王陽明 --mode variant
    python ldt_api.py get https://ld.ncl.edu.tw/authority/114743
    python ldt_api.py sparql 'SELECT ?s WHERE { ?s ?p ?o } LIMIT 3'
"""

import argparse
import email.utils
import http.client
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

BASE_URL = "https://ld.ncl.edu.tw"
RECONCILE_URL = f"{BASE_URL}/reconcile"
SPARQL_URL = f"{BASE_URL}/fuseki/lod/query"
USER_AGENT = (
    "TaiwanLDTSkill/1.0 (Claude Code skill; research use; "
    "+https://github.com/kltng/humanities-skills)"
)

# Attempts per request; waits between them are 5, 10, 20 s (or Retry-After)
MAX_ATTEMPTS = 4
RETRY_HTTP_CODES = (429, 500, 502, 503, 504)
NETWORK_ERRORS = (urllib.error.URLError, ConnectionError, TimeoutError, http.client.HTTPException)

PREFIXES = """PREFIX madsrdf: <http://www.loc.gov/mads/rdf/v1#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX identifiers: <http://id.loc.gov/vocabulary/identifiers/>
PREFIX bflc: <http://id.loc.gov/ontologies/bflc/>
"""

# Reconciliation types: authority = personal names; topic = subject headings;
# classification = Chinese classification. Sub-types narrow personal names.
RECONCILE_TYPES = (
    "authority", "authority>name", "authority>prefname", "authority>altname",
    "authority>note", "topic", "classification",
)

# rdf:type values that are only markers, not the kind of record
GENERIC_TYPES = {"Authority", "Concept"}


class LDTError(RuntimeError):
    """The service returned an error or an unreadable answer."""


class LDTAPI:
    """Client for LDT@Library reconciliation and SPARQL."""

    def __init__(self, min_interval: float = 1.0, timeout: int = 90):
        self._min_interval = min_interval
        self._timeout = timeout
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

    def _post(self, url: str, form: Dict[str, str], accept: str) -> Any:
        body = urllib.parse.urlencode(form).encode()
        req = urllib.request.Request(url, data=body, headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        for attempt in range(MAX_ATTEMPTS):
            self._rate_limit()
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    raw = resp.read()
                break
            except urllib.error.HTTPError as e:
                if e.code not in RETRY_HTTP_CODES or attempt == MAX_ATTEMPTS - 1:
                    raise
                time.sleep(self._retry_after_seconds(e, 5.0 * 2 ** attempt))
            except NETWORK_ERRORS:
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                time.sleep(5.0 * 2 ** attempt)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise LDTError(f"Unreadable answer from {url}: {raw[:200]!r}") from e

    # ── Reconciliation ──

    def reconcile(self, query: str, type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Match a name or heading with the OpenRefine reconciliation API.

        Ranking is loose: the right record is often in the list but not first
        (王守仁 ranks a scholar who wrote about him above him). Check `name`.
        """
        if type and type not in RECONCILE_TYPES:
            raise ValueError(f"Unknown type: {type}. Use one of {RECONCILE_TYPES}")
        q: Dict[str, Any] = {"query": query, "limit": max(1, min(limit, 50))}
        if type:
            q["type"] = type
        data = self._post(RECONCILE_URL, {"queries": json.dumps({"q0": q}, ensure_ascii=False)}, "application/json")
        out = []
        for r in data.get("q0", {}).get("result", []):
            out.append({
                "uri": BASE_URL + r["id"] if r.get("id", "").startswith("/") else r.get("id", ""),
                "name": r.get("name", ""),
                "score": r.get("score"),
                "match": r.get("match", False),
                "type": (r.get("type") or [{}])[0].get("name", ""),
            })
        # the service can list the same record twice
        seen, unique = set(), []
        for r in out:
            if r["uri"] not in seen:
                seen.add(r["uri"])
                unique.append(r)
        return unique

    # ── SPARQL ──

    def sparql(self, query: str) -> List[Dict[str, str]]:
        """Run a SPARQL SELECT. Returns rows as {variable: value}. PREFIXES are added."""
        if "PREFIX madsrdf:" not in query:
            query = PREFIXES + query
        data = self._post(SPARQL_URL, {"query": query}, "application/sparql-results+json")
        return [{k: v.get("value", "") for k, v in b.items()} for b in data.get("results", {}).get("bindings", [])]

    @staticmethod
    def literal(text: str) -> str:
        """Quote text as a SPARQL string literal."""
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'

    def lookup(self, label: str, mode: str = "exact", limit: int = 20) -> List[Dict[str, Any]]:
        """
        Find authority records by label.

        Args:
            label: Name, heading, or class caption, e.g. 孔廟, 王守仁, 王陽明
            mode: exact (preferred label, fast), prefix (preferred label
                  starts with, ~1-2 s), variant (variant names start with,
                  slow: ~15 s)
            limit: Maximum records
        """
        lit = self.literal(label)
        limit = max(1, min(limit, 200))
        if mode == "exact":
            # labels are stored with a language tag (often @en even for Chinese);
            # matching the literal directly is much faster than FILTER(STR(...))
            values = f"{lit}@en {lit}@zh {lit}"
            where = f"""{{ VALUES ?label {{ {values} }} ?s madsrdf:authoritativeLabel ?label }}
                UNION {{ VALUES ?label {{ {values} }} ?s skos:prefLabel ?label }}"""
        elif mode == "prefix":
            where = f"""{{ ?s madsrdf:authoritativeLabel ?label }} UNION {{ ?s skos:prefLabel ?label }}
                FILTER(STRSTARTS(STR(?label), {lit}))"""
        elif mode == "variant":
            where = f"""?s madsrdf:hasVariant/madsrdf:variantLabel ?variant .
                FILTER(STRSTARTS(STR(?variant), {lit}))
                ?s madsrdf:authoritativeLabel ?label"""
        else:
            raise ValueError("mode must be exact, prefix, or variant")
        rows = self.sparql(f"""SELECT DISTINCT ?s ?label ?type WHERE {{
            {where}
            OPTIONAL {{ ?s rdf:type ?type }}
        }} LIMIT {limit * 4}""")
        found: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            rec = found.setdefault(row["s"], {"uri": row["s"], "label": row["label"], "kind": ""})
            kind = _local(row.get("type", ""))
            if kind and kind not in GENERIC_TYPES:
                rec["kind"] = kind
        for rec in found.values():
            if not rec["kind"] and "/classification/" in rec["uri"]:
                rec["kind"] = "Classification"
        return list(found.values())[:limit]

    def get(self, uri: str) -> Dict[str, Any]:
        """Fetch one record: label, kind, variants, sources, notes, related headings."""
        if not uri.startswith("http"):
            uri = f"{BASE_URL}/{uri.lstrip('/')}"
        s = f"<{uri}>"
        props = self.sparql(f"SELECT ?p ?o WHERE {{ {s} ?p ?o . FILTER(!isBlank(?o)) }}")
        variants = self.sparql(f"SELECT ?v WHERE {{ {s} madsrdf:hasVariant/madsrdf:variantLabel ?v }}")
        sources = self.sparql(f"""SELECT ?source ?note ?status WHERE {{ {s} madsrdf:hasSource ?src .
            OPTIONAL {{ ?src madsrdf:citationSource ?source }} OPTIONAL {{ ?src madsrdf:citationNote ?note }}
            OPTIONAL {{ ?src madsrdf:citationStatus ?status }} }}""")
        related = self.sparql(f"""SELECT ?r ?label ?rel WHERE {{
            VALUES ?rel {{ madsrdf:hasReciprocalAuthority madsrdf:hasBroaderAuthority madsrdf:hasNarrowerAuthority
                          skos:broader skos:narrower skos:related }}
            {s} ?rel ?r . OPTIONAL {{ ?r madsrdf:authoritativeLabel ?label }} OPTIONAL {{ ?r skos:prefLabel ?label }} }}""")
        return summarize(uri, props, variants, sources, related)


# ── Summarizing ──

def _local(uri: str) -> str:
    return uri.rstrip("/").rsplit("#", 1)[-1].rsplit("/", 1)[-1] if uri else ""


def summarize(uri: str, props: List[Dict[str, str]], variants: List[Dict[str, str]],
              sources: List[Dict[str, str]], related: List[Dict[str, str]]) -> Dict[str, Any]:
    """Turn SPARQL rows for one record into a clean dict."""
    by_prop: Dict[str, List[str]] = {}
    for row in props:
        by_prop.setdefault(_local(row["p"]), []).append(row["o"])
    kinds = [_local(t) for t in by_prop.get("type", []) if _local(t) not in GENERIC_TYPES]
    label = (by_prop.get("authoritativeLabel") or by_prop.get("prefLabel") or [""])[0]
    return {
        "uri": uri,
        "label": label,
        "kind": kinds[0] if kinds else ("Classification" if "/classification/" in uri else ""),
        "variants": list(dict.fromkeys(v["v"] for v in variants if v.get("v"))),
        "sources": [
            {k: row[k] for k in ("source", "note", "status") if row.get(k)} for row in sources
        ],
        "notes": by_prop.get("note", []) + by_prop.get("historyNote", []),
        "notation": (by_prop.get("notation") or [""])[0],
        "local_id": [v for v in by_prop.get("local", []) if v],
        "lccn": [v for v in by_prop.get("lccn", []) if v],
        "marc_key": (by_prop.get("marcKey") or [""])[0],
        "related": [
            # related headings are often blank nodes: keep the label, drop the node id
            {"relation": _local(r.get("rel", "")), "uri": r["r"] if r["r"].startswith("http") else "",
             "label": r.get("label", "")}
            for r in related
        ],
        "url": uri,
    }


# ── CLI ──

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Search Taiwan's LDT@Library authorities (names, subjects, classification).")
    sub = parser.add_subparsers(dest="command", required=True)

    r = sub.add_parser("reconcile", help="Ranked matches from the reconciliation API")
    r.add_argument("query")
    r.add_argument("--type", choices=RECONCILE_TYPES)
    r.add_argument("--limit", type=int, default=10)

    lk = sub.add_parser("lookup", help="Find records by label through SPARQL")
    lk.add_argument("label")
    lk.add_argument("--mode", choices=("exact", "prefix", "variant"), default="exact")
    lk.add_argument("--limit", type=int, default=20)

    g = sub.add_parser("get", help="Full record by URI")
    g.add_argument("uri")

    sq = sub.add_parser("sparql", help="Run a raw SPARQL SELECT (prefixes added)")
    sq.add_argument("query")

    args = parser.parse_args(argv)
    api = LDTAPI()
    if args.command == "reconcile":
        result: Any = api.reconcile(args.query, type=args.type, limit=args.limit)
    elif args.command == "lookup":
        result = api.lookup(args.label, mode=args.mode, limit=args.limit)
    elif args.command == "get":
        result = api.get(args.uri)
    else:
        result = api.sparql(args.query)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
