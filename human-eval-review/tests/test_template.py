"""Tests for the review page (scripts/template.html).

The behaviour test runs tests/template_behavior.js in Node with jsdom. It is
skipped when Node or jsdom is missing. To run it:

    npm install --prefix /tmp/jsdom jsdom
    NODE_PATH=/tmp/jsdom/node_modules python3 -m unittest discover -s tests
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, SKILL)

from scripts.review_builder import ReviewBuilder  # noqa: E402


def build_sample(path: str) -> None:
    """Two items: a match + single question, then two single and two rating questions."""
    rb = ReviewBuilder(title="Test review", lang="zh-Hant", cjk=True)
    it = rb.add_item(source="王鏊", heading="A")
    q = it.add_question(type="match", id="m", allow_none=True)
    q.add_candidate(id="c1", title="王鏊 1450", preselected=True)
    q.add_candidate(id="c2", title="王鏊 other")
    q2 = it.add_question(type="single", id="s", allow_none=True)
    q2.add_candidate(id="x1", title="x1")
    q2.add_candidate(id="x2", title="x2")
    it2 = rb.add_item(source="two", heading="B")
    a = it2.add_question(type="single", id="a", allow_none=True, prompt="first")
    a.add_candidate(id="a1", title="a1")
    a.add_candidate(id="a2", title="a2")
    b = it2.add_question(type="single", id="b", allow_none=True, prompt="second")
    b.add_candidate(id="b1", title="b1")
    b.add_candidate(id="b2", title="b2")
    it2.add_question(type="rating", id="r1")
    it2.add_question(type="rating", id="r2")
    rb.save_html(path)


def jsdom_available() -> bool:
    if not shutil.which("node"):
        return False
    r = subprocess.run(["node", "-e", "require('jsdom')"], capture_output=True)
    return r.returncode == 0


class TemplateStaticTest(unittest.TestCase):
    def setUp(self) -> None:
        with open(os.path.join(SKILL, "scripts", "template.html"), encoding="utf-8") as f:
            self.src = f.read()

    def test_none_row_has_only_its_own_handler(self) -> None:
        # The None row must not get onCandChange, which would un-tick it.
        self.assertIn("itype, () => onNoneChange(qi, q))", self.src)
        self.assertNotIn("li.querySelector('input').addEventListener('change', () => onNoneChange", self.src)

    def test_keyboard_targets_question_block(self) -> None:
        self.assertIn("QLIST[qi].block = qBlock;", self.src)
        self.assertNotIn("QLIST[qi].block = card;", self.src)


@unittest.skipUnless(jsdom_available(), "node + jsdom not installed")
class TemplateBehaviourTest(unittest.TestCase):
    def test_behaviour_in_jsdom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = os.path.join(tmp, "review.html")
            build_sample(html)
            r = subprocess.run(
                ["node", os.path.join(HERE, "template_behavior.js"), html],
                capture_output=True, text=True,
            )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 failed", r.stdout)


if __name__ == "__main__":
    unittest.main()
