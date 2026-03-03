#!/usr/bin/env python3
"""
Wikidata API client for searching items and retrieving identifiers.
"""

import json
import os
import time
import urllib.parse
import urllib.request
import gzip
from typing import Optional, Iterable, Any
from urllib.error import HTTPError, URLError


class WikidataAPI:
    """Client for Wikidata API operations."""
    
    BASE_URL = "https://www.wikidata.org/w/api.php"

    # EntityData (often faster for current entity JSON than Action API)
    ENTITYDATA_URL = "https://www.wikidata.org/wiki/Special:EntityData"

    # Wikidata Query Service (SPARQL)
    WDQS_URL = "https://query.wikidata.org/sparql"

    # Wikidata Vector Database
    VDB_BASE_URL = "https://wd-vectordb.wmcloud.org"
    
    # Common external identifier properties
    IDENTIFIER_PROPERTIES = {
        "P214": "VIAF ID",
        "P227": "GND ID", 
        "P244": "Library of Congress ID",
        "P213": "ISNI",
        "P345": "IMDb ID",
        "P646": "Freebase ID",
        "P349": "NDL ID",
        "P268": "BnF ID",
        "P269": "IdRef ID",
        "P906": "SELIBR ID",
        "P396": "SBN author ID",
        "P1566": "GeoNames ID",
        "P402": "OpenStreetMap relation ID",
        "P1015": "NORAF ID",
        "P950": "BNE ID",
        "P1006": "NTA ID",
        "P1017": "BAV ID",
        "P691": "NKC ID",
        "P409": "NLA ID",
        "P1273": "CANTIC ID",
        "P3430": "SNAC Ark ID",
        "P2163": "FAST ID",
        "P1953": "Discogs artist ID",
        "P1728": "AllMusic artist ID",
        "P434": "MusicBrainz artist ID",
        "P496": "ORCID iD",
    }

    def __init__(
        self,
        user_agent: str = "WikidataSearchSkill/1.0 (https://www.wikidata.org; contact: example@example.com)",
        min_request_interval: float = 0.5,
        max_retries: int = 4,
        maxlag: int = 5,
        vectordb_api_secret: Optional[str] = None,
    ):
        self.user_agent = user_agent
        self._last_request_time = 0
        self._min_request_interval = float(min_request_interval)
        self._max_retries = int(max_retries)
        self._maxlag = int(maxlag)
        self._vectordb_api_secret = (
            vectordb_api_secret
            if vectordb_api_secret is not None
            else os.environ.get("WIKIDATA_VECTORDB_API_SECRET")
        )
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _read_response_body(self, response) -> bytes:
        body = response.read()
        encoding = (response.headers.get("Content-Encoding") or "").lower()
        if encoding == "gzip":
            return gzip.decompress(body)
        return body

    def _request_json(
        self,
        base_url: str,
        params: dict,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 30,
        method: str = "GET",
    ) -> Any:
        """Make a JSON HTTP request with retry/backoff and basic etiquette."""
        params = dict(params)
        params.setdefault("format", "json")

        url = f"{base_url}?{urllib.parse.urlencode(params)}"

        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip,deflate",
            "Accept": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            self._rate_limit()

            req = urllib.request.Request(url, headers=headers, method=method)

            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    body = self._read_response_body(response)
                    return json.loads(body.decode("utf-8"))
            except HTTPError as e:
                last_error = e
                # Respect Retry-After on 429
                if e.code == 429:
                    retry_after = e.headers.get("Retry-After")
                    if retry_after:
                        try:
                            time.sleep(float(retry_after))
                            continue
                        except ValueError:
                            pass
                # Retry transient errors
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(min(8.0, 0.5 * (2**attempt)))
                    continue
                raise
            except URLError as e:
                last_error = e
                time.sleep(min(8.0, 0.5 * (2**attempt)))
                continue

        if last_error:
            raise last_error
        raise RuntimeError("Request failed without an exception")

    def _request(self, params: dict) -> dict:
        """Make Wikidata Action API request with rate limiting and retries."""
        params = dict(params)
        params.setdefault("maxlag", str(self._maxlag))
        params.setdefault("formatversion", "2")
        return self._request_json(self.BASE_URL, params)
    
    def search(
        self,
        query: str,
        language: str = "en",
        entity_type: str = "item",
        limit: int = 10,
        continue_offset: int = 0
    ) -> list[dict]:
        """
        Search for Wikidata entities by label or alias.
        
        Args:
            query: Search term
            language: Language code (default: en)
            entity_type: 'item' for Q-entities, 'property' for P-entities
            limit: Maximum results (1-50)
            continue_offset: Offset for pagination
            
        Returns:
            List of search results with id, label, description, aliases, url
        """
        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": language,
            "uselang": language,
            "type": entity_type,
            "limit": min(limit, 50),
        }
        if continue_offset > 0:
            params["continue"] = continue_offset
            
        response = self._request(params)
        return response.get("search", [])

    def vector_search_items(
        self,
        query: str,
        lang: str = "all",
        k: int = 20,
        instanceof: Optional[list[str]] = None,
        rerank: bool = False,
    ) -> list[dict]:
        """Hybrid (vector+keyword) search for Wikidata items via Wikidata Vector DB."""
        params: dict[str, object] = {
            "query": query,
            "lang": lang,
            "K": int(k),
            "rerank": bool(rerank),
        }
        if instanceof:
            params["instanceof"] = ",".join(instanceof)

        headers = {}
        if self._vectordb_api_secret:
            headers["X-API-SECRET"] = self._vectordb_api_secret

        url = f"{self.VDB_BASE_URL}/item/query/"
        data = self._request_json(url, params, extra_headers=headers, timeout=30)
        if not isinstance(data, list):
            raise ValueError("Unexpected Vector DB response (expected list)")
        return data

    def vector_search_properties(
        self,
        query: str,
        lang: str = "all",
        k: int = 20,
        rerank: bool = False,
        exclude_external_ids: bool = False,
    ) -> list[dict]:
        """Hybrid (vector+keyword) search for Wikidata properties via Wikidata Vector DB."""
        params: dict[str, object] = {
            "query": query,
            "lang": lang,
            "K": int(k),
            "rerank": bool(rerank),
            "exclude_external_ids": bool(exclude_external_ids),
        }

        headers = {}
        if self._vectordb_api_secret:
            headers["X-API-SECRET"] = self._vectordb_api_secret

        url = f"{self.VDB_BASE_URL}/property/query/"
        data = self._request_json(url, params, extra_headers=headers, timeout=30)
        if not isinstance(data, list):
            raise ValueError("Unexpected Vector DB response (expected list)")
        return data

    def similarity_score(
        self,
        query: str,
        qids: list[str],
        lang: str = "en",
    ) -> list[dict]:
        """Compute similarity scores (query vs specific entities) via Vector DB."""
        params: dict[str, object] = {
            "query": query,
            "qid": ",".join(qids),
            "lang": lang,
        }

        headers = {}
        if self._vectordb_api_secret:
            headers["X-API-SECRET"] = self._vectordb_api_secret

        url = f"{self.VDB_BASE_URL}/similarity-score/"
        data = self._request_json(url, params, extra_headers=headers, timeout=30)
        if not isinstance(data, list):
            raise ValueError("Unexpected Vector DB response (expected list)")
        return data
    
    def get_entity(
        self,
        entity_id: str,
        props: Optional[list[str]] = None,
        languages: Optional[list[str]] = None
    ) -> Optional[dict]:
        """
        Get full entity data.
        
        Args:
            entity_id: Wikidata ID (e.g., Q42)
            props: Properties to retrieve (labels, descriptions, aliases, claims, sitelinks, info)
            languages: Language codes to filter (e.g., ['en', 'fr'])
            
        Returns:
            Entity data dict or None if not found
        """
        return self.get_entities([entity_id], props, languages).get(entity_id)
    
    def get_entities(
        self,
        entity_ids: list[str],
        props: Optional[list[str]] = None,
        languages: Optional[list[str]] = None
    ) -> dict:
        """
        Get multiple entities (max 50 per request).
        
        Args:
            entity_ids: List of Wikidata IDs
            props: Properties to retrieve
            languages: Language codes to filter
            
        Returns:
            Dict mapping entity IDs to their data
        """
        if not entity_ids:
            return {}
            
        params = {
            "action": "wbgetentities",
            "ids": "|".join(entity_ids[:50]),
        }
        
        if props:
            params["props"] = "|".join(props)
        if languages:
            params["languages"] = "|".join(languages)
            
        response = self._request(params)
        entities = response.get("entities", {})
        
        # Filter out missing entities
        return {k: v for k, v in entities.items() if "missing" not in v}

    def get_entitydata(
        self,
        entity_id: str,
        flavor: str = "simple",
        revision: Optional[int] = None,
    ) -> dict:
        """
        Fetch entity JSON from Special:EntityData.

        flavor:
          - simple: truthy statements; includes sitelinks/version
          - full: full data
          - dump: excludes descriptions of referenced entities (RDF-focused)
        """
        allowed = {"simple", "full", "dump"}
        if flavor not in allowed:
            raise ValueError(f"Invalid flavor: {flavor}. Expected one of {sorted(allowed)}")

        url = f"{self.ENTITYDATA_URL}/{entity_id}.json"
        qs = {"flavor": flavor}
        if revision is not None:
            qs["revision"] = str(int(revision))
        full_url = f"{url}?{urllib.parse.urlencode(qs)}"

        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip,deflate",
            "Accept": "application/json",
        }

        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            self._rate_limit()
            req = urllib.request.Request(full_url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    body = self._read_response_body(response)
                    return json.loads(body.decode("utf-8"))
            except (HTTPError, URLError) as e:
                last_error = e
                time.sleep(min(8.0, 0.5 * (2**attempt)))
                continue

        if last_error:
            raise last_error
        raise RuntimeError("Request failed without an exception")
    
    def get_claims(
        self,
        entity_id: str,
        property_id: Optional[str] = None
    ) -> dict:
        """
        Get claims for an entity, optionally filtered by property.
        
        Args:
            entity_id: Wikidata ID (e.g., Q42)
            property_id: Optional property ID to filter (e.g., P31)
            
        Returns:
            Dict of claims keyed by property ID
        """
        params = {
            "action": "wbgetclaims",
            "entity": entity_id,
        }
        if property_id:
            params["property"] = property_id
            
        response = self._request(params)
        return response.get("claims", {})

    def execute_sparql(
        self,
        sparql: str,
        accept: str = "application/sparql-results+json",
        timeout: int = 30,
    ) -> bytes:
        """Execute SPARQL against WDQS and return raw response bytes."""
        params = {"query": sparql}
        url = f"{self.WDQS_URL}?{urllib.parse.urlencode(params)}"

        headers = {
            "User-Agent": self.user_agent,
            "Accept": accept,
            "Accept-Encoding": "gzip,deflate",
        }

        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            self._rate_limit()
            req = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return self._read_response_body(response)
            except HTTPError as e:
                last_error = e
                if e.code == 429:
                    retry_after = e.headers.get("Retry-After")
                    if retry_after:
                        try:
                            time.sleep(float(retry_after))
                            continue
                        except ValueError:
                            pass
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(min(8.0, 0.5 * (2**attempt)))
                    continue
                raise
            except URLError as e:
                last_error = e
                time.sleep(min(8.0, 0.5 * (2**attempt)))
                continue

        if last_error:
            raise last_error
        raise RuntimeError("Request failed without an exception")

    def sparql_json(
        self,
        sparql: str,
        timeout: int = 30,
    ) -> dict:
        """Execute SPARQL against WDQS and return parsed JSON results."""
        raw = self.execute_sparql(sparql, accept="application/sparql-results+json", timeout=timeout)
        return json.loads(raw.decode("utf-8"))

    def _property_labels(self, property_ids: Iterable[str], language: str = "en") -> dict[str, str]:
        ids = [pid for pid in property_ids if pid]
        if not ids:
            return {}
        entities = self.get_entities(ids[:50], props=["labels"], languages=[language])
        out: dict[str, str] = {}
        for pid, ent in entities.items():
            labels = ent.get("labels", {})
            label = (labels.get(language) or {}).get("value")
            if label:
                out[pid] = label
        return out

    def _rank_sort_key(self, claim: dict) -> int:
        rank = claim.get("rank")
        if rank == "preferred":
            return 0
        if rank == "normal":
            return 1
        if rank == "deprecated":
            return 2
        return 3
    
    def get_identifiers(
        self,
        entity_id: str,
        include_labels: bool = False,
        language: str = "en",
        first_only: bool = False,
        include_unknown_properties: bool = True,
    ) -> dict:
        """
        Get all external identifiers for an entity.
        
        Args:
            entity_id: Wikidata ID (e.g., Q42)
            include_labels: Include human-readable property labels
            
        Returns:
            Dict mapping property IDs (or labels) to identifier values
        """
        entity = self.get_entity(entity_id, props=["claims"])
        if not entity:
            return {}
            
        claims = entity.get("claims", {})
        identifiers = {}
        
        label_map: dict[str, str] = {}
        if include_labels:
            prop_ids = [pid for pid in claims.keys() if pid.startswith("P")]
            label_map = self._property_labels(prop_ids, language=language)

        for prop_id, prop_claims in claims.items():
            # Collect all external-id values for this property, preferring higher rank.
            external_claims = []
            for claim in prop_claims:
                mainsnak = claim.get("mainsnak", {})
                if mainsnak.get("datatype") != "external-id":
                    continue
                datavalue = mainsnak.get("datavalue") or {}
                value = datavalue.get("value")
                if value is None:
                    continue
                external_claims.append((claim, value))

            if not external_claims:
                continue

            if not include_unknown_properties and prop_id not in self.IDENTIFIER_PROPERTIES:
                continue

            # Sort by rank (preferred -> normal -> deprecated), preserving API order within rank.
            external_claims.sort(key=lambda cv: self._rank_sort_key(cv[0]))
            values = [v for _, v in external_claims]

            if include_labels:
                label = label_map.get(prop_id) or self.IDENTIFIER_PROPERTIES.get(prop_id) or prop_id
                key = f"{label} ({prop_id})"
            else:
                key = prop_id

            if first_only:
                identifiers[key] = values[0]
            else:
                identifiers[key] = values[0] if len(values) == 1 else values
                    
        return identifiers
    
    def get_label(
        self,
        entity_id: str,
        language: str = "en"
    ) -> Optional[str]:
        """Get the label for an entity in specified language."""
        entity = self.get_entity(entity_id, props=["labels"], languages=[language])
        if not entity:
            return None
        labels = entity.get("labels", {})
        label_data = labels.get(language, {})
        return label_data.get("value")


def main():
    """Demo usage of WikidataAPI."""
    wd = WikidataAPI()
    
    # Search example
    print("=== Searching for 'Albert Einstein' ===")
    results = wd.search("Albert Einstein", limit=3)
    for r in results:
        print(f"  {r['id']}: {r.get('label', 'N/A')} - {r.get('description', 'N/A')}")
    
    if results:
        entity_id = results[0]["id"]
        
        # Get identifiers
        print(f"\n=== External Identifiers for {entity_id} ===")
        identifiers = wd.get_identifiers(entity_id, include_labels=True)
        for prop, value in list(identifiers.items())[:10]:
            print(f"  {prop}: {value}")


if __name__ == "__main__":
    main()
