#!/usr/bin/env python3
"""Pure-numpy DSP toolkit for the Lantern Isles audio batch.

Everything in assets/audio is synthesised from first principles with numpy:
additive / FM / wavetable oscillators, Karplus-Strong strings, shaped noise,
causal one-pole filters, FFT filters, a generated convolution reverb and a
look-ahead peak limiter.  No scipy, no soundfile, no downloaded audio, no
generative audio service.

Only the Python standard library, numpy and ffmpeg (for OGG encode / decode)
are used.
"""
from __future__ import annotations

import math
import re
import struct
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100
PI = math.pi
TAU = 2.0 * PI
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"

NOTE_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NOTE_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def note_to_midi(name: str) -> int:
    m = _NOTE_RE.match(str(name).strip())
    if not m:
        raise ValueError(f"bad note name {name!r}")
    letter, accidental, octave = m.groups()
    midi = (int(octave) + 1) * 12 + NOTE_BASE[letter.upper()]
    if accidental == "#":
        midi += 1
    elif accidental == "b":
        midi -= 1
    return midi


def midi_to_hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((float(midi) - 69.0) / 12.0)


def hz(name) -> float:
    if isinstance(name, (int, np.integer)):
        return midi_to_hz(int(name))
    return midi_to_hz(note_to_midi(str(name)))


def db_to_amp(db: float) -> float:
    return 10.0 ** (db / 20.0)


def amp_to_db(x: float) -> float:
    return 20.0 * math.log10(max(float(x), 1e-12))


def rms(x) -> float:
    x = np.asarray(x, dtype=np.float64)
    if x.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(x * x)))


def peak(x) -> float:
    x = np.asarray(x, dtype=np.float64)
    return float(np.max(np.abs(x))) if x.size else 0.0


def next_fast_len(n: int) -> int:
    """Next power of two (simple and predictable, fast enough for this batch)."""
    if n <= 1:
        return 1
    return 1 << int(math.ceil(math.log2(int(n))))


def fade_edges(x: np.ndarray, fin_ms: float = 2.0, fout_ms: float = 2.0) -> np.ndarray:
    x = np.array(x, copy=True)
    n = len(x)
    ni = min(n, max(1, int(fin_ms * SR / 1000.0)))
    no = min(n, max(1, int(fout_ms * SR / 1000.0)))
    x[:ni] *= np.linspace(0.0, 1.0, ni, dtype=x.dtype) ** 0.5
    x[-no:] *= np.linspace(1.0, 0.0, no, dtype=x.dtype) ** 0.5
    return x


def normalize(x: np.ndarray, level: float = 1.0) -> np.ndarray:
    p = peak(x)
    if p < 1e-12:
        return np.zeros_like(x)
    return (x * (level / p)).astype(np.float32)


# --------------------------------------------------------------------------
# WAV I/O (float32 / int16 / int24) -- ffmpeg reads these happily
# --------------------------------------------------------------------------
def write_wav(path, data, sr: int = SR, fmt: str = "f32") -> None:
    data = np.asarray(data)
    if data.ndim == 1:
        data = data[:, None]
    ch = int(data.shape[1])
    if fmt == "f32":
        tag, bits = 3, 32
        block = np.ascontiguousarray(data, dtype="<f4").tobytes()
    elif fmt == "s16":
        tag, bits = 1, 16
        d = np.clip(data, -1.0, 1.0 - 1.5 / 32768.0)
        # TPDF dither, ~1 LSB, keeps fade tails musical instead of quantised
        rng = np.random.default_rng(0xA0D10)
        d = d * 32767.0 + (rng.random(d.shape) - rng.random(d.shape)) * 0.5
        block = np.clip(np.round(d), -32768, 32767).astype("<i2").tobytes()
    elif fmt == "s24":
        tag, bits = 1, 24
        d = np.clip(data, -1.0, 1.0 - 1.5 / 8388608.0)
        q = np.round(d * 8388607.0).astype("<i4")
        raw = q.tobytes()
        block = bytearray(len(q) * 3)
        for i in range(3):
            block[i::3] = raw[i::4]
        block = bytes(block)
    else:
        raise ValueError(fmt)
    byte_rate = sr * ch * bits // 8
    block_align = ch * bits // 8
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(block), b"WAVE", b"fmt ", 16, tag, ch, sr,
        byte_rate, block_align, bits, b"data", len(block),
    )
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        f.write(header)
        f.write(block)


def read_wav(path) -> tuple[np.ndarray, int]:
    """Minimal RIFF reader for PCM16 / PCM24 / IEEE float32."""
    raw = Path(path).read_bytes()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    pos = 12
    fmt_tag = ch = sr = bits = None
    data = None
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        size = struct.unpack("<I", raw[pos + 4:pos + 8])[0]
        body = raw[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt_tag, ch, sr, _br, _ba, bits = struct.unpack("<HHIIHH", body[:16])
        elif cid == b"data":
            data = body
        pos += 8 + size + (size & 1)
    if data is None:
        raise ValueError("no data chunk")
    if fmt_tag == 3 and bits == 32:
        arr = np.frombuffer(data, dtype="<f4").astype(np.float64)
    elif fmt_tag == 1 and bits == 16:
        arr = np.frombuffer(data, dtype="<i2").astype(np.float64) / 32768.0
    elif fmt_tag == 1 and bits == 24:
        b = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        v = np.where(v & 0x800000, v - 0x1000000, v)
        arr = v.astype(np.float64) / 8388608.0
    else:
        raise ValueError(f"unsupported wav format tag={fmt_tag} bits={bits}")
    return arr.reshape(-1, ch), int(sr)


def decode_audio(path, sr: int = SR, ch: int = 2) -> np.ndarray:
    """Decode any ffmpeg-readable file to float32 samples, shape (n, ch)."""
    cmd = [
        FFMPEG, "-v", "error", "-i", str(path), "-map_metadata", "-1",
        "-f", "f32le", "-acodec", "pcm_f32le", "-ac", str(ch), "-ar", str(sr), "-",
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg decode failed for {path}: {proc.stderr.decode('utf-8', 'replace')[-800:]}")
    a = np.frombuffer(proc.stdout, dtype="<f4")
    if a.size % ch:
        a = a[: a.size - (a.size % ch)]
    return a.reshape(-1, ch).astype(np.float64)


def encode_ogg(src_wav, dst_ogg, quality: int = 5) -> None:
    cmd = [
        FFMPEG, "-y", "-v", "error", "-i", str(src_wav),
        "-c:a", "libvorbis", "-q:a", str(quality), "-ar", str(SR), "-ac", "2",
        "-map_metadata", "-1", str(dst_ogg),
    ]
    subprocess.run(cmd, check=True)


# --------------------------------------------------------------------------
# basic envelopes
# --------------------------------------------------------------------------
def env_perc(n: int, attack: float = 0.003, tau: float = 0.5) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / SR
    a = np.clip(t / max(attack, 1e-5), 0.0, 1.0)
    return (a * np.exp(-t / max(tau, 1e-4))).astype(np.float32)


def env_pad(n: int, hold: float, attack: float = 0.8, release: float = 1.5) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / SR
    a = np.clip(t / max(attack, 1e-4), 0.0, 1.0)
    env = 0.5 - 0.5 * np.cos(PI * a)  # raised-cosine swell
    if release > 0:
        rel = np.clip((t - hold) / release, 0.0, 1.0)
        env *= 0.5 + 0.5 * np.cos(PI * rel)
    return env.astype(np.float32)


def env_adsr(n: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
    a = min(n, max(1, int(attack * SR)))
    d = min(max(0, n - a), max(1, int(decay * SR)))
    r = min(max(0, n - a - d), max(1, int(release * SR)))
    s = max(0, n - a - d - r)
    parts = [
        np.linspace(0.0, 1.0, a, endpoint=False, dtype=np.float32),
        np.linspace(1.0, sustain, d, endpoint=False, dtype=np.float32),
        np.full(s, sustain, dtype=np.float32),
        np.linspace(sustain, 0.0, r, dtype=np.float32),
    ]
    env = np.concatenate(parts)
    if len(env) < n:
        env = np.pad(env, (0, n - len(env)))
    return env[:n]


# --------------------------------------------------------------------------
# noise and filters
# --------------------------------------------------------------------------
def shaped_noise(n: int, seed: int, gain_fn, ch: int = 1, sr: int = SR) -> np.ndarray:
    """Circular noise with an arbitrary spectral gain curve (0..Nyquist)."""
    rng = np.random.default_rng(seed)
    N = next_fast_len(n)
    f = np.fft.rfftfreq(N, 1.0 / sr)
    g = np.asarray(gain_fn(f), dtype=np.float64)
    g = np.broadcast_to(g, f.shape)
    spec = (rng.standard_normal((f.size, ch)) + 1j * rng.standard_normal((f.size, ch))) * g[:, None]
    x = np.fft.irfft(spec, n=N, axis=0)[:n]
    x = x.astype(np.float32)
    scale = rms(x)
    return x if scale < 1e-9 else (x / scale).astype(np.float32)


def fft_filter(x: np.ndarray, lo=None, hi=None, slope: float = 2.0, sr: int = SR) -> np.ndarray:
    """Zero-phase Butterworth-magnitude filter (gentle, good for beds/pads)."""
    x = np.asarray(x, dtype=np.float32)
    squeeze = x.ndim == 1
    if squeeze:
        x = x[:, None]
    n = x.shape[0]
    N = next_fast_len(n)
    f = np.fft.rfftfreq(N, 1.0 / sr)
    g = np.ones_like(f)
    if hi is not None:
        g /= np.sqrt(1.0 + (f / max(float(hi), 1e-6)) ** (2.0 * slope))
    if lo is not None:
        g /= np.sqrt(1.0 + (max(float(lo), 1e-6) / np.maximum(f, 1e-6)) ** (2.0 * slope))
    X = np.fft.rfft(x, n=N, axis=0)
    y = np.fft.irfft(X * g[:, None], n=N, axis=0)[:n].astype(np.float32)
    return y[:, 0] if squeeze else y


def spectral_filter(x: np.ndarray, gain_fn, sr: int = SR) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    squeeze = x.ndim == 1
    if squeeze:
        x = x[:, None]
    n = x.shape[0]
    N = next_fast_len(n)
    f = np.fft.rfftfreq(N, 1.0 / sr)
    g = np.asarray(gain_fn(f), dtype=np.float64)
    X = np.fft.rfft(x, n=N, axis=0)
    y = np.fft.irfft(X * g[:, None], n=N, axis=0)[:n].astype(np.float32)
    return y[:, 0] if squeeze else y


def fftconvolve_full(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    h = np.asarray(h, dtype=np.float32)
    N = next_fast_len(len(x) + len(h) - 1)
    return np.fft.irfft(np.fft.rfft(x, n=N) * np.fft.rfft(h, n=N), n=N)[: len(x) + len(h) - 1].astype(np.float32)


def fftconvolve_same(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    y = fftconvolve_full(x, h)
    return y[: len(x)]


def fftconvolve_smooth(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Centred smoothing convolution, same length."""
    y = fftconvolve_full(x, h)
    off = (len(h) - 1) // 2
    return y[off: off + len(x)]


def onepole_lp(x: np.ndarray, fc: float, sr: int = SR) -> np.ndarray:
    """Causal one-pole lowpass via truncated exponential kernel (no pre-ring)."""
    a = math.exp(-TAU * max(fc, 1.0) / sr)
    k = min(len(x), max(2, int(math.ceil(math.log(1e-4) / math.log(a)))))
    h = ((1.0 - a) * a ** np.arange(k)).astype(np.float32)
    return fftconvolve_same(np.asarray(x, dtype=np.float32), h)


def onepole_hp(x: np.ndarray, fc: float, sr: int = SR) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    return (x - onepole_lp(x, fc, sr)).astype(np.float32)


def moving_average(x: np.ndarray, w: int) -> np.ndarray:
    if w <= 1:
        return np.asarray(x, dtype=np.float32)
    win = np.hanning(w + 2)[1:-1]
    win = (win / win.sum()).astype(np.float32)
    return fftconvolve_smooth(np.asarray(x, dtype=np.float32), win)


# --------------------------------------------------------------------------
# wavetable oscillators (cheap, band-limited by harmonic count)
# --------------------------------------------------------------------------
_TABLE_CACHE: dict[int, np.ndarray] = {}


def _saw_table(harmonics: int, size: int = 4096) -> np.ndarray:
    h = max(1, min(64, int(harmonics)))
    tab = _TABLE_CACHE.get(h)
    if tab is None:
        k = np.arange(size)
        tab = np.zeros(size, dtype=np.float32)
        for i in range(1, h + 1):
            tab += (np.sin(TAU * i * k / size) / i).astype(np.float32)
        m = np.max(np.abs(tab))
        if m > 1e-9:
            tab /= m
        tab = np.concatenate([tab, tab[:1]])
        _TABLE_CACHE[h] = tab
    return tab


def table_osc(phase_cycles: np.ndarray, harmonics: int = 16) -> np.ndarray:
    """Linear-interpolated wavetable lookup; phase in cycles."""
    tab = _saw_table(harmonics)
    size = len(tab) - 1
    ph = np.mod(phase_cycles, 1.0).astype(np.float32)
    idx = (ph * size).astype(np.int64)
    frac = (ph * size - idx).astype(np.float32)
    return (tab[idx] * (1.0 - frac) + tab[idx + 1] * frac).astype(np.float32)


def karplus(freq: float, dur: float, seed: int, rt60: float = 1.8,
            bright: float = 0.6, damp: float = 0.0) -> np.ndarray:
    """Vectorised Karplus-Strong plucked string with pitch correction.

    The delay line recurrence only depends on samples N back, so each N-sample
    block can be produced with numpy operations instead of a per-sample loop.
    """
    freq = max(20.0, float(freq))
    N = max(3, int(round(SR / freq)))
    n = max(N * 2, int(dur * SR))
    rng = np.random.default_rng(seed)
    exc = rng.standard_normal(N).astype(np.float32)
    # brightness: soften the excitation with a short moving average
    k = max(1, int(round((1.0 - bright) * 9.0)))
    if k > 1:
        exc = np.convolve(exc, np.ones(k, dtype=np.float32) / k, mode="same")
    exc -= exc.mean()
    exc /= max(np.max(np.abs(exc)), 1e-9)
    exc *= 0.8

    g = 10.0 ** (-3.0 / (max(rt60, 0.1) * freq))
    g = float(np.clip(g, 0.80, 0.9995))
    y = np.zeros(n, dtype=np.float32)
    head = min(N, n)
    y[:head] = exc[:head]
    prev = y[:head].copy()
    prev_last = 0.0
    for start in range(head, n, N):
        m = min(N, n - start)
        shifted = np.empty(m, dtype=np.float32)
        shifted[0] = prev_last
        if m > 1:
            shifted[1:] = prev[: m - 1]
        cur = (g * 0.5 * (prev[:m] + shifted)).astype(np.float32)
        if damp > 0:
            cur = (cur * (1.0 - damp) + damp * np.concatenate(([prev[-1] if len(prev) else 0.0], cur[:-1]))).astype(np.float32)
        y[start: start + m] = cur
        prev_last = prev[m - 1] if m <= len(prev) else prev[-1]
        prev = cur
    # correct equal-tempered pitch (delay N may be slightly off)
    actual = SR / N
    speed = freq / actual
    if abs(speed - 1.0) > 0.0015:
        n_out = max(2, int(round(n / speed)))
        idx = np.arange(n_out, dtype=np.float32) * speed
        y = np.interp(idx, np.arange(n, dtype=np.float32), y).astype(np.float32)
    return y


def fm_bell(freq: float, dur: float, seed: int, ratio: float = 1.4,
            index: float = 2.0, tau: float = 1.2,
            mod_tau: float = 0.35, shimmer: float = 0.18,
            shimmer_ratio: float = 3.97) -> np.ndarray:
    n = max(8, int(dur * SR))
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    ph = TAU * freq * t + index * np.exp(-t / max(mod_tau, 1e-4)) * np.sin(TAU * freq * ratio * t)
    x = np.sin(ph) * np.exp(-t / max(tau, 1e-4))
    if shimmer > 0:
        x += shimmer * np.sin(TAU * freq * shimmer_ratio * t + rng.random() * TAU) * np.exp(-t / max(tau * 0.45, 1e-4))
        x += 0.10 * np.sin(TAU * freq * 2.01 * t + rng.random() * TAU) * np.exp(-t / max(tau * 0.7, 1e-4))
    x *= 1.0 - np.exp(-t / 0.0015)
    return x.astype(np.float32)


def sine_env(freq: float, dur: float, tau: float, attack: float = 0.005, phase: float = 0.0) -> np.ndarray:
    n = max(4, int(dur * SR))
    t = np.arange(n, dtype=np.float32) / SR
    x = np.sin(TAU * freq * t + phase) * np.exp(-t / max(tau, 1e-4))
    x *= 1.0 - np.exp(-t / max(attack, 1e-5))
    return x.astype(np.float32)


# --------------------------------------------------------------------------
# reverb / convolution
# --------------------------------------------------------------------------
def make_reverb_ir(rt60: float = 3.2, predelay: float = 0.022, seed: int = 11,
                   low_gain: float = 1.0) -> np.ndarray:
    """Stereo convolution IR: band-split exponential noise + early reflections.

    IR energy is normalised so that a convolve(send, ir) has roughly the same
    RMS as send; sources use modest send levels on top of that.
    """
    n = int((rt60 * 1.15 + predelay) * SR)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    ir = np.zeros((n, 2), dtype=np.float32)
    # (lo, hi, rt60 multiplier, level)
    layers = [
        (30.0, 250.0, 1.35 * low_gain, 0.95),
        (250.0, 2000.0, 1.05, 1.0),
        (2000.0, 7000.0, 0.60, 0.70),
        (7000.0, 15500.0, 0.34, 0.34),
    ]
    for lo, hi, mult, lev in layers:
        noise = rng.standard_normal((n, 2)).astype(np.float32)
        env = np.where(t >= predelay,
                       np.exp(-6.9078 * np.maximum(t - predelay, 0.0) / max(rt60 * mult, 0.2)),
                       0.0).astype(np.float32)
        layer = fft_filter(noise * env[:, None], lo=lo, hi=hi, slope=1.6)
        ir += lev * layer
    # a handful of early reflections (decorrelated L/R)
    for dt, gain, bal in ((0.011, 0.55, 0.5), (0.019, 0.38, -0.6),
                          (0.029, 0.26, 0.8), (0.041, 0.17, -0.3)):
        idx = int((predelay + dt) * SR)
        if idx < n:
            ir[idx, 0] += gain * (1.0 - 0.5 * bal)
            ir[idx, 1] += gain * (1.0 + 0.5 * bal)
    ir = fft_filter(ir, lo=70.0, hi=13500.0)
    energy = np.sqrt(np.sum(ir.astype(np.float64) ** 2, axis=0, keepdims=True))
    ir /= np.maximum(energy, 1e-9)
    return ir.astype(np.float32)


def convolve_reverb(x: np.ndarray, ir: np.ndarray, block: int = 262144) -> np.ndarray:
    """Overlap-add convolution of a (n, 2) send bus with a (m, 2) IR."""
    x = np.asarray(x, dtype=np.float32)
    out = np.zeros_like(x)
    Lh = len(ir)
    N = next_fast_len(block + Lh - 1)
    H = np.fft.rfft(ir, n=N, axis=0)
    for start in range(0, len(x), block):
        chunk = x[start:start + block]
        n = len(chunk)
        Y = np.fft.irfft(np.fft.rfft(chunk, n=N, axis=0) * H, n=N, axis=0)
        m = min(n + Lh - 1, len(out) - start)
        out[start:start + m] += Y[:m].astype(np.float32)
    return out


# --------------------------------------------------------------------------
# loop assembly and mastering
# --------------------------------------------------------------------------
def crossfade_loop(buf: np.ndarray, loop_len: float, xfade: float, sr: int = SR) -> np.ndarray:
    """Equal-power head/tail crossfade.

    ``buf`` starts at ``-xfade`` and runs to ``loop_len + xfade``, so the
    composition itself occupies ``buf[xfade : xfade + loop_len]``.  The first
    ``xfade`` seconds of the loop are blended from the *next cycle's* opening
    (rendered just after loop_len) into the opening material, which makes the
    wrap sample-continuous: loop[0] equals the sample at loop_len and
    loop[-1] is the sample just before it.
    """
    buf = np.asarray(buf, dtype=np.float32)
    if buf.ndim == 1:
        buf = buf[:, None]
    nl = int(round(loop_len * sr))
    nx = int(round(xfade * sr))
    if len(buf) < 2 * nx + nl:
        raise ValueError(f"loop buffer too short: {len(buf)} < {2 * nx + nl}")
    off = nx
    out = buf[off: off + nl].copy()
    head = buf[off: off + nx]                 # composition 0 .. X
    tail = buf[off + nl: off + nl + nx]       # composition L .. L+X
    w = np.linspace(0.0, PI / 2.0, nx, dtype=np.float32)[:, None]
    out[:nx] = head * np.sin(w) + tail * np.cos(w)
    return out


def _dilate_max(a: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return a.copy()
    out = a.copy()
    s = 1
    while s <= radius:
        out[s:] = np.maximum(out[s:], a[:-s])
        out[:-s] = np.maximum(out[:-s], a[s:])
        s *= 2
    return out


def limit_peak(x: np.ndarray, ceiling: float = 0.9,
               lookahead: float = 0.006, release: float = 0.12,
               passes: int = 3) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    squeeze = x.ndim == 1
    if squeeze:
        x = x[:, None]
    for _ in range(passes):
        env = np.max(np.abs(x), axis=1)
        env = _dilate_max(env, max(1, int(lookahead * SR)))
        g = np.minimum(1.0, ceiling / np.maximum(env, 1e-9)).astype(np.float32)
        w = max(1, int(release * SR))
        if w > 3:
            gs = moving_average(g, w)
            g = np.minimum(g, gs).astype(np.float32)
        x = (x * g[:, None]).astype(np.float32)
    return x[:, 0] if squeeze else x


def master(x: np.ndarray, target_rms: float = -18.0, ceiling_db: float = -1.4,
           hp: float = 24.0) -> np.ndarray:
    """DC/rumble removal + iterated RMS gain + look-ahead peak limiting."""
    x = np.asarray(x, dtype=np.float32)
    squeeze = x.ndim == 1
    if squeeze:
        x = x[:, None]
    x = fft_filter(x, lo=hp, slope=2.0)
    x = x - np.mean(x, axis=0, keepdims=True)
    p = peak(x)
    if p < 1e-9:
        return x[:, 0] if squeeze else x
    x = (x / p).astype(np.float32)
    ceiling = db_to_amp(ceiling_db)
    for _ in range(9):
        cur = amp_to_db(rms(x))
        if abs(cur - target_rms) < 0.12:
            break
        adjust = float(np.clip(10.0 ** ((target_rms - cur) / 20.0), 0.5, 2.0))
        x = (x * adjust).astype(np.float32)
        x = limit_peak(x, ceiling=ceiling)
    # final safety trim (never boost here)
    p = peak(x)
    if p > ceiling:
        x = (x * (ceiling / p)).astype(np.float32)
    return x[:, 0] if squeeze else x
