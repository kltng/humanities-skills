"""
Library of Congress API client — zero external dependencies.

Searches LOC's digitized collections (books, photos, maps, manuscripts,
newspapers, audio, film/video) and retrieves item details by LCCN/ID.
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Any, Dict, List, Optional

BASE_URL = "https://www.loc.gov"

VALID_FORMATS = {
    "books", "photos", "maps", "audio", "newspapers",
    "manuscripts", "film-and-videos", "notated-music",
}

VALID_FACETS = {
    "subject", "contributor", "location", "language",
    "original-format", "online-format", "partof",
    "digitized", "access-restricted",
}

VALID_SORTS = {
    "date", "date_desc", "title_s", "title_s_desc",
    "shelf_id", "shelf_id_desc",
}


class LocAPI:
    """Client for the Library of Congress loc.gov JSON API."""

    def __init__(self, min_interval: float = 1.0):
        self._min_interval = min_interval
        self._last_request = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.time()

    def _get_json(self, url: str) -> Dict[str, Any]:
        self._rate_limit()
        req = urllib.request.Request(url, headers={
            "User-Agent": "LocCatalogSkill/1.0 (Claude Code skill; research use)",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    # ── Search ──

    def search(
        self,
        q: str = "",
        format: Optional[str] = None,
        facets: Optional[Dict[str, str]] = None,
        dates: Optional[str] = None,
        sort: Optional[str] = None,
        limit: int = 25,
        page: int = 1,
        include_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Search LOC collections. Returns the full API response dict
        with 'results', 'pagination', and 'facets'.

        Args:
            q: Keyword search query
            format: Collection format (books, photos, maps, etc.)
            facets: Dict of facet_name: value (e.g., {"subject": "physics"})
            dates: Date range as "YYYY/YYYY"
            sort: Sort order (date, date_desc, title_s, etc.)
            limit: Results per page (25, 50, 100, 150)
            page: Page number (starts at 1)
            include_all: Include non-digitized items
        """
        if format and format not in VALID_FORMATS:
            raise ValueError(f"Invalid format: {format}. Must be one of {VALID_FORMATS}")

        endpoint = f"/{format}/" if format else "/search/"
        params = {"fo": "json"}

        if q:
            params["q"] = q
        if limit != 25:
            params["c"] = str(limit)
        if page > 1:
            params["sp"] = str(page)
        if dates:
            params["dates"] = dates
        if sort:
            params["sb"] = sort
        if include_all:
            params["all"] = "true"

        if facets:
            fa_parts = []
            for name, value in facets.items():
                if name not in VALID_FACETS:
                    raise ValueError(f"Invalid facet: {name}. Must be one of {VALID_FACETS}")
                fa_parts.append(f"{name}:{value}")
            params["fa"] = "|".join(fa_parts)

        qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote, safe="|:")
        url = f"{BASE_URL}{endpoint}?{qs}"
        return self._get_json(url)

    def search_results(self, **kwargs) -> List[Dict]:
        """Search and return just the results list."""
        data = self.search(**kwargs)
        return data.get("results", [])

    def get_total(self, **kwargs) -> int:
        """Get total number of matching results."""
        kwargs["limit"] = 0
        data = self.search(**kwargs)
        return data.get("pagination", {}).get("of", 0)

    # ── Item Lookup ──

    def get_item(self, item_id: str) -> Optional[Dict]:
        """
        Look up a specific item by LCCN or LOC ID.
        Returns the full API response, or None if not found.
        """
        url = f"{BASE_URL}/item/{item_id}/?fo=json"
        try:
            return self._get_json(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def get_item_detail(self, item_id: str) -> Optional[Dict]:
        """Get just the 'item' sub-object for an item."""
        data = self.get_item(item_id)
        if data:
            return data.get("item", {})
        return None

    # ── Collections ──

    def list_collections(self, limit: int = 25, page: int = 1) -> Dict[str, Any]:
        """List all LOC collections."""
        params = {"fo": "json", "c": str(limit)}
        if page > 1:
            params["sp"] = str(page)
        qs = urllib.parse.urlencode(params)
        url = f"{BASE_URL}/collections/?{qs}"
        return self._get_json(url)

    def browse_collection(self, slug: str, q: str = "", limit: int = 25, page: int = 1) -> Dict[str, Any]:
        """Browse items in a specific collection by slug."""
        params = {"fo": "json", "c": str(limit)}
        if q:
            params["q"] = q
        if page > 1:
            params["sp"] = str(page)
        qs = urllib.parse.urlencode(params)
        url = f"{BASE_URL}/collections/{slug}/?{qs}"
        return self._get_json(url)

    # ── Extraction Helpers ──

    @staticmethod
    def get_title(result: Dict) -> str:
        return result.get("title", "")

    @staticmethod
    def get_date(result: Dict) -> str:
        return result.get("date", "")

    @staticmethod
    def get_contributors(result: Dict) -> List[str]:
        return result.get("contributor", []) or []

    @staticmethod
    def get_subjects(result: Dict) -> List[str]:
        return result.get("subject", []) or []

    @staticmethod
    def get_description(result: Dict) -> List[str]:
        return result.get("description", []) or []

    @staticmethod
    def get_lccn(result: Dict) -> Optional[str]:
        lccns = result.get("number_lccn", [])
        return lccns[0] if lccns else None

    @staticmethod
    def get_image_url(result: Dict) -> Optional[str]:
        urls = result.get("image_url", [])
        return urls[0] if urls else None

    @staticmethod
    def get_item_url(result: Dict) -> str:
        return result.get("url", result.get("id", ""))

    @staticmethod
    def get_citation(item_data: Dict, style: str = "apa") -> str:
        """
        Get a pre-formatted citation from an item detail response.
        style: 'apa', 'chicago', or 'mla'
        """
        cite = item_data.get("cite_this", {})
        return cite.get(style, "")

    def summarize(self, result: Dict) -> Dict[str, Any]:
        """Summarize a search result into a clean dict."""
        return {
            "title": self.get_title(result),
            "date": self.get_date(result),
            "contributors": self.get_contributors(result),
            "subjects": self.get_subjects(result)[:5],
            "lccn": self.get_lccn(result),
            "format": result.get("original_format", []),
            "language": result.get("language", []),
            "digitized": result.get("digitized", False),
            "url": self.get_item_url(result),
            "image_url": self.get_image_url(result),
        }


if __name__ == "__main__":
    loc = LocAPI()

    print("=== Search: hamlet shakespeare ===")
    data = loc.search("hamlet shakespeare", limit=3)
    for r in data.get("results", [])[:3]:
        s = loc.summarize(r)
        print(f"  {s['title']} ({s['date']})")
        print(f"    Contributors: {', '.join(s['contributors'][:2])}")
        print(f"    Format: {s['format']}")
    print(f"  Total results: {data.get('pagination', {}).get('of', '?')}")

    print()
    print("=== Photos: civil war (1860-1865) ===")
    data = loc.search("civil war", format="photos", dates="1860/1865", limit=3)
    for r in data.get("results", [])[:3]:
        print(f"  {r.get('title', '?')} ({r.get('date', '?')})")
    print(f"  Total results: {data.get('pagination', {}).get('of', '?')}")
