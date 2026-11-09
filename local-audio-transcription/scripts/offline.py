#!/usr/bin/env python3
"""Prove that a job can run with no network, and write the script the user runs after disconnecting.

    uv run offline.py check SAMPLE_JOB                 # run the whole pipeline on the sample clip, network blocked
    uv run offline.py script SAMPLE_JOB --job REAL_JOB # write REAL_JOB/transcribe-offline.sh (and .ps1)

`check` copies the sample job's settings into SAMPLE_JOB/offline-check/, then runs prepare, the model,
diarization (if planned), export and report there, each as a separate process with LOCAL_ASR_OFFLINE=1
(every network connection is refused) and `uv run --offline` (uv uses only its cache). It first proves
the guard itself works by trying to reach huggingface.co through it. All steps must PASS before the user
is told to disconnect.

`script` writes a shell script (macOS/Linux) and a PowerShell script (Windows) that run the same steps
on the real recordings, refuse to start while the network is still up, and never need this assistant.
Standard library only.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_job, read_rows, read_speakers  # noqa: E402

S = Path(__file__).resolve().parent
RUNNER = {"whisper": "run_whisper.py", "qwen3-asr": "run_qwen3asr.py", "sensevoice": "run_sensevoice.py",
          "parakeet": "run_parakeet.py"}


def step(name: str, cmd: list[str], cwd: Path | None = None, expect_fail: bool = False) -> bool:
    env = {**os.environ, "LOCAL_ASR_OFFLINE": "1", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
           "HF_HUB_DISABLE_TELEMETRY": "1", "UV_OFFLINE": "1"}
    t = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=cwd)
    ok = (p.returncode != 0) if expect_fail else (p.returncode == 0)
    print(f"{'PASS' if ok else 'FAIL'}  {name} ({round(time.time() - t, 1)} s)", flush=True)
    if not ok:
        tail = "\n".join((p.stderr or p.stdout).strip().splitlines()[-12:])
        print("      " + tail.replace("\n", "\n      "), flush=True)
    return ok


def prepare_args(data: dict[str, Any]) -> list[str]:
    args = ["--model", data["model"], "--formats", ",".join(data.get("formats") or ["txt"]), "--offline"]
    if data.get("language"):
        args += ["--language", data["language"]]
    if data.get("diarize"):
        args.append("--diarize")
    return args


def check(a: argparse.Namespace) -> None:
    data = load_job(a.sample_job)
    if not data.get("sample"):
        print("note: this job is not marked as a sample job (prepare.py --sample). Going on anyway.")
    sources = [s["path"] for s in data["sources"] if not s.get("error")]
    if not sources:
        raise SystemExit("the sample job has no readable recording")
    missing = [s for s in sources if not Path(s).exists()]
    if missing:
        raise SystemExit("sample recording(s) not found: " + ", ".join(missing))
    uv = shutil.which("uv") or "uv"
    job = a.sample_job / "offline-check"
    if job.exists():
        shutil.rmtree(job)
    results = []
    # 1. the guard itself: a connection through it must fail
    guard = ("import sys; sys.path.insert(0, %r); import _common; _common.network_guard(); import urllib.request; "
             "urllib.request.urlopen('https://huggingface.co', timeout=10)" % str(S))
    results.append(step("network guard blocks a connection", [sys.executable, "-c", guard], expect_fail=True))
    results.append(step("ffmpeg present", [shutil.which("ffmpeg") or "ffmpeg", "-version"]))
    results.append(step("prepare (convert and chunk)", [uv, "run", "--offline", str(S / "prepare.py"), *sources,
                                                        "--job", str(job), *prepare_args(data), "--sample"]))
    if results[-1]:
        run = [uv, "run", "--offline", str(S / RUNNER[data["model"]]), str(job)]
        results.append(step(f"transcribe with {data['model']}", run))
        if results[-1]:
            rows = read_rows(job)
            n_ok = sum(1 for r in rows.values() if r.get("status") == "ok")
            n = len(load_job(job)["chunks"])
            good = n_ok == n and n > 0
            print(f"{'PASS' if good else 'FAIL'}  every chunk transcribed ({n_ok}/{n})")
            results.append(good)
        if data.get("diarize"):
            results.append(step("speaker diarization", [uv, "run", "--offline", str(S / "diarize.py"), str(job)]))
            results.append(bool(read_speakers(job)))
        results.append(step("export", [uv, "run", "--offline", str(S / "export.py"), str(job)]))
        results.append(step("report", [uv, "run", "--offline", str(S / "report.py"), str(job)]))
    print()
    if all(results):
        print("ALL PASS: the pipeline ran with every network connection blocked. "
              f"Next: `offline.py script {a.sample_job} --job REAL_JOB`, then disconnect and run the script.")
    else:
        print("NOT READY: fix the failed step(s) with the network on (usually: run the model's --setup again), "
              "then run this check again. Do not disconnect yet.")
        sys.exit(1)


def script(a: argparse.Namespace) -> None:
    data = load_job(a.sample_job)
    real = a.job.resolve()
    real.mkdir(parents=True, exist_ok=True)
    runner = RUNNER[data["model"]]
    pargs = prepare_args(data)
    lang = ["--language", data["language"]] if data.get("language") else []
    spk = ["--speakers", str(a.speakers)] if a.speakers else []
    uv = "uv run --offline"

    sh = f"""#!/usr/bin/env bash
# Made by local-audio-transcription (offline job "{real.name}"). Run this with the network OFF:
#   bash "{real / 'transcribe-offline.sh'}" /path/to/recording1.mp3 /path/to/folder ...
# It converts the recordings, transcribes them with {data['model']}, {'labels speakers, ' if data.get('diarize') else ''}exports
# {', '.join(data.get('formats') or ['txt'])} and writes a report, all on this computer. Run it again to continue a stopped job.
set -euo pipefail
export LOCAL_ASR_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 UV_OFFLINE=1
S="{S}"
JOB="{real}"

if [ "${{LOCAL_ASR_SKIP_NETCHECK:-}}" != "1" ]; then
  while curl -s -m 4 -o /dev/null https://huggingface.co 2>/dev/null; do
    echo "The network is still ON. Turn Wi-Fi off and unplug the Ethernet cable, then press Enter to check again."
    read -r _
  done
  echo "Network check: offline. Starting."
fi

if [ "$#" -gt 0 ]; then
  {uv} "$S/prepare.py" "$@" --job "$JOB" {' '.join(pargs)}
fi
{uv} "$S/{runner}" "$JOB" {' '.join(lang)}
{f'{uv} "$S/diarize.py" "$JOB" {" ".join(spk)}' if data.get('diarize') else ''}
{uv} "$S/export.py" "$JOB"
{uv} "$S/report.py" "$JOB"
echo
echo "DONE. Transcripts: $JOB/export   Report (no transcript text): $JOB/report.md"
echo "You can reconnect now."
"""
    (real / "transcribe-offline.sh").write_text(sh, encoding="utf-8")
    os.chmod(real / "transcribe-offline.sh", 0o755)

    ps = f"""# Made by local-audio-transcription (offline job "{real.name}"). Run this with the network OFF:
#   powershell -ExecutionPolicy Bypass -File "{real / 'transcribe-offline.ps1'}" C:\\path\\recording1.mp3 C:\\path\\folder
$ErrorActionPreference = "Stop"
$env:LOCAL_ASR_OFFLINE = "1"; $env:HF_HUB_OFFLINE = "1"; $env:TRANSFORMERS_OFFLINE = "1"; $env:HF_HUB_DISABLE_TELEMETRY = "1"; $env:UV_OFFLINE = "1"
$S = "{S}"
$JOB = "{real}"

if ($env:LOCAL_ASR_SKIP_NETCHECK -ne "1") {{
  while ($true) {{
    try {{ Invoke-WebRequest -Uri "https://huggingface.co" -TimeoutSec 4 -UseBasicParsing | Out-Null; $online = $true }} catch {{ $online = $false }}
    if (-not $online) {{ break }}
    Read-Host "The network is still ON. Turn Wi-Fi off and unplug the Ethernet cable, then press Enter to check again"
  }}
  Write-Host "Network check: offline. Starting."
}}

if ($args.Count -gt 0) {{
  & uv run --offline "$S\\prepare.py" @args --job "$JOB" {' '.join(pargs)}
  if ($LASTEXITCODE -ne 0) {{ exit $LASTEXITCODE }}
}}
& uv run --offline "$S\\{runner}" "$JOB" {' '.join(lang)}
if ($LASTEXITCODE -ne 0) {{ exit $LASTEXITCODE }}
{f'& uv run --offline "$S\\diarize.py" "$JOB" {" ".join(spk)}' if data.get('diarize') else ''}
& uv run --offline "$S\\export.py" "$JOB"
& uv run --offline "$S\\report.py" "$JOB"
Write-Host ""
Write-Host "DONE. Transcripts: $JOB\\export   Report (no transcript text): $JOB\\report.md"
Write-Host "You can reconnect now."
"""
    (real / "transcribe-offline.ps1").write_text(ps, encoding="utf-8")
    print(f"Wrote {real / 'transcribe-offline.sh'}")
    print(f"Wrote {real / 'transcribe-offline.ps1'}")
    print("The user runs one of them after disconnecting, with the recordings (files or folders) as arguments.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("sample_job", type=Path)
    s = sub.add_parser("script"); s.add_argument("sample_job", type=Path)
    s.add_argument("--job", type=Path, required=True, help="the real job folder the script will make")
    s.add_argument("--speakers", type=int, help="number of speakers for diarize.py, if known")
    a = ap.parse_args()
    check(a) if a.cmd == "check" else script(a)


if __name__ == "__main__":
    main()
