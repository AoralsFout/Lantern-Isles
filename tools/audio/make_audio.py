#!/usr/bin/env python3
"""Build the complete Lantern Isles audio set and its manifest.

Usage (from the project root, with the bundled Python):
    python tools/audio/make_audio.py                 # build everything
    python tools/audio/make_audio.py --only music
    python tools/audio/make_audio.py --only title,spring
    python tools/audio/make_audio.py --reuse         # reuse _build/*.wav
    python tools/audio/make_audio.py --keep-wav      # keep float WAV masters

Music/ambience are rendered as float WAV, encoded to OGG/Vorbis q5, decoded
again and objectively checked (duration, peak, RMS, DC, NaN, channels, loop
seam slope/loudness).  SFX are written directly as 44.1 kHz 16-bit mono WAV.
A waveform + spectrogram PNG is produced for every music cue and ambience bed
in assets/audio/previews/.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

import analysis  # noqa: E402
import ambience  # noqa: E402
import music  # noqa: E402
import sfx  # noqa: E402
import synth  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
AUDIO = ROOT / "assets" / "audio"
MUSIC_DIR = AUDIO / "music"
AMB_DIR = AUDIO / "ambience"
SFX_DIR = AUDIO / "sfx"
PREVIEWS = AUDIO / "previews"
BUILD = Path(__file__).parent / "_build"
MANIFEST = ROOT / "data" / "audio_manifest.json"

MUSIC_META = {
    "title": dict(
        bpm=72, key="D major pentatonic", target_rms=-17.6,
        desc="Main theme - warm, glimmering, a little unresolved",
        subtitle="Lantern Isles main theme - 72 BPM - D major pentatonic - seamless loop",
    ),
    "spring": dict(
        bpm=64, key="D gong pentatonic", target_rms=-18.0,
        desc="Mossgarden, Spring Sleep - guzheng, harp, soft strings, bird gaps",
        subtitle="Mossgarden / Spring Sleep - 64 BPM - D gong pentatonic - seamless loop",
    ),
    "desert": dict(
        bpm=72, key="D Phrygian dominant", target_rms=-17.6,
        desc="Amberreach, Long Summer - oud, hand drums, dust drone, distant voices",
        subtitle="Amberreach / Long Summer - 72 BPM - D Phrygian dominant - seamless loop",
    ),
    "winter": dict(
        bpm=56, key="A minor add9", target_rms=-20.0,
        desc="Frostvale, Silent Winter - music box, low strings, distant bells, space",
        subtitle="Frostvale / Silent Winter - 56 BPM - A minor add9 - seamless loop",
    ),
    "night": dict(
        bpm=60, key="D suspended", target_rms=-19.0,
        desc="Starfall, Homecoming Night - glass bells, choir, deep bass, star dust",
        subtitle="Starfall / Homecoming Night - 60 BPM - D suspended - seamless loop",
    ),
    "ending": dict(
        bpm=76, key="D major", target_rms=-16.8,
        desc="Ending - the theme in full light, piano, strings and bells",
        subtitle="Ending - 76 BPM - D major - seamless loop",
    ),
}

AMB_META = {
    "spring_amb": dict(
        target_rms=-23.5,
        desc="Breeze, distant birds, stream, bamboo rustle",
        subtitle="Mossgarden ambience - breeze, stream, distant birds, bamboo - 65 s loop",
    ),
    "desert_amb": dict(
        target_rms=-23.5,
        desc="Dry hot wind, sand grains, distant chimes, a vulture",
        subtitle="Amberreach ambience - dry wind, sand, wind chimes, vulture - 65 s loop",
    ),
    "winter_amb": dict(
        target_rms=-23.5,
        desc="Snowfield wind, ice cracks, distant bells, hot spring bubbles",
        subtitle="Frostvale ambience - snow wind, ice, bells, hot spring - 65 s loop",
    ),
    "night_amb": dict(
        target_rms=-23.5,
        desc="High air, starry chimes, a very low drone, night insects",
        subtitle="Starfall ambience - high air, star chimes, low drone, insects - 65 s loop",
    ),
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def music_checks(x: np.ndarray, sr: int) -> dict:
    m = analysis.basic_metrics(x, sr)
    m.update(analysis.loop_metrics(x, sr, 2.0))
    m["peak_ok"] = bool(m["peak_dbfs"] <= -1.0)
    m["rms_ok"] = bool(-20.2 <= m["rms_dbfs"] <= -15.8)
    return m


def amb_checks(x: np.ndarray, sr: int) -> dict:
    m = analysis.basic_metrics(x, sr)
    m.update(analysis.loop_metrics(x, sr, 2.0))
    m["peak_ok"] = bool(m["peak_dbfs"] <= -1.0)
    return m


def sfx_checks(x: np.ndarray, sr: int) -> dict:
    m = analysis.basic_metrics(x, sr)
    m["peak_ok"] = bool(m["peak_dbfs"] <= -3.0)
    return m


def build_music(ids, reuse: bool, keep_wav: bool, previews: bool) -> dict:
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for sid in ids:
        meta = MUSIC_META[sid]
        t0 = time.time()
        wav = BUILD / f"{sid}.wav"
        if (not reuse) or (not wav.exists()):
            piece = music.build(sid)
            loop = piece.finish(target_rms=meta["target_rms"])
            synth.write_wav(wav, loop, fmt="f32")
            notes = piece.count
        else:
            notes = -1
        ogg = MUSIC_DIR / f"{sid}.ogg"
        synth.encode_ogg(wav, ogg, quality=5)
        x, sr, _ = analysis.load_audio(ogg)
        checks = music_checks(x, sr)
        preview = None
        if previews:
            preview = analysis.make_preview(
                ogg, x, sr, f"{sid}.ogg", meta["subtitle"], checks,
            )
        entry = {
            "id": sid,
            "file": rel(ogg),
            "bpm": meta["bpm"],
            "key": meta["key"],
            "duration": round(checks["duration"], 3),
            "peak_dbfs": checks["peak_dbfs"],
            "rms_dbfs": checks["rms_dbfs"],
            "loop": True,
            "description": meta["desc"],
            "checks": checks,
            "preview": rel(preview) if preview else None,
        }
        if notes > 0:
            entry["notes"] = notes
        out[sid] = entry
        print(
            f"music  {sid:7s} {checks['duration']:7.2f}s  peak {checks['peak_dbfs']:6.2f}  "
            f"rms {checks['rms_dbfs']:6.2f}  seam {checks['seam_slope_jump']:.4f}/"
            f"{checks['seam_rms_delta_db']:+.2f}dB  {time.time() - t0:.1f}s",
            flush=True,
        )
        if not keep_wav and wav.exists() and wav.parent == BUILD:
            wav.unlink()
    return out


def build_ambience(ids, reuse: bool, keep_wav: bool, previews: bool) -> dict:
    AMB_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for sid in ids:
        meta = AMB_META[sid]
        t0 = time.time()
        wav = BUILD / f"{sid}.wav"
        if (not reuse) or (not wav.exists()):
            amb = ambience.build(sid)
            loop = amb.finalize(target_rms=meta["target_rms"])
            synth.write_wav(wav, loop, fmt="f32")
        ogg = AMB_DIR / f"{sid}.ogg"
        synth.encode_ogg(wav, ogg, quality=5)
        x, sr, _ = analysis.load_audio(ogg)
        checks = amb_checks(x, sr)
        preview = None
        if previews:
            preview = analysis.make_preview(
                ogg, x, sr, f"{sid}.ogg", meta["subtitle"], checks,
            )
        entry = {
            "id": sid,
            "file": rel(ogg),
            "duration": round(checks["duration"], 3),
            "peak_dbfs": checks["peak_dbfs"],
            "rms_dbfs": checks["rms_dbfs"],
            "loop": True,
            "description": meta["desc"],
            "checks": checks,
            "preview": rel(preview) if preview else None,
        }
        out[sid] = entry
        print(
            f"amb    {sid:10s} {checks['duration']:7.2f}s  peak {checks['peak_dbfs']:6.2f}  "
            f"rms {checks['rms_dbfs']:6.2f}  seam {checks['seam_slope_jump']:.4f}/"
            f"{checks['seam_rms_delta_db']:+.2f}dB  {time.time() - t0:.1f}s",
            flush=True,
        )
        if not keep_wav and wav.exists() and wav.parent == BUILD:
            wav.unlink()
    return out


def build_sfx(ids=None) -> dict:
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for sid, (category, fn) in sfx.SFX.items():
        if ids and sid not in ids:
            continue
        x = fn()
        path = SFX_DIR / f"{sid}.wav"
        synth.write_wav(path, x, fmt="s16")
        y, sr = synth.read_wav(path)
        checks = sfx_checks(y, sr)
        entry = {
            "id": sid,
            "file": rel(path),
            "duration": round(checks["duration"], 3),
            "category": category,
            "peak_dbfs": checks["peak_dbfs"],
            "rms_dbfs": checks["rms_dbfs"],
            "checks": checks,
        }
        out[sid] = entry
        print(
            f"sfx    {sid:16s} {checks['duration']:5.3f}s  peak {checks['peak_dbfs']:6.2f}  "
            f"rms {checks['rms_dbfs']:6.2f}  ch={checks['channels']}",
            flush=True,
        )
    return out


def merge_manifest(new: dict) -> dict:
    old = {}
    if MANIFEST.exists():
        try:
            old = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    manifest = {
        "music": list(old.get("music", [])) if isinstance(old, dict) else [],
        "ambience": list(old.get("ambience", [])) if isinstance(old, dict) else [],
        "sfx": list(old.get("sfx", [])) if isinstance(old, dict) else [],
    }
    for key, items in new.items():
        by_id = {e["id"]: e for e in manifest[key] if isinstance(e, dict) and "id" in e}
        for sid, entry in items.items():
            by_id[sid] = entry
        order = []
        if key == "music":
            order = [x for x in music.BUILDERS]
        elif key == "ambience":
            order = [x for x in ambience.BUILDERS]
        else:
            order = [x for x in sfx.SFX]
        manifest[key] = [by_id[x] for x in order if x in by_id]
    return manifest


def report_sizes() -> None:
    files = [p for p in AUDIO.rglob("*") if p.is_file()]
    audio = [p for p in files if p.suffix.lower() in (".ogg", ".wav")]
    total = sum(p.stat().st_size for p in files)
    audio_bytes = sum(p.stat().st_size for p in audio)
    print(
        f"assets/audio: {len(files)} files, audio {audio_bytes / 1e6:.2f} MB, "
        f"all files {total / 1e6:.2f} MB"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="music|ambience|sfx or comma separated ids")
    ap.add_argument("--reuse", action="store_true", help="reuse intermediate float WAVs in _build")
    ap.add_argument("--keep-wav", action="store_true", help="keep intermediate float WAVs")
    ap.add_argument("--no-previews", action="store_true")
    args = ap.parse_args()

    BUILD.mkdir(parents=True, exist_ok=True)
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    only = [s.strip() for s in args.only.split(",") if s.strip()]
    previews = not args.no_previews

    do_music = do_amb = do_sfx = False
    music_ids = list(music.BUILDERS)
    amb_ids = list(ambience.BUILDERS)
    sfx_ids = None
    if not only:
        do_music = do_amb = do_sfx = True
    elif set(only) & {"music", "ambience", "sfx"}:
        do_music = "music" in only
        do_amb = "ambience" in only
        do_sfx = "sfx" in only
    else:
        music_ids = [x for x in only if x in music.BUILDERS]
        amb_ids = [x for x in only if x in ambience.BUILDERS]
        sfx_ids = [x for x in only if x in sfx.SFX]
        do_music = bool(music_ids)
        do_amb = bool(amb_ids)
        do_sfx = bool(sfx_ids)

    started = time.time()
    new = {}
    if do_music:
        new["music"] = build_music(music_ids, args.reuse, args.keep_wav, previews)
    if do_amb:
        new["ambience"] = build_ambience(amb_ids, args.reuse, args.keep_wav, previews)
    if do_sfx:
        new["sfx"] = build_sfx(sfx_ids)

    manifest = merge_manifest(new)
    analysis.write_manifest(manifest, MANIFEST)
    counts = {k: len(v) for k, v in manifest.items()}
    total_dur = sum(float(e["duration"]) for key in ("music", "ambience", "sfx")
                    for e in manifest[key])
    print(f"\nmanifest -> {MANIFEST}  {counts}  total audio {total_dur / 60:.2f} min")
    bad = []
    for key in ("music", "ambience", "sfx"):
        for e in manifest[key]:
            c = e.get("checks", {})
            if c.get("nan") or c.get("clipped_samples", 0) > 0:
                bad.append((key, e["id"], "nan/clip"))
            if not c.get("peak_ok", True):
                bad.append((key, e["id"], "peak"))
            if key == "music" and not c.get("rms_ok", True):
                bad.append((key, e["id"], "rms"))
            if key in ("music", "ambience") and not c.get("continuous", True):
                bad.append((key, e["id"], "seam"))
    if bad:
        print("CHECKS FAILED:", bad)
    else:
        print("all checks passed")
    report_sizes()
    print(f"elapsed {time.time() - started:.1f}s")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
