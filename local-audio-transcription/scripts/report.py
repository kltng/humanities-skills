#!/usr/bin/env python3
"""Write the run report for the user and a field report that is safe to post on GitHub.

    uv run report.py JOB [--describe "oral history interview, Cantonese, two speakers, phone recording"]
                     [--share-titles]

JOB/report.md        for the user: what was transcribed, how fast, which chunks need a look, where the files are.
JOB/field-report.md  for a GitHub issue: machine, model, speed, problems and notes. No transcript text,
                     no file paths, no recording names (unless --share-titles).
Standard library only. Neither file contains any transcript text, so both are safe to read in an
offline job.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import SKILL_VERSION, fmt_time, job_progress, load_job, read_rows, read_speakers  # noqa: E402

FLAGS = ("repeat", "no_speech", "empty", "uncertain", "language", "slow")
WHY = {"repeat": "the same text repeats many times; the model looped",
       "no_speech": "text on a chunk that sounds silent; probably invented",
       "empty": "no text although the chunk has sound",
       "uncertain": "segments with very low confidence; often invented text on music, noise or an unexpected language",
       "language": "detected language differs from the one expected",
       "slow": "took more than three times the length of the audio"}


def stats(data: dict[str, Any], rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    chunks = data["chunks"]
    ok = [c for c in chunks if rows.get(c["id"], {}).get("status") == "ok"]
    errors = [c["id"] for c in chunks if rows.get(c["id"], {}).get("status") == "error"]
    secs = [rows[c["id"]]["seconds"] for c in ok if rows[c["id"]].get("seconds")]
    audio_done = sum(c["duration"] for c in ok)
    flagged = {f: [c["id"] for c in ok if rows[c["id"]].get("flag") == f] for f in FLAGS}
    langs: dict[str, int] = {}
    for c in ok:
        lang = rows[c["id"]].get("language")
        if lang:
            langs[lang] = langs.get(lang, 0) + 1
    chars = sum(len(rows[c["id"]].get("text", "")) for c in ok)
    segs = sum(len(rows[c["id"]].get("segments", [])) for c in ok)
    return {"chunks": len(chunks), "done": len(ok), "errors": errors, "docs": len(data["sources"]),
            "audio_total": sum(s.get("duration", 0) for s in data["sources"]), "audio_done": audio_done,
            "compute": sum(secs), "speed": round(audio_done / sum(secs), 1) if secs else None,
            "median_chunk_s": round(statistics.median(secs), 1) if secs else None,
            "chars": chars, "segments": segs, "flagged": flagged, "languages": langs}


def ids(xs: list[str], n: int = 20) -> str:
    return ", ".join(xs[:n]) + (f" … (+{len(xs) - n})" if len(xs) > n else "") if xs else "none"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job", type=Path)
    ap.add_argument("--describe", help="a short, non-private description of the recordings for the field report")
    ap.add_argument("--share-titles", action="store_true", help="name the recordings in the field report")
    a = ap.parse_args()

    data = load_job(a.job)
    rows = read_rows(a.job)
    speakers = read_speakers(a.job)
    s = stats(data, rows)
    prog = job_progress(a.job)
    runs = data.get("runs") or []
    last = runs[-1] if runs else {}
    m = last.get("machine", {})
    gpu = ", ".join(f"{g['name']} {g['vram_gb']} GB" for g in m.get("gpus", [])) or "none / Apple Silicon"
    brief = data.get("brief") or {}
    export = a.job / "export"
    exported = sorted(p.name for p in export.iterdir()) if export.exists() else []
    where = {c["id"]: f"{c['doc']} {fmt_time(c['start'])}" for c in data["chunks"]}
    offline = bool(data.get("offline"))

    # ---------- report.md (for the user) ----------
    u = [f"# Transcription report: {data['name']}", "",
         f"Model **{data.get('model')}** ({last.get('backend', '?')}), skill local-audio-transcription {SKILL_VERSION}"
         + (", **strict offline job**" if offline else "") + ". "
         "Machine transcription, not proofread: listen before quoting.", "",
         "## What was transcribed", "",
         f"- {s['done']} of {s['chunks']} chunks: {fmt_time(s['audio_done'])} of {fmt_time(s['audio_total'])} "
         f"of audio in {s['docs']} recording(s); {s['segments']:,} segments, {s['chars']:,} characters.",
         f"- Speed: {s['speed']}x real time ({fmt_time(s['compute'])} of computing in {len(runs)} run(s))."]
    if s["languages"]:
        u.append("- Languages detected: " + ", ".join(f"{k} ({v} chunks)" for k, v in
                                                    sorted(s["languages"].items(), key=lambda x: -x[1])))
    if speakers:
        u.append("- Speakers: " + "; ".join(f"{d}: {r.get('speakers')} speaker(s), {len(r.get('turns', []))} turns"
                                             for d, r in speakers.items()))
    if prog["eta_minutes"] and s["done"] < s["chunks"]:
        u.append(f"- Not finished: about {prog['eta_minutes']} minutes left. Run the same command again to continue.")
    u += ["", "## Chunks to listen to", ""]
    for f in FLAGS:
        if s["flagged"][f]:
            u.append(f"- **{f}** ({len(s['flagged'][f])}): {WHY[f]}. "
                     + ids([f"{x} ({where[x]})" for x in s["flagged"][f]], 12))
    if s["errors"]:
        u.append(f"- **error** ({len(s['errors'])}): could not be transcribed. "
                 + ids([f"{x} ({where[x]})" for x in s["errors"]], 12))
    if u[-1] == "":
        u.append("- none flagged. Still listen to a few minutes against the text.")
    u += ["", "## Files", "", f"- Job folder: `{a.job.resolve()}`",
          f"- Exports: {', '.join(f'`export/{x}/`' for x in exported) or 'none yet (run export.py)'}",
          "- Raw transcripts: `rows.jsonl` (one line per chunk)" + (", `speakers.jsonl`" if speakers else ""), ""]
    if offline:
        u += ["## Offline", "",
              "This job ran with the network guard on: every connection attempt from the transcription scripts "
              "was blocked. The transcripts stayed on this computer. Do not paste them into any cloud tool "
              "(including an AI assistant) unless that is allowed for this material.", ""]
    if data.get("notes"):
        u += ["## Notes", ""] + [f"- {n['text']}" for n in data["notes"]] + [""]
    u += ["## Licences", "",
          "Whisper (OpenAI) is MIT; Qwen3-ASR (Alibaba) and Parakeet (NVIDIA) are Apache 2.0 / CC-BY-4.0; "
          "SenseVoice (Alibaba FunAudioLLM) has its own model licence. When you publish, say which model made "
          "the first draft.", ""]
    (a.job / "report.md").write_text("\n".join(u), encoding="utf-8")

    # ---------- field-report.md (for GitHub) ----------
    material = a.describe or ", ".join(f"{k}: {v}" for k, v in brief.items() if k in
                                       ("material", "languages", "speakers", "recording", "quality")) or "(not described)"
    if a.share_titles:
        material += f" | recordings: {', '.join(src['doc'] for src in data['sources'])}"
    flagged_line = "; ".join(f"{f} {len(v)}" for f, v in s["flagged"].items() if v) or "none"
    f = [f"**Skill:** local-audio-transcription {SKILL_VERSION} | **Date:** {data.get('created')} – "
         f"{(last.get('ended') or '')[:10]} | **Offline job:** {'yes' if offline else 'no'}",
         f"**Machine:** {m.get('chip')} | {m.get('cpu_cores')} cores | {m.get('ram_gb')} GB | GPU: {gpu} | "
         f"{m.get('os')} {m.get('arch')} | Python {m.get('python')}",
         f"**Model / backend:** {data.get('model')} / {last.get('backend')} | "
         + ", ".join(f"{k} {v}" for k, v in (last.get("versions") or {}).items()),
         f"**Material:** {material}",
         f"**Audio:** {fmt_time(s['audio_done'])} of {fmt_time(s['audio_total'])} in {s['docs']} recording(s), "
         f"{s['done']}/{s['chunks']} chunks | {s['speed']}x real time | median {s['median_chunk_s']} s per chunk | "
         f"{len(runs)} run(s)",
         f"**Languages detected:** {', '.join(f'{k} {v}' for k, v in s['languages'].items()) or 'n/a'}",
         f"**Flagged chunks:** {flagged_line} | errors {len(s['errors'])}",
         f"**Speaker labels:** {'yes' if speakers else 'no'} | **Formats exported:** {', '.join(exported) or 'none'}",
         "", "**What happened / problems:**"]
    f += [f"- {n['text']}" for n in data.get("notes", [])] or ["- (no notes logged)"]
    stopped = [r for r in runs if r.get("outcome") != "finished"]
    if stopped:
        f.append(f"- {len(stopped)} run(s) did not finish (stopped, killed or crashed).")
    f += ["", "**Quality (your judgement after listening):** <fill in>", "",
          "**What the skill says / lacks:** <fill in>", "", "**Proposed change:** <fill in>"]
    (a.job / "field-report.md").write_text("\n".join(f) + "\n", encoding="utf-8")

    print(f"Wrote {a.job / 'report.md'}")
    print(f"Wrote {a.job / 'field-report.md'} (read it and fill in the last three lines before posting)")


if __name__ == "__main__":
    main()
