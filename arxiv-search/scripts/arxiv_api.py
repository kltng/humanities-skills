"""
arXiv API client — zero external dependencies.

Searches arXiv for preprints, fetches metadata by ID, and handles
pagination, rate limiting, and Atom XML parsing using only the
Python standard library.
"""

import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Optional


# Atom / OpenSearch / arXiv XML namespaces
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    "arxiv": "http://arxiv.org/schemas/atom",
}

_BASE_URL = "http://export.arxiv.org/api/query"


class ArxivAPI:
    """Lightweight client for the arXiv Query API."""

    def __init__(
        self,
        min_request_interval: float = 3.0,
        max_retries: int = 4,
    ) -> None:
        self.min_request_interval = min_request_interval
        self.max_retries = max_retries
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        start: int = 0,
        max_results: int = 10,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> dict[str, Any]:
        """Run a search_query and return parsed results.

        Parameters
        ----------
        query : str
            arXiv search query (e.g. ``"ti:attention AND cat:cs.CL"``).
        start : int
            Zero-based offset for pagination.
        max_results : int
            Number of results (max 2000).
        sort_by : str, optional
            ``"relevance"``, ``"lastUpdatedDate"``, or ``"submittedDate"``.
        sort_order : str, optional
            ``"ascending"`` or ``"descending"``.

        Returns
        -------
        dict
            Keys: ``total_results``, ``start_index``, ``items_per_page``,
            ``entries`` (list of article dicts).
        """
        params: dict[str, str] = {
            "search_query": query,
            "start": str(start),
            "max_results": str(max_results),
        }
        if sort_by is not None:
            params["sortBy"] = sort_by
        if sort_order is not None:
            params["sortOrder"] = sort_order

        xml_text = self._request(_BASE_URL, params)
        return self._parse_feed(xml_text)

    def fetch_by_ids(
        self,
        ids: list[str],
        *,
        start: int = 0,
        max_results: Optional[int] = None,
    ) -> dict[str, Any]:
        """Fetch metadata for specific arXiv IDs.

        Parameters
        ----------
        ids : list[str]
            arXiv IDs, e.g. ``["2301.07041", "cond-mat/0207270v1"]``.
        """
        if max_results is None:
            max_results = len(ids)
        params: dict[str, str] = {
            "id_list": ",".join(ids),
            "start": str(start),
            "max_results": str(max_results),
        }
        xml_text = self._request(_BASE_URL, params)
        return self._parse_feed(xml_text)

    # ------------------------------------------------------------------
    # XML parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _text(element: Optional[ET.Element]) -> Optional[str]:
        if element is None or element.text is None:
            return None
        return re.sub(r"\s+", " ", element.text).strip()

    def _parse_entry(self, entry: ET.Element) -> dict[str, Any]:
        """Parse a single <entry> element into a dict."""
        raw_id = self._text(entry.find("atom:id", _NS)) or ""
        arxiv_id = raw_id.replace("http://arxiv.org/abs/", "")

        # Authors
        authors: list[dict[str, Optional[str]]] = []
        for author_el in entry.findall("atom:author", _NS):
            name = self._text(author_el.find("atom:name", _NS))
            affiliation = self._text(
                author_el.find("arxiv:affiliation", _NS)
            )
            authors.append({"name": name, "affiliation": affiliation})

        # Categories
        categories: list[str] = [
            cat.get("term", "")
            for cat in entry.findall("atom:category", _NS)
        ]
        primary_el = entry.find("arxiv:primary_category", _NS)
        primary_category = primary_el.get("term", "") if primary_el is not None else None

        # Links
        links: dict[str, str] = {}
        for link_el in entry.findall("atom:link", _NS):
            rel = link_el.get("rel", "")
            title = link_el.get("title", "")
            href = link_el.get("href", "")
            if rel == "alternate":
                links["abstract"] = href
            elif rel == "related" and title == "pdf":
                links["pdf"] = href
            elif rel == "related" and title == "doi":
                links["doi"] = href

        return {
            "id": arxiv_id,
            "title": self._text(entry.find("atom:title", _NS)),
            "summary": self._text(entry.find("atom:summary", _NS)),
            "authors": authors,
            "published": self._text(entry.find("atom:published", _NS)),
            "updated": self._text(entry.find("atom:updated", _NS)),
            "categories": categories,
            "primary_category": primary_category,
            "links": links,
            "comment": self._text(entry.find("arxiv:comment", _NS)),
            "journal_ref": self._text(entry.find("arxiv:journal_ref", _NS)),
            "doi": self._text(entry.find("arxiv:doi", _NS)),
        }

    def _parse_feed(self, xml_text: str) -> dict[str, Any]:
        """Parse a full Atom feed into a result dict."""
        root = ET.fromstring(xml_text)

        total_el = root.find("opensearch:totalResults", _NS)
        start_el = root.find("opensearch:startIndex", _NS)
        per_page_el = root.find("opensearch:itemsPerPage", _NS)

        entries = [
            self._parse_entry(e) for e in root.findall("atom:entry", _NS)
        ]

        return {
            "total_results": int(total_el.text) if total_el is not None and total_el.text else 0,
            "start_index": int(start_el.text) if start_el is not None and start_el.text else 0,
            "items_per_page": int(per_page_el.text) if per_page_el is not None and per_page_el.text else 0,
            "entries": entries,
        }

    # ------------------------------------------------------------------
    # HTTP layer
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)

    def _request(self, url: str, params: dict[str, str]) -> str:
        """Make a rate-limited GET request with retry + exponential backoff."""
        full_url = f"{url}?{urllib.parse.urlencode(params)}"

        for attempt in range(self.max_retries + 1):
            self._rate_limit()
            self._last_request_time = time.monotonic()

            req = urllib.request.Request(
                full_url,
                headers={"User-Agent": "ArxivSearchSkill/1.0"},
            )

            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    return resp.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                if exc.code == 429 or 500 <= exc.code < 600:
                    retry_after = exc.headers.get("Retry-After")
                    wait = (
                        float(retry_after)
                        if retry_after
                        else self.min_request_interval * (2 ** attempt)
                    )
                    if attempt < self.max_retries:
                        time.sleep(wait)
                        continue
                raise
            except urllib.error.URLError:
                if attempt < self.max_retries:
                    time.sleep(self.min_request_interval * (2 ** attempt))
                    continue
                raise

        raise RuntimeError("Max retries exceeded")


# ------------------------------------------------------------------
# Demo
# ------------------------------------------------------------------

def main() -> None:
    api = ArxivAPI()

    print("=== Search: 'attention mechanism' in titles ===")
    results = api.search("ti:attention AND ti:mechanism", max_results=3)
    print(f"Total results: {results['total_results']}")
    for entry in results["entries"]:
        print(f"  [{entry['id']}] {entry['title']}")
        print(f"    Authors: {', '.join(a['name'] or '' for a in entry['authors'])}")
        print(f"    Category: {entry['primary_category']}")
        print(f"    Published: {entry['published']}")
        print()

    print("=== Fetch by ID ===")
    results = api.fetch_by_ids(["2301.07041"])
    for entry in results["entries"]:
        print(f"  [{entry['id']}] {entry['title']}")
        print(f"    Abstract: {entry['summary'][:200]}...")
        print()


if __name__ == "__main__":
    main()
