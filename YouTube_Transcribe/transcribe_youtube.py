#!/usr/bin/env python3
"""Transcribe a YouTube video using yt-dlp + faster-whisper.

Mirrors the WhatsApp_Web_Poll pattern: stdlib-first, single-command, no GUI.

Workflow:
  1. Download audio with yt-dlp (mp3, best quality) into ./transcripts/
  2. Run faster-whisper to produce:
       - <id>_<slug>.transcript.txt   (plain text in source language)
       - <id>_<slug>.transcript.srt   (subtitle file with timestamps)
       - <id>_<slug>.translation.txt  (English translation, optional)
       - <id>_<slug>.summary.md       (header w/ metadata + transcript + translation)
  3. Print a short summary block to stdout.

Env vars:
  URL              YouTube URL (required if no positional arg)
  WHISPER_MODEL    tiny | base | small (default) | medium | large-v3
  TRANSLATE        "1" to also emit English translation (default off; auto-on if non-English)
  KEEP_AUDIO       "1" to keep the mp3 (default: deleted after transcription)
  OUTPUT_DIR       override output dir (default: <script_dir>/transcripts)
  YTDLP            override yt-dlp binary path
  WHISPER_PY       override the python interpreter that has faster_whisper installed
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT = SCRIPT_DIR / "transcripts"

YTDLP = os.environ.get("YTDLP") or os.path.expanduser("~/.local/share/pipx/venvs/yt-dlp/bin/yt-dlp")
WHISPER_PY = os.environ.get("WHISPER_PY") or os.path.expanduser("~/venvs/whisper/bin/python")
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")
TRANSLATE_FLAG = os.environ.get("TRANSLATE", "").strip() == "1"
KEEP_AUDIO = os.environ.get("KEEP_AUDIO", "").strip() == "1"
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR") or DEFAULT_OUT)


def log(msg: str) -> None:
    print(f"[yttx] {msg}", flush=True)


def fail(msg: str, code: int = 1) -> None:
    log(f"FAIL: {msg}")
    sys.exit(code)


def slugify(s: str, maxlen: int = 60) -> str:
    s = re.sub(r"[^\w\s.-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s_]+", "_", s).strip("._-")
    return (s[:maxlen] or "video").lower()


def fetch_metadata(url: str) -> dict:
    log(f"fetching metadata for {url}")
    p = subprocess.run(
        [YTDLP, "--skip-download", "--dump-single-json", "--no-warnings", url],
        capture_output=True, text=True, timeout=60,
    )
    if p.returncode != 0:
        fail(f"yt-dlp metadata failed:\n{p.stderr}")
    info = json.loads(p.stdout)
    return {
        "id": info.get("id"),
        "title": info.get("title", ""),
        "uploader": info.get("uploader", ""),
        "duration": info.get("duration"),
        "duration_string": info.get("duration_string", ""),
        "upload_date": info.get("upload_date", ""),
        "view_count": info.get("view_count"),
        "description": info.get("description", ""),
        "webpage_url": info.get("webpage_url", url),
        "language": info.get("language"),
    }


def download_audio(url: str, dest_template: Path) -> Path:
    log(f"downloading audio → {dest_template.with_suffix('.mp3').name}")
    out_pat = str(dest_template.with_suffix(".%(ext)s"))
    p = subprocess.run(
        [YTDLP, "-x", "--audio-format", "mp3", "--audio-quality", "0",
         "--no-warnings", "-o", out_pat, url],
        capture_output=True, text=True, timeout=300,
    )
    if p.returncode != 0:
        fail(f"yt-dlp audio download failed:\n{p.stderr}")
    mp3 = dest_template.with_suffix(".mp3")
    if not mp3.exists():
        fail(f"expected audio file not found: {mp3}")
    log(f"audio saved: {mp3} ({mp3.stat().st_size/1024:.0f} KB)")
    return mp3


WHISPER_RUNNER = r'''
import json, sys, time
from faster_whisper import WhisperModel

audio = sys.argv[1]
model_name = sys.argv[2]
do_translate = sys.argv[3] == "1"

def emit(obj):
    print(json.dumps(obj), flush=True)

emit({"event":"load","model":model_name})
model = WhisperModel(model_name, device="cpu", compute_type="int8")
emit({"event":"loaded"})

def run_pass(task_name, **kw):
    emit({"event": f"{task_name}_start"})
    t0 = time.time()
    segs, info = model.transcribe(audio, beam_size=5, vad_filter=True, **kw)
    emit({
        "event": f"{task_name}_info",
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
    })
    out = []
    audio_dur = info.duration or 0
    for s in segs:
        out.append({"start": s.start, "end": s.end, "text": s.text})
        # Stream live progress so the user sees something every few seconds.
        emit({
            "event": f"{task_name}_segment",
            "i": len(out),
            "start": s.start, "end": s.end,
            "text": s.text.strip(),
            "audio_progress": round(s.end / audio_dur, 3) if audio_dur else None,
            "wall": round(time.time() - t0, 1),
        })
    emit({
        "event": f"{task_name}_done",
        "elapsed": round(time.time()-t0, 1),
        "segments": out,
    })
    return info, out

info, segs = run_pass("transcribe")

if do_translate and info.language != "en":
    run_pass("translate", task="translate")
'''


def run_whisper(mp3: Path, model: str, do_translate: bool) -> dict:
    if not Path(WHISPER_PY).exists():
        fail(f"whisper python not found at {WHISPER_PY}\n"
             f"Bootstrap with:\n"
             f"  python3 -m venv ~/venvs/whisper && "
             f"~/venvs/whisper/bin/pip install faster-whisper")
    log(f"running faster-whisper (model={model}, translate={do_translate})")
    log("(streaming live progress — first segment usually appears within 10-30s)")
    proc = subprocess.Popen(
        [WHISPER_PY, "-u", "-c", WHISPER_RUNNER, str(mp3), model,
         "1" if do_translate else "0"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    result: dict = {"transcribe_segments": [], "translate_segments": []}
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            etype = evt.get("event", "")
            if etype == "loaded":
                log("model loaded; starting transcription")
            elif etype.endswith("_info"):
                phase = "transcribe" if etype.startswith("transcribe") else "translate"
                log(f"{phase}: language={evt['language']} "
                    f"(prob={evt['language_probability']:.2f}), "
                    f"audio duration={evt['duration']:.1f}s")
                result[etype] = evt
            elif etype.endswith("_segment"):
                phase = "transcribe" if etype.startswith("transcribe") else "translate"
                pct = evt.get("audio_progress")
                pct_s = f"{int(pct*100):3d}%" if pct is not None else "  ? "
                log(f"  [{phase} {pct_s} | {evt['wall']:5.1f}s wall] "
                    f"[{evt['start']:6.1f}-{evt['end']:6.1f}] "
                    f"{evt['text'][:100]}")
                result[f"{phase}_segments"].append(evt)
            elif etype.endswith("_done"):
                result[etype] = evt
                phase = "transcribe" if etype.startswith("transcribe") else "translate"
                log(f"{phase} finished in {evt['elapsed']}s "
                    f"({len(evt['segments'])} segments)")
    finally:
        proc.wait(timeout=60)

    if proc.returncode != 0:
        err = proc.stderr.read() if proc.stderr else ""
        fail(f"whisper failed (exit {proc.returncode}):\n{err[-2000:]}")
    if "transcribe_done" not in result:
        err = proc.stderr.read() if proc.stderr else ""
        fail(f"whisper produced no transcript output. stderr:\n{err[-1500:]}")
    return result


def fmt_ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments: list, path: Path) -> None:
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{fmt_ts(seg['start'])} --> {fmt_ts(seg['end'])}")
        lines.append(seg["text"].strip())
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def summarize_text(text: str, n_sentences: int = 7) -> list[str]:
    """Extractive summary using LSA. Returns [] on any failure or short text."""
    if n_sentences <= 0 or not text.strip():
        return []
    try:
        import nltk
        # punkt_tab is the newer tokenizer data (NLTK >= 3.8.2). Try both names.
        for pkg in ("punkt_tab", "punkt"):
            try:
                nltk.data.find(f"tokenizers/{pkg}")
            except LookupError:
                try:
                    nltk.download(pkg, quiet=True)
                except Exception:
                    pass
        from sumy.parsers.plaintext import PlaintextParser
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.summarizers.lsa import LsaSummarizer
        from sumy.nlp.stemmers import Stemmer
        from sumy.utils import get_stop_words

        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        stemmer = Stemmer("english")
        summarizer = LsaSummarizer(stemmer)
        summarizer.stop_words = get_stop_words("english")
        sents = [str(s).strip() for s in summarizer(parser.document, n_sentences)]
        return [s for s in sents if s]
    except Exception as exc:
        log(f"summary skipped (sumy/nltk unavailable: {exc})")
        return []


def write_outputs(meta: dict, whisper: dict, out_base: Path, summary_sents: int = 7) -> dict:
    transcribe = whisper["transcribe_done"]
    info = whisper.get("transcribe_info", {})
    segs = transcribe["segments"]
    lang = info.get("language") or transcribe.get("language", "?")
    lang_prob = info.get("language_probability", 0.0)

    txt_path = out_base.with_suffix(".transcript.txt")
    srt_path = out_base.with_suffix(".transcript.srt")
    sum_path = out_base.with_suffix(".summary.md")

    txt_path.write_text("\n".join(s["text"].strip() for s in segs) + "\n", encoding="utf-8")
    write_srt(segs, srt_path)

    trans_segs = whisper.get("translate_done", {}).get("segments") if lang != "en" else None
    trans_path = None
    if trans_segs:
        trans_path = out_base.with_suffix(".translation.txt")
        trans_path.write_text("\n".join(s["text"].strip() for s in trans_segs) + "\n", encoding="utf-8")

    # ---- Auto-summary (extractive, runs on English text) -------------------
    if lang == "en":
        english_text = " ".join(s["text"].strip() for s in segs)
    elif trans_segs:
        english_text = " ".join(s["text"].strip() for s in trans_segs)
    else:
        english_text = ""

    summary_sentences = summarize_text(english_text, summary_sents) if english_text else []
    summary_short_path = None
    if summary_sentences:
        summary_short_path = out_base.with_suffix(".summary7.txt")
        summary_short_path.write_text("\n".join(f"- {s}" for s in summary_sentences) + "\n",
                                      encoding="utf-8")
        log(f"summary: {len(summary_sentences)}-sentence extractive summary generated")
    elif summary_sents > 0:
        log("summary: skipped (no English text available — pass --translate or use English audio)")

    # Combined markdown summary
    lines = [
        f"# {meta['title']}",
        "",
        f"- URL: {meta['webpage_url']}",
        f"- Channel: {meta['uploader']}",
        f"- Duration: {meta['duration_string']}",
        f"- Upload date: {meta['upload_date']}",
        f"- Views: {meta['view_count']}",
        f"- Detected language: {lang} (prob {lang_prob:.2f})",
        "",
    ]
    if summary_sentences:
        lines += [f"## TL;DR ({len(summary_sentences)}-sentence summary)", ""]
        lines += [f"- {s}" for s in summary_sentences]
        lines += [""]
    lines += [
        "## Description",
        "",
        (meta["description"] or "_(no description)_").strip(),
        "",
        "## Transcript (source language)",
        "",
    ]
    lines.extend(s["text"].strip() for s in segs)
    if trans_segs:
        lines += ["", "## English translation", ""]
        lines.extend(s["text"].strip() for s in trans_segs)
    sum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {"txt": txt_path, "srt": srt_path, "summary": sum_path,
            "translation": trans_path, "summary7": summary_short_path}


def prune_old_outputs(out_dir: Path, max_age_days: int) -> None:
    """Delete files in out_dir whose mtime is older than max_age_days.

    Walks recursively, removes empty subdirs after. Skips when max_age_days <= 0.
    Robust to permission errors — logs and continues.
    """
    if max_age_days <= 0 or not out_dir.exists():
        return
    cutoff = time.time() - max_age_days * 86400
    deleted_files = 0
    deleted_bytes = 0
    errors = 0
    for p in out_dir.rglob("*"):
        if not p.is_file():
            continue
        try:
            if p.stat().st_mtime < cutoff:
                size = p.stat().st_size
                p.unlink()
                deleted_files += 1
                deleted_bytes += size
        except OSError as exc:
            errors += 1
            log(f"prune: could not delete {p.name}: {exc}")
    # Remove now-empty subdirectories (but never the root out_dir itself)
    for p in sorted(out_dir.rglob("*"), key=lambda x: len(x.parts), reverse=True):
        if p.is_dir() and p != out_dir:
            try:
                p.rmdir()
            except OSError:
                pass
    if deleted_files:
        log(f"prune: deleted {deleted_files} file(s) older than {max_age_days} days "
            f"({deleted_bytes/1024:.0f} KB freed)")
    elif errors == 0:
        log(f"prune: no files older than {max_age_days} days in {out_dir.name}/")


def main() -> None:
    ap = argparse.ArgumentParser(description="YouTube → audio → Whisper transcript")
    ap.add_argument("url", nargs="?", help="YouTube URL")
    ap.add_argument("--model", default=WHISPER_MODEL,
                    help="faster-whisper model (tiny/base/small/medium/large-v3)")
    ap.add_argument("--translate", action="store_true",
                    help="also produce English translation for non-English audio")
    ap.add_argument("--no-translate", action="store_true",
                    help="skip translation even if audio is non-English")
    ap.add_argument("--summary-sentences", type=int, default=int(os.environ.get("SUMMARY_SENTENCES", "7")),
                    help="number of sentences in the auto-summary (default 7, 0 = disable)")
    ap.add_argument("--keep-audio", action="store_true", help="keep downloaded mp3")
    ap.add_argument("--out-dir", default=str(OUTPUT_DIR),
                    help="output directory (default: ./transcripts)")
    ap.add_argument("--prune-days", type=int,
                    default=int(os.environ.get("PRUNE_DAYS", "20")),
                    help="delete files in out-dir older than N days at start "
                         "(default 20; 0 = disable)")
    args = ap.parse_args()

    url = (args.url or os.environ.get("URL") or "").strip()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Prune old outputs FIRST so it runs even on URL-less invocations
    # (e.g. you can do `python transcribe_youtube.py --prune-days 20` to clean up only).
    prune_old_outputs(out_dir, args.prune_days)

    if not url:
        if args.prune_days > 0:
            log("no URL — prune complete, exiting.")
            return
        fail("no URL provided (positional arg or URL=... env var)")

    if not Path(YTDLP).exists():
        fail(f"yt-dlp not found at {YTDLP} (set YTDLP=...)")

    meta = fetch_metadata(url)
    if not meta["id"]:
        fail("could not determine video ID")
    log(f"video: {meta['title']!r}  ({meta['duration_string']}, {meta['uploader']})")

    base_name = f"{meta['id']}_{slugify(meta['title'])}"
    out_base = out_dir / base_name

    mp3 = download_audio(url, out_base)

    # Decide whether to translate. Default: ON for non-English unless --no-translate.
    do_translate = TRANSLATE_FLAG or args.translate
    if not args.no_translate and meta.get("language") and meta["language"] != "en":
        do_translate = True
    # We don't truly know the language until Whisper runs, so just always pass True
    # when the user didn't explicitly opt out; the whisper runner itself skips when lang=en.
    if not args.no_translate:
        do_translate = True

    whisper_out = run_whisper(mp3, args.model, do_translate)
    outputs = write_outputs(meta, whisper_out, out_base, summary_sents=args.summary_sentences)

    if not (KEEP_AUDIO or args.keep_audio):
        try:
            mp3.unlink()
            log(f"deleted audio: {mp3.name} (use --keep-audio to retain)")
        except OSError:
            pass

    log("=" * 60)
    log("DONE.")
    log(f"  transcript: {outputs['txt']}")
    log(f"  subtitles:  {outputs['srt']}")
    if outputs["translation"]:
        log(f"  english:    {outputs['translation']}")
    if outputs.get("summary7"):
        log(f"  TL;DR:      {outputs['summary7']}")
    log(f"  summary md: {outputs['summary']}")

    # Print the TL;DR right to stdout so it's visible without opening files.
    if outputs.get("summary7"):
        log("=" * 60)
        log("TL;DR:")
        for line in outputs["summary7"].read_text(encoding="utf-8").splitlines():
            print(f"  {line}", flush=True)


if __name__ == "__main__":
    main()
