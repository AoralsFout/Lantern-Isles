#!/usr/bin/env python3
"""The six music cues of Lantern Isles, composed and rendered from scratch.

Each cue has a written chord progression, bass line, melody (a recurring
pentatonic theme for the title / ending), intro-A-B-A'-outro form, humanised
timing and velocity, reverb sends, and a 2 s equal-power loop crossfade.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from instruments import INSTRUMENTS
from synth import (
    PI, SR, TAU, amp_to_db, convolve_reverb, crossfade_loop, hz, make_reverb_ir,
    master, midi_to_hz, note_to_midi, peak, rms, shaped_noise,
)


# --------------------------------------------------------------------------
# harmony dictionary: pad voicing, bass root, arpeggio tones
# --------------------------------------------------------------------------
CHORDS = {
    # --- D major / pentatonic world -------------------------------------
    "Dmaj9":  dict(pad=["D3", "F#3", "A3", "C#4", "E4"], bass="D2", arp=["D4", "F#4", "A4", "E5"]),
    "Bm7":    dict(pad=["B2", "F#3", "A3", "D4"],          bass="B1", arp=["B3", "D4", "F#4", "A4"]),
    "Gmaj9":  dict(pad=["G2", "D3", "F#3", "A3", "B3"],    bass="G1", arp=["G3", "B3", "D4", "A4"]),
    "Asus4":  dict(pad=["A2", "E3", "A3", "D4"],           bass="A1", arp=["A3", "D4", "E4", "A4"]),
    "F#m7":   dict(pad=["F#2", "C#3", "E3", "A3"],         bass="F#1", arp=["F#3", "A3", "C#4", "E4"]),
    "Em9":    dict(pad=["E2", "B2", "D3", "F#3", "G3"],    bass="E2", arp=["E3", "G3", "B3", "D4"]),
    "D5":     dict(pad=["D3", "A3", "D4", "E4"],           bass="D2", arp=["D4", "A4", "D5", "E5"]),
    "F#m":    dict(pad=["F#2", "C#3", "E3", "A3"],         bass="F#1", arp=["F#3", "A3", "C#4", "E4"]),
    "Asus2":  dict(pad=["A2", "E3", "B3", "E4"],           bass="A1", arp=["A3", "B3", "E4", "A4"]),
    "Dadd9":  dict(pad=["D3", "F#3", "A3", "E4"],          bass="D2", arp=["D4", "F#4", "A4", "E5"]),
    "Gmaj7":  dict(pad=["G2", "D3", "F#3", "B3"],          bass="G1", arp=["G3", "B3", "D4", "F#4"]),
    # --- D Phrygian dominant (desert) ----------------------------------
    "Dm":     dict(pad=["D3", "A3", "D4", "F#4"],          bass="D2", arp=["D4", "A4", "D5", "F#4"]),
    "Ebsus":  dict(pad=["Eb3", "Bb3", "Eb4", "G4"],        bass="Eb2", arp=["Eb4", "Bb4", "Eb5", "G4"]),
    "Csus":   dict(pad=["C3", "G3", "C4"],                 bass="C2", arp=["C4", "G4", "C5", "G4"]),
    "Bb":     dict(pad=["Bb2", "F3", "Bb3", "D4"],         bass="Bb1", arp=["Bb3", "D4", "F4", "Bb4"]),
    "Gm":     dict(pad=["G2", "D3", "G3", "Bb3"],          bass="G1", arp=["G3", "Bb3", "D4", "G4"]),
    "Am":     dict(pad=["A2", "E3", "A3", "C4"],           bass="A1", arp=["A3", "C4", "E4", "A4"]),
    # --- A minor (winter) ----------------------------------------------
    "Am9":    dict(pad=["A2", "E3", "B3", "C4", "E4"],     bass="A1", arp=["A3", "C4", "E4", "B4"]),
    "Fmaj7":  dict(pad=["F2", "C3", "E3", "A3"],           bass="F1", arp=["F3", "A3", "C4", "E4"]),
    "Cmaj9":  dict(pad=["C3", "G3", "D4", "E4"],           bass="C2", arp=["C4", "E4", "G4", "D5"]),
    "Gsus2":  dict(pad=["G2", "D3", "A3", "D4"],           bass="G1", arp=["G3", "A3", "D4", "G4"]),
    "Dm9":    dict(pad=["D3", "A3", "C4", "E4"],           bass="D2", arp=["D4", "F4", "A4", "C5"]),
    "Esus4":  dict(pad=["E2", "B2", "E3", "A3"],           bass="E2", arp=["E3", "A3", "B3", "E4"]),
    # --- D suspended (night) -------------------------------------------
    "Dsus2":  dict(pad=["D3", "A3", "E4"],                 bass="D1", arp=["D4", "A4", "E5", "A5"]),
    "Bbmaj7": dict(pad=["Bb2", "F3", "A3", "D4"],          bass="Bb1", arp=["Bb3", "D4", "F4", "A4"]),
    "Gm9":    dict(pad=["G2", "D3", "Bb3", "F4"],          bass="G1", arp=["G3", "Bb3", "D4", "F4"]),
    "Dsus4":  dict(pad=["D3", "A3", "G4"],                 bass="D1", arp=["D4", "G4", "A4", "D5"]),
    "Asus4n": dict(pad=["A2", "E3", "D4"],                 bass="A1", arp=["A3", "D4", "E4", "A4"]),
}


# --------------------------------------------------------------------------
# session: renders events into a buffer from -xfade .. loop_len + xfade
# --------------------------------------------------------------------------
def pan_gains(pan: float) -> tuple[float, float]:
    p = 0.5 * (float(np.clip(pan, -1.0, 1.0)) + 1.0)
    return math.cos(p * PI / 2.0), math.sin(p * PI / 2.0)


class Session:
    def __init__(self, loop_len: float, xfade: float = 2.0):
        self.loop_len = float(loop_len)
        self.xfade = float(xfade)
        self.n = int(round((self.loop_len + 2.0 * self.xfade) * SR))
        self.dry = np.zeros((self.n, 2), dtype=np.float32)
        self.send = np.zeros((self.n, 2), dtype=np.float32)

    def _add(self, dst: np.ndarray, sig: np.ndarray, start: int, mono: bool = False) -> None:
        if start >= self.n or start + len(sig) <= 0:
            return
        s0 = max(0, -start)
        d0 = max(0, start)
        m = min(len(sig) - s0, self.n - d0)
        if m <= 0:
            return
        frag = sig[s0:s0 + m]
        if mono:
            dst[d0:d0 + m] += frag[:, None]
        else:
            dst[d0:d0 + m] += frag

    def place(self, sig: np.ndarray, t: float, pan: float = 0.0,
              gain: float = 1.0, send: float = 0.25) -> None:
        sig = np.asarray(sig, dtype=np.float32)
        gl, gr = pan_gains(pan)
        stereo = np.stack([sig * gl, sig * gr], axis=1) * gain
        wet = sig * (gain * send)
        for tt in (t, t + self.loop_len, t - self.loop_len):
            start = int(round((tt + self.xfade) * SR))
            self._add(self.dry, stereo, start)
            if send > 0.0:
                self._add(self.send, wet, start, mono=True)

    def mixdown(self, ir: np.ndarray, wet: float = 0.6) -> np.ndarray:
        wet_sig = convolve_reverb(self.send, ir) * wet
        mix = self.dry + wet_sig
        return crossfade_loop(mix, self.loop_len, self.xfade)

    def finalize(self, ir: np.ndarray, target_rms: float,
                 wet: float = 0.6) -> np.ndarray:
        return master(self.mixdown(ir, wet), target_rms=target_rms,
                      ceiling_db=-1.4, hp=24.0)


class Piece:
    """A looping cue with humanised note scheduling."""

    def __init__(self, sid: str, bpm: float, bars: int, seed: int,
                 xfade: float = 2.0):
        self.sid = sid
        self.bpm = float(bpm)
        self.spb = 60.0 / self.bpm
        self.bars = int(bars)
        self.loop_len = self.bars * 4.0 * self.spb
        self.session = Session(self.loop_len, xfade)
        self.rng = np.random.default_rng(seed)
        self.seed = int(seed)
        self.count = 0
        self.ir = make_reverb_ir(rt60=3.4 if bpm < 70 else 3.0,
                                 predelay=0.024, seed=seed + 77)

    def t(self, bar: float, beat: float = 0.0) -> float:
        return (float(bar) * 4.0 + float(beat)) * self.spb

    def play(self, inst: str, bar: float, beat: float, dur_beats: float,
             pitch, vel: float = 0.75, pan: float = 0.0, send: float = 0.25,
             jitter: float = 0.0, **kw):
        self.count += 1
        seed = (self.seed * 1000003 + self.count * 7919 + 13) & 0x7FFFFFFF
        t = self.t(bar, beat)
        if jitter:
            t += float(self.rng.normal() * jitter)
        t = t % self.loop_len
        if isinstance(pitch, str):
            midi = note_to_midi(pitch)
        else:
            midi = int(pitch)
        freq = midi_to_hz(midi + kw.pop("transpose", 0))
        hold = max(0.03, float(dur_beats) * self.spb)
        v = float(np.clip(vel * (1.0 + self.rng.normal() * 0.045), 0.02, 1.0))
        sig = INSTRUMENTS[inst](freq, hold, v, seed, **kw)
        self.session.place(sig, t, pan=pan, gain=1.0, send=send)

    def finish(self, target_rms: float, wet: float = 0.6,
               save_mix: str | None = None) -> np.ndarray:
        mix = self.session.mixdown(self.ir, wet=wet)
        if save_mix:
            from synth import write_wav
            write_wav(save_mix, mix, fmt="f32")
        return master(mix, target_rms=target_rms, ceiling_db=-1.4, hp=24.0)


# --------------------------------------------------------------------------
# part writers
# --------------------------------------------------------------------------
_PAN_SPREAD = (-0.55, 0.45, -0.18, 0.6, 0.05, -0.35)


def pad_chord(p: Piece, bar: float, bars: float, name: str,
              vel: float = 0.45, inst: str = "strings", send: float = 0.42,
              attack: float = 1.2, release: float = 1.8,
              spread=_PAN_SPREAD, octave: int = 0, **kw) -> None:
    tones = CHORDS[name]["pad"]
    for i, note in enumerate(tones):
        pan = spread[i % len(spread)]
        p.play(inst, bar, 0.0, bars * 4.0, note,
               vel * (1.0 - 0.035 * i), pan=pan, send=send,
               jitter=0.02, attack=attack, release=release,
               transpose=12 * octave, **kw)


def bass_bar(p: Piece, bar: float, name: str, vel: float = 0.8,
             style: str = "basic", send: float = 0.10) -> None:
    root = note_to_midi(CHORDS[name]["bass"])
    fifth = root + 7
    p.play("bass", bar, 0.0, 1.8, root, vel, pan=0.0, send=send, jitter=0.006)
    p.play("bass", bar, 2.0, 0.8, fifth, vel * 0.78, pan=0.0, send=send, jitter=0.007)
    if style in ("walk", "octave"):
        p.play("bass", bar, 3.0, 0.85, root + 12, vel * 0.62, pan=0.0, send=send, jitter=0.007)
    if style == "walk":
        p.play("bass", bar, 3.55, 0.4, root + 10, vel * 0.38, pan=-0.1, send=send, jitter=0.008)


def drone(p: Piece, bar: float, bars: float, note: str = "D1",
          vel: float = 0.5, attack: float = 2.5, release: float = 3.0,
          send: float = 0.22) -> None:
    p.play("sub", bar, 0.0, bars * 4.0, note, vel, pan=0.0,
           send=send, attack=attack, release=release)


def arp_bar(p: Piece, bar: float, name: str, pattern, step: float = 0.5,
            vel: float = 0.42, inst: str = "harp", send: float = 0.32,
            pan_alt: float = 0.32, octave: int = 0,
            accents=(0.0, 2.0), jitter: float = 0.004) -> None:
    tones = CHORDS[name]["arp"]
    for i, idx in enumerate(pattern):
        beat = i * step
        if beat >= 3.999:
            break
        note = note_to_midi(tones[idx % len(tones)]) + 12 * octave
        acc = 1.12 if any(abs(beat - a) < 1e-6 for a in accents) else 1.0
        p.play(inst, bar, beat, step * 0.92, note, vel * acc,
               pan=pan_alt if i % 2 else -pan_alt, send=send, jitter=jitter)


def play_notes(p: Piece, bar0: float, notes, inst: str, vel: float = 0.75,
               pan: float = 0.0, send: float = 0.3, jitter: float = 0.009,
               transpose: int = 0, accent: float = 0.05,
               grace: bool = False, grace_vel: float = 0.3,
               **inst_kw) -> None:
    for beat, dur, note in notes:
        b_in_bar = beat % 4.0
        v = vel + (accent if b_in_bar < 1e-6 else 0.0)
        midi = note_to_midi(note) + transpose
        p.play(inst, bar0 + int(beat // 4), b_in_bar, dur, midi, v,
               pan=pan, send=send, jitter=jitter, **inst_kw)
        if grace and b_in_bar > 0.05 and p.rng.random() < 0.32:
            gmidi = midi - (2 if p.rng.random() < 0.5 else 1)
            p.play(inst, bar0 + int(beat // 4), b_in_bar - 0.12, 0.12, gmidi,
                   grace_vel, pan=pan, send=send, jitter=0.003, **inst_kw)


# --------------------------------------------------------------------------
# the theme (D major pentatonic), shared by title & ending
# --------------------------------------------------------------------------
THEME = [
    (0.00, 0.75, "D5"), (0.75, 0.25, "E5"), (1.00, 1.50, "F#5"),
    (2.50, 0.50, "A5"), (3.00, 1.00, "F#5"),
    (4.00, 1.00, "E5"), (5.00, 0.50, "D5"), (5.50, 0.50, "B4"),
    (6.00, 1.50, "D5"), (7.50, 0.50, "E5"),
    (8.00, 0.75, "F#5"), (8.75, 0.25, "E5"), (9.00, 1.00, "D5"),
    (10.00, 0.50, "B4"), (10.50, 1.50, "A4"),
    (12.00, 1.00, "B4"), (13.00, 0.75, "D5"), (13.75, 0.25, "E5"),
    (14.00, 2.00, "D5"),
    (16.00, 0.50, "A5"), (16.50, 0.50, "B5"), (17.00, 1.00, "A5"),
    (18.00, 0.50, "F#5"), (18.50, 0.50, "E5"), (19.00, 1.00, "F#5"),
    (20.00, 0.75, "D5"), (20.75, 0.25, "E5"), (21.00, 1.50, "F#5"),
    (22.50, 0.50, "A5"), (23.00, 1.00, "B5"),
    (24.00, 0.50, "A5"), (24.50, 0.50, "F#5"), (25.00, 1.00, "E5"),
    (26.00, 0.50, "D5"), (26.50, 0.50, "B4"), (27.00, 1.00, "D5"),
    (28.00, 1.00, "E5"), (29.00, 0.50, "F#5"), (29.50, 0.50, "E5"),
    (30.00, 2.00, "D5"),
]

THEME_B = [
    (0.00, 0.50, "B4"), (0.50, 0.50, "D5"), (1.00, 1.50, "F#5"),
    (2.50, 0.50, "E5"), (3.00, 1.00, "D5"),
    (4.00, 1.00, "B4"), (5.00, 1.00, "D5"), (6.00, 2.00, "E5"),
    (8.00, 1.00, "A5"), (9.00, 0.50, "F#5"), (9.50, 0.50, "E5"),
    (10.00, 1.00, "D5"), (11.00, 1.00, "B4"),
    (12.00, 2.00, "A4"), (14.00, 2.00, "D5"),
    (16.00, 0.50, "F#5"), (16.50, 0.50, "A5"), (17.00, 1.50, "B5"),
    (18.50, 0.50, "A5"), (19.00, 1.00, "F#5"),
    (20.00, 0.50, "E5"), (20.50, 0.50, "F#5"), (21.00, 1.00, "A5"),
    (22.00, 1.00, "B5"), (23.00, 1.00, "D6"),
    (24.00, 1.00, "B5"), (25.00, 0.50, "A5"), (25.50, 0.50, "F#5"),
    (26.00, 1.00, "E5"), (27.00, 1.00, "D5"),
    (28.00, 1.00, "E5"), (29.00, 1.00, "F#5"), (30.00, 2.00, "A5"),
]


def play_theme(p: Piece, bar0: float, inst: str, vel: float = 0.7,
               pan: float = 0.0, send: float = 0.3, transpose: int = 0,
               jitter: float = 0.01, **kw) -> None:
    play_notes(p, bar0, THEME, inst, vel=vel, pan=pan, send=send,
               jitter=jitter, transpose=transpose, **kw)


def play_theme_b(p: Piece, bar0: float, inst: str, vel: float = 0.65,
                 pan: float = 0.0, send: float = 0.3, transpose: int = 0,
                 jitter: float = 0.012, **kw) -> None:
    play_notes(p, bar0, THEME_B, inst, vel=vel, pan=pan, send=send,
               jitter=jitter, transpose=transpose, **kw)


# --------------------------------------------------------------------------
# 1. title -- warm, glimmering, a little unresolved (72 BPM, D pentatonic)
# --------------------------------------------------------------------------
def build_title() -> Piece:
    p = Piece("title", bpm=72, bars=36, seed=101)
    prog_a = ["Dmaj9", "Bm7", "Gmaj9", "Asus4", "F#m7", "Bm7", "Em9", "Asus4"]
    prog_b = ["Bm7", "Gmaj9", "Em9", "F#m7", "Gmaj9", "Asus4", "Bm7", "Asus4"]

    # ---- intro (bars 0-7): drone, slowly opening pad, kalimba fragments ----
    drone(p, 0, 8, "D1", vel=0.46, attack=3.0, release=3.0)
    pad_chord(p, 0, 4, "Dmaj9", vel=0.30, attack=2.6, release=2.4)
    pad_chord(p, 4, 2, "Bm7", vel=0.32, attack=2.0, release=2.0)
    pad_chord(p, 6, 1, "Gmaj9", vel=0.34, attack=1.6, release=1.8)
    pad_chord(p, 7, 1, "Asus4", vel=0.36, attack=1.4, release=1.8)
    # sparse picked fragments
    intro_frag = [        (2, 0.0, 0.5, "D5"), (2, 1.5, 0.5, "A4"), (2, 3.0, 0.5, "F#4"),
        (3, 0.5, 0.5, "E5"), (3, 2.0, 0.5, "D5"), (3, 3.5, 0.5, "A4"),
        (4, 0.0, 0.5, "B4"), (4, 1.5, 0.5, "F#4"),
        (5, 0.0, 0.5, "D5"), (5, 2.5, 0.5, "A4"),
        (6, 0.0, 0.5, "B4"), (6, 1.0, 0.5, "D5"),
        (6, 2.0, 0.5, "A4"), (6, 3.0, 0.5, "F#4"),
        (7, 0.0, 0.5, "A4"), (7, 1.5, 0.5, "D5"), (7, 3.0, 1.0, "E5"),
    ]
    for bar, beat, dur, note in intro_frag:
        p.play("kalimba", bar, beat, dur, note, 0.34,
               pan=0.28 if (beat * 2) % 2 == 0 else -0.25, send=0.45, jitter=0.012)
    arp_pattern = [0, 1, 2, 3, 2, 1, 3, 2]
    for bar, chord in ((4, "Bm7"), (5, "Bm7"), (6, "Gmaj9"), (7, "Asus4")):
        arp_bar(p, bar, chord, arp_pattern, step=0.5, vel=0.24,
                inst="kalimba", send=0.4, pan_alt=0.3, jitter=0.007)
    for bar, beat, note, vel in ((3, 2.5, "A5", 0.25), (5, 3.5, "D6", 0.28),
                                 (7, 3.5, "A5", 0.26)):
        p.play("bell", bar, beat, 3.0, note, vel, pan=-0.2, send=0.7, jitter=0.01)

    # ---- A (bars 8-15): the theme, piano + soft kalimba -------------------
    for i, chord in enumerate(prog_a):
        pad_chord(p, 8 + i, 1, chord, vel=0.42, attack=1.1, release=1.6)
        bass_bar(p, 8 + i, chord, vel=0.78, style="basic")
    play_theme(p, 8, "piano", vel=0.72, pan=-0.04, send=0.32)
    play_theme(p, 8, "kalimba", vel=0.36, pan=0.30, send=0.5, jitter=0.014)
    # gentle upper chord tone on each phrase start
    for bar, note in ((8, "A5"), (10, "B5"), (12, "A5")):
        p.play("glass", bar, 0.0, 3.0, note, 0.16, pan=0.42, send=0.75, jitter=0.02)
    p.play("bell", 15, 3.5, 3.0, "D6", 0.30, pan=0.35, send=0.7, jitter=0.01)

    # ---- B (bars 16-23): development, suspended harmony, low pulse -------
    for i, chord in enumerate(prog_b):
        pad_chord(p, 16 + i, 1, chord, vel=0.46, attack=1.3, release=1.8)
        bass_bar(p, 16 + i, chord, vel=0.80, style="walk" if i in (2, 5) else "basic")
    play_theme_b(p, 16, "piano", vel=0.70, pan=0.05, send=0.34)
    play_theme_b(p, 16, "kalimba", vel=0.30, pan=-0.32, send=0.5, jitter=0.016)
    for bar, beat in ((16, 0.0), (20, 0.0), (22, 2.0), (23, 0.0)):
        p.play("dum", bar, beat, 1.0, 60, 0.22, pan=0.0, send=0.35, jitter=0.008)
    # long upper line, a held breath above the development
    for bar, note, vel in ((17, "D6", 0.13), (21, "E6", 0.12)):
        p.play("glass", bar, 1.0, 5.0, note, vel, pan=-0.45, send=0.85, jitter=0.02)

    # ---- A' (bars 24-31): theme returns, richer, bell doubling -----------
    for i, chord in enumerate(prog_a):
        pad_chord(p, 24 + i, 1, chord, vel=0.48, attack=1.0, release=1.7)
        bass_bar(p, 24 + i, chord, vel=0.82, style="octave")
    play_theme(p, 24, "piano", vel=0.78, pan=0.02, send=0.30)
    play_theme(p, 24, "kalimba", vel=0.34, pan=-0.30, send=0.5, jitter=0.013)
    # bell doubling only on the long structural notes
    for bar, beat, note, vel in ((24, 0.0, "A5", 0.26), (26, 0.0, "D6", 0.24),
                                 (28, 0.0, "A5", 0.25), (30, 0.0, "D5", 0.28)):
        p.play("bell", bar, beat, 3.5, note, vel, pan=0.4, send=0.7, jitter=0.012)
    # quiet lower counterline (chord roots/fifths)
    counter = [(24, 0, 2, "A3"), (25, 2, 2, "F#3"), (26, 0, 2, "E3"),
               (27, 2, 2, "D3"), (28, 0, 2, "A3"), (29, 2, 2, "F#3"),
               (30, 0, 2, "E3"), (31, 2, 2, "D3")]
    for bar, beat, dur, note in counter:
        p.play("strings", bar, beat, dur, note, 0.30, pan=-0.35, send=0.5,
               jitter=0.02, attack=0.7, release=1.2, harmonics=8, cutoff=1600)
    p.play("bell", 31, 3.0, 4.0, "A5", 0.26, pan=-0.25, send=0.8, jitter=0.012)

    # ---- outro (bars 32-35): settle on D, leave a light on -----------------
    pad_chord(p, 32, 4, "Dmaj9", vel=0.34, attack=1.8, release=2.6)
    drone(p, 32, 4, "D1", vel=0.40, attack=2.0, release=3.0)
    bass_bar(p, 32, "Dmaj9", vel=0.55, style="basic")
    outro_notes = [(0.0, 2.0, "F#5"), (2.0, 1.0, "E5"), (3.0, 2.0, "D5")]
    for beat, dur, note in outro_notes:
        p.play("piano", 32, beat, dur, note, 0.45, pan=0.0, send=0.4, jitter=0.015)
    p.play("bell", 34, 0.0, 4.0, "D6", 0.28, pan=0.2, send=0.85, jitter=0.01)
    p.play("kalimba", 35, 2.5, 1.0, "A4", 0.24, pan=-0.25, send=0.5, jitter=0.01)
    return p


# --------------------------------------------------------------------------
# shared extra part writers
# --------------------------------------------------------------------------
def noise_bed(p: Piece, level: float, lo: float, hi: float, seed: int,
              rate: float = 0.07, depth: float = 0.45, slope: float = 1.2) -> None:
    """Very quiet continuous air/dust layer (RMS `level`, slowly breathing)."""
    n = p.session.n
    t = np.arange(n, dtype=np.float32) / SR
    noise = shaped_noise(
        n, seed,
        lambda f: 1.0 / np.sqrt((1.0 + (f / hi) ** (2 * slope)) *
                                (1.0 + (lo / np.maximum(f, 1.0)) ** (2 * slope))),
        ch=2,
    )
    lfo1 = 0.5 + 0.5 * np.sin(TAU * rate * t + 0.7)
    lfo2 = 0.5 + 0.5 * np.sin(TAU * rate * 0.37 * t + 2.1)
    mod = (1.0 - depth) + depth * (0.65 * lfo1 + 0.35 * lfo2)
    p.session.dry += (noise * (level * mod)[:, None]).astype(np.float32)


def choir_chord(p: Piece, bar: float, bars: float, name: str,
                vel: float = 0.22, tones: int = 3, send: float = 0.55,
                attack: float = 2.0, release: float = 2.6) -> None:
    notes = CHORDS[name]["pad"][:tones]
    spread = (-0.45, 0.35, -0.05, 0.55)
    for i, note in enumerate(notes):
        p.play("choir", bar, 0.0, bars * 4.0, note, vel * (1.0 - 0.05 * i),
               pan=spread[i % len(spread)], send=send, jitter=0.03,
               attack=attack, release=release)


def long_bass(p: Piece, bar: float, name: str, dur_beats: float = 3.6,
              vel: float = 0.5, fifth: bool = True) -> None:
    root = note_to_midi(CHORDS[name]["bass"])
    p.play("bass", bar, 0.0, dur_beats, root, vel, pan=0.0, send=0.10, jitter=0.008)
    if fifth:
        p.play("bass", bar, 2.5, 1.0, root + 7, vel * 0.58, pan=0.0,
               send=0.10, jitter=0.009)


# --------------------------------------------------------------------------
# 2. spring -- Mossgarden, waking up (64 BPM, D gong pentatonic)
# --------------------------------------------------------------------------
SPRING_A = [
    (0, 0.5, "D5"), (0.5, 0.5, "E5"), (1, 1.0, "F#5"), (2.5, 0.5, "A5"), (3, 1.0, "F#5"),
    (4, 1.0, "E5"), (5, 0.5, "D5"), (5.5, 0.5, "B4"), (6, 1.5, "D5"),
    (8, 0.5, "F#5"), (8.5, 0.5, "A5"), (9, 1.0, "B5"), (10.5, 0.5, "A5"), (11, 1.0, "F#5"),
    (12, 2.0, "D5"),
    (16, 0.5, "A5"), (16.5, 0.5, "B5"), (17, 1.0, "D6"), (18.5, 0.5, "B5"), (19, 1.0, "A5"),
    (20, 1.0, "E5"), (21, 0.5, "F#5"), (21.5, 0.5, "E5"), (22, 2.0, "D5"),
    (24, 0.5, "B4"), (24.5, 0.5, "D5"), (25, 1.0, "F#5"), (26, 1.0, "A5"), (27, 1.0, "F#5"),
    (28, 1.0, "E5"), (29, 1.0, "D5"), (30, 2.0, "D5"),
]

SPRING_B = [
    (0, 0.5, "B5"), (0.5, 0.5, "A5"), (1, 1.0, "F#5"), (2, 0.5, "E5"),
    (2.5, 0.5, "D5"), (3, 1.0, "B4"),
    (4, 0.5, "D5"), (4.5, 0.5, "E5"), (5, 1.0, "F#5"), (6, 2.0, "A5"),
    (8, 1.0, "B5"), (9, 0.5, "D6"), (9.5, 0.5, "B5"), (10, 1.0, "A5"), (11, 1.0, "F#5"),
    (12, 2.0, "E5"), (14, 2.0, "A4"),
    (16, 0.5, "F#5"), (16.5, 0.5, "A5"), (17, 1.5, "B5"), (18.5, 0.5, "A5"), (19, 1.0, "F#5"),
    (20, 1.0, "E5"), (21, 1.0, "F#5"), (22, 1.0, "A5"), (23, 1.0, "B5"),
    (24, 0.5, "D6"), (24.5, 0.5, "B5"), (25, 1.0, "A5"), (26, 1.0, "F#5"), (27, 1.0, "E5"),
    (28, 1.0, "D5"), (29, 1.0, "E5"), (30, 2.0, "A4"),
]

SPRING_A2 = SPRING_A[:-3] + [(28, 1.0, "F#5"), (29, 1.0, "E5"), (30, 2.0, "A4")]


def build_spring() -> Piece:
    p = Piece("spring", bpm=64, bars=34, seed=202)
    prog_a = ["D5", "Bm7", "F#m", "Asus2", "Bm7", "D5", "Asus2", "D5"]
    prog_ap = ["D5", "F#m", "Bm7", "Asus2", "D5", "Bm7", "Asus2", "D5"]
    prog_b = ["Bm7", "Asus2", "D5", "F#m", "Bm7", "D5", "Asus2", "Asus2"]

    # low D/A pedal, in long breathing chunks
    drone(p, 0, 10, "D2", vel=0.20, attack=4.0, release=2.5)
    drone(p, 10, 8, "A2", vel=0.18, attack=4.0, release=2.5)
    drone(p, 18, 8, "D2", vel=0.20, attack=4.0, release=2.5)
    drone(p, 26, 8, "D2", vel=0.20, attack=4.0, release=2.5)

    # ---- intro (bars 0-1) ------------------------------------------------
    pad_chord(p, 0, 2, "D5", vel=0.24, attack=2.4, release=2.2,
              cutoff=2400, harmonics=8)
    for bar, chord in ((0, "D5"), (1, "Bm7")):
        arp_bar(p, bar, chord, [0, 1, 2, 3, 2, 1, 2, 3], step=0.5, vel=0.24,
                inst="harp", send=0.45, pan_alt=0.34)
    p.play("flute", 1, 2.8, 0.5, "A5", 0.15, pan=-0.5, send=0.8, jitter=0.02)
    p.play("bell", 1, 3.5, 2.0, "D6", 0.16, pan=0.3, send=0.85, jitter=0.01)

    sections = [
        (2, prog_a, SPRING_A, "guzheng", 0.64, 0.0, 0.34, False),
        (10, prog_ap, SPRING_A2, "guzheng", 0.66, 0.0, 0.35, True),
        (18, prog_b, SPRING_B, "flute", 0.55, 0.05, 0.42, False),
        (26, prog_ap, SPRING_A, "guzheng", 0.68, -0.02, 0.34, True),
    ]
    for bar0, prog, melody, lead, vel, pan, send, grace in sections:
        for i, chord in enumerate(prog):
            pad_chord(p, bar0 + i, 1, chord, vel=0.29, attack=1.9,
                      release=2.1, cutoff=2200, harmonics=8)
            long_bass(p, bar0 + i, chord, vel=0.50)
        play_notes(p, bar0, melody, lead, vel=vel, pan=pan, send=send,
                   jitter=0.010, grace=grace, grace_vel=0.22)
        # harp shadow an octave below the lead
        play_notes(p, bar0, melody, "harp", vel=0.20, pan=-0.35, send=0.55,
                   jitter=0.013, transpose=-12)
        # arpeggio bed
        for i, chord in enumerate(prog):
            if bar0 == 18:
                pat = [0, 1, 2, 3, 2, 1, 2, 3]
            elif (bar0 + i) in (13, 17, 25, 33):
                pat = [0, 1, 2, 3, 2, 1, 0, 2, 1, 3, 2, 1, 3, 2, 1, 0]
                arp_bar(p, bar0 + i, chord, pat, step=0.25, vel=0.18,
                        inst="harp", send=0.4, pan_alt=0.3)
                continue
            else:
                pat = [0, 1, 2, 3, 2, 1, 2, 3]
            arp_bar(p, bar0 + i, chord, pat, step=0.5, vel=0.21,
                    inst="harp", send=0.4, pan_alt=0.3)

    # bird-like flute ornaments in the gaps
    for bar, beat, note, pan in ((6, 2.6, "D6", -0.5), (9, 3.2, "A5", 0.55),
                                 (15, 1.4, "B5", -0.45), (23, 2.6, "D6", 0.5),
                                 (31, 3.1, "A5", -0.5)):
        p.play("flute", bar, beat, 0.45, note, 0.12, pan=pan, send=0.8, jitter=0.02)
        p.play("flute", bar, beat + 0.24, 0.3, "F#5", 0.08, pan=pan, send=0.8, jitter=0.02)

    # a few high bells / glass points of light
    for bar, beat, note, vel in ((7, 2.5, "D6", 0.18), (17, 3.5, "A5", 0.16),
                                 (25, 2.0, "B5", 0.15), (33, 2.0, "D6", 0.20)):
        p.play("bell", bar, beat, 3.0, note, vel, pan=0.35, send=0.85, jitter=0.015)
    p.play("glass", 13, 1.0, 4.0, "D6", 0.10, pan=-0.45, send=0.9, jitter=0.02)
    p.play("glass", 27, 1.0, 4.0, "B5", 0.10, pan=0.45, send=0.9, jitter=0.02)
    return p


# --------------------------------------------------------------------------
# 3. desert -- Amberreach, the long summer road (72 BPM, D Phrygian dominant)
# --------------------------------------------------------------------------
DESERT_A = [
    (0, 0.75, "D4"), (0.75, 0.25, "Eb4"), (1, 0.5, "D4"), (1.5, 0.5, "A3"),
    (2, 1.0, "Bb3"), (3, 0.5, "A3"), (3.5, 0.5, "G3"),
    (4, 1.0, "F#3"), (5, 0.5, "G3"), (5.5, 0.5, "A3"), (6, 1.5, "D4"),
    (8, 0.5, "D4"), (8.5, 0.5, "Eb4"), (9, 1.0, "F#4"), (10, 0.5, "G4"),
    (10.5, 0.5, "F#4"), (11, 1.0, "Eb4"),
    (12, 1.0, "D4"), (13, 2.0, "A3"),
    (16, 0.5, "Bb3"), (16.5, 0.5, "A3"), (17, 1.0, "G3"), (18, 0.5, "F#3"),
    (18.5, 0.5, "G3"), (19, 1.0, "A3"),
    (20, 1.0, "Bb3"), (21, 0.5, "A3"), (21.5, 0.5, "G3"), (22, 1.0, "F#3"),
    (23, 1.0, "Eb3"),
    (24, 0.5, "D4"), (24.5, 0.5, "Eb4"), (25, 0.5, "F#4"), (25.5, 0.5, "G4"),
    (26, 1.0, "A4"), (27, 1.0, "Bb4"),
    (28, 2.0, "A4"), (30, 2.0, "D4"),
]

DESERT_B = [
    (0, 1.5, "D5"), (1.5, 0.5, "C5"), (2, 1.0, "Bb4"), (3, 1.0, "A4"),
    (4, 1.0, "G4"), (5, 1.0, "F#4"), (6, 2.0, "Eb4"),
    (8, 0.5, "D5"), (8.5, 0.5, "Eb5"), (9, 0.5, "D5"), (9.5, 0.5, "C5"),
    (10, 1.0, "Bb4"), (11, 1.0, "A4"),
    (12, 1.0, "G4"), (13, 1.0, "A4"), (14, 2.0, "D5"),
    (16, 1.0, "G4"), (17, 1.0, "A4"), (18, 1.0, "Bb4"), (19, 1.0, "C5"),
    (20, 1.0, "D5"), (21, 1.0, "C5"), (22, 1.0, "Bb4"), (23, 1.0, "A4"),
    (24, 0.5, "A4"), (24.5, 0.5, "Bb4"), (25, 0.5, "A4"), (25.5, 0.5, "G4"),
    (26, 1.0, "F#4"), (27, 1.0, "Eb4"), (28, 4.0, "D4"),
]


def play_oud_phrase(p: Piece, bar0: float, notes, vel: float = 0.6,
                    pan: float = 0.10, send: float = 0.35) -> None:
    for beat, dur, note in notes:
        p.play("oud", bar0, beat, dur, note, vel, pan=pan, send=send, jitter=0.011)
        if dur >= 1.5:
            k = int((dur - 0.5) / 0.25)
            for j in range(1, k + 1):
                p.play("oud", bar0, beat + j * 0.25, 0.18, note, vel * 0.34,
                       pan=pan, send=send, jitter=0.006)


def desert_drums(p: Piece, bar: float, intensity: float = 1.0,
                 extra: bool = False) -> None:
    p.play("dum", bar, 0.0, 1.0, 58, 0.52 * intensity, pan=0.0, send=0.22, jitter=0.005)
    p.play("dum", bar, 2.5, 0.7, 58, 0.30 * intensity, pan=-0.05, send=0.22, jitter=0.006)
    p.play("tek", bar, 1.5, 0.4, 200, 0.28 * intensity, pan=0.28, send=0.28, jitter=0.005)
    p.play("tek", bar, 3.5, 0.4, 200, 0.26 * intensity, pan=-0.28, send=0.28, jitter=0.006)
    if extra:
        p.play("tek", bar, 0.75, 0.3, 200, 0.16 * intensity, pan=-0.2, send=0.28, jitter=0.005)
        p.play("tek", bar, 2.75, 0.3, 200, 0.15 * intensity, pan=0.2, send=0.28, jitter=0.005)
    for i in range(8):
        v = (0.13 if i % 2 == 0 else 0.085) * intensity
        p.play("shaker", bar, i * 0.5, 0.15, 900, v,
               pan=0.45 if i % 2 else -0.4, send=0.18, jitter=0.004)


def build_desert() -> Piece:
    p = Piece("desert", bpm=72, bars=34, seed=303)
    prog_a = ["Dm", "Ebsus", "Dm", "Csus", "Bb", "Gm", "Ebsus", "Dm"]
    prog_b = ["Bb", "Gm", "Ebsus", "Dm", "Bb", "Csus", "Ebsus", "Dm"]

    noise_bed(p, level=0.010, lo=45.0, hi=900.0, seed=3031, rate=0.045, depth=0.55)
    drone(p, 0, 12, "D1", vel=0.34, attack=5.0, release=3.0)
    drone(p, 12, 11, "D1", vel=0.30, attack=4.0, release=3.0)
    drone(p, 23, 11, "D1", vel=0.34, attack=4.0, release=3.0)

    # ---- intro (bars 0-3) ------------------------------------------------
    choir_chord(p, 0, 4, "Dm", vel=0.16, tones=2, attack=3.0, release=3.0)
    for bar, beat, note, vel in ((1, 1.5, "D4", 0.24), (1, 2.5, "Eb4", 0.22),
                                 (2, 2.0, "A3", 0.20), (3, 3.0, "D4", 0.24)):
        p.play("oud", bar, beat, 1.0, note, vel, pan=0.15, send=0.45, jitter=0.012)
    p.play("dum", 3, 2.0, 1.0, 58, 0.28, pan=0.0, send=0.3, jitter=0.006)
    p.play("bell", 3, 3.5, 3.0, "D5", 0.13, pan=-0.35, send=0.9, jitter=0.012)

    # ---- A (bars 4-11) ----------------------------------------------------
    for i, chord in enumerate(prog_a):
        choir_chord(p, 4 + i, 1, chord, vel=0.18, tones=3, attack=1.8, release=2.2)
        pad_chord(p, 4 + i, 1, chord, vel=0.22, attack=1.4, release=1.8,
                  cutoff=1900, harmonics=8)
        long_bass(p, 4 + i, chord, vel=0.48)
        desert_drums(p, 4 + i, intensity=0.85)
    play_oud_phrase(p, 4, DESERT_A, vel=0.58, pan=0.10, send=0.38)
    # a distant high answer, like a second player on the ridge
    for bar, beat, note, vel in ((7, 3.0, "D5", 0.16), (9, 3.5, "A5", 0.14),
                                 (10, 2.0, "Bb4", 0.15)):
        p.play("bell", bar, beat, 3.5, note, vel, pan=-0.5, send=0.9, jitter=0.015)

    # ---- B (bars 12-19) ---------------------------------------------------
    for i, chord in enumerate(prog_b):
        choir_chord(p, 12 + i, 1, chord, vel=0.20, tones=3, attack=1.6, release=2.0)
        pad_chord(p, 12 + i, 1, chord, vel=0.24, attack=1.2, release=1.8,
                  cutoff=2100, harmonics=9)
        long_bass(p, 12 + i, chord, vel=0.52)
        desert_drums(p, 12 + i, intensity=1.0, extra=True)
    play_oud_phrase(p, 12, DESERT_B, vel=0.62, pan=-0.05, send=0.38)
    p.play("bell", 18, 3.0, 4.0, "D5", 0.16, pan=0.4, send=0.9, jitter=0.012)

    # ---- A' (bars 20-27) --------------------------------------------------
    for i, chord in enumerate(prog_a):
        choir_chord(p, 20 + i, 1, chord, vel=0.20, tones=3, attack=1.5, release=2.2)
        pad_chord(p, 20 + i, 1, chord, vel=0.24, attack=1.3, release=1.8,
                  cutoff=2200, harmonics=9)
        long_bass(p, 20 + i, chord, vel=0.50)
        desert_drums(p, 20 + i, intensity=0.95, extra=True)
    play_oud_phrase(p, 20, DESERT_A, vel=0.62, pan=0.12, send=0.38)
    # second oud voice: sparse octave answers
    for bar, beat, note, vel in ((20, 2.5, "D5", 0.18), (22, 1.0, "A4", 0.16),
                                 (24, 1.5, "D5", 0.18), (26, 2.5, "A4", 0.16)):
        p.play("oud", bar, beat, 0.7, note, vel, pan=-0.45, send=0.55, jitter=0.012)

    # ---- outro (bars 28-33) ----------------------------------------------
    for bar, chord in ((28, "Dm"), (29, "Ebsus"), (30, "Dm"), (31, "Dm"),
                       (32, "Dm"), (33, "Dm")):
        pad_chord(p, bar, 1, chord, vel=0.22, attack=1.6, release=2.4,
                  cutoff=1800, harmonics=8)
        choir_chord(p, bar, 1, chord, vel=0.15, tones=2, attack=2.0, release=2.8)
    drone(p, 28, 6, "D2", vel=0.22, attack=3.0, release=3.0)
    p.play("dum", 28, 0.0, 1.0, 58, 0.25, pan=0.0, send=0.3, jitter=0.006)
    for bar, beat, note, vel in ((28, 2.0, "D4", 0.22), (29, 2.5, "Eb4", 0.20),
                                 (30, 1.5, "A3", 0.18), (31, 3.0, "D4", 0.20),
                                 (32, 2.0, "A3", 0.16), (33, 1.5, "D4", 0.18)):
        p.play("oud", bar, beat, 1.2, note, vel, pan=0.05, send=0.55, jitter=0.014)
    p.play("bell", 33, 2.5, 4.0, "D5", 0.16, pan=-0.3, send=0.9, jitter=0.012)
    return p


# --------------------------------------------------------------------------
# 4. winter -- Frostvale, waiting (56 BPM, A minor add9)
# --------------------------------------------------------------------------
WINTER_A = [
    (0, 2.0, "E5"), (2, 1.0, "C5"), (3, 1.0, "B4"),
    (4, 2.0, "A4"),
    (8, 1.0, "G5"), (9, 1.0, "E5"), (10, 2.0, "D5"),
    (12, 2.0, "C5"),
    (16, 1.0, "D5"), (17, 1.0, "C5"), (18, 2.0, "A4"),
    (20, 3.0, "B4"),
]

WINTER_B = [
    (0, 1.5, "A5"), (1.5, 0.5, "G5"), (2, 1.0, "E5"), (3, 1.0, "F5"),
    (4, 2.0, "C5"), (6, 2.0, "D5"),
    (8, 1.0, "E5"), (9, 1.0, "G5"), (10, 1.0, "F5"), (11, 1.0, "D5"),
    (12, 2.0, "C5"), (14, 2.0, "B4"),
    (16, 1.0, "A4"), (17, 1.0, "E5"), (18, 1.0, "D5"), (19, 1.0, "C5"),
    (20, 4.0, "B4"),
]


def build_winter() -> Piece:
    p = Piece("winter", bpm=56, bars=26, seed=404)
    prog_a = ["Am9", "Fmaj7", "Cmaj9", "Gsus2", "Dm9", "Am9"]
    prog_b = ["Fmaj7", "Cmaj9", "Gsus2", "Dm9", "Fmaj7", "Esus4"]

    noise_bed(p, level=0.008, lo=35.0, hi=700.0, seed=4041, rate=0.035, depth=0.6)
    drone(p, 0, 8, "A1", vel=0.26, attack=5.0, release=3.0)
    drone(p, 8, 7, "E2", vel=0.20, attack=4.0, release=3.0)
    drone(p, 15, 11, "A1", vel=0.24, attack=4.0, release=4.0)

    # distant bells
    for bar, beat, note, vel in ((1, 2.5, "A4", 0.14), (7, 3.0, "E4", 0.12),
                                 (13, 2.0, "D4", 0.12), (20, 3.5, "A4", 0.13),
                                 (25, 1.0, "A5", 0.13)):
        p.play("bell", bar, beat, 6.0, note, vel, pan=-0.35, send=0.9, jitter=0.02,
               tau=3.4, ratio=1.41)

    # ---- intro (bars 0-3) ------------------------------------------------
    pad_chord(p, 0, 4, "Am9", vel=0.22, attack=3.0, release=3.5,
              cutoff=950, harmonics=7)
    p.play("musicbox", 1, 2.0, 2.0, "E5", 0.34, pan=0.15, send=0.55, jitter=0.02)
    p.play("musicbox", 2, 0.0, 2.0, "C5", 0.28, pan=0.1, send=0.55, jitter=0.02)
    p.play("musicbox", 3, 1.0, 3.0, "B4", 0.24, pan=0.0, send=0.6, jitter=0.02)

    # ---- A (bars 4-9) -----------------------------------------------------
    for i, chord in enumerate(prog_a):
        pad_chord(p, 4 + i, 1, chord, vel=0.27, attack=2.4, release=3.0,
                  cutoff=1000, harmonics=7)
        long_bass(p, 4 + i, chord, vel=0.36, fifth=False)
    play_notes(p, 4, WINTER_A, "musicbox", vel=0.46, pan=0.12, send=0.55, jitter=0.018)
    play_notes(p, 4, WINTER_A, "strings", vel=0.16,
               pan=-0.4, send=0.6, jitter=0.02, transpose=-12,
               attack=1.8, release=2.0, harmonics=6, cutoff=900, vibrato=1.2)

    # ---- B (bars 10-15) ---------------------------------------------------
    for i, chord in enumerate(prog_b):
        pad_chord(p, 10 + i, 1, chord, vel=0.30, attack=2.0, release=3.0,
                  cutoff=1100, harmonics=8)
        long_bass(p, 10 + i, chord, vel=0.40, fifth=False)
    play_notes(p, 10, WINTER_B, "celesta", vel=0.44, pan=-0.08, send=0.55, jitter=0.016)
    play_notes(p, 10, WINTER_B, "musicbox", vel=0.18, pan=0.4, send=0.6, jitter=0.02)
    p.play("strings", 10, 0.0, 24.0, "A2", 0.22, pan=0.0, send=0.5,
           jitter=0.02, attack=4.0, release=4.0, harmonics=6, cutoff=700, vibrato=0.8)
    p.play("bell", 15, 3.0, 5.0, "A4", 0.14, pan=0.4, send=0.9, jitter=0.02, tau=3.2)

    # ---- A' (bars 16-21) --------------------------------------------------
    for i, chord in enumerate(prog_a):
        pad_chord(p, 16 + i, 1, chord, vel=0.29, attack=2.2, release=3.0,
                  cutoff=1100, harmonics=8)
        long_bass(p, 16 + i, chord, vel=0.40, fifth=False)
    play_notes(p, 16, WINTER_A, "musicbox", vel=0.48, pan=0.10, send=0.55,
               jitter=0.018, grace=True, grace_vel=0.16)
    play_notes(p, 16, WINTER_A, "celesta", vel=0.18, pan=-0.35, send=0.6,
               jitter=0.02, transpose=-12)
    p.play("glass", 19, 1.0, 4.0, "A5", 0.10, pan=0.45, send=0.95, jitter=0.02)

    # ---- outro (bars 22-25) ----------------------------------------------
    for bar, chord in ((22, "Am9"), (23, "Am9"), (24, "Fmaj7"), (25, "Am9")):
        pad_chord(p, bar, 1, chord, vel=0.24, attack=2.0, release=3.5,
                  cutoff=900, harmonics=7)
        long_bass(p, bar, chord, vel=0.32, fifth=False)
    for beat, dur, note, vel in ((0, 2, "A4", 0.28), (2, 1, "C5", 0.24),
                                 (3, 1, "E5", 0.22)):
        p.play("musicbox", 24, beat, dur, note, vel, pan=0.05, send=0.6, jitter=0.02)
    p.play("bell", 25, 1.0, 6.0, "A5", 0.16, pan=-0.2, send=0.95, jitter=0.015, tau=3.5)
    p.play("musicbox", 25, 2.5, 2.0, "A4", 0.22, pan=0.2, send=0.6, jitter=0.02)
    return p


# --------------------------------------------------------------------------
# 5. night -- Starfall, homecoming (60 BPM, D suspended)
# --------------------------------------------------------------------------
NIGHT_A = [
    (0, 2.0, "D5"), (2, 1.0, "E5"), (3, 1.0, "F5"),
    (4, 2.0, "D5"), (6, 2.0, "A4"),
    (8, 1.5, "Bb4"), (9.5, 0.5, "A4"), (10, 2.0, "G4"),
    (12, 2.0, "A4"), (14, 2.0, "D5"),
    (16, 1.0, "F5"), (17, 1.0, "E5"), (18, 2.0, "D5"),
    (20, 4.0, "E5"),
]

NIGHT_B = [
    (0, 1.5, "G5"), (1.5, 0.5, "F5"), (2, 2.0, "D5"),
    (4, 1.0, "F5"), (5, 1.0, "E5"), (6, 1.0, "D5"), (7, 1.0, "Bb4"),
    (8, 1.0, "A5"), (9, 1.0, "G5"), (10, 2.0, "F5"),
    (12, 2.0, "E5"), (14, 2.0, "A4"),
    (16, 2.0, "D6"), (18, 1.0, "C6"), (19, 1.0, "Bb5"),
    (20, 2.0, "A5"), (22, 2.0, "G5"),
]


def build_night() -> Piece:
    p = Piece("night", bpm=60, bars=28, seed=505)
    prog_a = ["Dsus2", "Bbmaj7", "Gm9", "Dsus4", "Bbmaj7", "Asus4n"]
    prog_b = ["Gm9", "Bbmaj7", "Dsus4", "Asus4n", "Bbmaj7", "Gm9"]

    noise_bed(p, level=0.008, lo=60.0, hi=2400.0, seed=5051, rate=0.03, depth=0.55)

    # deep bass, 2 bars at a time
    for bar, note in ((0, "D1"), (2, "D1"), (4, "D1"), (6, "Bb1"), (8, "G1"),
                      (10, "D1"), (12, "Bb1"), (14, "A1"), (16, "D1"),
                      (18, "D1"), (20, "Bb1"), (22, "G1"), (24, "D1"),
                      (26, "D1")):
        drone(p, bar, 2, note, vel=0.30, attack=2.5, release=3.0)

    # ---- intro (bars 0-3) ------------------------------------------------
    choir_chord(p, 0, 4, "Dsus2", vel=0.22, tones=3, attack=3.5, release=4.0)
    pad_chord(p, 0, 4, "Dsus2", vel=0.18, attack=3.0, release=4.0,
              cutoff=1400, harmonics=8)
    for bar, beat, note, vel in ((1, 1.0, "D5", 0.22), (1, 2.5, "E5", 0.18),
                                 (2, 0.0, "A4", 0.18), (3, 2.0, "D5", 0.20)):
        p.play("glass", bar, beat, 3.0, note, vel, pan=0.25, send=0.8, jitter=0.02)
    p.play("bell", 3, 3.5, 5.0, "A5", 0.14, pan=-0.4, send=0.95, jitter=0.02, tau=3.5)

    # ---- A (bars 4-9) -----------------------------------------------------
    for i, chord in enumerate(prog_a):
        choir_chord(p, 4 + i, 1, chord, vel=0.23, tones=3, attack=2.2, release=2.8)
        pad_chord(p, 4 + i, 1, chord, vel=0.20, attack=1.8, release=2.5,
                  cutoff=1500, harmonics=8)
        long_bass(p, 4 + i, chord, vel=0.30, fifth=False)
    play_notes(p, 4, NIGHT_A, "glass", vel=0.36, pan=0.15, send=0.7, jitter=0.018)
    p.play("bell", 9, 3.0, 5.0, "D5", 0.13, pan=-0.4, send=0.95, jitter=0.02, tau=3.6)

    # ---- B (bars 10-15) ---------------------------------------------------
    for i, chord in enumerate(prog_b):
        choir_chord(p, 10 + i, 1, chord, vel=0.25, tones=3, attack=2.0, release=2.8)
        pad_chord(p, 10 + i, 1, chord, vel=0.22, attack=1.6, release=2.4,
                  cutoff=1700, harmonics=9)
        long_bass(p, 10 + i, chord, vel=0.32, fifth=False)
    play_notes(p, 10, NIGHT_B, "glass", vel=0.40, pan=-0.1, send=0.7, jitter=0.016)
    play_notes(p, 10, NIGHT_B, "bell", vel=0.12, pan=0.4, send=0.9,
               jitter=0.02, transpose=12)
    p.play("choir", 14, 0.0, 8.0, "D4", 0.14, pan=0.0, send=0.75,
           jitter=0.03, attack=3.0, release=3.5)

    # ---- A' (bars 16-21) --------------------------------------------------
    for i, chord in enumerate(prog_a):
        choir_chord(p, 16 + i, 1, chord, vel=0.26, tones=3, attack=1.9, release=3.0)
        pad_chord(p, 16 + i, 1, chord, vel=0.23, attack=1.5, release=2.5,
                  cutoff=1800, harmonics=9)
        long_bass(p, 16 + i, chord, vel=0.34, fifth=False)
    play_notes(p, 16, NIGHT_A, "glass", vel=0.42, pan=0.05, send=0.7, jitter=0.018)
    play_notes(p, 16, NIGHT_A, "choir", vel=0.10, pan=-0.45, send=0.8,
               jitter=0.03, transpose=0, attack=1.2, release=2.0)
    p.play("bell", 17, 2.0, 6.0, "D6", 0.12, pan=0.4, send=0.95, jitter=0.02, tau=4.0)
    p.play("bell", 21, 3.0, 6.0, "A5", 0.14, pan=-0.3, send=0.95, jitter=0.02, tau=4.0)

    # ---- outro (bars 22-27) ----------------------------------------------
    choir_chord(p, 22, 6, "Dsus2", vel=0.20, tones=3, attack=2.5, release=4.0)
    pad_chord(p, 22, 6, "Dsus2", vel=0.17, attack=2.5, release=4.0,
              cutoff=1300, harmonics=8)
    for bar, beat, note, vel in ((23, 2.0, "D6", 0.14), (25, 1.0, "A5", 0.12),
                                 (26, 3.0, "D5", 0.10)):
        p.play("glass", bar, beat, 4.0, note, vel, pan=0.2, send=0.9, jitter=0.025)
    p.play("bell", 27, 1.0, 6.0, "D6", 0.15, pan=-0.25, send=0.95, jitter=0.02, tau=4.2)

    # star dust: very quiet high grains scattered through the whole cue
    rng = np.random.default_rng(5052)
    stars = ["D6", "E6", "F6", "A6", "Bb6", "D7"]
    for _ in range(44):
        bar = float(rng.uniform(0.0, 27.5))
        beat = float(rng.uniform(0.0, 4.0))
        note = stars[int(rng.integers(0, len(stars)))]
        p.play("shimmer", bar, beat, 1.2, note, float(rng.uniform(0.035, 0.09)),
               pan=float(rng.uniform(-0.85, 0.85)), send=0.9, jitter=0.04)
    return p


# --------------------------------------------------------------------------
# 6. ending -- the theme in full light (76 BPM, D major)
# --------------------------------------------------------------------------
def build_ending() -> Piece:
    p = Piece("ending", bpm=76, bars=34, seed=606)
    prog_a = ["Dmaj9", "Bm7", "Gmaj9", "Asus4", "F#m7", "Bm7", "Em9", "Asus4"]
    prog_b = ["Bm7", "Gmaj9", "Em9", "F#m7", "Gmaj9", "Asus4", "Bm7", "Asus4"]

    drone(p, 0, 6, "D1", vel=0.22, attack=4.0, release=3.0)
    drone(p, 6, 10, "D1", vel=0.25, attack=4.0, release=3.0)
    drone(p, 16, 8, "D1", vel=0.28, attack=3.0, release=3.0)
    drone(p, 24, 10, "D1", vel=0.24, attack=3.0, release=4.0)

    # ---- intro (bars 0-3): let the room breathe before the piano speaks ----
    intro_notes = [(0, 2.0, "D5"), (2, 1.0, "E5"), (3, 1.0, "F#5"),
                   (4, 2.0, "A5"), (6, 1.0, "F#5"), (7, 1.0, "E5")]
    play_notes(p, 1, intro_notes, "piano", vel=0.40, pan=0.0, send=0.45, jitter=0.015)
    pad_chord(p, 0, 4, "Dmaj9", vel=0.21, attack=3.0, release=2.8)
    p.play("bell", 3, 3.5, 4.0, "A5", 0.16, pan=0.3, send=0.85, jitter=0.012)
    long_bass(p, 2, "Dmaj9", vel=0.36, fifth=False)

    # ---- A (bars 4-11) ----------------------------------------------------
    for i, chord in enumerate(prog_a):
        pad_chord(p, 4 + i, 1, chord, vel=0.36, attack=1.2, release=1.7)
        long_bass(p, 4 + i, chord, vel=0.62)
    play_theme(p, 4, "piano", vel=0.72, pan=-0.04, send=0.32)
    play_theme(p, 4, "kalimba", vel=0.22, pan=0.30, send=0.5, jitter=0.014)
    p.play("bell", 11, 3.5, 4.0, "D6", 0.24, pan=0.35, send=0.8, jitter=0.012)
    p.play("glass", 8, 1.0, 4.0, "D6", 0.10, pan=-0.4, send=0.9, jitter=0.02)

    # ---- B (bars 12-19) ---------------------------------------------------
    for i, chord in enumerate(prog_b):
        pad_chord(p, 12 + i, 1, chord, vel=0.38, attack=1.2, release=1.8)
        long_bass(p, 12 + i, chord, vel=0.64, fifth=True)
    play_theme_b(p, 12, "strings", vel=0.50, pan=0.04, send=0.42,
                 transpose=-12, jitter=0.012, attack=0.10, release=0.35,
                 harmonics=10, cutoff=4200, vibrato=3.0)
    for i in (0, 2, 4, 6):
        arp_bar(p, 12 + i, prog_b[i], [0, 1, 2, 3, 2, 1, 2, 3], step=0.5,
                vel=0.20, inst="piano", send=0.45, pan_alt=0.25)
    play_theme_b(p, 12, "kalimba", vel=0.16, pan=-0.35, send=0.55, jitter=0.016)
    p.play("bell", 19, 3.0, 4.0, "D6", 0.22, pan=0.4, send=0.85, jitter=0.012)

    # ---- A' (bars 20-27) --------------------------------------------------
    for i, chord in enumerate(prog_a):
        pad_chord(p, 20 + i, 1, chord, vel=0.42, attack=1.0, release=1.8)
        long_bass(p, 20 + i, chord, vel=0.66, fifth=True)
        if i >= 4:
            choir_chord(p, 20 + i, 1, chord, vel=0.10, tones=2,
                        attack=1.5, release=2.2)
    play_theme(p, 20, "piano", vel=0.78, pan=0.0, send=0.30)
    play_theme(p, 20, "strings", vel=0.42, pan=-0.2, send=0.4, transpose=-12,
               jitter=0.014, attack=0.12, release=0.4, harmonics=10,
               cutoff=3800, vibrato=3.0)
    for bar, beat, note, vel in ((20, 0.0, "A5", 0.20), (22, 0.0, "B5", 0.18),
                                 (24, 0.0, "A5", 0.20), (26, 0.0, "D6", 0.18)):
        p.play("bell", bar, beat, 4.0, note, vel, pan=0.42, send=0.8, jitter=0.014)
    counter = [(20, 0, 2, "A3"), (21, 2, 2, "F#3"), (22, 0, 2, "E3"),
               (23, 2, 2, "D3"), (24, 0, 2, "A3"), (25, 2, 2, "F#3"),
               (26, 0, 2, "E3"), (27, 2, 2, "D3")]
    for bar, beat, dur, note in counter:
        p.play("strings", bar, beat, dur, note, 0.26, pan=-0.4, send=0.55,
               jitter=0.02, attack=0.5, release=1.0, harmonics=8, cutoff=1500)
    for bar in (20, 24):
        p.play("dum", bar, 0.0, 1.0, 60, 0.20, pan=0.0, send=0.4, jitter=0.008)

    # ---- outro (bars 28-33): plagal G -> D, then quiet home --------------
    for bar, chord in ((28, "Gmaj9"), (29, "Gmaj9"), (30, "Dmaj9"),
                       (31, "Dmaj9"), (32, "Dmaj9"), (33, "Dmaj9")):
        pad_chord(p, bar, 1, chord, vel=0.34, attack=1.4, release=3.0)
    for bar, beat, dur, note, vel in ((28, 0, 2, "B4", 0.40), (29, 0, 2, "F#5", 0.38),
                                      (30, 0, 2, "D5", 0.42), (32, 0, 4, "D5", 0.36),
                                      (33, 2, 2, "A4", 0.30)):
        p.play("piano", bar, beat, dur, note, vel, pan=0.0, send=0.4, jitter=0.015)
    long_bass(p, 28, "Gmaj9", vel=0.42, fifth=False)
    long_bass(p, 29, "Gmaj9", vel=0.40, fifth=False)
    for bar in (30, 31, 32, 33):
        long_bass(p, bar, "Dmaj9", vel=0.38, fifth=False)
    p.play("bell", 30, 0.0, 6.0, "D6", 0.22, pan=-0.25, send=0.9, jitter=0.015, tau=4.0)
    p.play("bell", 32, 0.0, 6.0, "A5", 0.16, pan=0.3, send=0.9, jitter=0.015, tau=4.0)
    p.play("choir", 32, 0.0, 8.0, "D4", 0.12, pan=0.0, send=0.75,
           jitter=0.03, attack=2.0, release=3.0)
    return p


BUILDERS = {
    "title": build_title,
    "spring": build_spring,
    "desert": build_desert,
    "winter": build_winter,
    "night": build_night,
    "ending": build_ending,
}


def build(sid: str) -> Piece:
    if sid not in BUILDERS:
        raise KeyError(f"unknown cue {sid}")
    return BUILDERS[sid]()


if __name__ == "__main__":
    import sys
    from pathlib import Path
    from synth import write_wav

    ids = sys.argv[1:] or list(BUILDERS)
    out = Path(__file__).parent / "_build"
    out.mkdir(exist_ok=True)
    for cue in ids:
        piece = build(cue)
        loop = piece.finish(target_rms=-18.0)
        write_wav(out / f"{cue}.wav", loop, fmt="f32")
        print(f"{cue}: {piece.loop_len:.2f}s notes={piece.count} "
              f"peak={20*math.log10(max(peak(loop),1e-9)):.2f}dBFS "
              f"rms={20*math.log10(max(rms(loop),1e-9)):.2f}dBFS")
