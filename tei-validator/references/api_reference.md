# tei-validator: command line, Python API and output

## Command line

`python3 scripts/validate_tei.py INPUT... [options]`

`INPUT` is one or more files or folders. A folder means every `*.xml` file inside it, including
subfolders, in sorted order.

| Option | Meaning |
|---|---|
| `--level basic\|standard\|strict` | default `standard` |
| `--strict` | same as `--level strict` |
| `--schema PATH` | a RelaxNG (`.rng`) schema to use instead of `tei_all.rng` |
| `--no-schema` | skip the schema check |
| `--update-schema` | download `tei_all.rng` again |
| `--json` | JSON output |
| `--report FILE` | also write the text report to `FILE` |
| `--quiet` | text output shows errors only |

Exit codes: `0` all valid, `1` at least one file has an ERROR, `2` no `.xml` files found.

What each level runs:

| Check | basic | standard | strict |
|---|---|---|---|
| XML, namespace, structure (`XML`, `NS`, `STRUCT`) | yes | yes | yes |
| TEI schema (`SCHEMA`) | | yes | yes |
| ids, links, names, dates (`ID`, `REF`, `ENTITY`, `DATE`) | | yes | yes |
| best practice (`BP`) | | | yes |

## The schema

- Default schema: `https://tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng` (current TEI
  release, about 1 MB).
- It is cached at `~/.cache/tei-validator/tei_all.rng`, or `$TEI_VALIDATOR_HOME/tei_all.rng`. It is
  downloaded on the first run that needs it, with a generic User-Agent
  (`humanities-skills-tei-validator/<version>`).
- It is run with `xmllint --noout --nonet --relaxng SCHEMA FILE...`, in chunks of 200 files. Reading
  `tei_all.rng` takes about 8 s per call, whether there is one file or many.
- Files that are not well-formed XML are not sent to `xmllint`.
- If `xmllint` is missing, the schema file is missing, or the download fails, each file gets a `SCHEMA000`
  warning. The other checks still run, and `schema` in the JSON output is `null`.
- The report names the schema and its TEI version, for example `tei_all.rng 4.12.0`.

## JSON output

One file gives one object. Several files give a list of objects:

```json
{
  "file": "edition/letter1.xml",
  "valid": false,
  "schema": "tei_all.rng 4.12.0",
  "errors": [
    {"code": "SCHEMA001", "severity": "ERROR", "message": "Did not expect element foo there",
     "line": 41, "element": "foo", "suggestion": null}
  ],
  "warnings": [],
  "info": []
}
```

`line` is the line where the element starts. It is `null` for issues about the whole document (most BP
codes).

## Python API

```python
from validate_tei import TEIValidator, format_report

v = TEIValidator(level="standard", schema=None, use_schema=True, update_schema=False)
r = v.validate("file.xml")              # one ValidationResult
rs = v.validate_many(["a.xml", "b.xml"])  # one xmllint call for all files
```

- `TEIValidator(strict=True)` still works, as the same as `level="strict"`.
- `ValidationResult` has these fields:
  - `is_valid`, `file`, `schema`;
  - `errors`, `warnings` and `info`, each a list of `ValidationIssue`;
  - `all_issues`, and `as_dict()`.
- `ValidationIssue` has `code`, `severity` (`Severity.ERROR` / `WARNING` / `INFO`), `message`, `line`,
  `element`, `suggestion` and `as_dict()`.
- `format_report(result, quiet=False)` returns the text report.

## Tests

```bash
cd tei-validator && python3 -m unittest discover -s tests
```

The tests are offline. The schema tests use a small RelaxNG schema, and they are skipped when `xmllint`
is not installed.
