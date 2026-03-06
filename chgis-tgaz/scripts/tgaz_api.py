#!/usr/bin/env python3
"""
CHGIS Temporal Gazetteer (TGAZ) API client.
Zero external dependencies — uses only Python stdlib.
"""

import json
import time
import urllib.parse
import urllib.request
from typing import Optional, Any
from urllib.error import HTTPError, URLError


class TGAZAPI:
    """Client for the CHGIS Temporal Gazetteer API.

    IMPORTANT: The current domain is chgis.hudci.org (NOT the old maps.cga.harvard.edu).
    """

    BASE_URL = "https://chgis.hudci.org/tgaz/placename"

    def __init__(self, min_request_interval: float = 1.0, max_retries: int = 3):
        self._last_request_time = 0.0
        self._min_request_interval = min_request_interval
        self._max_retries = max_retries

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _request(self, url: str, params: Optional[dict] = None, timeout: int = 30) -> Any:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            self._rate_limit()
            req = urllib.request.Request(url)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except (HTTPError, URLError) as e:
                last_error = e
                time.sleep(min(8.0, 0.5 * (2 ** attempt)))
                continue

        if last_error:
            raise last_error
        raise RuntimeError("Request failed")

    def search(
        self,
        name: str,
        year: Optional[int] = None,
        feature_type: Optional[str] = None,
        parent: Optional[str] = None,
    ) -> list:
        """Search for placenames using the faceted search endpoint.

        Args:
            name: Place name (Chinese characters or Romanized).
                  Note: API uses prefix matching. "beijing" matches 北京路, 北京行省, etc.
                  Note: Some romanizations differ from modern pinyin (e.g., Ningbo → "Ningpo").
            year: Historical year (-222 to 1911). Negative for BCE.
            feature_type: Administrative type filter (xian, fu, zhou, sheng, dao, lu, jun).
            parent: Parent administrative unit name (ipar parameter).
                    WARNING: The ipar parameter is unreliable. For hierarchical queries,
                    prefer using get_by_id() on the parent record and reading its
                    subordinate units.

        Returns:
            List of placename result dicts.
        """
        params = {"n": name, "fmt": "json"}
        if year is not None:
            params["yr"] = str(year)
        if feature_type:
            params["ftyp"] = feature_type
        if parent:
            params["ipar"] = parent

        data = self._request(self.BASE_URL, params)
        if isinstance(data, list):
            return data
        # Sometimes the API wraps results
        return data.get("placenames", data.get("results", [data]))

    def get_by_id(self, tgaz_id: str, fmt: str = "json") -> dict:
        """Retrieve a specific placename record by TGAZ ID.

        IMPORTANT: The format is specified in the URL path, NOT as a query parameter.
        /placename/json/{id} — correct
        /placename?id={id}&fmt=json — WRONG (fmt only works for faceted search)

        Args:
            tgaz_id: TGAZ ID (e.g., "hvd_32180"). If a bare number is given,
                     "hvd_" prefix is added automatically.
            fmt: Output format — "json", "xml", or "rdf" (default: "json").

        Returns:
            Placename record dict.
        """
        if not tgaz_id.startswith("hvd_"):
            tgaz_id = f"hvd_{tgaz_id}"

        url = f"{self.BASE_URL}/{fmt}/{tgaz_id}"
        return self._request(url)

    def get_name(self, record: dict) -> str:
        """Extract the primary Chinese name from a record."""
        spellings = record.get("spellings", [])
        for s in spellings:
            if s.get("script") == "漢" or s.get("writing.system") == "Chinese Traditional":
                return s.get("written.form", "")
        # Fallback
        return record.get("name", "")

    def get_transcription(self, record: dict) -> str:
        """Extract the romanized transcription from a record."""
        spellings = record.get("spellings", [])
        for s in spellings:
            if s.get("script") == "Latn" or s.get("writing.system") == "Pinyin":
                return s.get("written.form", "")
        return record.get("transcription", "")

    def get_temporal_span(self, record: dict) -> tuple:
        """Extract (begin_year, end_year) from a record."""
        temporal = record.get("temporal", {})
        begin = temporal.get("begin", "")
        end = temporal.get("end", "")
        return (begin, end)

    def get_modern_location(self, record: dict) -> str:
        """Extract the modern equivalent location."""
        spatial = record.get("spatial", {})
        return spatial.get("present_location", "")

    def get_feature_type(self, record: dict) -> str:
        """Extract the feature type (administrative type)."""
        ftype = record.get("feature.type", {})
        if isinstance(ftype, dict):
            return ftype.get("name.en", ftype.get("name.ch", ""))
        return str(ftype)

    def get_subordinates(self, record: dict) -> list:
        """Extract subordinate administrative units from a canonical record.

        This is the reliable way to find child units — more dependable than
        using the ipar search parameter.
        """
        context = record.get("historical_context", {})
        parts = context.get("has parts", [])
        if isinstance(parts, dict):
            return [parts]
        return parts

    def summarize(self, record: dict) -> str:
        """Generate a formatted summary of a placename record."""
        lines = []
        name = self.get_name(record)
        transcription = self.get_transcription(record)
        begin, end = self.get_temporal_span(record)
        modern = self.get_modern_location(record)
        ftype = self.get_feature_type(record)

        lines.append(f"# {name} ({transcription})")
        if ftype:
            lines.append(f"\n**Type:** {ftype}")
        if begin or end:
            lines.append(f"**Period:** {begin} – {end}")
        if modern:
            lines.append(f"**Modern location:** {modern}")

        return "\n".join(lines)


def main():
    api = TGAZAPI()

    print("=== Search: suzhou, year 1820 ===")
    results = api.search("suzhou", year=1820)
    for r in results[:3]:
        print(f"  {r.get('name', '')} ({r.get('transcription', '')}) — {r.get('feature type', '')}")

    print("\n=== Lookup: hvd_32180 ===")
    record = api.get_by_id("hvd_32180")
    print(api.summarize(record))


if __name__ == "__main__":
    main()
