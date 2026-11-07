---
name: tei-validator
description: >-
  Validate TEI P5 XML files (single files, folders or teiCorpus files) for archival and historical
  editions. Checks XML well-formedness and TEI structure, validates against the official TEI P5 RelaxNG
  schema (tei_all, via xmllint), and adds the checks a schema cannot make: broken #id links, duplicate
  xml:id, impossible dates (Feb 30), date ranges in the wrong order, undeclared pointer prefixes such as
  cbdb: or tgaz:, empty or untyped name markup, and archival best practice (authority links, entity lists,
  revision history). Reports line numbers, as text or JSON. Use when the user wants to validate, check or
  audit a TEI file, asks whether their TEI is correct or schema-valid, checks named-entity or date
  markup, or wants to check TEI exported by OCR or annotation tools before publishing.
version: 1.1.0
license: MIT
author: Kwok-leong Tang
contributors:
  - Claude (Anthropic)
---

# TEI Validator

## Overview

`scripts/validate_tei.py` checks TEI P5 files in three layers:

1. **XML and structure.** The file must be well-formed XML with a `TEI` or `teiCorpus` root in the TEI
   namespace. It needs a `teiHeader` with `titleStmt/title`, `publicationStmt` and `sourceDesc`, then a
   `text` with a `body` or `group`. A record that has only page images (`facsimile` or `sourceDoc`) is
   also accepted.
2. **The TEI schema.** The official `tei_all.rng` schema, run with `xmllint`. This catches wrong element
   names, wrong nesting and wrong attribute values. The schema (about 1 MB) is downloaded once and cached.
3. **Checks the schema cannot make:**
   - `#id` links that point nowhere;
   - duplicate `xml:id` values;
   - days that do not exist (1865-02-30);
   - `@from` after `@to`;
   - pointer prefixes like `cbdb:1234` with no `<prefixDef>`;
   - empty names, and `<rs>` with no `@type`;
   - in strict mode, archival best practice.

It uses only the Python standard library. `xmllint` is part of libxml2: it comes with macOS, and on
Debian or Ubuntu it is installed with `apt install libxml2-utils`. Without `xmllint`, layers 1 and 3
still run, and the report says that the schema was not checked.

## When to Use

- The user asks whether a TEI file is valid, correct or follows the schema.
- Before publishing or depositing a TEI edition, or after a tool made TEI: OCR exports such as
  `local-ocr` or `multi-agent-vision-ocr`, entity annotation, or conversion scripts.
- When checking name and date markup: authority links (CBDB, CHGIS/TGAZ, Wikidata, VIAF), normalized
  dates, and reign or lunar dates given with `@when-custom`.
- When checking a whole folder of TEI files.

It does **not** check whether the text matches the source. It does not check whether an external URI
resolves. It does not check a project's own ODD rules unless you pass that project's schema with `--schema`.

## Workflow

1. **Find the files.** One file, several files, or a folder. A folder means every `*.xml` file inside
   it, including subfolders.
2. **Pick the level.**

   | Level | What it checks | Use |
   |---|---|---|
   | `basic` | XML, namespace, required structure | quick syntax check |
   | `standard` (default) | + TEI schema, names, dates, links, ids | normal check |
   | `strict` | + best practice (encodingDesc, revisionDesc, authority links, entity lists) | before publishing |

3. **Run it.**
   ```bash
   python3 scripts/validate_tei.py edition/ --strict
   ```
   The first run downloads the schema. Each run spends about 8 s reading the schema. A whole folder is
   checked in one `xmllint` call, so check folders, not files one by one.
4. **Read the report.** Each problem has a code, a line number, the element and a suggested fix. The
   file is VALID when there are no ERRORs. Warnings and INFO do not change the exit code.
5. **Fix and run again.** The codes are explained in
   [references/validation-rules.md](references/validation-rules.md). Fix the schema errors (`SCHEMA001`)
   first: one nesting mistake can cause several follow-on errors.

## Options

| Option | Meaning |
|---|---|
| `--level basic\|standard\|strict` | how much to check (`--strict` = `--level strict`) |
| `--schema PATH` | use your own RelaxNG schema (for example one made from a project ODD) instead of `tei_all.rng` |
| `--no-schema` | skip the schema check (offline, or no `xmllint`) |
| `--update-schema` | download `tei_all.rng` again (new TEI release) |
| `--json` | print JSON (one object for one file, a list for several) |
| `--report FILE` | also write the text report to a file |
| `--quiet` | show errors only |

Exit code: 0 if all files are valid, 1 if any file has an error, 2 if no XML files were found.

## Best Practices

- Run `--strict` before you publish. `standard` is enough while you work.
- Keep the schema check on. Most real mistakes, such as a wrong element name or a `<p>` inside a `<p>`,
  are only found by the schema.
- For Chinese, Japanese or Korean dates, give the reign date in the text. Add `@when` when the
  Gregorian date is known, or `@when-custom` with `@datingMethod` when it is not. Convert dates with the
  `cjk-calendar` skill. Do not put a lunar date in `@when`: `@when` is always a Gregorian date.
- Short authority links like `ref="cbdb:30374"` are good TEI, but declare the prefix once in
  `encodingDesc/listPrefixDef`. Otherwise other tools cannot expand it (`REF003`).
- A file of 10,000 lines can have hundreds of follow-on schema errors. Use `--json` and count them by
  code to see the pattern.

## Example Code

```bash
# one file
python3 scripts/validate_tei.py letter.xml

# a folder, strict, JSON for a script
python3 scripts/validate_tei.py edition/ --strict --json > validation.json

# a project schema made from an ODD
python3 scripts/validate_tei.py edition/ --schema myproject.rng
```

```python
import sys
sys.path.insert(0, "scripts")
from validate_tei import TEIValidator

v = TEIValidator(level="strict")            # schema=PATH, use_schema=False also work
for r in v.validate_many(["a.xml", "b.xml"]):
    print(r.file, "valid" if r.is_valid else "INVALID", r.schema)
    for e in r.errors:
        print(f"  {e.code} line {e.line}: {e.message}")
```

A minimal valid file:

```xml
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader><fileDesc>
    <titleStmt><title>崇禎十年家書</title></titleStmt>
    <publicationStmt><p>Unpublished transcription</p></publicationStmt>
    <sourceDesc><p>Manuscript letter, private collection</p></sourceDesc>
  </fileDesc></teiHeader>
  <text><body>
    <p><date when-custom="崇禎十年" datingMethod="#chongzhen">崇禎十年</date>
       <persName ref="https://cbdb.fas.harvard.edu/cbdbapi/person.php?id=30374">王守仁</persName></p>
  </body></text>
</TEI>
```

## Resources

- [references/api_reference.md](references/api_reference.md): command line, Python API, JSON output, schema cache
- [references/validation-rules.md](references/validation-rules.md): every check and code, with fixes
- TEI P5 Guidelines: https://tei-c.org/guidelines/p5/
- The `tei_all` schema: https://tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng
- TEI Roma (build a project schema from an ODD): https://roma.tei-c.org/

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "tei-validator"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[tei-validator] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: tei-validator* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
