# Yale University Library — Alma SRU API Reference

## Endpoint

```
https://yale.alma.exlibrisgroup.com/view/sru/01YALE_INST
```

- No API key, no login.
- Protocol: SRU 1.2. Query language: CQL.
- Server description (all indexes, schemas): `?version=1.2&operation=explain`

## Request Parameters (searchRetrieve)

| Param | Required | Description | Example |
|-------|----------|-------------|---------|
| `version` | yes | Always `1.2` | `1.2` |
| `operation` | yes | `searchRetrieve` or `explain` | `searchRetrieve` |
| `query` | yes | CQL query (URL-encoded) | `alma.title="明史"` |
| `maximumRecords` | no | Records per page, **max 50** (default 10) | `50` |
| `startRecord` | no | 1-based position of first record | `51` |
| `recordSchema` | no | `marcxml` (default), `dc`, `mods`, `dcx` | `marcxml` |

`sortKeys` is accepted but **ignored**. Sort with `sortBy` inside the CQL instead.

## CQL Syntax

```
alma.title="明史"                                   all words, anywhere in the title (NOT a phrase)
alma.title=明史 and alma.language=chi               AND
alma.creator="Brook, Timothy" or alma.creator=卜正民  OR
alma.title=Ming not alma.title=Qing                 NOT
alma.lc_class_number=DS753*                         truncation (unquoted)
alma.main_pub_date<1700                             range (also >, >=, <=)
alma.main_pub_date>=1600 and alma.main_pub_date<1700
alma.title=明史 sortBy alma.main_pub_date/sort.descending
```

Relations: `=` (all words, any order, anywhere — quotes and `adj` do not make a phrase), `==` (the whole field, exactly), `all`, `<>`, and `< > <= >=` on date and ID indexes.

CJK titles are split into words by a dictionary, so a CJK term can miss a title that contains it (文廟 misses 文廟祀典考, indexed as 文 / 廟祀 / 典考). Search traditional, simplified, and romanized forms and merge.

Subject indexes: drop the ` -- ` from LCSH strings and use the inverted LC form (`Temples, Confucian`).

Sortable indexes: `alma.title`, `alma.creator`, `alma.main_pub_date` (`/sort.ascending` or `/sort.descending`).

Records with an unknown date (`uuuu`) sort first in ascending order. Add `alma.main_pub_date>=1000` to leave them out. (`alma.main_pub_date>0` returns nothing.)

## Useful Indexes

The `explain` response lists about 400 indexes. These are the most useful for research:

| Index | Script field | Notes |
|-------|--------------|-------|
| `alma.all_for_ui` | `keyword` | All fields (keyword search) |
| `alma.title` | `title` | Title words, romanized or vernacular |
| `alma.creator` | `author` | Personal/corporate authors |
| `alma.subjects` | `subject` | All subject headings |
| `alma.lcsh` | — | LC subject headings only |
| `alma.isbn` | `isbn` | |
| `alma.issn` | `issn` | |
| `alma.oclc_control_number_035_a` | `oclc` | Plain number, e.g. `424023` |
| `alma.lccn` | `lccn` | |
| `alma.publisher` | `publisher` | |
| `alma.publisher_location` | — | Place of publication |
| `alma.series` | `series` | |
| `alma.lc_class_number` | `call_number` | Use `*` for ranges |
| `alma.local_call_numbers` | — | Local (non-LC) call numbers |
| `alma.language` | `language` | MARC language code: `chi`, `jpn`, `kor`, `eng`, `fre`, … |
| `alma.main_pub_date` | — | Year; supports `< > <= >=` |
| `alma.mms_id` | `mms_id` | Alma record ID |
| `alma.mms_material_type` | — | e.g. `BOOK` |
| `alma.genre_form` | — | Genre/form terms |
| `alma.uniform_title` | — | Uniform title |
| `alma.name` | — | Any name field |

An unknown index returns the diagnostic "Catalog search has encountered an error".

## Response

```xml
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <version>1.2</version>
  <numberOfRecords>207</numberOfRecords>
  <records>
    <record>
      <recordSchema>marcxml</recordSchema>
      <recordData>
        <record xmlns="http://www.loc.gov/MARC21/slim"> ... </record>
      </recordData>
      <recordPosition>1</recordPosition>
    </record>
  </records>
</searchRetrieveResponse>
```

Errors come back as `<diagnostics><diagnostic><message>…</message></diagnostic></diagnostics>`, sometimes with HTTP 400.

## MARC Fields Used by the Script

| Tag | Content |
|-----|---------|
| `001` | MMS ID (record ID) |
| `008` | Fixed data: positions 7–10 = date 1, 35–37 = language |
| `010 $a` | LCCN |
| `020 $a` | ISBN |
| `035 $a` | System numbers; `(OCoLC)…` = OCLC number |
| `050 $a $b` | LC call number |
| `100/110/111` | Main author |
| `245 $a $b $n $p` | Title |
| `250` | Edition |
| `260/264 $a $b $c` | Place, publisher, date |
| `300` | Physical description |
| `490/830` | Series |
| `600–651` | Subjects |
| `700/710/711` | Other contributors |
| `880` | Vernacular script version of a linked field |

### 880 linking

A romanized field carries `$6 880-01`. Its partner 880 field carries `$6 245-01/$1` (tag of the romanized field, same occurrence number, then script code). `$1` = CJK.

### AVA — physical holdings (Alma-generated)

| Subfield | Meaning | Example |
|----------|---------|---------|
| `$b` | Library code | `BUHR` |
| `$q` | Library name | `Buhr Shelving Facility` |
| `$c` | Location name | `Main` |
| `$j` | Location code | `MAIN` |
| `$d` | Call number | `Z 3102 .P15` |
| `$e` | Availability | `available`, `unavailable`, `check_holdings` |
| `$f` | Total items | `2` |
| `$g` | Unavailable items | `0` |
| `$t` | Summary holdings (volumes) | `(v.1-16 1883)` |
| `$8` | Holdings ID | |

### AVE — electronic access (Alma-generated)

| Subfield | Meaning | Example |
|----------|---------|---------|
| `$m` | Collection name | `Taylor & Francis eBooks Complete` |
| `$t` | Interface/platform (script key `interface`) | `EBSCOhost` |
| `$e` | Availability | `Available` |
| `$n` | Public note | `Online book` |
| `$u` | Access link (only some libraries supply it) | OpenURL |
| `$8` | Portfolio ID | |

When `$u` is missing, link users to the record page instead.

## Record Page Link

```
https://search.library.yale.edu/catalog/{mms_id}
```

Opens Quicksearch (search.library.yale.edu) in a browser. Do not fetch it from scripts.

## Etiquette

- At least 1 second between requests.
- Set a descriptive `User-Agent`.
- On HTTP 429 or 503, wait for `Retry-After` and retry.
- For large harvests, ask Yale University Library rather than paging through SRU.
