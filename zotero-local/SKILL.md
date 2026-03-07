---
name: zotero-local
description: Interact with a local Zotero 8 desktop application through its HTTP API at localhost:23119. Use this skill whenever the user wants to search, fetch, add, edit, or organize bibliographic items in their Zotero library, import citations (BibTeX, RIS, etc.), attach files, manage collections and tags, or retrieve full-text content from Zotero. Triggers on mentions of Zotero, citation management, reference libraries, bibliographic databases, or local library management. Also use when chaining with other catalog skills (Harvard, LOC, HathiTrust, etc.) to save found records into the user's Zotero library.
version: 1.0.0
---

# Zotero Local API Skill

Interact with a running Zotero 8 desktop app via its local HTTP API.

## Critical: Two API Layers

Zotero's local server has **two separate API layers** with different capabilities:

### 1. Local API (Read-Only) — `/api/...`

Mirrors the Zotero Web API v3 at `http://localhost:23119/api/`. Supports comprehensive read operations but **no writes** (POST/PUT/PATCH/DELETE all return 400).

- Uses `users/0` for the local user (not the actual user ID)
- No authentication required
- All query parameters from the Web API work: `q`, `qmode`, `sort`, `direction`, `limit`, `start`, `format`, `include`, `itemType`, `tag`, `since`
- Supports `format=json` (default), `format=bib`, `format=citation`, `format=keys`, `format=versions`, and export formats like `format=bibtex`

### 2. Connector API (Write) — `/connector/...`

The connector endpoints handle all write operations:

| Endpoint | What it does |
|----------|-------------|
| `POST /connector/saveItems` | Create items with full metadata, notes, and tags |
| `POST /connector/saveSnapshot` | Save a webpage as a Zotero item |
| `POST /connector/import` | Import BibTeX, RIS, or other bibliographic formats |
| `POST /connector/saveAttachment` | Attach files to existing items |
| `POST /connector/saveStandaloneAttachment` | Save a standalone file attachment |
| `POST /connector/saveSingleFile` | Save SingleFile webpage snapshots |
| `POST /connector/updateSession` | Update tags, target collection for a save session |
| `POST /connector/getSelectedCollection` | Get current library/collection selection |
| `POST /connector/installStyle` | Install citation styles |

## Prerequisites

- Zotero 8 must be running on the local machine
- In Zotero preferences: "Allow other applications on this computer to communicate with Zotero" must be enabled
- The API runs at `http://localhost:23119/api/`

## Common Workflows

### Search Items

```
GET http://localhost:23119/api/users/0/items?q=keyword&format=json&limit=20
```

Query parameters: `q` (search text), `qmode` (titleCreatorYear or everything), `sort` (dateAdded, dateModified, title, creator, date), `direction` (asc/desc), `itemType` (book, journalArticle, etc.), `tag` (filter by tag).

### Get a Specific Item

```
GET http://localhost:23119/api/users/0/items/{itemKey}?format=json
```

### Get Item Children (notes, attachments)

```
GET http://localhost:23119/api/users/0/items/{itemKey}/children?format=json
```

### Create Items

```bash
POST http://localhost:23119/connector/saveItems
Content-Type: application/json

{
  "items": [{
    "itemType": "book",
    "title": "The Title",
    "creators": [{"firstName": "First", "lastName": "Last", "creatorType": "author"}],
    "date": "2024",
    "publisher": "Publisher Name",
    "ISBN": "978-0-123456-78-9",
    "tags": [{"tag": "history"}, {"tag": "research"}],
    "notes": [{"note": "<p>My note about this book</p>"}]
  }],
  "uri": "http://example.com",
  "sessionID": "unique-session-id"
}
```

The `uri` and `sessionID` fields are required by the connector protocol. Use any unique string for `sessionID`.

### Import BibTeX/RIS

The import endpoint requires a unique `session` query parameter:

```bash
POST http://localhost:23119/connector/import?session=unique-id
Content-Type: text/plain

@book{key2024,
  author = {Author Name},
  title = {Book Title},
  year = {2024},
  publisher = {Publisher}
}
```

Returns the created item(s) as JSON. Without the `session` parameter, repeated imports return 409 Conflict.

### Import a PDF into Zotero

Upload a PDF as a standalone attachment. Zotero auto-recognizes the document and creates a parent item with extracted metadata (title, authors, DOI, etc.).

```bash
POST http://localhost:23119/connector/saveStandaloneAttachment
Content-Type: application/pdf
X-Metadata: {"sessionID": "unique-id", "url": "file:///path/to/file.pdf", "title": "file.pdf"}

<binary PDF data>
```

Returns `{"canRecognize": true}` on success (201).

### Attach a File to an Existing Item

Requires the **Better BibTeX (BBT)** extension for its debug-bridge endpoint. Without BBT, use `import_pdf()` to import as a standalone item instead.

```bash
POST http://127.0.0.1:23119/debug-bridge/execute
Content-Type: application/javascript

var item = await Zotero.Items.getByLibraryAndKeyAsync(
    Zotero.Libraries.userLibraryID, 'ITEMKEY'
);
var att = await Zotero.Attachments.importFromFile({
    file: '/path/to/file.pdf',
    parentItemID: item.id
});
return JSON.stringify({key: att.key});
```

### Download Attached Files

Get the local file path for an attachment:

```
GET http://localhost:23119/api/users/0/items/{attachmentKey}/file/view/url
```

Returns a `file://` URL pointing to the file in Zotero's storage directory.

Or redirect to the file directly (returns 302):

```
GET http://localhost:23119/api/users/0/items/{attachmentKey}/file
```

### Get Full-Text Content

```
GET http://localhost:23119/api/users/0/items/{itemKey}/fulltext
```

Returns indexed full-text content for PDFs and other indexed documents.

### List Collections

```
GET http://localhost:23119/api/users/0/collections?format=json
GET http://localhost:23119/api/users/0/collections/top?format=json
GET http://localhost:23119/api/users/0/collections/{collectionKey}/items?format=json
```

### Create / Delete Collections (requires BBT)

These operations use the Better BibTeX debug-bridge. See the "Better BibTeX" section below.

```python
z = ZoteroLocal()

# Check if BBT is available
if not z.check_bbt():
    print("Install Better BibTeX: https://retorque.re/zotero-better-bibtex/installation/")

# Create a top-level collection
col = z.create_collection("My Research")
# Returns: {"key": "ABCD1234", "name": "My Research"}

# Create a sub-collection
sub = z.create_collection("Chapter 1", parent_key=col["key"])
# Returns: {"key": "EFGH5678", "name": "Chapter 1", "parentKey": "ABCD1234"}

# Delete a collection (items remain in library)
z.delete_collection("ABCD1234")

# Delete a collection and trash items only in that collection
z.delete_collection("ABCD1234", delete_items=True)
```

### List Tags

```
GET http://localhost:23119/api/users/0/tags?format=json
```

### Export Citations

```
GET http://localhost:23119/api/users/0/items?format=bibtex
GET http://localhost:23119/api/users/0/items/{itemKey}?format=ris
GET http://localhost:23119/api/users/0/items?format=bib&style=chicago-author-date
```

Supported export formats: `bibtex`, `ris`, `csljson`, `mods`, `refer`, `rdf_bibliontology`, `rdf_dc`, `rdf_zotero`, `tei`, `wikipedia`.

### Execute Saved Searches

Unlike the web API, the local API can execute saved searches:

```
GET http://localhost:23119/api/users/0/searches/{searchKey}/items?format=json
```

## Item Types

Common types: `book`, `bookSection`, `journalArticle`, `conferencePaper`, `thesis`, `report`, `webpage`, `document`, `manuscript`, `letter`, `map`, `artwork`, `film`, `videoRecording`, `audioRecording`, `presentation`, `statute`, `case`, `patent`, `blogPost`, `forumPost`, `encyclopediaArticle`, `dictionaryEntry`, `newspaperArticle`, `magazineArticle`.

Get all types: `GET http://localhost:23119/api/itemTypes`
Get fields for a type: `GET http://localhost:23119/api/itemTypeFields?itemType=book`
Get creator types: `GET http://localhost:23119/api/itemTypeCreatorTypes?itemType=book`

## Response Structure

Items from the local API return this structure:

```json
{
  "key": "ABC12345",
  "version": 0,
  "library": {"type": "user", "id": 0, "name": "My Library"},
  "meta": {"creatorSummary": "Author", "numChildren": 2},
  "data": {
    "key": "ABC12345",
    "itemType": "book",
    "title": "...",
    "creators": [...],
    "date": "2024",
    "publisher": "...",
    "ISBN": "...",
    "tags": [{"tag": "..."}],
    "collections": ["COLLKEY1"],
    "dateAdded": "2024-01-01T00:00:00Z",
    "dateModified": "2024-01-01T00:00:00Z"
  }
}
```

## Python Script

```python
from scripts.zotero_api import ZoteroLocal
z = ZoteroLocal()  # connects to localhost:23119

# Search
items = z.search("keyword", limit=10)

# Get item
item = z.get_item("ABC12345")

# Create book
item = z.create_item("book", title="My Book", creators=[{"firstName":"A","lastName":"B","creatorType":"author"}])

# Import BibTeX
items = z.import_bibtex('@book{...}')

# Import a PDF (auto-recognizes metadata)
result = z.import_pdf("/path/to/paper.pdf")

# Download an attachment
path = z.download_attachment("ATTKEY12", "/tmp/")

# Check if Better BibTeX is available
if z.check_bbt():
    # Attach file to existing item (requires BBT)
    z.attach_file("/path/to/paper.pdf", "ITEMKEY1")

    # Create/delete collections (requires BBT)
    col = z.create_collection("My Collection")
    sub = z.create_collection("Sub-Collection", parent_key=col["key"])
    z.delete_collection(sub["key"])

# Export
bibtex = z.export_items(format="bibtex")
```

## Better BibTeX (BBT)

Some features require the [Better BibTeX](https://retorque.re/zotero-better-bibtex/) extension, which provides a debug-bridge for executing JavaScript inside Zotero. BBT is free and open-source — any user can install it.

**Features requiring BBT:**
- Creating and deleting collections/sub-collections
- Attaching files to existing items

**Check if BBT is installed:**
```python
z = ZoteroLocal()
if z.check_bbt():
    print("BBT is available")
else:
    print("Install BBT: https://retorque.re/zotero-better-bibtex/installation/")
```

**Install BBT:** Download the latest `.xpi` from [BBT releases](https://retorque.re/zotero-better-bibtex/installation/), then in Zotero: Tools → Add-ons → gear icon → Install Add-on From File.

## Limitations

- **No PATCH/PUT/DELETE**: The local API is read-only. Items can only be created through connector endpoints, not updated or deleted programmatically.
- **Connector write format**: `saveItems` requires `uri` and `sessionID` wrapper fields around the items array.
- **No item templates**: The `/api/items/new?itemType=` endpoint returns empty on the local API. Use `/api/itemTypeFields?itemType=` to discover fields instead.
- **Collection management and file attachment**: Requires Better BibTeX (BBT) extension. Without BBT, use `import_pdf()` to import files as standalone items with auto-recognition instead.

## Resources

- `references/api_reference.md` — Complete endpoint reference with all parameters
- `scripts/zotero_api.py` — Python client for read and write operations
