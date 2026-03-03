# CHGIS TGAZ API Reference

The China Historical GIS (CHGIS) Temporal Gazetteer (TGAZ) is a RESTful API providing access to historical Chinese placenames from 222 BCE to 1911 CE. The API supports searches in UTF-8 encoded Chinese characters and Romanized transcriptions.

## Base URL

```
https://chgis.hudci.org/tgaz
```

## Historical Coverage

Valid years: **-222 to 1911** (222 BCE to 1911 CE)

## API Methods

### 1. Canonical Placename Lookup

Retrieve a specific placename record by its unique ID.

**Endpoint Patterns:**
```
GET /placename/{UNIQUE_ID}          (HTML, default)
GET /placename/json/{UNIQUE_ID}     (JSON)
GET /placename/xml/{UNIQUE_ID}      (XML)
GET /placename/rdf/{UNIQUE_ID}      (RDF)
```

**Important:** For ID-based lookups, the output format is part of the URL path, NOT a query parameter. The `fmt` query parameter only works with the faceted search endpoint.

**ID Format:**
- TGAZ uses IDs with the prefix `hvd_`
- CHGIS IDs are converted by adding this prefix
- Example: CHGIS ID `32180` → TGAZ ID `hvd_32180`

**Example Requests:**
```
GET https://chgis.hudci.org/tgaz/placename/hvd_32180           (HTML)
GET https://chgis.hudci.org/tgaz/placename/json/hvd_32180      (JSON)
GET https://chgis.hudci.org/tgaz/placename/xml/hvd_32180       (XML)
```

---

### 2. Faceted Search

Search using multiple query parameters to find placenames matching specific criteria.

**Endpoint:**
```
GET /placename
```

**Query Parameters:**

| Parameter | Code | Description | Example |
|-----------|------|-------------|---------|
| Placename | `n` | Name of the place (Chinese characters or Romanization) | `n=mengla` or `n=蒙拉` |
| Year | `yr` | Historical year (use `-` prefix for BCE) | `yr=1820` or `yr=-100` |
| Feature Type | `ftyp` | Administrative type (xian, zhou, fu, etc.) | `ftyp=xian` |
| Data Source | `src` | Source dataset identifier | `src=chgis` |
| Immediate Parent | `ipar` | Name of parent administrative unit | `ipar=yunnan` |
| Format | `fmt` | Output format (`xml` or `json`) | `fmt=json` |

**Important Notes:**
- **Blank spaces are accepted** in placename, feature type, and immediate parent values (no need to URL-encode spaces)
- **Chinese characters** should be sent as plain UTF-8 encodings, NOT URLencoded hexadecimal strings
- Default output is XML unless `fmt=json` is specified
- Multiple parameters can be combined in a single query
- **Prefix matching**: The `n` parameter uses wildcard suffix matching (e.g., `n=beijing` matches "北京路", "北京行省", "北井县", etc.)

**Example Requests:**

Basic search by placename:
```
GET https://chgis.hudci.org/tgaz/placename?n=mengla
```

Search with year and feature type:
```
GET https://chgis.hudci.org/tgaz/placename?n=mengla&yr=1820&ftyp=xian
```

Search in JSON format:
```
GET https://chgis.hudci.org/tgaz/placename?n=北京&yr=1800&fmt=json
```

Complex search with parent:
```
GET https://chgis.hudci.org/tgaz/placename?n=hangzhou&yr=1500&ipar=zhejiang&fmt=json
```

---

## Common Feature Types

Historical Chinese administrative units include:

- `xian` (县) - County
- `zhou` (州) - Prefecture  
- `fu` (府) - Superior prefecture
- `sheng` (省) - Province
- `dao` (道) - Circuit
- `lu` (路) - Route
- `jun` (郡) - Commandery

---

## Response Structures

### Faceted Search JSON Response

```json
{
  "system": "CHGIS - Harvard University & Fudan University",
  "memo": "Results for query matching key 'suzhou%' and year '1820' and feature type 'fu'",
  "count of displayed results": "3",
  "count of total results": "3",
  "placenames": [
    {
      "sys_id": "hvd_32432",
      "uri": "https://chgis.hudci.org/tgaz/placename/hvd_32432",
      "name": "苏州府",
      "transcription": "Suzhou Fu",
      "years": "1367 ~ 1911",
      "parent sys_id": "hvd_30040",
      "parent name": "江南行省 (Jiangnan Xings)",
      "feature type": "府 (fu)",
      "object type": "POINT",
      "xy coordinates": "120.61862, 31.31271",
      "data source": "CHGIS"
    }
  ]
}
```

**Note:** The `memo` field shows the actual query pattern used, including the wildcard suffix (`%`). This confirms the API uses prefix matching.

### Canonical Lookup JSON Response

```json
{
  "system": "China Historical GIS, Harvard University and Fudan University",
  "license": "CC BY-NC 4.0",
  "uri": "https://chgis.hudci.org/tgaz/placename/hvd_32180",
  "sys_id": "hvd_32180",
  "spellings": [
    {"written form": "婺州", "script": "traditional Chinese"},
    {"written form": "Wu Zhou", "transcribed in": "Pinyin"}
  ],
  "feature_type": {
    "name": "州",
    "transcription": "zhou",
    "English": "prefecture"
  },
  "temporal": {
    "begin": "758",
    "end": "1275"
  },
  "spatial": {
    "object_type": "POINT",
    "latitude": "29.10471",
    "longitude": "119.64992",
    "present_location": [
      {"country code": "cn", "text": "今浙江金华市"}
    ]
  },
  "historical_context": {
    "part of": [
      {"begin year": "758", "end year": "769", "parent id": "hvd_30083", "name": "浙江东道节度使"}
    ]
  },
  "data_source": "CHGIS"
}
```

### XML Response (Default)

The API returns XML with the same fields as above.

---

## Data Sources

The TGAZ integrates multiple historical gazetteer databases:
- **CHGIS** - China Historical GIS
- **Toponimika** - Historical Gazetteer of Russia
- **Greater Tibet** - Gazetteer of Historical Monasteries

---

## Usage Notes

1. **Character Encoding**: Always use UTF-8 for Chinese characters
2. **Year Format**: Use negative numbers for BCE dates (e.g., `-100` for 100 BCE)
3. **Search Strategy**: Start with broad searches (just placename) and add parameters to narrow results
4. **Multiple Results**: Faceted searches may return multiple matching records
5. **Historical Context**: Consider that placenames, boundaries, and administrative statuses changed over time

---

## Example Use Cases

### Find a county in a specific year
```
GET https://chgis.hudci.org/tgaz/placename?n=suzhou&yr=1820&ftyp=xian&fmt=json
```

### Search using Chinese characters
```
GET https://chgis.hudci.org/tgaz/placename?n=苏州府&yr=1750&fmt=json
```

### Search within a province
```
GET https://chgis.hudci.org/tgaz/placename?n=ningbo&ipar=zhejiang&yr=1850&fmt=json
```

### Retrieve specific record by ID (JSON)
```
GET https://chgis.hudci.org/tgaz/placename/json/hvd_32180
```
