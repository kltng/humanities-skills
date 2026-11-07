#!/usr/bin/env python3
"""
TEI Validator for archival documents.

Checks TEI P5 XML files in three layers:
  1. XML well-formedness and TEI structure (header, text or facsimile, body or group)
  2. the official TEI P5 RelaxNG schema (tei_all), run with xmllint
  3. checks the schema cannot make: broken #id links, duplicate xml:id, impossible dates,
     date ranges in the wrong order, undeclared pointer prefixes, archival best practices

Usage:
    python3 validate_tei.py document.xml
    python3 validate_tei.py folder/ more.xml --strict --json
    python3 validate_tei.py document.xml --schema my_project.rng
    python3 validate_tei.py document.xml --no-schema

Standard library only. The schema check needs `xmllint` (part of libxml2; built into macOS,
`apt install libxml2-utils` on Debian/Ubuntu). The TEI schema (about 1 MB) is downloaded once
and cached in ~/.cache/tei-validator (or $TEI_VALIDATOR_HOME).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET
from xml.parsers import expat

VERSION = "1.1.0"
TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI_NS}
T = f"{{{TEI_NS}}}"
XML_ID = f"{{{XML_NS}}}id"

SCHEMA_URL = "https://tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng"
USER_AGENT = f"humanities-skills-tei-validator/{VERSION} (+https://github.com/kltng/humanities-skills)"
LEVELS = ("basic", "standard", "strict")

# Attributes that hold normalized dates (att.datable.w3c / -iso / -custom).
DATE_ATTRS = ("when", "from", "to", "notBefore", "notAfter")
# Attributes whose values are pointers; '#id' targets must exist in the file.
POINTER_ATTRS = ("ref", "target", "corresp", "sameAs", "who", "next", "prev", "copyOf", "ana", "facs")
# URI schemes that never need a <prefixDef>.
KNOWN_SCHEMES = {"http", "https", "urn", "doi", "info", "mailto", "ftp", "file", "tag", "data", "ark"}

# W3C date forms allowed by TEI @when/@from/...: date, gYearMonth, gYear, dateTime, time,
# gMonthDay (--MM-DD), gMonth (--MM), gDay (---DD). Years may have more than 4 digits.
TZ = r"(Z|[+-]\d{2}:\d{2})?"
W3C_DATE = re.compile(
    r"^(?P<y>-?\d{4,})(-(?P<m>\d{2})(-(?P<d>\d{2})(T(?P<t>\d{2}:\d{2}:\d{2}(\.\d+)?))?)?)?" + TZ + "$")
W3C_OTHER = re.compile(r"^(\d{2}:\d{2}:\d{2}(\.\d+)?|--\d{2}(-\d{2})?|---\d{2})" + TZ + "$")


class Severity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ValidationIssue:
    code: str
    severity: Severity
    message: str
    line: Optional[int] = None
    element: Optional[str] = None
    suggestion: Optional[str] = None

    def __str__(self) -> str:
        loc = f" (line {self.line})" if self.line else ""
        elem = f" [{self.element}]" if self.element else ""
        return f"[{self.severity.value}] {self.code}{loc}{elem}: {self.message}"

    def as_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity.value, "message": self.message,
                "line": self.line, "element": self.element, "suggestion": self.suggestion}


@dataclass
class ValidationResult:
    is_valid: bool = True
    file: str = ""
    schema: Optional[str] = None  # which schema was used, or None if skipped
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    info: List[ValidationIssue] = field(default_factory=list)

    @property
    def all_issues(self) -> List[ValidationIssue]:
        return self.errors + self.warnings + self.info

    def add_issue(self, issue: ValidationIssue) -> None:
        if issue.severity == Severity.ERROR:
            self.errors.append(issue)
            self.is_valid = False
        elif issue.severity == Severity.WARNING:
            self.warnings.append(issue)
        else:
            self.info.append(issue)

    def as_dict(self) -> dict:
        return {"file": self.file, "valid": self.is_valid, "schema": self.schema,
                "errors": [i.as_dict() for i in self.errors],
                "warnings": [i.as_dict() for i in self.warnings],
                "info": [i.as_dict() for i in self.info]}


# ---------------------------------------------------------------- parsing with line numbers

def parse_with_lines(data: bytes) -> Tuple[ET.Element, Dict[ET.Element, int]]:
    """Parse XML with expat and remember the line where each element starts."""
    builder = ET.TreeBuilder()
    lines: Dict[ET.Element, int] = {}
    p = expat.ParserCreate(namespace_separator=" ")

    def name(n: str) -> str:
        return "{%s}%s" % tuple(n.split(" ", 1)) if " " in n else n

    def start(tag: str, attrs: dict) -> None:
        el = builder.start(name(tag), {name(k): v for k, v in attrs.items()})
        lines[el] = p.CurrentLineNumber

    p.StartElementHandler = start
    p.EndElementHandler = lambda tag: builder.end(name(tag))
    p.CharacterDataHandler = builder.data
    p.buffer_text = True
    p.Parse(data, True)
    return builder.close(), lines


def local(tag: str) -> str:
    return tag.split("}", 1)[1] if tag.startswith("{") else tag


def is_leap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def days_in_month(y: int, m: int) -> int:
    return 29 if m == 2 and is_leap(y) else [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]


def date_key(value: str) -> Optional[Tuple[int, int, int]]:
    """Sortable (y, m, d) for a W3C date, filling missing parts; None if not comparable."""
    m = W3C_DATE.match(value)
    if not m:
        return None
    return int(m["y"]), int(m["m"] or 0), int(m["d"] or 0)


# ---------------------------------------------------------------- schema (xmllint)

def cache_dir() -> Path:
    return Path(os.environ.get("TEI_VALIDATOR_HOME") or Path.home() / ".cache" / "tei-validator")


def schema_version(path: Path) -> str:
    """Read the TEI release from the schema's header comment, e.g. 'tei_all 4.9.0'."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return path.name
    m = re.search(r"Version\s+(\d+\.\d+\.\d+)", head)
    return f"{path.name} {m.group(1)}" if m else path.name


def get_schema(update: bool = False) -> Path:
    """Return the cached tei_all.rng, downloading it the first time (or with update=True)."""
    path = cache_dir() / "tei_all.rng"
    if path.exists() and path.stat().st_size > 100_000 and not update:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(SCHEMA_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if b"relaxng" not in data[:5000]:
        raise RuntimeError("the download is not a RelaxNG schema")
    tmp = path.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(path)
    return path


SCHEMA_LINE = re.compile(r"^(?P<file>.+?):(?P<line>\d+): (element (?P<el>[^:]+): )?Relax-NG validity error : (?P<msg>.*)$")


def run_xmllint(schema: Path, files: Sequence[str]) -> Dict[str, List[ValidationIssue]]:
    """Validate files against a RelaxNG schema in one xmllint call per chunk."""
    out: Dict[str, List[ValidationIssue]] = {f: [] for f in files}
    for i in range(0, len(files), 200):
        chunk = list(files[i:i + 200])
        proc = subprocess.run(["xmllint", "--noout", "--nonet", "--relaxng", str(schema), *chunk],
                              capture_output=True, text=True, errors="replace")
        by_len = sorted(chunk, key=len, reverse=True)
        for line in proc.stderr.splitlines():
            m = SCHEMA_LINE.match(line)
            if not m:
                if "failed to compile" in line or "Relax-NG parser error" in line:
                    raise RuntimeError(f"xmllint could not read the schema: {line.strip()}")
                continue
            f = next((f for f in by_len if m["file"] == f), None)
            if f is None:
                continue
            out[f].append(ValidationIssue("SCHEMA001", Severity.ERROR, m["msg"].strip(), line=int(m["line"]),
                                          element=m["el"], suggestion=None))
    return out


# ---------------------------------------------------------------- the validator

class TEIValidator:
    """Validate TEI P5 documents.

    level:  'basic' (XML + structure), 'standard' (+ schema, entities, dates, links), 'strict' (+ best practice)
    schema: path to a RelaxNG schema; None = the cached official tei_all.rng; use_schema=False skips it
    """

    def __init__(self, strict: bool = False, level: Optional[str] = None, schema: Optional[str] = None,
                 use_schema: bool = True, update_schema: bool = False):
        self.level = level or ("strict" if strict else "standard")
        if self.level not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}")
        self.strict = self.level == "strict"
        self.schema = Path(schema) if schema else None
        self.use_schema = use_schema and self.level != "basic"
        self.update_schema = update_schema
        self._schema_path: Optional[Path] = None
        self._schema_problem: Optional[str] = None
        self._parsed: Dict[str, bool] = {}

    # ----- public API

    def validate(self, filepath: str) -> ValidationResult:
        return self.validate_many([filepath])[0]

    def validate_many(self, filepaths: Iterable[str]) -> List[ValidationResult]:
        files = [str(f) for f in filepaths]
        results = [self._check_file(f) for f in files]
        if self.use_schema:
            ok = [r.file for r in results if self._parsed.get(r.file)]
            schema = self._prepare_schema() if ok else None
            if schema and ok:
                try:
                    found = run_xmllint(schema, ok)
                except (RuntimeError, OSError) as e:
                    self._schema_problem, found = str(e), {}
            else:
                found = {}
            for r in results:
                if r.file not in found:
                    if self._parsed.get(r.file):
                        r.add_issue(ValidationIssue("SCHEMA000", Severity.WARNING,
                                                    f"Schema check skipped: {self._schema_problem}",
                                                    suggestion="Install xmllint, or pass --schema PATH, or use --no-schema"))
                    continue
                r.schema = schema_version(schema)
                for issue in found[r.file]:
                    r.add_issue(issue)
                self._sort(r)
        return results

    # ----- internals

    def _prepare_schema(self) -> Optional[Path]:
        if self._schema_path or self._schema_problem:
            return self._schema_path
        if not shutil.which("xmllint"):
            self._schema_problem = "xmllint not found"
        elif self.schema:
            if self.schema.exists():
                self._schema_path = self.schema
            else:
                self._schema_problem = f"schema file not found: {self.schema}"
        else:
            try:
                self._schema_path = get_schema(self.update_schema)
            except Exception as e:  # network, disk
                self._schema_problem = f"could not download the TEI schema ({e})"
        return self._schema_path

    @staticmethod
    def _sort(r: ValidationResult) -> None:
        for lst in (r.errors, r.warnings, r.info):
            lst.sort(key=lambda i: (i.line or 0, i.code))

    def _check_file(self, filepath: str) -> ValidationResult:
        self.result = r = ValidationResult(file=filepath)
        self._parsed[filepath] = False
        path = Path(filepath)
        if not path.is_file():
            r.add_issue(ValidationIssue("FILE001", Severity.ERROR, f"File not found: {filepath}"))
            return r
        try:
            data = path.read_bytes()
        except OSError as e:
            r.add_issue(ValidationIssue("FILE002", Severity.ERROR, f"Cannot read file: {e}"))
            return r
        try:
            self.root, self.lines = parse_with_lines(data)
        except expat.ExpatError as e:
            r.add_issue(ValidationIssue("XML001", Severity.ERROR, f"XML parse error: {expat.ErrorString(e.code)}",
                                        line=e.lineno,
                                        suggestion="Check for unclosed tags, unescaped & or <, or the file encoding"))
            return r
        self._parsed[filepath] = True

        if self._check_namespace():
            self._check_structure(self.root)
        if self.level != "basic":
            self._index_ids()
            self._check_entities()
            self._check_dates()
            self._check_pointers()
        if self.strict:
            self._check_best_practices()
        self._sort(r)
        return r

    def _add(self, code: str, sev: Severity, msg: str, el: Optional[ET.Element] = None,
             suggestion: Optional[str] = None) -> None:
        self.result.add_issue(ValidationIssue(code, sev, msg, line=self.lines.get(el) if el is not None else None,
                                              element=local(el.tag) if el is not None else None,
                                              suggestion=suggestion))

    def _check_namespace(self) -> bool:
        tag = self.root.tag
        if tag in (T + "TEI", T + "teiCorpus"):
            return True
        if local(tag) in ("TEI", "teiCorpus"):
            self._add("NS001", Severity.ERROR, "Root element must use the TEI namespace", self.root,
                      f'Add xmlns="{TEI_NS}" to the root element')
        else:
            self._add("NS002", Severity.ERROR, f"Root element must be TEI or teiCorpus, found: {local(tag)}",
                      self.root)
        return False

    def _check_structure(self, el: ET.Element) -> None:
        """TEI: teiHeader, then text and/or facsimile/sourceDoc. teiCorpus: teiHeader, then TEI or teiCorpus."""
        header = el.find("tei:teiHeader", NS)
        if header is None:
            self._add("STRUCT001", Severity.ERROR, "Missing required element: teiHeader", el, "Add <teiHeader>")
        else:
            fd = header.find("tei:fileDesc", NS)
            if fd is None:
                self._add("STRUCT001", Severity.ERROR, "Missing required element: fileDesc", header)
            else:
                for path, what in (("tei:titleStmt", "titleStmt"), ("tei:titleStmt/tei:title", "title"),
                                   ("tei:publicationStmt", "publicationStmt"), ("tei:sourceDesc", "sourceDesc")):
                    found = fd.findall(path, NS)
                    if not found:
                        self._add("STRUCT001", Severity.ERROR, f"Missing required element: {what}", fd,
                                  f"Add <{what}> inside <fileDesc>")
                    elif not any("".join(x.itertext()).strip() or len(x) for x in found):
                        self._add("STRUCT002", Severity.WARNING, f"Empty element: {what}", found[0])
        if el.tag == T + "teiCorpus":
            members = [c for c in el if c.tag in (T + "TEI", T + "teiCorpus")]
            if not members:
                self._add("STRUCT003", Severity.ERROR, "teiCorpus has no TEI documents", el)
            for c in members:
                self._check_structure(c)
            return
        text = el.find("tei:text", NS)
        if text is None:
            if el.find("tei:facsimile", NS) is None and el.find("tei:sourceDoc", NS) is None:
                self._add("STRUCT001", Severity.ERROR, "Missing required element: text", el,
                          "Add <text> (or <facsimile>/<sourceDoc> for image-only records)")
        elif text.find("tei:body", NS) is None and text.find("tei:group", NS) is None:
            self._add("STRUCT001", Severity.ERROR, "Missing required element: body", text, "Add <body> inside <text>")

    def _index_ids(self) -> None:
        self.ids: Dict[str, ET.Element] = {}
        for el in self.root.iter():
            i = el.get(XML_ID)
            if i is None:
                continue
            if i in self.ids:
                self._add("ID001", Severity.ERROR, f"Duplicate xml:id '{i}' (first on line {self.lines.get(self.ids[i])})",
                          el, "Each xml:id must be unique in the file")
            else:
                self.ids[i] = el
        self.prefixes = {p.get("ident") for p in self.root.iter(T + "prefixDef") if p.get("ident")}

    def _check_entities(self) -> None:
        for name in ("persName", "placeName", "orgName", "rs", "date"):
            for el in self.root.iter(T + name):
                if "".join(el.itertext()).strip():
                    pass
                elif name == "date" and any(a.split("-")[0] in DATE_ATTRS for a in el.attrib):
                    pass  # <date when="1865"/> is a normal way to give a date
                elif "ref" in el.attrib or "key" in el.attrib:
                    pass  # an empty name that points to an authority
                else:
                    self._add("ENTITY001", Severity.WARNING, f"Empty <{name}> with no @ref or date", el,
                              "Add the name, or remove the element")
                if name == "rs" and "type" not in el.attrib:
                    self._add("ENTITY002", Severity.WARNING, "<rs> without @type", el,
                              'Add a type, e.g. type="event"')

    def _check_dates(self) -> None:
        for el in self.root.iter():
            if not el.tag.startswith(T):
                continue
            attrs = el.attrib
            for a in DATE_ATTRS:
                v = attrs.get(a)
                if v is not None:
                    self._check_w3c(el, a, v)
                v = attrs.get(a + "-iso")
                if v is not None and W3C_DATE.match(v):  # other ISO 8601 forms are allowed and not checked
                    self._check_w3c(el, a + "-iso", v)
            for lo, hi in (("from", "to"), ("notBefore", "notAfter")):
                for sfx in ("", "-iso"):
                    a, b = date_key(attrs.get(lo + sfx, "")), date_key(attrs.get(hi + sfx, ""))
                    if a and b and a > b:
                        self._add("DATE005", Severity.ERROR,
                                  f"@{lo}{sfx}='{attrs[lo + sfx]}' is after @{hi}{sfx}='{attrs[hi + sfx]}'", el)
            if el.tag == T + "date" and not any(k.split("-")[0] in DATE_ATTRS for k in attrs):
                self._add("DATE002", Severity.WARNING,
                          f"Date without a normalized value: '{''.join(el.itertext()).strip()[:30]}'", el,
                          "Add @when (or @from/@to, @notBefore/@notAfter); for reign or lunar dates use "
                          "@when-custom with @datingMethod")

    def _check_w3c(self, el: ET.Element, attr: str, v: str) -> None:
        m = W3C_DATE.match(v)
        if not m:
            if not W3C_OTHER.match(v):
                self._add("DATE001", Severity.ERROR, f"Invalid @{attr} format: '{v}'", el,
                          "Use YYYY, YYYY-MM, YYYY-MM-DD or YYYY-MM-DDThh:mm:ss (negative years for BCE)")
            return
        y = int(m["y"])
        if m["m"] and not 1 <= int(m["m"]) <= 12:
            self._add("DATE003", Severity.ERROR, f"Invalid month in @{attr}: '{v}'", el)
        elif m["d"] and not 1 <= int(m["d"]) <= days_in_month(y, int(m["m"])):
            self._add("DATE004", Severity.ERROR, f"Day does not exist in @{attr}: '{v}'", el,
                      "Dates are proleptic Gregorian; convert Julian or lunar dates first")

    def _check_pointers(self) -> None:
        for el in self.root.iter():
            for attr in POINTER_ATTRS:
                v = el.get(attr)
                if not v:
                    continue
                for tok in v.split():
                    if tok.startswith("#"):
                        if tok[1:] not in self.ids:
                            self._add("REF002", Severity.ERROR, f"Broken internal link in @{attr}: '{tok}'", el,
                                      f'Add an element with xml:id="{tok[1:]}"')
                        continue
                    scheme = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*):", tok)
                    if scheme and scheme.group(1).lower() not in KNOWN_SCHEMES and scheme.group(1) not in self.prefixes:
                        self._add("REF003", Severity.WARNING,
                                  f"Prefix '{scheme.group(1)}:' in @{attr} is not declared", el,
                                  f'Add <prefixDef ident="{scheme.group(1)}" ...> in <listPrefixDef> '
                                  "(encodingDesc), or use a full URI")
                    elif attr == "ref" and not scheme and not tok.startswith(("/", ".")) and "." not in tok and "/" not in tok:
                        self._add("REF001", Severity.WARNING, f"@ref '{tok}' does not look like a URI", el,
                                  "Use a full URI, #id, or a declared prefix (cbdb:1234)")

    def _check_best_practices(self) -> None:
        if self.root.find(".//tei:encodingDesc", NS) is None:
            self._add("BP001", Severity.INFO, "No <encodingDesc>", None,
                      "Describe the encoding and annotation practice")
        for sd in self.root.iter(T + "sourceDesc"):
            if not len(sd) and not (sd.text or "").strip():
                self._add("BP002", Severity.WARNING, "Empty <sourceDesc>", sd, "Add msDesc, bibl or p")
        names = [e for n in ("persName", "placeName", "orgName") for e in self.root.iter(T + n)]
        if names:
            with_ref = sum(1 for e in names if "ref" in e.attrib or "key" in e.attrib)
            if with_ref / len(names) < 0.5:
                self._add("BP003", Severity.INFO, f"Only {with_ref}/{len(names)} names have @ref", None,
                          "Link names to authorities (CBDB, CHGIS/TGAZ, VIAF, Wikidata, GeoNames)")
            standoff = self.root.find(".//tei:particDesc", NS) is not None or any(
                self.root.find(f".//tei:{x}", NS) is not None for x in ("listPerson", "listPlace", "listOrg"))
            if len(names) > 5 and not standoff:
                self._add("BP004", Severity.INFO, "Names are marked but there is no listPerson/listPlace/listOrg",
                          None, "Keep person and place records in particDesc, settingDesc or standOff")
        if self.root.find(".//tei:revisionDesc", NS) is None:
            self._add("BP005", Severity.INFO, "No <revisionDesc>", None, "Record changes in <revisionDesc>")
        for body in self.root.iter(T + "body"):
            if not "".join(body.itertext()).strip():
                self._add("BP006", Severity.WARNING, "<body> has no text", body)


# ---------------------------------------------------------------- command line

def expand(inputs: Sequence[Path]) -> List[str]:
    files: List[str] = []
    for p in inputs:
        if p.is_dir():
            files += sorted(str(f) for f in p.rglob("*.xml"))
        else:
            files.append(str(p))
    return files


def format_report(result: ValidationResult, filepath: Optional[str] = None, quiet: bool = False) -> str:
    lines = ["=" * 60, f"TEI VALIDATION: {filepath or result.file}",
             f"Status: {'VALID' if result.is_valid else 'INVALID'} | errors {len(result.errors)}, "
             f"warnings {len(result.warnings)}, info {len(result.info)} | schema: {result.schema or 'not checked'}",
             "-" * 60]
    groups = [("ERRORS", result.errors)] + ([] if quiet else [("WARNINGS", result.warnings), ("INFO", result.info)])
    for title, items in groups:
        if items:
            lines.append(f"{title}:")
            for i in items:
                lines.append(f"  {i}")
                if i.suggestion:
                    lines.append(f"    -> {i.suggestion}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", type=Path, help="TEI XML files or folders (folders: every *.xml inside)")
    ap.add_argument("--level", choices=LEVELS, help="basic, standard (default) or strict")
    ap.add_argument("--strict", action="store_true", help="same as --level strict")
    ap.add_argument("--schema", help="RelaxNG schema to use instead of the official tei_all.rng")
    ap.add_argument("--no-schema", action="store_true", help="skip the schema check")
    ap.add_argument("--update-schema", action="store_true", help="download tei_all.rng again")
    ap.add_argument("--report", type=Path, help="also write the text report to this file")
    ap.add_argument("--quiet", action="store_true", help="show errors only")
    ap.add_argument("--json", action="store_true", help="print results as JSON")
    a = ap.parse_args(argv)

    files = expand(a.inputs)
    if not files:
        print("No .xml files found.", file=sys.stderr)
        return 2
    v = TEIValidator(level=a.level or ("strict" if a.strict else "standard"), schema=a.schema,
                     use_schema=not a.no_schema, update_schema=a.update_schema)
    results = v.validate_many(files)
    bad = sum(not r.is_valid for r in results)

    if a.json:
        out = [r.as_dict() for r in results]
        print(json.dumps(out[0] if len(out) == 1 else out, indent=2, ensure_ascii=False))
    else:
        text = "\n\n".join(format_report(r, quiet=a.quiet) for r in results)
        if len(results) > 1:
            text += f"\n\n{'=' * 60}\n{len(results)} files: {len(results) - bad} valid, {bad} invalid"
        print(text)
        if a.report:
            a.report.write_text(text + "\n", encoding="utf-8")
            print(f"Report written to {a.report}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
