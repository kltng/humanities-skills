#!/usr/bin/env python3
"""
JBDB API client for querying the Japan Biographical Database.
Zero external dependencies — uses only Python stdlib.
"""

import json
import time
import urllib.parse
import urllib.request
from typing import Optional, Any
from urllib.error import HTTPError, URLError


class JBDBAPI:
    """Client for the Japan Biographical Database API."""

    BASE_URL = "https://jbdb.jp/api"

    def __init__(self, min_request_interval: float = 1.0, max_retries: int = 3):
        self._last_request_time = 0.0
        self._min_request_interval = min_request_interval
        self._max_retries = max_retries
        self._nengo_cache: dict[int, dict] = {}

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _request(self, path: str, filter_obj: Optional[dict] = None, timeout: int = 30) -> Any:
        url = f"{self.BASE_URL}/{path}"
        if filter_obj:
            filter_json = json.dumps(filter_obj, ensure_ascii=False)
            url += f"?filter={urllib.parse.quote(filter_json)}"

        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            self._rate_limit()
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except HTTPError as e:
                if e.code == 404:
                    return None
                last_error = e
                time.sleep(min(8.0, 0.5 * (2 ** attempt)))
            except URLError as e:
                last_error = e
                time.sleep(min(8.0, 0.5 * (2 ** attempt)))

        if last_error:
            raise last_error
        raise RuntimeError("Request failed")

    # ── Person queries ──────────────────────────────────────────

    def query_by_id(self, person_id: int) -> Optional[dict]:
        """Query JBDB by person ID. Returns the BiogMain dict or None."""
        return self._request(f"BiogMains/{person_id}")

    def search_by_name(self, name: str, limit: int = 20) -> list[dict]:
        """Search across all name fields (Japanese, furigana, romaji).
        Returns a list of matching BiogMain dicts."""
        escaped = name.replace("/", "\\/")
        filter_obj = {
            "where": {
                "or": [
                    {"cName": {"regexp": f"/{escaped}/i"}},
                    {"cNameFurigana": {"regexp": f"/{escaped}/i"}},
                    {"cNameRomaji": {"regexp": f"/{escaped}/i"}},
                ]
            },
            "limit": limit,
        }
        result = self._request("BiogMains", filter_obj)
        return result if isinstance(result, list) else []

    def search_by_exact_name(self, name: str) -> list[dict]:
        """Search by exact Japanese name match."""
        filter_obj = {"where": {"cName": name}}
        result = self._request("BiogMains", filter_obj)
        return result if isinstance(result, list) else []

    # ── Related data queries ────────────────────────────────────

    def get_alt_names(self, person_id: int) -> list[dict]:
        """Get alternative names for a person."""
        result = self._request("AltnameData", {"where": {"cPersonid": person_id}})
        return result if isinstance(result, list) else []

    def get_kinship(self, person_id: int) -> list[dict]:
        """Get kinship (family) relations for a person."""
        result = self._request("KinData", {"where": {"cPersonid": person_id}})
        return result if isinstance(result, list) else []

    def get_nonkinship(self, person_id: int) -> list[dict]:
        """Get non-kinship associations for a person."""
        result = self._request("NonkinData", {"where": {"cPersonid": person_id}})
        return result if isinstance(result, list) else []

    def get_events(self, person_id: int) -> list[dict]:
        """Get events involving a person."""
        result = self._request("EventData", {"where": {"cPersonid": person_id}})
        return result if isinstance(result, list) else []

    def get_personal_history(self, person_id: int) -> list[dict]:
        """Get personal history records for a person."""
        result = self._request("PersonalHistoryData", {"where": {"cPersonid": person_id}})
        return result if isinstance(result, list) else []

    def get_sources(self, person_id: int) -> list[dict]:
        """Get source documents linked to a person."""
        result = self._request("PersonsToSources", {"where": {"cPersonid": person_id}})
        return result if isinstance(result, list) else []

    # ── Lookup tables ───────────────────────────────────────────

    def resolve_nengo(self, nengo_code: int) -> Optional[dict]:
        """Resolve a nengo code to era name and start year."""
        if nengo_code in self._nengo_cache:
            return self._nengo_cache[nengo_code]
        result = self._request(f"NengoCodes/{nengo_code}")
        if result:
            self._nengo_cache[nengo_code] = result
        return result

    def resolve_occupation(self, code: int) -> Optional[dict]:
        """Resolve an occupation code."""
        return self._request(f"OccupationCodes/{code}")

    def resolve_place(self, code: int) -> Optional[dict]:
        """Resolve a place code."""
        return self._request(f"PlaceCodes/{code}")

    def resolve_kinship_code(self, code: int) -> Optional[dict]:
        """Resolve a kinship type code."""
        return self._request(f"KinshipCodes/{code}")

    def resolve_nonkinship_code(self, code: int) -> Optional[dict]:
        """Resolve a non-kinship type code."""
        return self._request(f"NonkinshipCodes/{code}")

    # ── Date conversion ─────────────────────────────────────────

    def nengo_to_western(self, nengo_code: int, nengo_year: int) -> Optional[int]:
        """Convert a nengo era code + year to a Western calendar year."""
        nengo = self.resolve_nengo(nengo_code)
        if not nengo:
            return None
        start = nengo.get("cStartYearMinusOne")
        if start is None:
            return None
        return int(start) + int(nengo_year)

    # ── Summary ─────────────────────────────────────────────────

    def summarize(self, person: dict) -> str:
        """Generate a formatted biographical summary."""
        lines = []

        name = person.get("cName", "")
        romaji = person.get("cNameRomaji", "")
        person_id = person.get("cPersonid", "")
        lines.append(f"# {name} ({romaji}) — JBDB ID {person_id}")

        # Dates
        birth_nengo = person.get("cByNengoCode")
        birth_year = person.get("cByNengoYear")
        death_nengo = person.get("cDyNengoCode")
        death_year = person.get("cDyNengoYear")

        birth_western = None
        death_western = None
        birth_era = ""
        death_era = ""

        if birth_nengo and birth_year:
            birth_western = self.nengo_to_western(birth_nengo, birth_year)
            nengo_info = self.resolve_nengo(birth_nengo)
            if nengo_info:
                birth_era = f"{nengo_info.get('cNengoName', '')} {birth_year}"

        if death_nengo and death_year:
            death_western = self.nengo_to_western(death_nengo, death_year)
            nengo_info = self.resolve_nengo(death_nengo)
            if nengo_info:
                death_era = f"{nengo_info.get('cNengoName', '')} {death_year}"

        birth_str = str(birth_western) if birth_western else "?"
        death_str = str(death_western) if death_western else "?"
        lines.append(f"\n**Dates:** {birth_str}–{death_str}  ")

        if birth_era or death_era:
            lines.append(f"**Era dates:** {birth_era or '?'}–{death_era or '?'}  ")

        gender = "Female" if person.get("cFemale") else "Male"
        lines.append(f"**Gender:** {gender}  ")

        death_age = person.get("cDeathAge")
        if death_age:
            lines.append(f"**Death age:** {death_age}  ")

        notes = person.get("cNotes")
        if notes:
            lines.append(f"\n**Notes:** {notes}")

        # Occupations
        occ_codes = person.get("cOccupationCodes", [])
        if occ_codes:
            lines.append("\n## Occupations")
            for code in occ_codes:
                occ = self.resolve_occupation(code)
                if occ:
                    desc = occ.get("cOccupationDescTrans") or occ.get("cOccupationDesc", "")
                    lines.append(f"- {desc}")

        # Alt names
        alt_names = self.get_alt_names(person.get("cPersonid", 0))
        if alt_names:
            lines.append("\n## Alternative Names")
            for an in alt_names:
                name_val = an.get("cAltName", "")
                romaji_val = an.get("cAltNameRomaji", "")
                display = f"{name_val} ({romaji_val})" if romaji_val else name_val
                if display:
                    lines.append(f"- {display}")

        # Kinship
        kin = self.get_kinship(person.get("cPersonid", 0))
        if kin:
            lines.append(f"\n## Kinship Relations ({len(kin)} records)")
            for k in kin[:20]:
                kin_code = k.get("cKinCode")
                kin_id = k.get("cKinId")
                rel_info = self.resolve_kinship_code(kin_code) if kin_code else None
                rel_name = ""
                if rel_info:
                    rel_name = rel_info.get("cKinrelTrans") or rel_info.get("cKinrel", "")
                lines.append(f"- {rel_name} → person ID {kin_id}")
            if len(kin) > 20:
                lines.append(f"- ... and {len(kin) - 20} more")

        return "\n".join(lines)


def main():
    api = JBDBAPI()

    print("=== Search by name: Matsuo Basho ===")
    persons = api.search_by_name("Matsuo Basho")
    if persons:
        print(f"Found {len(persons)} result(s)")
        print(api.summarize(persons[0]))
    else:
        print("Not found")


if __name__ == "__main__":
    main()
