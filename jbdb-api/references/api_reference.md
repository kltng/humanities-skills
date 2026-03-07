# JBDB API Reference

## API Endpoint

Base URL: `https://jbdb.jp/api`

The API uses LoopBack 3 REST conventions. No authentication is required.

**Content Types:**
- Accepts: `application/json`, `application/x-www-form-urlencoded`, `application/xml`
- Returns: `application/json`, `application/xml`, `text/xml`

## LoopBack Filter Syntax

All list endpoints accept a `filter` query parameter as a JSON string.

### Where Clause

```json
{"where": {"cName": "松尾芭蕉"}}
```

**Operators:**
```json
{"where": {"cPersonid": {"gt": 100}}}          // greater than
{"where": {"cPersonid": {"lt": 100}}}          // less than
{"where": {"cPersonid": {"gte": 100}}}         // greater or equal
{"where": {"cPersonid": {"lte": 100}}}         // less or equal
{"where": {"cName": {"regexp": "/芭蕉/i"}}}    // regex (case-insensitive)
{"where": {"cPersonid": {"inq": [1, 2, 3]}}}   // in list
```

**Logical operators:**
```json
{"where": {"or": [{"cName": "A"}, {"cNameRomaji": "B"}]}}
{"where": {"and": [{"cFemale": true}, {"cPlaceCode": 5}]}}
```

### Pagination

```json
{"limit": 20, "offset": 0}
```

### Field Selection

```json
{"fields": {"cPersonid": true, "cName": true, "cNameRomaji": true}}
```

### Ordering

```json
{"order": "cName ASC"}
{"order": ["cByNengoYear DESC", "cName ASC"]}
```

### Include (Relations)

```json
{"include": "resolve"}
```

## Core Endpoints

### BiogMain (Persons)

**Find all:**
```
GET /BiogMains?filter={...}
```

**Find by ID:**
```
GET /BiogMains/{id}
```

#### BiogMain Schema

| Field | Type | Description |
|-------|------|-------------|
| cPersonid | number | Primary key |
| cName | string | Name (Japanese) |
| cNameFurigana | string | Furigana reading |
| cNameRomaji | string | Romanized name |
| cFemale | boolean | Gender (true = female) |
| cByDay | number | Birth day |
| cByMonth | number | Birth month |
| cByNengoYear | number | Birth year within nengo era |
| cByNengoCode | number | Birth nengo era code → NengoCodes |
| cByIntercalary | boolean | Birth month is intercalary |
| cDyDay | number | Death day |
| cDyMonth | number | Death month |
| cDyNengoYear | number | Death year within nengo era |
| cDyNengoCode | number | Death nengo era code → NengoCodes |
| cDyIntercalary | boolean | Death month is intercalary |
| cDeathAge | number | Age at death |
| cOccupationCodes | array | Occupation code list → OccupationCodes |
| cReligionTypes | array | Religion type list → ReligionTypes |
| cStatusCodes | array | Status code list → StatusCodes |
| cSourceIds | array | Source references → SourceData |
| cProjectIds | array | Project references → Projects |
| cPlaceCode | number | Place code → PlaceCodes |
| cPlaceCountryCode | number | Country code → CountryCodes |
| cOriginKuniCode | number | Origin province (kuni) code |
| cOriginGunCode | number | Origin district (gun) code |
| cOriginMuraCode | number | Origin village (mura) code |
| cPlaceString | string | Place description (free text) |
| cImageName | string | Portrait filename |
| cImageSource | string | Portrait source |
| cNotes | string | Biographical notes |
| cApprovedEntry | boolean | Entry validated |
| cCreatedDate | string | Creation timestamp |
| cModifiedDate | string | Last modified timestamp |

### AltnameData (Alternative Names)

```
GET /AltnameData?filter={"where":{"cPersonid":{id}}}
GET /AltnameData/{mappingId}
```

| Field | Type | Description |
|-------|------|-------------|
| cMappingid | number | Record ID |
| cPersonid | number | Person reference |
| cAltName | string | Alternative name (Japanese) |
| cAltNameFurigana | string | Furigana |
| cAltNameRomaji | string | Romanized |
| cAltNameTypeCode | number | Name type → AltnameCodes |
| cSource | number | Source reference |
| cPages | string | Page reference |
| cNotes | string | Notes |

### AltnameCodes (Name Type Lookup)

```
GET /AltnameCodes
GET /AltnameCodes/{cNameTypeCode}
```

| Field | Type | Description |
|-------|------|-------------|
| cNameTypeCode | number | Type ID |
| cNameTypeDesc | string | Description (Japanese) |
| cNameTypeDescRomaji | string | Romanized description |
| cNameTypeDescTrans | string | English translation |

### KinData (Kinship Relations)

```
GET /KinData?filter={"where":{"cPersonid":{id}}}
```

| Field | Type | Description |
|-------|------|-------------|
| cMappingid | number | Record ID |
| cPersonid | number | Person reference |
| cKinCode | number | Relationship type → KinshipCodes |
| cKinId | number | Related person ID |
| cSourceid | number | Source reference |
| cPages | string | Page reference |
| cNotes | string | Notes |

### KinshipCodes (Kinship Type Lookup)

```
GET /KinshipCodes
GET /KinshipCodes/{cKincode}
```

| Field | Type | Description |
|-------|------|-------------|
| cKincode | number | Type ID |
| cKinrel | string | Relationship (Japanese) |
| cKinrelTrans | string | English translation |
| cKinrelAlt | string | Alternative term |
| cKinPair1 | number | Reciprocal code (direction 1) |
| cKinPair2 | number | Reciprocal code (direction 2) |
| cSorting | number | Sort order |
| cUpstep, cDwnstep, cMarstep, cColstep | number | Genealogical distance |
| cHierarchy | string | Hierarchical classification |

### NonkinData (Non-Kinship Associations)

```
GET /NonkinData?filter={"where":{"cPersonid":{id}}}
```

| Field | Type | Description |
|-------|------|-------------|
| cMappingid | number | Record ID |
| cPersonid | number | Person reference |
| cNonkinCode | number | Relationship type → NonkinshipCodes |
| cNonkinId | number | Related person ID |
| cSourceid | number | Source reference |
| cPages | string | Page reference |
| cNotes | string | Notes |

### NonkinshipCodes (Non-Kinship Type Lookup)

```
GET /NonkinshipCodes
GET /NonkinshipCodes/{cNonkincode}
```

| Field | Type | Description |
|-------|------|-------------|
| cNonkincode | number | Type ID |
| cNonkinrel | string | Relationship (Japanese) |
| cNonkinrelTrans | string | English translation |
| cNonkinPair1 | number | Reciprocal code (direction 1) |
| cNonkinPair2 | number | Reciprocal code (direction 2) |
| cHierarchy | string | Hierarchical classification |

### EventData (Person-Event Links)

```
GET /EventData?filter={"where":{"cPersonid":{id}}}
```

| Field | Type | Description |
|-------|------|-------------|
| cEventDataEntryId | number | Record ID |
| cEventId | number | Event reference → EventCodes |
| cPersonid | number | Person reference |
| cEventRoleId | number | Role → EventRoleCodes |
| cYear | number | Event year (Western) |
| cMonth | string | Month |
| cDay | string | Day |
| cIntercalary | boolean | Intercalary month |
| cSourceId | number | Source reference |
| cPages | string | Page reference |
| cEventNotes | string | Notes |
| cEventCodeId | number | Event code reference |

### EventCodes (Event Definitions)

```
GET /EventCodes
GET /EventCodes/{cEventId}
```

| Field | Type | Description |
|-------|------|-------------|
| cEventId | number | Event ID |
| cEventTypeCode | number | Event category → EventTypes |
| cEventSubject | string | Subject (Japanese) |
| cEventSubjectTrans | string | English translation |
| cFirstYear | number | Start year (Western) |
| cLastYear | number | End year (Western) |
| cPlaceCode | number | Place → PlaceCodes |
| cPlaceString | string | Place description |
| cEventNotes | string | Notes |

### EventTypes (Event Category Lookup)

```
GET /EventTypes
GET /EventTypes/{cEventTypeCode}
```

| Field | Type | Description |
|-------|------|-------------|
| cEventTypeCode | number | Type ID |
| cEventType | string | Category (Japanese) |
| cEventTypeTrans | string | English translation |
| cEventCategory | string | Broader category |

### EventRoleCodes (Event Role Lookup)

```
GET /EventRoleCodes
GET /EventRoleCodes/{cEventRoleId}
```

| Field | Type | Description |
|-------|------|-------------|
| cEventRoleId | number | Role ID |
| cEventRoleDesc | string | Description (Japanese) |
| cEventRoleTrans | string | English translation |

### PersonalHistoryData

```
GET /PersonalHistoryData?filter={"where":{"cPersonid":{id}}}
```

| Field | Type | Description |
|-------|------|-------------|
| cMappingid | number | Record ID |
| cPersonid | number | Person reference |
| cPersonalHistoryTypeCode | number | Type → PersonalHistoryTypeCodes |
| cPlaceCode | number | Place → PlaceCodes |
| cPlaceString | string | Place description |
| cStartNengoYear | number | Start year in nengo era |
| cStartNengoCode | number | Start era → NengoCodes |
| cEndNengoYear | number | End year in nengo era |
| cEndNengoCode | number | End era → NengoCodes |
| cSourceid | number | Source reference |
| cNotes | string | Notes |

### PersonalHistoryTypeCodes

```
GET /PersonalHistoryTypeCodes
```

| Field | Type | Description |
|-------|------|-------------|
| cPersonalHistoryTypeCode | number | Type ID |
| cPersonalHistoryTypeDesc | string | Description (Japanese) |
| cPersonalHistoryTypeDescTrans | string | English translation |

### SourceData (Bibliographic Sources)

```
GET /SourceData?filter={"where":{"cSourceid":{id}}}
GET /SourceData/{id}
```

| Field | Type | Description |
|-------|------|-------------|
| cSourceid | number | Source ID |
| cTitle | string | Title (Japanese) |
| cTitleRomaji | string | Romanized title |
| cAuthor | string | Author (Japanese) |
| cAuthorRomaji | string | Romanized author |
| cPublisher | string | Publisher |
| cYear | number | Publication year |
| cUri | string | Online resource URL |
| cNotes | string | Notes |

### NengoCodes (Japanese Era Names)

```
GET /NengoCodes
GET /NengoCodes/{cNengoId}
```

| Field | Type | Description |
|-------|------|-------------|
| cNengoId | number | Era ID |
| cNengoName | string | Era name (Japanese) |
| cNengoNameRomaji | string | Romanized era name |
| cStartYearMinusOne | number | Starting Western year minus 1 |
| cMaxYears | number | Era duration in years |

**Converting nengo to Western year:** `western_year = cStartYearMinusOne + cByNengoYear`

### PlaceCodes (Japanese Locations)

```
GET /PlaceCodes
GET /PlaceCodes/{cPlaceCode}
```

| Field | Type | Description |
|-------|------|-------------|
| cPlaceCode | number | Place ID |
| cPlaceTypeCode | number | Type → PlaceTypeCodes |
| cPlaceName | string | Name (Japanese) |
| cPlaceNameFurigana | string | Furigana |
| cPlaceNameRomaji | string | Romanized |
| cLatitude | string | Latitude |
| cLongitude | string | Longitude |
| cCoordinates | GeoPoint | `{lat, lng}` |

### OccupationCodes

```
GET /OccupationCodes
GET /OccupationCodes/{cOccupationCode}
```

| Field | Type | Description |
|-------|------|-------------|
| cOccupationCode | number | Code ID |
| cOccupationDesc | string | Description (Japanese) |
| cOccupationDescTrans | string | English translation |

### StatusCodes / StatusTypes

```
GET /StatusCodes
GET /StatusCodes/{cStatusCode}
GET /StatusTypes
GET /StatusTypes/{cStatusTypeCode}
```

StatusCodes fields: `cStatusCode`, `cStatusTypeCode`, `cStatusDesc`, `cStatusDescTrans`
StatusTypes fields: `cStatusTypeCode`, `cStatusType`, `cStatusTypeTrans`

### ReligionTypes

```
GET /ReligionTypes
GET /ReligionTypes/{cReligionTypeCode}
```

| Field | Type | Description |
|-------|------|-------------|
| cReligionTypeCode | number | Type ID |
| cReligionType | string | Religion name |
| cReligionTypeTrans | string | English translation |
| cBelongsTo | number | Parent category code |

### Projects

```
GET /Projects
GET /Projects/{cProjectId}
```

| Field | Type | Description |
|-------|------|-------------|
| cProjectId | number | Project ID |
| cProjectTitle | string | Title |
| cProjectDesc | string | Description (Japanese) |
| cProjectDescTrans | string | English description |
| cProjectUrl | string | URL |
| cProjectPi | string | Principal investigator |

## Query Examples

### Search person by exact Japanese name
```
GET /BiogMains?filter={"where":{"cName":"松尾芭蕉"}}
```

### Search by romaji (regex, case-insensitive)
```
GET /BiogMains?filter={"where":{"cNameRomaji":{"regexp":"/Matsuo Basho/i"}}}
```

### Search across all name fields
```
GET /BiogMains?filter={"where":{"or":[{"cName":{"regexp":"/芭蕉/i"}},{"cNameFurigana":{"regexp":"/ばしょう/i"}},{"cNameRomaji":{"regexp":"/Basho/i"}}]}}
```

### Paginate results
```
GET /BiogMains?filter={"where":{"cNameRomaji":{"regexp":"/Tokugawa/i"}},"limit":10,"offset":0}
```

### Get all kin relations for a person
```
GET /KinData?filter={"where":{"cPersonid":12345}}
```

### Get events for a person with specific fields
```
GET /EventData?filter={"where":{"cPersonid":12345},"fields":{"cEventId":true,"cYear":true,"cEventNotes":true}}
```

## Best Practices

1. **Name Queries**: Japanese characters yield the most precise results. Romaji with regex is useful for partial/fuzzy matching. Always try multiple name fields if initial query returns empty.

2. **Code Resolution**: Many fields store numeric codes. Resolve them using the corresponding lookup endpoints (OccupationCodes, StatusCodes, NengoCodes, PlaceCodes, etc.).

3. **Nengo Date Conversion**: To get a Western calendar year from nengo dates, fetch the NengoCode and compute: `western_year = cStartYearMinusOne + nengo_year`.

4. **Rate Limiting**: Space requests 0.5–1s apart. Respect HTTP 429 responses.

5. **Pagination**: Use `limit` and `offset` for large result sets. Default behavior returns all matching records.
