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

The API returns comprehensive biographical data including:

- Basic information (name, alternative names, gender, dynasty)
- Birth and death dates/locations
- Biographical notes and historical context
- Social relationships and associations
- Official positions and titles
- Literary works and writings
- Geographic locations associated with the person
- References to source materials

## Output Formats

### HTML
The default format provides a formatted web page suitable for direct viewing in a browser.

### XML
Structured XML output following CBDB's schema, providing maximum flexibility for data extraction and transformation.

### JSON
JavaScript Object Notation format for easy integration with modern web applications and APIs.

## Best Practices

1. **URL Encoding**: Always URL-encode query parameters, especially for:
   - Chinese characters
   - Spaces in Pinyin names
   - Special characters

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
