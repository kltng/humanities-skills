#!/usr/bin/env python3
"""
CBDB API client for querying the China Biographical Database.
Zero external dependencies — uses only Python stdlib.
"""

import json
import time
import urllib.parse
import urllib.request
from typing import Optional, Any
from urllib.error import HTTPError, URLError


class CBDBAPI:
    """Client for the China Biographical Database API."""

    BASE_URL = "https://cbdb.fas.harvard.edu/cbdbapi/person.php"

    def __init__(self, min_request_interval: float = 1.0, max_retries: int = 3):
        self._last_request_time = 0.0
        self._min_request_interval = min_request_interval
        self._max_retries = max_retries

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _request(self, params: dict, timeout: int = 30) -> Any:
        params = dict(params)
        params.setdefault("o", "json")
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

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

    def _extract_person(self, data: dict) -> Optional[dict]:
        """Navigate the deeply nested CBDB JSON response to the Person object."""
        try:
            return data["Package"]["PersonAuthority"]["PersonInfo"]["Person"]
        except (KeyError, TypeError):
            return None

    def query_by_id(self, person_id: int) -> Optional[dict]:
        """Query CBDB by person ID. Returns the Person dict or None."""
        data = self._request({"id": person_id})
        if "error" in data:
            return None
        return self._extract_person(data)

    def query_by_name(self, name: str) -> Optional[dict]:
        """Query CBDB by name (Chinese characters or Pinyin). Returns the Person dict or None."""
        data = self._request({"name": name})
        if "error" in data:
            return None
        return self._extract_person(data)

    def get_basic_info(self, person: dict) -> dict:
        """Extract BasicInfo fields from a Person dict."""
        return person.get("BasicInfo", {})

    def get_postings(self, person: dict) -> list:
        """Extract official postings from a Person dict."""
        info = person.get("PostingInfo", {})
        postings = info.get("Posting", [])
        if isinstance(postings, dict):
            return [postings]
        return postings

    def get_social_associations(self, person: dict) -> list:
        """Extract social associations from a Person dict."""
        info = person.get("SocialAssocInfo", {})
        assocs = info.get("SocialAssociation", [])
        if isinstance(assocs, dict):
            return [assocs]
        return assocs

    def get_kinship(self, person: dict) -> list:
        """Extract kinship relations from a Person dict."""
        info = person.get("KinshipInfo", {})
        kin = info.get("Kinship", [])
        if isinstance(kin, dict):
            return [kin]
        return kin

    def get_alt_names(self, person: dict) -> list:
        """Extract alternative names (courtesy name, pen name, etc.)."""
        info = person.get("AltNameInfo", {})
        names = info.get("AltName", [])
        if isinstance(names, dict):
            return [names]
        return names

    def get_entries(self, person: dict) -> list:
        """Extract examination entries and ranks."""
        info = person.get("EntryInfo", {})
        entries = info.get("Entry", [])
        if isinstance(entries, dict):
            return [entries]
        return entries

    def summarize(self, person: dict) -> str:
        """Generate a formatted biographical summary."""
        basic = self.get_basic_info(person)
        lines = []

        ch_name = basic.get("ChName", "")
        eng_name = basic.get("EngName", "")
        person_id = basic.get("PersonId", "")
        lines.append(f"# {ch_name} ({eng_name}) — CBDB ID {person_id}")

        dynasty = basic.get("Dynasty", "")
        birth = basic.get("YearBirth", "?")
        death = basic.get("YearDeath", "?")
        lines.append(f"\n**Dynasty:** {dynasty}  ")
        lines.append(f"**Dates:** {birth}–{death}  ")

        alt_names = self.get_alt_names(person)
        if alt_names:
            lines.append("\n## Alternative Names")
            for an in alt_names:
                name_type = an.get("AltNameType", "")
                name_val = an.get("AltNameCh", "") or an.get("AltNameEng", "")
                if name_val:
                    lines.append(f"- {name_type}: {name_val}")

        postings = self.get_postings(person)
        if postings:
            lines.append(f"\n## Official Positions ({len(postings)} records)")
            for p in postings[:20]:
                office = p.get("OfficeCh", "") or p.get("OfficeEng", "")
                year = p.get("FirstYear", "")
                lines.append(f"- {office} ({year})" if year else f"- {office}")
            if len(postings) > 20:
                lines.append(f"- ... and {len(postings) - 20} more")

        assocs = self.get_social_associations(person)
        if assocs:
            lines.append(f"\n## Social Associations ({len(assocs)} records)")
            for a in assocs[:20]:
                assoc_name = a.get("AssocName", "")
                assoc_type = a.get("AssocType", "")
                lines.append(f"- {assoc_name} ({assoc_type})")
            if len(assocs) > 20:
                lines.append(f"- ... and {len(assocs) - 20} more")

        return "\n".join(lines)


def main():
    api = CBDBAPI()

    print("=== Query by name: 蘇軾 ===")
    person = api.query_by_name("蘇軾")
    if person:
        print(api.summarize(person))
    else:
        print("Not found")


if __name__ == "__main__":
    main()
