---
name: zotero-local
description: Interact with a local Zotero 8 desktop application through its HTTP API at localhost:23119. Use this skill whenever the user wants to search, read, or export items in their Zotero library, add new items (with tags and notes), import citations (BibTeX, RIS, etc.) or PDFs, list collections and tags, or retrieve full-text content from Zotero. With the optional Debug Bridge add-on it can also attach files to existing items and create or delete collections. It cannot edit or delete existing items. Triggers on mentions of Zotero, citation management, reference libraries, bibliographic databases, or local library management. Also use when chaining with other catalog skills (Harvard, LOC, HathiTrust, etc.) to save found records into the user's Zotero library.
version: 1.0.2
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

Requires the **Debug Bridge** add-on and its token (see "Debug Bridge add-on" below). Without
it, use `import_pdf()` to import the file as a standalone item instead.

```bash
POST http://127.0.0.1:23119/debug-bridge/execute
Authorization: Bearer <token>
Content-Type: text/plain

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

Or redirect to the file directly (returns 302 to a `file://` URL; Python's urllib will not follow it, so `get_file()` reads the path from `/file/view/url` instead):

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

### Create / Delete Collections (requires the Debug Bridge add-on)

These operations use the Debug Bridge add-on. See the "Debug Bridge add-on" section below.

```python
z = ZoteroLocal()   # reads the token from ZOTERO_DEBUG_BRIDGE_TOKEN

# Check that the Debug Bridge is installed and the token works
if not z.check_debug_bridge():
    print("See the 'Debug Bridge add-on' section to set it up.")

# Create a top-level collection
col = z.create_collection("My Research")
# Returns: {"key": "ABCD1234", "name": "My Research"}

# Create a sub-collection
sub = z.create_collection("Chapter 1", parent_key=col["key"])
# Returns: {"key": "EFGH5678", "name": "Chapter 1", "parentKey": "ABCD1234"}

# Delete a collection (items remain in library).
# Warning: Zotero also deletes all sub-collections of this collection.
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
GET http://localhost:23119/api/users/0/items?format=bibtex&limit=100
GET http://localhost:23119/api/users/0/items/{itemKey}?format=ris
GET http://localhost:23119/api/users/0/items?format=bib&style=chicago-author-date
```

Supported export formats: `bibtex`, `ris`, `csljson`, `mods`, `refer`, `rdf_bibliontology`, `rdf_dc`, `rdf_zotero`, `tei`, `wikipedia`.

**Always set `limit` when you export without item keys.** The local API has no default limit,
so `items?format=bibtex` returns the whole library in one call, which can be thousands of
entries. (Notes and attachments give no entry.)
`export_items()` in the Python script uses `limit=100` by default. Use `start` to page, or
pass `limit=None` only if you really want everything.

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

# Check if the Debug Bridge add-on is ready (token from ZOTERO_DEBUG_BRIDGE_TOKEN)
if z.check_debug_bridge():
    # Attach file to existing item
    z.attach_file("/path/to/paper.pdf", "ITEMKEY1")

    # Create/delete collections
    col = z.create_collection("My Collection")
    sub = z.create_collection("Sub-Collection", parent_key=col["key"])
    z.delete_collection(sub["key"])

# Export (at most 100 items unless you pass keys or a larger limit)
bibtex = z.export_items(format="bibtex", tag="history")
bibtex = z.export_items(keys=["ABC12345", "DEF67890"])
```

## Debug Bridge add-on

Some features run JavaScript inside Zotero through the `/debug-bridge/execute` endpoint. This
endpoint comes from the **Debug Bridge** add-on, not from Better BibTeX. (The add-on is made by
the Better BibTeX author and lives in the same repository, which caused the confusion.) Without
it, the endpoint returns 404.

**Features that need it:**
- Creating and deleting collections and sub-collections
- Attaching files to existing items

**Set it up (once):**
1. Download `debug-bridge-*.xpi` from
   https://github.com/retorquere/zotero-better-bibtex/releases/tag/debug-bridge
2. In Zotero: Tools → Plugins → gear icon → Install Plugin From File.
3. In Zotero: Settings → Advanced → Config Editor. Add a new **string** pref
   `extensions.zotero.debug-bridge.token` and give it a secret value.
4. Give the same value to the script: `export ZOTERO_DEBUG_BRIDGE_TOKEN=<value>`, or
   `ZoteroLocal(debug_bridge_token="<value>")`.

**Check it:**
```python
z = ZoteroLocal()
print(z.check_debug_bridge())   # True when the add-on is installed and the token is right
```

`check_bbt()` still works as an old name for `check_debug_bridge()`.

**Be careful:** the Debug Bridge runs any JavaScript it receives, with full access to your
library. Keep the token secret.

## Limitations

- **No editing of existing items**: The local API is read-only (no PATCH/PUT/DELETE). New items can be created through the connector endpoints, with tags and notes. This skill has no function to change or delete an existing item, or to add or remove tags on one.
- **Connector write format**: `saveItems` requires `uri` and `sessionID` wrapper fields around the items array.
- **No item templates**: The `/api/items/new?itemType=` endpoint returns empty on the local API. Use `/api/itemTypeFields?itemType=` to discover fields instead.
- **Collection management and file attachment**: Requires the Debug Bridge add-on and its token. Without it, use `import_pdf()` to import files as standalone items with auto-recognition instead.

## Resources

- `references/api_reference.md` — Complete endpoint reference with all parameters
- `scripts/zotero_api.py` — Python client for read and write operations

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "zotero-local"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[zotero-local] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: zotero-local* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
