# Zotero Local API Reference

## Base URLs

- **Local API (read)**: `http://localhost:23119/api/`
- **Connector API (write)**: `http://localhost:23119/connector/`

No authentication required. Zotero 8 must be running with "Allow other applications" enabled.

## Local API Endpoints (Read-Only)

All endpoints below use GET. Use `users/0` for the local user.

### Metadata

| Endpoint | Description |
|----------|-------------|
| `/api/itemTypes` | All item types |
| `/api/itemFields` | All item fields |
| `/api/itemTypeFields?itemType={type}` | Fields for a specific item type |
| `/api/itemTypeCreatorTypes?itemType={type}` | Creator types for item type |
| `/api/creatorFields` | Creator field names (firstName, lastName, name) |

### Items

| Endpoint | Description |
|----------|-------------|
| `/api/users/0/items` | All items |
| `/api/users/0/items/top` | Top-level items only (no notes/attachments) |
| `/api/users/0/items/trash` | Trashed items |
| `/api/users/0/items/{key}` | Single item by key |
| `/api/users/0/items/{key}/children` | Child items (notes, attachments) |
| `/api/users/0/items/{key}/file` | Download attached file |
| `/api/users/0/items/{key}/file/view/url` | Get file path as plain text |
| `/api/users/0/items/{key}/fulltext` | Full-text content |
| `/api/users/0/items/tags` | All tags with item counts |

### Collections

| Endpoint | Description |
|----------|-------------|
| `/api/users/0/collections` | All collections |
| `/api/users/0/collections/top` | Top-level collections |
| `/api/users/0/collections/{key}` | Single collection |
| `/api/users/0/collections/{key}/collections` | Sub-collections |
| `/api/users/0/collections/{key}/items` | Items in collection |
| `/api/users/0/collections/{key}/items/top` | Top-level items in collection |
| `/api/users/0/collections/{key}/items/tags` | Tags in collection |

### Saved Searches

| Endpoint | Description |
|----------|-------------|
| `/api/users/0/searches` | All saved searches |
| `/api/users/0/searches/{key}` | Single saved search |
| `/api/users/0/searches/{key}/items` | Execute search and return matching items |

### Tags

| Endpoint | Description |
|----------|-------------|
| `/api/users/0/tags` | All tags |
| `/api/users/0/tags/{urlEncodedTag}` | Specific tag |

### Groups

| Endpoint | Description |
|----------|-------------|
| `/api/users/0/groups` | User's groups |
| `/api/groups/{groupID}/items` | Items in group |
| `/api/groups/{groupID}/collections` | Collections in group |

### Full-Text Index

| Endpoint | Description |
|----------|-------------|
| `/api/users/0/fulltext?since={version}` | Full-text availability since version |

### Publications

| Endpoint | Description |
|----------|-------------|
| `/api/users/0/publications/items` | Published items |
| `/api/users/0/publications/items/top` | Top-level published items |

## Query Parameters (Items)

| Parameter | Values | Notes |
|-----------|--------|-------|
| `format` | `json` (default), `keys`, `versions`, `bib`, `citation`, `bibtex`, `ris`, `csljson`, `mods`, `refer`, `tei`, `wikipedia` | Output format |
| `include` | `data`, `bib`, `citation`, or export format | Include additional representations |
| `q` | string | Quick search text |
| `qmode` | `titleCreatorYear`, `everything` | Search scope |
| `sort` | `dateAdded`, `dateModified`, `title`, `creator`, `itemType`, `date`, `publisher`, `publicationTitle`, `journalAbbreviation`, `language`, `accessDate`, `libraryCatalog`, `callNumber`, `rights`, `addedBy`, `numItems` | Sort field |
| `direction` | `asc`, `desc` | Sort direction |
| `limit` | integer | Max results (no default limit locally) |
| `start` | integer | Pagination offset |
| `since` | integer | Return items changed since this version |
| `itemType` | string | Filter: `book`, `journalArticle`, `-attachment`, etc. Use `\|\|` for OR |
| `tag` | string | Filter by tag. Multiple `tag` params = AND. Use `-tag` for NOT |
| `style` | string | CSL style ID for `format=bib` |
| `locale` | string | Locale for citations |
| `linkwrap` | `1` | Wrap URLs in `<a>` tags in citations |

## Connector Endpoints (Write)

### POST /connector/saveItems

Create items in the Zotero library.

**Request:**
```json
{
  "items": [
    {
      "itemType": "book",
      "title": "Title",
      "creators": [
        {"firstName": "First", "lastName": "Last", "creatorType": "author"}
      ],
      "date": "2024",
      "publisher": "Publisher",
      "ISBN": "978-...",
      "place": "City",
      "language": "en",
      "url": "https://...",
      "abstractNote": "Abstract text",
      "tags": [{"tag": "keyword1"}, {"tag": "keyword2"}],
      "notes": [{"note": "<p>HTML note content</p>"}]
    }
  ],
  "uri": "http://source-url.com",
  "sessionID": "unique-string"
}
```

**Response:** 201 Created (empty body on success)

### POST /connector/import?session={uniqueID}

Import bibliographic data in any supported format (BibTeX, RIS, MODS, etc.).

**Request:**
- Query param: `session` — unique session ID (required, or returns 409 on repeat calls)
- Content-Type: `text/plain`
- Body: raw bibliographic data

**Response:** 201 with JSON array of created items

### POST /connector/saveSnapshot

Save a webpage as a Zotero item.

**Request:**
```json
{
  "url": "https://example.com/page",
  "title": "Page Title",
  "sessionID": "unique-string"
}
```

**Response:** 201 Created

### POST /connector/saveAttachment

Attach a file to an item created in the same `saveItems` session. The `parentItemID` is the connector-assigned ID from the session, not the Zotero item key. **Cannot attach to pre-existing items.**

**Request:**
- Content-Type: file MIME type
- Header: `X-Metadata: {"parentItemID": "connector-item-id", "title": "filename.pdf", "url": "https://...", "sessionID": "sess-id"}`
- Body: file binary data

### POST /debug-bridge/execute (Better BibTeX)

Execute JavaScript inside Zotero. Requires the [Better BibTeX](https://retorque.re/zotero-better-bibtex/) extension. Use this to attach files to **existing** items.

**Request:**
- Content-Type: `application/javascript`
- Body: JavaScript code (runs as async function body)

**Response:** `201` with JSON return value, or `500` with error

**Example — attach PDF to existing item:**
```javascript
var item = await Zotero.Items.getByLibraryAndKeyAsync(
    Zotero.Libraries.userLibraryID, 'ITEMKEY1'
);
if (!item) throw new Error('Item not found');
var att = await Zotero.Attachments.importFromFile({
    file: '/path/to/file.pdf',
    parentItemID: item.id
});
return JSON.stringify({key: att.key, title: att.getField('title')});
```

**Example — create a collection:**
```javascript
var col = new Zotero.Collection();
col.libraryID = Zotero.Libraries.userLibraryID;
col.name = 'My Collection';
await col.saveTx();
return JSON.stringify({key: col.key, name: col.name});
```

**Example — create a sub-collection:**
```javascript
var parent = await Zotero.Collections.getByLibraryAndKeyAsync(
    Zotero.Libraries.userLibraryID, 'PARENTKEY'
);
if (!parent) throw new Error('Parent not found');
var col = new Zotero.Collection();
col.libraryID = Zotero.Libraries.userLibraryID;
col.name = 'Sub-Collection';
col.parentID = parent.id;
await col.saveTx();
return JSON.stringify({key: col.key, name: col.name});
```

**Example — delete a collection:**
```javascript
var col = await Zotero.Collections.getByLibraryAndKeyAsync(
    Zotero.Libraries.userLibraryID, 'COLLKEY'
);
if (!col) throw new Error('Collection not found');
await col.eraseTx();
return JSON.stringify({deleted: true});
```

**Example — check if BBT is available:**
```javascript
return 'ok';
```
If this returns 201, BBT is installed. If 404, it is not.

### POST /connector/saveStandaloneAttachment

Import a file (PDF, EPUB, etc.) as a standalone attachment. Zotero auto-recognizes PDFs/EPUBs and creates a parent item with extracted metadata.

**Request:**
- Content-Type: file MIME type (e.g., `application/pdf`)
- Header: `X-Metadata: {"sessionID": "unique-id", "url": "file:///path/to/file.pdf", "title": "file.pdf"}`
- Body: file binary data

**Response:** `201` with `{"canRecognize": true|false}`

**Example (curl):**
```bash
curl -X POST \
  -H "Content-Type: application/pdf" \
  -H 'X-Metadata: {"sessionID": "abc-123", "url": "file:///path/to/paper.pdf", "title": "paper.pdf"}' \
  --data-binary @/path/to/paper.pdf \
  http://localhost:23119/connector/saveStandaloneAttachment
```

### POST /connector/getSelectedCollection

Get the currently selected library/collection in Zotero UI.

**Request:** `{}` (empty JSON)

**Response:**
```json
{
  "libraryID": 1,
  "libraryName": "My Library",
  "libraryEditable": true,
  "filesEditable": true,
  "id": null,
  "name": "My Library",
  "targets": [
    {"id": "L1", "name": "My Library", "level": 0},
    {"id": "C_ABCDEF", "name": "Collection Name", "level": 1}
  ],
  "tags": {"L1": [{"tag": "existing-tag", "type": 1}]}
}
```

### POST /connector/updateSession

Update metadata for an active save session.

**Request:**
```json
{
  "sessionID": "the-session-id",
  "target": "L1",
  "tags": "tag1,tag2"
}
```

### POST /connector/ping

Health check.

**GET Response:** HTML body "Zotero is running"
**POST Response:** JSON with Zotero version and preferences

## Item Types

annotation, artwork, attachment, audioRecording, bill, blogPost, book, bookSection, case, computerProgram, conferencePaper, dataset, dictionaryEntry, document, email, encyclopediaArticle, film, forumPost, hearing, instantMessage, interview, journalArticle, letter, magazineArticle, manuscript, map, newspaperArticle, note, patent, podcast, preprint, presentation, radioBroadcast, report, standard, statute, thesis, tvBroadcast, videoRecording, webpage

## Common Book Fields

title, abstractNote, date, publisher, place, volume, numberOfVolumes, edition, series, seriesNumber, numPages, ISBN, shortTitle, url, accessDate, archive, archiveLocation, callNumber, language, libraryCatalog, rights, extra

## Creator Types (Book)

author, contributor, editor, seriesEditor, translator

## Error Codes

| HTTP Status | Meaning |
|-------------|---------|
| 200 | Success |
| 201 | Created (write success) |
| 400 | Bad request / method not supported |
| 404 | Endpoint or item not found |
| 500 | Internal server error |
