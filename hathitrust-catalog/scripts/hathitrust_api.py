"""
HathiTrust Bibliographic API client — zero external dependencies.

Looks up bibliographic records and digitized volume info by identifier
(ISBN, OCLC, LCCN, ISSN, HathiTrust ID, record number).
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Any, Dict, List, Optional, Tuple

BASE_URL = "https://catalog.hathitrust.org/api/volumes"

VALID_ID_TYPES = {"isbn", "lccn", "oclc", "issn", "htid", "recordnumber"}


class HathiTrustAPI:
    """Client for the HathiTrust Bibliographic API."""

    def __init__(self, min_interval: float = 0.5):
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
            "User-Agent": "HathiTrustSkill/1.0 (Claude Code skill; research use)",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    # ── Single-ID Lookups ──

    def _lookup(self, id_type: str, id_value: str, full: bool = False) -> Optional[Dict]:
        """
        Look up a single identifier. Returns the raw API response dict,
        or None if no records found.
        """
        if id_type not in VALID_ID_TYPES:
            raise ValueError(f"Invalid id_type: {id_type}. Must be one of {VALID_ID_TYPES}")
        variant = "full" if full else "brief"
        encoded_id = urllib.parse.quote(str(id_value), safe="")
        url = f"{BASE_URL}/{variant}/{id_type}/{encoded_id}.json"
        data = self._get_json(url)
        if not data.get("records"):
            return None
        return data

    def lookup_isbn(self, isbn: str, full: bool = False) -> Optional[Dict]:
        """Look up by ISBN (10 or 13 digit)."""
        return self._lookup("isbn", isbn, full)

    def lookup_oclc(self, oclc: str, full: bool = False) -> Optional[Dict]:
        """Look up by OCLC number."""
        return self._lookup("oclc", oclc, full)

    def lookup_lccn(self, lccn: str, full: bool = False) -> Optional[Dict]:
        """Look up by Library of Congress Control Number."""
        return self._lookup("lccn", lccn, full)

    def lookup_issn(self, issn: str, full: bool = False) -> Optional[Dict]:
        """Look up by ISSN."""
        return self._lookup("issn", issn, full)

    def lookup_htid(self, htid: str, full: bool = False) -> Optional[Dict]:
        """Look up by HathiTrust volume ID (e.g., mdp.39015058510069)."""
        return self._lookup("htid", htid, full)

    def lookup_recordnumber(self, recnum: str, full: bool = False) -> Optional[Dict]:
        """Look up by HathiTrust 9-digit record number."""
        return self._lookup("recordnumber", recnum, full)

    # ── Batch Lookups ──

    def batch_lookup(
        self, identifiers: List[Tuple[str, str]], full: bool = False
    ) -> Dict[str, Optional[Dict]]:
        """
        Look up multiple identifiers in one request (max 20).

        identifiers: list of (id_type, id_value) tuples
        Returns: dict mapping "id_type:id_value" to response or None
        """
        if len(identifiers) > 20:
            raise ValueError("Max 20 identifiers per batch request")
        for id_type, _ in identifiers:
            if id_type not in VALID_ID_TYPES:
                raise ValueError(f"Invalid id_type: {id_type}")

        specs = "|".join(f"{t}:{urllib.parse.quote(str(v), safe='')}" for t, v in identifiers)
        variant = "full" if full else "brief"
        url = f"{BASE_URL}/{variant}/json/{specs}"
        data = self._get_json(url)

        results = {}
        for id_type, id_value in identifiers:
            key = f"{id_type}:{id_value}"
            # The API keys results by the search spec
            entry = data.get(key)
            if entry and entry.get("records"):
                results[key] = entry
            else:
                results[key] = None
        return results

    # ── Record Extraction Helpers ──

    @staticmethod
    def get_records(response: Dict) -> List[Dict]:
        """Extract all record dicts from an API response."""
        return list(response.get("records", {}).values())

    @staticmethod
    def get_items(response: Dict) -> List[Dict]:
        """Extract all item dicts from an API response."""
        return response.get("items", [])

    @staticmethod
    def get_first_record(response: Dict) -> Optional[Dict]:
        """Get the first (usually only) record from a response."""
        records = response.get("records", {})
        if records:
            return next(iter(records.values()))
        return None

    @staticmethod
    def get_title(record: Dict) -> str:
        """Extract the primary title from a record dict."""
        titles = record.get("titles", [])
        return titles[0] if titles else ""

    @staticmethod
    def get_isbns(record: Dict) -> List[str]:
        return record.get("isbns", [])

    @staticmethod
    def get_oclcs(record: Dict) -> List[str]:
        return record.get("oclcs", [])

    @staticmethod
    def get_lccns(record: Dict) -> List[str]:
        return record.get("lccns", [])

    @staticmethod
    def get_publish_dates(record: Dict) -> List[str]:
        return record.get("publishDates", [])

    @staticmethod
    def get_marc_xml(response: Dict) -> Optional[str]:
        """Extract MARC-XML from a /full/ response. Returns None if not present."""
        for rec in response.get("records", {}).values():
            marc = rec.get("marc-xml")
            if marc:
                return marc
        return None

    @staticmethod
    def has_full_view(response: Dict) -> bool:
        """Check if any item in the response has full-view access."""
        for item in response.get("items", []):
            if item.get("rightsCode") == "pd" or item.get("usRightsString") == "Full View":
                return True
        return False

    @staticmethod
    def get_full_view_url(response: Dict) -> Optional[str]:
        """Get the URL of the first full-view item, if any."""
        for item in response.get("items", []):
            if item.get("rightsCode") == "pd" or item.get("usRightsString") == "Full View":
                return item.get("itemURL")
        return None

    def summarize(self, response: Dict) -> Dict[str, Any]:
        """
        Summarize an API response into a clean dict.

        Returns: {title, isbns, oclcs, lccns, publish_dates, record_url,
                  num_items, has_full_view, full_view_url, holding_libraries}
        """
        record = self.get_first_record(response)
        items = self.get_items(response)

        libraries = list({item.get("orig", "") for item in items if item.get("orig")})

        return {
            "title": self.get_title(record) if record else "",
            "isbns": self.get_isbns(record) if record else [],
            "oclcs": self.get_oclcs(record) if record else [],
            "lccns": self.get_lccns(record) if record else [],
            "publish_dates": self.get_publish_dates(record) if record else [],
            "record_url": record.get("recordURL", "") if record else "",
            "num_items": len(items),
            "has_full_view": self.has_full_view(response),
            "full_view_url": self.get_full_view_url(response),
            "holding_libraries": libraries,
        }


if __name__ == "__main__":
    ht = HathiTrustAPI()

    # Example: Look up The Odyssey by Fagles (Penguin Classics)
    print("=== ISBN lookup: 0140268863 (Odyssey, Fagles) ===")
    result = ht.lookup_isbn("0140268863")
    if result:
        s = ht.summarize(result)
        print(f"  Title: {s['title']}")
        print(f"  Published: {', '.join(s['publish_dates'])}")
        print(f"  ISBNs: {s['isbns']}")
        print(f"  Items: {s['num_items']} volumes")
        print(f"  Full view: {s['has_full_view']}")
        print(f"  Libraries: {', '.join(s['holding_libraries'][:5])}")
    else:
        print("  No results found")

    print()

    # Example: Batch lookup
    print("=== Batch lookup ===")
    batch = ht.batch_lookup([
        ("isbn", "0140268863"),
        ("oclc", "34228839"),
    ])
    for key, resp in batch.items():
        if resp:
            rec = ht.get_first_record(resp)
            print(f"  {key}: {ht.get_title(rec)}")
        else:
            print(f"  {key}: not found")
