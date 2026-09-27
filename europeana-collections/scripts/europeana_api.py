"""
Europeana Collections API client — zero external dependencies.

Searches 50M+ cultural heritage items from 4,000+ European institutions.
Requires an API key. Reads EUROPEANA_API_KEY from the environment and
falls back to the public demo key 'api2demo' (testing only).
"""

import email.utils
import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Any, Dict, List, Optional

BASE_URL = "https://api.europeana.eu/record/v2"

VALID_TYPES = {"IMAGE", "TEXT", "SOUND", "VIDEO", "3D"}
VALID_REUSABILITY = {"open", "restricted", "permission"}


class EuropeanaAPI:
    """Client for the Europeana Search and Record APIs."""

    def __init__(self, api_key: Optional[str] = None, min_interval: float = 0.5):
        self._api_key = api_key or os.environ.get("EUROPEANA_API_KEY") or "api2demo"
        self._min_interval = min_interval
        self._last_request = 0.0

    def _rate_limit(self):
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
            "User-Agent": "EuropeanaSkill/1.0 (Claude Code skill; research use)",
        })
        for attempt in range(3):
            self._rate_limit()
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == 2:
                    raise
                time.sleep(self._retry_after_seconds(e, 5.0 * (attempt + 1)))
        raise RuntimeError("unreachable")

    # ── Search ──

    def search(
        self,
        query: str,
        type: Optional[str] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
        provider: Optional[str] = None,
        data_provider: Optional[str] = None,
        reusability: Optional[str] = None,
        media: Optional[bool] = None,
        rows: int = 12,
        start: int = 1,
        profile: str = "standard",
    ) -> List[Dict]:
        """
        Search Europeana collections. Returns list of item dicts.

        Args:
            query: Search query (supports Lucene syntax)
            type: Filter by type: IMAGE, TEXT, SOUND, VIDEO, 3D
            country: Filter by country
            language: Filter by language (ISO code)
            provider: Filter by provider
            data_provider: Filter by institution
            reusability: License filter: open, restricted, permission
            media: Has media (True/False)
            rows: Results per page (max 100)
            start: Start offset (1-based)
            profile: Response detail: minimal, standard, rich
        """
        params = {
            "query": query,
            "wskey": self._api_key,
            "rows": str(rows),
            "start": str(start),
            "profile": profile,
        }

        qf_parts = []
        if type:
            if type.upper() not in VALID_TYPES:
                raise ValueError(f"Invalid type: {type}. Must be one of {VALID_TYPES}")
            qf_parts.append(f"TYPE:{type.upper()}")
        if country:
            qf_parts.append(f"COUNTRY:{country}")
        if language:
            qf_parts.append(f"LANGUAGE:{language}")
        if provider:
            qf_parts.append(f"PROVIDER:{provider}")
        if data_provider:
            qf_parts.append(f"DATA_PROVIDER:{data_provider}")

        if reusability:
            if reusability not in VALID_REUSABILITY:
                raise ValueError(f"Invalid reusability: {reusability}")
            params["reusability"] = reusability
        if media is not None:
            params["media"] = "true" if media else "false"

        # Build URL
        qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        for qf in qf_parts:
            qs += f"&qf={urllib.parse.quote(qf, safe=':')}"

        url = f"{BASE_URL}/search.json?{qs}"
        data = self._get_json(url)

        if not data.get("success"):
            raise RuntimeError(f"Europeana API error: {data.get('error', 'unknown')}")

        return data.get("items", [])

    def search_with_count(self, query: str, **kwargs) -> tuple:
        """Search and return (items, total_count)."""
        params = {
            "query": query,
            "wskey": self._api_key,
            "rows": str(kwargs.get("rows", 12)),
            "start": str(kwargs.get("start", 1)),
            "profile": kwargs.get("profile", "standard"),
        }

        qf_parts = []
        for key in ("type", "country", "language", "provider", "data_provider"):
            val = kwargs.get(key)
            if val:
                if key == "type":
                    val = val.upper()
                    if val not in VALID_TYPES:
                        raise ValueError(f"Invalid type: {val}. Must be one of {VALID_TYPES}")
                qf_parts.append(f"{key.upper()}:{val}")

        if kwargs.get("reusability"):
            if kwargs["reusability"] not in VALID_REUSABILITY:
                raise ValueError(f"Invalid reusability: {kwargs['reusability']}")
            params["reusability"] = kwargs["reusability"]
        if kwargs.get("media") is not None:
            params["media"] = "true" if kwargs["media"] else "false"

        qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        for qf in qf_parts:
            qs += f"&qf={urllib.parse.quote(qf, safe=':')}"

        url = f"{BASE_URL}/search.json?{qs}"
        data = self._get_json(url)
        if not data.get("success"):
            raise RuntimeError(f"Europeana API error: {data.get('error', 'unknown')}")
        return data.get("items", []), data.get("totalResults", 0)

    # ── Record Lookup ──

    def get_record(self, record_id: str) -> Optional[Dict]:
        """
        Get a single record by Europeana ID.
        record_id: e.g., "/15502/GG_9128" (from search result 'id' field)
        """
        # Encode each path segment; keep the dataset/item slash structure
        segments = record_id.strip("/").split("/")
        if any(seg in ("", ".", "..") for seg in segments):
            raise ValueError(f"Invalid Europeana record ID: {record_id!r}")
        path = "/".join(urllib.parse.quote(seg, safe="") for seg in segments)
        qs = urllib.parse.urlencode({"wskey": self._api_key})
        url = f"{BASE_URL}/{path}.json?{qs}"
        try:
            data = self._get_json(url)
            if data.get("success"):
                return data.get("object", data)
            return None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    # ── Extraction Helpers ──

    @staticmethod
    def get_title(item: Dict, lang: str = "en") -> str:
        """Get title, preferring specified language."""
        lang_aware = item.get("dcTitleLangAware", {})
        if lang in lang_aware:
            titles = lang_aware[lang]
            return titles[0] if titles else ""
        titles = item.get("title", [])
        return titles[0] if titles else ""

    @staticmethod
    def get_creators(item: Dict) -> List[str]:
        creators = item.get("dcCreator", [])
        # Filter out URI-only entries
        return [c for c in creators if not c.startswith("http")]

    @staticmethod
    def get_year(item: Dict) -> str:
        years = item.get("year", [])
        return years[0] if years else ""

    @staticmethod
    def get_country(item: Dict) -> str:
        countries = item.get("country", [])
        return countries[0] if countries else ""

    @staticmethod
    def get_provider(item: Dict) -> str:
        providers = item.get("dataProvider", [])
        return providers[0] if providers else ""

    @staticmethod
    def get_type(item: Dict) -> str:
        return item.get("type", "")

    @staticmethod
    def get_rights(item: Dict) -> str:
        rights = item.get("rights", [])
        return rights[0] if rights else ""

    @staticmethod
    def get_thumbnail(item: Dict) -> Optional[str]:
        previews = item.get("edmPreview", [])
        return previews[0] if previews else None

    @staticmethod
    def get_provider_url(item: Dict) -> Optional[str]:
        urls = item.get("edmIsShownAt", [])
        return urls[0] if urls else None

    @staticmethod
    def get_full_image_url(item: Dict) -> Optional[str]:
        urls = item.get("edmIsShownBy", [])
        return urls[0] if urls else None

    @staticmethod
    def get_europeana_url(item: Dict) -> str:
        item_id = item.get("id", "")
        return f"https://www.europeana.eu/item{item_id}" if item_id else ""

    def summarize(self, item: Dict) -> Dict[str, Any]:
        """Summarize a search result item into a clean dict."""
        return {
            "id": item.get("id", ""),
            "title": self.get_title(item),
            "creators": self.get_creators(item),
            "year": self.get_year(item),
            "country": self.get_country(item),
            "provider": self.get_provider(item),
            "type": self.get_type(item),
            "rights": self.get_rights(item),
            "thumbnail": self.get_thumbnail(item),
            "provider_url": self.get_provider_url(item),
            "europeana_url": self.get_europeana_url(item),
        }


if __name__ == "__main__":
    eu = EuropeanaAPI()

    print("=== Search: vermeer (IMAGE, open access) ===")
    results = eu.search("vermeer", type="IMAGE", reusability="open", rows=3)
    for r in results:
        s = eu.summarize(r)
        print(f"  {s['title']} ({s['year']}) — {s['provider']}")
        print(f"    Type: {s['type']}, Rights: {s['rights']}")
        print(f"    URL: {s['europeana_url']}")

    print()
    print("=== Search: medieval manuscript (TEXT, France) ===")
    results = eu.search("medieval manuscript", type="TEXT", country="France", rows=3)
    for r in results:
        s = eu.summarize(r)
        print(f"  {s['title']} ({s['year']}) — {s['provider']}")
