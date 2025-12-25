#!/usr/bin/env python3
"""
Wikidata API client for searching items and retrieving identifiers.
"""

import json
import time
import urllib.parse
import urllib.request
from typing import Optional


class WikidataAPI:
    """Client for Wikidata API operations."""
    
    BASE_URL = "https://www.wikidata.org/w/api.php"
    
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
        "P1015": "BIBSYS ID",
    }
    
    def __init__(self, user_agent: str = "WikidataSearchSkill/1.0"):
        self.user_agent = user_agent
        self._last_request_time = 0
        self._min_request_interval = 0.5  # 500ms between requests
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    def _request(self, params: dict) -> dict:
        """Make API request with rate limiting."""
        self._rate_limit()
        params["format"] = "json"
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
        
        req = urllib.request.Request(url)
        req.add_header("User-Agent", self.user_agent)
        
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    
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
    
    def get_identifiers(
        self,
        entity_id: str,
        include_labels: bool = False
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
        
        for prop_id, prop_claims in claims.items():
            # Check if this is an external-id property
            for claim in prop_claims:
                mainsnak = claim.get("mainsnak", {})
                datatype = mainsnak.get("datatype")
                
                if datatype == "external-id":
                    datavalue = mainsnak.get("datavalue", {})
                    value = datavalue.get("value")
                    
                    if value:
                        if include_labels and prop_id in self.IDENTIFIER_PROPERTIES:
                            key = f"{self.IDENTIFIER_PROPERTIES[prop_id]} ({prop_id})"
                        else:
                            key = prop_id
                            
                        # Handle multiple values for same property
                        if key in identifiers:
                            if isinstance(identifiers[key], list):
                                identifiers[key].append(value)
                            else:
                                identifiers[key] = [identifiers[key], value]
                        else:
                            identifiers[key] = value
                    break  # Only take preferred/first value
                    
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
