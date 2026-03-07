"""
Zotero Local API client — zero external dependencies.

Interacts with a running Zotero 8 desktop app through its local HTTP API
at localhost:23119. Supports reading items, collections, tags, full-text,
and creating items via the connector endpoints.

Requires Zotero 8 running with "Allow other applications on this computer
to communicate with Zotero" enabled in preferences.
"""

import json
import time
import uuid
import urllib.request
import urllib.parse
import urllib.error
from typing import Any, Dict, List, Optional

API_BASE = "http://localhost:23119/api"
CONNECTOR_BASE = "http://localhost:23119/connector"


class ZoteroLocal:
    """Client for the Zotero 8 local HTTP API."""

    def __init__(self, base_url: str = "http://localhost:23119", min_interval: float = 0.1):
        self._api_base = f"{base_url}/api"
        self._connector_base = f"{base_url}/connector"
        self._min_interval = min_interval
        self._last_request = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.time()

    def _request(self, url: str, method: str = "GET", data: Any = None,
                 content_type: str = "application/json", headers: Optional[Dict] = None) -> Any:
        self._rate_limit()
        hdrs = {"User-Agent": "ZoteroLocalSkill/1.0"}
        if content_type:
            hdrs["Content-Type"] = content_type
        if headers:
            hdrs.update(headers)

        body = None
        if data is not None:
            if isinstance(data, str):
                body = data.encode("utf-8")
            elif isinstance(data, bytes):
                body = data
            else:
                body = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if not raw:
                    return None
                ct = resp.headers.get("Content-Type", "")
                if "json" in ct:
                    return json.loads(raw)
                return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def _api_get(self, path: str, params: Optional[Dict] = None) -> Any:
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            qs = urllib.parse.urlencode(clean, doseq=True)
            url = f"{self._api_base}/{path}?{qs}"
        else:
            url = f"{self._api_base}/{path}"
        return self._request(url)

    def _connector_post(self, endpoint: str, data: Any = None,
                        content_type: str = "application/json") -> Any:
        url = f"{self._connector_base}/{endpoint}"
        return self._request(url, method="POST", data=data, content_type=content_type)

    # ── Health Check ──

    def ping(self) -> bool:
        """Check if Zotero is running."""
        try:
            result = self._request(f"{self._connector_base}/ping")
            return result is not None
        except Exception:
            return False

    # ── Read: Items ──

    def search(self, query: str, limit: int = 20, offset: int = 0,
               sort: str = "dateModified", direction: str = "desc",
               item_type: Optional[str] = None, tag: Optional[str] = None,
               qmode: str = "titleCreatorYear") -> List[Dict]:
        """Search items by keyword."""
        params = {
            "format": "json",
            "q": query,
            "qmode": qmode,
            "limit": limit,
            "start": offset,
            "sort": sort,
            "direction": direction,
        }
        if item_type:
            params["itemType"] = item_type
        if tag:
            params["tag"] = tag
        result = self._api_get("users/0/items", params)
        return result if isinstance(result, list) else []

    def get_items(self, limit: int = 50, offset: int = 0,
                  sort: str = "dateModified", direction: str = "desc",
                  item_type: Optional[str] = None, tag: Optional[str] = None,
                  top_level: bool = True) -> List[Dict]:
        """List items in the library."""
        path = "users/0/items/top" if top_level else "users/0/items"
        params = {
            "format": "json",
            "limit": limit,
            "start": offset,
            "sort": sort,
            "direction": direction,
        }
        if item_type:
            params["itemType"] = item_type
        if tag:
            params["tag"] = tag
        result = self._api_get(path, params)
        return result if isinstance(result, list) else []

    def get_item(self, key: str) -> Optional[Dict]:
        """Get a single item by key."""
        return self._api_get(f"users/0/items/{key}", {"format": "json"})

    def get_children(self, key: str) -> List[Dict]:
        """Get child items (notes, attachments) of an item."""
        result = self._api_get(f"users/0/items/{key}/children", {"format": "json"})
        return result if isinstance(result, list) else []

    def get_fulltext(self, key: str) -> Optional[Dict]:
        """Get full-text content for an item."""
        return self._api_get(f"users/0/items/{key}/fulltext")

    def get_file(self, attachment_key: str) -> Optional[bytes]:
        """Download an attached file. Returns raw bytes."""
        url = f"{self._api_base}/users/0/items/{attachment_key}/file"
        self._rate_limit()
        req = urllib.request.Request(url, headers={"User-Agent": "ZoteroLocalSkill/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError:
            return None

    def get_file_path(self, attachment_key: str) -> Optional[str]:
        """Get the local file path for an attachment."""
        result = self._api_get(f"users/0/items/{attachment_key}/file/view/url")
        if isinstance(result, str):
            return result.strip()
        return None

    # ── Read: Collections ──

    def get_collections(self, top_level: bool = False) -> List[Dict]:
        """List collections."""
        path = "users/0/collections/top" if top_level else "users/0/collections"
        result = self._api_get(path, {"format": "json"})
        return result if isinstance(result, list) else []

    def get_collection_items(self, collection_key: str, limit: int = 50,
                             top_level: bool = True) -> List[Dict]:
        """Get items in a collection."""
        suffix = "/top" if top_level else ""
        path = f"users/0/collections/{collection_key}/items{suffix}"
        result = self._api_get(path, {"format": "json", "limit": limit})
        return result if isinstance(result, list) else []

    # ── Read: Tags ──

    def get_tags(self) -> List[Dict]:
        """List all tags."""
        result = self._api_get("users/0/tags", {"format": "json"})
        return result if isinstance(result, list) else []

    # ── Read: Saved Searches ──

    def get_searches(self) -> List[Dict]:
        """List saved searches."""
        result = self._api_get("users/0/searches", {"format": "json"})
        return result if isinstance(result, list) else []

    def run_search(self, search_key: str, limit: int = 50) -> List[Dict]:
        """Execute a saved search and return matching items."""
        result = self._api_get(f"users/0/searches/{search_key}/items",
                               {"format": "json", "limit": limit})
        return result if isinstance(result, list) else []

    # ── Read: Groups ──

    def get_groups(self) -> List[Dict]:
        """List user's groups."""
        result = self._api_get("users/0/groups", {"format": "json"})
        return result if isinstance(result, list) else []

    # ── Read: Metadata ──

    def get_item_types(self) -> List[Dict]:
        """Get all supported item types."""
        return self._api_get("itemTypes") or []

    def get_item_fields(self, item_type: str) -> List[Dict]:
        """Get fields for a specific item type."""
        return self._api_get("itemTypeFields", {"itemType": item_type}) or []

    def get_creator_types(self, item_type: str) -> List[Dict]:
        """Get creator types for a specific item type."""
        return self._api_get("itemTypeCreatorTypes", {"itemType": item_type}) or []

    # ── Read: Export ──

    def export_items(self, format: str = "bibtex", keys: Optional[List[str]] = None,
                     item_type: Optional[str] = None, tag: Optional[str] = None) -> str:
        """Export items in a bibliographic format.
        Formats: bibtex, ris, csljson, mods, refer, tei, wikipedia
        """
        if keys:
            # Export specific items
            results = []
            for key in keys:
                r = self._api_get(f"users/0/items/{key}", {"format": format})
                if r:
                    results.append(r)
            return "\n".join(results)
        else:
            params = {"format": format}
            if item_type:
                params["itemType"] = item_type
            if tag:
                params["tag"] = tag
            result = self._api_get("users/0/items", params)
            return result if isinstance(result, str) else ""

    # ── Write: Create Items ──

    def create_item(self, item_type: str, title: str,
                    creators: Optional[List[Dict]] = None,
                    uri: str = "http://zotero-local-skill",
                    **fields) -> bool:
        """Create a single item in the library.

        Args:
            item_type: e.g., 'book', 'journalArticle'
            title: Item title
            creators: List of {"firstName", "lastName", "creatorType"} dicts
            **fields: Any other valid fields (date, publisher, ISBN, etc.)

        Returns True on success.
        """
        item = {"itemType": item_type, "title": title}
        if creators:
            item["creators"] = creators
        # Handle tags and notes specially
        tags = fields.pop("tags", None)
        notes = fields.pop("notes", None)
        if tags:
            if isinstance(tags, list) and tags and isinstance(tags[0], str):
                item["tags"] = [{"tag": t} for t in tags]
            else:
                item["tags"] = tags
        if notes:
            if isinstance(notes, list) and notes and isinstance(notes[0], str):
                item["notes"] = [{"note": f"<p>{n}</p>"} for n in notes]
            else:
                item["notes"] = notes
        item.update(fields)

        payload = {
            "items": [item],
            "uri": uri,
            "sessionID": str(uuid.uuid4()),
        }
        try:
            self._connector_post("saveItems", payload)
            return True
        except urllib.error.HTTPError:
            return False

    def create_items(self, items: List[Dict],
                     uri: str = "http://zotero-local-skill") -> bool:
        """Create multiple items at once.

        Each item dict should have at minimum 'itemType' and 'title'.
        """
        payload = {
            "items": items,
            "uri": uri,
            "sessionID": str(uuid.uuid4()),
        }
        try:
            self._connector_post("saveItems", payload)
            return True
        except urllib.error.HTTPError:
            return False

    def import_bibtex(self, bibtex: str) -> Optional[List[Dict]]:
        """Import BibTeX data. Returns list of created items."""
        session_id = str(uuid.uuid4())
        url = f"{self._connector_base}/import?session={session_id}"
        try:
            result = self._request(url, method="POST", data=bibtex, content_type="text/plain")
            if isinstance(result, list):
                return result
            if isinstance(result, str):
                return json.loads(result)
            return None
        except (urllib.error.HTTPError, json.JSONDecodeError):
            return None

    def import_ris(self, ris: str) -> Optional[List[Dict]]:
        """Import RIS data. Returns list of created items."""
        return self.import_bibtex(ris)  # Same endpoint handles both formats

    def import_pdf(self, file_path: str, title: Optional[str] = None) -> Optional[Dict]:
        """Import a PDF (or EPUB) as a standalone attachment into Zotero.

        Zotero will auto-recognize the document and create a parent item
        with extracted metadata (title, authors, DOI, etc.).

        Args:
            file_path: Absolute path to the PDF/EPUB file.
            title: Optional display title (defaults to filename).

        Returns:
            Dict with 'canRecognize' on success, None on failure.
        """
        import os
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = os.path.basename(file_path)
        if title is None:
            title = filename

        ext = os.path.splitext(filename)[1].lower()
        content_types = {
            ".pdf": "application/pdf",
            ".epub": "application/epub+zip",
        }
        content_type = content_types.get(ext, "application/octet-stream")

        session_id = str(uuid.uuid4())
        metadata = json.dumps({
            "sessionID": session_id,
            "url": f"file://{file_path}",
            "title": title,
        })

        with open(file_path, "rb") as f:
            file_data = f.read()

        url = f"{self._connector_base}/saveStandaloneAttachment"
        try:
            return self._request(url, method="POST", data=file_data,
                                 content_type=content_type,
                                 headers={"X-Metadata": metadata})
        except urllib.error.HTTPError:
            return None

    def attach_file(self, file_path: str, parent_key: str) -> bool:
        """Attach a file to an existing Zotero item.

        Requires the Better BibTeX (BBT) extension for its debug-bridge.
        Falls back to error if debug-bridge is unavailable.

        Args:
            file_path: Absolute path to the file.
            parent_key: The 8-character Zotero item key of the parent item.

        Returns:
            True on success.

        Raises:
            RuntimeError: If the debug-bridge is not available.
        """
        import os
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Escape backslashes and quotes in the path for JS
        escaped_path = file_path.replace("\\", "\\\\").replace("'", "\\'")

        js_code = f"""
        var item = await Zotero.Items.getByLibraryAndKeyAsync(
            Zotero.Libraries.userLibraryID, '{parent_key}'
        );
        if (!item) throw new Error('Item not found: {parent_key}');
        var attachment = await Zotero.Attachments.importFromFile({{
            file: '{escaped_path}',
            parentItemID: item.id
        }});
        return JSON.stringify({{key: attachment.key, title: attachment.getField('title')}});
        """

        url = f"{self._connector_base.rsplit('/', 1)[0]}/debug-bridge/execute"
        self._rate_limit()
        req = urllib.request.Request(
            url, data=js_code.encode("utf-8"),
            headers={
                "Content-Type": "application/javascript",
                "User-Agent": "ZoteroLocalSkill/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise RuntimeError(
                    "debug-bridge not available. Install Better BibTeX (BBT) "
                    "to attach files to existing items. Alternatively, use "
                    "import_pdf() to import as a standalone item with auto-recognition."
                )
            body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            raise RuntimeError(f"debug-bridge error ({e.code}): {body}")

    def download_attachment(self, attachment_key: str, dest_path: str) -> str:
        """Download an attachment file from Zotero to a local path.

        Args:
            attachment_key: The 8-character key of the attachment item.
            dest_path: Destination directory or file path.

        Returns:
            The path to the downloaded file.

        Raises:
            FileNotFoundError: If the attachment has no file.
        """
        import os
        # Get the storage file path from Zotero
        file_url = self.get_file_path(attachment_key)
        if not file_url:
            raise FileNotFoundError(f"No file found for attachment: {attachment_key}")

        # file_url is like "file:///Users/.../file.pdf" — extract the path
        source_path = urllib.parse.unquote(file_url.replace("file://", ""))

        if os.path.isdir(dest_path):
            filename = os.path.basename(source_path)
            dest_path = os.path.join(dest_path, filename)

        import shutil
        shutil.copy2(source_path, dest_path)
        return dest_path

    def save_snapshot(self, url: str, title: str) -> bool:
        """Save a webpage snapshot."""
        payload = {
            "url": url,
            "title": title,
            "sessionID": str(uuid.uuid4()),
        }
        try:
            self._connector_post("saveSnapshot", payload)
            return True
        except urllib.error.HTTPError:
            return False

    # ── Write: Get Selected Collection ──

    def get_selected_collection(self) -> Optional[Dict]:
        """Get the currently selected library/collection in Zotero UI."""
        return self._connector_post("getSelectedCollection", {})

    # ── Helpers ──

    @staticmethod
    def get_title(item: Dict) -> str:
        """Extract title from an item response."""
        data = item.get("data", item)
        return data.get("title", "")

    @staticmethod
    def get_creators(item: Dict) -> List[Dict]:
        """Extract creators from an item response."""
        data = item.get("data", item)
        return data.get("creators", [])

    @staticmethod
    def get_creator_str(item: Dict) -> str:
        """Get a formatted creator string."""
        creators = ZoteroLocal.get_creators(item)
        parts = []
        for c in creators:
            if "lastName" in c:
                name = f"{c.get('firstName', '')} {c['lastName']}".strip()
            else:
                name = c.get("name", "")
            if name:
                parts.append(name)
        return "; ".join(parts)

    @staticmethod
    def get_key(item: Dict) -> str:
        """Extract item key."""
        return item.get("key", item.get("data", {}).get("key", ""))

    @staticmethod
    def get_field(item: Dict, field: str) -> Any:
        """Get any field from an item."""
        data = item.get("data", item)
        return data.get(field, "")

    def summarize(self, item: Dict) -> Dict[str, Any]:
        """Summarize an item into a clean dict."""
        data = item.get("data", item)
        return {
            "key": self.get_key(item),
            "type": data.get("itemType", ""),
            "title": self.get_title(item),
            "creators": self.get_creator_str(item),
            "date": data.get("date", ""),
            "publisher": data.get("publisher", ""),
            "isbn": data.get("ISBN", ""),
            "doi": data.get("DOI", ""),
            "url": data.get("url", ""),
            "tags": [t.get("tag", "") for t in data.get("tags", [])],
            "children": item.get("meta", {}).get("numChildren", 0),
        }


if __name__ == "__main__":
    z = ZoteroLocal()
    if not z.ping():
        print("Zotero is not running or not accepting connections.")
        print("Make sure Zotero 8 is open and 'Allow other applications' is enabled.")
        raise SystemExit(1)

    print("=== Zotero is running ===")
    items = z.get_items(limit=5)
    print(f"\nLibrary has {len(items)} items (showing up to 5):")
    for item in items:
        s = z.summarize(item)
        print(f"  [{s['key']}] {s['title']} — {s['creators']} ({s['date']})")

    tags = z.get_tags()
    if tags:
        print(f"\nTags: {', '.join(t.get('tag', '') for t in tags)}")

    collections = z.get_collections()
    if collections:
        print(f"\nCollections: {len(collections)}")
