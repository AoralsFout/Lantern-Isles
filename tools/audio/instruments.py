#!/usr/bin/env python3
"""Instrument voice bank for the Lantern Isles score.

Every voice is algorithmically synthesised: additive tines/piano partials,
Karplus-Strong strings, FM bells, wavetable string/choir pads, filtered noise
percussion and breath.  Renderers take (freq, hold_seconds, velocity, seed)
and return a mono float32 array.
"""
from __future__ import annotations

import math

import numpy as np

from synth import (
    SR, TAU, PI, amp_to_db, db_to_amp, env_pad, fft_filter, fm_bell, hz,
    karplus, normalize, shaped_noise, sine_env, table_osc,
)


def _finish(x: np.ndarray, scale: float, vel: float, dc: bool = True) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if dc and x.size:
        x = x - np.mean(x)
    m = float(np.max(np.abs(x))) if x.size else 0.0
    if m < 1e-9:
        return np.zeros_like(x)
    return (x * (scale * vel / m)).astype(np.float32)


def _n(dur: float, extra: float = 0.0) -> int:
    return max(8, int(round((max(dur, 0.02) + extra) * SR)))


# --------------------------------------------------------------------------
# tines / keys
# --------------------------------------------------------------------------
def i_kalimba(freq, dur, vel, seed, **kw):
    n = _n(min(dur, 5.0), 0.35)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    partials = [(1.0, 1.0, 1.7), (2.0, 0.38, 0.95), (4.08, 0.13, 0.52),
                (6.35, 0.05, 0.3), (9.1, 0.02, 0.18)]
    x = np.zeros(n, dtype=np.float32)
    for ratio, a, tau in partials:
        x += (a * np.exp(-t / tau) * np.sin(TAU * freq * ratio * t + rng.random() * TAU)).astype(np.float32)
    click = rng.standard_normal(n).astype(np.float32) * np.exp(-t / 0.004).astype(np.float32)
    click = fft_filter(click, lo=1800, hi=7500)
    x += 0.055 * click
    x *= (1.0 - np.exp(-t / 0.0018)).astype(np.float32)
    return _finish(x, 0.64, vel)


def i_musicbox(freq, dur, vel, seed, **kw):
    n = _n(min(dur, 5.0), 0.4)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    partials = [(1.0, 1.0, 1.35), (2.0, 0.30, 0.65), (3.01, 0.22, 0.42),
                (4.23, 0.12, 0.26), (5.62, 0.05, 0.16), (7.1, 0.02, 0.1)]
    x = np.zeros(n, dtype=np.float32)
    for ratio, a, tau in partials:
        x += (a * np.exp(-t / tau) * np.sin(TAU * freq * ratio * t + rng.random() * TAU)).astype(np.float32)
    x += 0.02 * rng.standard_normal(n).astype(np.float32) * np.exp(-t / 0.003)
    x *= (1.0 - np.exp(-t / 0.0012)).astype(np.float32)
    return _finish(x, 0.55, vel)


def i_celesta(freq, dur, vel, seed, **kw):
    n = _n(min(dur, 5.0), 0.5)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    partials = [(1.0, 1.0, 1.8), (2.0, 0.22, 0.9), (3.98, 0.18, 0.5),
                (5.4, 0.06, 0.3), (7.9, 0.03, 0.18)]
    x = np.zeros(n, dtype=np.float32)
    for ratio, a, tau in partials:
        x += (a * np.exp(-t / tau) * np.sin(TAU * freq * ratio * t + rng.random() * TAU)).astype(np.float32)
    x *= (1.0 - np.exp(-t / 0.0015)).astype(np.float32)
    x = fft_filter(x, lo=120, hi=11000)
    return _finish(x, 0.58, vel)


def i_piano(freq, dur, vel, seed, **kw):
    n = _n(min(dur, 7.0), 0.35)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    B = 0.00038
    base_tau = float(np.clip(3.1 * (220.0 / max(freq, 30.0)) ** 0.28, 0.85, 4.2))
    max_h = max(1, min(15, int(9000.0 / max(freq, 30.0))))
    x = np.zeros(n, dtype=np.float32)
    for h in range(1, max_h + 1):
        fh = freq * h * math.sqrt(1.0 + B * h * h)
        if fh > 15000:
            break
        a = (1.0 / h ** 1.12) * math.exp(-0.055 * (h - 1))
        tau = base_tau / (1.0 + 0.30 * (h - 1))
        x += (a * np.exp(-t / tau) * np.sin(TAU * fh * t + rng.random() * TAU)).astype(np.float32)
    # unison beating string
    x += (0.16 * np.exp(-t / base_tau) * np.sin(TAU * freq * 2.0 ** (1.1 / 1200.0) * t)).astype(np.float32)
    # hammer
    hammer = rng.standard_normal(n).astype(np.float32) * np.exp(-t / 0.007).astype(np.float32)
    hammer = fft_filter(hammer, lo=250, hi=4200)
    x += 0.06 * hammer
    x *= (1.0 - np.exp(-t / 0.0025)).astype(np.float32)
    x = fft_filter(x, lo=45, hi=12500)
    return _finish(x, 0.70, vel)


# --------------------------------------------------------------------------
# strings / choir / pads
# --------------------------------------------------------------------------
def _formant_gain(f):
    g = 0.10
    for c, bw, a in ((720.0, 150.0, 1.0), (1180.0, 180.0, 0.58),
                     (2750.0, 320.0, 0.34), (3600.0, 400.0, 0.16)):
        g = g + a / (1.0 + ((f - c) / bw) ** 2)
    return g / 1.7


def i_strings(freq, dur, vel, seed, attack=1.1, release=1.6,
              harmonics=9, detune=5.0, cutoff=2600.0, vibrato=2.2, **kw):
    n = _n(dur, release)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    x = np.zeros(n, dtype=np.float32)
    for d in (-detune, 0.0, detune):
        f = freq * 2.0 ** (d / 1200.0)
        depth = rng.uniform(0.55, 1.15) * vibrato  # cents
        rate = rng.uniform(0.85, 1.85)
        ph = f * t + (depth / 1200.0 * math.log(2.0)) * f / (TAU * rate) * np.cos(TAU * rate * t + rng.random() * TAU)
        x += table_osc(ph, harmonics)
    x /= 3.0
    env = env_pad(n, hold=dur, attack=attack, release=release)
    x *= env
    x = fft_filter(x, lo=55.0, hi=cutoff)
    return _finish(x, 0.26, vel)


def i_choir(freq, dur, vel, seed, attack=1.4, release=2.2, **kw):
    n = _n(dur, release)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    x = np.zeros(n, dtype=np.float32)
    for d in (-7.0, -2.0, 3.0, 8.0):
        f = freq * 2.0 ** (d / 1200.0)
        rate = rng.uniform(0.7, 1.4)
        depth = rng.uniform(2.0, 4.0)
        ph = f * t + (depth / 1200.0 * math.log(2.0)) * f / (TAU * rate) * np.cos(TAU * rate * t + rng.random() * TAU)
        x += table_osc(ph, 26)
    x /= 4.0
    env = env_pad(n, hold=dur, attack=attack, release=release)
    x *= env
    x = fft_filter(x, lo=90.0, hi=6200.0)
    # formant colouring
    freqs = np.fft.rfftfreq(1 << max(1, int(math.ceil(math.log2(n)))), 1.0 / SR)
    gain = _formant_gain(freqs)
    spec = np.fft.rfft(x, n=1 << int(math.ceil(math.log2(n))))
    x = np.fft.irfft(spec * gain, n=1 << int(math.ceil(math.log2(n))))[:n].astype(np.float32)
    # breath
    breath = shaped_noise(n, seed + 991, lambda f: np.exp(-((np.log(np.maximum(f, 20.0) / 2100.0)) ** 2) / 0.5), ch=1)[:, 0]
    x += 0.06 * breath * env
    x *= 1.0 - np.exp(-t / 0.0008)
    return _finish(x, 0.23, vel)


def next_fast_len_local(n):
    return 1 << int(math.ceil(math.log2(max(1, n))))


def i_pad(freq, dur, vel, seed, attack=2.2, release=3.0, **kw):
    return i_strings(freq, dur, vel, seed, attack=attack, release=release,
                     harmonics=11, detune=7.5, cutoff=1700.0, vibrato=1.2)


def i_flute(freq, dur, vel, seed, attack=0.09, release=0.25, **kw):
    n = _n(dur, release)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    vib = 1.0 + 0.0035 * np.sin(TAU * 5.1 * t + rng.random() * TAU)
    ph = TAU * freq * np.cumsum(vib.astype(np.float64)) / SR
    x = (np.sin(ph) + 0.16 * np.sin(2.0 * ph + 0.3) + 0.06 * np.sin(3.0 * ph + 1.1)).astype(np.float32)
    env = env_pad(n, hold=dur, attack=attack, release=release)
    x *= env
    breath = shaped_noise(n, seed + 17, lambda f: np.exp(-((np.log(np.maximum(f, 20.0) / 2600.0)) ** 2) / 0.35), ch=1)[:, 0]
    x += 0.07 * breath * env
    x = fft_filter(x, lo=180.0, hi=9000.0)
    return _finish(x, 0.40, vel)


# --------------------------------------------------------------------------
# plucked strings
# --------------------------------------------------------------------------
def i_harp(freq, dur, vel, seed, **kw):
    n = _n(dur, 0.5)
    y = karplus(freq, dur + 0.5, seed, rt60=2.3, bright=0.62)
    y = y[:n]
    n = len(y)
    t = np.arange(n, dtype=np.float32) / SR
    # body + string air
    y = fft_filter(y, lo=55.0, hi=7500.0)
    y += 0.10 * np.sin(TAU * freq * t) * np.exp(-t / 1.1).astype(np.float32)
    y *= (1.0 - np.exp(-t / 0.0015)).astype(np.float32)
    return _finish(y, 0.58, vel)


def i_guzheng(freq, dur, vel, seed, **kw):
    n = _n(dur, 0.6)
    y = karplus(freq, dur + 0.6, seed, rt60=2.6, bright=0.86, damp=0.02)
    y = y[:n]
    n = len(y)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed + 5)
    pick = rng.standard_normal(n).astype(np.float32) * np.exp(-t / 0.0035).astype(np.float32)
    pick = fft_filter(pick, lo=2600, hi=9000)
    y = y + 0.09 * pick
    # sympathetic octave shimmer, like a guzheng soundboard
    y += 0.06 * np.sin(TAU * freq * 2.0 * t) * np.exp(-t / 0.9).astype(np.float32)
    y = fft_filter(y, lo=70.0, hi=9500.0)
    return _finish(y, 0.62, vel)


def i_oud(freq, dur, vel, seed, **kw):
    n = _n(dur, 0.35)
    y = karplus(freq, dur + 0.35, seed, rt60=1.05, bright=0.92)
    y = y[:n]
    n = len(y)
    t = np.arange(n, dtype=np.float32) / SR
    # body resonance around 190 Hz + a little string buzz
    body = np.sin(TAU * 190.0 * t) * np.exp(-t / 0.22).astype(np.float32)
    y += 0.10 * body
    rng = np.random.default_rng(seed + 3)
    buzz = rng.standard_normal(n).astype(np.float32) * np.exp(-t / 0.02).astype(np.float32)
    buzz = fft_filter(buzz, lo=900, hi=3200)
    y += 0.035 * buzz
    y = fft_filter(y, lo=70.0, hi=6500.0)
    return _finish(y, 0.62, vel)


# --------------------------------------------------------------------------
# bells / glass / shimmer
# --------------------------------------------------------------------------
def i_bell(freq, dur, vel, seed, **kw):
    ratio = kw.get("ratio", 1.41)
    index = kw.get("index", 2.1)
    tau = kw.get("tau", 1.35)
    y = fm_bell(freq, dur, seed, ratio=ratio, index=index, tau=tau,
                mod_tau=0.4, shimmer=0.2)
    y = fft_filter(y, lo=90.0, hi=12000.0)
    return _finish(y, 0.54, vel)


def i_glass(freq, dur, vel, seed, **kw):
    y = fm_bell(freq, dur, seed, ratio=2.76, index=1.8, tau=2.2,
                mod_tau=0.7, shimmer=0.28, shimmer_ratio=5.42)
    y = fft_filter(y, lo=150.0, hi=15000.0)
    return _finish(y, 0.50, vel)


def i_shimmer(freq, dur, vel, seed, **kw):
    n = _n(min(dur, 3.0), 0.6)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    x = 0.6 * np.sin(TAU * freq * t + 0.9 * np.exp(-t / 0.08) * np.sin(TAU * freq * 2.4 * t))
    x += 0.4 * np.sin(TAU * freq * 2.01 * t + rng.random() * TAU)
    x *= np.exp(-t / 1.1) * (1.0 - np.exp(-t / 0.004))
    x = fft_filter(x, lo=1200.0, hi=17000.0)
    return _finish(x, 0.17, vel)


# --------------------------------------------------------------------------
# low end
# --------------------------------------------------------------------------
def i_bass(freq, dur, vel, seed, attack=0.018, release=0.35, **kw):
    n = _n(dur, release)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    f2 = freq * 2.0 ** (0.7 / 1200.0)  # slow beating with the main sine
    x = (np.sin(TAU * freq * t) + 0.14 * np.sin(TAU * f2 * t)
         + 0.10 * np.sin(TAU * 2.0 * freq * t + 0.4)
         + 0.035 * np.sin(TAU * 3.0 * freq * t + 1.2)).astype(np.float32)
    env = env_pad(n, hold=dur, attack=attack, release=release)
    x *= env
    x = np.tanh(1.25 * x) * 0.8
    x = fft_filter(x, lo=28.0, hi=1800.0)
    return _finish(x, 0.40, vel)


def i_sub(freq, dur, vel, seed, attack=2.0, release=3.5, **kw):
    n = _n(dur, release)
    t = np.arange(n, dtype=np.float32) / SR
    x = (np.sin(TAU * freq * t) + 0.20 * np.sin(TAU * freq * 2.0 * t + 0.6)
         + 0.10 * np.sin(TAU * freq * 3.0 * t + 2.1)).astype(np.float32)
    # very slow acoustic beating so the drone never sits on one exact frequency
    x += 0.10 * np.sin(TAU * (freq + 0.13) * t).astype(np.float32)
    env = env_pad(n, hold=dur, attack=attack, release=release)
    x *= env
    x = np.tanh(0.9 * x) * 0.9
    x = fft_filter(x, lo=24.0, hi=900.0)
    return _finish(x, 0.20, vel)


# --------------------------------------------------------------------------
# percussion
# --------------------------------------------------------------------------
def i_dum(freq, dur, vel, seed, **kw):
    n = _n(0.55, 0.2)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    f0 = float(freq) if freq > 30 else 78.0
    # pitch drop: instantaneous frequency f0*(1 + 0.55*exp(-t/0.035))
    phase = TAU * f0 * (t + 0.55 * 0.035 * (1.0 - np.exp(-t / 0.035)))
    body = np.sin(phase) * np.exp(-t / 0.24)
    click = rng.standard_normal(n).astype(np.float32) * np.exp(-t / 0.018).astype(np.float32)
    click = fft_filter(click, lo=55.0, hi=900.0)
    x = body + 0.45 * click
    x *= 1.0 - np.exp(-t / 0.0015)
    return _finish(x, 0.50, vel)


def i_tek(freq, dur, vel, seed, **kw):
    n = _n(0.20, 0.1)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n).astype(np.float32)
    noise = fft_filter(noise, lo=1600.0, hi=9000.0)
    x = noise * np.exp(-t / 0.038).astype(np.float32)
    click = np.sin(TAU * 310.0 * t) * np.exp(-t / 0.02).astype(np.float32)
    x = x + 0.35 * click
    x *= 1.0 - np.exp(-t / 0.0008)
    return _finish(x, 0.42, vel)


def i_shaker(freq, dur, vel, seed, **kw):
    n = _n(0.16, 0.08)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n).astype(np.float32)
    noise = fft_filter(noise, lo=3800.0, hi=13000.0)
    grain = 0.55 + 0.45 * np.sin(TAU * 42.0 * t + rng.random() * TAU)
    shape = (1.0 - np.exp(-t / 0.008)) * np.exp(-t / 0.06)
    x = noise * grain * shape
    return _finish(x, 0.22, vel)


INSTRUMENTS = {
    "kalimba": i_kalimba,
    "musicbox": i_musicbox,
    "celesta": i_celesta,
    "piano": i_piano,
    "strings": i_strings,
    "choir": i_choir,
    "pad": i_pad,
    "flute": i_flute,
    "harp": i_harp,
    "guzheng": i_guzheng,
    "oud": i_oud,
    "bell": i_bell,
    "glass": i_glass,
    "shimmer": i_shimmer,
    "bass": i_bass,
    "sub": i_sub,
    "dum": i_dum,
    "tek": i_tek,
    "shaker": i_shaker,
}
