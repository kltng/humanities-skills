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
    USER_AGENT = "humanities-skills-chgis-tgaz/1.1 (https://github.com/kltng/humanities-skills)"
    FORMATS = ("json", "xml", "rdf")

    def __init__(self, min_request_interval: float = 1.0, max_retries: int = 3):
        self._last_request_time = 0.0
        self._min_request_interval = min_request_interval
        self._max_retries = max_retries

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    @staticmethod
    def _retry_delay(error: HTTPError, attempt: int) -> float:
        """Honor Retry-After (seconds) on 429/503; else exponential backoff."""
        retry_after = error.headers.get("Retry-After") if error.headers else None
        if retry_after and retry_after.strip().isdigit():
            return min(60.0, float(retry_after.strip()))
        return min(8.0, 0.5 * (2 ** attempt))

    def _request(self, url: str, params: Optional[dict] = None, timeout: int = 30,
                 raw: bool = False) -> Any:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            self._rate_limit()
            req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    body = resp.read().decode("utf-8")
                return body if raw else json.loads(body)
            except HTTPError as e:
                last_error = e
                # 4xx other than 429 (e.g. 404 for an unknown ID) will not
                # change on retry, so fail at once.
                if 400 <= e.code < 500 and e.code != 429:
                    raise
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay(e, attempt))
            except (URLError, TimeoutError) as e:
                last_error = e
                if attempt < self._max_retries:
                    time.sleep(min(8.0, 0.5 * (2 ** attempt)))

        if last_error:
            raise last_error
        raise RuntimeError("Request failed")

    @staticmethod
    def has_bad_coords(result: dict) -> bool:
        """True when a search result's coordinates cannot be right.

        Many places have a second POLYGON record (often an hvd_90xxx id)
        whose longitude is 0 (or 1-5). Some other records are 0, 0. On a
        map these land near Africa. No real TGAZ place is within 10 degrees
        of longitude 0. Accepts a search result ("xy coordinates": "lon, lat")
        or a full record (spatial.longitude / spatial.latitude).
        """
        lon = lat = None
        xy = result.get("xy coordinates")
        if isinstance(xy, str) and "," in xy:
            lon, lat = (v.strip() for v in xy.split(",", 1))
        elif isinstance(result.get("spatial"), dict):
            lon = result["spatial"].get("longitude")
            lat = result["spatial"].get("latitude")
        try:
            lon_f, lat_f = float(lon), float(lat)
        except (TypeError, ValueError):
            return True
        return abs(lon_f) < 10 or lat_f == 0

    def search(
        self,
        name: str,
        year: Optional[int] = None,
        feature_type: Optional[str] = None,
        parent: Optional[str] = None,
        drop_bad_coords: bool = False,
    ) -> list:
        """Search for placenames using the faceted search endpoint.

        Args:
            name: Place name (Chinese characters or Romanized).
                  Note: API uses prefix matching. "beijing" matches 北京路, 北京行省, etc.
                  Note: Some romanizations differ from modern pinyin (e.g., Ningbo → "Ningpo").
                  Note: Some records split syllables with a space: 苏州 before 1367 is
                  "Su Zhou", so "suzhou" with year=1100 finds nothing. Search
                  Chinese characters when you can (蘇州 or 苏州 both work).
            year: Historical year (-222 to 1911). Negative for BCE.
            feature_type: Administrative type filter (xian, fu, zhou, sheng, dao, lu, jun).
            parent: Parent administrative unit name (ipar parameter).
                    WARNING: The ipar parameter is unreliable. For hierarchical queries,
                    prefer using get_by_id() on the parent record and reading its
                    subordinate units.
            drop_bad_coords: Leave out results whose coordinates are broken
                    (see has_bad_coords). Use this before putting results on a map.

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
            results = data
        else:
            # The API wraps results in {"placenames": [...]}.
            results = data.get("placenames", data.get("results", [data]))
        if drop_bad_coords:
            results = [r for r in results if not self.has_bad_coords(r)]
        return results

    def get_by_id(self, tgaz_id: str, fmt: str = "json") -> dict:
        """Retrieve a specific placename record by TGAZ ID.

        IMPORTANT: The format is specified in the URL path, NOT as a query parameter.
        /placename/json/{id} — correct
        /placename?id={id}&fmt=json — WRONG (fmt only works for faceted search)

        Args:
            tgaz_id: TGAZ ID (e.g., "hvd_32180", "TBRC_G123"). If a bare number
                     is given, "hvd_" prefix is added automatically.
            fmt: Output format — "json", "xml", or "rdf" (default: "json").

        Returns:
            Placename record dict for "json"; the raw text for "xml"/"rdf".
        """
        if fmt not in self.FORMATS:
            raise ValueError(f"fmt must be one of {self.FORMATS}, got {fmt!r}")
        tgaz_id = str(tgaz_id).strip()
        if tgaz_id.isdigit():
            tgaz_id = f"hvd_{tgaz_id}"

        url = f"{self.BASE_URL}/{fmt}/{urllib.parse.quote(tgaz_id, safe='')}"
        return self._request(url, raw=(fmt != "json"))

    def get_name(self, record: dict) -> str:
        """Extract the primary Chinese name from a record."""
        spellings = record.get("spellings", [])
        for script in ("traditional Chinese", "simplified Chinese"):
            for s in spellings:
                if s.get("script") == script:
                    return s.get("written form", "")
        # Fallback
        return record.get("name", "")

    def get_transcription(self, record: dict) -> str:
        """Extract the romanized transcription from a record."""
        spellings = record.get("spellings", [])
        for s in spellings:
            if s.get("transcribed in") == "Pinyin":
                return s.get("written form", "")
        for s in spellings:
            if "transcribed in" in s:
                return s.get("written form", "")
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
        present = spatial.get("present_location", "")
        # The API returns a list of {"country code", "text", ...} entries.
        if isinstance(present, dict):
            present = [present]
        if isinstance(present, list):
            return "; ".join(p.get("text", "") for p in present if p.get("text"))
        return str(present)

    def get_feature_type(self, record: dict) -> str:
        """Extract the feature type (administrative type)."""
        ftype = record.get("feature_type", {})
        if isinstance(ftype, dict):
            return ftype.get("English") or ftype.get("transcription") or ftype.get("name", "")
        return str(ftype)

    def get_subordinates(self, record: dict) -> list:
        """Extract subordinate administrative units from a canonical record.

        This is the reliable way to find child units — more dependable than
        using the ipar search parameter.
        """
        context = record.get("historical_context", {})
        parts = context.get("subordinate units", [])
        if isinstance(parts, dict):
            return [parts]
        return parts

    @staticmethod
    def _in_year(unit: dict, year: Optional[int]) -> bool:
        if year is None:
            return True
        try:
            return int(unit["begin_year"]) <= year <= int(unit["end_year"])
        except (KeyError, TypeError, ValueError):
            return False

    def get_descendants(self, tgaz_id: str, year: Optional[int] = None,
                        levels: int = 2) -> list:
        """Drill down the hierarchy, `levels` steps below a unit.

        A province's record lists only the next level (prefectures, 府/州/厅).
        Counties sit one level lower, so "all counties in Zhejiang" needs
        levels=2: one request for the province plus one per prefecture
        (about 13 requests, 1 per second). Each returned unit gets "level"
        (1 = direct child) and "parent id". Units are filtered to `year`,
        and each child id is returned once.
        """
        found: list = []
        seen = set()
        frontier = [str(tgaz_id)]
        for level in range(1, levels + 1):
            next_frontier = []
            for parent_id in frontier:
                record = self.get_by_id(parent_id)
                for unit in self.get_subordinates(record):
                    child = unit.get("child id")
                    if not child or child in seen or not self._in_year(unit, year):
                        continue
                    seen.add(child)
                    found.append({**unit, "level": level, "parent id": parent_id})
                    next_frontier.append(child)
            frontier = next_frontier
        return found

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
