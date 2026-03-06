"""
Columbia University CLIO catalog API client — zero external dependencies.

Searches Columbia's Blacklight-based library catalog for books, journals,
manuscripts, and other holdings. Uses the undocumented JSON API.
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Any, Dict, List, Optional

BASE_URL = "https://clio.columbia.edu/catalog"

VALID_SEARCH_FIELDS = {"title", "author"}

VALID_FACETS = {
    "format", "language_facet", "location_facet",
    "subject_topic_facet", "subject_geo_facet",
    "subject_era_facet", "subject_form_facet",
    "author_facet", "pub_date_sort",
}


class ColumbiaClioAPI:
    """Client for Columbia University's CLIO catalog (Blacklight JSON API)."""

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
            "User-Agent": "ColumbiaClioSkill/1.0 (Claude Code skill; research use)",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    # ── Search ──

    def search(
        self,
        q: str = "",
        search_field: Optional[str] = None,
        facets: Optional[Dict[str, str]] = None,
        sort: Optional[str] = None,
        per_page: int = 10,
        page: int = 1,
    ) -> List[Dict]:
        """
        Search CLIO catalog. Returns list of document dicts.

        Args:
            q: Search query
            search_field: Limit to 'title' or 'author' (None for all fields)
            facets: Dict of facet_name: value (e.g., {"format": "Book"})
            sort: Sort string (e.g., "pub_date_sort desc")
            per_page: Results per page
            page: Page number
        """
        params = {"q": q, "per_page": str(per_page)}
        if page > 1:
            params["page"] = str(page)
        if search_field:
            if search_field not in VALID_SEARCH_FIELDS:
                raise ValueError(f"Invalid search_field: {search_field}. Use 'title' or 'author'")
            params["search_field"] = search_field
        if sort:
            params["sort"] = sort

        # Build URL manually to handle facet array params
        qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

        if facets:
            for name, value in facets.items():
                if name not in VALID_FACETS:
                    raise ValueError(f"Invalid facet: {name}. Must be one of {VALID_FACETS}")
                encoded_val = urllib.parse.quote(str(value))
                qs += f"&f[{name}][]={encoded_val}"

        url = f"{BASE_URL}.json?{qs}"
        data = self._get_json(url)
        return data.get("response", {}).get("docs", [])

    def search_with_pagination(
        self, q: str = "", **kwargs
    ) -> Dict[str, Any]:
        """
        Search and return full response with docs, facets, and pagination.
        """
        params = {"q": q, "per_page": str(kwargs.get("per_page", 10))}
        page = kwargs.get("page", 1)
        if page > 1:
            params["page"] = str(page)
        search_field = kwargs.get("search_field")
        if search_field:
            params["search_field"] = search_field
        sort = kwargs.get("sort")
        if sort:
            params["sort"] = sort

        qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

        facets = kwargs.get("facets")
        if facets:
            for name, value in facets.items():
                encoded_val = urllib.parse.quote(str(value))
                qs += f"&f[{name}][]={encoded_val}"

        url = f"{BASE_URL}.json?{qs}"
        data = self._get_json(url)
        resp = data.get("response", {})
        return {
            "docs": resp.get("docs", []),
            "pages": resp.get("pages", {}),
            "facets": resp.get("facets", []),
        }

    def search_all(self, q: str = "", max_results: int = 100, **kwargs) -> List[Dict]:
        """Paginate through results up to max_results."""
        all_docs = []
        per_page = min(25, max_results)
        page = 1

        while len(all_docs) < max_results:
            docs = self.search(q=q, per_page=per_page, page=page, **kwargs)
            if not docs:
                break
            all_docs.extend(docs)
            page += 1
            if len(docs) < per_page:
                break

        return all_docs[:max_results]

    # ── Record Lookup ──

    def get_record(self, record_id: str) -> Optional[Dict]:
        """Get a single record by ID. Returns the document dict or None."""
        url = f"{BASE_URL}/{record_id}.json"
        try:
            data = self._get_json(url)
            return data.get("response", {}).get("document", data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    # ── Extraction Helpers ──

    @staticmethod
    def get_title(doc: Dict) -> str:
        val = doc.get("title_display", "")
        if isinstance(val, list):
            return val[0] if val else ""
        return val

    @staticmethod
    def get_author(doc: Dict) -> str:
        val = doc.get("author_display", "")
        if isinstance(val, list):
            return val[0] if val else ""
        return val

    @staticmethod
    def get_authors(doc: Dict) -> List[str]:
        return doc.get("author_facet", [])

    @staticmethod
    def get_format(doc: Dict) -> List[str]:
        fmt = doc.get("format", [])
        if isinstance(fmt, str):
            return [fmt]
        return fmt

    @staticmethod
    def get_year(doc: Dict) -> str:
        years = doc.get("pub_year_display", [])
        return years[0] if years else ""

    @staticmethod
    def get_publisher(doc: Dict) -> str:
        pubs = doc.get("pub_name_display", [])
        return pubs[0] if pubs else ""

    @staticmethod
    def get_languages(doc: Dict) -> List[str]:
        return doc.get("language_facet", [])

    @staticmethod
    def get_subjects(doc: Dict) -> List[str]:
        return doc.get("subject_topic_facet", [])

    @staticmethod
    def get_isbns(doc: Dict) -> List[str]:
        return doc.get("isbn_display", [])

    @staticmethod
    def get_oclcs(doc: Dict) -> List[str]:
        return doc.get("oclc_display", [])

    @staticmethod
    def get_location_call_number(doc: Dict) -> List[str]:
        return doc.get("location_call_number_id_display", [])

    def summarize(self, doc: Dict) -> Dict[str, Any]:
        """Summarize a catalog document into a clean dict."""
        return {
            "id": doc.get("id", ""),
            "title": self.get_title(doc),
            "author": self.get_author(doc),
            "format": self.get_format(doc),
            "year": self.get_year(doc),
            "publisher": self.get_publisher(doc),
            "languages": self.get_languages(doc),
            "subjects": self.get_subjects(doc)[:5],
            "isbns": self.get_isbns(doc),
            "oclcs": self.get_oclcs(doc),
            "locations": self.get_location_call_number(doc),
        }


if __name__ == "__main__":
    clio = ColumbiaClioAPI()

    print("=== Search: hamlet (title) ===")
    results = clio.search("hamlet", search_field="title", per_page=3)
    for doc in results:
        s = clio.summarize(doc)
        print(f"  {s['title']} ({s['year']}) — {s['author']}")
        print(f"    Format: {s['format']}, Lang: {s['languages']}")

    print()
    print("=== Search: Chinese poetry (Book format) ===")
    results = clio.search("Chinese poetry", facets={"format": "Book"}, per_page=3)
    for doc in results:
        s = clio.summarize(doc)
        print(f"  {s['title']} ({s['year']})")
        print(f"    Subjects: {', '.join(s['subjects'][:3])}")
