# Validation rules and codes

A file is VALID when it has no ERROR. WARNING means "should fix". INFO means "consider".

## File and XML

| Code | Severity | Meaning | Fix |
|---|---|---|---|
| FILE001 | ERROR | file not found | check the path |
| FILE002 | ERROR | file cannot be read | check the permissions |
| XML001 | ERROR | not well-formed XML (line given) | close tags; write `&` as `&amp;` and `<` as `&lt;`; check the encoding |

When the XML is broken, nothing else is checked.

## Namespace and structure

| Code | Severity | Meaning |
|---|---|---|
| NS001 | ERROR | the root is `TEI`/`teiCorpus` but not in the TEI namespace: add `xmlns="http://www.tei-c.org/ns/1.0"` |
| NS002 | ERROR | the root is not `TEI` or `teiCorpus` |
| STRUCT001 | ERROR | a required element is missing (see below) |
| STRUCT002 | WARNING | `titleStmt`, `title`, `publicationStmt` or `sourceDesc` is empty |
| STRUCT003 | ERROR | a `teiCorpus` holds no `TEI` documents |

Required structure:

- `TEI` needs `teiHeader/fileDesc` with `titleStmt/title`, `publicationStmt` and `sourceDesc`.
- It then needs `text` containing `body` or `group`. A record with `facsimile` or `sourceDoc` and no
  `text` is allowed.
- `teiCorpus` needs its own `teiHeader`, then one or more `TEI` or `teiCorpus` documents. Each one is
  checked in the same way.

## Schema

| Code | Severity | Meaning |
|---|---|---|
| SCHEMA001 | ERROR | the TEI schema (or your `--schema`) rejects the file. The message is xmllint's own, for example "Did not expect element foo there" or "Invalid attribute when for element date" |
| SCHEMA000 | WARNING | the schema was not checked: no `xmllint`, no schema file, or the download failed |

Common SCHEMA001 messages:

- **Did not expect element X there.** X is not a TEI element, or it is not allowed in this place, like
  `<p>` inside `<p>`, or `<div>` inside `<p>`.
- **Expecting element X, got nothing.** A required child is missing.
- **Invalid attribute A for element E.** The attribute does not exist on E, or its value is wrong (for
  example a date that does not exist in `@when`).
- **Element E failed to validate content.** This usually follows another error inside E. Fix the inner
  error first.

## Ids and links

| Code | Severity | Meaning |
|---|---|---|
| ID001 | ERROR | the same `xml:id` is used twice |
| REF002 | ERROR | a `#id` pointer has no target |
| REF003 | WARNING | a prefix such as `cbdb:` is used with no `<prefixDef ident="cbdb">` |
| REF001 | WARNING | `@ref` is a bare word, not a URI, `#id` or prefix |

Pointer attributes checked: `ref`, `target`, `corresp`, `sameAs`, `who`, `next`, `prev`, `copyOf`, `ana`
and `facs`.

Each value can hold several pointers separated by spaces (`ref="#a #b"`), and each one is checked. These
schemes need no `prefixDef`: `http`, `https`, `urn`, `doi`, `info`, `mailto`, `ftp`, `file`, `tag`,
`data` and `ark`. A link to another file (`persons.xml#li`) is accepted, but the other file is not opened.

Declaring a prefix:

```xml
<encodingDesc>
  <listPrefixDef>
    <prefixDef ident="cbdb" matchPattern="(\d+)"
      replacementPattern="https://cbdb.fas.harvard.edu/cbdbapi/person.php?id=$1"/>
  </listPrefixDef>
</encodingDesc>
...
<persName ref="cbdb:30374">王守仁</persName>
```

Authority URI patterns:

| Authority | Pattern |
|---|---|
| CBDB | `https://cbdb.fas.harvard.edu/cbdbapi/person.php?id={id}` |
| CHGIS TGAZ | `https://maps.cga.harvard.edu/tgaz/placename/{hvd_id}` |
| Wikidata | `https://www.wikidata.org/entity/{Qid}` |
| VIAF | `https://viaf.org/viaf/{id}` |
| LC Name Authority | `https://id.loc.gov/authorities/names/{id}` |
| GeoNames | `https://www.geonames.org/{id}` |

## Names

| Code | Severity | Meaning |
|---|---|---|
| ENTITY001 | WARNING | an empty `persName`, `placeName`, `orgName`, `rs` or `date`, with no `@ref`/`@key` (or for a date, no date attribute) |
| ENTITY002 | WARNING | `<rs>` has no `@type`, for example `type="event"` or `type="work"` |

An empty element that carries a link, like `<persName ref="#wang"/>` or `<date when="1865"/>`, is
accepted.

## Dates

| Code | Severity | Meaning |
|---|---|---|
| DATE001 | ERROR | `@when`, `@from`, `@to`, `@notBefore` or `@notAfter` is not a W3C date |
| DATE002 | WARNING | a `<date>` has no normalized value |
| DATE003 | ERROR | the month is not 01–12 |
| DATE004 | ERROR | the day does not exist in that month (leap years are counted) |
| DATE005 | ERROR | `@from` is after `@to`, or `@notBefore` is after `@notAfter` |

These forms are accepted in `@when` and the other date attributes:

- `1865`, `1865-04`, `1865-04-14`;
- `1865-04-14T10:30:00`, optionally with `Z` or `+08:00`;
- `-0044` for 44 BCE;
- years with more than four digits;
- `--04-14` (a day of the year), `--04` (a month), `---14` (a day).

The checks apply to every TEI element that has these attributes (`date`, `change`, `birth`, `death`,
`event` …), not only `<date>`.

The `-iso` forms (`@when-iso` …) are checked in the same way when they look like simple dates. Other ISO
8601 forms in them, such as week dates or intervals, are accepted without checks.

The `-custom` forms (`@when-custom` …) are not checked. They are meant for other calendars. Give
`@datingMethod` with them.

`@when` is always Gregorian: the proleptic Gregorian calendar, also used for dates before 1582. Convert
Julian, Chinese, Japanese or Korean dates before you put them in `@when`. The `cjk-calendar` skill does
this. If the Gregorian date is not known, use `@when-custom`:

```xml
<date when="1637-02-25">崇禎十年二月初一</date>
<date when-custom="崇禎十年" datingMethod="#chongzhen">崇禎十年</date>
<date notBefore="1628" notAfter="1644">崇禎年間</date>
```

## Best practice (strict only)

| Code | Severity | Meaning |
|---|---|---|
| BP001 | INFO | no `<encodingDesc>`: describe how the text was encoded and annotated |
| BP002 | WARNING | an empty `<sourceDesc>`: describe the source with `msDesc`, `bibl` or `p` |
| BP003 | INFO | fewer than half of the names have `@ref` or `@key` |
| BP004 | INFO | more than 5 names but no `listPerson`, `listPlace`, `listOrg` or `particDesc` |
| BP005 | INFO | no `<revisionDesc>` |
| BP006 | WARNING | a `<body>` with no text at all |
