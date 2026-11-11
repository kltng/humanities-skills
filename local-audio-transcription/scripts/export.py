#!/usr/bin/env python3
"""Export a job's transcripts: txt, md, srt, vtt, json, jsonl, tei, csv. Standard library only.

    uv run export.py JOB [--formats txt,srt] [--no-timestamps] [--max-gap 1.0]

Files go to JOB/export/<format>/<recording>.<ext>. Segments from all chunks of a recording are joined
in time order. If diarize.py has run, every segment gets a speaker label (the speaker who talks most
during it). Chunks with status error are left out and listed.
"""
from __future__ import annotations

import argparse
import math
import csv
import json
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import SKILL_VERSION, esc, fmt_time, is_cjk, load_job, read_rows, read_speakers, srt_time  # noqa: E402

EXT = {"txt": "txt", "md": "md", "srt": "srt", "vtt": "vtt", "json": "json", "jsonl": "jsonl", "tei": "xml", "csv": "csv"}


def collect(job: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]:
    """The job, {doc: {segments, language, duration, flags}}, and chunk ids that could not be exported."""
    data = load_job(job)
    rows = read_rows(job)
    speakers = read_speakers(job)
    docs: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for src in data["sources"]:
        docs[src["doc"]] = {"doc": src["doc"], "source": src["path"], "duration": src.get("duration", 0),
                            "segments": [], "languages": {}, "flags": {}, "chunks": 0,
                            "speakers": speakers.get(src["doc"], {}).get("turns")}
    for c in data["chunks"]:
        r = rows.get(c["id"])
        d = docs[c["doc"]]
        if r is None or r.get("status") == "error":
            missing.append(c["id"])
            continue
        d["chunks"] += 1
        if r.get("flag"):
            d["flags"].setdefault(r["flag"], []).append(c["id"])
        if r.get("language"):
            d["languages"][r["language"]] = d["languages"].get(r["language"], 0) + 1
        for s in r.get("segments", []):
            seg = {"start": s["start"], "end": s["end"], "text": s["text"]}
            for k in ("words", "language", "logprob", "no_speech", "emotion", "event"):
                if k in s and s[k] not in (None, [], ""):
                    seg[k] = s[k]
            seg["chunk"] = c["id"]
            d["segments"].append(seg)
    for d in docs.values():
        d["segments"].sort(key=lambda s: (s["start"], s["end"]))
        d["language"] = max(d["languages"], key=d["languages"].get) if d["languages"] else None
        if d["speakers"]:
            assign_speakers(d["segments"], d["speakers"])
    return data, docs, missing


def assign_speakers(segments: list[dict[str, Any]], turns: list[dict[str, Any]]) -> None:
    """Give each segment the speaker who talks most during it."""
    for s in segments:
        best, best_overlap = None, 0.0
        for t in turns:
            ov = min(s["end"], t["end"]) - max(s["start"], t["start"])
            if ov > best_overlap:
                best, best_overlap = t["speaker"], ov
        if best is not None:
            s["speaker"] = best


def paragraphs(segments: list[dict[str, Any]], max_gap: float, max_seconds: float = 60.0) -> list[dict[str, Any]]:
    """Segments joined into paragraphs.

    A new paragraph starts at a speaker change, at a pause longer than max_gap, after 1,200 characters,
    or when the paragraph would get longer than max_seconds. So the time marks in txt and md are never
    much more than max_seconds apart, and a place in the recording is easy to find. 0 = no time limit.
    """
    out: list[dict[str, Any]] = []
    for s in segments:
        if out and out[-1].get("speaker") == s.get("speaker") and s["start"] - out[-1]["end"] <= max_gap \
                and len(out[-1]["text"]) < 1200 and not (max_seconds and s["end"] - out[-1]["start"] > max_seconds):
            p = out[-1]
            p["text"] += ("" if is_cjk(p["text"][-1:]) and is_cjk(s["text"][:1]) else " ") + s["text"]
            p["end"] = s["end"]
        else:
            out.append({"start": s["start"], "end": s["end"], "text": s["text"], "speaker": s.get("speaker")})
    return out


def speaker_name(s: Any) -> str:
    return f"Speaker {int(s) + 1}" if isinstance(s, int) else str(s)


# ---------- writers ----------

def write_txt(out: Path, data: dict, docs: dict, opt: Any) -> None:
    for name, d in docs.items():
        lines = []
        for p in paragraphs(d["segments"], opt.max_gap, opt.max_paragraph_seconds):
            head = ""
            if not opt.no_timestamps:
                head += f"[{fmt_time(p['start'])}] "
            if p.get("speaker") is not None:
                head += f"{speaker_name(p['speaker'])}: "
            lines.append(head + p["text"])
        (out / f"{name}.txt").write_text("\n\n".join(lines) + "\n", encoding="utf-8")


def write_md(out: Path, data: dict, docs: dict, opt: Any) -> None:
    for name, d in docs.items():
        lines = [f"# {name}", "", f"Transcribed by {data.get('model')} (local-audio-transcription {SKILL_VERSION}). "
                 f"Length {fmt_time(d['duration'])}. Machine transcription, not proofread.", ""]
        for p in paragraphs(d["segments"], opt.max_gap, opt.max_paragraph_seconds):
            head = ""
            if not opt.no_timestamps:
                head += f"**{fmt_time(p['start'])}** "
            if p.get("speaker") is not None:
                head += f"**{speaker_name(p['speaker'])}:** "
            lines += [head + p["text"], ""]
        (out / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")


_STRONG = "。！？!?…"            # sentence ends
_WEAK = "，、；：,;:"              # clause ends


def split_text(text: str, parts: int) -> list[str]:
    """Cut text into about `parts` pieces of similar length: at sentence ends when possible, else at
    clause ends, else at spaces, else (Chinese with no punctuation) anywhere."""
    text = text.strip()
    if parts <= 1 or len(text) < 2:
        return [text] if text else []
    target = len(text) / parts
    out: list[str] = []
    rest = text
    while len(out) < parts - 1 and len(rest) > target * 1.3:
        lo, hi = int(target * 0.6), min(int(target * 1.3), len(rest) - 1)
        cut = None
        for marks in (_STRONG + ".", _WEAK, " "):
            # the mark closest to the target length; a "." only counts before a space (not 3.5)
            places = [i + 1 for i in range(lo, hi) if rest[i] in marks
                      and not (rest[i] == "." and rest[i + 1:i + 2] not in (" ", ""))]
            if places:
                cut = min(places, key=lambda i: abs(i - target))
                break
        if cut is None:
            cut = max(1, int(target))
        out.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        out.append(rest)
    return [x for x in out if x]


def _cues(d: dict, max_seconds: float = 8.0, max_chars: int = 80) -> list[dict[str, Any]]:
    """Subtitle cues: a segment, or shorter pieces when it is long (over max_seconds or max_chars;
    Chinese, Japanese and Korean characters count double).

    With word times (Whisper --words, Parakeet) the pieces have real times. Without them (Qwen3-ASR,
    SenseVoice: one segment per piece between silences, up to 30 s) the text is cut at punctuation and
    the time is shared out by the number of characters, so the times inside such a segment are estimates.
    """
    def width(t: str) -> int:
        return sum(2 if is_cjk(ch) else 1 for ch in t)

    cues = []
    for s in d["segments"]:
        words = s.get("words")
        long = s["end"] - s["start"] > max_seconds or width(s["text"]) > max_chars
        if long and words:
            cur: list[dict[str, Any]] = []
            for w in words:
                cur.append(w)
                if cur[-1]["end"] - cur[0]["start"] > max_seconds * 0.75 or sum(len(x["text"]) + 1 for x in cur) > max_chars * 0.875:
                    cues.append({"start": cur[0]["start"], "end": cur[-1]["end"],
                                 "text": " ".join(x["text"] for x in cur), "speaker": s.get("speaker")})
                    cur = []
            if cur:
                cues.append({"start": cur[0]["start"], "end": cur[-1]["end"],
                             "text": " ".join(x["text"] for x in cur), "speaker": s.get("speaker")})
        elif long:
            n = max(math.ceil((s["end"] - s["start"]) / max_seconds), math.ceil(width(s["text"]) / max_chars))
            pieces = split_text(s["text"], n)
            total = sum(len(x) for x in pieces) or 1
            t = s["start"]
            for i, piece in enumerate(pieces):
                end = s["end"] if i == len(pieces) - 1 else round(t + (s["end"] - s["start"]) * len(piece) / total, 2)
                cues.append({"start": round(t, 2), "end": end, "text": piece, "speaker": s.get("speaker"),
                             "estimated": True})
                t = end
        else:
            cues.append({"start": s["start"], "end": s["end"], "text": s["text"], "speaker": s.get("speaker")})
    return cues


def write_srt(out: Path, data: dict, docs: dict, opt: Any) -> None:
    for name, d in docs.items():
        lines = []
        for i, c in enumerate(_cues(d, opt.max_cue_seconds), 1):
            text = (f"{speaker_name(c['speaker'])}: " if c.get("speaker") is not None else "") + c["text"]
            lines += [str(i), f"{srt_time(c['start'])} --> {srt_time(c['end'])}", text, ""]
        (out / f"{name}.srt").write_text("\n".join(lines), encoding="utf-8")


def write_vtt(out: Path, data: dict, docs: dict, opt: Any) -> None:
    for name, d in docs.items():
        lines = ["WEBVTT", ""]
        for c in _cues(d, opt.max_cue_seconds):
            text = (f"<v {speaker_name(c['speaker'])}>" if c.get("speaker") is not None else "") + c["text"]
            lines += [f"{srt_time(c['start'], '.')} --> {srt_time(c['end'], '.')}", text, ""]
        (out / f"{name}.vtt").write_text("\n".join(lines), encoding="utf-8")


def write_json(out: Path, data: dict, docs: dict, opt: Any) -> None:
    for name, d in docs.items():
        doc = {"recording": name, "source": d["source"], "duration": d["duration"], "job": data["name"],
               "model": data.get("model"), "skill_version": SKILL_VERSION, "language": d["language"],
               "speakers": d["speakers"], "flags": d["flags"], "segments": d["segments"]}
        (out / f"{name}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def write_jsonl(out: Path, data: dict, docs: dict, opt: Any) -> None:
    with open(out / f"{data['name']}.jsonl", "w", encoding="utf-8") as fh:
        for name, d in docs.items():
            for s in d["segments"]:
                fh.write(json.dumps({"recording": name, **s}, ensure_ascii=False) + "\n")


def write_csv(out: Path, data: dict, docs: dict, opt: Any) -> None:
    with open(out / f"{data['name']}.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["recording", "start", "end", "speaker", "language", "text"])
        for name, d in docs.items():
            for s in d["segments"]:
                w.writerow([name, s["start"], s["end"],
                            speaker_name(s["speaker"]) if s.get("speaker") is not None else "",
                            s.get("language") or d["language"] or "", s["text"]])


def write_tei(out: Path, data: dict, docs: dict, opt: Any) -> None:
    """TEI P5 for transcribed speech: <u> per paragraph with who/start/end on a <timeline>."""
    for name, d in docs.items():
        paras = paragraphs(d["segments"], opt.max_gap, opt.max_paragraph_seconds)
        spk = sorted({p["speaker"] for p in paras if p.get("speaker") is not None})
        x = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<TEI xmlns="http://www.tei-c.org/ns/1.0">', "<teiHeader><fileDesc>",
             f"<titleStmt><title>{esc(name)}: machine transcription</title></titleStmt>",
             f"<publicationStmt><p>Transcribed locally with {esc(str(data.get('model')))} "
             f"(local-audio-transcription {SKILL_VERSION}). Not proofread.</p></publicationStmt>",
             f"<sourceDesc><recordingStmt><recording type=\"audio\" dur-iso=\"PT{int(d['duration'])}S\">"
             f"<p>{esc(Path(d['source']).name)}</p></recording></recordingStmt></sourceDesc>",
             "</fileDesc>",
             "<profileDesc>" + (f'<langUsage><language ident="{esc(d["language"])}"/></langUsage>' if d["language"] else "")
             + "<particDesc><listPerson>" + "".join(f'<person xml:id="spk{s + 1}"><persName>{speaker_name(s)}</persName></person>'
                                                   for s in spk) + "</listPerson></particDesc></profileDesc>",
             "</teiHeader>", "<text><body>", '<timeline unit="s" origin="#t0"><when xml:id="t0" absolute="0"/>']
        for i, p in enumerate(paras, 1):
            x.append(f'<when xml:id="s{i}" interval="{p["start"]}" since="#t0"/>'
                     f'<when xml:id="e{i}" interval="{p["end"]}" since="#t0"/>')
        x.append("</timeline>")
        for i, p in enumerate(paras, 1):
            who = f' who="#spk{p["speaker"] + 1}"' if p.get("speaker") is not None else ""
            x.append(f'<u{who} start="#s{i}" end="#e{i}">{esc(p["text"])}</u>')
        x += ["</body></text>", "</TEI>"]
        (out / f"{name}.xml").write_text("\n".join(x) + "\n", encoding="utf-8")


WRITERS: dict[str, Callable[[Path, dict, dict, Any], None]] = {
    "txt": write_txt, "md": write_md, "srt": write_srt, "vtt": write_vtt, "json": write_json,
    "jsonl": write_jsonl, "csv": write_csv, "tei": write_tei,
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job", type=Path)
    ap.add_argument("--formats", help="comma list; default: the formats stored in the job")
    ap.add_argument("--no-timestamps", action="store_true", help="txt/md without the time at each paragraph")
    ap.add_argument("--max-gap", type=float, default=1.0, help="a pause longer than this starts a new paragraph")
    ap.add_argument("--max-paragraph-seconds", type=float, default=60.0,
                    help="txt/md/tei: start a new paragraph (with its time mark) at least this often; 0 = no limit")
    ap.add_argument("--max-cue-seconds", type=float, default=8.0,
                    help="srt/vtt: cut longer segments into cues of about this length")
    a = ap.parse_args()

    data, docs, missing = collect(a.job)
    formats = [f.strip() for f in (a.formats or ",".join(data.get("formats") or ["txt"])).split(",") if f.strip()]
    bad = [f for f in formats if f not in WRITERS]
    if bad:
        raise SystemExit(f"unknown format(s): {', '.join(bad)}; choose from {', '.join(WRITERS)}")
    for f in formats:
        out = a.job / "export" / f
        out.mkdir(parents=True, exist_ok=True)
        WRITERS[f](out, data, docs, a)
        print(f"{f}: {out}")
    n = sum(len(d["segments"]) for d in docs.values())
    print(f"{len(docs)} recording(s), {n} segments")
    if missing:
        print(f"Chunks not exported (not done or error): {', '.join(missing[:30])}{' …' if len(missing) > 30 else ''}")
    flagged = {k: v for d in docs.values() for k, v in d["flags"].items()}
    if flagged:
        print("Flagged chunks (look at these): " + "; ".join(f"{k} {len(v)}" for k, v in flagged.items()))


if __name__ == "__main__":
    main()
