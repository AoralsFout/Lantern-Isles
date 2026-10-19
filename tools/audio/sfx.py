#!/usr/bin/env python3
"""Short, clean mono SFX for Lantern Isles.

Footsteps (grass / sand / snow / stone), movement, UI, dialogue ticks and the
large story stings (memory unlock, beacon ignition, chapter complete, gate).
Everything is synthesised from noise, sines, FM bells and Karplus-Strong
strings; no samples are used.  Final files are 44.1 kHz 16-bit PCM WAV.
"""
from __future__ import annotations

import math

import numpy as np

from instruments import i_bell, i_glass, i_kalimba, i_piano, i_strings
from synth import (
    SR, TAU, env_perc, fade_edges, fft_filter, fm_bell, midi_to_hz,
    normalize, note_to_midi, shaped_noise, write_wav,
)


def _n(dur: float) -> int:
    return max(8, int(round(dur * SR)))


def _noise(n: int, seed: int, lo: float, hi: float, slope: float = 1.5) -> np.ndarray:
    g = lambda f: 1.0 / np.sqrt((1.0 + (f / hi) ** (2 * slope)) *
                                (1.0 + (lo / np.maximum(f, 1.0)) ** (2 * slope)))
    return shaped_noise(n, seed, g, ch=1)[:, 0]


def _sine(freq, n: int, phase: float = 0.0) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / SR
    return np.sin(TAU * freq * t + phase).astype(np.float32)


def _env(n: int, attack: float, tau: float, power: float = 1.0) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / SR
    a = np.clip(t / max(attack, 1e-4), 0.0, 1.0) ** power
    return (a * np.exp(-t / max(tau, 1e-4))).astype(np.float32)


def finish(x: np.ndarray, dur: float, peak_db: float = -4.0,
           fade_in: float = 2.0, fade_out: float = 8.0) -> np.ndarray:
    n = _n(dur)
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    if len(x) < n:
        x = np.pad(x, (0, n - len(x)))
    x = x[:n]
    x = x - np.mean(x)
    x = fft_filter(x, lo=30.0, hi=18000.0)
    x = fade_edges(x, fade_in, fade_out)
    x = x - np.mean(x)
    p = float(np.max(np.abs(x)))
    if p < 1e-9:
        return np.zeros(n, dtype=np.float32)
    return (x * (10.0 ** (peak_db / 20.0) / p)).astype(np.float32)


# --------------------------------------------------------------------------
# footsteps
# --------------------------------------------------------------------------
def step_grass(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    dur = float(rng.uniform(0.20, 0.30))
    n = _n(dur)
    t = np.arange(n, dtype=np.float32) / SR
    nz = _noise(n, seed, 380.0, 5200.0, 1.4)
    env = _env(n, 0.003, 0.065)
    thump = np.sin(TAU * (72.0 + 26.0 * np.exp(-t / 0.03)) * t) * np.exp(-t / 0.045)
    x = 0.85 * nz * env + 0.22 * thump
    return finish(x, dur, fade_in=1.5, fade_out=15.0)


def step_sand(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    dur = float(rng.uniform(0.21, 0.30))
    n = _n(dur)
    t = np.arange(n, dtype=np.float32) / SR
    nz = _noise(n, seed + 2, 900.0, 7200.0, 1.2)
    grain = 0.55 + 0.45 * (0.5 + 0.5 * np.sin(TAU * rng.uniform(120.0, 200.0) * t))
    env = _env(n, 0.005, 0.085)
    thump = np.sin(TAU * 88.0 * t) * np.exp(-t / 0.04)
    x = 0.8 * nz * grain * env + 0.14 * thump
    return finish(x, dur, fade_in=1.5, fade_out=20.0)


def step_snow(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    dur = float(rng.uniform(0.22, 0.32))
    n = _n(dur)
    t = np.arange(n, dtype=np.float32) / SR
    nz = _noise(n, seed + 4, 220.0, 3600.0, 1.6)
    crunch = 0.55 + 0.45 * (0.5 + 0.5 * np.sin(TAU * rng.uniform(45.0, 80.0) * t + 0.7))
    env = _env(n, 0.004, 0.12)
    thump = np.sin(TAU * 62.0 * t) * np.exp(-t / 0.05)
    x = 0.9 * nz * crunch * env + 0.18 * thump
    return finish(x, dur, fade_in=1.5, fade_out=20.0)


def step_stone(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    dur = float(rng.uniform(0.18, 0.25))
    n = _n(dur)
    t = np.arange(n, dtype=np.float32) / SR
    click = _noise(n, seed + 6, 1100.0, 10000.0, 1.0) * np.exp(-t / 0.018)
    ring = (0.8 * np.sin(TAU * 190.0 * t) * np.exp(-t / 0.10)
            + 0.45 * np.sin(TAU * 415.0 * t + 0.4) * np.exp(-t / 0.06)
            + 0.25 * np.sin(TAU * 760.0 * t + 1.2) * np.exp(-t / 0.04))
    x = 0.55 * click + 0.50 * ring
    return finish(x, dur, fade_in=0.8, fade_out=10.0)


# --------------------------------------------------------------------------
# movement
# --------------------------------------------------------------------------
def jump() -> np.ndarray:
    dur = 0.55
    n = _n(dur)
    t = np.arange(n, dtype=np.float32) / SR
    nz = _noise(n, 501, 350.0, 5000.0, 1.2)
    env = np.clip(t / 0.10, 0, 1) * np.exp(-np.maximum(t - 0.10, 0) / 0.17)
    sweep = np.sin(TAU * np.cumsum(170.0 + 700.0 * np.clip(t / 0.22, 0, 1) ** 1.5) / SR)
    sweep *= np.exp(-t / 0.13) * 0.35
    x = 0.7 * nz * env + sweep
    return finish(x, dur, fade_in=3.0, fade_out=25.0)


def land() -> np.ndarray:
    dur = 0.42
    n = _n(dur)
    t = np.arange(n, dtype=np.float32) / SR
    f = 62.0 + 55.0 * np.exp(-t / 0.035)
    thump = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-t / 0.12)
    nz = _noise(n, 502, 160.0, 1800.0, 1.4) * np.exp(-t / 0.055)
    x = 0.9 * thump + 0.35 * nz
    return finish(x, dur, fade_in=1.5, fade_out=30.0)


def splash() -> np.ndarray:
    dur = 0.75
    n = _n(dur)
    t = np.arange(n, dtype=np.float32) / SR
    nz = _noise(n, 503, 350.0, 10000.0, 1.1)
    env = _env(n, 0.004, 0.22)
    low = np.sin(TAU * 115.0 * t) * np.exp(-t / 0.09)
    x = 0.8 * nz * env + 0.25 * low
    rng = np.random.default_rng(5031)
    for i in range(9):
        t0 = float(rng.uniform(0.02, 0.5))
        blen = _n(0.06)
        bt = np.arange(blen, dtype=np.float32) / SR
        bf = rng.uniform(500.0, 1500.0) + 900.0 * (bt / 0.06)
        b = np.sin(TAU * np.cumsum(bf) / SR) * np.sin(np.pi * bt / 0.06) ** 2
        a = int(t0 * SR)
        m = min(blen, n - a)
        if m > 0:
            x[a:a + m] += 0.18 * b[:m]
    return finish(x, dur, fade_in=1.0, fade_out=35.0)


# --------------------------------------------------------------------------
# pickups / memory / beacon / chapter / gate
# --------------------------------------------------------------------------
def pickup_ember() -> np.ndarray:
    dur = 0.60
    n = _n(dur)
    out = np.zeros(n, dtype=np.float32)
    notes = [1174.66, 1479.98, 1760.0, 2349.32]
    for i, f in enumerate(notes):
        nlen = _n(0.45)
        t = np.arange(nlen, dtype=np.float32) / SR
        x = (np.sin(TAU * f * t) + 0.30 * np.sin(TAU * f * 2.01 * t)
             + 0.12 * np.sin(TAU * f * 3.99 * t))
        x *= np.exp(-t / 0.18) * (1.0 - np.exp(-t / 0.002))
        a = int(0.055 * i * SR)
        m = min(nlen, n - a)
        out[a:a + m] += (0.8 ** i) * x[:m].astype(np.float32)
    return finish(out, dur, peak_db=-5.0, fade_in=1.0, fade_out=20.0)


def memory_unlock() -> np.ndarray:
    dur = 1.60
    n = _n(dur)
    out = np.zeros(n, dtype=np.float32)
    for i, note in enumerate(("D3", "F#3", "A3", "C#4", "E4")):
        s = i_strings(midi_to_hz(note_to_midi(note)), 0.9, 0.30, 7700 + i,
                      attack=0.22, release=0.55, harmonics=9, cutoff=2800)
        m = min(len(s), n)
        out[:m] += s[:m]
    g = i_glass(midi_to_hz(note_to_midi("D6")), 0.8, 0.35, 7711)
    out[: min(len(g), n)] += g[: min(len(g), n)] * 0.6
    g = i_glass(midi_to_hz(note_to_midi("A5")), 0.8, 0.25, 7712)
    a = int(0.11 * SR)
    m = min(len(g), n - a)
    out[a:a + m] += g[:m] * 0.45
    return finish(out, dur, peak_db=-4.0, fade_in=2.0, fade_out=60.0)


def beacon_ignite() -> np.ndarray:
    dur = 4.0
    n = _n(dur)
    out = np.zeros(n, dtype=np.float32)
    t = np.arange(n, dtype=np.float32) / SR
    # fire crackle grows, then settles into a glow
    nz = _noise(n, 1201, 700.0, 14000.0, 1.2)
    flare = np.clip(t / 2.6, 0, 1) ** 2 * np.exp(-np.maximum(t - 2.6, 0) / 0.7)
    out += 0.10 * nz * flare
    rng = np.random.default_rng(1202)
    for i in range(110):
        pos = float(rng.uniform(0.0, 3.6))
        amp = float(rng.uniform(0.01, 0.06)) * (0.3 + 0.7 * min(pos / 2.5, 1.0))
        plen = _n(float(rng.uniform(0.002, 0.008)))
        pop = rng.standard_normal(plen).astype(np.float32) * np.exp(
            -np.arange(plen, dtype=np.float32) / (plen * 0.25))
        a = int(pos * SR)
        m = min(plen, n - a)
        if m > 0:
            out[a:a + m] += amp * pop[:m]
    # harmonic swell: low strings and choir-like pad
    for i, note in enumerate(("D2", "A2", "D3", "F#3", "A3")):
        s = i_strings(midi_to_hz(note_to_midi(note)), 2.9, 0.34, 1210 + i,
                      attack=2.3, release=1.1, harmonics=10, cutoff=2200,
                      detune=6.0)
        m = min(len(s), n)
        out[:m] += s[:m] * 0.55
    # low bell arrival
    b = i_bell(midi_to_hz(note_to_midi("D3")), 2.4, 0.55, 1220, tau=2.2, index=1.8)
    a = int(1.7 * SR)
    m = min(len(b), n - a)
    out[a:a + m] += b[:m] * 0.55
    # final shimmer
    g = i_glass(midi_to_hz(note_to_midi("D6")), 1.2, 0.30, 1230)
    a = int(2.8 * SR)
    m = min(len(g), n - a)
    out[a:a + m] += g[:m] * 0.45
    out += 0.06 * np.sin(TAU * 73.42 * t) * np.clip(t / 2.5, 0, 1) * np.exp(
        -np.maximum(t - 2.5, 0) / 0.8)
    return finish(out, dur, peak_db=-4.0, fade_in=3.0, fade_out=80.0)


def chapter_complete() -> np.ndarray:
    dur = 5.0
    n = _n(dur)
    out = np.zeros(n, dtype=np.float32)
    notes = [(0.00, "D5"), (0.20, "E5"), (0.40, "F#5"), (0.68, "A5")]
    for i, (t0, note) in enumerate(notes):
        g = i_glass(midi_to_hz(note_to_midi(note)), 1.2, 0.55, 1300 + i)
        a = int(t0 * SR)
        m = min(len(g), n - a)
        out[a:a + m] += g[:m]
    # warm pad
    for i, note in enumerate(("D3", "F#3", "A3", "C#4", "E4")):
        s = i_strings(midi_to_hz(note_to_midi(note)), 3.2, 0.30, 1310 + i,
                      attack=1.2, release=1.6, harmonics=9, cutoff=2600)
        a = int(0.35 * SR)
        m = min(len(s), n - a)
        out[a:a + m] += s[:m] * 0.5
    b = i_bell(midi_to_hz(note_to_midi("D3")), 3.0, 0.6, 1320, tau=2.8, index=1.7)
    a = int(1.6 * SR)
    m = min(len(b), n - a)
    out[a:a + m] += b[:m] * 0.65
    p = i_piano(midi_to_hz(note_to_midi("D6")), 2.2, 0.35, 1330)
    a = int(2.2 * SR)
    m = min(len(p), n - a)
    out[a:a + m] += p[:m] * 0.5
    return finish(out, dur, peak_db=-4.0, fade_in=4.0, fade_out=90.0)


def gate_open() -> np.ndarray:
    dur = 2.0
    n = _n(dur)
    t = np.arange(n, dtype=np.float32) / SR
    out = np.zeros(n, dtype=np.float32)
    # stone rumble
    rumble = _noise(n, 1401, 40.0, 300.0, 1.8)
    renv = np.clip(t / 0.3, 0, 1) * np.exp(-np.maximum(t - 0.3, 0) / 0.8)
    out += 0.7 * rumble * renv
    # wooden/stone creak, with a slow wobble
    creak = _noise(n, 1402, 480.0, 1900.0, 2.0)
    wobble = 0.5 + 0.5 * np.sin(TAU * 6.3 * t + 0.4)
    cenv = np.clip(t / 0.15, 0, 1) * np.exp(-np.maximum(t - 0.15, 0) / 0.55)
    out += 0.22 * creak * wobble * cenv
    # stone settling thud
    f = 48.0 + 40.0 * np.exp(-t / 0.03)
    thud = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-np.maximum(t - 0.85, 0) / 0.12)
    thud *= (t >= 0.85).astype(np.float32) * (1.0 - np.exp(-np.maximum(t - 0.85, 0) / 0.010))
    out += 0.9 * thud
    # paper / sliding door hiss
    paper = _noise(n, 1403, 1800.0, 8000.0, 1.0)
    penv = (np.clip((t - 1.0) / 0.25, 0, 1) * np.exp(-np.maximum(t - 1.25, 0) / 0.30))
    penv *= (t >= 1.0).astype(np.float32)
    out += 0.16 * paper * penv
    return finish(out, dur, peak_db=-4.0, fade_in=2.0, fade_out=50.0)


def wind_gust() -> np.ndarray:
    dur = 2.0
    n = _n(dur)
    t = np.arange(n, dtype=np.float32) / SR
    low = _noise(n, 1501, 60.0, 900.0, 1.7)
    high = _noise(n, 1502, 800.0, 7000.0, 1.2)
    env_low = np.sin(np.pi * np.clip(t / 2.0, 0, 1)) ** 0.8
    env_high = np.clip((t - 0.35) / 0.45, 0, 1) * np.exp(-np.maximum(t - 0.8, 0) / 0.55)
    x = 0.8 * low * env_low + 0.45 * high * env_high
    body = np.sin(TAU * 52.0 * t) * env_low * 0.12
    return finish(x + body, dur, peak_db=-4.0, fade_in=20.0, fade_out=60.0)


# --------------------------------------------------------------------------
# UI / dialogue
# --------------------------------------------------------------------------
def _ui_tone(f0: float, f1: float, dur: float, tau: float, seed: int,
             peak_db: float, harmonic: float = 0.18) -> np.ndarray:
    n = _n(dur)
    t = np.arange(n, dtype=np.float32) / SR
    f = f0 + (f1 - f0) * np.clip(t / dur, 0, 1)
    ph = TAU * np.cumsum(f) / SR
    env = (1.0 - np.exp(-t / 0.003)) * np.exp(-t / tau)
    x = (np.sin(ph) + harmonic * np.sin(2.0 * ph + 0.5)).astype(np.float32) * env
    nz = _noise(n, seed, 1800.0, 9000.0, 1.0) * np.exp(-t / 0.004) * 0.04
    return finish(x + nz, dur, peak_db=peak_db, fade_in=1.0, fade_out=5.0)


def ui_hover() -> np.ndarray:
    return _ui_tone(1180.0, 1220.0, 0.09, 0.035, 1601, -10.0, 0.10)


def ui_click() -> np.ndarray:
    return _ui_tone(860.0, 620.0, 0.10, 0.045, 1602, -7.5, 0.22)


def ui_back() -> np.ndarray:
    return _ui_tone(720.0, 430.0, 0.14, 0.060, 1603, -8.5, 0.16)


def ui_error() -> np.ndarray:
    dur = 0.28
    n = _n(dur)
    t = np.arange(n, dtype=np.float32) / SR
    env = (1.0 - np.exp(-t / 0.01)) * np.exp(-t / 0.10)
    x = (np.sin(TAU * 196.0 * t) + 0.7 * np.sin(TAU * 185.0 * t + 0.3)
         + 0.12 * np.sin(TAU * 392.0 * t)) * env
    x = fft_filter(x, hi=1400.0)
    return finish(x, dur, peak_db=-9.0, fade_in=2.0, fade_out=12.0)


def dialogue() -> np.ndarray:
    n = _n(0.08)
    t = np.arange(n, dtype=np.float32) / SR
    f = 950.0 - 220.0 * (t / 0.08)
    ph = TAU * np.cumsum(f) / SR
    env = (1.0 - np.exp(-t / 0.002)) * np.exp(-t / 0.020)
    x = (np.sin(ph) + 0.15 * np.sin(2.0 * ph)) * env
    return finish(x, 0.08, peak_db=-11.0, fade_in=0.8, fade_out=3.0)


# --------------------------------------------------------------------------
# registry / writer
# --------------------------------------------------------------------------
SFX = {
    # footsteps
    "step_grass_1": ("footstep_grass", lambda: step_grass(2001)),
    "step_grass_2": ("footstep_grass", lambda: step_grass(2002)),
    "step_grass_3": ("footstep_grass", lambda: step_grass(2003)),
    "step_grass_4": ("footstep_grass", lambda: step_grass(2004)),
    "step_sand_1": ("footstep_sand", lambda: step_sand(2011)),
    "step_sand_2": ("footstep_sand", lambda: step_sand(2012)),
    "step_sand_3": ("footstep_sand", lambda: step_sand(2013)),
    "step_sand_4": ("footstep_sand", lambda: step_sand(2014)),
    "step_snow_1": ("footstep_snow", lambda: step_snow(2021)),
    "step_snow_2": ("footstep_snow", lambda: step_snow(2022)),
    "step_snow_3": ("footstep_snow", lambda: step_snow(2023)),
    "step_snow_4": ("footstep_snow", lambda: step_snow(2024)),
    "step_stone_1": ("footstep_stone", lambda: step_stone(2031)),
    "step_stone_2": ("footstep_stone", lambda: step_stone(2032)),
    "step_stone_3": ("footstep_stone", lambda: step_stone(2033)),
    "step_stone_4": ("footstep_stone", lambda: step_stone(2034)),
    # movement
    "jump": ("movement", jump),
    "land": ("movement", land),
    "splash": ("movement", splash),
    # pickups / memory
    "pickup_ember": ("pickup", pickup_ember),
    "memory_unlock": ("memory", memory_unlock),
    "beacon_ignite": ("beacon", beacon_ignite),
    # ui / dialogue
    "ui_hover": ("ui", ui_hover),
    "ui_click": ("ui", ui_click),
    "ui_back": ("ui", ui_back),
    "ui_error": ("ui", ui_error),
    "dialogue": ("dialogue", dialogue),
    # story
    "chapter_complete": ("chapter", chapter_complete),
    "gate_open": ("gate", gate_open),
    "wind_gust": ("wind", wind_gust),
}


def build_all(out_dir) -> dict:
    from pathlib import Path
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    for sid, (category, fn) in SFX.items():
        x = fn()
        path = out / f"{sid}.wav"
        write_wav(path, x, fmt="s16")
        results[sid] = dict(category=category, path=path, samples=len(x))
        print(f"sfx {sid:16s} {len(x)/SR:.3f}s cat={category}", flush=True)
    return results


if __name__ == "__main__":
    from pathlib import Path
    build_all(Path(__file__).parent / "_build" / "sfx")
