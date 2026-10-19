#!/usr/bin/env python3
"""Build the four diorama heightfields, paths, landmarks and prop scatter.

Design coordinates are normalized [-1, 1] over a 160 m island. Heights are in
metres. Output is data-driven so the Godot world builder only has to assemble
meshes, props and collision.

Run:  python tools/build_worlds.py
      python tools/build_worlds.py --preview-only
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "worlds"
SHOTS = ROOT / "screenshots" / "maps"
N = 100
CELL = 1.6
HALF = N * CELL * 0.5
S = N + 1
VOID = -40.0

# ----------------------------------------------------------------------------
# utility
# ----------------------------------------------------------------------------

def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-9), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def value_noise(shape, res, rng):
    """Smooth 2D value noise in [-1,1]."""
    h, w = shape
    grid = rng.random((res + 1, res + 1)) * 2.0 - 1.0
    y = np.linspace(0, res, h)
    x = np.linspace(0, res, w)
    xi = np.floor(x).astype(int).clip(0, res - 1)
    yi = np.floor(y).astype(int).clip(0, res - 1)
    xf = x - xi
    yf = y - yi
    xf = xf * xf * (3 - 2 * xf)
    yf = yf * yf * (3 - 2 * yf)
    a = grid[yi][:, xi]
    b = grid[yi][:, xi + 1]
    c = grid[yi + 1][:, xi]
    d = grid[yi + 1][:, xi + 1]
    return (a * (1 - xf) + b * xf) * (1 - yf) + (c * (1 - xf) + d * xf) * yf


def fbm(shape, seed, octaves=4, base_res=2, gain=0.5):
    rng = np.random.default_rng(seed)
    total = np.zeros(shape, dtype=np.float64)
    amp = 1.0
    norm = 0.0
    for o in range(octaves):
        total += value_noise(shape, base_res * (2 ** o), rng) * amp
        norm += amp
        amp *= gain
    return total / norm


def blur(a, passes=1):
    out = a.copy()
    for _ in range(passes):
        p = np.pad(out, 1, mode="edge")
        out = (
            p[1:-1, 1:-1] * 0.4
            + (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) * 0.125
            + (p[:-2, :-2] + p[:-2, 2:] + p[2:, :-2] + p[2:, 2:]) * 0.025
        )
    return out


def seg_dist(X, Z, a, b):
    ax, az = a
    bx, bz = b
    vx, vz = bx - ax, bz - az
    l2 = vx * vx + vz * vz + 1e-9
    t = np.clip(((X - ax) * vx + (Z - az) * vz) / l2, 0.0, 1.0)
    px = ax + vx * t
    pz = az + vz * t
    return np.sqrt((X - px) ** 2 + (Z - pz) ** 2), t


def shape_grid(shape):
    return np.zeros(shape, dtype=np.float64)


# ----------------------------------------------------------------------------
# heightfield composer
# ----------------------------------------------------------------------------

class World:
    def __init__(self, cfg):
        self.cfg = cfg
        self.n = N
        self.cell = CELL
        self.xs = np.linspace(-HALF, HALF, S)
        self.zs = np.linspace(-HALF, HALF, S)
        self.X, self.Z = np.meshgrid(self.xs, self.zs)
        self.H = np.zeros((S, S), dtype=np.float64)
        self.road = np.zeros((S, S), dtype=np.float64)
        self.road_dist = np.full((S, S), 999.0)
        self.rng = random.Random(cfg["seed"])
        self.props = []
        self.multi = {}
        self.water_specs = []
        self.bridge_specs = []
        self._placed = []

    # -- helpers -------------------------------------------------------------
    def to_world(self, xn, zn):
        return xn * HALF, zn * HALF

    def height_at(self, x, z):
        fx = (x + HALF) / CELL
        fz = (z + HALF) / CELL
        fx = float(np.clip(fx, 0, S - 1.001))
        fz = float(np.clip(fz, 0, S - 1.001))
        x0, z0 = int(fx), int(fz)
        tx, tz = fx - x0, fz - z0
        h = self.H
        return (
            h[z0, x0] * (1 - tx) * (1 - tz)
            + h[z0, x0 + 1] * tx * (1 - tz)
            + h[z0 + 1, x0] * (1 - tx) * tz
            + h[z0 + 1, x0 + 1] * tx * tz
        )

    def slope_at(self, x, z):
        e = 2.0
        dx = (self.height_at(x + e, z) - self.height_at(x - e, z)) / (2 * e)
        dz = (self.height_at(x, z + e) - self.height_at(x, z - e)) / (2 * e)
        return math.hypot(dx, dz)

    def add_hill(self, xn, zn, radius, height):
        x, z = self.to_world(xn, zn)
        d = np.sqrt((self.X - x) ** 2 + (self.Z - z) ** 2) / (radius * HALF)
        self.H += height * np.exp(-(d * d) * 2.2)

    def add_ridge(self, pts, height, width, sharp=2.0):
        """Raise a broad ridge along a polyline (canyon walls, mountain spines)."""
        w = width * HALF
        for a, b in zip(pts[:-1], pts[1:]):
            ax, az = self.to_world(*a)
            bx, bz = self.to_world(*b)
            d, _ = seg_dist(self.X, self.Z, (ax, az), (bx, bz))
            self.H += height * np.exp(-((d / w) ** 2) * sharp)

    def add_pad(self, xn, zn, radius, h, falloff=1.0):
        x, z = self.to_world(xn, zn)
        r = radius * HALF
        d = np.sqrt((self.X - x) ** 2 + (self.Z - z) ** 2)
        w = smoothstep(r * 1.15, r * 0.55 * falloff, d)
        self.H = self.H * (1 - w) + h * w

    def add_basin(self, xn, zn, radius, depth, flatten=True):
        x, z = self.to_world(xn, zn)
        r = radius * HALF
        d = np.sqrt((self.X - x) ** 2 + (self.Z - z) ** 2)
        w = smoothstep(r, r * 0.25, d)
        self.H -= depth * w
        if flatten:
            # make a believable shallow bowl, not a needle
            self.H -= depth * 0.25 * smoothstep(r * 0.8, r * 0.1, d)

    def road_height_at(self, x, z):
        """Nearest main-road height, used to seat bridges on the path."""
        best = (1e18, 0.0)
        for road in self.cfg["roads"]:
            pts = road["pts"]
            for i in range(len(pts) - 1):
                ax, az = self.to_world(pts[i][0], pts[i][1])
                bx, bz = self.to_world(pts[i + 1][0], pts[i + 1][1])
                ah, bh = pts[i][2], pts[i + 1][2]
                vx, vz = bx - ax, bz - az
                l2 = vx * vx + vz * vz + 1e-9
                t = max(0.0, min(1.0, ((x - ax) * vx + (z - az) * vz) / l2))
                px, pz = ax + vx * t, az + vz * t
                d = (x - px) ** 2 + (z - pz) ** 2
                if d < best[0]:
                    best = (d, ah + (bh - ah) * t)
        return best[1]

    def bridge_yaw(self, b):
        x, z = self.to_world(b["x"], b["z"])
        best = (1e18, 0.0)
        for road in self.cfg["roads"]:
            pts = road["pts"]
            for i in range(len(pts) - 1):
                ax, az = self.to_world(pts[i][0], pts[i][1])
                bx, bz = self.to_world(pts[i + 1][0], pts[i + 1][1])
                vx, vz = bx - ax, bz - az
                l2 = vx * vx + vz * vz + 1e-9
                t = max(0.0, min(1.0, ((x - ax) * vx + (z - az) * vz) / l2))
                px, pz = ax + vx * t, az + vz * t
                d = (x - px) ** 2 + (z - pz) ** 2
                if d < best[0]:
                    best = (d, math.atan2(vx, vz))
        return best[1]

    def carve_road(self, pts, widths):
        """pts: [(xn,zn,h)], widths: metres at each point (interp)."""
        wpts = [(self.to_world(x, z)[0], self.to_world(x, z)[1], h, w * 0.5)
                for (x, z, h), w in zip(pts, widths)]
        for i in range(len(wpts) - 1):
            ax, az, ah, aw = wpts[i]
            bx, bz, bh, bw = wpts[i + 1]
            # bbox
            pad = max(aw, bw) * 2.2 + 2.0
            x0 = int(np.clip((min(ax, bx) - pad + HALF) / CELL, 0, S - 1))
            x1 = int(np.clip((max(ax, bx) + pad + HALF) / CELL, 0, S - 1))
            z0 = int(np.clip((min(az, bz) - pad + HALF) / CELL, 0, S - 1))
            z1 = int(np.clip((max(az, bz) + pad + HALF) / CELL, 0, S - 1))
            if x1 <= x0 or z1 <= z0:
                continue
            X = self.X[z0:z1 + 1, x0:x1 + 1]
            Z = self.Z[z0:z1 + 1, x0:x1 + 1]
            d, t = seg_dist(X, Z, (ax, az), (bx, bz))
            h = ah + (bh - ah) * t
            w = aw + (bw - aw) * t
            influence = 1.0 - smoothstep(w * 0.55, w * 1.55, d)
            self.H[z0:z1 + 1, x0:x1 + 1] = (
                self.H[z0:z1 + 1, x0:x1 + 1] * (1 - influence) + h * influence
            )
            rm = 1.0 - smoothstep(w * 0.72, w * 1.05 + 0.55, d)
            self.road[z0:z1 + 1, x0:x1 + 1] = np.maximum(
                self.road[z0:z1 + 1, x0:x1 + 1], rm
            )
            self.road_dist[z0:z1 + 1, x0:x1 + 1] = np.minimum(
                self.road_dist[z0:z1 + 1, x0:x1 + 1], d
            )

    def add_chasm(self, xn, zn, angle_deg, length, width, depth):
        x, z = self.to_world(xn, zn)
        ang = math.radians(angle_deg)
        dx, dz = math.cos(ang) * length * HALF * 0.5, math.sin(ang) * length * HALF * 0.5
        d, _ = seg_dist(self.X, self.Z, (x - dx, z - dz), (x + dx, z + dz))
        w = width * HALF * 0.5
        fall = 1.0 - smoothstep(w * 0.55, w * 1.15, d)
        # keep a bit of a jagged edge
        fall *= 0.9 + 0.1 * np.sin(self.X * 0.3 + self.Z * 0.21)
        self.H -= depth * fall

    def add_spawn_pad(self, xn, zn, h, r=0.055):
        self.add_pad(xn, zn, r, h)

    # -- generation ----------------------------------------------------------
    def build(self):
        cfg = self.cfg
        base = cfg.get("base", 3.0)
        noise = fbm((S, S), cfg["seed"] + 1, octaves=4, base_res=3)
        self.H = base + noise * cfg.get("noise", 3.0)
        # gentle south-to-north tilt gives every island a readable silhouette
        self.H += fbm((S, S), cfg["seed"] + 2, octaves=2, base_res=2) * cfg.get("broad", 4.0)

        for h in cfg.get("hills", []):
            self.add_hill(*h)
        for r in cfg.get("ridges", []):
            self.add_ridge(*r)

        # land mask ----------------------------------------------------------
        if cfg["island"]["type"] == "blobs":
            mask = np.zeros_like(self.H)
            for (cx, cz, rx, rz) in cfg["island"]["blobs"]:
                d = np.sqrt(((self.X / HALF - cx) / rx) ** 2 + ((self.Z / HALF - cz) / rz) ** 2)
                mask = np.maximum(mask, 1.0 - smoothstep(0.86, 1.04, d))
        else:
            b = cfg["island"]
            nx = self.X / HALF
            nz = self.Z / HALF
            d = np.sqrt(((nx - b.get("cx", 0)) / b["ax"]) ** 2 + ((nz - b.get("cz", 0)) / b["az"]) ** 2)
            d += fbm((S, S), cfg["seed"] + 3, octaves=3, base_res=4) * 0.055
            # irregular coves and headlands so the silhouette never reads as a circle
            theta = np.arctan2(nz - b.get("cz", 0), nx - b.get("cx", 0))
            d += 0.042 * np.sin(theta * 3 + cfg["seed"] * 0.17)
            d += 0.026 * np.cos(theta * 5 - cfg["seed"] * 0.11)
            for (bx, bz, br) in b.get("bays", []):
                db = np.sqrt((nx - bx) ** 2 + (nz - bz) ** 2)
                d += smoothstep(br * 1.6, br * 0.2, db) * 0.06
            mask = 1.0 - smoothstep(0.88, 1.02, d)
        mask = np.clip(mask, 0, 1)
        self.H = self.H * mask + VOID * (1 - mask)

        # low-poly strata: quantise the raw land into broad terraces before
        # paths are carved. Paths then become readable ramps through the strata.
        terrace = float(cfg.get("terrace", 0.0))
        if terrace > 0.0:
            self.H = np.round(self.H / terrace) * terrace

        for p in cfg.get("pads", []):
            self.add_pad(*p)
        for b in cfg.get("basins", []):
            self.add_basin(*b)
        for p in cfg.get("pads_after", []):
            self.add_pad(*p)

        for road in cfg["roads"]:
            pts = [(p[0], p[1], p[2]) for p in road["pts"]]
            widths = [p[3] if len(p) > 3 else road.get("width", 4.0) for p in road["pts"]]
            self.carve_road(pts, widths)

        for ch in cfg.get("chasms", []):
            self.add_chasm(*ch)
        # every bridge gets a matching ravine carved perpendicular to its deck
        for b in cfg.get("bridges", []):
            yaw = self.bridge_yaw(b)
            self.add_chasm(b["x"], b["z"], -math.degrees(yaw), 0.42, 0.062,
                           b.get("depth", 20.0))

        # spawn path pad exactly matches the first road point
        sp = cfg["spawn"]
        self.add_pad(sp["x"], sp["z"], 0.035, sp["h"])

        self._make_water()
        self._make_bridges()
        self._landmarks()
        self._road_lanterns()
        self._scatter()
        self._flowers_and_grass()
        self._water_props()
        self._zones()
        self._fix_heights()

    def _fix_heights(self):
        # clamp crazy values and round for JSON
        self.H = np.round(np.clip(self.H, -40.0, 42.0), 2)
        self.road = np.round(np.clip(self.road, 0, 1), 2)

    # -- water ---------------------------------------------------------------
    def _make_water(self):
        for w in self.cfg.get("water", []):
            x, z = self.to_world(w["x"], w["z"])
            level = w["level"]
            # deepen the bed so water is not a paper-thin film
            bed = level - w.get("depth", 1.4)
            self.add_basin(w["x"], w["z"], w["r"], max(0.0, level - bed), flatten=False)
            # local flat-ish bed
            d = np.sqrt((self.X - x) ** 2 + (self.Z - z) ** 2)
            rr = w["r"] * HALF
            m = smoothstep(rr, rr * 0.25, d)
            self.H = self.H * (1 - m * 0.7) + (bed - 0.3) * (m * 0.7)
            self.water_specs.append(dict(x=x, z=z, level=level, r=rr, style=w.get("style", "pond")))

    def _make_bridges(self):
        for b in self.cfg.get("bridges", []):
            x, z = self.to_world(b["x"], b["z"])
            yaw = self.bridge_yaw(b)
            self.bridge_specs.append(dict(
                x=round(x, 2), z=round(z, 2), y=round(self.road_height_at(x, z), 2),
                angle=round(yaw, 4), span=b["span"],
                width=b.get("width", 3.0), type=b["type"]
            ))

    # -- props ---------------------------------------------------------------
    def add_prop(self, t, xn, zn, rot=0.0, scale=1.0, col="none", y_off=0.0, y=None):
        x, z = self.to_world(xn, zn)
        yy = self.height_at(x, z) if y is None else y
        # keep props out of deep holes (unless explicitly placed)
        self.props.append(dict(t=t, p=[round(x, 2), round(yy + y_off, 2), round(z, 2)],
                               r=round(rot, 4), s=round(scale, 3), c=col))
        self._placed.append((x, z, t))

    def _clear_of(self, x, z, radius):
        for (px, pz, _t) in self._placed:
            if (px - x) ** 2 + (pz - z) ** 2 < radius * radius:
                return False
        return True

    def _landmarks(self):
        cfg = self.cfg
        for hp in cfg.get("hand_props", []):
            self.add_prop(hp["t"], hp["x"], hp["z"],
                          math.radians(hp.get("rot", 0.0)), hp.get("s", 1.0),
                          hp.get("col", "none"), hp.get("y_off", 0.0))
        # required + optional embers
        for e in cfg.get("embers", []):
            self.add_prop("ember", e["x"], e["z"], 0.0, 1.0, "none", 1.25)
        for n in cfg.get("npcs", []):
            self.add_prop("npc_" + n["id"], n["x"], n["z"], math.radians(n.get("rot", 0)), 1.0, "none")
        for m in cfg.get("memorials", []):
            self.add_prop("memory_shard", m["x"], m["z"], math.radians(m.get("rot", 0)), 1.0, "box")
        b = cfg["beacon"]
        self.add_prop("beacon", b["x"], b["z"], math.radians(b.get("rot", 0)), 1.0, "box")

    def _road_lanterns(self):
        cfg = self.cfg
        if not cfg.get("lanterns", True):
            return
        main = cfg["roads"][0]
        pts = main["pts"]
        # sample roughly every 22 m along the main path, alternate sides
        dist_accum = 0.0
        next_d = 16.0
        side = 1
        for i in range(1, len(pts)):
            ax, az = self.to_world(pts[i - 1][0], pts[i - 1][1])
            bx, bz = self.to_world(pts[i][0], pts[i][1])
            seg = math.hypot(bx - ax, bz - az)
            while next_d <= dist_accum + seg:
                t = (next_d - dist_accum) / max(seg, 1e-6)
                x = ax + (bx - ax) * t
                z = az + (bz - az) * t
                # tangent + perpendicular offset
                dx, dz = (bx - ax) / max(seg, 1e-6), (bz - az) / max(seg, 1e-6)
                ox, oz = -dz * 2.5 * side, dx * 2.5 * side
                px, pz = x + ox, z + oz
                if self.height_at(px, pz) > -1 and self.slope_at(px, pz) < 0.75:
                    self.add_prop("stone_lantern", (px / HALF), (pz / HALF),
                                  math.atan2(dx, dz), 0.82, "cyl")
                side *= -1
                next_d += 19.0
            dist_accum += seg
        # a few floating paper lanterns for the night chapter
        if cfg["id"] == "ch4":
            for i in range(1, len(pts), 3):
                x, z = self.to_world(pts[i][0], pts[i][1])
                for k in range(2):
                    self.add_prop("paper_lantern", x / HALF + self.rng.uniform(-0.02, 0.02),
                                  z / HALF + self.rng.uniform(-0.02, 0.02), 0, 1.0, "none",
                                  self.rng.uniform(2.0, 5.0))

    def _scatter(self):
        cfg = self.cfg
        rng = self.rng
        # candidate lattice at 3.2 m, jittered
        step = 2
        candidates = []
        for iz in range(2, N - 1, step):
            for ix in range(2, N - 1, step):
                x = self.xs[ix] + rng.uniform(-1.1, 1.1)
                z = self.zs[iz] + rng.uniform(-1.1, 1.1)
                candidates.append((x, z))
        rng.shuffle(candidates)
        noise = fbm((S, S), cfg["seed"] + 7, octaves=3, base_res=4)
        for c in cfg.get("scatter", []):
            goal = c.get("count", 0)
            placed = 0
            min_sep = c.get("sep", 2.6)
            for (x, z) in candidates:
                if placed >= goal:
                    break
                if not (-HALF + 2 < x < HALF - 2 and -HALF + 2 < z < HALF - 2):
                    continue
                h = self.height_at(x, z)
                if h < -1.0:
                    continue
                slope = self.slope_at(x, z)
                if slope > c.get("slope", 0.6):
                    continue
                ix = int((x + HALF) / CELL)
                iz = int((z + HALF) / CELL)
                if c.get("path_clear", True):
                    if self.road_dist[iz, ix] < c.get("path_dist", 4.0):
                        continue
                    if self.road[iz, ix] > 0.05:
                        continue
                # water clearance
                wet = False
                for w in self.water_specs:
                    if math.hypot(x - w["x"], z - w["z"]) < w["r"] + c.get("water_dist", 1.0):
                        wet = True
                        break
                if wet:
                    continue
                # keep the arrival plaza open and readable
                _spawn_w = self.to_world(cfg["spawn"]["x"], cfg["spawn"]["z"])
                spawn_clear = float(c.get("spawn_clear", 0.0))
                if spawn_clear <= 0.0 and c["t"] in ["cherry_tree_a", "cherry_tree_b", "big_cherry",
                        "pine_tree_a", "pine_tree_b", "palm_tree", "bamboo_cluster", "glow_tree", "bare_tree"]:
                    spawn_clear = 12.0
                elif spawn_clear <= 0.0 and c["t"] in ["azalea_bush", "snow_bush", "desert_shrub", "rock_a"]:
                    spawn_clear = 7.5
                if spawn_clear > 0.0 and math.hypot(x - _spawn_w[0], z - _spawn_w[1]) < spawn_clear:
                    continue
                # clear around embers / npcs / beacon / big hand props
                clear_r = c.get("clear", 2.2)
                if not self._clear_of(x, z, clear_r):
                    continue
                field = noise[iz, ix]
                if c.get("cluster", 0.0) > 0 and field < c.get("cluster_threshold", 0.0):
                    continue
                # pack
                self.add_prop(c["t"], x / HALF, z / HALF, rng.uniform(0, math.tau),
                              rng.uniform(*c.get("scale", [0.85, 1.15])), c.get("col", "none"))
                self._placed.append((x, z, c["t"]))
                placed += 1
            print(f"    {c['t']}: {placed}/{goal}")

    def _flowers_and_grass(self):
        cfg = self.cfg
        rng = self.rng
        for m in cfg.get("multi", []):
            positions = []
            goal = m.get("count", 100)
            attempts = 0
            while len(positions) < goal and attempts < goal * 8:
                attempts += 1
                ix = rng.randint(2, N - 2)
                iz = rng.randint(2, N - 2)
                x = self.xs[ix] + rng.uniform(-0.8, 0.8)
                z = self.zs[iz] + rng.uniform(-0.8, 0.8)
                h = self.height_at(x, z)
                if h < -0.5:
                    continue
                if self.road_dist[iz, ix] < m.get("path_dist", 1.4):
                    continue
                slope = self.slope_at(x, z)
                if slope > m.get("slope", 0.8):
                    continue
                if any(math.hypot(x - w["x"], z - w["z"]) < w["r"] + 0.4 for w in self.water_specs):
                    continue
                if not self._clear_of(x, z, m.get("clear", 0.3)):
                    continue
                positions.append([round(x, 2), round(h - 0.03, 2), round(z, 2),
                                  round(rng.uniform(0, math.tau), 3),
                                  round(rng.uniform(*m.get("scale", [0.8, 1.3])), 3)])
            self.multi.setdefault(m["t"], []).extend(positions)
            print(f"    {m['t']}: {len(positions)}")

    def _water_props(self):
        rng = self.rng
        for w in self.water_specs:
            if w["style"] not in ("pond", "oasis", "hotspring", "mirror", "lake"):
                continue
            # lilypads + koi
            for k in range(max(4, int(w["r"] / 3))):
                a = rng.uniform(0, math.tau)
                rr = rng.uniform(0.15, 0.75) * w["r"]
                x = w["x"] + math.cos(a) * rr
                z = w["z"] + math.sin(a) * rr
                t = "lilypad" if w["style"] in ("pond", "oasis", "hotspring") else None
                if t and rng.random() < 0.8:
                    self.multi.setdefault(t, []).append([round(x, 2), round(w["level"] + 0.03, 2),
                                                         round(z, 2), round(rng.uniform(0, 6.28), 3),
                                                         round(rng.uniform(0.8, 1.3), 3)])
            if w["style"] in ("pond", "oasis") and self.cfg["id"] in ("ch1", "ch2"):
                for k in range(2):
                    a = rng.uniform(0, math.tau)
                    rr = rng.uniform(0.2, 0.55) * w["r"]
                    self.multi.setdefault("koi", []).append([
                        round(w["x"] + math.cos(a) * rr, 2),
                        round(w["level"] - 0.12, 2),
                        round(w["z"] + math.sin(a) * rr, 2),
                        round(rng.uniform(0, 6.28), 3),
                        round(rng.uniform(0.8, 1.1), 3),
                    ])

    def _zones(self):
        self.zone_specs = []
        for z in self.cfg.get("zones", []):
            x, zz = self.to_world(z["x"], z["z"])
            self.zone_specs.append(dict(name=z["name"], x=round(x, 2), z=round(zz, 2),
                                        r=round(z["r"] * HALF, 2)))

    # -- export --------------------------------------------------------------
    def output(self):
        cfg = self.cfg
        # resolve spawn/beacon/npc ground positions
        sp = cfg["spawn"]
        sx, sz = self.to_world(sp["x"], sp["z"])
        spawn = [round(sx, 2), round(self.height_at(sx, sz), 2), round(sz, 2)]
        b = cfg["beacon"]
        bx, bz = self.to_world(b["x"], b["z"])
        beacon = [round(bx, 2), round(self.height_at(bx, bz), 2), round(bz, 2)]
        embers = []
        for i, e in enumerate(cfg.get("embers", [])):
            ex, ez = self.to_world(e["x"], e["z"])
            embers.append(dict(id=f"{cfg['id']}_ember_{i+1}", name=e.get("name", "余烬"),
                               p=[round(ex, 2), round(self.height_at(ex, ez) + 1.15, 2), round(ez, 2)],
                               secret=e.get("secret", False)))
        npcs = []
        for n in cfg.get("npcs", []):
            nx, nz = self.to_world(n["x"], n["z"])
            npcs.append(dict(id=n["id"], name=n["name"], role=n.get("role", ""),
                             p=[round(nx, 2), round(self.height_at(nx, nz), 2), round(nz, 2)],
                             rot=n.get("rot", 0.0), memory=n.get("memory", ""),
                             lines=n.get("lines", [])))
        zones = getattr(self, "zone_specs", [])
        paths = []
        for road in cfg["roads"]:
            pts = []
            widths = []
            for pt in road["pts"]:
                wx, wz = self.to_world(pt[0], pt[1])
                pts.append([round(wx, 2), round(wz, 2)])
                widths.append(float(pt[3]) if len(pt) > 3 else float(road.get("width", 4.0)))
            paths.append(dict(pts=pts, w=widths, main=(road is cfg["roads"][0])))
        return dict(
            id=cfg["id"], title=cfg["title"], en=cfg.get("en", ""), num=cfg.get("num", 1),
            n=N, cell=CELL,
            h=self.H.flatten().tolist(),
            road=self.road.flatten().tolist(),
            spawn=spawn,
            spawn_yaw=sp.get("yaw", 0.0),
            beacon=beacon,
            embers=embers,
            npcs=npcs,
            props=self.props,
            multi=[dict(t=k, p=v) for k, v in self.multi.items()],
            water=self.water_specs,
            bridges=self.bridge_specs,
            zones=zones,
            paths=paths,
            env=cfg.get("env", {}),
            camera=cfg.get("camera", {}),
            palette=cfg.get("palette", {}),
        )

    # -- preview -------------------------------------------------------------
    def preview(self, path):
        cfg = self.cfg
        pal = cfg.get("preview")
        base = np.array(pal["base"], dtype=np.float64) / 255.0
        rock = np.array(pal["rock"], dtype=np.float64) / 255.0
        water = np.array(pal["water"], dtype=np.float64) / 255.0
        roadc = np.array(pal["road"], dtype=np.float64) / 255.0

        gy, gx = np.gradient(self.H, CELL, CELL)
        slope = np.sqrt(gx * gx + gy * gy)
        light = np.clip(0.55 - (gx * 0.6 + gy * 0.4) * 0.12, 0.2, 1.2)
        hnorm = (self.H - np.nanmin(self.H)) / (np.nanmax(self.H) - np.nanmin(self.H) + 1e-6)
        img = np.zeros((S, S, 3), dtype=np.float64)
        rockmask = smoothstep(0.45, 1.1, slope)
        alt = np.clip(hnorm[..., None] * 1.4, 0, 1)
        col = base[None, None, :] * (0.78 + 0.4 * alt)
        col = col * (1 - rockmask[..., None]) + rock[None, None, :] * rockmask[..., None]
        col = col * (1 - self.road[..., None] * 0.7) + roadc[None, None, :] * self.road[..., None] * 0.7
        for w in self.water_specs:
            d = np.sqrt((self.X - w["x"]) ** 2 + (self.Z - w["z"]) ** 2)
            m = (d < w["r"]).astype(float)
            col = col * (1 - m[..., None] * 0.8) + water[None, None, :] * m[..., None] * 0.8
        void = (self.H < -3).astype(float)
        col = col * (1 - void[..., None]) + np.array([0.06, 0.07, 0.08])[None, None, :] * void[..., None]
        col *= light[..., None]
        col = np.clip(col, 0, 1) ** (1 / 2.2)
        rgba = (col * 255).astype(np.uint8)
        rgba[self.H < -3] = [18, 20, 24]
        im = Image.fromarray(rgba, "RGB").resize((900, 900), Image.Resampling.NEAREST)
        d = ImageDraw.Draw(im)
        # water rings
        for w in self.water_specs:
            px = (w["x"] + HALF) / (N * CELL) * 900
            pz = (w["z"] + HALF) / (N * CELL) * 900
            rr = w["r"] / (N * CELL) * 900
            d.ellipse([px - rr, pz - rr, px + rr, pz + rr], outline=(120, 230, 220), width=2)
        # paths
        for road in cfg["roads"]:
            pts = [((p[0] * HALF + HALF) / (N * CELL) * 900,
                    (p[1] * HALF + HALF) / (N * CELL) * 900) for p in road["pts"]]
            d.line(pts, fill=(245, 230, 190), width=2)
        # bridges
        for b in self.bridge_specs:
            px = (b["x"] + HALF) / (N * CELL) * 900
            pz = (b["z"] + HALF) / (N * CELL) * 900
            d.ellipse([px - 4, pz - 4, px + 4, pz + 4], fill=(255, 120, 80))
        # landmarks
        for e in cfg.get("embers", []):
            x, z = self.to_world(e["x"], e["z"])
            px, pz = (x + HALF) / (N * CELL) * 900, (z + HALF) / (N * CELL) * 900
            d.ellipse([px - 6, pz - 6, px + 6, pz + 6], fill=(255, 190, 40), outline=(30, 20, 10), width=2)
        for n in cfg.get("npcs", []):
            x, z = self.to_world(n["x"], n["z"])
            px, pz = (x + HALF) / (N * CELL) * 900, (z + HALF) / (N * CELL) * 900
            d.rectangle([px - 5, pz - 5, px + 5, pz + 5], fill=(120, 210, 255))
        b = cfg["beacon"]
        x, z = self.to_world(b["x"], b["z"])
        px, pz = (x + HALF) / (N * CELL) * 900, (z + HALF) / (N * CELL) * 900
        d.ellipse([px - 10, pz - 10, px + 10, pz + 10], outline=(255, 80, 80), width=3)
        sp = cfg["spawn"]
        x, z = self.to_world(sp["x"], sp["z"])
        px, pz = (x + HALF) / (N * CELL) * 900, (z + HALF) / (N * CELL) * 900
        d.ellipse([px - 9, pz - 9, px + 9, pz + 9], outline=(255, 255, 255), width=3)
        # zones labels
        try:
            font = ImageFont.truetype(str(ROOT / "assets/fonts/NotoSerifSC-Variable.ttf"), 15)
        except Exception:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 16)
            except Exception:
                font = ImageFont.load_default()
        for zon in getattr(self, "zone_specs", []):
            px = (zon["x"] + HALF) / (N * CELL) * 900
            pz = (zon["z"] + HALF) / (N * CELL) * 900
            d.text((px + 8, pz - 8), zon["name"], fill=(20, 20, 20), font=font,
                   stroke_width=2, stroke_fill=(240, 235, 220))
        d.rectangle([0, 0, 900, 34], fill=(20, 22, 25))
        d.text((10, 8), f"{cfg['id']}  {cfg['title']}  —  embers {len(cfg.get('embers', []))}, beacon {cfg['beacon']}",
               fill=(245, 235, 215), font=font)
        path.parent.mkdir(parents=True, exist_ok=True)
        im.save(path)


# ----------------------------------------------------------------------------
# shared data
# ----------------------------------------------------------------------------

def lines_tai():
    return [
        "……你醒了。",
        "这里是星鲸的梦。灯灭了，梦就会沉下去。",
        "孩子，去把散落的余烬捡回来吧。",
        "山脊上那盏残灯，还认得回家的路。",
    ]


def lines_xiaoying():
    return [
        "你也看见这棵树了吗？",
        "我总觉得，很久以前我在这里点过一盏灯。",
        "火苗很小，可它照亮了一整只迷路的鲸。",
        "奇怪……我怎么会记得鲸呢？",
    ]


def lines_atuo():
    return [
        "客官，借个火？",
        "这条沙路我走了三十遍，每一遍都以为尽头是海。",
        "结果尽头是一头睡着的鲸。你说好笑不好笑。",
        "再走一程吧。灯还亮着，就不算走丢。",
    ]


def lines_ling():
    return [
        "嘘——你听见骨头在唱歌吗？",
        "阿姐说，鲸骨里住着风。",
        "我把风铃挂在这里，等阿姐回来就能找到路。",
        "你要不要也挂一只？……算了，你看起来比我还迷路。",
    ]


def lines_xiaoman():
    return [
        "姐姐说，雪停的时候就回来。",
        "我每天擦一遍窗，灯就能照得远一点。",
        "你看，窗上的霜花像不像一片海？",
        "她一定是在海上，被什么东西耽搁了。",
    ]


def lines_laozhou():
    return [
        "灯要添油，人要添念想。",
        "那年雪大，她把最后一点油都倒进了灯里。",
        "我在这儿守着。守习惯了，就不觉得冷。",
        "你往上走吧。塔顶的灯，从来不是为死人亮的。",
    ]


def lines_aying():
    return [
        "你终于来了。",
        "我把自己的名字点成了灯芯，所以有点记不清了。",
        "但是你的灯……很暖。像很久以前，我点给一只小鲸的那一盏。",
        "把它给我，好吗？我想记起自己是谁。",
    ]


def lines_bell():
    return [
        "（你把手贴在鲸骨上，听见很远的潮声。）",
        "「万灯归海，一灯回家。」",
        "骨缝里漏下的星光，像一场很慢很慢的雨。",
    ]


CH1 = dict(
    id="ch1", num=1, terrace=1.2, title="苔庭 · 春眠", en="Mossgarden", seed=101,
    base=4.0, noise=1.6, broad=2.0,
    island=dict(type="ellipse", ax=0.94, az=0.83, cx=0.0, cz=0.03,
                bays=[(0.82, 0.52, 0.32), (-0.88, 0.55, 0.25), (0.55, -0.82, 0.2)]),
    hills=[(-0.15, -0.52, 0.38, 8.0), (0.55, -0.38, 0.28, 5.0), (-0.5, -0.05, 0.3, 4.0),
           (0.2, 0.28, 0.4, 2.0)],
    ridges=[
        ([( -0.95, -0.48), (-0.4, -0.62), (0.1, -0.64), (0.6, -0.55), (0.92, -0.4)], 9.0, 0.1, 1.6),
        ([(0.33, 0.02), (0.42, -0.12), (0.48, -0.28), (0.45, -0.44)], 7.0, 0.08, 2.2),
        ([(-0.3, -0.1), (-0.2, -0.25), (-0.08, -0.36)], 5.0, 0.07, 2.0),
    ],
    pads=[
        (0.0, 0.62, 0.08, 2.6),
        (0.18, -0.16, 0.15, 9.6),
        (0.52, -0.36, 0.15, 11.8),
        (-0.5, 0.0, 0.17, 8.0),
        (-0.16, -0.39, 0.09, 11.6),
        (0.03, -0.72, 0.12, 20.2),
        (0.02, 0.13, 0.07, 5.0),
        (0.0, 0.60, 0.20, 6.5),
    ],
    basins=[
        (0.22, -0.16, 0.11, 2.2),
        (0.53, 0.36, 0.085, 1.8),
        (0.56, -0.4, 0.1, 2.4),
        (-0.08, 0.24, 0.18, 2.6),
    ],
    roads=[
        dict(width=4.4, pts=[
            (0.0, 0.62, 6.5, 4.6), (-0.08, 0.46, 6.0, 4.3), (-0.05, 0.29, 5.0, 4.0),
            (0.02, 0.13, 5.0, 3.8), (0.08, 0.0, 6.0, 3.6), (0.14, -0.1, 7.4, 3.4),
            (0.19, -0.17, 8.9, 3.8), (0.29, -0.2, 9.5, 4.6), (0.39, -0.24, 10.1, 4.0),
            (0.47, -0.3, 10.9, 3.2), (0.53, -0.37, 11.8, 3.0), (0.5, -0.45, 12.6, 3.0),
            (0.42, -0.51, 13.4, 3.0), (0.33, -0.57, 14.7, 3.2), (0.22, -0.63, 17.0, 3.4),
            (0.1, -0.68, 19.3, 3.8), (0.02, -0.72, 20.2, 5.0),
        ]),
        dict(width=3.0, pts=[
            (0.02, 0.13, 5.0, 3.0), (-0.14, 0.09, 5.7, 2.8), (-0.3, 0.03, 6.8, 2.7),
            (-0.45, 0.0, 7.7, 2.8), (-0.55, 0.05, 7.8, 3.0),
        ]),
        dict(width=2.5, pts=[
            (0.18, -0.16, 9.6, 2.8), (0.05, -0.26, 10.2, 2.5), (-0.08, -0.34, 11.0, 2.4),
            (-0.16, -0.39, 11.6, 3.4),
        ]),
        dict(width=2.2, pts=[
            (0.33, 0.55, 3.0, 2.4), (0.45, 0.46, 3.1, 2.2), (0.53, 0.36, 3.1, 3.0),
        ]),
        dict(width=2.0, pts=[
            (0.5, -0.33, 11.5, 2.0), (0.6, -0.34, 11.7, 2.0), (0.64, -0.3, 11.6, 2.2),
        ]),
    ],
    chasms=[],
    bridges=[dict(x=0.46, z=-0.48, span=11.0, width=3.1, type="stone_bridge", depth=15.0)],
    water=[
        dict(x=0.22, z=-0.16, level=8.0, r=0.09, depth=1.4, style="pond"),
        dict(x=0.53, z=0.36, level=2.9, r=0.065, depth=1.0, style="pond"),
        dict(x=0.56, z=-0.4, level=12.25, r=0.075, depth=1.2, style="pond"),
    ],
    hand_props=[
        dict(t="torii_gate", x=0.02, z=0.585, rot=4, s=1.0, col="box"),
        dict(t="stone_lantern", x=-0.062, z=0.575, rot=8, s=0.86, col="cyl"),
        dict(t="stone_lantern", x=0.064, z=0.575, rot=-8, s=0.86, col="cyl"),
        dict(t="paper_lantern", x=-0.03, z=0.6, rot=0, s=1.0, col="none", y_off=3.4),
        dict(t="paper_lantern", x=0.055, z=0.605, rot=0, s=0.9, col="none", y_off=3.9),
        dict(t="torii_gate", x=0.02, z=-0.745, rot=2, s=1.0, col="box"),
        dict(t="moss_shrine", x=0.29, z=-0.22, rot=28, s=1.0, col="box"),
        dict(t="big_cherry", x=-0.17, z=-0.39, rot=30, s=1.6, col="cyl"),
        dict(t="well", x=-0.47, z=0.03, rot=0, s=1.0, col="cyl"),
        dict(t="signpost", x=0.02, z=0.17, rot=-20, s=1.0, col="cyl"),
        dict(t="signpost", x=0.48, z=-0.3, rot=40, s=0.9, col="cyl"),
        dict(t="ruin_pillar", x=-0.52, z=-0.03, rot=15, s=1.0, col="cyl"),
        dict(t="ruin_pillar", x=-0.45, z=0.07, rot=-30, s=0.85, col="cyl"),
        dict(t="ruin_pillar", x=-0.57, z=0.08, rot=4, s=1.1, col="cyl"),
        dict(t="paper_lantern", x=-0.47, z=0.12, rot=0, s=1.0, col="none", y_off=3.2),
        dict(t="paper_lantern", x=-0.4, z=-0.02, rot=0, s=1.0, col="none", y_off=3.6),
        dict(t="memory_shard", x=-0.22, z=-0.34, rot=150, s=1.0, col="box"),
        dict(t="memory_shard", x=0.61, z=-0.36, rot=220, s=1.0, col="box"),
    ],
    embers=[
        dict(x=0.29, z=-0.155, name="池畔余烬"),
        dict(x=0.64, z=-0.32, name="瀑后余烬", secret=True),
        dict(x=-0.19, z=-0.42, name="樱下余烬"),
        dict(x=-0.52, z=-0.01, name="旧园余烬"),
        dict(x=0.52, z=0.37, name="竹影余烬", secret=True),
    ],
    npcs=[
        dict(id="tai", name="苔婆婆", x=0.0, z=0.2, rot=180,
             memory="memory_2_torii", lines=lines_tai()),
        dict(id="xiaoying", name="小萤", x=-0.23, z=-0.37, rot=120,
             memory="memory_1_firstlight", lines=lines_xiaoying()),
    ],
    zones=[
        dict(name="南坡苔原", x=0.0, z=0.55, r=0.14),
        dict(name="樱林小径", x=-0.03, z=0.28, r=0.13),
        dict(name="镜鲤池", x=0.22, z=-0.17, r=0.12),
        dict(name="旧石阶", x=0.15, z=-0.1, r=0.1),
        dict(name="苔痕峡谷", x=0.55, z=-0.35, r=0.12),
        dict(name="瀑后幽庭", x=0.64, z=-0.31, r=0.07),
        dict(name="断鸟居", x=0.03, z=-0.72, r=0.15),
    ],
    spawn=dict(x=0.0, z=0.60, h=6.5, yaw=0.0),
    beacon=dict(x=0.02, z=-0.72, rot=0),
    scatter=[
        dict(t="cherry_tree_a", count=48, sep=4.2, path_dist=5.0, clear=3.5, slope=0.45,
             cluster=0.35, cluster_threshold=0.0, scale=[0.8, 1.25], col="cyl"),
        dict(t="cherry_tree_b", count=40, sep=4.0, path_dist=4.6, clear=3.2, slope=0.5,
             cluster=0.35, cluster_threshold=-0.05, scale=[0.8, 1.25], col="cyl"),
        dict(t="bamboo_cluster", count=26, sep=3.4, path_dist=3.8, clear=2.8, slope=0.55,
             cluster=0.2, cluster_threshold=-0.1, scale=[0.8, 1.2], col="cyl"),
        dict(t="azalea_bush", count=70, sep=2.6, path_dist=2.8, clear=1.8, slope=0.6,
             scale=[0.75, 1.25], col="none"),
        dict(t="fern", count=90, sep=1.7, path_dist=2.0, clear=1.0, slope=0.7,
             scale=[0.8, 1.3], col="none"),
        dict(t="rock_a", count=45, sep=4.0, path_dist=3.2, clear=2.0, slope=0.7,
             scale=[0.7, 1.3], col="cyl"),
        dict(t="rock_b", count=65, sep=2.7, path_dist=2.0, clear=1.4, slope=0.8,
             scale=[0.7, 1.4], col="none"),
        dict(t="stump", count=16, sep=6.0, path_dist=3.0, clear=2.0, slope=0.5,
             scale=[0.8, 1.2], col="none"),
        dict(t="driftwood", count=10, sep=7.0, path_dist=2.5, clear=2.0, slope=0.5,
             scale=[0.8, 1.1], col="none"),
    ],
    multi=[
        dict(t="grass_tuft", count=3600, path_dist=1.2, slope=0.9, clear=0.3,
             scale=[0.7, 1.5]),
        dict(t="flower_spring_a", count=550, path_dist=1.6, slope=0.7, clear=0.3,
             scale=[0.8, 1.3]),
        dict(t="flower_spring_b", count=420, path_dist=1.4, slope=0.7, clear=0.3,
             scale=[0.8, 1.3]),
    ],
    env=dict(
        sky_top="#8FBDB8", sky_horizon="#F9E4C4", sky_bottom="#5E8F86",
        sun_color="#FFE3B0", sun_energy=1.45, sun_angle=(-42, -38),
        ambient="#A9C4B3", ambient_energy=0.62, fog="#CFE4D8", fog_density=0.006,
        glow=0.85, saturation=1.0, exposure=1.05, star=0.0, aurora=0.0,
        petals="#F3C9C5", motes="#FFF0C4",
    ),
    camera=dict(yaw=-36.0, pitch=-38.0, distance=19.0, fov=42.0),
    preview=dict(base=(91, 124, 88), rock=(118, 124, 102), water=(76, 142, 134), road=(201, 188, 156)),
    palette=dict(
        grass_a="#6F9468", grass_b="#89A86F", grass_c="#A9BC7C", dirt="#B9A47F",
        rock="#7E8878", rock_dark="#5B665C", path="#C9B994", path_dark="#A89978",
        water="#4F9C92", shore="#D8C9A5", accent="#E7B0AE",
    ),
)

CH2 = dict(
    id="ch2", num=2, terrace=1.2, title="琥珀沙海 · 长夏", en="Amberreach", seed=202,
    base=3.0, noise=1.5, broad=2.0,
    island=dict(type="ellipse", ax=0.97, az=0.8, cx=0.0, cz=0.02,
                bays=[(-0.75, 0.7, 0.25), (0.8, -0.55, 0.2), (0.9, 0.55, 0.28)]),
    hills=[(0.22, -0.62, 0.35, 10.0), (-0.4, 0.1, 0.25, 4.0), (0.62, -0.28, 0.22, 5.0)],
    ridges=[
        ([(-0.6, 0.38), (-0.35, 0.26), (-0.1, 0.1), (0.1, 0.0)], 7.0, 0.11, 1.7),
        ([(0.36, 0.28), (0.3, 0.06), (0.28, -0.2), (0.34, -0.4)], 8.0, 0.1, 1.8),
        ([(0.55, -0.58), (0.36, -0.68), (0.12, -0.72)], 6.0, 0.1, 1.7),
    ],
    pads=[
        (-0.55, 0.5, 0.12, 2.4), (0.2, 0.02, 0.17, 7.0), (0.38, -0.12, 0.14, 7.2),
        (-0.25, 0.3, 0.12, 3.0), (0.52, -0.5, 0.1, 14.0), (0.2, -0.69, 0.13, 18.2),
        (0.52, 0.18, 0.09, 4.2), (-0.4, 0.12, 0.09, 2.6), (0.65, -0.3, 0.09, 13.6),
        (-0.55, 0.5, 0.25, 5.5),
    ],
    basins=[
        (-0.25, 0.31, 0.1, 1.2), (-0.41, 0.13, 0.08, 1.2), (0.2, 0.02, 0.05, 0.6),
    ],
    roads=[
        dict(width=5.0, pts=[
            (-0.55, 0.5, 5.5, 5.0), (-0.48, 0.39, 5.0, 4.5), (-0.4, 0.3, 4.2, 3.6),
            (-0.31, 0.22, 3.9, 3.2), (-0.22, 0.14, 4.5, 3.4), (-0.12, 0.07, 5.2, 4.2),
            (-0.02, 0.03, 6.0, 4.0), (0.08, 0.01, 6.8, 4.4), (0.18, 0.02, 7.0, 5.2),
            (0.27, -0.03, 7.0, 4.2), (0.35, -0.1, 7.2, 3.6), (0.42, -0.18, 8.0, 3.3),
            (0.48, -0.28, 9.2, 3.0), (0.52, -0.38, 11.2, 3.0), (0.52, -0.48, 13.6, 3.0),
            (0.43, -0.55, 14.8, 3.2), (0.32, -0.62, 16.0, 3.4), (0.22, -0.67, 17.4, 3.8),
            (0.2, -0.69, 18.2, 5.0),
        ]),
        dict(width=3.0, pts=[
            (-0.55, 0.5, 2.4, 4.0), (-0.42, 0.44, 2.5, 3.0), (-0.3, 0.35, 2.8, 2.7),
            (-0.25, 0.31, 3.0, 3.6),
        ]),
        dict(width=2.4, pts=[
            (0.2, 0.02, 7.0, 3.0), (0.32, 0.1, 6.0, 2.5), (0.44, 0.16, 5.0, 2.4),
            (0.52, 0.18, 4.2, 3.2),
        ]),
        dict(width=2.4, pts=[
            (0.2, 0.02, 7.0, 2.8), (-0.1, 0.08, 4.2, 2.4), (-0.3, 0.14, 3.0, 2.3),
            (-0.41, 0.13, 2.6, 2.8),
        ]),
        dict(width=2.2, pts=[
            (0.52, -0.48, 13.6, 2.6), (0.62, -0.37, 13.6, 2.3), (0.65, -0.3, 13.6, 2.8),
        ]),
    ],
    chasms=[],
    bridges=[dict(x=0.03, z=0.05, span=12.5, width=2.8, type="rope_bridge", depth=18.0)],
    water=[
        dict(x=-0.25, z=0.31, level=2.75, r=0.09, depth=1.2, style="oasis"),
        dict(x=-0.41, z=0.13, level=2.2, r=0.07, depth=1.1, style="grotto"),
        dict(x=0.2, z=0.02, level=6.35, r=0.045, depth=0.9, style="well"),
    ],
    hand_props=[
        dict(t="market_tent", x=0.17, z=0.065, rot=-12, s=1.05, col="box"),
        dict(t="market_tent", x=0.25, z=-0.005, rot=64, s=0.95, col="box"),
        dict(t="market_tent", x=0.1, z=0.075, rot=152, s=0.9, col="box"),
        dict(t="well", x=0.2, z=0.035, rot=0, s=1.0, col="cyl"),
        dict(t="sandstone_arch", x=0.5, z=-0.53, rot=48, s=1.0, col="box"),
        dict(t="whale_ribs", x=0.37, z=-0.12, rot=96, s=1.05, col="none"),
        dict(t="market_tent", x=-0.68, z=0.58, rot=30, s=0.8, col="box"),
        dict(t="signpost", x=0.08, z=0.01, rot=20, s=1.0, col="cyl"),
        dict(t="signpost", x=-0.3, z=0.24, rot=-40, s=0.9, col="cyl"),
        dict(t="ruin_pillar", x=0.49, z=0.21, rot=10, s=0.9, col="cyl"),
        dict(t="ruin_pillar", x=0.56, z=0.15, rot=-25, s=0.7, col="cyl"),
        dict(t="memory_shard", x=0.44, z=-0.07, rot=100, s=1.0, col="box"),
        dict(t="paper_lantern", x=-0.36, z=0.44, rot=0, s=1.0, col="none", y_off=3.4),
        dict(t="paper_lantern", x=-0.3, z=0.38, rot=0, s=0.9, col="none", y_off=2.9),
    ],
    embers=[
        dict(x=0.36, z=-0.19, name="鲸骨余烬"),
        dict(x=0.63, z=-0.29, name="高台余烬", secret=True),
        dict(x=-0.42, z=0.1, name="石隙余烬"),
        dict(x=0.51, z=0.2, name="沉舟余烬", secret=True),
        dict(x=-0.12, z=-0.18, name="风蚀余烬"),
    ],
    npcs=[
        dict(id="atuo", name="阿柘", x=-0.6, z=0.44, rot=80,
             memory="memory_3_caravan", lines=lines_atuo()),
        dict(id="ling", name="铃", x=0.37, z=-0.08, rot=180,
             memory="memory_4_ribcage", lines=lines_ling()),
    ],
    zones=[
        dict(name="沙海驼铃", x=-0.55, z=0.5, r=0.12),
        dict(name="一线天", x=-0.28, z=0.18, r=0.11),
        dict(name="风脊绳桥", x=0.03, z=0.05, r=0.1),
        dict(name="绿洲集市", x=0.2, z=0.03, r=0.13),
        dict(name="鲸骨客栈", x=0.37, z=-0.12, r=0.12),
        dict(name="风蚀拱门", x=0.5, z=-0.53, r=0.11),
        dict(name="鲸眼高崖", x=0.2, z=-0.69, r=0.14),
    ],
    spawn=dict(x=-0.55, z=0.5, h=5.5, yaw=180.0),
    beacon=dict(x=0.2, z=-0.69, rot=0),
    scatter=[
        dict(t="palm_tree", count=34, sep=5.0, path_dist=5.5, clear=3.0, slope=0.45,
             cluster=0.4, cluster_threshold=-0.05, scale=[0.8, 1.25], col="cyl"),
        dict(t="desert_shrub", count=130, sep=2.6, path_dist=2.6, clear=1.8, slope=0.65,
             scale=[0.7, 1.3], col="none"),
        dict(t="cactus", count=28, sep=5.0, path_dist=4.0, clear=2.4, slope=0.55,
             scale=[0.75, 1.2], col="cyl"),
        dict(t="reeds", count=55, sep=2.0, path_dist=3.0, clear=1.2, slope=0.4,
             scale=[0.8, 1.2], col="none"),
        dict(t="rock_a", count=55, sep=4.5, path_dist=3.0, clear=2.0, slope=0.8,
             scale=[0.7, 1.5], col="cyl"),
        dict(t="rock_b", count=80, sep=2.8, path_dist=2.0, clear=1.3, slope=0.85,
             scale=[0.7, 1.4], col="none"),
        dict(t="driftwood", count=28, sep=5.0, path_dist=2.8, clear=1.8, slope=0.45,
             scale=[0.8, 1.4], col="none"),
        dict(t="stump", count=10, sep=7.0, path_dist=3.0, clear=2.0, slope=0.5,
             scale=[0.7, 1.1], col="none"),
    ],
    multi=[
        dict(t="grass_tuft", count=900, path_dist=1.2, slope=0.9, clear=0.3,
             scale=[0.6, 1.2]),
        dict(t="flower_desert", count=260, path_dist=1.8, slope=0.7, clear=0.3,
             scale=[0.7, 1.2]),
    ],
    env=dict(
        sky_top="#E8B06A", sky_horizon="#FFE1A8", sky_bottom="#C97C4C",
        sun_color="#FFD08A", sun_energy=1.8, sun_angle=(-28, -52),
        ambient="#D9B18A", ambient_energy=0.7, fog="#E9C99B", fog_density=0.0065,
        glow=0.9, saturation=1.04, exposure=1.02, star=0.0, aurora=0.0,
        petals="#F0C27C", motes="#FFE0A0",
    ),
    camera=dict(yaw=-38.0, pitch=-37.0, distance=19.5, fov=42.0),
    preview=dict(base=(196, 158, 104), rock=(164, 108, 76), water=(72, 150, 142), road=(228, 199, 146)),
    palette=dict(
        grass_a="#A98F5B", grass_b="#C2A96E", grass_c="#D6BE86", dirt="#C79262",
        rock="#B7704F", rock_dark="#8A4F3A", path="#E0C692", path_dark="#C7A46F",
        water="#3F9C91", shore="#E9D3A0", accent="#E7A05D",
    ),
)

CH3 = dict(
    id="ch3", num=3, terrace=1.2, title="霜枝谷 · 静冬", en="Frostvale", seed=303,
    base=4.0, noise=1.5, broad=2.0,
    island=dict(type="ellipse", ax=0.9, az=0.87, cx=0.0, cz=0.0,
                bays=[(0.78, 0.35, 0.24), (-0.75, 0.6, 0.22), (0.35, -0.8, 0.18)]),
    hills=[(0.0, -0.6, 0.4, 12.0), (-0.55, -0.2, 0.3, 7.0), (0.55, 0.1, 0.3, 4.5),
           (-0.1, 0.5, 0.35, 2.0)],
    ridges=[
        ([(0.0, -0.45), (0.8, -0.55), (0.95, -0.3)], 9.0, 0.1, 1.8),
        ([(-0.95, -0.3), (-0.7, -0.5), (-0.2, -0.6)], 8.0, 0.1, 1.7),
        ([(0.15, 0.28), (0.28, 0.1), (0.25, -0.16), (0.2, -0.34)], 6.0, 0.09, 2.0),
    ],
    pads=[
        (0.0, 0.56, 0.19, 4.0), (-0.08, 0.08, 0.11, 7.2), (0.02, 0.2, 0.08, 6.4),
        (0.2, -0.3, 0.1, 13.2), (0.0, -0.7, 0.13, 21.5), (0.45, 0.18, 0.13, 5.6),
        (0.15, 0.47, 0.09, 4.2), (0.06, -0.44, 0.08, 15.8),
        (0.0, 0.56, 0.27, 6.0),
    ],
    basins=[
        (-0.08, 0.08, 0.1, 1.6), (0.45, 0.18, 0.15, 1.0), (0.06, 0.28, 0.035, 0.8),
    ],
    roads=[
        dict(width=4.6, pts=[
            (0.0, 0.62, 6.0, 4.4), (0.02, 0.53, 5.8, 4.2), (-0.02, 0.43, 5.2, 3.8),
            (0.03, 0.34, 4.9, 3.4), (0.05, 0.25, 5.4, 3.2), (0.02, 0.18, 5.8, 3.4),
            (0.0, 0.12, 6.2, 3.8), (-0.04, 0.06, 6.9, 4.2), (0.02, -0.01, 7.8, 3.6),
            (0.06, -0.1, 9.0, 3.2), (0.1, -0.2, 10.6, 3.0), (0.15, -0.29, 12.2, 3.0),
            (0.14, -0.38, 13.8, 3.2), (0.1, -0.47, 15.6, 3.2), (0.05, -0.56, 17.7, 3.6),
            (0.01, -0.65, 20.0, 4.0), (0.0, -0.7, 21.5, 4.6),
        ]),
        dict(width=3.0, pts=[
            (0.02, 0.53, 4.0, 3.4), (0.15, 0.48, 4.1, 3.0), (0.28, 0.4, 4.0, 2.8),
        ]),
        dict(width=2.8, pts=[
            (0.0, 0.18, 5.8, 3.0), (0.18, 0.2, 5.7, 2.8), (0.35, 0.19, 5.6, 2.7),
            (0.5, 0.15, 5.6, 3.0),
        ]),
        dict(width=2.4, pts=[
            (0.06, 0.08, 6.9, 2.8), (-0.2, 0.02, 8.0, 2.5), (-0.42, -0.04, 9.4, 2.4),
            (-0.55, -0.1, 10.6, 2.8),
        ]),
        dict(width=2.2, pts=[
            (0.15, -0.29, 12.2, 2.4), (0.28, -0.3, 12.6, 2.2), (0.36, -0.34, 12.8, 2.6),
        ]),
    ],
    chasms=[],
    bridges=[
        dict(x=0.045, z=0.17, span=9.5, width=3.0, type="stone_bridge", depth=10.0),
        dict(x=0.13, z=-0.41, span=10.0, width=2.8, type="rope_bridge", depth=14.0),
    ],
    water=[
        dict(x=-0.08, z=0.08, level=7.15, r=0.07, depth=1.2, style="hotspring"),
        dict(x=0.45, z=0.18, level=5.7, r=0.13, depth=1.0, style="frozen_lake"),
        dict(x=0.06, z=0.28, level=5.15, r=0.03, depth=0.5, style="creek"),
    ],
    hand_props=[
        dict(t="wooden_cabin", x=-0.24, z=0.64, rot=12, s=1.0, col="box"),
        dict(t="wooden_cabin", x=0.27, z=0.59, rot=-62, s=0.92, col="box"),
        dict(t="wooden_cabin", x=-0.32, z=0.49, rot=95, s=0.85, col="box"),
        dict(t="well", x=0.03, z=0.48, rot=0, s=0.9, col="cyl"),
        dict(t="signpost", x=0.02, z=0.3, rot=-15, s=1.0, col="cyl"),
        dict(t="signpost", x=0.06, z=-0.08, rot=25, s=0.9, col="cyl"),
        dict(t="lighthouse", x=0.02, z=-0.725, rot=0, s=1.0, col="box"),
        dict(t="ruin_pillar", x=-0.3, z=0.15, rot=30, s=0.9, col="cyl"),
        dict(t="ruin_pillar", x=-0.24, z=0.22, rot=-10, s=0.7, col="cyl"),
        dict(t="memory_shard", x=0.2, z=0.49, rot=100, s=1.0, col="box"),
        dict(t="memory_shard", x=0.1, z=-0.43, rot=200, s=1.0, col="box"),
        dict(t="paper_lantern", x=0.1, z=0.54, rot=0, s=1.0, col="none", y_off=2.8),
        dict(t="paper_lantern", x=-0.04, z=0.55, rot=0, s=0.9, col="none", y_off=2.6),
        dict(t="ice_crystal", x=0.52, z=0.12, rot=10, s=1.2, col="none"),
        dict(t="ice_crystal", x=0.4, z=0.24, rot=70, s=1.0, col="none"),
    ],
    embers=[
        dict(x=-0.12, z=0.12, name="泉边余烬"),
        dict(x=0.36, z=-0.34, name="冰瀑余烬", secret=True),
        dict(x=-0.5, z=-0.12, name="松岭余烬", secret=True),
        dict(x=0.3, z=0.44, name="雪村余烬"),
        dict(x=0.44, z=0.24, name="冰湖余烬"),
    ],
    npcs=[
        dict(id="xiaoman", name="小满", x=0.15, z=0.555, rot=180,
             memory="memory_5_waiting", lines=lines_xiaoman()),
        dict(id="laozhou", name="老周", x=0.07, z=-0.43, rot=10,
             memory="memory_6_storm", lines=lines_laozhou()),
    ],
    zones=[
        dict(name="雪村", x=0.0, z=0.56, r=0.16),
        dict(name="冻溪石桥", x=0.045, z=0.17, r=0.09),
        dict(name="温泉谷", x=-0.06, z=0.07, r=0.1),
        dict(name="松岭", x=0.1, z=-0.08, r=0.12),
        dict(name="冰瀑", x=0.2, z=-0.3, r=0.11),
        dict(name="断塔山脊", x=0.0, z=-0.7, r=0.15),
    ],
    spawn=dict(x=0.0, z=0.62, h=6.0, yaw=0.0),
    beacon=dict(x=0.0, z=-0.665, rot=0),
    scatter=[
        dict(t="pine_tree_a", count=82, sep=4.4, path_dist=5.0, clear=3.2, slope=0.55,
             cluster=0.45, cluster_threshold=0.02, scale=[0.75, 1.25], col="cyl"),
        dict(t="pine_tree_b", count=55, sep=4.0, path_dist=4.4, clear=3.0, slope=0.6,
             cluster=0.4, cluster_threshold=-0.05, scale=[0.8, 1.25], col="cyl"),
        dict(t="snow_bush", count=100, sep=2.6, path_dist=2.8, clear=1.6, slope=0.65,
             scale=[0.7, 1.2], col="none"),
        dict(t="bare_tree", count=34, sep=5.2, path_dist=4.0, clear=2.6, slope=0.55,
             scale=[0.8, 1.25], col="cyl"),
        dict(t="ice_crystal", count=40, sep=3.2, path_dist=2.6, clear=1.4, slope=0.7,
             scale=[0.7, 1.3], col="none"),
        dict(t="rock_a", count=40, sep=4.4, path_dist=3.0, clear=2.0, slope=0.8,
             scale=[0.7, 1.3], col="cyl"),
        dict(t="rock_b", count=60, sep=2.8, path_dist=2.0, clear=1.4, slope=0.85,
             scale=[0.7, 1.4], col="none"),
        dict(t="stump", count=14, sep=6.0, path_dist=3.0, clear=2.0, slope=0.5,
             scale=[0.8, 1.1], col="none"),
    ],
    multi=[
        dict(t="grass_tuft", count=1300, path_dist=1.2, slope=0.9, clear=0.3,
             scale=[0.6, 1.2]),
        dict(t="flower_snow", count=220, path_dist=1.6, slope=0.7, clear=0.3,
             scale=[0.7, 1.1]),
    ],
    env=dict(
        sky_top="#6E93B4", sky_horizon="#D7E4E2", sky_bottom="#4D6D7A",
        sun_color="#CFE2ED", sun_energy=1.15, sun_angle=(-24, -46),
        ambient="#AFC6D2", ambient_energy=0.8, fog="#C6D7DC", fog_density=0.008,
        glow=0.95, saturation=0.92, exposure=1.1, star=0.25, aurora=0.55,
        petals="#E8F2F2", motes="#FFFFFF",
    ),
    camera=dict(yaw=-35.0, pitch=-37.0, distance=19.0, fov=42.0),
    preview=dict(base=(198, 213, 214), rock=(116, 130, 134), water=(128, 190, 198), road=(224, 230, 226)),
    palette=dict(
        grass_a="#B7CBC6", grass_b="#D5E2DD", grass_c="#EAF1EC", dirt="#B0BDB9",
        rock="#7C8D8D", rock_dark="#5C6E70", path="#D8E0DB", path_dark="#B8C6C2",
        water="#6FA9B2", shore="#E3ECE8", accent="#F2B15E",
    ),
)

CH4 = dict(
    id="ch4", num=4, terrace=1.2, title="星坠之穹 · 归夜", en="Starfall", seed=404,
    base=3.0, noise=1.8, broad=2.0,
    island=dict(type="blobs", blobs=[
        (0.0, 0.55, 0.34, 0.26), (0.1, 0.3, 0.28, 0.24), (0.0, 0.03, 0.34, 0.26),
        (0.12, -0.26, 0.28, 0.22), (0.0, -0.6, 0.32, 0.26), (-0.35, 0.13, 0.19, 0.17),
        (0.42, -0.32, 0.18, 0.17),
    ]),
    hills=[(0.0, -0.58, 0.3, 13.0), (0.1, -0.25, 0.18, 5.0), (-0.35, 0.12, 0.12, 2.0)],
    ridges=[
        ([(-0.35, 0.25), (-0.3, 0.0), (-0.2, -0.2)], 5.0, 0.08, 2.0),
        ([(0.38, 0.0), (0.42, -0.2), (0.36, -0.4)], 5.0, 0.08, 2.0),
    ],
    pads=[
        (0.0, 0.55, 0.11, 3.6), (0.1, 0.3, 0.1, 5.6), (0.0, 0.03, 0.13, 7.0),
        (0.12, -0.26, 0.11, 9.8), (0.0, -0.6, 0.11, 19.6), (-0.35, 0.13, 0.08, 4.6),
        (0.42, -0.32, 0.08, 14.8), (0.14, -0.45, 0.07, 13.2),
    ],
    basins=[
        (0.0, 0.03, 0.12, 1.2), (0.1, 0.3, 0.06, 0.8),
    ],
    roads=[
        dict(width=4.2, pts=[
            (0.0, 0.55, 6.0, 4.0), (0.05, 0.46, 5.6, 3.4), (0.1, 0.38, 5.0, 3.0),
            (0.12, 0.3, 5.6, 2.8), (0.11, 0.22, 6.2, 2.6), (0.07, 0.14, 6.6, 2.8),
            (0.0, 0.07, 6.9, 3.2), (0.01, 0.0, 7.0, 3.6), (0.05, -0.08, 7.6, 3.0),
            (0.1, -0.17, 8.6, 2.8), (0.13, -0.25, 9.8, 3.0), (0.17, -0.32, 11.4, 2.8),
            (0.16, -0.39, 12.8, 2.7), (0.12, -0.47, 14.4, 2.8), (0.06, -0.54, 16.7, 3.0),
            (0.02, -0.6, 18.8, 3.2), (0.0, -0.62, 19.6, 4.2),
        ]),
        dict(width=2.6, pts=[
            (0.0, 0.07, 6.9, 2.8), (-0.16, 0.09, 6.6, 2.4), (-0.35, 0.13, 5.2, 2.4),
            (-0.45, 0.18, 4.8, 2.8),
        ]),
        dict(width=2.4, pts=[
            (0.13, -0.25, 9.8, 2.6), (0.28, -0.29, 11.2, 2.3), (0.42, -0.32, 14.8, 2.8),
        ]),
    ],
    chasms=[],
    bridges=[
        dict(x=0.105, z=0.26, span=11.0, width=3.0, type="stone_bridge", depth=25.0),
        dict(x=0.145, z=-0.285, span=10.5, width=3.0, type="rope_bridge", depth=25.0),
        dict(x=0.04, z=-0.5, span=11.5, width=3.0, type="stone_bridge", depth=24.0),
        dict(x=-0.22, z=0.11, span=9.5, width=2.6, type="rope_bridge", depth=22.0),
        dict(x=0.3, z=-0.28, span=9.5, width=2.5, type="rope_bridge", depth=22.0),
    ],
    water=[
        dict(x=0.0, z=0.03, level=6.35, r=0.095, depth=1.0, style="mirror"),
        dict(x=0.1, z=0.3, level=5.0, r=0.05, depth=0.7, style="pond"),
    ],
    hand_props=[
        dict(t="lighthouse", x=0.0, z=-0.7, rot=6, s=1.0, col="box"),
        dict(t="whale_ribs", x=0.11, z=-0.24, rot=66, s=1.0, col="none"),
        dict(t="big_cherry", x=0.1, z=0.33, rot=60, s=1.15, col="cyl"),
        dict(t="ruin_pillar", x=-0.1, z=0.02, rot=20, s=1.0, col="cyl"),
        dict(t="ruin_pillar", x=0.1, z=0.08, rot=-15, s=0.85, col="cyl"),
        dict(t="ruin_pillar", x=0.0, z=-0.02, rot=80, s=0.7, col="cyl"),
        dict(t="torii_gate", x=0.11, z=-0.22, rot=58, s=0.9, col="box"),
        dict(t="signpost", x=0.02, z=0.16, rot=20, s=0.9, col="cyl"),
        dict(t="memory_shard", x=0.22, z=0.0, rot=0, s=1.0, col="box"),
        dict(t="paper_lantern", x=-0.3, z=0.1, rot=0, s=1.0, col="none", y_off=2.6),
        dict(t="paper_lantern", x=-0.4, z=0.2, rot=0, s=0.9, col="none", y_off=3.4),
        dict(t="paper_lantern", x=0.46, z=-0.3, rot=0, s=1.0, col="none", y_off=2.8),
    ],
    embers=[
        dict(x=0.18, z=0.36, name="萤庭余烬"),
        dict(x=-0.05, z=-0.02, name="镜湖余烬"),
        dict(x=0.24, z=-0.3, name="鲸骨余烬"),
        dict(x=-0.44, z=0.15, name="孤岛余烬", secret=True),
        dict(x=0.46, z=-0.34, name="星阶余烬", secret=True),
    ],
    npcs=[
        dict(id="aying", name="阿萤", x=0.0, z=-0.59, rot=180,
             memory="memory_7_reunion", lines=lines_aying()),
        dict(id="bell", name="鲸骨钟", x=0.06, z=-0.2, rot=45,
             memory="memory_8_lanterns", lines=lines_bell()),
    ],
    zones=[
        dict(name="星落滩", x=0.0, z=0.55, r=0.1),
        dict(name="萤光庭", x=0.1, z=0.3, r=0.1),
        dict(name="虹桥", x=0.105, z=0.26, r=0.08),
        dict(name="镜湖", x=0.0, z=0.03, r=0.13),
        dict(name="鲸骨门", x=0.11, z=-0.24, r=0.11),
        dict(name="螺旋星阶", x=0.13, z=-0.4, r=0.1),
        dict(name="断塔之巅", x=0.0, z=-0.62, r=0.14),
    ],
    spawn=dict(x=0.0, z=0.55, h=6.0, yaw=0.0),
    beacon=dict(x=0.0, z=-0.64, rot=0),
    scatter=[
        dict(t="glow_tree", count=46, sep=4.0, path_dist=4.2, clear=2.8, slope=0.55,
             cluster=0.4, cluster_threshold=0.0, scale=[0.8, 1.25], col="cyl"),
        dict(t="glow_mushroom", count=85, sep=2.2, path_dist=2.4, clear=1.2, slope=0.65,
             scale=[0.7, 1.4], col="none"),
        dict(t="crystal_cluster", count=50, sep=3.0, path_dist=2.6, clear=1.6, slope=0.7,
             scale=[0.7, 1.3], col="none"),
        dict(t="bare_tree", count=22, sep=5.0, path_dist=4.0, clear=2.6, slope=0.6,
             scale=[0.8, 1.2], col="cyl"),
        dict(t="rock_a", count=40, sep=4.0, path_dist=3.0, clear=2.0, slope=0.8,
             scale=[0.7, 1.4], col="cyl"),
        dict(t="rock_b", count=50, sep=2.8, path_dist=2.0, clear=1.3, slope=0.85,
             scale=[0.7, 1.4], col="none"),
        dict(t="floating_rock", count=7, sep=8.0, path_dist=4.0, clear=3.0, slope=0.9,
             scale=[0.7, 1.2], col="none", water_dist=0.5),
        dict(t="ruin_pillar", count=14, sep=4.0, path_dist=2.6, clear=1.2, slope=0.65,
             scale=[0.7, 1.2], col="cyl"),
    ],
    multi=[
        dict(t="glow_grass", count=2300, path_dist=1.2, slope=0.9, clear=0.3,
             scale=[0.6, 1.4]),
        dict(t="flower_night", count=600, path_dist=1.6, slope=0.8, clear=0.3,
             scale=[0.7, 1.3]),
    ],
    env=dict(
        sky_top="#151932", sky_horizon="#4B4A78", sky_bottom="#101322",
        sun_color="#D9C6FF", sun_energy=0.55, sun_angle=(-18, -55),
        ambient="#6B6DA8", ambient_energy=0.65, fog="#2A2E51", fog_density=0.009,
        glow=1.3, saturation=1.06, exposure=1.08, star=0.9, aurora=0.85,
        petals="#9FE6DC", motes="#F6D98E",
    ),
    camera=dict(yaw=-34.0, pitch=-36.0, distance=19.0, fov=42.0),
    preview=dict(base=(101, 91, 128), rock=(66, 62, 88), water=(62, 136, 140), road=(155, 134, 139)),
    palette=dict(
        grass_a="#4A4A70", grass_b="#5C5A82", grass_c="#747092", dirt="#5F586F",
        rock="#56506F", rock_dark="#3C3A54", path="#857A92", path_dark="#6C6179",
        water="#3C8E95", shore="#7A7A9B", accent="#72D6CD",
    ),
)


# ---------------------------------------------------------------------------
# art-direction tuning (applied after the literal chapter definitions)
# ---------------------------------------------------------------------------

TUNING = {
    "ch1": dict(
        env=dict(
            sky_top="#6E9F9B", sky_horizon="#F5DCB4", sky_bottom="#3F6E68",
            sun_color="#FFE2AE", sun_energy=2.1, sun_angle=(-38.0, -40.0),
            ambient="#9B9A82", ambient_energy=0.5, fog="#D6D4BD", fog_density=0.0016,
            glow=0.55, saturation=1.08, exposure=1.0, star=0.0, aurora=0.0,
            petals="#F3C9C5", motes="#FFF0C4",
        ),
        camera=dict(yaw=-36.0, pitch=-26.0, distance=15.0, fov=50.0),
        palette=dict(
            grass_a="#4C734B", grass_b="#6B9255", grass_c="#8FAA64", dirt="#A98D62",
            rock="#6E7A68", rock_dark="#4E5B50", path="#A38D66", path_dark="#85714F",
            water="#3D847F", shore="#CDBB92", accent="#E39A9A",
        ),
        scatter={"cherry_tree_a": 96, "cherry_tree_b": 82, "bamboo_cluster": 40,
                 "azalea_bush": 132, "fern": 180, "rock_a": 65, "rock_b": 95},
        multi={"grass_tuft": 4200, "flower_spring_a": 720, "flower_spring_b": 500},
    ),
    "ch2": dict(
        env=dict(
            sky_top="#D89B55", sky_horizon="#FFD89A", sky_bottom="#A95F3F",
            sun_color="#FFC57A", sun_energy=2.4, sun_angle=(-26.0, -52.0),
            ambient="#A87F5E", ambient_energy=0.45, fog="#DCC49E", fog_density=0.0018,
            glow=0.6, saturation=1.1, exposure=1.0, star=0.0, aurora=0.0,
            petals="#F0C27C", motes="#FFE0A0",
        ),
        camera=dict(yaw=-38.0, pitch=-26.5, distance=15.5, fov=50.0),
        palette=dict(
            grass_a="#B08B4E", grass_b="#C6A45D", grass_c="#D8B970", dirt="#B2794E",
            rock="#9E5C3F", rock_dark="#75412F", path="#C3A16B", path_dark="#9A7A4E",
            water="#2F7F7A", shore="#E4CB94", accent="#E09156",
        ),
        scatter={"palm_tree": 62, "desert_shrub": 220, "cactus": 46, "reeds": 80,
                 "rock_a": 80, "rock_b": 120, "driftwood": 42},
        multi={"grass_tuft": 1500, "flower_desert": 360},
    ),
    "ch3": dict(
        env=dict(
            sky_top="#547A9A", sky_horizon="#C9DADF", sky_bottom="#3E5D6B",
            sun_color="#CFE3EE", sun_energy=1.5, sun_angle=(-22.0, -46.0),
            ambient="#8E9FA6", ambient_energy=0.5, fog="#C9D5D8", fog_density=0.002,
            glow=0.7, saturation=1.0, exposure=1.02, star=0.2, aurora=0.6,
            petals="#E8F2F2", motes="#FFFFFF",
        ),
        camera=dict(yaw=-35.0, pitch=-26.0, distance=15.0, fov=50.0),
        palette=dict(
            grass_a="#A9C0BC", grass_b="#C6D8D2", grass_c="#E1EBE5", dirt="#9FAEAC",
            rock="#6D8082", rock_dark="#506469", path="#B4C2BC", path_dark="#8FA09C",
            water="#5A959F", shore="#D5E4DF", accent="#F0AE5B",
        ),
        scatter={"pine_tree_a": 125, "pine_tree_b": 92, "snow_bush": 185, "bare_tree": 52,
                 "ice_crystal": 62, "rock_a": 60, "rock_b": 100},
        multi={"grass_tuft": 1700, "flower_snow": 300},
    ),
    "ch4": dict(
        env=dict(
            sky_top="#0E1228", sky_horizon="#3A3A62", sky_bottom="#090C18",
            sun_color="#CDBBFF", sun_energy=0.7, sun_angle=(-16.0, -55.0),
            ambient="#4F527F", ambient_energy=0.52, fog="#202544", fog_density=0.0022,
            glow=1.05, saturation=1.12, exposure=1.05, star=1.0, aurora=0.9,
            petals="#9FE6DC", motes="#F6D98E",
        ),
        camera=dict(yaw=-34.0, pitch=-25.5, distance=15.5, fov=51.0),
        palette=dict(
            grass_a="#3E3F60", grass_b="#514E74", grass_c="#676184", dirt="#4A4459",
            rock="#49425F", rock_dark="#2F2C44", path="#6A5E77", path_dark="#51465F",
            water="#2E707D", shore="#67678A", accent="#6FCBC4",
        ),
        scatter={"glow_tree": 72, "glow_mushroom": 145, "crystal_cluster": 82,
                 "bare_tree": 42, "rock_a": 60, "rock_b": 85, "floating_rock": 10,
                 "ruin_pillar": 24},
        multi={"glow_grass": 2800, "flower_night": 700},
    ),
}

CHAPTERS = [CH1, CH2, CH3, CH4]

for _cfg in CHAPTERS:
    _t = TUNING.get(_cfg["id"], {})
    if "env" in _t:
        _cfg["env"].update(_t["env"])
    if "camera" in _t:
        _cfg["camera"].update(_t["camera"])
    if "palette" in _t:
        _cfg["palette"].update(_t["palette"])
    for _sc in _cfg.get("scatter", []):
        if _sc["t"] in _t.get("scatter", {}):
            _sc["count"] = _t["scatter"][_sc["t"]]
    for _m in _cfg.get("multi", []):
        if _m["t"] in _t.get("multi", {}):
            _m["count"] = _t["multi"][_m["t"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview-only", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    for cfg in CHAPTERS:
        if only and cfg["id"] not in only:
            continue
        print(f"building {cfg['id']} {cfg['title']}")
        w = World(cfg)
        w.build()
        prev = SHOTS / f"{cfg['id']}_topdown.png"
        w.preview(prev)
        print(f"  preview -> {prev}")
        if not args.preview_only:
            out = DATA / f"{cfg['id']}.json"
            payload = w.output()
            out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print(f"  data -> {out} ({out.stat().st_size/1024:.0f} KB), "
                  f"props {len(payload['props'])}, multi {sum(len(m['p']) for m in payload['multi'])}")
        # combined sheet
        if not only:
            pass


if __name__ == "__main__":
    main()

