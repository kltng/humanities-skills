"""
Northwestern University Libraries Digital Collections client — zero external dependencies.

The Digital Collections API (DC API v2) is Northwestern's official public API
for its digitized images, manuscripts, maps, audio, and video. Search uses
OpenSearch query-string syntax; records include IIIF manifests. No API key
for public items.

Usage as a CLI:
    python northwestern_dc.py search "Yungang" --limit 5
    python northwestern_dc.py search 'subject.label:"China" AND work_type:Image' --sort date_created:asc
    python northwestern_dc.py search --dsl '{"query": {"match": {"title": "Shanghai"}}}'
    python northwestern_dc.py work a84ea83c-bf11-4c4f-89ac-87a951b9ce58
    python northwestern_dc.py collections --limit 20
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

BASE_URL = "https://api.dc.library.northwestern.edu/api/v2"
MCP_URL = "https://api.dc.library.northwestern.edu/api/v2/mcp"
USER_AGENT = (
    "NorthwesternDCSkill/1.0 (Claude Code skill; research use; "
    "+https://github.com/kltng/humanities-skills)"
)

# Attempts per request; waits between them are 5, 10, 20 s (or Retry-After)
MAX_ATTEMPTS = 4
RETRY_HTTP_CODES = (429, 500, 502, 503, 504)
NETWORK_ERRORS = (urllib.error.URLError, ConnectionError, TimeoutError, http.client.HTTPException)

# Large fields not needed for summaries (vector embeddings, ingest bookkeeping)
EXCLUDE_FIELDS = "embedding,embedding_model,embedding_text_length,file_sets,csv_metadata_update_jobs,batch_ids,ingest_sheet,ingest_project"


class NorthwesternDC:
    """Client for the Northwestern Digital Collections API v2."""

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

    def _request(self, path: str, params: Optional[Dict[str, Any]] = None,
                 body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{BASE_URL}{path}"
        if params:
            clean = {k: str(v) for k, v in params.items() if v not in (None, "")}
            url += "?" + urllib.parse.urlencode(clean, quote_via=urllib.parse.quote)
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers)
        for attempt in range(MAX_ATTEMPTS):
            self._rate_limit()
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code not in RETRY_HTTP_CODES or attempt == MAX_ATTEMPTS - 1:
                    raise
                time.sleep(self._retry_after_seconds(e, 5.0 * 2 ** attempt))
            except NETWORK_ERRORS:
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                time.sleep(5.0 * 2 ** attempt)
        raise RuntimeError("unreachable")

    # ── Search ──

    def search(
        self,
        query: Optional[str] = None,
        dsl: Optional[Dict[str, Any]] = None,
        model: str = "works",
        limit: int = 10,
        page: int = 1,
        sort: Optional[str] = None,
        raw: bool = False,
    ) -> Dict[str, Any]:
        """
        Search works (or collections / file-sets). Returns {"total", "page", "records"}.

        Args:
            query: OpenSearch query string, e.g. 'Yungang' or 'work_type:Image AND China'
            dsl: Full OpenSearch query body (sent by POST); overrides `query`
            model: works (default), collections, or file-sets
            limit: Results per page
            page: 1-based page number
            sort: e.g. 'date_created:asc', 'create_date:desc', 'title.keyword:asc'
            raw: Return API records unchanged instead of summaries
        """
        if model not in ("works", "collections", "file-sets"):
            raise ValueError("model must be works, collections, or file-sets")
        if not query and dsl is None:
            raise ValueError("Give a query string or a dsl body")
        params = {"size": max(1, min(limit, 250)), "page": max(1, page), "sort": sort,
                  "_source_excludes": EXCLUDE_FIELDS}
        if dsl is not None:
            data = self._request(f"/search/{model}", params, body=dsl)
        else:
            params["query"] = query
            data = self._request(f"/search/{model}", params)
        records = data.get("data", [])
        summarize_fn = summarize_collection if model == "collections" else summarize_work
        return {
            "total": data.get("pagination", {}).get("total_hits", 0),
            "page": page,
            "records": records if raw else [summarize_fn(r) for r in records],
        }

    def get_work(self, work_id: str, raw: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch one work by its ID (UUID). Returns None if not found."""
        try:
            data = self._request(f"/works/{urllib.parse.quote(work_id, safe='')}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        doc = data.get("data", {})
        return doc if raw else summarize_work(doc)

    def collections(self, limit: int = 50, page: int = 1) -> Dict[str, Any]:
        """List digital collections."""
        data = self._request("/collections", {"size": max(1, min(limit, 250)), "page": page})
        return {
            "total": data.get("pagination", {}).get("total_hits", 0),
            "page": page,
            "records": [summarize_collection(c) for c in data.get("data", [])],
        }


# ── Summarizing ──

def _labels(items: Any, key: str = "label") -> List[str]:
    out = []
    for item in items or []:
        if isinstance(item, dict):
            value = item.get(key) or item.get("label")
        else:
            value = item
        if value:
            out.append(value)
    return list(dict.fromkeys(out))


def summarize_work(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize a DC API work into a clean dict."""
    rights = doc.get("rights_statement") or {}
    collection = doc.get("collection") or {}
    return {
        "id": doc.get("id", ""),
        "title": doc.get("title", ""),
        "alternate_titles": doc.get("alternate_title") or [],
        "work_type": doc.get("work_type", ""),
        "dates": doc.get("date_created") or [],
        "creators": _labels(doc.get("creator"), "label_with_role") + _labels(doc.get("contributor"), "label_with_role"),
        "subjects": _labels(doc.get("subject")),
        "genres": _labels(doc.get("genre")),
        "languages": _labels(doc.get("language")),
        "places": _labels(doc.get("location")),
        "materials": doc.get("physical_description_material") or [],
        "description": doc.get("description") or [],
        "collection": collection.get("title", "") if isinstance(collection, dict) else "",
        "library_unit": doc.get("library_unit", ""),
        "accession_number": doc.get("accession_number", ""),
        "rights": rights.get("label", "") if isinstance(rights, dict) else "",
        "visibility": doc.get("visibility", ""),
        "url": doc.get("canonical_link", ""),
        "iiif_manifest": doc.get("iiif_manifest", ""),
        "thumbnail": doc.get("thumbnail", ""),
    }


def summarize_collection(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize a DC API collection."""
    description = doc.get("description") or ""
    return {
        "id": doc.get("id", ""),
        "title": doc.get("title", ""),
        "description": description[:300],
        "url": doc.get("canonical_link", ""),
        "iiif_manifest": doc.get("iiif_collection") or doc.get("iiif_manifest", ""),
    }


# ── CLI ──

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Search Northwestern University Libraries Digital Collections.")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="Search works")
    s.add_argument("query", nargs="?", help="OpenSearch query string")
    s.add_argument("--dsl", help="Full OpenSearch query body as JSON (overrides query)")
    s.add_argument("--model", choices=("works", "collections", "file-sets"), default="works")
    s.add_argument("--sort")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--page", type=int, default=1)

    w = sub.add_parser("work", help="Fetch one work by ID")
    w.add_argument("work_id")
    w.add_argument("--raw", action="store_true", help="Print the full API record")

    c = sub.add_parser("collections", help="List collections")
    c.add_argument("--limit", type=int, default=50)
    c.add_argument("--page", type=int, default=1)

    args = parser.parse_args(argv)
    api = NorthwesternDC()

    if args.command == "search":
        dsl = json.loads(args.dsl) if args.dsl else None
        result = api.search(args.query, dsl=dsl, model=args.model, limit=args.limit, page=args.page, sort=args.sort)
    elif args.command == "work":
        result = api.get_work(args.work_id, raw=args.raw)
        if result is None:
            print(f"No work found for {args.work_id}", file=sys.stderr)
            return 1
    else:
        result = api.collections(limit=args.limit, page=args.page)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
