"""
Human-eval review builder — zero external dependencies.

Turns a set of items (each with one or more review questions) into a single,
self-contained HTML file for human-in-the-loop evaluation. No server, no build
step, no CDN — open the file in any browser. The reviewer's selections export
to JSON and can be re-loaded to resume.

Two ways to use it:

1. Programmatic (shape data from arbitrary analysis output):

    from review_builder import ReviewBuilder

    rb = ReviewBuilder(title="Match Review", subtitle="run 2026-05", cjk=True, lang="zh-Hant")
    item = rb.add_item(source="毛陳氏賣契壹紙…", heading="Entry 1")
    q = item.add_question(type="match", prompt="賣契", allow_none=True, notes=True)
    q.add_candidate(id="1496", label="1496", excerpt="立賣契<mark>毛陳氏</mark>…",
                    score=88, reason="標記為賣契", preselected=True)
    q.add_excluded(id="1502", label="1502", excerpt="…", score=20)
    rb.save_html("review.html")

2. From a data dict / JSON file (config + items):

    from review_builder import render_html, load_data
    render_html(load_data("data.json"), "review.html")

CLI:

    python review_builder.py data.json -o review.html
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html")

_VALID_TYPES = {"match", "single", "rating", "boolean", "text"}


# ──────────────────────────────────────────────────────────────────────────────
# Rendering
# ──────────────────────────────────────────────────────────────────────────────
def _js_embed(obj: Any) -> str:
    """Serialize to JSON safe to embed inside an inline <script> block.

    Escapes `<`, `>`, `&` (and line/paragraph separators) so the HTML parser
    never ends the script early. The JS engine un-escapes them back, so any
    HTML inside string fields (e.g. ``<mark>`` in excerpts) survives intact.
    """
    s = json.dumps(obj, ensure_ascii=False)
    return (
        s.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _attr(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
    )


def render_html(data: dict[str, Any], out_path: Optional[str] = None) -> str:
    """Render a ``{"config": {...}, "items": [...]}`` dict into standalone HTML.

    Returns the HTML string. If ``out_path`` is given, also writes it there.
    """
    config = dict(data.get("config") or {})
    items = data.get("items") or []
    if not config.get("title"):
        config["title"] = "Review"

    with open(_TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()

    html = (
        template.replace("__LANG__", _attr(str(config.get("lang", "en"))))
        .replace("__TITLE__", _attr(str(config["title"])))
        .replace("__CONFIG__", _js_embed(config))
        .replace("__DATA__", _js_embed(items))
    )

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
    return html


def load_data(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────────────────────────────────────
# Fluent builder
# ──────────────────────────────────────────────────────────────────────────────
def _clean(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


class Question:
    """A single review question attached to an item."""

    def __init__(
        self,
        id: str,
        type: str = "match",
        prompt: Optional[str] = None,
        allow_none: bool = False,
        notes: bool = False,
        scale: Optional[dict[str, Any]] = None,
        labels: Optional[dict[str, str]] = None,
        placeholder: Optional[str] = None,
        rows: Optional[int] = None,
        default: Any = None,
    ) -> None:
        if type not in _VALID_TYPES:
            raise ValueError(f"type must be one of {sorted(_VALID_TYPES)}, got {type!r}")
        self.id = id
        self.type = type
        self.prompt = prompt
        self.allow_none = allow_none
        self.notes = notes
        self.scale = scale
        self.labels = labels
        self.placeholder = placeholder
        self.rows = rows
        self.default = default
        self.candidates: list[dict[str, Any]] = []
        self.excluded: list[dict[str, Any]] = []

    def add_candidate(
        self,
        id: str,
        label: Optional[str] = None,
        title: Optional[str] = None,
        excerpt: Optional[str] = None,
        score: Optional[float] = None,
        reason: Optional[str] = None,
        preselected: bool = False,
    ) -> "Question":
        """Add a selectable candidate. ``excerpt`` may contain HTML (e.g. ``<mark>``)."""
        self.candidates.append(
            _clean(
                {
                    "id": str(id),
                    "label": label,
                    "title": title,
                    "excerpt": excerpt,
                    "score": score,
                    "reason": reason,
                    "preselected": True if preselected else None,
                }
            )
        )
        return self

    def add_excluded(self, id: str, **kwargs: Any) -> "Question":
        """Add a candidate to the collapsed 'excluded' section (still selectable)."""
        q = Question("_tmp")
        q.add_candidate(id, **kwargs)
        self.excluded.append(q.candidates[0])
        return self

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = _clean(
            {
                "id": self.id,
                "type": self.type,
                "prompt": self.prompt,
                "allow_none": True if self.allow_none else None,
                "notes": True if self.notes else None,
                "scale": self.scale,
                "labels": self.labels,
                "placeholder": self.placeholder,
                "rows": self.rows,
                "default": self.default,
            }
        )
        if self.candidates:
            d["candidates"] = self.candidates
        if self.excluded:
            d["excluded"] = self.excluded
        return d


class Item:
    """One source item under review, holding one or more questions."""

    def __init__(
        self,
        id: str,
        source: Optional[str] = None,
        heading: Optional[str] = None,
        source_html: bool = False,
        context: Optional[list[dict[str, str]]] = None,
    ) -> None:
        self.id = id
        self.source = source
        self.heading = heading
        self.source_html = source_html
        self.context = context or []
        self.questions: list[Question] = []

    def add_context(self, label: str, value: str) -> "Item":
        self.context.append({"label": label, "value": value})
        return self

    def add_question(self, type: str = "match", id: Optional[str] = None, **kwargs: Any) -> Question:
        if id is None:
            id = f"q{len(self.questions) + 1}"
        q = Question(id=id, type=type, **kwargs)
        self.questions.append(q)
        return q

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = _clean(
            {
                "id": self.id,
                "heading": self.heading,
                "source": self.source,
                "source_html": True if self.source_html else None,
                "context": self.context or None,
            }
        )
        d["questions"] = [q.to_dict() for q in self.questions]
        return d


class ReviewBuilder:
    """Build a human-in-the-loop review document and render it to standalone HTML."""

    def __init__(
        self,
        title: str,
        subtitle: Optional[str] = None,
        lang: str = "en",
        cjk: bool = False,
        theme: Optional[dict[str, str]] = None,
        result_filename: Optional[str] = None,
        storage_key: Optional[str] = None,
    ) -> None:
        self.config: dict[str, Any] = _clean(
            {
                "title": title,
                "subtitle": subtitle,
                "lang": lang,
                "cjk": True if cjk else None,
                "theme": theme,
                "result_filename": result_filename,
                "storage_key": storage_key,
            }
        )
        self.items: list[Item] = []

    def add_item(self, source: Optional[str] = None, id: Optional[str] = None, **kwargs: Any) -> Item:
        if id is None:
            id = str(len(self.items) + 1)
        item = Item(id=id, source=source, **kwargs)
        self.items.append(item)
        return item

    def to_dict(self) -> dict[str, Any]:
        return {"config": self.config, "items": [it.to_dict() for it in self.items]}

    def to_json(self, **kwargs: Any) -> str:
        kwargs.setdefault("ensure_ascii", False)
        kwargs.setdefault("indent", 2)
        return json.dumps(self.to_dict(), **kwargs)

    def render(self) -> str:
        return render_html(self.to_dict())

    def save_html(self, path: str) -> str:
        render_html(self.to_dict(), path)
        return path


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────
def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Render a human-eval review HTML file from a data JSON.")
    parser.add_argument("data", help='JSON file: {"config": {...}, "items": [...]}')
    parser.add_argument("-o", "--out", help="Output HTML path (default: alongside data, .html)")
    args = parser.parse_args()

    data = load_data(args.data)
    out = args.out or os.path.splitext(args.data)[0] + ".html"
    render_html(data, out)
    n_items = len(data.get("items") or [])
    n_q = sum(len(it.get("questions") or []) for it in (data.get("items") or []))
    print(f"Wrote {out}  ({n_items} items, {n_q} questions)")


if __name__ == "__main__":
    _main()
