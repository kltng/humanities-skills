# CBDB API Reference

## API Endpoint

Base URL: `https://cbdb.fas.harvard.edu/cbdbapi/person.php`

## Query Parameters

### Required (one of the following)

- `id` - CBDB person ID (integer)
- `name` - Person's name in Chinese characters, Pinyin, or other romanization

### Optional

- `o` - Output format (default: HTML)
  - `xml` - XML format
  - `json` - JSON format
  - (no parameter) - HTML format

## Query Examples

### Query by CBDB ID

```
https://cbdb.fas.harvard.edu/cbdbapi/person.php?id=1762
```

Returns data for person with CBDB ID 1762 (Wang Anshi) in HTML format.

### Query by Chinese Name

```
https://cbdb.fas.harvard.edu/cbdbapi/person.php?name=王安石
```

Returns data for person named 王安石 in HTML format.

### Query by Pinyin Name

```
https://cbdb.fas.harvard.edu/cbdbapi/person.php?name=Wang%20Anshi
```

Returns data for person named Wang Anshi in HTML format. Note: URL encoding required for spaces (%20).

### Query with XML Output

```
https://cbdb.fas.harvard.edu/cbdbapi/person.php?id=1762&o=xml
```

Returns XML-formatted data for person with CBDB ID 1762.

### Query with JSON Output

```
https://cbdb.fas.harvard.edu/cbdbapi/person.php?name=王安石&o=json
```

Returns JSON-formatted data for person named 王安石.

## Response Data

### JSON Response Structure

The JSON response nests data under `Package.PersonAuthority.PersonInfo.Person`:

```json
{
  "Package": {
    "PersonAuthority": {
      "DataSource": "CBDB",
      "Version": "20131220",
      "PersonInfo": {
        "Person": {
          "BasicInfo": {
            "PersonId": "1762",
            "EngName": "Wang Anshi",
            "ChName": "王安石",
            "IndexYear": "1021",
            "Gender": "0",
            "YearBirth": "1021",
            "YearDeath": "1086",
            "YearsLived": "66",
            "Dynasty": "宋",
            "DynastyId": "15",
            "DynastyBirth": "北宋",
            "EraBirth": "天禧",
            "EraYearBirth": "5",
            "EraDeath": "元祐",
            "EraYearDeath": "1",
            "IndexAddr": "臨川",
            "JunWang": "太原",
            "Notes": "..."
          },
          "PersonSources": { "Source": [...] },
          "AltNameInfo": { "AltName": [...] },
          "AddrInfo": { "Addr": [...] },
          "EntryInfo": { "Entry": [...] },
          "PostingInfo": { "Posting": [...] },
          "SocialAssocInfo": { "SocialAssoc": [...] }
        }
      }
    }
  }
}
```

### Key BasicInfo Fields

| Field | Description | Example |
|-------|-------------|---------|
| PersonId | Unique CBDB identifier | 1762 |
| EngName | Romanized name | Wang Anshi |
| ChName | Chinese name | 王安石 |
| Gender | 0 = male, 1 = female | 0 |
| YearBirth / YearDeath | Western calendar years | 1021 / 1086 |
| Dynasty | Dynasty name (Chinese) | 宋 |
| EraBirth / EraDeath | Reign era names | 天禧 / 元祐 |
| EraYearBirth / EraYearDeath | Year within the era | 5 / 1 |
| IndexAddr | Index address (place) | 臨川 |
| Notes | Biographical notes (English) | ... |

### Error Response

```json
{"error": {"code": 404, "message": "Person not found."}}
```

## Output Formats

### HTML
The default format provides a formatted web page suitable for direct viewing in a browser.

### XML
Structured XML output following CBDB's schema, providing maximum flexibility for data extraction and transformation.

### JSON
JavaScript Object Notation format for easy integration with modern web applications and APIs.

## SocialAssocInfo Structure

Social associations include relationship types and associated persons:

| Field | Description |
|-------|-------------|
| AssocName / AssocChName | Associated person's name |
| AssocId | Associated person's CBDB ID |
| AssocRelation | Relationship type (e.g., "Father", "Teacher", "Friend") |
| AssocRelationId | Relationship type ID |

## PostingInfo Structure

Official postings include:

| Field | Description |
|-------|-------------|
| PostingName | Office/position name (Chinese) |
| PostingNameEng | Office/position name (English) |
| PostingAddr | Location of posting |
| FirstYear / LastYear | Years of appointment |

## Best Practices

1. **URL Encoding**:
   - Spaces in Pinyin names should be encoded as `%20`
   - Chinese characters can be passed as UTF-8 (HTTP clients handle encoding)

2. **Output Format Selection**:
   - Use JSON for programmatic data extraction and processing
   - Use XML for structured data interchange with other systems
   - Use HTML for direct display to users

3. **Name Queries**: When searching by name:
   - Chinese characters often yield most accurate results
   - Pinyin may return multiple matches if names are similar
   - Consider trying both Chinese and Pinyin if initial query returns no results

4. **ID Queries**: When CBDB ID is known, always prefer ID-based queries as they are:
   - More precise (single person guaranteed)
   - Faster to process
   - Less ambiguous than name-based queries
