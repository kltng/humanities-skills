"""Offline tests for validate_tei.py (no network).

    cd tei-validator && python3 -m unittest discover -s tests
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
os.environ["TEI_VALIDATOR_HOME"] = tempfile.mkdtemp()

import validate_tei as vt  # noqa: E402

HEADER = ("<teiHeader><fileDesc><titleStmt><title>T</title></titleStmt><publicationStmt><p>x</p>"
          "</publicationStmt><sourceDesc><p>s</p></sourceDesc></fileDesc>{extra}</teiHeader>")


def tei(body: str, extra: str = "", root: str = "TEI") -> str:
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<{root} xmlns="http://www.tei-c.org/ns/1.0">\n'
            f"{HEADER.format(extra=extra)}\n<text><body>\n{body}\n</body></text></{root}>\n")


# A tiny RelaxNG schema: a TEI document whose body may only hold <p> with text.
TINY_RNG = """<grammar xmlns="http://relaxng.org/ns/structure/1.0" ns="http://www.tei-c.org/ns/1.0">
  <start><element name="TEI"><element name="teiHeader"><ref name="any"/></element>
    <element name="text"><element name="body"><oneOrMore><element name="p"><text/></element></oneOrMore>
    </element></element></element></start>
  <define name="any"><zeroOrMore><choice><element><anyName/><ref name="any"/></element><text/></choice>
  </zeroOrMore></define>
</grammar>"""


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir)

    def check(self, xml: str, level: str = "standard", **kw) -> vt.ValidationResult:
        f = self.dir / "doc.xml"
        f.write_text(xml, encoding="utf-8")
        return vt.TEIValidator(level=level, use_schema=kw.pop("use_schema", False), **kw).validate(str(f))

    @staticmethod
    def codes(r: vt.ValidationResult) -> list:
        return [i.code for i in r.all_issues]


class TestValidTEIPasses(Base):
    def test_legal_features_raise_nothing(self):
        body = """<p><date when="1865-04-14T10:30:00">morning</date> <date when="0044"/> <date when="12345">far</date>
<date when-custom="崇禎十年" datingMethod="#chinese">崇禎十年</date> <date when="-0044">44 BCE</date>
<date when="1600-02-29">leap</date> <date from="1861" to="1865">war</date> <date when="--04-14">day</date></p>
<p><persName ref="#a #b">two</persName> <persName ref="cbdb:1234">prefix</persName>
<persName ref="#p.1">dot</persName> <persName ref="persons.xml#li">other file</persName>
<placeName ref="https://www.wikidata.org/entity/Q1">x</placeName> <persName ref="#a"/></p>
<p xml:id="a">a</p><p xml:id="b">b</p><p xml:id="p.1">c</p><p xml:id="chinese">d</p>"""
        extra = ('<encodingDesc><listPrefixDef><prefixDef ident="cbdb" matchPattern="(\\d+)" '
                 'replacementPattern="https://cbdb.fas.harvard.edu/cbdbapi/person.php?id=$1"/></listPrefixDef>'
                 "</encodingDesc>")
        r = self.check(tei(body, extra))
        self.assertEqual(r.all_issues, [], [str(i) for i in r.all_issues])

    def test_tei_corpus(self):
        inner = tei("<p>x</p>").split("\n", 1)[1].replace(' xmlns="http://www.tei-c.org/ns/1.0"', "")
        xml = (f'<teiCorpus xmlns="http://www.tei-c.org/ns/1.0">{HEADER.format(extra="")}{inner}</teiCorpus>')
        self.assertTrue(self.check(xml).is_valid)

    def test_facsimile_only_record(self):
        xml = (f'<TEI xmlns="http://www.tei-c.org/ns/1.0">{HEADER.format(extra="")}'
               '<facsimile><surface><graphic url="p1.png"/></surface></facsimile></TEI>')
        self.assertTrue(self.check(xml).is_valid)


class TestProblemsFound(Base):
    def test_dates(self):
        r = self.check(tei('<p><date when="1865-02-30">a</date><date when="1900-02-29">b</date>'
                           '<date when="1865-13">c</date><date when="04/14/1865">d</date>'
                           '<date from="1870" to="1865">e</date><date>f</date></p>'))
        self.assertEqual(sorted(self.codes(r)),
                         ["DATE001", "DATE002", "DATE003", "DATE004", "DATE004", "DATE005"])

    def test_links_and_ids(self):
        r = self.check(tei('<p xml:id="x">a</p><p xml:id="x">b</p><p><persName ref="#x #nope">n</persName>'
                           '<persName ref="cbdb:1">m</persName><rs>r</rs><persName/></p>'))
        self.assertEqual(sorted(self.codes(r)), ["ENTITY001", "ENTITY002", "ID001", "REF002", "REF003"])
        self.assertFalse(r.is_valid)

    def test_structure(self):
        r = self.check('<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><titleStmt><title/>'
                       "</titleStmt></fileDesc></teiHeader><text/></TEI>")
        msgs = " ".join(i.message for i in r.errors)
        for want in ("publicationStmt", "sourceDesc", "body"):
            self.assertIn(want, msgs)
        self.assertIn("STRUCT002", self.codes(r))

    def test_namespace_and_root(self):
        self.assertEqual(self.codes(self.check("<TEI><text/></TEI>")), ["NS001"])
        self.assertEqual(self.codes(self.check("<html/>")), ["NS002"])

    def test_broken_xml_has_line(self):
        r = self.check("<TEI>\n<p>\n</TEI>")
        self.assertEqual((r.errors[0].code, r.errors[0].line), ("XML001", 3))

    def test_line_numbers_point_at_the_element(self):
        r = self.check(tei("<p><date>first</date></p>\n<p><date>second</date></p>"))
        self.assertEqual([i.line for i in r.warnings], [5, 6])

    def test_levels(self):
        xml = tei('<p><date when="1865-02-30">a</date></p>')
        self.assertTrue(self.check(xml, level="basic").is_valid)
        self.assertFalse(self.check(xml).is_valid)
        self.assertNotIn("BP005", self.codes(self.check(xml)))
        self.assertIn("BP005", self.codes(self.check(xml, level="strict")))


@unittest.skipUnless(shutil.which("xmllint"), "xmllint not installed")
class TestSchema(Base):
    def test_custom_schema_errors_have_lines(self):
        rng = self.dir / "tiny.rng"
        rng.write_text(TINY_RNG)
        ok = self.check(tei("<p>fine</p>"), use_schema=True, schema=str(rng))
        self.assertTrue(ok.is_valid, [str(i) for i in ok.all_issues])
        self.assertEqual(ok.schema, "tiny.rng")
        bad = self.check(tei("<p>fine</p>\n<foo/>"), use_schema=True, schema=str(rng))
        self.assertEqual([(i.code, i.line) for i in bad.errors], [("SCHEMA001", 6)])

    def test_many_files_one_call(self):
        rng = self.dir / "tiny.rng"
        rng.write_text(TINY_RNG)
        files = []
        for i, body in enumerate(["<p>a</p>", "<foo/>", "<p>c</p>"]):
            f = self.dir / f"f{i}.xml"
            f.write_text(tei(body))
            files.append(str(f))
        rs = vt.TEIValidator(schema=str(rng)).validate_many(files)
        self.assertEqual([r.is_valid for r in rs], [True, False, True])


class TestSchemaSetup(Base):
    def test_missing_schema_is_a_warning_not_a_crash(self):
        r = self.check(tei("<p>x</p>"), use_schema=True, schema=str(self.dir / "none.rng"))
        self.assertTrue(r.is_valid)
        self.assertEqual(self.codes(r), ["SCHEMA000"])
        self.assertIsNone(r.schema)

    def test_download_is_cached(self):
        fake = b'<?xml version="1.0"?><!-- TEI Edition Version 4.12.0 --><grammar xmlns="http://relaxng.org/ns/structure/1.0">' + b" " * 200_000 + b"</grammar>"
        resp = mock.MagicMock()
        resp.__enter__.return_value.read.return_value = fake
        with mock.patch.object(vt.urllib.request, "urlopen", return_value=resp) as u:
            p1 = vt.get_schema()
            p2 = vt.get_schema()
        self.assertEqual(u.call_count, 1)
        self.assertEqual(p1, p2)
        self.assertEqual(vt.schema_version(p1), "tei_all.rng 4.12.0")
        self.assertNotIn("@", u.call_args[0][0].get_header("User-agent"))  # no e-mail sent


class TestCommandLine(Base):
    def test_folder_json_and_exit_code(self):
        (self.dir / "sub").mkdir()
        (self.dir / "a.xml").write_text(tei("<p>a</p>"))
        (self.dir / "sub" / "b.xml").write_text(tei('<p><date when="2001-02-29">x</date></p>'))
        out = io.StringIO()
        with redirect_stdout(out):
            code = vt.main([str(self.dir), "--no-schema", "--json"])
        data = json.loads(out.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual([d["valid"] for d in data], [True, False])
        self.assertEqual(data[1]["errors"][0]["code"], "DATE004")


if __name__ == "__main__":
    unittest.main()
