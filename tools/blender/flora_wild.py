# -*- coding: utf-8 -*-
"""flora_wild -- low-poly foliage for Amberreach (ch.2), Frostvale (ch.3) and Starfall (ch.4).

Ten assets, all built procedurally, flat shaded, one joined mesh each, origin at the
bottom-centre, front toward Blender -Y.  GLBs go to assets/models/foliage/, previews to
assets/previews/flora_wild/, plus a 4-column contact sheet.

Run (build + export + renders + manifest + contact sheet):
    blender.exe -b --python tools/blender/flora_wild.py
Iterate on a subset without rendering:
    blender.exe -b --python tools/blender/flora_wild.py -- --only palm_tree,pine_tree_a --skip-render
Build only the contact sheet (uses the Pillow-enabled python from the asset brief):
    python.exe tools/blender/flora_wild.py --contact-sheet
"""

import json
import math
import os
import random
import subprocess
import sys

try:
    import bpy
    import bmesh
    from mathutils import Vector, Matrix
    HAS_BPY = True
except Exception:  # running outside Blender, only the contact-sheet path works
    bpy = None
    bmesh = None
    Vector = None
    Matrix = None
    HAS_BPY = False

TAU = math.pi * 2.0

ROOT = r"E:\GodotProjects\xiang-ting-game"
MODEL_DIR = os.path.join(ROOT, "assets", "models", "foliage")
PREVIEW_DIR = os.path.join(ROOT, "assets", "previews", "flora_wild")
MANIFEST_PATH = os.path.join(MODEL_DIR, "manifest_flora_wild.json")
SHEET_PATH = os.path.join(PREVIEW_DIR, "contact_sheet.png")
PY_EXE = r"C:\Users\32506\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

BEIGE = (237, 230, 218)


# --------------------------------------------------------------------------------------
# palette / materials
# --------------------------------------------------------------------------------------

MAT_SPEC = {
    # Amberreach
    "Bark_Palm":       {"color": "#8A6B4C", "rough": 0.90},
    "Leaf_Palm":       {"color": "#5E7D4E", "rough": 0.86},
    "Coconut":         {"color": "#6B4C33", "rough": 0.92},
    "Bark_Shrub":      {"color": "#B08B57", "rough": 0.95},
    "Leaf_Dry":        {"color": "#8F6B3C", "rough": 0.95},
    "Cactus_Body":     {"color": "#4F7058", "rough": 0.88},
    "Cactus_Ridge":    {"color": "#B7CFAB", "rough": 0.84},
    "Grass_Reed":      {"color": "#A6B468", "rough": 0.88},
    "Grass_Reed_Dark": {"color": "#8A9A52", "rough": 0.90},
    "Grass_Cattail":   {"color": "#7F8D4A", "rough": 0.90},
    "Cattail_Head":    {"color": "#7A5334", "rough": 0.92},
    # Frostvale
    "Leaf_Pine":       {"color": "#2F5450", "rough": 0.88},
    "Leaf_Pine_Light": {"color": "#47706A", "rough": 0.88},
    "Bark_Pine":       {"color": "#5B4A3E", "rough": 0.93},
    "Leaf_SnowBush":   {"color": "#355B54", "rough": 0.88},
    "Bark_Bare":       {"color": "#6B6055", "rough": 0.94},
    "Bark_Bare_Dark":  {"color": "#564C43", "rough": 0.94},
    "Snow":            {"color": "#ECF2EF", "rough": 0.86},
    "Snow_Deep":       {"color": "#D3E0DF", "rough": 0.88},
    "Ice":             {"color": "#B8D9DF", "rough": 0.78, "emission": "#B8D9DF", "strength": 0.5},
    "Ice_Deep":        {"color": "#9CC4CD", "rough": 0.80, "emission": "#9CC4CD", "strength": 0.35},
    # Starfall
    "Grass_Base":      {"color": "#3D7274", "rough": 0.88},
    "Grass_Glow":      {"color": "#4FD3CC", "rough": 0.80, "emission": "#2FBFB9", "strength": 2.0},
    # preview only
    "Preview_Ground":  {"color": "#C9C0AF", "rough": 0.95},
}


def hex_to_linear(hexstr):
    h = hexstr.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        c = c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        out.append(c)
    return (out[0], out[1], out[2], 1.0)


def new_material(name):
    spec = MAT_SPEC[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = None
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            bsdf = n
            break
    if bsdf is None:
        raise RuntimeError("no Principled BSDF on material " + name)
    bsdf.inputs["Base Color"].default_value = hex_to_linear(spec["color"])
    bsdf.inputs["Roughness"].default_value = spec.get("rough", 0.88)
    bsdf.inputs["Metallic"].default_value = 0.0
    if "emission" in spec:
        ecol = hex_to_linear(spec["emission"])
        for key in ("Emission Color", "Emission"):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = ecol
                break
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = spec.get("strength", 1.0)
    mat.use_backface_culling = False
    mat.diffuse_color = hex_to_linear(spec["color"])
    return mat


# --------------------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------------------

class Builder:
    """Accumulates verts / faces / per-face material names for one asset."""

    def __init__(self):
        self.verts = []
        self.faces = []
        self.face_mats = []

    def add(self, verts, faces, mats):
        if not faces:
            return
        if isinstance(mats, str):
            mats = [mats] * len(faces)
        if len(mats) != len(faces):
            raise ValueError("materials/faces length mismatch")
        off = len(self.verts)
        self.verts.extend(Vector(v) for v in verts)
        for f, m in zip(faces, mats):
            if len(f) < 3:
                continue
            if len(set(f)) < 3:
                continue
            self.faces.append(tuple(off + i for i in f))
            self.face_mats.append(m)


def frames_for(pts):
    frames = []
    n = len(pts)
    for i in range(n):
        if n == 1:
            t = Vector((0, 0, 1))
        elif i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        if t.length < 1e-9:
            t = Vector((0, 0, 1))
        t.normalize()
        ref = Vector((0, 0, 1)) if abs(t.z) < 0.92 else Vector((0, 1, 0))
        right = t.cross(ref)
        if right.length < 1e-7:
            right = Vector((1, 0, 0))
        right.normalize()
        up = right.cross(t).normalized()
        frames.append((t, right, up))
    return frames


def tube(mb, pts, radii, sides, mat, cap_start=False, cap_end=True,
         phase=0.0, jitter=0.0, seed=0):
    pts = [Vector(p) for p in pts]
    if len(pts) < 2:
        return
    frames = frames_for(pts)
    verts = []
    rings = []
    for i, (p, r) in enumerate(zip(pts, radii)):
        _t, right, up = frames[i]
        ring = []
        for k in range(sides):
            a = phase + TAU * k / sides
            rr = max(1e-4, r * (1.0 + jitter * math.sin(k * 2.0 + i * 1.7 + seed)))
            ring.append(len(verts))
            verts.append(p + right * (math.cos(a) * rr) + up * (math.sin(a) * rr))
        rings.append(ring)
    faces = []
    for i in range(len(pts) - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            faces.append((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
    if cap_start:
        ci = len(verts)
        verts.append(pts[0])
        for k in range(sides):
            faces.append((rings[0][(k + 1) % sides], rings[0][k], ci))
    if cap_end:
        ci = len(verts)
        verts.append(pts[-1])
        for k in range(sides):
            faces.append((rings[-1][k], rings[-1][(k + 1) % sides], ci))
    mb.add(verts, faces, mat)


_ICO_CACHE = {}


def ico_template():
    if "v" in _ICO_CACHE:
        return _ICO_CACHE["v"], _ICO_CACHE["f"]
    phi = (1.0 + 5.0 ** 0.5) / 2.0
    verts = [
        (-1, phi, 0), (1, phi, 0), (-1, -phi, 0), (1, -phi, 0),
        (0, -1, phi), (0, 1, phi), (0, -1, -phi), (0, 1, -phi),
        (phi, 0, -1), (phi, 0, 1), (-phi, 0, -1), (-phi, 0, 1),
    ]
    verts = [tuple(Vector(v).normalized()) for v in verts]
    faces = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    ]
    _ICO_CACHE["v"] = verts
    _ICO_CACHE["f"] = faces
    return verts, faces


def add_ico(mb, center, scale, mat, seed=0, yaw=0.0, jitter=0.12):
    center = Vector(center)
    base_v, base_f = ico_template()
    rng = random.Random(seed)
    rot = Matrix.Rotation(yaw, 3, "Z")
    verts = []
    for x, y, z in base_v:
        rr = 1.0 + rng.uniform(-jitter, jitter)
        v = Vector((x * rr, y * rr, z * rr))
        v = Vector((v.x * scale[0], v.y * scale[1], v.z * scale[2]))
        verts.append(center + (rot @ v))
    faces = []
    for f in base_f:
        a, b, c = verts[f[0]], verts[f[1]], verts[f[2]]
        n = (b - a).cross(c - a)
        if n.dot((a + b + c) / 3.0 - center) < 0:
            f = (f[0], f[2], f[1])
        faces.append(f)
    mb.add(verts, faces, mat)


def add_snow_lump(mb, center, radius, height, sides=5, seed=0, mat="Snow"):
    """Faceted, angular snow clump: irregular base ring -> irregular top ring -> peak."""
    center = Vector(center)
    rng = random.Random(seed)
    ang0 = rng.uniform(0.0, TAU)
    bot = []
    top = []
    for k in range(sides):
        a = ang0 + TAU * k / sides
        rb = radius * rng.uniform(0.78, 1.14)
        bot.append(center + Vector((math.cos(a) * rb, math.sin(a) * rb, 0.0)))
    top_h = []
    for k in range(sides):
        a = ang0 + TAU * k / sides + rng.uniform(-0.13, 0.13)
        rt = radius * rng.uniform(0.42, 0.80)
        h = height * rng.uniform(0.60, 1.15)
        top_h.append(h)
        top.append(center + Vector((math.cos(a) * rt, math.sin(a) * rt, h)))
    peak_h = max(top_h) * 1.04 + 0.008
    peak = center + Vector((radius * rng.uniform(-0.10, 0.10),
                            radius * rng.uniform(-0.10, 0.10),
                            peak_h))
    verts = bot + top + [peak]
    faces = []
    for k in range(sides):
        k2 = (k + 1) % sides
        faces.append((k, k2, sides + k2, sides + k))
    for k in range(sides):
        faces.append((sides + k, sides + ((k + 1) % sides), 2 * sides))
    mb.add(verts, faces, mat)


def add_mound(mb, cx, cy, radius, height, sides, seed, mat, top_ratio=0.45):
    """Low irregular faceted mound sitting on z=0 (snow bed / soil clump)."""
    rng = random.Random(seed)
    ang0 = rng.uniform(0.0, TAU)
    bot = []
    mid = []
    for k in range(sides):
        a = ang0 + TAU * k / sides
        rr = radius * rng.uniform(0.84, 1.12)
        bot.append(Vector((cx + math.cos(a) * rr, cy + math.sin(a) * rr, 0.0)))
    for k in range(sides):
        a = ang0 + TAU * k / sides
        rr = radius * top_ratio * rng.uniform(0.78, 1.12)
        botz = height * (0.55 + rng.uniform(-0.05, 0.10))
        mid.append(Vector((cx + math.cos(a) * rr, cy + math.sin(a) * rr, botz)))
    top = Vector((cx, cy, height))
    verts = bot + mid + [top]
    faces = []
    for k in range(sides):
        k2 = (k + 1) % sides
        faces.append((k, k2, sides + k2, sides + k))
    for k in range(sides):
        faces.append((sides + k, sides + ((k + 1) % sides), 2 * sides))
    mb.add(verts, faces, mat)


def add_dry_leaf(mb, pos, length, width, az, pitch, mat="Leaf_Dry"):
    pos = Vector(pos)
    d = Vector((math.cos(az), math.sin(az), 0.0))
    side = Vector((-math.sin(az), math.cos(az), 0.0))
    tip = pos + d * (length * math.cos(pitch)) + Vector((0, 0, length * math.sin(pitch)))
    left = pos + side * width
    right = pos - side * width
    verts = [left, right, tip, pos + Vector((0, 0, 0.004))]
    faces = [(0, 1, 2), (0, 2, 3)]
    mb.add(verts, faces, mat)


# --------------------------------------------------------------------------------------
# 1. palm_tree
# --------------------------------------------------------------------------------------

def build_palm_tree(mb):
    H = 6.95
    rng = random.Random(101)
    n = 15
    pts = []
    radii = []
    for i in range(n):
        t = i / (n - 1)
        z = H * t
        # S-curved, leaning toward -Y; extra +X drift keeps the curve readable in 3/4
        y = -0.03 * t - 0.66 * (t ** 2.5)
        x = 0.34 * math.sin(1.35 * t) + 0.055 * math.sin(6.2 * t) * t
        pts.append(Vector((x, y, z)))
        base = 0.285 - 0.100 * t
        ring = 0.016 * math.sin(t * math.pi * 12.0) + 0.006
        crown = 0.030 * max(0.0, (t - 0.80) / 0.20)
        radii.append(base + ring + crown)
    tube(mb, pts, radii, 7, "Bark_Palm", cap_start=True, cap_end=True, jitter=0.06, seed=3)

    # root flare spurs, tips flat on the ground
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2 + 0.14 * k
        tube(mb,
             [Vector((0.05 * math.cos(a), 0.05 * math.sin(a), 0.28)),
              Vector((0.28 * math.cos(a), 0.28 * math.sin(a), 0.10)),
              Vector((0.48 * math.cos(a), 0.48 * math.sin(a), 0.0))],
             [0.078, 0.055, 0.020], 4, "Bark_Palm", cap_start=False, cap_end=True)

    top = pts[-1]
    # green crown collar
    tube(mb,
         [top + Vector((0, 0, -0.03)), top + Vector((0, 0, 0.11)), top + Vector((0, 0, 0.22))],
         [0.190, 0.155, 0.045], 7, "Leaf_Palm", cap_start=False, cap_end=True)

    # seven radial fronds: narrow folded rachis + feather leaflets
    for i in range(7):
        az = -math.pi / 2 + i * TAU / 7 + rng.uniform(-0.16, 0.16)
        L = rng.uniform(2.65, 3.35)
        upbias = rng.uniform(0.35, 0.74)
        droop = rng.uniform(0.54, 0.82)
        d = Vector((math.cos(az), math.sin(az), 0.0))
        side = Vector((-math.sin(az), math.cos(az), 0.0))
        base = top + Vector((math.cos(az) * 0.10, math.sin(az) * 0.10,
                             0.17 + 0.02 * i))
        stations = 11
        spines = []
        for j in range(stations):
            s = j / (stations - 1)
            dd = L * (s ** 0.93)
            zoff = L * (upbias * s - droop * s * s)
            lateral = 0.09 * math.sin(s * 5.2 + i * 1.7) * s
            spines.append(base + d * dd + side * lateral + Vector((0, 0, zoff)))

        # folded rachis strip (thin, keeps a crisp top edge)
        verts = []
        for j, sp in enumerate(spines):
            s = j / (stations - 1)
            w = (0.045 + 0.030 * math.sin(math.pi * s)) * (1.0 - 0.65 * s)
            verts.extend([sp - side * w - Vector((0, 0, w * 0.30)),
                          sp + Vector((0, 0, 0.020 + 0.02 * w)),
                          sp + side * w - Vector((0, 0, w * 0.30))])
        faces = []
        for j in range(stations - 1):
            o = 3 * j
            faces.append((o + 0, o + 3, o + 4, o + 1))
            faces.append((o + 1, o + 4, o + 5, o + 2))
        mb.add(verts, faces, "Leaf_Palm")

        # leaflets: two-triangle blades that overlap into a feathered frond
        leaf_verts = []
        leaf_faces = []
        for j in range(12):
            s = 0.08 + (0.94 - 0.08) * j / 11.0
            idx = s * (stations - 1)
            i0 = min(stations - 2, int(idx))
            fr = idx - i0
            sp = spines[i0].lerp(spines[i0 + 1], fr)
            tan = (spines[i0 + 1] - spines[i0]).normalized()
            prof = math.sin(math.pi * (0.06 + 0.90 * s)) ** 0.52
            for sgn in (-1.0, 1.0):
                ll = (0.50 + 0.10 * math.sin(j * 2.3 + i)) * prof
                sweep = 0.72
                direction = (side * (sgn * math.cos(sweep))
                             + tan * math.sin(sweep)
                             + Vector((0, 0, -0.50))).normalized()
                a = sp - tan * 0.070
                b = sp + tan * 0.070
                c = a + direction * ll - tan * 0.012
                d = b + direction * ll + tan * 0.012
                o = len(leaf_verts)
                leaf_verts.extend([a, b, d, c])
                leaf_faces.append((o, o + 1, o + 2))
                leaf_faces.append((o, o + 2, o + 3))
        mb.add(leaf_verts, leaf_faces, "Leaf_Palm")

    # two coconuts hanging in a short cluster on the front of the crown
    nuts = [(-0.01, -0.48, -0.32, 0.175),
            (-0.07, -0.48, -0.66, 0.155)]
    stem_top = top + Vector((-0.02, -0.16, -0.20))
    for k, (dx, dy, dz, r) in enumerate(nuts):
        c = top + Vector((dx, dy, dz))
        tube(mb, [stem_top, (stem_top + c) * 0.5, c],
             [0.022, 0.016, 0.010], 3, "Bark_Palm",
             cap_start=False, cap_end=True)
        add_ico(mb, c, (r, r, r * 1.06), "Coconut",
                seed=40 + k, yaw=0.6 * k, jitter=0.10)


# --------------------------------------------------------------------------------------
# 2. desert_shrub
# --------------------------------------------------------------------------------------

def build_desert_shrub(mb):
    rng = random.Random(202)

    def grow(start, direction, length, radius, depth):
        stations = 4 if depth >= 1 else 3
        d = Vector(direction).normalized()
        pts = [Vector(start)]
        for j in range(1, stations):
            t = j / (stations - 1)
            d = (d + Vector((rng.uniform(-0.14, 0.14),
                             rng.uniform(-0.14, 0.14),
                             -0.20 * t + rng.uniform(-0.05, 0.05)))).normalized()
            pts.append(pts[-1] + d * (length / (stations - 1)))
        radii = []
        for j in range(stations):
            t = j / (stations - 1)
            radii.append(max(0.0055, radius * (1.0 - 0.74 * t)))
        tube(mb, pts, radii, 5 if depth >= 2 else 4, "Bark_Shrub",
             cap_start=False, cap_end=True, jitter=0.10, seed=rng.randrange(9999))

        end = pts[-1]
        if depth > 0:
            count = 2 if depth == 2 else rng.choice([2, 2, 3])
            base_ang = math.atan2(d.y, d.x)
            for c in range(count):
                a = base_ang + (c - (count - 1) / 2.0) * rng.uniform(0.9, 1.7)
                tilt = rng.uniform(0.30, 0.78)
                nd = Vector((math.cos(a) * math.sin(tilt),
                             math.sin(a) * math.sin(tilt),
                             math.cos(tilt)))
                grow(end - d * 0.015, nd, length * rng.uniform(0.58, 0.76),
                     radius * 0.62, depth - 1)
        else:
            for _ in range(rng.randint(2, 3)):
                add_dry_leaf(mb,
                             end + Vector((rng.uniform(-0.025, 0.025),
                                           rng.uniform(-0.025, 0.025), 0.0)),
                             rng.uniform(0.052, 0.090), rng.uniform(0.012, 0.021),
                             rng.uniform(0, TAU), rng.uniform(0.15, 0.85),
                             "Leaf_Dry")

    base_specs = [(-2.30, 0.50), (-1.10, 0.68), (0.35, 0.60),
                  (1.55, 0.78), (2.70, 0.55)]
    for k, (a, tilt) in enumerate(base_specs):
        a += rng.uniform(-0.18, 0.18)
        tilt += rng.uniform(-0.10, 0.10)
        d = Vector((math.cos(a) * math.sin(tilt),
                    math.sin(a) * math.sin(tilt),
                    math.cos(tilt)))
        grow(Vector((0.045 * math.cos(a), 0.045 * math.sin(a), 0.02)),
             d, rng.uniform(0.38, 0.49), rng.uniform(0.030, 0.040), 2)

    # a few low side twigs to break the candelabra silhouette
    for k in range(3):
        a = 0.9 + k * TAU / 3 + rng.uniform(-0.3, 0.3)
        d = Vector((math.cos(a) * 0.92, math.sin(a) * 0.92, 0.38))
        grow(Vector((0.03 * math.cos(a), 0.03 * math.sin(a), 0.05)),
             d, rng.uniform(0.20, 0.28), 0.018, 1)


# --------------------------------------------------------------------------------------
# 3. cactus
# --------------------------------------------------------------------------------------

def build_cactus(mb):
    main_pts = []
    main_r = []
    for i in range(9):
        t = i / 8.0
        z = 2.80 * t
        main_pts.append(Vector((0.095 * (t ** 2), -0.060 * (t ** 2), z)))
        main_r.append(0.245 - 0.072 * t + 0.006 * math.sin(t * 9.0))
    main_pts.append(Vector((0.095, -0.060, 2.90)))
    main_r.append(0.160)
    main_pts.append(Vector((0.098, -0.061, 2.965)))
    main_r.append(0.092)
    main_pts.append(Vector((0.100, -0.062, 3.000)))
    main_r.append(0.020)

    phase = math.pi / 8.0
    tube(mb, main_pts, main_r, 8, "Cactus_Body", cap_start=True, cap_end=True,
         phase=phase, jitter=0.02, seed=7)

    # pale ridge lines on the column (no thorn geometry)
    frames = frames_for(main_pts)
    width = 0.020
    for k in range(8):
        a = phase + TAU * k / 8.0
        verts = []
        for i in range(1, 7):
            t, right, up = frames[i]
            p = main_pts[i]
            r = main_r[i]
            outward = right * math.cos(a) + up * math.sin(a)
            tangential = -right * math.sin(a) + up * math.cos(a)
            base = p + outward * (r * 1.010)
            verts.append(base + tangential * (width * 0.5))
            verts.append(base - tangential * (width * 0.5))
        faces = []
        for j in range(len(verts) // 2 - 1):
            i0, i1 = 2 * j, 2 * j + 1
            i2, i3 = 2 * (j + 1), 2 * (j + 1) + 1
            faces.append((i0, i1, i3, i2))
        mb.add(verts, faces, "Cactus_Ridge")

    # arm A: out to +X, then up, joins high on the right side
    tube(mb,
         [Vector((0.02, 0.00, 1.05)), Vector((0.28, 0.02, 1.03)),
          Vector((0.50, 0.04, 1.10)), Vector((0.58, 0.04, 1.36)),
          Vector((0.58, 0.04, 1.66)), Vector((0.55, 0.04, 1.79))],
         [0.135, 0.130, 0.118, 0.108, 0.098, 0.052],
         6, "Cactus_Body", cap_start=False, cap_end=True, phase=0.3, jitter=0.03, seed=31)

    # arm B: out toward the front (-Y), then up
    tube(mb,
         [Vector((0.00, -0.02, 1.55)), Vector((0.02, -0.28, 1.53)),
          Vector((0.03, -0.46, 1.62)), Vector((0.02, -0.52, 1.90)),
          Vector((0.01, -0.51, 2.16)), Vector((0.00, -0.49, 2.30))],
         [0.140, 0.132, 0.118, 0.108, 0.098, 0.050],
         6, "Cactus_Body", cap_start=False, cap_end=True, phase=0.9, jitter=0.03, seed=32)


# --------------------------------------------------------------------------------------
# 4. reeds
# --------------------------------------------------------------------------------------

def add_reed_blade(mb, base, height, width, az, lean, seed, mat="Grass_Reed"):
    d = Vector((math.cos(az), math.sin(az), 0.0))
    side = Vector((-math.sin(az), math.cos(az), 0.0))
    base = Vector(base)
    stations = [(0.0, 0.55), (0.42, 1.0), (0.78, 0.62)]
    verts = []
    for s, wf in stations:
        c = base + d * (lean * (s ** 1.45)) + Vector((0, 0, height * s))
        w = width * wf
        verts.append(c - side * w)
        verts.append(c + d * (0.18 * w) + Vector((0, 0, 0.012)))
        verts.append(c + side * w)
    tip = base + d * (lean * 1.04) + Vector((0, 0, height * 1.02))
    verts.append(tip)
    faces = []
    for j in range(2):
        o = 3 * j
        faces.append((o + 0, o + 3, o + 4, o + 1))
        faces.append((o + 1, o + 4, o + 5, o + 2))
    faces.append((6, 8, 9))
    faces.append((7, 8, 9))
    mb.add(verts, faces, mat)


def build_reeds(mb):
    rng = random.Random(404)
    for i in range(12):
        a = i * TAU / 12.0 + rng.uniform(-0.22, 0.22)
        rad = rng.uniform(0.010, 0.130)
        base = Vector((math.cos(a) * rad, math.sin(a) * rad, 0.0))
        height = rng.uniform(1.00, 1.36)
        width = rng.uniform(0.016, 0.028)
        az = a + rng.uniform(-0.55, 0.55)
        lean = rng.uniform(0.10, 0.22)
        mat = "Grass_Reed" if i % 3 else "Grass_Reed_Dark"
        add_reed_blade(mb, base, height, width, az, lean, seed=i, mat=mat)

    cattails = [(-2.25, 0.030, 1.33, 0.12),
                (0.15, 0.070, 1.39, 0.16),
                (2.45, 0.110, 1.27, 0.20)]
    for i, (a, rad, h, lean) in enumerate(cattails):
        base = Vector((math.cos(a) * rad, math.sin(a) * rad, 0.0))
        d = Vector((math.cos(a), math.sin(a), 0.0))
        pts = [base,
               base + d * (lean * 0.35) + Vector((0, 0, h * 0.42)),
               base + d * (lean * 0.75) + Vector((0, 0, h * 0.78)),
               base + d * lean + Vector((0, 0, h * 0.95))]
        tube(mb, pts, [0.014, 0.013, 0.011, 0.010], 5, "Grass_Cattail",
             cap_start=True, cap_end=True)
        top = pts[-1]
        head_pts = [top + Vector((0, 0, -0.035)),
                    top + Vector((0, 0, 0.020)),
                    top + Vector((0, 0, 0.120)),
                    top + Vector((0, 0, 0.245)),
                    top + Vector((0, 0, 0.300))]
        tube(mb, head_pts, [0.014, 0.047, 0.052, 0.042, 0.008], 6,
             "Cattail_Head", cap_start=True, cap_end=True, phase=0.4 + i)


# --------------------------------------------------------------------------------------
# 5/6. snow pines
# --------------------------------------------------------------------------------------

def pine_trunk(mb, H, lean, seed, sides=8, n=10):
    pts = []
    radii = []
    for i in range(n):
        t = i / (n - 1)
        x = lean[0] * (t ** 1.7) + 0.07 * math.sin(t * 6.0 + seed)
        y = lean[1] * (t ** 1.7) + 0.05 * math.sin(t * 4.4 + seed * 1.7)
        pts.append(Vector((x, y, H * t)))
        radii.append(0.30 * ((1.0 - t) ** 0.9) + 0.045
                     + 0.018 * math.sin(t * 8.0 + seed))
    tube(mb, pts, radii, sides, "Bark_Pine", cap_start=True, cap_end=True,
         jitter=0.05, seed=seed)
    return pts


def add_snow_slab(mb, center, az, length, width, height, seed, mat="Snow"):
    """Directional snow drift lying along a branch (angular block, not white noise)."""
    center = Vector(center)
    rng = random.Random(seed)
    along = Vector((math.cos(az), math.sin(az), 0.0))
    side = Vector((-math.sin(az), math.cos(az), 0.0))
    # base outline: 6 points, heavier at the inner end, tapering to the branch tip
    base_uv = [(-0.50, -0.46), (0.18, -0.52), (0.50, -0.26),
               (0.50, 0.24), (0.18, 0.50), (-0.50, 0.44)]
    bot = []
    for u, v in base_uv:
        bot.append(center + along * (u * length) + side * (v * width)
                   + Vector((0, 0, rng.uniform(-0.02, 0.02))))
    top = []
    for k, (u, v) in enumerate(base_uv):
        uu = u * 0.80
        vv = v * rng.uniform(0.62, 0.82)
        hh = height * rng.uniform(0.55, 1.15)
        if u > 0.4:          # outer end of the drift is thinner
            hh *= 0.62
        top.append(center + along * (uu * length) + side * (vv * width)
                   + Vector((0, 0, hh)))
    top_uv = [(-0.12 + rng.uniform(-0.10, 0.10),
               rng.uniform(-0.12, 0.12))]
    peak_h = max((v.z - center.z) for v in top) * 1.12 + 0.01
    peak = center + along * (top_uv[0][0] * length) + side * (top_uv[0][1] * width) \
        + Vector((0, 0, peak_h))
    verts = bot + top + [peak]
    faces = []
    for k in range(6):
        k2 = (k + 1) % 6
        faces.append((k, k2, 6 + k2, 6 + k))
    for k in range(6):
        faces.append((6 + k, 6 + ((k + 1) % 6), 12))
    mb.add(verts, faces, mat)


def pine_pad(mb, cx, cy, z, az, R, seed, mat, snow=True, snow_mat="Snow"):
    """One faceted bough wedge: green underside + a narrower snow layer on top."""
    rng = random.Random(seed)
    along = Vector((math.cos(az), math.sin(az), 0.0))
    side = Vector((-math.sin(az), math.cos(az), 0.0))
    base = Vector((cx, cy, z))
    # t, z offset, half width, thickness (all relative to R)
    st = [(0.06, 0.15, 0.20, 0.10),
          (0.38, 0.035, 0.28, 0.080),
          (0.72, -0.055, 0.22, 0.052),
          (1.00, -0.17, 0.025, 0.012)]

    def pad_at(t):
        for i in range(3):
            t0, dz0, w0, th0 = st[i]
            t1, dz1, w1, th1 = st[i + 1]
            if t <= t1:
                f = (t - t0) / max(1e-6, t1 - t0)
                return (dz0 + (dz1 - dz0) * f,
                        w0 + (w1 - w0) * f,
                        th0 + (th1 - th0) * f)
        return st[-1][1:]

    verts = []
    for t, dz, wf, th in st:
        c = base + along * (t * R) + Vector((0, 0, dz * R))
        w = wf * R
        camber = 0.035 * R * (1.0 - 0.5 * t)
        bt = th * R
        verts.extend([c - side * w,
                      c + Vector((0, 0, camber)),
                      c + side * w,
                      c - side * w - Vector((0, 0, bt)),
                      c - Vector((0, 0, bt * 0.8)),
                      c + side * w - Vector((0, 0, bt))])
    faces = []

    def ti(i, off):
        return i * 6 + off

    for i in range(3):
        faces.append((ti(i, 0), ti(i, 1), ti(i + 1, 1), ti(i + 1, 0)))
        faces.append((ti(i, 1), ti(i, 2), ti(i + 1, 2), ti(i + 1, 1)))
        faces.append((ti(i, 3), ti(i + 1, 3), ti(i + 1, 4), ti(i, 4)))
        faces.append((ti(i, 4), ti(i + 1, 4), ti(i + 1, 5), ti(i, 5)))
        faces.append((ti(i, 0), ti(i, 3), ti(i + 1, 3), ti(i + 1, 0)))
        faces.append((ti(i, 2), ti(i + 1, 2), ti(i + 1, 5), ti(i, 5)))
    faces.append((ti(0, 0), ti(0, 1), ti(0, 4), ti(0, 3)))
    faces.append((ti(0, 1), ti(0, 2), ti(0, 5), ti(0, 4)))
    faces.append((ti(3, 0), ti(3, 3), ti(3, 4), ti(3, 1)))
    faces.append((ti(3, 1), ti(3, 4), ti(3, 5), ti(3, 2)))
    mb.add(verts, faces, mat)

    if snow:
        sverts = []
        for t, width_mul in ((0.36, 0.60), (0.66, 0.56), (0.88, 0.50)):
            dz, wf, th = pad_at(t)
            c = base + along * (t * R) + Vector((0, 0, dz * R))
            w = wf * R * width_mul
            lift = 0.045 * R
            camber = 0.028 * R * (1.0 - 0.4 * t)
            sverts.extend([c - side * w + Vector((0, 0, lift)),
                           c + Vector((0, 0, lift + camber)),
                           c + side * w + Vector((0, 0, lift)),
                           c - side * w - Vector((0, 0, 0.020 * R)),
                           c - Vector((0, 0, 0.010 * R)),
                           c + side * w - Vector((0, 0, 0.020 * R))])
        sfaces = []
        for i in range(2):
            sfaces.append((ti(i, 0), ti(i, 1), ti(i + 1, 1), ti(i + 1, 0)))
            sfaces.append((ti(i, 1), ti(i, 2), ti(i + 1, 2), ti(i + 1, 1)))
            sfaces.append((ti(i, 0), ti(i, 3), ti(i + 1, 3), ti(i + 1, 0)))
            sfaces.append((ti(i, 2), ti(i + 1, 2), ti(i + 1, 5), ti(i, 5)))
        sfaces.append((ti(0, 0), ti(0, 1), ti(0, 4), ti(0, 3)))
        sfaces.append((ti(0, 1), ti(0, 2), ti(0, 5), ti(0, 4)))
        sfaces.append((ti(2, 0), ti(2, 3), ti(2, 4), ti(2, 1)))
        sfaces.append((ti(2, 1), ti(2, 4), ti(2, 5), ti(2, 2)))
        mb.add(sverts, sfaces, snow_mat)


def pine_cone_tier(mb, cx, cy, z, R, height, sides, seed, green_mat,
                   gap_idx=None, tilt_scale=1.0, gap_scale=0.58):
    """One overlapping, jagged conical bough layer: green rim fringe, a visible
    snow shelf above it, thick green under-skirt and a tilted, irregular outline."""
    rng = random.Random(seed)
    ang0 = rng.uniform(0.0, TAU)
    tilt = R * rng.uniform(-0.11, 0.11) * tilt_scale
    tilt_az = rng.uniform(0.0, TAU)
    cols = []
    top_r = max(0.025, R * 0.045)
    for k in range(sides):
        a = ang0 + TAU * k / sides + rng.uniform(-0.06, 0.06)
        rr = R * rng.uniform(0.70, 1.24)
        if gap_idx is not None and k == gap_idx:
            rr *= gap_scale
        rim_z = z - R * rng.uniform(0.02, 0.22) + tilt * math.cos(a - tilt_az)
        cols.append({
            "a": a,
            "rr": rr,
            "rim_z": rim_z,
            "sr": rr * rng.uniform(0.82, 0.96),
            "sz": rim_z + height * rng.uniform(0.27, 0.42),
            "mr": rr * rng.uniform(0.46, 0.58),
            "mz": z + height * rng.uniform(0.44, 0.56),
            "tz": z + height + rng.uniform(-0.03, 0.03),
        })
    verts = []
    rim = []
    shelf = []
    mid = []
    top = []
    under = []
    for c in cols:
        a = c["a"]
        rim.append(len(verts))
        verts.append(Vector((cx + math.cos(a) * c["rr"],
                             cy + math.sin(a) * c["rr"], c["rim_z"])))
    for c in cols:
        a = c["a"]
        shelf.append(len(verts))
        verts.append(Vector((cx + math.cos(a) * c["sr"],
                             cy + math.sin(a) * c["sr"], c["sz"])))
    for c in cols:
        a = c["a"]
        mid.append(len(verts))
        verts.append(Vector((cx + math.cos(a) * c["mr"],
                             cy + math.sin(a) * c["mr"], c["mz"])))
    for c in cols:
        a = c["a"]
        top.append(len(verts))
        verts.append(Vector((cx + math.cos(a) * top_r,
                             cy + math.sin(a) * top_r, c["tz"])))
    for c in cols:
        a = c["a"]
        under.append(len(verts))
        verts.append(Vector((cx + math.cos(a) * c["rr"] * 0.97,
                             cy + math.sin(a) * c["rr"] * 0.97,
                             c["rim_z"] - R * 0.11 - 0.03)))
    uc = len(verts)
    verts.append(Vector((cx, cy, z - R * 0.16 - 0.03)))
    tc = len(verts)
    verts.append(Vector((cx, cy, z + height + 0.03)))
    faces = []
    mats = []
    alt_mat = "Leaf_Pine_Light" if green_mat == "Leaf_Pine" else "Leaf_Pine"
    for k in range(sides):
        k2 = (k + 1) % sides
        face_green = alt_mat if ((k // 2 + seed) % 6 == 0) else green_mat
        faces.append((rim[k], rim[k2], shelf[k2], shelf[k]))
        mats.append(face_green)
        faces.append((shelf[k], shelf[k2], mid[k2], mid[k]))
        mats.append("Snow")
        faces.append((mid[k], mid[k2], top[k2], top[k]))
        mats.append("Snow")
        faces.append((rim[k], under[k], under[k2], rim[k2]))
        mats.append(face_green)
        faces.append((under[k2], under[k], uc))
        mats.append(face_green)
        faces.append((top[k], top[k2], tc))
        mats.append("Snow")
    mb.add(verts, faces, mats)

    # chunky snow blocks along the snow shelf (overhang the green rim)
    for j in range(5):
        c = cols[rng.randrange(sides)]
        a = c["a"] + rng.uniform(-0.06, 0.06)
        rho = c["sr"] * rng.uniform(0.99, 1.06)
        add_snow_lump(mb, (cx + math.cos(a) * rho, cy + math.sin(a) * rho,
                           c["sz"] - 0.01),
                      R * rng.uniform(0.075, 0.135),
                      R * rng.uniform(0.030, 0.060) + 0.02,
                      5, seed=seed * 37 + j,
                      mat="Snow" if rng.random() > 0.2 else "Snow_Deep")
    # snow clinging to the dark branch tips
    for j in range(3):
        c = cols[rng.randrange(sides)]
        a = c["a"]
        add_snow_lump(mb, (cx + math.cos(a) * c["rr"] * 0.98,
                           cy + math.sin(a) * c["rr"] * 0.98,
                           c["rim_z"] + 0.012),
                      R * rng.uniform(0.040, 0.065),
                      R * rng.uniform(0.018, 0.030) + 0.012,
                      5, seed=seed * 53 + j, mat="Snow")


def lean_xy(z, H, lean):
    t = max(0.0, min(1.0, z / H))
    return lean[0] * (t ** 1.7), lean[1] * (t ** 1.7)


def pine_core(mb, H, lean, rings, seed, mat="Leaf_Pine"):
    """Irregular conical foliage core that fills the space between branch whorls,
    with clustered snow faces so the gaps read as snow-laden needles."""
    pts = []
    radii = []
    rng = random.Random(seed)
    for z, r in rings:
        lx, ly = lean_xy(z, H, lean)
        pts.append(Vector((lx + rng.uniform(-0.05, 0.05),
                           ly + rng.uniform(-0.05, 0.05), z)))
        radii.append(max(0.02, r * rng.uniform(0.92, 1.08)))
    sides = 8
    phase = rng.uniform(0, TAU)
    frames = frames_for(pts)
    verts = []
    ring_ids = []
    for i, (p, r) in enumerate(zip(pts, radii)):
        _t, right, up = frames[i]
        ids = []
        for k in range(sides):
            a = phase + TAU * k / sides
            rr = r * (1.0 + 0.10 * math.sin(k * 2.1 + i * 1.7 + seed))
            ids.append(len(verts))
            verts.append(p + right * (math.cos(a) * rr) + up * (math.sin(a) * rr))
        ring_ids.append(ids)
    faces = []
    mats = []
    for i in range(len(pts) - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            faces.append((ring_ids[i][k], ring_ids[i][k2],
                          ring_ids[i + 1][k2], ring_ids[i + 1][k]))
            v = (math.sin((i + 1) * 1.9 + k * 1.6 + seed * 0.7)
                 + 0.6 * math.sin(k * 2.9 - i * 1.2))
            snow = v > 0.80 or i >= len(pts) - 2
            mats.append("Snow" if snow else mat)
    ci = len(verts)
    verts.append(pts[-1])
    for k in range(sides):
        faces.append((ring_ids[-1][k], ring_ids[-1][(k + 1) % sides], ci))
        mats.append("Snow")
    mb.add(verts, faces, mats)


def build_pine_tree_a(mb):
    H = 10.0
    lean = (0.28, -0.55)
    trunk_pts = pine_trunk(mb, H, lean, seed=5, sides=8, n=10)

    tiers = [
        (1.90, 2.55, 1.80, 11, 0.06, -0.05, 1),
        (3.55, 2.18, 1.70, 10, -0.05, -0.08, 4),
        (5.15, 1.72, 1.60, 9, 0.05, 0.02, 2),
        (6.65, 1.26, 1.50, 8, -0.03, -0.05, 5),
        (8.05, 0.86, 1.45, 7, 0.02, -0.02, 3),
    ]
    for i, (z, rad, h, sides, ox, oy, gap) in enumerate(tiers):
        lx, ly = lean_xy(z, H, lean)
        mat = "Leaf_Pine" if i < 3 else "Leaf_Pine_Light"
        pine_cone_tier(mb, lx + ox, ly + oy, z, rad, h, sides,
                       seed=60 + i, green_mat=mat, gap_idx=gap)

    # snow-covered leader spike, with a dark green tip poking out
    z0, z1 = 9.30, 9.76
    x0, y0 = lean_xy(z0, H, lean)
    x1, y1 = lean_xy(z1, H, lean)
    tube(mb, [Vector((x0, y0, z0)),
              Vector(((x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5)),
              Vector((x1, y1, z1))],
         [0.17, 0.085, 0.020], 5, "Snow",
         cap_start=False, cap_end=True, jitter=0.18, seed=77)

    gz0, gz1 = 9.52, 9.995
    gx0, gy0 = lean_xy(gz0, H, lean)
    gx1, gy1 = lean_xy(gz1, H, lean)
    tube(mb, [Vector((gx0, gy0, gz0)),
              Vector((gx0 * 0.6 + gx1 * 0.4, gy0 * 0.6 + gy1 * 0.4,
                      (gz0 + gz1) * 0.5)),
              Vector((gx1, gy1, gz1))],
         [0.085, 0.045, 0.008], 5, "Leaf_Pine_Light",
         cap_start=False, cap_end=True, jitter=0.15, seed=78)

    # hide the very top of the trunk under the snow
    top = trunk_pts[-1]
    add_snow_lump(mb, (top.x, top.y, 9.42), 0.14, 0.26, 5,
                  seed=899, mat="Snow")


def build_pine_tree_b(mb):
    H = 6.0
    lean = (0.22, -0.72)
    trunk_pts = pine_trunk(mb, H, lean, seed=9, sides=7, n=9)

    tiers = [
        (2.15, 1.35, 1.05, 7, 0.04, -0.03, None),
        (3.40, 1.00, 1.00, 7, -0.03, 0.02, 2),
        (4.55, 0.70, 0.95, 6, 0.02, -0.02, None),
        (5.55, 0.40, 0.65, 5, 0.01, -0.01, None),
    ]
    for i, (z, rad, h, sides, ox, oy, gap) in enumerate(tiers):
        lx, ly = lean_xy(z, H, lean)
        mat = "Leaf_Pine_Light" if i == 2 else "Leaf_Pine"
        pine_cone_tier(mb, lx + ox, ly + oy, z, rad, h, sides,
                       seed=120 + i, green_mat=mat, gap_idx=gap,
                       tilt_scale=0.55, gap_scale=0.80)

    # bare lower branches and root spurs for a sparse, wind-beaten silhouette
    tube(mb, [Vector((-0.03, 0.02, 0.72)), Vector((-0.48, 0.22, 0.84)),
              Vector((-0.80, 0.32, 0.78))],
         [0.070, 0.042, 0.015], 4, "Bark_Pine", cap_start=False, cap_end=True)
    tube(mb, [Vector((0.02, -0.02, 0.98)), Vector((0.38, -0.20, 1.04)),
              Vector((0.62, -0.34, 0.98))],
         [0.055, 0.032, 0.012], 4, "Bark_Pine", cap_start=False, cap_end=True)
    for k in range(3):
        a = 0.8 + k * TAU / 3
        tube(mb,
             [Vector((0.04 * math.cos(a), 0.04 * math.sin(a), 0.30)),
              Vector((0.20 * math.cos(a), 0.20 * math.sin(a), 0.10)),
              Vector((0.36 * math.cos(a), 0.36 * math.sin(a), 0.0))],
             [0.075, 0.048, 0.018], 4, "Bark_Pine",
             cap_start=False, cap_end=True)

    # green leader poking out of the snow tip
    gz0, gz1 = 5.88, 6.18
    gx0, gy0 = lean_xy(gz0, H, lean)
    gx1, gy1 = lean_xy(gz1, H, lean)
    tube(mb, [Vector((gx0, gy0, gz0)),
              Vector((gx0 * 0.5 + gx1 * 0.5, gy0 * 0.5 + gy1 * 0.5,
                      (gz0 + gz1) * 0.5)),
              Vector((gx1, gy1, gz1))],
         [0.070, 0.035, 0.007], 5, "Leaf_Pine_Light",
         cap_start=False, cap_end=True, jitter=0.15, seed=91)

    # hide the bare trunk tip inside the crown snow
    top = trunk_pts[-1]
    add_snow_lump(mb, (top.x, top.y, 5.90), 0.080, 0.11, 5,
                  seed=95, mat="Snow")


# --------------------------------------------------------------------------------------
# 7. snow_bush
# --------------------------------------------------------------------------------------

def build_snow_bush(mb):
    rng = random.Random(707)
    blobs = [
        (0.00, 0.04, 0.20, 0.19, 0.18, 0.20, 0.0),
        (-0.28, -0.04, 0.20, 0.16, 0.15, 0.18, 0.6),
        (0.27, -0.06, 0.20, 0.17, 0.16, 0.19, 1.2),
        (0.04, 0.26, 0.21, 0.16, 0.15, 0.18, 2.0),
        (-0.16, -0.24, 0.18, 0.14, 0.13, 0.17, 2.7),
        (-0.18, 0.10, 0.40, 0.14, 0.13, 0.16, 0.9),
        (0.16, 0.12, 0.42, 0.15, 0.14, 0.17, 1.7),
        (-0.05, -0.10, 0.45, 0.16, 0.15, 0.17, 2.3),
        (0.24, -0.14, 0.38, 0.13, 0.12, 0.15, 0.3),
        (-0.26, -0.12, 0.36, 0.12, 0.12, 0.15, 1.1),
        (0.03, 0.02, 0.56, 0.12, 0.11, 0.13, 2.5),
        (-0.10, 0.18, 0.52, 0.10, 0.10, 0.12, 1.6),
        (0.12, -0.02, 0.54, 0.10, 0.09, 0.12, 0.4),
    ]
    for i, (x, y, z, sx, sy, sz, yaw) in enumerate(blobs):
        add_ico(mb, (x, y, z), (sx, sy, sz), "Leaf_SnowBush",
                seed=710 + i, yaw=yaw, jitter=0.10)

    lumps = [
        (0.00, 0.02, 0.63, 0.22, 0.07, 5, "Snow"),
        (-0.13, 0.08, 0.62, 0.20, 0.07, 5, "Snow"),
        (0.14, 0.07, 0.62, 0.20, 0.07, 5, "Snow_Deep"),
        (0.00, -0.12, 0.61, 0.20, 0.07, 5, "Snow"),
        (-0.02, 0.14, 0.60, 0.17, 0.06, 5, "Snow"),
        (-0.29, -0.04, 0.47, 0.14, 0.06, 5, "Snow"),
        (0.29, -0.06, 0.48, 0.14, 0.06, 5, "Snow"),
        (0.04, 0.27, 0.50, 0.14, 0.06, 5, "Snow"),
        (-0.20, 0.20, 0.52, 0.13, 0.05, 5, "Snow_Deep"),
        (0.20, -0.22, 0.39, 0.12, 0.05, 5, "Snow"),
        (-0.25, -0.20, 0.38, 0.11, 0.05, 5, "Snow"),
    ]
    for i, (x, y, z, r, h, sides, mat) in enumerate(lumps):
        add_snow_lump(mb, (x, y, z), r, h, sides, seed=760 + i, mat=mat)

    # green sprigs around the snow line
    sprigs = [(0.28, -0.06, 0.52, 2.2), (-0.28, -0.10, 0.47, -2.0),
              (0.07, 0.28, 0.54, 1.4), (-0.17, 0.26, 0.56, 1.9),
              (0.23, 0.17, 0.47, 0.4), (-0.06, -0.29, 0.44, -1.5),
              (0.14, -0.09, 0.60, 0.9), (-0.09, 0.05, 0.61, -0.6)]
    for i, (x, y, z, az) in enumerate(sprigs):
        add_dry_leaf(mb, (x, y, z), rng.uniform(0.075, 0.125),
                     rng.uniform(0.014, 0.022), az,
                     rng.uniform(0.9, 1.35), "Leaf_SnowBush")


# --------------------------------------------------------------------------------------
# 8. bare_tree
# --------------------------------------------------------------------------------------

def build_bare_tree(mb):
    rng = random.Random(808)

    # twisted trunk
    H = 3.25
    n = 9
    pts = []
    radii = []
    for i in range(n):
        t = i / (n - 1)
        x = 0.20 * math.sin(t * 3.4 + 0.4) + 0.14 * t
        y = -0.32 * (t ** 1.5) + 0.10 * math.sin(t * 5.2)
        pts.append(Vector((x, y, H * t)))
        radii.append(0.205 * ((1.0 - t) ** 0.75) + 0.060 + 0.010 * math.sin(t * 10.0))
    tube(mb, pts, radii, 7, "Bark_Bare", cap_start=True, cap_end=True,
         jitter=0.08, seed=4)

    # root spurs
    for k in range(3):
        a = 0.7 + k * TAU / 3
        tube(mb,
             [Vector((0.03 * math.cos(a), 0.03 * math.sin(a), 0.28)),
              Vector((0.18 * math.cos(a), 0.18 * math.sin(a), 0.09)),
              Vector((0.32 * math.cos(a), 0.32 * math.sin(a), 0.0))],
             [0.075, 0.052, 0.018], 4, "Bark_Bare", cap_start=False, cap_end=True)

    def grow(start, direction, length, radius, depth):
        stations = 3 if depth > 0 else 2
        d = Vector(direction).normalized()
        local = [Vector(start)]
        for j in range(1, stations):
            d = (d + Vector((rng.uniform(-0.28, 0.28),
                             rng.uniform(-0.28, 0.28),
                             rng.uniform(-0.20, 0.05)))).normalized()
            local.append(local[-1] + d * (length / (stations - 1)))
        rad = [radius * (1.0 - 0.42 * j / (stations - 1)) for j in range(stations)]
        tube(mb, local, rad, 5 if depth >= 1 else 4,
             "Bark_Bare" if depth != 1 else "Bark_Bare_Dark",
             cap_start=False, cap_end=True, jitter=0.08, seed=rng.randrange(9999))
        end = local[-1]
        if depth > 0:
            count = 2 if depth >= 2 else rng.choice([2, 2, 3])
            base_ang = math.atan2(d.y, d.x)
            for c in range(count):
                a = base_ang + (c - (count - 1) / 2.0) * rng.uniform(1.0, 1.9)
                tilt = rng.uniform(0.40, 0.85)
                nd = Vector((math.cos(a) * math.sin(tilt),
                             math.sin(a) * math.sin(tilt),
                             math.cos(tilt)))
                grow(end - d * 0.012, nd, length * rng.uniform(0.58, 0.76),
                     radius * 0.60, depth - 1)
        else:
            add_snow_lump(mb, end + Vector((0, 0, 0.005)),
                          rng.uniform(0.065, 0.105), rng.uniform(0.045, 0.075),
                          5, seed=rng.randrange(9999),
                          mat="Snow" if rng.random() > 0.25 else "Snow_Deep")

    branch_meta = [
        (0.40, 2.30, 1.30, 0.105),
        (0.56, -1.05, 1.25, 0.100),
        (0.70, 0.65, 1.15, 0.092),
        (0.82, 2.95, 1.05, 0.082),
        (0.92, -2.15, 0.95, 0.070),
    ]
    for t, az, length, rad in branch_meta:
        idx = min(n - 1, int(round(t * (n - 1))))
        start = pts[idx] + Vector((0, 0, 0.02))
        tilt = rng.uniform(0.30, 0.55)
        d = Vector((math.cos(az) * math.sin(tilt),
                    math.sin(az) * math.sin(tilt),
                    math.cos(tilt)))
        grow(start, d, length, rad, 2)


# --------------------------------------------------------------------------------------
# 9. ice_crystal
# --------------------------------------------------------------------------------------

def crystal(mb, cx, cy, height, radius, sides, lean, seed, mat="Ice", broken=False):
    rng = random.Random(seed)
    ang0 = rng.uniform(0.0, TAU)
    levels = [0.0, 0.28, 0.55, 0.80]
    rads = [1.00, 0.95, 0.80, 0.44]
    verts = []
    rings = []
    for j in range(len(levels)):
        z = height * levels[j]
        rr = radius * rads[j]
        ring = []
        for k in range(sides):
            a = ang0 + TAU * k / sides + j * 0.10
            rk = rr * (1.0 + 0.05 * math.sin(k * 3.1 + seed))
            ring.append(len(verts))
            verts.append(Vector((cx + math.cos(a) * rk + lean[0] * z,
                                 cy + math.sin(a) * rk + lean[1] * z, z)))
        rings.append(ring)
    if broken:
        tip_z = height * 0.90
        tip_ring = []
        for k in range(sides):
            a = ang0 + TAU * k / sides
            rk = radius * 0.36 * (1.0 + 0.16 * math.sin(k * 2.3 + seed))
            tip_ring.append(len(verts))
            verts.append(Vector((cx + math.cos(a) * rk + lean[0] * tip_z,
                                 cy + math.sin(a) * rk + lean[1] * tip_z, tip_z)))
        tip = None
    else:
        tip = len(verts)
        verts.append(Vector((cx + lean[0] * height * 1.02,
                             cy + lean[1] * height * 1.02, height)))
    faces = []
    for j in range(len(levels) - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            faces.append((rings[j][k], rings[j][k2], rings[j + 1][k2], rings[j + 1][k]))
    if broken:
        for k in range(sides):
            k2 = (k + 1) % sides
            faces.append((tip_ring[k], tip_ring[k2], rings[-1][k2], rings[-1][k]))
    else:
        for k in range(sides):
            k2 = (k + 1) % sides
            faces.append((rings[-1][k], rings[-1][k2], tip))
    mb.add(verts, faces, mat)


def build_ice_crystal(mb):
    # snow bed
    add_mound(mb, 0.0, 0.0, 0.44, 0.19, 10, 909, "Snow", top_ratio=0.68)

    specs = [
        (0.00, 0.02, 1.50, 0.180, 6, (0.060, -0.100), "Ice", False),
        (-0.34, -0.05, 1.08, 0.120, 5, (-0.075, -0.020), "Ice", False),
        (0.31, 0.01, 1.14, 0.130, 6, (0.085, -0.030), "Ice_Deep", False),
        (-0.12, -0.34, 0.98, 0.105, 5, (0.015, 0.085), "Ice", False),
        (0.20, -0.35, 0.90, 0.095, 5, (0.035, 0.075), "Ice_Deep", False),
        (-0.20, 0.30, 0.82, 0.090, 5, (-0.040, 0.060), "Ice", True),
    ]
    for i, (x, y, h, r, sides, lean, mat, broken) in enumerate(specs):
        crystal(mb, x, y, h, r, sides, lean, 910 + i, mat=mat, broken=broken)

    base_lumps = [(-0.34, 0.18, 0.18, 0.12, "Snow"),
                  (0.34, 0.16, 0.17, 0.11, "Snow"),
                  (0.28, -0.28, 0.18, 0.12, "Snow"),
                  (-0.30, -0.22, 0.16, 0.10, "Snow_Deep"),
                  (0.02, 0.34, 0.16, 0.10, "Snow"),
                  (-0.04, -0.38, 0.15, 0.09, "Snow_Deep")]
    for i, (x, y, r, h, mat) in enumerate(base_lumps):
        add_snow_lump(mb, (x, y, 0.01), r, h, 5, seed=930 + i, mat=mat)
    for i, (x, y, r, h) in enumerate([(0.18, 0.17, 0.13, 0.07),
                                      (-0.24, -0.20, 0.12, 0.06),
                                      (0.02, 0.24, 0.11, 0.06)]):
        add_snow_lump(mb, (x, y, 0.14), r, h, 5, seed=940 + i,
                      mat="Snow" if i != 1 else "Snow_Deep")


# --------------------------------------------------------------------------------------
# 10. glow_grass  (<= 60 tris)
# --------------------------------------------------------------------------------------

def build_glow_grass(mb):
    rng = random.Random(1002)
    for i in range(12):
        a = -math.pi / 2 + i * TAU / 12 + rng.uniform(-0.18, 0.18)
        rad = 0.006 + 0.042 * rng.random()
        base = Vector((math.cos(a) * rad, math.sin(a) * rad, 0.0))
        h = rng.uniform(0.21, 0.392)
        w = rng.uniform(0.008, 0.014)
        lean = rng.uniform(0.08, 0.20)
        d = Vector((math.cos(a), math.sin(a), 0.0))
        side = Vector((-math.sin(a), math.cos(a), 0.0))
        mid = base + d * (lean * 0.30) + Vector((0, 0, h * 0.45))
        upper = base + d * (lean * 0.78) + Vector((0, 0, h * 0.75))
        tip = base + d * (lean * 1.25) + Vector((0, 0, h * 0.95))
        verts = [base - side * w, base + side * w,
                 mid - side * w, mid + side * w,
                 upper - side * w * 0.55, upper + side * w * 0.55,
                 tip]
        faces = [(0, 1, 3, 2), (2, 3, 5, 4), (4, 5, 6)]
        mb.add(verts, faces, ["Grass_Base", "Grass_Base", "Grass_Glow"])


# --------------------------------------------------------------------------------------
# asset registry
# --------------------------------------------------------------------------------------

ASSETS = [
    {
        "name": "palm_tree",
        "build": build_palm_tree,
        "height": 7.5,
        "chapter": "amberreach",
        "tags": ["amberreach", "oasis", "palm", "tree", "landmark"],
        "suggested_use": "琥珀沙海绿洲的主景棕榈，放在水洼边或集市入口，可旋转出 3 个变体。",
    },
    {
        "name": "desert_shrub",
        "build": build_desert_shrub,
        "height": 0.9,
        "chapter": "amberreach",
        "tags": ["amberreach", "desert", "shrub", "dry", "filler"],
        "suggested_use": "沙海绿洲外围、沙丘脚下的中景填充灌木，成组摆放时旋转缩放即可。",
    },
    {
        "name": "cactus",
        "build": build_cactus,
        "height": 3.0,
        "chapter": "amberreach",
        "tags": ["amberreach", "desert", "cactus", "landmark"],
        "suggested_use": "沙海峡谷口与商道旁的柱状仙人掌，可作路标或绿洲边界的主景。",
    },
    {
        "name": "reeds",
        "build": build_reeds,
        "height": 1.4,
        "chapter": "amberreach",
        "tags": ["amberreach", "oasis", "water", "grass", "detail"],
        "suggested_use": "绿洲水边、浅水与湿地边缘的细节点缀，沿水线成排布置。",
    },
    {
        "name": "pine_tree_a",
        "build": build_pine_tree_a,
        "height": 10.0,
        "chapter": "frostvale",
        "tags": ["frostvale", "conifer", "snow", "tree", "landmark"],
        "suggested_use": "霜枝谷雪松林的主景树，用于雪村、冻瀑与冰湖周边，少量即可撑起天际线。",
    },
    {
        "name": "pine_tree_b",
        "build": build_pine_tree_b,
        "height": 6.0,
        "chapter": "frostvale",
        "tags": ["frostvale", "conifer", "snow", "tree", "filler"],
        "suggested_use": "倾斜雪松，用于雪松林边缘、坡地与石桥两侧，与 pine_tree_a 混植避免重复。",
    },
    {
        "name": "snow_bush",
        "build": build_snow_bush,
        "height": 0.9,
        "chapter": "frostvale",
        "tags": ["frostvale", "snow", "shrub", "filler"],
        "suggested_use": "雪村屋檐下、路边与雪松林间的低矮雪灌木，可半埋进雪坡。",
    },
    {
        "name": "bare_tree",
        "build": build_bare_tree,
        "height": 4.5,
        "chapter": "frostvale",
        "tags": ["frostvale", "dead_tree", "snow", "tree", "detail"],
        "suggested_use": "霜枝谷枯树剪影，放在温泉、冰湖与悬崖边，增强荒寒与等待感。",
    },
    {
        "name": "ice_crystal",
        "build": build_ice_crystal,
        "height": 1.5,
        "chapter": "frostvale",
        "tags": ["frostvale", "ice", "crystal", "snow", "detail"],
        "suggested_use": "冻瀑、冰湖与温泉边的发光冰晶簇，可作采集点或低强度冷光源。",
    },
    {
        "name": "glow_grass",
        "build": build_glow_grass,
        "height": 0.4,
        "chapter": "starfall",
        "tags": ["starfall", "glow", "grass", "emissive", "detail"],
        "suggested_use": "星坠之穹镜湖与虹桥边的发光草簇，作为夜色中的低位补光点，可大量散布。",
    },
]


# --------------------------------------------------------------------------------------
# scene / export / preview
# --------------------------------------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    return scene


def normalise(mb, target_height):
    if not mb.verts:
        raise RuntimeError("empty mesh")
    minz = min(v.z for v in mb.verts)
    for v in mb.verts:
        v.z -= minz
    height = max(v.z for v in mb.verts)
    if target_height and height > 1e-6:
        s = target_height / height
        for v in mb.verts:
            v.x *= s
            v.y *= s
            v.z *= s
    return target_height


def make_object(mb, name):
    used = []
    for m in mb.face_mats:
        if m not in used:
            used.append(m)
    for m in used:
        if m not in MAT_SPEC:
            raise KeyError("material %s not defined" % m)

    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in mb.verts], [], mb.faces)
    me.validate(verbose=False)
    me.update()
    if len(me.polygons) != len(mb.faces):
        print("WARN %s: %d/%d faces survived validation" %
              (name, len(me.polygons), len(mb.faces)))

    for m in used:
        me.materials.append(new_material(m))
    index = {m: i for i, m in enumerate(used)}
    for p, m in zip(me.polygons, mb.face_mats):
        p.material_index = index[m]
        p.use_smooth = False

    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    me.update()

    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    obj.location = (0, 0, 0)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    me.calc_loop_triangles()
    return obj, used, len(me.loop_triangles)


def mesh_stats(obj):
    me = obj.data
    co = [v.co for v in me.vertices]
    mn = [min(c[i] for c in co) for i in range(3)]
    mx = [max(c[i] for c in co) for i in range(3)]
    me.calc_loop_triangles()
    return {
        "min": [round(v, 4) for v in mn],
        "max": [round(v, 4) for v in mx],
        "size": [round(mx[i] - mn[i], 4) for i in range(3)],
        "tris": len(me.loop_triangles),
    }


def export_glb(obj, path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
    )


def add_sun(scene, name, travel, energy, color, angle_deg):
    data = bpy.data.lights.new(name, "SUN")
    data.energy = energy
    data.color = color
    data.angle = math.radians(angle_deg)
    ob = bpy.data.objects.new(name, data)
    scene.collection.objects.link(ob)
    d = Vector(travel).normalized()
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    ob.location = (0, 0, 5)
    return ob


def setup_preview(scene, stats):
    mn = Vector(stats["min"])
    mx = Vector(stats["max"])
    center = (mn + mx) * 0.5
    radius = max(0.12, (mx - mn).length * 0.5)

    # beige ground so floating / contact problems are obvious
    bpy.ops.mesh.primitive_plane_add(size=max(radius * 18.0, 2.0),
                                     location=(0, 0, -0.004))
    ground = bpy.context.object
    ground.name = "PreviewGround"
    gm = new_material("Preview_Ground")
    ground.data.materials.append(gm)

    # --- fit a 3/4 camera to the asset extents --------------------------------------
    direction = Vector((0.82, -1.0, 0.46)).normalized()
    fov = 2.0 * math.atan(18.0 / 50.0)       # 50 mm lens, 36 mm sensor, square render
    tan_half = math.tan(fov * 0.5)
    size = mx - mn
    d_h = size.z / (2.0 * tan_half * 0.82)
    d_w = max(size.x, size.y) / (2.0 * tan_half * 0.82) * 1.10
    cam_dist = max(d_h, d_w, radius * 1.15) * 1.03

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 50
    cam_data.clip_start = max(0.01, radius * 0.005)
    cam_data.clip_end = radius * 120.0
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.location = center + direction * cam_dist
    look = (center - cam.location).normalized()
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    print("        camera dist=%.2fm radius=%.2fm" % (cam_dist, radius))

    add_sun(scene, "KeyWarm", (0.45, 0.72, -1.0), 2.2, (1.0, 0.865, 0.70), 14)
    add_sun(scene, "FillCool", (-0.72, 0.45, -0.38), 0.65, (0.64, 0.79, 1.0), 45)
    add_sun(scene, "Rim", (0.15, -0.95, -0.42), 1.35, (1.0, 0.94, 0.86), 22)

    # light beige backdrop for the camera, dimmer beige ambient for lighting
    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg_light = nt.nodes.new("ShaderNodeBackground")
    bg_light.inputs[0].default_value = hex_to_linear("#D9D2C3")
    bg_light.inputs[1].default_value = 0.55
    bg_view = nt.nodes.new("ShaderNodeBackground")
    bg_view.inputs[0].default_value = hex_to_linear("#D9D2C3")
    bg_view.inputs[1].default_value = 1.0
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg_light.outputs["Background"], mix.inputs[1])
    nt.links.new(bg_view.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    scene.world = world
    return cam, radius, center


def render_preview(scene, name, stats):
    setup_preview(scene, stats)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    scene.cycles.max_bounces = 4
    scene.cycles.diffuse_bounces = 2
    scene.cycles.glossy_bounces = 2
    scene.cycles.transmission_bounces = 2
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 20
    scene.render.filepath = os.path.join(PREVIEW_DIR, name + ".png")
    try:
        scene.view_settings.view_transform = "Standard"
    except Exception:
        pass
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    bpy.ops.render.render(write_still=True)


def build_asset(spec):
    name = spec["name"]
    scene = reset_scene()
    mb = Builder()
    spec["build"](mb)
    normalise(mb, spec["height"])
    obj, used_mats, _tris = make_object(mb, name)
    stats = mesh_stats(obj)
    stats["materials"] = used_mats
    stats["object"] = obj

    glb_path = os.path.join(MODEL_DIR, name + ".glb")
    export_glb(obj, glb_path)
    render_preview(scene, name, stats)
    png = os.path.join(PREVIEW_DIR, name + ".png")

    print("[flora_wild] %-12s tris=%-5d h=%.3f  minZ=%.4f  size=%s  glb=%dKB  png=%dKB" % (
        name, stats["tris"], stats["size"][2], stats["min"][2],
        "x".join("%.2f" % v for v in stats["size"]),
        os.path.getsize(glb_path) // 1024,
        os.path.getsize(png) // 1024))
    return stats


# --------------------------------------------------------------------------------------
# manifest + verification
# --------------------------------------------------------------------------------------

def write_manifest(results):
    assets = []
    total = 0
    for spec in ASSETS:
        st = results[spec["name"]]
        total += st["tris"]
        assets.append({
            "name": spec["name"],
            "file": "assets/models/foliage/%s.glb" % spec["name"],
            "chapter": spec["chapter"],
            "bounds": {"min": st["min"], "max": st["max"], "size": st["size"]},
            "tris": st["tris"],
            "materials": st["materials"],
            "tags": spec["tags"],
            "suggested_use": spec["suggested_use"],
        })
    manifest = {
        "batch": "flora_wild",
        "units": "meters",
        "up_axis": "Blender +Z (exported glTF +Y with export_yup)",
        "forward": "-Y in Blender (Godot +Z after glTF import)",
        "origin": "bottom-centre, ground at z=0",
        "asset_count": len(assets),
        "total_tris": total,
        "assets": assets,
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("[flora_wild] manifest -> %s (%d assets, %d tris)" %
          (MANIFEST_PATH, len(assets), total))
    return manifest


def verify_glbs():
    print("[flora_wild] verifying GLB round-trip ...")
    for spec in ASSETS:
        name = spec["name"]
        path = os.path.join(MODEL_DIR, name + ".glb")
        if not os.path.exists(path):
            print("  FAIL missing", path)
            continue
        reset_scene()
        bpy.ops.import_scene.gltf(filepath=path)
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        if not meshes:
            print("  FAIL no mesh in", name)
            continue
        obj = meshes[0]
        me = obj.data
        me.calc_loop_triangles()
        zmin = min((obj.matrix_world @ v.co).z for v in me.vertices)
        print("  OK   %-12s objs=%d tris=%-5d zmin=%.4f  materials=%s" % (
            name, len(meshes), len(me.loop_triangles), round(zmin, 4),
            [m.name for m in me.materials]))


# --------------------------------------------------------------------------------------
# contact sheet (Pillow, run outside Blender)
# --------------------------------------------------------------------------------------

def make_contact_sheet():
    from PIL import Image, ImageDraw, ImageFont
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        man = json.load(f)

    def font(path, size):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return ImageFont.load_default()

    f_name = font(r"C:\Windows\Fonts\arialbd.ttf", 22)
    f_meta = font(r"C:\Windows\Fonts\arial.ttf", 16)
    f_title = font(r"C:\Windows\Fonts\arialbd.ttf", 30)
    f_sub = font(r"C:\Windows\Fonts\arial.ttf", 17)

    cols = 4
    cell = 512
    label_h = 52
    gap = 18
    margin = 28
    header = 74
    assets = man["assets"]
    rows = (len(assets) + cols - 1) // cols
    width = margin * 2 + cols * cell + (cols - 1) * gap
    height = header + margin * 2 + rows * (cell + label_h) + (rows - 1) * gap
    img = Image.new("RGB", (width, height), BEIGE)
    draw = ImageDraw.Draw(img)

    title = "flora_wild  |  low-poly foliage  |  Amberreach / Frostvale / Starfall"
    draw.text((margin, 20), title, fill=(64, 56, 48), font=f_title)
    sub = "%d assets  ·  %d triangles total  ·  all flat shaded, GLB" % (
        man["asset_count"], man["total_tris"])
    tw = draw.textlength(title, font=f_title)
    draw.text((width - margin - draw.textlength(sub, font=f_sub), 32),
              sub, fill=(122, 110, 96), font=f_sub)
    draw.line([(margin, header - 12), (width - margin, header - 12)],
              fill=(201, 191, 174), width=2)

    for i, a in enumerate(assets):
        r, c = divmod(i, cols)
        x = margin + c * (cell + gap)
        y = header + margin + r * (cell + label_h + gap)
        png = os.path.join(PREVIEW_DIR, a["name"] + ".png")
        if os.path.exists(png):
            im = Image.open(png).convert("RGB")
            if im.size != (cell, cell):
                im = im.resize((cell, cell), Image.Resampling.LANCZOS)
            img.paste(im, (x, y))
        else:
            draw.rectangle([x, y, x + cell, y + cell], fill=(214, 205, 190))
            draw.text((x + 20, y + 20), "MISSING PREVIEW", fill=(150, 60, 50), font=f_name)
        draw.rectangle([x - 1, y - 1, x + cell, y + cell], outline=(199, 189, 172), width=2)

        name = a["name"]
        size = a["bounds"]["size"]
        meta = "%.2f m  ·  %d tris" % (size[2], a["tris"])
        nw = draw.textlength(name, font=f_name)
        draw.text((x + (cell - nw) / 2, y + cell + 7), name,
                  fill=(58, 50, 43), font=f_name)
        mw = draw.textlength(meta, font=f_meta)
        draw.text((x + (cell - mw) / 2, y + cell + 31), meta,
                  fill=(124, 112, 98), font=f_meta)

    os.makedirs(PREVIEW_DIR, exist_ok=True)
    img.save(SHEET_PATH)
    print("contact sheet ->", SHEET_PATH, img.size)


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------

def run_build(only=None, skip_render=False):
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    results = {}
    for spec in ASSETS:
        if only and spec["name"] not in only:
            continue
        if skip_render:
            scene = reset_scene()
            mb = Builder()
            spec["build"](mb)
            normalise(mb, spec["height"])
            obj, used, _ = make_object(mb, spec["name"])
            st = mesh_stats(obj)
            st["materials"] = used
            results[spec["name"]] = st
            print("[flora_wild] %-12s tris=%-5d h=%.3f minZ=%.4f size=%s (no render)" % (
                spec["name"], st["tris"], st["size"][2], st["min"][2],
                "x".join("%.2f" % v for v in st["size"])))
        else:
            results[spec["name"]] = build_asset(spec)

    if only is None:
        write_manifest(results)
        verify_glbs()
        if not skip_render:
            run_contact_sheet()
    print("[flora_wild] done: %d assets, %d tris" %
          (len(results), sum(r["tris"] for r in results.values())))


def run_contact_sheet():
    if not os.path.exists(PY_EXE):
        print("WARN: Pillow python not found, skipping contact sheet")
        return
    cmd = [PY_EXE, os.path.abspath(__file__), "--contact-sheet"]
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=180)
        if r.stdout.strip():
            print(r.stdout.strip())
        if r.returncode != 0:
            print("contact sheet failed:", r.returncode, r.stderr[-2000:])
    except Exception as exc:
        print("contact sheet subprocess failed:", exc)


def main():
    if HAS_BPY:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
        only = None
        if "--only" in argv:
            i = argv.index("--only")
            only = set(argv[i + 1].split(","))
        skip_render = "--skip-render" in argv
        run_build(only=only, skip_render=skip_render)
    else:
        argv = sys.argv[1:]
        if "--contact-sheet" in argv:
            make_contact_sheet()
        else:
            print(__doc__)


if __name__ == "__main__":
    main()
