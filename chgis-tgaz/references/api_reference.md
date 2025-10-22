# CHGIS TGAZ API Reference

The China Historical GIS (CHGIS) Temporal Gazetteer (TGAZ) is a RESTful API providing access to historical Chinese placenames from 222 BCE to 1911 CE. The API supports searches in UTF-8 encoded Chinese characters and Romanized transcriptions.

## Base URL

```
https://chgis.hudci.org/tgaz
```

## Historical Coverage

Valid years: **-222 to 1911** (222 BCE to 1911 CE)

## API Methods

### 1. Canonical Placename Search

Retrieve a specific placename record by its unique ID.

**Endpoint Pattern:**
```
GET /placename/{UNIQUE_ID}
```

**ID Format:**
- TGAZ uses IDs with the prefix `hvd_`
- CHGIS IDs are converted by adding this prefix
- Example: CHGIS ID `32180` → TGAZ ID `hvd_32180`

**Example Request:**
```
GET https://chgis.hudci.org/tgaz/placename/hvd_32180
```

**Default Response Format:** XML (can be changed with `fmt` parameter)

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

## Response Structure

### XML Response (Default)

The API returns XML with placename records including:
- Unique identifiers
- Placename spellings (multiple transcriptions/languages)
- Historical dates (begin/end validity)
- Administrative hierarchy
- Geographic coordinates
- Feature type classifications

### JSON Response

Use `fmt=json` parameter to receive responses in JSON format with the same data structure.

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

### Retrieve specific record by ID
```
GET https://chgis.hudci.org/tgaz/placename/hvd_32180
```
