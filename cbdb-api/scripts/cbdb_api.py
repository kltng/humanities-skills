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
    DEFAULT_USER_AGENT = "CBDBAPISkill/1.1 (https://github.com/kltng/humanities-skills)"

    def __init__(self, min_request_interval: float = 1.0, max_retries: int = 3,
                 user_agent: str = DEFAULT_USER_AGENT):
        self._last_request_time = 0.0
        self._min_request_interval = min_request_interval
        self._max_retries = max_retries
        self._user_agent = user_agent

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    @staticmethod
    def _retry_after(e: HTTPError, default: float) -> float:
        value = e.headers.get("Retry-After") if e.headers else None
        try:
            return min(60.0, max(default, float(value)))
        except (TypeError, ValueError):
            return default

    def _request(self, params: dict, timeout: int = 30) -> Any:
        params = dict(params)
        params.setdefault("o", "json")
        # urlencode percent-encodes the UTF-8 bytes of Chinese text correctly.
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            self._rate_limit()
            req = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except HTTPError as e:
                backoff = min(8.0, 0.5 * (2 ** attempt))
                if e.code in (429, 503):
                    last_error = e
                    time.sleep(self._retry_after(e, backoff))
                    continue
                if 400 <= e.code < 500:
                    # "Person not found" (404) and bad input (422) come back as a
                    # JSON {"error": ...} body; return it instead of retrying.
                    try:
                        return json.loads(e.read().decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        raise e
                last_error = e
                time.sleep(backoff)
            except URLError as e:
                last_error = e
                time.sleep(min(8.0, 0.5 * (2 ** attempt)))

        if last_error:
            raise last_error
        raise RuntimeError("Request failed")

    def _extract_persons(self, data: Any) -> list[dict]:
        """Navigate the nested CBDB JSON to the Person object(s).

        `Person` is a dict for one match and may be a list for several.
        """
        try:
            person = data["Package"]["PersonAuthority"]["PersonInfo"]["Person"]
        except (KeyError, TypeError):
            return []
        if isinstance(person, dict):
            return [person]
        if isinstance(person, list):
            return [p for p in person if isinstance(p, dict)]
        return []

    def query_by_id(self, person_id: int) -> Optional[dict]:
        """Query CBDB by person ID. Returns the Person dict or None."""
        persons = self._extract_persons(self._request({"id": person_id}))
        return persons[0] if persons else None

    def query_by_name(self, name: str) -> Optional[dict]:
        """Query CBDB by name (Chinese characters or Pinyin).

        Returns the first matching Person dict or None. Use query_by_name_all()
        to get every match when a name is ambiguous.
        """
        persons = self.query_by_name_all(name)
        return persons[0] if persons else None

    def query_by_name_all(self, name: str) -> list[dict]:
        """Query CBDB by name and return all matching Person dicts (may be empty)."""
        return self._extract_persons(self._request({"name": name}))

    def name_match(self, person: dict, name: str) -> str:
        """Say how `name` matched the returned person.

        "primary": the main Chinese or English name.
        "alias": exactly one of the person's alternative names (字, 號 ...).
            The API then returns only one person, even when several people
            share that alt name, so check the result.
        "other": neither (e.g. the API matched part of an alt name).
        """
        basic = self.get_basic_info(person)
        query = name.strip().casefold()
        if query in {str(basic.get(k, "")).strip().casefold() for k in ("ChName", "EngName")}:
            return "primary"
        aliases = {str(a.get("AliasName", "")).strip().casefold() for a in self.get_alt_names(person)}
        return "alias" if query in aliases else "other"

    @staticmethod
    def _section_list(person: dict, section: str, key: str) -> list:
        """Return person[section][key] as a list.

        CBDB returns an empty string for empty sections, a dict for a single
        record, and a list for several records.
        """
        info = person.get(section)
        if not isinstance(info, dict):
            return []
        items = info.get(key, [])
        if isinstance(items, dict):
            return [items]
        return items if isinstance(items, list) else []

    def get_basic_info(self, person: dict) -> dict:
        """Extract BasicInfo fields from a Person dict."""
        basic = person.get("BasicInfo")
        return basic if isinstance(basic, dict) else {}

    def get_postings(self, person: dict) -> list:
        """Extract official postings (PersonPostings.Posting)."""
        return self._section_list(person, "PersonPostings", "Posting")

    def get_social_associations(self, person: dict) -> list:
        """Extract social associations (PersonSocialAssociation.Association)."""
        return self._section_list(person, "PersonSocialAssociation", "Association")

    def get_kinship(self, person: dict) -> list:
        """Extract kinship relations (PersonKinshipInfo.Kinship)."""
        return self._section_list(person, "PersonKinshipInfo", "Kinship")

    def get_alt_names(self, person: dict) -> list:
        """Extract alternative names, e.g. courtesy/pen names (PersonAliases.Alias)."""
        return self._section_list(person, "PersonAliases", "Alias")

    def get_entries(self, person: dict) -> list:
        """Extract examination entries and ranks (PersonEntryInfo.Entry)."""
        return self._section_list(person, "PersonEntryInfo", "Entry")

    def get_addresses(self, person: dict) -> list:
        """Extract addresses (PersonAddresses.Address)."""
        return self._section_list(person, "PersonAddresses", "Address")

    @staticmethod
    def _count_label(shown: int, total: int) -> str:
        if shown < total:
            return f"{total} records, first {shown} shown"
        return f"{total} records"

    def summarize(self, person: dict, max_items: Optional[int] = 20) -> str:
        """Generate a formatted biographical summary.

        Lists at most `max_items` postings and associations (None = all) and
        says how many were left out.
        """
        basic = self.get_basic_info(person)
        lines: list[str] = []

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
                name_type = an.get("AliasType", "")
                name_val = an.get("AliasName", "")
                if name_val:
                    lines.append(f"- {name_type}: {name_val}")

        postings = self.get_postings(person)
        if postings:
            shown = postings if max_items is None else postings[:max_items]
            lines.append(f"\n## Official Positions ({self._count_label(len(shown), len(postings))})")
            for p in shown:
                office = p.get("OfficeName", "")
                year = p.get("FirstYear", "")
                # CBDB uses "0" for an unknown year.
                lines.append(f"- {office} ({year})" if year and year != "0" else f"- {office}")
            if len(postings) > len(shown):
                lines.append(f"- ... and {len(postings) - len(shown)} more")

        assocs = self.get_social_associations(person)
        if assocs:
            shown = assocs if max_items is None else assocs[:max_items]
            lines.append(f"\n## Social Associations ({self._count_label(len(shown), len(assocs))})")
            for a in shown:
                assoc_name = a.get("AssocPersonName", "")
                assoc_type = a.get("AssocName", "")
                lines.append(f"- {assoc_name} ({assoc_type})")
            if len(assocs) > len(shown):
                lines.append(f"- ... and {len(assocs) - len(shown)} more")

        return "\n".join(lines)


def main() -> None:
    api = CBDBAPI()

    print("=== Query by name: 蘇軾 ===")
    person = api.query_by_name("蘇軾")
    if person:
        print(api.summarize(person))
    else:
        print("Not found")


if __name__ == "__main__":
    main()
