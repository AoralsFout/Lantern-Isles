#!/usr/bin/env python3
"""Objective audio checks and inspection previews for the Lantern Isles batch."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from synth import SR, amp_to_db, decode_audio, peak, read_wav, rms

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets" / "audio"
PREVIEWS = ASSETS / "previews"
FONT_MAIN = ROOT / "assets" / "fonts" / "Marcellus-Regular.ttf"
FONT_MONO = Path(r"C:\Windows\Fonts\consola.ttf")


def load_audio(path) -> tuple[np.ndarray, int, str]:
    path = Path(path)
    if path.suffix.lower() == ".ogg":
        x = decode_audio(path, sr=SR, ch=2)
        return x, SR, "ogg"
    x, sr = read_wav(path)
    return x.astype(np.float64), sr, "wav"


def basic_metrics(x: np.ndarray, sr: int) -> dict:
    x = np.asarray(x)
    if x.ndim == 1:
        x = x[:, None]
    p = peak(x)
    r = rms(x)
    dc = float(np.mean(x)) if x.size else 0.0
    clip = int(np.sum(np.abs(x) > 0.999))
    return {
        "sample_rate": int(sr),
        "channels": int(x.shape[1]),
        "duration": round(len(x) / sr, 4),
        "peak_dbfs": round(amp_to_db(p), 3) if p > 1e-12 else -120.0,
        "rms_dbfs": round(amp_to_db(r), 3) if r > 1e-12 else -120.0,
        "dc_offset": float(f"{dc:.3e}"),
        "nan": bool(np.isnan(x).any() or np.isinf(x).any()),
        "clipped_samples": clip,
        "silent": bool(r < 1e-6),
    }


def loop_metrics(x: np.ndarray, sr: int, xfade: float = 2.0) -> dict:
    """Seam continuity measurements on the finished loop file."""
    x = np.asarray(x)
    if x.ndim == 1:
        x = x[:, None]
    mono = x.mean(axis=1)
    win = min(len(mono) // 3, int(0.10 * sr))
    head = rms(mono[:win])
    tail = rms(mono[-win:])
    p = peak(mono)
    edge = abs(float(mono[0] - mono[-1])) / max(p, 1e-9)
    d0 = float(mono[1] - mono[0]) if len(mono) > 1 else 0.0
    d1 = float(mono[-1] - mono[-2]) if len(mono) > 1 else 0.0
    deriv = abs(d0 - d1) / max(p, 1e-9)
    # loudness continuity across the actual wrap point
    pre = rms(mono[-int(0.05 * sr):])
    post = rms(mono[: int(0.05 * sr)])
    delta = amp_to_db(max(post, 1e-9)) - amp_to_db(max(pre, 1e-9))
    return {
        "seam_edge_jump": float(f"{edge:.5f}"),
        "seam_slope_jump": float(f"{deriv:.5f}"),
        "seam_head_rms_dbfs": round(amp_to_db(max(head, 1e-9)), 2),
        "seam_tail_rms_dbfs": round(amp_to_db(max(tail, 1e-9)), 2),
        "seam_rms_delta_db": round(delta, 2),
        "xfade_seconds": float(xfade),
        # loop[0] is the sample at loop_len by construction, so a genuine click
        # shows up as a slope discontinuity, not as an absolute edge jump.
        "continuous": bool(deriv < 0.02 and abs(delta) < 3.0),
    }


def spectrogram_db(mono: np.ndarray, n_fft: int = 2048, hop: int = 1024) -> np.ndarray:
    if len(mono) < n_fft:
        mono = np.pad(mono, (0, n_fft - len(mono)))
    win = np.hanning(n_fft).astype(np.float32)
    frames = 1 + (len(mono) - n_fft) // hop
    out = np.empty((frames, n_fft // 2 + 1), dtype=np.float32)
    for i in range(frames):
        seg = mono[i * hop: i * hop + n_fft]
        out[i] = np.abs(np.fft.rfft(seg * win))
    out = 20.0 * np.log10(np.maximum(out, 1e-9))
    out -= float(np.max(out))
    return out


def _cmap(values: np.ndarray) -> np.ndarray:
    """float 0..1 -> RGB via a soft night-sky / gold palette."""
    stops = np.array([0.00, 0.14, 0.32, 0.52, 0.70, 0.86, 1.00])
    cols = np.array([
        [7, 10, 18], [15, 35, 55], [25, 84, 98], [70, 132, 120],
        [174, 162, 103], [232, 198, 120], [255, 246, 219],
    ], dtype=np.float32)
    v = np.clip(values, 0.0, 1.0)
    out = np.empty(v.shape + (3,), dtype=np.uint8)
    for c in range(3):
        out[..., c] = np.interp(v, stops, cols[:, c]).astype(np.uint8)
    return out


def make_preview(path, x: np.ndarray, sr: int, title: str, subtitle: str,
                 metrics: dict) -> Path:
    W, H = 1400, 780
    img = Image.new("RGB", (W, H), (10, 13, 20))
    d = ImageDraw.Draw(img)
    try:
        f_title = ImageFont.truetype(str(FONT_MAIN), 30)
        f_small = ImageFont.truetype(str(FONT_MAIN), 16)
        f_tiny = ImageFont.truetype(str(FONT_MONO), 13)
    except Exception:
        f_title = f_small = f_tiny = ImageFont.load_default()
    cream = (238, 226, 196)
    gold = (214, 178, 98)
    dim = (128, 142, 148)

    d.text((26, 16), title, font=f_title, fill=cream)
    d.text((28, 52), subtitle, font=f_small, fill=dim)
    d.text((40, 74), "WAVEFORM  /  min-max envelope  /  0 dBFS = full panel",
           font=f_tiny, fill=dim)

    mono = x.mean(axis=1) if x.ndim > 1 else x
    # ---- waveform panel -------------------------------------------------
    wx, wy, ww, wh = 40, 94, 1320, 200
    d.rectangle([wx, wy, wx + ww, wy + wh], fill=(13, 19, 28), outline=(38, 50, 58))
    n = len(mono)
    cols = np.linspace(0, n, ww + 1).astype(np.int64)
    mid = wy + wh // 2
    for i in range(ww):
        a, b = cols[i], max(cols[i] + 1, cols[i + 1])
        seg = mono[a:b]
        if len(seg) == 0:
            continue
        lo, hi = float(seg.min()), float(seg.max())
        y0 = mid - int(hi * (wh * 0.46))
        y1 = mid - int(lo * (wh * 0.46))
        d.line([(wx + i, y0), (wx + i, max(y1, y0 + 1))], fill=gold)
    d.line([(wx, mid), (wx + ww, mid)], fill=(45, 60, 66))

    # ---- spectrogram panel ---------------------------------------------
    sx, sy, sw, sh = 100, 330, 1260, 350
    d.text((40, 310), "SPECTROGRAM  /  log 40 Hz-18 kHz  /  78 dB  /  +4.5 dB-oct display tilt > 200 Hz",
           font=f_tiny, fill=dim)
    spec = spectrogram_db(mono)
    n_bins = spec.shape[1]
    freqs = np.linspace(0, sr / 2, n_bins)
    log_f = np.geomspace(40.0, 18000.0, sh)
    idx = np.clip(np.searchsorted(freqs, log_f), 1, n_bins - 1)
    spec = spec[:, idx]
    tilt = np.clip(4.5 * np.log2(np.maximum(log_f, 200.0) / 200.0), 0.0, 18.0)
    spec = spec + tilt[None, :]
    spec = spec - float(np.max(spec))
    # time resample to sw columns via PIL (avoids aliasing stripes)
    norm = np.clip((spec + 78.0) / 78.0, 0.0, 1.0)
    grey = Image.fromarray((norm * 255.0).astype(np.uint8), "L").resize(
        (sw, sh), Image.BILINEAR)
    norm2 = np.asarray(grey, dtype=np.float32) / 255.0
    rgb = _cmap(norm2[::-1, :])
    s_img = Image.fromarray(rgb, "RGB")
    img.paste(s_img, (sx, sy))
    d.rectangle([sx, sy, sx + sw, sy + sh], outline=(38, 50, 58))
    for hz_label in (100, 500, 2000, 8000):
        yy = int(sy + sh - (math.log(hz_label / 40.0) / math.log(18000.0 / 40.0)) * sh)
        d.line([(sx, yy), (sx + sw, yy)], fill=(88, 104, 110), width=1)
        d.text((44, yy - 7), f"{hz_label} Hz", font=f_tiny, fill=(210, 200, 180))

    # ---- footer stats ---------------------------------------------------
    lines = [
        f"duration {metrics['duration']:.2f}s   peak {metrics['peak_dbfs']:.2f} dBFS   "
        f"rms {metrics['rms_dbfs']:.2f} dBFS   dc {metrics['dc_offset']:.1e}   "
        f"ch {metrics['channels']} @ {metrics['sample_rate']} Hz",
    ]
    if "seam_rms_delta_db" in metrics:
        lines.append(
            f"loop seam: edge {metrics['seam_edge_jump']:.4f}   slope "
            f"{metrics['seam_slope_jump']:.4f}   rms delta {metrics['seam_rms_delta_db']:+.2f} dB   "
            f"{'CONTINUOUS' if metrics.get('continuous') else 'CHECK'}"
        )
    d.text((40, 700), lines[0], font=f_tiny, fill=cream)
    if len(lines) > 1:
        d.text((40, 722), lines[1], font=f_tiny, fill=dim)
    d.text((40, 748), f"{path.name}  -  generated from numpy oscillators, no sampled audio",
           font=f_tiny, fill=(90, 103, 110))
    out = PREVIEWS / f"{path.stem}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def analyze_file(path, loop: bool = False, xfade: float = 2.0) -> dict:
    x, sr, kind = load_audio(path)
    m = basic_metrics(x, sr)
    if loop:
        m.update(loop_metrics(x, sr, xfade))
    return m


def write_manifest(items: dict, path: Path) -> None:
    path.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
