"""
NLB Singapore Catalogue API client — zero external dependencies.

Searches the National Library Board Singapore catalog for books,
audiovisual materials, and digital resources.

Requires API key and app code. Set environment variables:
    NLB_API_KEY — your API key
    NLB_APP_CODE — your application code

Apply for free keys at https://go.gov.sg/nlblabs-form
"""

import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Any, Dict, List, Optional

BASE_URL = "https://openweb.nlb.gov.sg/api/v2/Catalogue"


class NlbAPI:
    """Client for the NLB Singapore Catalogue API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        app_code: Optional[str] = None,
        min_interval: float = 0.5,
    ):
        self._api_key = api_key or os.environ.get("NLB_API_KEY", "")
        self._app_code = app_code or os.environ.get("NLB_APP_CODE", "")
        self._min_interval = min_interval
        self._last_request = 0.0

        if not self._api_key or not self._app_code:
            raise ValueError(
                "NLB API key and app code required. Set NLB_API_KEY and NLB_APP_CODE "
                "environment variables, or pass api_key and app_code to constructor. "
                "Apply at https://go.gov.sg/nlblabs-form"
            )

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.time()

    def _get_json(self, url: str) -> Dict[str, Any]:
        self._rate_limit()
        req = urllib.request.Request(url, headers={
            "X-API-KEY": self._api_key,
            "X-APP-Code": self._app_code,
            "User-Agent": "NlbSingaporeSkill/1.0 (Claude Code skill; research use)",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # Rate limited — wait and retry once
                time.sleep(5)
                self._rate_limit()
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read())
            raise

    def _build_url(self, endpoint: str, params: Dict[str, Any]) -> str:
        # Filter out None values
        clean = {k: v for k, v in params.items() if v is not None}
        qs = urllib.parse.urlencode(clean, doseq=True)
        return f"{BASE_URL}/{endpoint}?{qs}"

    # ── Search ──

    def search(
        self,
        keywords: str,
        limit: int = 20,
        offset: int = 0,
        material_types: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        date_from: Optional[int] = None,
        date_to: Optional[int] = None,
        availability: Optional[bool] = None,
        fiction: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Keyword search across the NLB catalog.
        Returns full response with titles, facets, and pagination info.
        """
        params = {
            "Keywords": keywords,
            "Limit": limit,
            "Offset": offset,
        }
        if material_types:
            params["MaterialTypes"] = material_types
        if languages:
            params["Languages"] = languages
        if locations:
            params["Locations"] = locations
        if date_from is not None:
            params["DateFrom"] = date_from
        if date_to is not None:
            params["DateTo"] = date_to
        if availability is not None:
            params["Availability"] = str(availability).lower()
        if fiction is not None:
            params["Fiction"] = str(fiction).lower()

        url = self._build_url("SearchTitles", params)
        return self._get_json(url)

    def search_titles(self, keywords: str, **kwargs) -> List[Dict]:
        """Search and return just the titles list."""
        data = self.search(keywords, **kwargs)
        return data.get("titles", [])

    # ── Field-Specific Search ──

    def get_titles(
        self,
        keywords: Optional[str] = None,
        title: Optional[str] = None,
        author: Optional[str] = None,
        subject: Optional[str] = None,
        isbn: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Field-specific search. At least one search field required.
        Returns full response with titles and pagination info.
        """
        params = {"Limit": limit, "Offset": offset}
        if keywords:
            params["Keywords"] = keywords
        if title:
            params["Title"] = title
        if author:
            params["Author"] = author
        if subject:
            params["Subject"] = subject
        if isbn:
            params["ISBN"] = isbn

        url = self._build_url("GetTitles", params)
        return self._get_json(url)

    # ── Title Details ──

    def get_title_details(
        self, brn: Optional[int] = None, isbn: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get full title details by BRN or ISBN.
        Returns the title record dict, or None if not found.
        """
        params = {}
        if brn is not None:
            params["BRN"] = brn
        elif isbn:
            params["ISBN"] = isbn
        else:
            raise ValueError("Either brn or isbn required")

        url = self._build_url("GetTitleDetails", params)
        try:
            return self._get_json(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    # ── Availability ──

    def get_availability(
        self,
        brn: Optional[int] = None,
        isbn: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict]:
        """
        Check physical item availability across library branches.
        Returns list of item dicts with location and status.
        """
        params = {"Limit": limit, "Offset": offset}
        if brn is not None:
            params["BRN"] = brn
        elif isbn:
            params["ISBN"] = isbn
        else:
            raise ValueError("Either brn or isbn required")

        url = self._build_url("GetAvailabilityInfo", params)
        try:
            data = self._get_json(url)
            return data.get("items", [])
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            raise

    # ── New Titles ──

    def get_new_titles(
        self,
        date_range: str = "Weekly",
        limit: int = 20,
        offset: int = 0,
        material_types: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Browse new arrivals.
        date_range: "Weekly" or other supported values.
        """
        params = {
            "DateRange": date_range,
            "Limit": limit,
            "Offset": offset,
        }
        if material_types:
            params["MaterialTypes"] = material_types
        if languages:
            params["Languages"] = languages

        url = self._build_url("GetNewTitles", params)
        return self._get_json(url)

    # ── Checkout Trends ──

    def get_checkout_trends(
        self,
        location_code: str,
        duration: str = "past30days",
    ) -> Dict[str, Any]:
        """
        Get checkout trends for a library branch.
        location_code: e.g., "TRL", "AMKPL", "BIPL"
        duration: "past30days" or other supported values
        """
        params = {"LocationCode": location_code, "Duration": duration}
        url = self._build_url("GetMostCheckoutsTrendsTitles", params)
        return self._get_json(url)

    # ── Pagination Helper ──

    def search_all(self, keywords: str, max_results: int = 200, **kwargs) -> List[Dict]:
        """Paginate through search results up to max_results."""
        all_titles = []
        page_size = min(100, max_results)
        offset = 0

        while len(all_titles) < max_results:
            data = self.search(keywords, limit=page_size, offset=offset, **kwargs)
            titles = data.get("titles", [])
            if not titles:
                break
            all_titles.extend(titles)
            if not data.get("hasMoreRecords", False):
                break
            offset = data.get("nextRecordsOffset", offset + page_size)

        return all_titles[:max_results]

    # ── Extraction Helpers ──

    @staticmethod
    def get_title(record: Dict) -> str:
        """Get title, preferring native title if available."""
        native = record.get("nativeTitle", "")
        title = record.get("title", "")
        if native and native != title:
            return f"{title} ({native})"
        return title

    @staticmethod
    def get_author(record: Dict) -> str:
        native = record.get("nativeAuthor", "")
        author = record.get("author", "")
        if native and native != author:
            return f"{author} ({native})"
        return author

    @staticmethod
    def get_brn(record: Dict) -> Optional[int]:
        """Extract BRN from a search result (may be nested in records)."""
        brn = record.get("brn")
        if brn:
            return brn
        records = record.get("records", [])
        if records:
            return records[0].get("brn")
        return None

    @staticmethod
    def get_isbns(record: Dict) -> List[str]:
        isbns = record.get("isbns", [])
        if isbns:
            return isbns
        records = record.get("records", [])
        if records:
            return records[0].get("isbns", [])
        return []

    @staticmethod
    def get_publish_date(record: Dict) -> str:
        date = record.get("publishDate", "")
        if date:
            return date
        records = record.get("records", [])
        if records:
            return records[0].get("publishDate", "")
        return ""

    @staticmethod
    def get_subjects(record: Dict) -> List[str]:
        subjects = record.get("subjects", [])
        if subjects:
            return subjects
        records = record.get("records", [])
        if records:
            return records[0].get("subjects", [])
        return []

    @staticmethod
    def get_format(record: Dict) -> str:
        fmt = record.get("format", {})
        if isinstance(fmt, dict):
            return fmt.get("name", "")
        records = record.get("records", [])
        if records:
            fmt = records[0].get("format", {})
            if isinstance(fmt, dict):
                return fmt.get("name", "")
        return ""

    def summarize(self, record: Dict) -> Dict[str, Any]:
        """Summarize a search result into a clean dict."""
        return {
            "title": self.get_title(record),
            "author": self.get_author(record),
            "brn": self.get_brn(record),
            "isbns": self.get_isbns(record),
            "publish_date": self.get_publish_date(record),
            "subjects": self.get_subjects(record)[:5],
            "format": self.get_format(record),
        }


if __name__ == "__main__":
    # This requires valid API credentials
    try:
        nlb = NlbAPI()
        print("=== Search: singapore history ===")
        data = nlb.search("singapore history", limit=3)
        for t in data.get("titles", [])[:3]:
            s = nlb.summarize(t)
            print(f"  {s['title']} — {s['author']}")
            print(f"    BRN: {s['brn']}, Date: {s['publish_date']}")
        print(f"  Total: {data.get('totalRecords', '?')}")
    except ValueError as e:
        print(f"Note: {e}")
        print("Set NLB_API_KEY and NLB_APP_CODE environment variables to test.")
