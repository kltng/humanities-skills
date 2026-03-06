"""
Harvard Library API client — zero external dependencies.

Wraps LibraryCloud Item API and PRESTO Data Lookup for searching and
retrieving bibliographic records from Harvard Library's 13M+ catalog.
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple


LIBRARYCLOUD_BASE = "https://api.lib.harvard.edu/v2"
PRESTO_BASE = "https://webservices.lib.harvard.edu/rest"

# LibraryCloud fields that support field-based query params
SEARCH_FIELDS = {
    "q", "title", "name", "subject", "identifier", "genre",
    "languageCode", "languageText", "dateIssued", "dateCreated",
    "copyrightDate", "originDate", "originPlace", "publisher",
    "classification", "recordIdentifier", "repository",
    "physicalLocation", "resourceType", "role", "edition",
    "issuance", "isOnline", "isCollection", "isManuscript",
    "abstractTOC", "collectionId", "collectionTitle", "seriesTitle",
    "shelfLocator", "source", "url", "urn",
    "subject.topic", "subject.geographic", "subject.temporal",
    "subject.name", "subject.genre", "subject.titleInfo",
    "subject.hierarchicalGeographic",
    "dates.start", "dates.end",
    # DRS extensions
    "inDRS", "accessFlag", "contentModel", "digitalFormat",
    "availableTo", "drsFileId", "drsObjectId", "ownerCode",
}

# Fields that support _exact suffix
EXACT_FIELDS = {
    "title", "subject", "genre", "identifier", "name",
    "dateIssued", "dateCreated", "copyrightDate", "originDate",
    "originPlace", "publisher", "classification", "edition",
    "languageCode", "languageText", "recordIdentifier",
    "repository", "resourceType", "role", "issuance",
    "collectionId", "collectionTitle", "seriesTitle",
    "shelfLocator", "source", "url",
    "subject.topic", "subject.geographic", "subject.temporal",
    "subject.name", "subject.genre", "subject.titleInfo",
}


class HarvardLibraryAPI:
    """Client for Harvard Library APIs (LibraryCloud + PRESTO)."""

    def __init__(self, min_interval: float = 1.0):
        self._min_interval = min_interval
        self._last_request = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.time()

    def _get(self, url: str, accept: str = "application/json") -> bytes:
        self._rate_limit()
        req = urllib.request.Request(url, headers={
            "Accept": accept,
            "User-Agent": "HarvardLibrarySkill/1.0 (Claude Code skill; research use)",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # Rate limited — wait and retry once
                time.sleep(300)
                self._rate_limit()
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.read()
            raise

    def _get_json(self, url: str) -> Dict[str, Any]:
        data = self._get(url)
        return json.loads(data)

    # ── LibraryCloud Item API ──

    def search(self, limit: int = 10, start: int = 0, **fields) -> List[Dict]:
        """
        Search LibraryCloud items using field-based parameters.

        Pass any search field as a keyword argument:
            search(title="hamlet", name="shakespeare", languageCode="eng")
            search(q="Chinese porcelain Ming dynasty")

        Returns a list of MODS records (dicts).
        """
        params = {}
        for key, val in fields.items():
            if key in SEARCH_FIELDS or key.endswith("_exact"):
                params[key] = val
            else:
                raise ValueError(f"Unknown search field: {key}. Use q= for keyword search.")
        params["limit"] = str(limit)
        if start > 0:
            params["start"] = str(start)

        qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = f"{LIBRARYCLOUD_BASE}/items.json?{qs}"
        data = self._get_json(url)

        items = data.get("items") or {}
        mods = items.get("mods") or []
        if isinstance(mods, dict):
            mods = [mods]
        return mods

    def search_with_facets(
        self, facets: List[str], limit: int = 10, **fields
    ) -> Tuple[List[Dict], Dict[str, List[Dict]]]:
        """
        Search with facets. Returns (records, facet_dict).
        facet_dict maps facet name to list of {value, count} dicts.
        """
        params = {}
        for key, val in fields.items():
            if key in SEARCH_FIELDS or key.endswith("_exact"):
                params[key] = str(val)
        params["limit"] = str(limit)
        params["facets"] = ",".join(facets)

        qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote, safe=",")
        url = f"{LIBRARYCLOUD_BASE}/items.json?{qs}"
        data = self._get_json(url)

        items = data.get("items") or {}
        mods = items.get("mods") or []
        if isinstance(mods, dict):
            mods = [mods]

        facet_data = {}
        raw_facets = data.get("facets") or {}
        if isinstance(raw_facets, dict):
            facet_list = raw_facets.get("facetField") or []
            if isinstance(facet_list, dict):
                facet_list = [facet_list]
            for f in facet_list:
                name = f.get("facetName", "")
                values = f.get("facet") or []
                if isinstance(values, dict):
                    values = [values]
                facet_data[name] = [
                    {"value": v.get("term", ""), "count": v.get("count", 0)}
                    for v in values
                ]

        return mods, facet_data

    def search_all(self, max_results: int = 1000, **fields) -> List[Dict]:
        """
        Paginate through all results up to max_results.
        Uses start-based pagination (works up to ~30K results).
        """
        all_records = []
        page_size = min(250, max_results)
        start = 0

        while len(all_records) < max_results:
            batch = self.search(limit=page_size, start=start, **fields)
            if not batch:
                break
            all_records.extend(batch)
            start += page_size
            if len(batch) < page_size:
                break

        return all_records[:max_results]

    def get_num_found(self, **fields) -> int:
        """Return total number of matching records without fetching them."""
        params = {}
        for key, val in fields.items():
            if key in SEARCH_FIELDS or key.endswith("_exact"):
                params[key] = val
        params["limit"] = "0"

        qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = f"{LIBRARYCLOUD_BASE}/items.json?{qs}"
        data = self._get_json(url)
        return int(data.get("pagination", {}).get("numFound", 0))

    # ── PRESTO Data Lookup ──

    def get_presto_record(self, hollis_id: str, format: str = "mods") -> str:
        """
        Retrieve a catalog record by HOLLIS ID via PRESTO.

        format: "marc", "mods", or "dc"
        Returns raw XML string.
        """
        if format not in ("marc", "mods", "dc"):
            raise ValueError(f"Unsupported format: {format}. Use marc, mods, or dc.")
        url = f"{PRESTO_BASE}/{format}/hollis/{hollis_id}"
        data = self._get(url, accept="application/xml")
        return data.decode("utf-8")

    # ── Record Extraction Helpers ──

    @staticmethod
    def get_title(record: Dict) -> str:
        """Extract title from a MODS record."""
        ti = record.get("titleInfo", {})
        if isinstance(ti, list):
            ti = ti[0]
        parts = []
        non_sort = ti.get("nonSort", "")
        if non_sort:
            parts.append(non_sort.strip())
        title = ti.get("title", "")
        if title:
            parts.append(title)
        subtitle = ti.get("subTitle", "")
        if subtitle:
            parts.append(f": {subtitle}")
        return " ".join(parts).strip()

    @staticmethod
    def get_names(record: Dict) -> List[str]:
        """Extract all names (authors, editors, etc.) from a MODS record."""
        names_raw = record.get("name", [])
        if isinstance(names_raw, dict):
            names_raw = [names_raw]
        results = []
        for n in names_raw:
            np = n.get("namePart", "")
            if isinstance(np, list):
                # Filter to string parts only (skip date dicts etc.)
                parts = []
                for p in np:
                    if isinstance(p, str):
                        parts.append(p)
                    elif isinstance(p, dict) and p.get("@type") != "date":
                        parts.append(p.get("#text", ""))
                np = " ".join(parts)
            if isinstance(np, dict):
                np = np.get("#text", "")
            if np:
                results.append(str(np).strip())
        return results

    @staticmethod
    def get_date(record: Dict) -> str:
        """Extract publication date from a MODS record."""
        origin = record.get("originInfo", {})
        if isinstance(origin, list):
            origin = origin[0]
        for field in ("dateIssued", "dateCreated", "copyrightDate"):
            val = origin.get(field)
            if val:
                if isinstance(val, list):
                    # Prefer the plain string version over the encoded one
                    for v in val:
                        if isinstance(v, str):
                            return v
                    return str(val[0]) if val else ""
                if isinstance(val, dict):
                    return val.get("#text", "")
                return str(val)
        return ""

    @staticmethod
    def get_publisher(record: Dict) -> str:
        """Extract publisher from a MODS record."""
        origin = record.get("originInfo", {})
        if isinstance(origin, list):
            origin = origin[0]
        pub = origin.get("publisher", "")
        if isinstance(pub, list):
            return pub[0] if pub else ""
        return str(pub)

    @staticmethod
    def get_subjects(record: Dict) -> List[str]:
        """Extract subject terms from a MODS record."""
        subjects_raw = record.get("subject", [])
        if isinstance(subjects_raw, dict):
            subjects_raw = [subjects_raw]
        results = []
        for s in subjects_raw:
            topic = s.get("topic", "")
            if isinstance(topic, list):
                results.extend(str(t) for t in topic)
            elif topic:
                results.append(str(topic))
            geo = s.get("geographic", "")
            if geo and isinstance(geo, str):
                results.append(geo)
        return results

    @staticmethod
    def get_identifiers(record: Dict) -> Dict[str, str]:
        """Extract identifiers (ISBN, LCCN, etc.) from a MODS record."""
        ids_raw = record.get("identifier", [])
        if isinstance(ids_raw, dict):
            ids_raw = [ids_raw]
        result = {}
        for ident in ids_raw:
            if isinstance(ident, dict):
                id_type = ident.get("@type", "unknown")
                id_val = ident.get("#text", "")
                if id_val:
                    result[id_type] = str(id_val)
            elif isinstance(ident, str):
                result["id"] = ident
        return result

    @staticmethod
    def get_record_id(record: Dict) -> Optional[str]:
        """Extract the HOLLIS/Alma record identifier for PRESTO lookups."""
        ri = record.get("recordInfo", {})
        if isinstance(ri, list):
            ri = ri[0]
        rec_id = ri.get("recordIdentifier", "")
        if isinstance(rec_id, dict):
            return rec_id.get("#text", "")
        if isinstance(rec_id, list):
            for r in rec_id:
                if isinstance(r, dict):
                    return r.get("#text", "")
                return str(r)
        return str(rec_id) if rec_id else None

    @staticmethod
    def get_language(record: Dict) -> str:
        """Extract language text from a MODS record."""
        lang = record.get("language", {})
        if isinstance(lang, list):
            lang = lang[0]
        terms = lang.get("languageTerm", [])
        if isinstance(terms, dict):
            terms = [terms]
        for t in terms:
            if isinstance(t, dict) and t.get("@type") == "text":
                return t.get("#text", "")
        # Fallback to code
        for t in terms:
            if isinstance(t, dict):
                return t.get("#text", "")
        return ""

    def summarize(self, record: Dict) -> Dict[str, Any]:
        """
        Extract key bibliographic fields into a clean summary dict.

        Returns: {title, authors, date, publisher, language, subjects,
                  identifiers, record_id, physical_description}
        """
        phys = record.get("physicalDescription", {})
        if isinstance(phys, list):
            phys = phys[0]
        extent = phys.get("extent", "")
        if isinstance(extent, dict):
            extent = extent.get("#text", "")

        return {
            "title": self.get_title(record),
            "authors": self.get_names(record),
            "date": self.get_date(record),
            "publisher": self.get_publisher(record),
            "language": self.get_language(record),
            "subjects": self.get_subjects(record),
            "identifiers": self.get_identifiers(record),
            "record_id": self.get_record_id(record),
            "physical_description": str(extent),
        }


if __name__ == "__main__":
    api = HarvardLibraryAPI()

    # Example: search for Hamlet by Shakespeare
    print("=== Searching for Hamlet by Shakespeare ===")
    results = api.search(title="hamlet", name="shakespeare", limit=3)
    for r in results:
        s = api.summarize(r)
        print(f"  {s['title']} ({s['date']}) — {', '.join(s['authors'][:2])}")
        if s['identifiers']:
            print(f"    IDs: {s['identifiers']}")
    print()

    # Example: faceted search
    print("=== Chinese rare books by genre ===")
    records, facets = api.search_with_facets(
        facets=["genre", "languageCode"],
        q="Chinese rare books",
        limit=2
    )
    for name, vals in facets.items():
        print(f"  {name}:")
        for v in vals[:5]:
            print(f"    {v['value']}: {v['count']}")
