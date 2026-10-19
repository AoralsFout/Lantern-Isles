#!/usr/bin/env python3
"""Four seamless environment beds, synthesised from shaped noise + events.

Each bed is 65 s, rendered from -2 s to 67 s, then equal-power crossfaded into a
65 s loop.  Continuous layers are spectrally shaped noise with slow, breathing
modulation; discrete events (birds, ice, bells, grains, insects) are generated
per event and wrapped around the loop point, with reverb sends for distance.
"""
from __future__ import annotations

import math

import numpy as np

from synth import (
    SR, TAU, amp_to_db, convolve_reverb, crossfade_loop, db_to_amp, env_perc,
    fade_edges, fft_filter, fm_bell, make_reverb_ir, master, peak,
    shaped_noise, SR as _SR,
)


def pan_gains(pan: float) -> tuple[float, float]:
    p = 0.5 * (float(np.clip(pan, -1.0, 1.0)) + 1.0)
    return math.cos(p * math.pi / 2.0), math.sin(p * math.pi / 2.0)


def band_gain(lo: float, hi: float, slope: float = 2.0, peak_at: float = 0.0,
              peak_width: float = 0.4, peak_boost: float = 0.0):
    def g(f):
        f = np.maximum(f, 1.0)
        out = 1.0 / np.sqrt((1.0 + (f / hi) ** (2.0 * slope)) *
                            (1.0 + (lo / f) ** (2.0 * slope)))
        if peak_boost > 0.0 and peak_at > 0.0:
            out = out * (1.0 + peak_boost * np.exp(
                -((np.log(f / peak_at)) / peak_width) ** 2))
        return out
    return g


def slow_mod(n: int, seed: int, rates, depth: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float32) / SR
    m = np.ones(n, dtype=np.float32)
    for rate in rates:
        ph = rng.random() * TAU
        m *= ((1.0 - depth) + depth * (0.5 + 0.5 * np.sin(TAU * rate * t + ph))).astype(np.float32)
    return m


class Ambience:
    def __init__(self, sid: str, duration: float = 65.0, seed: int = 0,
                 xfade: float = 2.0):
        self.sid = sid
        self.loop_len = float(duration)
        self.xfade = float(xfade)
        self.n = int(round((self.loop_len + 2.0 * self.xfade) * SR))
        self.buf = np.zeros((self.n, 2), dtype=np.float32)
        self.send = np.zeros((self.n, 2), dtype=np.float32)
        self.rng = np.random.default_rng(seed)
        self.ir = make_reverb_ir(rt60=4.2, predelay=0.032, seed=seed + 31,
                                 low_gain=1.1)
        self.count = 0

    def bed(self, sig: np.ndarray, level: float) -> None:
        sig = np.asarray(sig, dtype=np.float32)
        if sig.ndim == 1:
            sig = np.stack([sig, sig], axis=1)
        if len(sig) < self.n:
            sig = np.pad(sig, ((0, self.n - len(sig)), (0, 0)))
        sig = sig[: self.n]
        from synth import rms
        m = rms(sig)
        if m > 1e-9:
            sig = sig * (level / m)
        self.buf += sig

    def _add(self, sig: np.ndarray, start: int, send: np.ndarray | None = None) -> None:
        if start >= self.n or start + len(sig) <= 0:
            return
        s0 = max(0, -start)
        d0 = max(0, start)
        m = min(len(sig) - s0, self.n - d0)
        if m <= 0:
            return
        self.buf[d0:d0 + m] += sig[s0:s0 + m]
        if send is not None:
            self.send[d0:d0 + m] += send[s0:s0 + m, None]

    def event(self, sig: np.ndarray, t: float, pan: float = 0.0,
              gain: float = 1.0, send: float = 0.3) -> None:
        sig = np.asarray(sig, dtype=np.float32)
        self.count += 1
        gl, gr = pan_gains(pan)
        stereo = np.stack([sig * gl, sig * gr], axis=1) * gain
        wet = (sig * (gain * send)).astype(np.float32)
        for tt in (t, t + self.loop_len, t - self.loop_len):
            start = int(round((tt + self.xfade) * SR))
            self._add(stereo, start, wet)

    def finalize(self, target_rms: float = -23.5) -> np.ndarray:
        wet = convolve_reverb(self.send, self.ir) * 0.62
        mix = self.buf + wet
        loop = crossfade_loop(mix, self.loop_len, self.xfade)
        return master(loop, target_rms=target_rms, ceiling_db=-2.0, hp=20.0)


# --------------------------------------------------------------------------
# event synthesis
# --------------------------------------------------------------------------
def bird_call(seed: int, f0: float = 2400.0, f1: float = 3400.0,
              dur: float = 0.55, chirps: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    out = np.zeros(n, dtype=np.float32)
    pos = 0
    for _ in range(chirps):
        clen = int(rng.uniform(0.055, 0.13) * SR)
        if pos + clen >= n:
            break
        t = np.arange(clen, dtype=np.float32) / SR
        T = clen / SR
        glide = f0 * (f1 / f0) ** (t / T)
        ph = TAU * np.cumsum(glide) / SR
        env = np.sin(np.pi * t / T) ** 2
        x = (np.sin(ph) + 0.25 * np.sin(2.0 * ph + 0.4)).astype(np.float32)
        out[pos:pos + clen] += (x * env).astype(np.float32)
        pos += clen + int(rng.uniform(0.045, 0.12) * SR)
    out = fft_filter(out, lo=1300.0, hi=7200.0)
    return fade_edges(out, 3.0, 8.0)


def bamboo_rustle(seed: int, dur: float = 1.6) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    noise = shaped_noise(n, seed, band_gain(900.0, 9000.0, 1.2), ch=1)[:, 0]
    grain = 0.55 + 0.45 * np.sin(TAU * rng.uniform(9.0, 17.0) * t + rng.random() * TAU)
    grain *= 0.6 + 0.4 * np.sin(TAU * rng.uniform(2.0, 5.0) * t + rng.random() * TAU)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5
    return fade_edges((noise * grain * env).astype(np.float32), 30.0, 60.0)


def grain(seed: int) -> np.ndarray:
    n = int(0.014 * SR)
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n).astype(np.float32)
    x *= np.exp(-np.arange(n) / (0.003 * SR)).astype(np.float32)
    x = fft_filter(x, lo=4500.0, hi=14000.0)
    return fade_edges(x, 0.5, 1.5)


def vulture_call(seed: int) -> np.ndarray:
    n = int(1.5 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    f = 360.0 + 520.0 * np.exp(-t / 0.55)
    ph = TAU * np.cumsum(f) / SR
    x = np.zeros(n, dtype=np.float32)
    for h in range(1, 7):
        x += (np.sin(h * ph + rng.random() * 0.4) / h).astype(np.float32)
    am = 0.65 + 0.35 * np.sin(TAU * 27.0 * t + 0.6)
    noise = shaped_noise(n, seed + 3, band_gain(250.0, 2600.0, 1.0), ch=1)[:, 0]
    env = env_perc(n, attack=0.12, tau=0.45)
    x = (0.55 * x * am + 0.28 * noise) * env
    x = fft_filter(x, lo=180.0, hi=3000.0)
    return fade_edges(x.astype(np.float32), 10.0, 80.0)


def ice_crack(seed: int) -> np.ndarray:
    n = int(0.75 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    imp = rng.standard_normal(n).astype(np.float32) * np.exp(-t / 0.006).astype(np.float32)
    imp = fft_filter(imp, lo=900.0, hi=9000.0)
    ring = np.zeros(n, dtype=np.float32)
    for f, a, tau in ((430.0, 1.0, 0.18), (690.0, 0.55, 0.12),
                      (1180.0, 0.30, 0.08)):
        ring += (a * np.sin(TAU * f * t) * np.exp(-t / tau)).astype(np.float32)
    x = 0.7 * imp + 0.6 * ring
    x = fft_filter(x, lo=200.0, hi=6000.0)
    return fade_edges(x, 2.0, 40.0)


def bubble(seed: int) -> np.ndarray:
    n = int(0.075 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    T = n / SR
    f = 260.0 + 900.0 * (t / T) ** 0.7
    ph = TAU * np.cumsum(f) / SR
    env = np.sin(np.pi * np.clip(t / T, 0, 1)) ** 2
    x = np.sin(ph).astype(np.float32) * env.astype(np.float32)
    return fade_edges(x, 2.0, 8.0)


def insect_chirp(seed: int, dur: float = 1.8, carrier: float = 4300.0) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)
    pulse = (0.5 + 0.5 * np.sin(TAU * rng.uniform(21.0, 29.0) * t + rng.random() * TAU)) ** 6
    trem = 0.6 + 0.4 * np.sin(TAU * rng.uniform(0.6, 1.2) * t + rng.random() * TAU)
    x = np.sin(TAU * carrier * t + 0.25 * np.sin(TAU * 9.0 * t))
    x = (x * pulse * trem).astype(np.float32)
    x = fft_filter(x, lo=2800.0, hi=8000.0)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.7
    return fade_edges((x * env).astype(np.float32), 20.0, 20.0)


def chime(freq: float, seed: int, dur: float = 5.0) -> np.ndarray:
    x = fm_bell(freq, dur, seed, ratio=1.41, index=1.6, tau=2.6,
                mod_tau=0.8, shimmer=0.3, shimmer_ratio=3.97)
    x = fft_filter(x, lo=120.0, hi=9000.0)
    m = np.max(np.abs(x))
    return x if m < 1e-9 else (x / m).astype(np.float32)


# --------------------------------------------------------------------------
# 1. spring
# --------------------------------------------------------------------------
def build_spring() -> Ambience:
    a = Ambience("spring_amb", 65.0, seed=701)
    n = a.n
    rng = a.rng
    t = np.arange(n, dtype=np.float32) / SR
    # breeze
    breeze = shaped_noise(n, 7011, band_gain(55.0, 950.0, 1.8), ch=2)
    breeze *= slow_mod(n, 7012, (0.043, 0.071, 0.019), 0.55)[:, None]
    common = breeze.mean(axis=1, keepdims=True)
    breeze = 0.78 * breeze + 0.22 * common
    a.bed(breeze, 0.032)
    # stream
    stream = shaped_noise(n, 7013, band_gain(240.0, 4800.0, 1.3,
                                            peak_at=900.0, peak_width=0.55,
                                            peak_boost=0.6), ch=2)
    flow = (0.66 + 0.16 * np.sin(TAU * 0.21 * t + 1.1)
            + 0.11 * np.sin(TAU * 0.73 * t + 2.2)
            + 0.07 * np.sin(TAU * 1.91 * t + 0.3))
    stream *= flow[:, None]
    a.bed(stream, 0.028)

    # birds, mostly far away, clustered rather than constant
    scales = [(2400.0, 3300.0), (1900.0, 2700.0), (2900.0, 3900.0),
              (2100.0, 3000.0)]
    for i in range(14):
        t0 = float(rng.uniform(0.0, 64.0))
        f0, f1 = scales[int(rng.integers(0, len(scales)))]
        call = bird_call(7100 + i, f0=f0, f1=f1,
                         dur=float(rng.uniform(0.35, 0.8)),
                         chirps=int(rng.integers(2, 5)))
        a.event(call, t0, pan=float(rng.uniform(-0.85, 0.85)),
                gain=float(rng.uniform(0.30, 0.55)), send=0.75)
    # a near bird once, then answered from the other side
    call = bird_call(7199, f0=2600.0, f1=3600.0, dur=0.75, chirps=4)
    a.event(call, 31.0, pan=-0.45, gain=0.62, send=0.6)
    a.event(call, 33.1, pan=0.55, gain=0.35, send=0.8)

    # bamboo rustle now and then
    for i, (t0, pan, g) in enumerate(((12.5, 0.65, 0.20), (27.8, -0.6, 0.17),
                                      (44.2, 0.5, 0.16), (57.5, -0.55, 0.15))):
        a.event(bamboo_rustle(7200 + i, dur=float(rng.uniform(1.2, 2.0))),
                t0, pan=pan, gain=g, send=0.35)

    # water drips / bubbles from the stream
    for i in range(22):
        t0 = float(rng.uniform(0.0, 64.0))
        a.event(bubble(7300 + i), t0, pan=float(rng.uniform(-0.5, 0.5)),
                gain=float(rng.uniform(0.05, 0.14)), send=0.35)
    return a


# --------------------------------------------------------------------------
# 2. desert
# --------------------------------------------------------------------------
def build_desert() -> Ambience:
    a = Ambience("desert_amb", 65.0, seed=801)
    n = a.n
    rng = a.rng
    t = np.arange(n, dtype=np.float32) / SR
    # dry, hot wind: broad low-mid hiss with a breathy 500 Hz body
    wind = shaped_noise(n, 8011, band_gain(55.0, 1600.0, 1.5,
                                          peak_at=420.0, peak_width=0.7,
                                          peak_boost=0.35), ch=2)
    wind *= slow_mod(n, 8012, (0.031, 0.053, 0.017), 0.65)[:, None]
    common = wind.mean(axis=1, keepdims=True)
    wind = 0.72 * wind + 0.28 * common
    a.bed(wind, 0.050)
    # sand grains, sparse high ticks
    for i in range(240):
        t0 = float(rng.uniform(0.0, 64.5))
        a.event(grain(8100 + i), t0, pan=float(rng.uniform(-0.9, 0.9)),
                gain=float(rng.uniform(0.008, 0.035)), send=0.10)
    # distant wind chimes
    notes = [1174.7, 880.0, 1396.9, 987.8, 1318.5, 1760.0, 1568.0]
    for i in range(7):
        t0 = float(rng.uniform(2.0, 62.0))
        f = notes[i % len(notes)]
        a.event(chime(f, 8200 + i, dur=5.0), t0,
                pan=float(rng.uniform(-0.7, 0.7)),
                gain=float(rng.uniform(0.10, 0.18)), send=0.9)
    # two very distant vultures
    a.event(vulture_call(8301), 17.5, pan=-0.55, gain=0.20, send=0.85)
    a.event(vulture_call(8302), 45.0, pan=0.65, gain=0.14, send=0.9)
    return a


# --------------------------------------------------------------------------
# 3. winter
# --------------------------------------------------------------------------
def build_winter() -> Ambience:
    a = Ambience("winter_amb", 65.0, seed=901)
    n = a.n
    rng = a.rng
    t = np.arange(n, dtype=np.float32) / SR
    # snowfield wind
    wind = shaped_noise(n, 9011, band_gain(32.0, 700.0, 1.9,
                                          peak_at=180.0, peak_width=0.8,
                                          peak_boost=0.25), ch=2)
    wind *= slow_mod(n, 9012, (0.027, 0.046, 0.013), 0.6)[:, None]
    common = wind.mean(axis=1, keepdims=True)
    wind = 0.75 * wind + 0.25 * common
    a.bed(wind, 0.050)
    # thin whistling through a gap
    whistle = shaped_noise(n, 9013, band_gain(760.0, 1500.0, 3.0,
                                             peak_at=1080.0, peak_width=0.12,
                                             peak_boost=1.4), ch=2)
    whistle *= slow_mod(n, 9014, (0.037, 0.061), 0.8)[:, None]
    a.bed(whistle, 0.006)
    # ice cracks
    for i, (t0, pan, g) in enumerate(((8.5, 0.5, 0.25), (24.0, -0.6, 0.22),
                                      (39.5, 0.35, 0.20), (53.0, -0.45, 0.24),
                                      (61.0, 0.6, 0.18))):
        a.event(ice_crack(9100 + i), t0, pan=pan, gain=g, send=0.55)
    # distant bells across the valley
    for i, (t0, f, g) in enumerate(((4.0, 220.0, 0.16), (21.0, 329.6, 0.12),
                                    (47.0, 293.7, 0.13), (63.0, 220.0, 0.10))):
        a.event(chime(f, 9200 + i, dur=7.0), t0, pan=float(rng.uniform(-0.5, 0.5)),
                gain=g, send=0.95)
    # hot spring bubbles, in three little clusters
    for c, t0 in enumerate((14.0, 35.0, 55.0)):
        for i in range(9):
            a.event(bubble(9300 + c * 10 + i), t0 + float(rng.uniform(0.0, 2.5)),
                    pan=float(rng.uniform(-0.35, 0.35)),
                    gain=float(rng.uniform(0.05, 0.12)), send=0.4)
    return a


# --------------------------------------------------------------------------
# 4. night
# --------------------------------------------------------------------------
def build_night() -> Ambience:
    a = Ambience("night_amb", 65.0, seed=1001)
    n = a.n
    rng = a.rng
    t = np.arange(n, dtype=np.float32) / SR
    # high air
    air = shaped_noise(n, 10011, band_gain(120.0, 3200.0, 1.6,
                                          peak_at=900.0, peak_width=0.9,
                                          peak_boost=0.3), ch=2)
    air *= slow_mod(n, 10012, (0.023, 0.041, 0.015), 0.55)[:, None]
    common = air.mean(axis=1, keepdims=True)
    air = 0.74 * air + 0.26 * common
    a.bed(air, 0.030)
    # very low drone, slowly breathing
    drone = (0.5 * np.sin(TAU * 36.708 * t + 0.4)
             + 0.3 * np.sin(TAU * 55.0 * t + 1.7)
             + 0.2 * np.sin(TAU * 73.416 * t + 0.2)).astype(np.float32)
    drone *= (0.7 + 0.3 * np.sin(TAU * 0.021 * t + 0.9)).astype(np.float32)
    a.bed(np.stack([drone, drone * 0.97], axis=1), 0.017)
    # starry high grains
    stars = [1174.7, 1396.9, 1760.0, 2349.3, 2793.8, 3520.0]
    for i in range(26):
        t0 = float(rng.uniform(0.0, 64.5))
        f = stars[int(rng.integers(0, len(stars)))]
        a.event(chime(f, 10100 + i, dur=3.5), t0,
                pan=float(rng.uniform(-0.9, 0.9)),
                gain=float(rng.uniform(0.035, 0.085)), send=0.95)
    # night insects
    for i, (t0, pan, g) in enumerate(((9.0, 0.55, 0.028), (28.0, -0.6, 0.024),
                                      (46.0, 0.4, 0.022), (60.0, -0.45, 0.020))):
        a.event(insect_chirp(10200 + i, dur=float(rng.uniform(1.4, 2.4))),
                t0, pan=pan, gain=g, send=0.5)
    return a


BUILDERS = {
    "spring_amb": build_spring,
    "desert_amb": build_desert,
    "winter_amb": build_winter,
    "night_amb": build_night,
}


def build(sid: str) -> Ambience:
    return BUILDERS[sid]()
