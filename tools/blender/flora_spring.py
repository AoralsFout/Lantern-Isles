#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flora_spring.py -- procedural low-poly flora for Lantern Isles (batch flora_spring).

Chapters covered:
  * Mossgarden / Spring Sleep
  * Starfall / Homecoming Night

Run (headless):
  & 'D:\\BlenderPortable\\blender-4.2.9-windows-x64\\blender.exe' -b --python tools/blender/flora_spring.py

Optional flags after "--":
  --only=cherry_tree_a,koi     build/render only selected assets
  --samples=24                 cycles samples (default 24)
  --no-render                  skip preview rendering
  --no-sheet                   skip contact sheet
  --sheet-only                 only rebuild the contact sheet

Conventions (docs/ASSET_BRIEF.md):
  * metres, origin = bottom centre (koi: body centre), forward = Blender -Y
  * all polygons flat shaded, Principled BSDF only, no image textures
  * one merged mesh per asset, semantically named materials
  * GLB: export_format='GLB', export_apply=True, export_yup=True
  * preview: Cycles CPU, 24 samples, 512x512, 3/4 camera, beige backdrop
"""

import bpy
import bmesh
import json
import math
import os
import random
import subprocess
import sys
import time

from mathutils import Euler, Vector

# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------


def _workspace_root():
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.abspath(os.path.join(here, "..", ".."))
    except NameError:
        return os.path.abspath(os.getcwd())


ROOT = _workspace_root()
MODEL_DIR = os.path.join(ROOT, "assets", "models", "foliage")
PREVIEW_DIR = os.path.join(ROOT, "assets", "previews", "flora_spring")
MANIFEST_PATH = os.path.join(MODEL_DIR, "manifest_flora_spring.json")
SYSTEM_PYTHON = r"C:\Users\32506\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

# ---------------------------------------------------------------------------
# palette (sRGB hex straight from docs/ASSET_BRIEF.md + small supporting tones)
# ---------------------------------------------------------------------------

MOSS = "#4F765B"
MOSS_LIGHT = "#86A87C"
BLOSSOM = "#E7B0AE"
BLOSSOM_PALE = "#F4D3CE"
BLOSSOM_DEEP = "#D79B9E"
BARK = "#5D4A3E"
BARK_DARK = "#4A3B31"
STONE = "#8C9480"
MORNING_GOLD = "#F2D49A"

NIGHT = "#242A48"
ROCK_PURPLE = "#4A4664"
PURPLE = "#6A5790"
TEAL = "#72D6CD"
ANCIENT_GOLD = "#E6C07A"
STAR_TEAL = "#8FE6DC"

KOI_ORANGE = "#E8894A"
KOI_WHITE = "#F8F0E2"
KOI_INK = "#2E2A2A"
KOI_FIN = "#F7E6D2"

IVORY = "#E7DDC6"
BAMBOO_STALK = "#5F7C4C"
BAMBOO_NODE = "#B3A677"

MATS = {}

# semantic material registry: name -> spec (all Principled, no textures)
MATERIAL_SPECS = {
    # Mossgarden cherry
    "Bark": dict(color=BARK, rough=0.90),
    "Blossom_Pink": dict(color=BLOSSOM, rough=0.80, double=True),
    "Blossom_Pale": dict(color=BLOSSOM_PALE, rough=0.80, double=True),
    "Blossom_Deep": dict(color=BLOSSOM_DEEP, rough=0.80, double=True),
    # bamboo
    "Bamboo_Stalk": dict(color=BAMBOO_STALK, rough=0.85),
    "Bamboo_Node": dict(color=BAMBOO_NODE, rough=0.85),
    "Leaf_Bamboo": dict(color="#6E8B5A", rough=0.80, double=True),
    # azalea
    "Leaf_Azalea": dict(color=MOSS, rough=0.82, double=True),
    "Leaf_Azalea_Mid": dict(color="#5B805F", rough=0.82, double=True),
    "Leaf_Azalea_Light": dict(color="#6E8B5A", rough=0.82, double=True),
    "Blossom_Azalea": dict(color=BLOSSOM, rough=0.78, double=True),
    "Blossom_Azalea_Pale": dict(color=BLOSSOM_PALE, rough=0.78, double=True),
    "Blossom_Azalea_Deep": dict(color=BLOSSOM_DEEP, rough=0.78, double=True),
    "Blossom_Azalea_Center": dict(color=MORNING_GOLD, rough=0.72),
    # fern
    "Leaf_Fern": dict(color=MOSS, rough=0.82, double=True),
    "Leaf_Fern_Dark": dict(color="#3E6149", rough=0.85, double=True),
    "Leaf_Fern_Tip": dict(color=MOSS_LIGHT, rough=0.80, double=True),
    # grass
    "Grass_Base": dict(color="#3F5F49", rough=0.88),
    "Grass_Blade": dict(color="#6E8B5A", rough=0.82, double=True),
    "Grass_Blade_Light": dict(color=MOSS_LIGHT, rough=0.82, double=True),
    # lilypad
    "Leaf_Lilypad": dict(color="#5E7D4E", rough=0.75, double=True),
    "Leaf_Lilypad_Light": dict(color="#6E8B5A", rough=0.75, double=True),
    "Leaf_Lily_Stem": dict(color=MOSS, rough=0.85),
    "Blossom_Lily": dict(color="#F7E6E2", rough=0.72, double=True),
    "Blossom_Lily_Pink": dict(color=BLOSSOM, rough=0.72, double=True),
    "Blossom_Lily_Center": dict(color=ANCIENT_GOLD, rough=0.75),
    # Starfall glow tree
    "Bark_Glow": dict(color="#3B3652", rough=0.90),
    "Leaf_Glow_Teal": dict(color=TEAL, rough=0.65, emission=3.0,
                           emission_hex="#2C8B86", double=True),
    "Leaf_Glow_Gold": dict(color=ANCIENT_GOLD, rough=0.65, emission=3.0,
                           emission_hex="#8E672A", double=True),
    "Glow_Crystal_Teal": dict(color=STAR_TEAL, rough=0.45, emission=3.5,
                              emission_hex="#2C8B86"),
    "Glow_Crystal_Gold": dict(color=ANCIENT_GOLD, rough=0.45, emission=3.5,
                              emission_hex="#8E672A"),
    # glow mushroom
    "Stem_Ivory": dict(color="#EFE3C8", rough=0.78),
    "Glow_Mushroom_Cap": dict(color=TEAL, rough=0.55, emission=2.5,
                              emission_hex="#2C8B86"),
    "Glow_Mushroom_Cap_Pale": dict(color="#A9EFE4", rough=0.55, emission=2.5,
                                   emission_hex="#4FADA7"),
    "Glow_Mushroom_Gills": dict(color="#2E5E68", rough=0.65, emission=1.0,
                                emission_hex="#173F47", double=True),
    "Glow_Mushroom_Rim": dict(color="#4FA3A8", rough=0.60, emission=1.8,
                              emission_hex="#1F5A62"),
    "Glow_Spore": dict(color="#BFF6EE", rough=0.40, emission=3.0,
                       emission_hex="#7FD8CC"),
    "Glow_Spore_Gold": dict(color=ANCIENT_GOLD, rough=0.40, emission=2.5,
                            emission_hex="#B08A3E"),
    # koi
    "Koi_Orange": dict(color=KOI_ORANGE, rough=0.72),
    "Koi_White": dict(color=KOI_WHITE, rough=0.72),
    "Koi_Ink": dict(color=KOI_INK, rough=0.65),
    "Koi_Fin": dict(color=KOI_FIN, rough=0.68, double=True),
}


def srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_lin(h):
    h = h.lstrip("#")
    return tuple(srgb_to_linear(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def get_mat(name, hex_color, rough=0.85, metallic=0.0, emission=0.0,
            emission_hex=None, double=False):
    """Create (or fetch) a Principled material.  No textures anywhere."""
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    col = hex_lin(hex_color)
    bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic
    if emission > 0.0:
        ec = hex_lin(emission_hex or hex_color)
        bsdf.inputs["Emission Color"].default_value = (*ec, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission
    # glTF exports doubleSided = not use_backface_culling
    m.use_backface_culling = not double
    MATS[name] = m
    return m


def material(name):
    """Fetch/create a material from MATERIAL_SPECS."""
    if name in MATS:
        return MATS[name]
    spec = MATERIAL_SPECS[name]
    return get_mat(name, spec["color"], rough=spec.get("rough", 0.85),
                   metallic=spec.get("metallic", 0.0),
                   emission=spec.get("emission", 0.0),
                   emission_hex=spec.get("emission_hex"),
                   double=spec.get("double", False))


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------


def bez(p0, p1, p2, p3, t):
    mt = 1.0 - t
    return (p0 * (mt ** 3) + p1 * (3.0 * mt * mt * t)
            + p2 * (3.0 * mt * t * t) + p3 * (t ** 3))


def bez_points(p0, p1, p2, p3, count):
    return [bez(Vector(p0), Vector(p1), Vector(p2), Vector(p3), i / (count - 1.0))
            for i in range(count)]


def ico_blob(center, radius, scale=(1.0, 1.0, 1.0), subdiv=2, jitter=0.0,
             seed=0, rot=(0.0, 0.0, 0.0)):
    """Faceted organic blob; icosphere keeps the cut-plane look."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    bm.verts.ensure_lookup_table()
    rng = random.Random(seed)
    rot_m = Euler(rot, "XYZ").to_matrix()
    c = Vector(center)
    verts = []
    for v in bm.verts:
        co = v.co.copy()
        f = 1.0 + (rng.uniform(-jitter, jitter) if jitter else 0.0)
        co.x *= scale[0] * radius * f
        co.y *= scale[1] * radius * f
        co.z *= scale[2] * radius * f
        verts.append(rot_m @ co + c)
    bm.verts.index_update()
    bm.faces.ensure_lookup_table()
    faces = [tuple(v.index for v in face.verts) for face in bm.faces]
    bm.free()
    return verts, faces


def octa(center, size, scale=(1.0, 1.0, 1.0), rot=(0.0, 0.0, 0.0)):
    c = Vector(center)
    base = [Vector((1, 0, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0)),
            Vector((0, -1, 0)), Vector((0, 0, 1)), Vector((0, 0, -1))]
    rm = Euler(rot, "XYZ").to_matrix()
    verts = []
    for p in base:
        q = Vector((p.x * scale[0], p.y * scale[1], p.z * scale[2])) * size
        verts.append(rm @ q + c)
    faces = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4),
             (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
    return verts, faces


def tube(points, radii, sides=6, phase=0.0, twist=0.0,
         cap_start=True, cap_end=True, squash=None):
    """Lofted faceted tube with a stable frame.

    Returns (verts, faces).  Closed tubes are normal-recalculated later.
    """
    pts = [Vector(p) for p in points]
    n = len(pts)
    rings = []
    for i, p in enumerate(pts):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        if t.length < 1e-8:
            t = Vector((0, 0, 1))
        t.normalize()
        ref = Vector((0, 0, 1))
        if abs(t.dot(ref)) > 0.94:
            ref = Vector((1, 0, 0))
        u = t.cross(ref)
        if u.length < 1e-8:
            u = t.cross(Vector((0, 1, 0)))
        u.normalize()
        v = u.cross(t).normalized()
        r = radii[i]
        if squash is None:
            rx = ry = r
        else:
            rx, ry = r * squash[0], r * squash[1]
        tw = twist * (i / (n - 1.0)) if n > 1 else 0.0
        ring = []
        for j in range(sides):
            a = phase + tw + 2.0 * math.pi * j / sides
            ring.append(p + u * (math.cos(a) * rx) + v * (math.sin(a) * ry))
        rings.append(ring)
    verts = [tuple(x) for ring in rings for x in ring]
    faces = []
    for i in range(n - 1):
        for j in range(sides):
            a = i * sides + j
            b = i * sides + (j + 1) % sides
            c = (i + 1) * sides + (j + 1) % sides
            d = (i + 1) * sides + j
            faces.append((a, b, c, d))
    if cap_start:
        faces.append(tuple(range(sides - 1, -1, -1)))
    if cap_end:
        base = (n - 1) * sides
        faces.append(tuple(base + j for j in range(sides)))
    return verts, faces


def ribbon(points, widths, hint=(0.0, 0.0, 1.0)):
    """Flat tapered strip; exported double sided via the material flag."""
    pts = [Vector(p) for p in points]
    hint = Vector(hint)
    rows = []
    for i, p in enumerate(pts):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == len(pts) - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        if t.length < 1e-8:
            t = Vector((0, 0, 1))
        t.normalize()
        side = t.cross(hint)
        if side.length < 1e-6:
            side = t.cross(Vector((1, 0, 0)))
        if side.length < 1e-6:
            side = Vector((1, 0, 0))
        side.normalize()
        w = max(widths[i], 0.0008)
        rows.append((p - side * (w * 0.5), p + side * (w * 0.5)))
    verts = [tuple(v) for row in rows for v in row]
    faces = []
    for i in range(len(rows) - 1):
        a = i * 2
        b = i * 2 + 1
        c = (i + 1) * 2 + 1
        d = (i + 1) * 2
        faces.append((a, b, c, d))
    return verts, faces


def flat_petal(center, angle, length, width, z, lift=0.006):
    """Small ground petal, slightly cupped."""
    cx, cy = center
    dx, dy = math.cos(angle), math.sin(angle)
    sx, sy = -dy, dx
    p0 = (cx - dx * length * 0.5, cy - dy * length * 0.5, z)
    p1 = (cx + sx * width * 0.5, cy + sy * width * 0.5, z + lift * 0.5)
    p2 = (cx + dx * length * 0.5, cy + dy * length * 0.5, z + lift)
    p3 = (cx - sx * width * 0.5, cy - sy * width * 0.5, z + lift * 0.5)
    return [p0, p1, p2, p3], [(0, 2, 1), (0, 3, 2)]


def flower_bloom(bloom_builder, center, normal, petal_len, petals, mat,
                 phase=0.0, tilt=0.42, seed=0):
    """One small blossom made of diamond petals fanning around a normal."""
    n = Vector(normal).normalized()
    u = n.cross(Vector((0, 0, 1)))
    if u.length < 1e-5:
        u = n.cross(Vector((1, 0, 0)))
    u.normalize()
    v = n.cross(u)
    rng = random.Random(seed)
    c = Vector(center)
    for i in range(petals):
        a = phase + 2.0 * math.pi * i / petals + rng.uniform(-0.05, 0.05)
        d = (u * math.cos(a) + v * math.sin(a)).normalized()
        side = n.cross(d)
        L = petal_len * rng.uniform(0.88, 1.10)
        W = L * 0.62
        base = c + d * 0.004 + n * 0.003
        mid = c + d * (L * 0.55) + n * (L * tilt)
        tip = c + d * L + n * (L * tilt * 1.45)
        left = mid + side * (W * 0.5)
        right = mid - side * (W * 0.5)
        bloom_builder.add(([base, left, tip, right],
                           [(0, 2, 1), (0, 3, 2)]), mat)


def flower_center(bloom_builder, center, normal, radius, mat, sides=6):
    n = Vector(normal).normalized()
    u = n.cross(Vector((0, 0, 1)))
    if u.length < 1e-5:
        u = n.cross(Vector((1, 0, 0)))
    u.normalize()
    v = n.cross(u)
    c = Vector(center)
    verts = [tuple(c + n * (radius * 0.9))]
    for i in range(sides):
        a = 2.0 * math.pi * i / sides
        verts.append(tuple(c + u * (math.cos(a) * radius) + v * (math.sin(a) * radius)))
    faces = [(0, 1 + i, 1 + (i + 1) % sides) for i in range(sides)]
    bloom_builder.add((verts, faces), mat)


# ---------------------------------------------------------------------------
# mesh builder
# ---------------------------------------------------------------------------


class MeshBuilder:
    def __init__(self):
        self.verts = []
        self.faces = []
        self.mats = []

    def add(self, part, material, xform=None):
        verts, faces = part
        self.add_multi(verts, faces, [material] * len(faces), xform)

    def add_multi(self, verts, faces, materials, xform=None):
        off = len(self.verts)
        for v in verts:
            p = Vector(v)
            if xform is not None:
                p = xform @ p
            self.verts.append(p)
        for f, m in zip(faces, materials):
            self.faces.append(tuple(i + off for i in f))
            self.mats.append(m)


def finalize(builder, name, pivot="bottom"):
    """Create one flat-shaded mesh object, origin at bottom centre / body centre."""
    verts = [Vector(v) for v in builder.verts]
    if not verts:
        raise RuntimeError("empty asset: " + name)
    mn = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    mx = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    if pivot == "bottom":
        cx = (mn.x + mx.x) * 0.5
        cy = (mn.y + mx.y) * 0.5
        for v in verts:
            v.x -= cx
            v.y -= cy
            v.z -= mn.z
            if v.z < 0.0:
                v.z = 0.0
    else:
        c = (mn + mx) * 0.5
        for v in verts:
            v -= c

    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], builder.faces)
    me.update()

    # consistent outward normals for closed solids only: open leaf/petal
    # strips keep their authored (upward) facing so foliage stays readable.
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    visited = set()
    closed_faces = []
    for face in bm.faces:
        if face.index in visited:
            continue
        comp = []
        stack = [face]
        while stack:
            cur = stack.pop()
            if cur.index in visited:
                continue
            visited.add(cur.index)
            comp.append(cur)
            for edge in cur.edges:
                for nbr in edge.link_faces:
                    if nbr.index not in visited:
                        stack.append(nbr)
        if all(len(edge.link_faces) == 2 for f in comp for edge in f.edges):
            closed_faces.extend(comp)
    if closed_faces:
        bmesh.ops.recalc_face_normals(bm, faces=closed_faces)
    bm.to_mesh(me)
    bm.free()

    order = []
    for m in builder.mats:
        if m not in order:
            order.append(m)
    for m in order:
        me.materials.append(material(m))
    index = {m: i for i, m in enumerate(order)}
    for poly, m in zip(me.polygons, builder.mats):
        poly.material_index = index[m]
        poly.use_smooth = False

    me.validate(verbose=False)
    me.update()

    # triangulate before export so every glTF triangle carries its own flat
    # normal (non-planar quads would otherwise reuse the quad normal)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY",
                          ngon_method="BEAUTY")
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = False
    me.update()

    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    mn = Vector((min(v.co.x for v in me.vertices), min(v.co.y for v in me.vertices),
                 min(v.co.z for v in me.vertices)))
    mx = Vector((max(v.co.x for v in me.vertices), max(v.co.y for v in me.vertices),
                 max(v.co.z for v in me.vertices)))
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    stats = {
        "verts": len(me.vertices),
        "faces": len(me.polygons),
        "tris": tris,
        "bounds": {
            "min": [round(mn.x, 4), round(mn.y, 4), round(mn.z, 4)],
            "max": [round(mx.x, 4), round(mx.y, 4), round(mx.z, 4)],
            "size": [round(mx.x - mn.x, 4), round(mx.y - mn.y, 4), round(mx.z - mn.z, 4)],
        },
        "materials": order,
        "obj": obj,
    }
    return stats


# ---------------------------------------------------------------------------
# shared tree pieces
# ---------------------------------------------------------------------------


def add_roots(b, radius, mat, angles, seed=0, length=0.55):
    rng = random.Random(seed)
    for ang in angles:
        a = math.radians(ang + rng.uniform(-7, 7))
        d = Vector((math.cos(a), math.sin(a), 0.0))
        start = Vector((d.x * radius * 0.30, d.y * radius * 0.30, 0.55))
        mid = Vector((d.x * radius * 1.15, d.y * radius * 1.15, 0.24))
        end = Vector((d.x * (radius + length), d.y * (radius + length), 0.015))
        b.add(tube([start, mid, end], [radius * 0.30, radius * 0.18, 0.028], sides=5), mat)


def add_branch(b, pts, r0, r1, mat, sides=6, twist=0.0):
    n = len(pts)
    radii = [r0 + (r1 - r0) * (i / (n - 1.0)) for i in range(n)]
    b.add(tube(pts, radii, sides=sides, twist=twist), mat)


# ---------------------------------------------------------------------------
# 1. cherry_tree_a -- 8 m, 7 m crown, twisted forked trunk, 6 faceted crowns
# ---------------------------------------------------------------------------


def build_cherry_tree_a(b):
    rng = random.Random(1101)
    bark = "Bark"
    add_roots(b, 0.52, bark, [22, 108, 198, 292], seed=11, length=0.62)

    trunk = [(0.00, 0.00, 0.00), (0.10, 0.05, 0.85), (-0.10, 0.13, 1.72),
             (0.13, -0.02, 2.55), (-0.03, 0.08, 3.30)]
    tr = [0.52, 0.43, 0.35, 0.27, 0.19]
    b.add(tube(trunk, tr, sides=8, twist=0.65), bark)

    branches = [
        ([(0.02, 0.05, 3.15), (0.55, 0.20, 3.85), (1.20, 0.32, 4.55),
          (1.75, 0.42, 5.35)], 0.240, 0.050),
        ([(-0.03, 0.07, 3.20), (-0.65, 0.02, 3.95), (-1.30, -0.18, 4.85),
          (-1.75, -0.30, 5.60)], 0.230, 0.050),
        ([(0.05, 0.04, 3.35), (0.02, 0.06, 4.30), (-0.10, 0.10, 5.35),
          (-0.20, 0.12, 6.30)], 0.180, 0.045),
        ([(0.03, 0.05, 3.30), (0.18, 0.75, 4.05), (0.32, 1.35, 4.85),
          (0.38, 1.62, 5.25)], 0.140, 0.040),
        ([(0.06, 0.02, 3.40), (0.22, -0.70, 4.15), (0.42, -1.40, 5.05),
          (0.46, -1.65, 5.40)], 0.135, 0.040),
        ([(0.04, 0.00, 2.95), (0.55, 0.12, 3.55), (0.95, 0.25, 4.25)],
         0.100, 0.035),
    ]
    for pts, r0, r1 in branches:
        add_branch(b, pts, r0, r1, bark, sides=5 if r0 < 0.15 else 7, twist=0.3)

    # a few dark twigs breaking the blossom silhouette
    twigs = [
        [(2.50, 0.55, 5.42), (3.15, 0.72, 5.68), (3.60, 0.85, 5.78)],
        [(-2.45, -0.35, 5.78), (-3.05, -0.50, 6.02), (-3.42, -0.60, 6.10)],
        [(0.50, -2.10, 5.90), (0.60, -2.70, 6.10), (0.66, -3.00, 6.18)],
        [(-0.20, 0.12, 7.50), (0.00, 0.22, 7.82), (-0.04, 0.30, 7.98)],
        [(1.20, 0.30, 4.05), (1.80, 0.45, 4.30), (2.20, 0.55, 4.42)],
    ]
    for pts in twigs:
        add_branch(b, pts, 0.048, 0.012, bark, sides=4)

    clumps = [
        ((2.05, 0.42, 5.50), 1.40, (1.00, 0.95, 0.66), 0, "Blossom_Pink"),
        ((-1.95, -0.30, 5.85), 1.45, (1.00, 1.00, 0.65), 1, "Blossom_Pale"),
        ((0.40, 1.70, 5.30), 1.25, (1.00, 0.92, 0.66), 2, "Blossom_Pink"),
        ((0.46, -1.72, 5.95), 1.30, (0.98, 1.00, 0.66), 3, "Blossom_Deep"),
        ((-0.20, 0.12, 7.00), 1.45, (1.00, 1.00, 0.64), 4, "Blossom_Pale"),
        ((1.00, 0.25, 4.40), 1.05, (1.00, 0.95, 0.68), 5, "Blossom_Deep"),
    ]
    for center, radius, scale, seed, mat_name in clumps:
        b.add(ico_blob(center, radius, scale=scale, subdiv=2, jitter=0.20, seed=seed),
              mat_name)

    # fallen petals on the moss
    petals = [("Blossom_Pale", 0.250, 0.110), ("Blossom_Pink", 0.280, 0.120),
              ("Blossom_Deep", 0.230, 0.100)]
    for i in range(26):
        a = rng.uniform(0, 2.0 * math.pi)
        r = 0.65 + (rng.random() ** 0.6) * 1.45
        x = math.cos(a) * r
        y = math.sin(a) * r
        mat_name, length, width = petals[i % 3]
        z = 0.010 + rng.uniform(0.0, 0.010)
        b.add(flat_petal((x, y), rng.uniform(0, 2.0 * math.pi), length, width, z,
                         lift=0.012), mat_name)


# ---------------------------------------------------------------------------
# 2. cherry_tree_b -- 5 m, leaning to +X, 3 crowns, wilder gesture
# ---------------------------------------------------------------------------


def build_cherry_tree_b(b):
    rng = random.Random(2202)
    bark = "Bark"
    add_roots(b, 0.36, bark, [15, 130, 250], seed=21, length=0.5)

    trunk = [(0.00, 0.00, 0.00), (0.26, 0.11, 0.80), (0.62, -0.03, 1.60),
             (1.02, 0.10, 2.35), (1.32, 0.05, 2.95)]
    tr = [0.37, 0.30, 0.235, 0.17, 0.115]
    b.add(tube(trunk, tr, sides=7, twist=0.9), bark)

    branches = [
        ([(1.10, 0.08, 2.30), (1.38, 0.34, 3.10), (1.58, 0.58, 3.95)],
         0.125, 0.042),
        ([(1.22, 0.06, 2.60), (1.98, -0.20, 3.25), (2.66, -0.40, 4.02)],
         0.115, 0.040),
        ([(1.28, 0.05, 2.80), (1.05, -0.58, 3.00), (0.80, -1.02, 3.22)],
         0.090, 0.032),
        ([(0.55, 0.00, 1.55), (-0.10, 0.18, 2.10), (-0.42, 0.32, 2.55)],
         0.085, 0.022),
    ]
    for pts, r0, r1 in branches:
        add_branch(b, pts, r0, r1, bark, sides=5, twist=0.4)

    twigs = [
        [(2.66, -0.42, 4.48), (3.12, -0.60, 4.80), (3.42, -0.72, 4.94)],
        [(0.90, -1.00, 3.98), (0.64, -1.30, 4.28), (0.54, -1.48, 4.40)],
        [(1.62, 0.58, 4.38), (1.92, 0.86, 4.72), (2.06, 1.02, 4.86)],
    ]
    for pts in twigs:
        add_branch(b, pts, 0.035, 0.010, bark, sides=4)

    clumps = [
        ((1.55, 0.60, 4.05), 1.18, (1.00, 0.95, 0.71), 0, "Blossom_Pale"),
        ((2.72, -0.40, 4.12), 1.28, (1.00, 1.00, 0.69), 1, "Blossom_Pink"),
        ((0.78, -1.05, 3.24), 0.95, (1.00, 0.95, 0.72), 2, "Blossom_Deep"),
    ]
    for center, radius, scale, seed, mat_name in clumps:
        b.add(ico_blob(center, radius, scale=scale, subdiv=2, jitter=0.20, seed=seed + 10),
              mat_name)

    petals = [("Blossom_Pale", 0.195, 0.085), ("Blossom_Pink", 0.220, 0.095)]
    for i in range(18):
        a = rng.uniform(0, 2.0 * math.pi)
        r = 0.35 + (rng.random() ** 0.6) * 1.55
        x = 0.95 + math.cos(a) * r
        y = math.sin(a) * r
        mat_name, length, width = petals[i % 2]
        b.add(flat_petal((x, y), rng.uniform(0, 2.0 * math.pi), length, width,
                         0.010 + rng.uniform(0, 0.006), lift=0.010), mat_name)


# ---------------------------------------------------------------------------
# 3. bamboo_cluster -- 6 culms, 5.5 m, node bands, feathery top leaves
# ---------------------------------------------------------------------------


def _bamboo_culm(b, bx, by, height, lean, phase, rng):
    side = 6
    node_fracs = [0.20, 0.41, 0.62, 0.83]
    rings = [(0.0, 1.00, False)]
    for frac in node_fracs:
        rings.append((height * frac, 1.40, True))          # bulged node ring
        rings.append((height * frac + 0.12, 0.86, False))   # narrow band top
    rings.append((height, 0.55, False))

    verts = []
    starts = []
    centers = []
    for z, fac, is_node in rings:
        t = z / height
        cx = bx + lean[0] * (t ** 1.3) + 0.028 * math.sin(t * 5.1 + phase)
        cy = by + lean[1] * (t ** 1.3) + 0.028 * math.cos(t * 4.3 + phase)
        rad = (0.060 * (1.0 - t) + 0.027 * t) * fac
        starts.append(len(verts))
        centers.append(Vector((cx, cy, z)))
        for k in range(side):
            a = phase + 2.0 * math.pi * k / side
            verts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad, z))

    faces = []
    mats = []
    for i in range(len(rings) - 1):
        is_node_band = rings[i][2]
        for k in range(side):
            a = starts[i] + k
            bb = starts[i] + (k + 1) % side
            c = starts[i + 1] + (k + 1) % side
            d = starts[i + 1] + k
            faces.append((a, bb, c, d))
            mats.append("Bamboo_Node" if is_node_band else "Bamboo_Stalk")
    faces.append(tuple(range(side - 1, -1, -1)))
    mats.append("Bamboo_Stalk")
    top = starts[-1]
    faces.append(tuple(top + k for k in range(side)))
    mats.append("Bamboo_Stalk")
    b.add_multi(verts, faces, mats)

    # leaf sprays over the upper half: 4-point lanceolate blades
    for frac in (0.56, 0.68, 0.79, 0.89, 0.97):
        z = height * frac
        t = frac
        cx = bx + lean[0] * (t ** 1.3)
        cy = by + lean[1] * (t ** 1.3)
        rad = (0.060 * (1.0 - t) + 0.027 * t)
        for _ in range(4):
            ang = rng.uniform(0, 2.0 * math.pi)
            d = Vector((math.cos(ang), math.sin(ang), 0.0))
            base = Vector((cx, cy, z)) + d * (rad * 0.55)
            length = rng.uniform(0.24, 0.40)
            rise = rng.uniform(0.02, 0.07)
            p1 = base + d * (length * 0.30) + Vector((0, 0, rise))
            p2 = base + d * (length * 0.62) + Vector((0, 0, rise * 0.25))
            p3 = base + d * (length * 0.95) + Vector((0, 0, -length * 0.32))
            b.add(ribbon([base, p1, p2, p3],
                         [0.010, 0.100, 0.070, 0.002], hint=(0, 0, 1)), "Leaf_Bamboo")


def build_bamboo_cluster(b):
    rng = random.Random(3303)
    culms = [
        ((0.00, 0.00), 5.50, (0.03, -0.05), 0.2),
        ((0.19, 0.12), 4.95, (0.26, 0.10), 1.1),
        ((-0.21, 0.09), 5.20, (-0.22, 0.18), 2.0),
        ((0.06, -0.21), 4.45, (0.12, -0.30), 2.8),
        ((-0.13, -0.17), 5.00, (-0.28, -0.12), 3.6),
        ((0.27, -0.07), 4.10, (0.32, 0.16), 4.4),
    ]
    for (bx, by), height, lean, phase in culms:
        _bamboo_culm(b, bx, by, height, lean, phase, rng)

    # sparse dry leaf litter around the base
    for i in range(9):
        a = rng.uniform(0, 2.0 * math.pi)
        r = rng.uniform(0.16, 0.48)
        x = math.cos(a) * r
        y = math.sin(a) * r
        b.add(flat_petal((x, y), rng.uniform(0, 2.0 * math.pi),
                         rng.uniform(0.05, 0.09), rng.uniform(0.012, 0.02),
                         0.004 + rng.uniform(0, 0.004), lift=0.004), "Leaf_Bamboo")


# ---------------------------------------------------------------------------
# 4. azalea_bush -- 1.2 m, 3 irregular green masses + pink blossoms
# ---------------------------------------------------------------------------


def build_azalea_bush(b):
    rng = random.Random(4404)
    # three leafy masses, each with a couple of smaller lobes; subdiv 2 keeps
    # the facets soft enough to read as foliage rather than boulders
    blobs = [
        ((0.00, 0.01, 0.62), 0.50, (1.02, 0.94, 1.02), 0, "Leaf_Azalea"),
        ((-0.40, 0.16, 0.42), 0.38, (0.95, 0.88, 0.95), 1, "Leaf_Azalea"),
        ((0.43, -0.11, 0.46), 0.40, (0.97, 0.92, 0.96), 2, "Leaf_Azalea"),
        ((0.08, -0.05, 0.30), 0.36, (1.00, 0.95, 0.85), 3, "Leaf_Azalea_Mid"),
        ((-0.02, 0.10, 0.90), 0.31, (0.95, 0.92, 0.95), 4, "Leaf_Azalea_Light"),
        ((-0.56, 0.20, 0.55), 0.26, (0.95, 0.90, 0.90), 5, "Leaf_Azalea_Mid"),
        ((0.56, -0.18, 0.58), 0.25, (0.95, 0.90, 0.90), 6, "Leaf_Azalea_Light"),
    ]
    for center, radius, scale, seed, mat_name in blobs:
        b.add(ico_blob(center, radius, scale=scale, subdiv=2, jitter=0.20,
                       seed=seed, rot=(seed * 0.31, seed * 0.17, seed * 0.73)),
              mat_name)

    # small leaf tufts popping out of the mass
    tufts = [
        ((0.16, 0.22, 0.94), 0.15, 20),
        ((-0.18, 0.24, 0.76), 0.13, 21),
        ((0.32, -0.14, 0.70), 0.14, 22),
        ((-0.30, -0.08, 0.56), 0.13, 23),
        ((0.04, 0.02, 1.08), 0.12, 24),
        ((-0.54, 0.12, 0.70), 0.14, 25),
        ((0.56, -0.06, 0.72), 0.14, 26),
        ((0.12, 0.32, 0.50), 0.12, 27),
    ]
    for pos, r, seed in tufts:
        b.add(ico_blob(pos, r, scale=(1.0, 0.95, 0.90), subdiv=1, jitter=0.22,
                       seed=seed, rot=(seed * 0.4, seed * 0.2, seed * 0.6)),
              "Leaf_Azalea_Light")

    flower_mats = ["Blossom_Azalea", "Blossom_Azalea_Pale"]
    for i in range(28):
        center, radius, scale, seed, _ = blobs[i % len(blobs)]
        d = Vector((rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0),
                    rng.uniform(-0.12, 1.0)))
        if d.length < 1e-4:
            d = Vector((0, 0, 1))
        d.normalize()
        surf = Vector(center) + Vector((d.x * scale[0], d.y * scale[1],
                                        d.z * scale[2])) * (radius * 1.05)
        surf.z = max(surf.z, 0.22)
        flower_bloom(b, surf, d, rng.uniform(0.095, 0.115), 5,
                     flower_mats[i % 2], phase=rng.uniform(0, 1.0),
                     tilt=0.42, seed=100 + i)
        flower_center(b, surf + d * 0.010, d, 0.014,
                      "Blossom_Azalea_Center", sides=5)

    for i in range(6):
        center, radius, scale, seed, _ = blobs[i + 1]
        d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1),
                    rng.uniform(0.0, 1.0))).normalized()
        surf = Vector(center) + Vector((d.x * scale[0], d.y * scale[1],
                                        d.z * scale[2])) * (radius * 1.07)
        surf.z = max(surf.z, 0.26)
        b.add(octa(surf, 0.030, scale=(0.8, 0.8, 1.25)), "Blossom_Azalea_Deep")


# ---------------------------------------------------------------------------
# 5. fern -- 0.7 m, 6 curled fronds radiating from the centre
# ---------------------------------------------------------------------------


def build_fern(b):
    rng = random.Random(5505)
    b.add(ico_blob((0.0, 0.0, 0.02), 0.055, scale=(1.0, 1.0, 0.50), subdiv=1,
                   jitter=0.10, seed=3), "Leaf_Fern_Dark")

    for fi in range(6):
        ang = math.radians(30.0 + fi * 60.0 + rng.uniform(-7.0, 7.0))
        d = Vector((math.cos(ang), math.sin(ang), 0.0))
        perp = Vector((-math.sin(ang), math.cos(ang), 0.0))
        L = rng.uniform(0.58, 0.68)
        p0 = Vector((math.cos(ang) * 0.03, math.sin(ang) * 0.03, 0.02))
        p1 = p0 + d * (L * 0.24) + Vector((0, 0, 0.95))
        p2 = p0 + d * (L * 0.68) + Vector((0, 0, 0.66))
        p3 = p0 + d * L + Vector((0, 0, 0.05))
        spine = bez_points(p0, p1, p2, p3, 25)

        # thin rachis in the frond's vertical plane
        rib = [p + perp * 0.003 for p in spine]
        rib_w = [0.018 * (1.0 - 0.55 * (i / 24.0)) for i in range(25)]
        b.add(ribbon(rib, rib_w, hint=perp), "Leaf_Fern_Dark")

        # paired pinnae along the rachis, fanning up and down in-plane
        for j, t in enumerate((0.10, 0.17, 0.24, 0.31, 0.38, 0.45, 0.52,
                               0.59, 0.66, 0.73, 0.80, 0.87, 0.93)):
            idx = min(max(int(t * 24), 1), 23)
            base = spine[idx]
            tan = (spine[idx + 1] - spine[idx - 1]).normalized()
            inplane = tan.cross(perp).normalized()
            length = (0.150 * (1.0 - 0.55 * t)) * rng.uniform(0.90, 1.08)
            for sgn in (1.0, -1.0):
                dirv = (inplane * sgn * 0.95 + tan * 0.28).normalized()
                l0 = base + inplane * sgn * 0.006
                tip = l0 + dirv * length
                w0 = 0.024 * (1.0 - 0.30 * t)
                w1 = 0.003
                verts = [l0 - tan * w0, l0 + tan * w0,
                         tip + tan * w1, tip - tan * w1]
                faces = [(0, 1, 2), (0, 2, 3)]
                mat = "Leaf_Fern_Tip" if j >= 9 else "Leaf_Fern"
                b.add((verts, faces), mat)


# ---------------------------------------------------------------------------
# 6. grass_tuft -- 0.4 m, 7 blades, <= 40 tris (MultiMesh friendly)
# ---------------------------------------------------------------------------


def build_grass_tuft(b):
    rng = random.Random(6606)
    # tiny dark base clump
    sides = 5
    verts = [(0.0, 0.0, 0.018)]
    for i in range(sides):
        a = 2.0 * math.pi * i / sides
        verts.append((math.cos(a) * 0.026, math.sin(a) * 0.026, 0.0))
    faces = [(0, 1 + i, 1 + (i + 1) % sides) for i in range(sides)]
    faces.append(tuple(range(sides, 0, -1)))
    b.add((verts, faces), "Grass_Base")

    for i in range(7):
        ang = math.radians(i * 51.4 + rng.uniform(-12.0, 12.0))
        d = Vector((math.cos(ang), math.sin(ang), 0.0))
        r0 = rng.uniform(0.008, 0.026)
        base = Vector((d.x * r0, d.y * r0, 0.0))
        L = rng.uniform(0.29, 0.41)
        lean = rng.uniform(0.12, 0.26)
        p1 = base + d * (lean * 0.30) + Vector((0, 0, L * 0.55))
        p2 = base + d * (lean * 1.15) + Vector((0, 0, L * 0.98))
        p2 += Vector((-d.y, d.x, 0.0)) * rng.uniform(-0.035, 0.035)
        mat = "Grass_Blade" if i % 3 else "Grass_Blade_Light"
        b.add(ribbon([base, p1, p2], [0.026, 0.015, 0.0012], hint=(0, 0, 1)), mat)


# ---------------------------------------------------------------------------
# 7. lilypad -- 0.6 m, four notched pads + one pink-white flower, z ~= 0
# ---------------------------------------------------------------------------


def _lily_pad(b, cx, cy, radius, rot_deg, z, mat, segments=12, notch=24.0):
    a0 = math.radians(rot_deg + notch * 0.5)
    span = math.radians(360.0 - notch)
    verts = [(cx, cy, z)]
    inner = []
    outer = []
    for i in range(segments):
        a = a0 + span * i / (segments - 1)
        inner.append((cx + math.cos(a) * radius * 0.66,
                      cy + math.sin(a) * radius * 0.66, z + 0.0025))
        outer.append((cx + math.cos(a) * radius,
                      cy + math.sin(a) * radius, z + 0.0075))
    base = 1
    for p in inner:
        verts.append(p)
    for p in outer:
        verts.append(p)
    faces = []
    for i in range(segments - 1):
        faces.append((0, base + i, base + i + 1))
        faces.append((base + i, base + segments + i,
                      base + segments + i + 1, base + i + 1))
    b.add((verts, faces), mat)


def build_lilypad(b):
    pads = [
        (0.000, 0.000, 0.130, 18.0, 0.008, "Leaf_Lilypad"),
        (0.205, 0.085, 0.100, 128.0, 0.006, "Leaf_Lilypad_Light"),
        (-0.185, 0.135, 0.095, 246.0, 0.010, "Leaf_Lilypad"),
        (0.015, -0.195, 0.090, 312.0, 0.007, "Leaf_Lilypad_Light"),
    ]
    for cx, cy, r, rot, z, mat in pads:
        _lily_pad(b, cx, cy, r, rot, z, mat)

    # one pink-white flower on a short stem above the front pad
    fx, fy = 0.095, 0.020
    stem = [Vector((fx, fy, 0.006)), Vector((fx + 0.010, fy + 0.004, 0.08)),
            Vector((fx + 0.004, fy - 0.002, 0.150))]
    b.add(tube(stem, [0.011, 0.009, 0.007], sides=4), "Leaf_Lily_Stem")
    center = Vector((fx + 0.004, fy - 0.002, 0.158))
    flower_bloom(b, center, (0.05, -0.03, 1.0), 0.075, 6, "Blossom_Lily",
                 phase=0.0, tilt=0.36, seed=7)
    flower_bloom(b, center + Vector((0, 0, 0.008)), (0.05, -0.03, 1.0), 0.055, 6,
                 "Blossom_Lily_Pink", phase=math.pi / 6.0, tilt=0.60, seed=8)
    flower_center(b, center + Vector((0.0, 0.0, 0.016)), (0.05, -0.03, 1.0), 0.018,
                  "Blossom_Lily_Center")


# ---------------------------------------------------------------------------
# 8. glow_tree -- 6.5 m, dark twisted trunk, teal + gold emissive crowns
# ---------------------------------------------------------------------------


def build_glow_tree(b):
    rng = random.Random(8808)
    bark = "Bark_Glow"
    add_roots(b, 0.46, bark, [38, 142, 232, 320], seed=31, length=0.62)

    trunk = [(0.00, 0.00, 0.00), (0.20, 0.13, 0.90), (-0.16, 0.24, 1.85),
             (0.28, 0.05, 2.75), (-0.02, -0.12, 3.55), (0.14, 0.06, 4.15)]
    tr = [0.46, 0.37, 0.29, 0.21, 0.14, 0.085]
    b.add(tube(trunk, tr, sides=7, twist=0.9), bark)

    branches = [
        ([(0.10, 0.02, 2.55), (0.78, 0.22, 3.30), (1.24, 0.34, 4.05),
          (1.50, 0.36, 4.85)], 0.155, 0.045),
        ([(-0.04, 0.16, 2.95), (-0.78, 0.02, 3.65), (-1.24, -0.28, 4.35),
          (-1.46, -0.40, 5.00)], 0.150, 0.042),
        ([(0.02, 0.02, 3.15), (0.08, 0.72, 3.75), (0.16, 1.26, 4.15),
          (0.22, 1.46, 4.45)], 0.130, 0.038),
        ([(0.04, -0.02, 3.45), (0.12, -0.78, 4.05), (0.18, -1.30, 4.75),
          (0.20, -1.50, 4.95)], 0.125, 0.036),
        ([(0.12, 0.04, 3.85), (0.02, 0.02, 4.55), (-0.22, 0.04, 5.25),
          (-0.30, 0.10, 5.55)], 0.115, 0.035),
    ]
    for pts, r0, r1 in branches:
        add_branch(b, pts, r0, r1, bark, sides=5, twist=0.4)

    # dark twigs poking through the glow
    twigs = [
        [(1.90, 0.55, 4.75), (2.45, 0.70, 5.02), (2.80, 0.82, 5.12)],
        [(-1.90, -0.50, 4.95), (-2.40, -0.65, 5.18), (-2.70, -0.75, 5.25)],
        [(-0.30, 0.10, 6.15), (-0.42, 0.20, 6.45), (-0.50, 0.28, 6.58)],
        [(0.40, -1.70, 4.58), (0.55, -2.10, 4.82), (0.62, -2.30, 4.92)],
    ]
    for pts in twigs:
        add_branch(b, pts, 0.042, 0.010, bark, sides=4)

    clumps = [
        ((1.52, 0.36, 5.02), 1.20, (1.00, 0.95, 0.68), 0, "Leaf_Glow_Teal"),
        ((-1.46, -0.40, 5.16), 1.30, (1.00, 1.00, 0.66), 1, "Leaf_Glow_Teal"),
        ((0.22, 1.46, 4.64), 1.08, (1.00, 0.95, 0.70), 2, "Leaf_Glow_Gold"),
        ((0.20, -1.50, 5.10), 1.14, (1.00, 0.96, 0.68), 3, "Leaf_Glow_Gold"),
        ((-0.30, 0.10, 5.76), 1.26, (1.00, 1.00, 0.66), 4, "Leaf_Glow_Teal"),
    ]
    for center, radius, scale, seed, mat_name in clumps:
        b.add(ico_blob(center, radius, scale=scale, subdiv=2, jitter=0.20,
                       seed=seed + 40), mat_name)

    # emissive crystal shards caught in the branches
    crystal_mats = ["Glow_Crystal_Teal", "Glow_Crystal_Gold"]
    for i in range(12):
        ci = i % len(clumps)
        center, radius, scale, seed, _ = clumps[ci]
        d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.6, 1))).normalized()
        pos = Vector(center) + Vector((d.x * scale[0], d.y * scale[1],
                                       d.z * scale[2])) * radius * 0.96
        b.add(octa(pos, rng.uniform(0.075, 0.16),
                   scale=(0.55, 0.55, rng.uniform(1.6, 2.6)),
                   rot=(rng.uniform(0, 1), rng.uniform(0, 1), rng.uniform(0, 6))),
              crystal_mats[i % 2])

    # two shards growing from the trunk
    for i, (p, s) in enumerate((((0.34, 0.20, 1.30), 0.10), ((-0.28, 0.22, 2.10), 0.075))):
        b.add(octa(p, s, scale=(0.6, 0.6, 2.2), rot=(0.4, -0.3, 1.0)),
              "Glow_Crystal_Teal" if i == 0 else "Glow_Crystal_Gold")

    # larger shards at the lower crown edge, readable against the sky
    edge_shards = [
        ((2.30, 0.52, 4.62), 0.150, (0.55, 0.55, 2.5), "Glow_Crystal_Teal"),
        ((-2.12, -0.42, 4.64), 0.135, (0.55, 0.55, 2.4), "Glow_Crystal_Gold"),
        ((0.42, 1.92, 4.34), 0.120, (0.55, 0.55, 2.2), "Glow_Crystal_Gold"),
        ((0.38, -2.02, 4.42), 0.130, (0.55, 0.55, 2.3), "Glow_Crystal_Teal"),
        ((-0.96, 0.42, 4.36), 0.115, (0.55, 0.55, 2.1), "Glow_Crystal_Gold"),
    ]
    for pos, size, scale, m in edge_shards:
        b.add(octa(pos, size, scale=scale, rot=(0.5, 0.4, 1.2)), m)


# ---------------------------------------------------------------------------
# 9. glow_mushroom -- 6 glowing mushrooms, ivory stems, 0.9 m cluster
# ---------------------------------------------------------------------------


def _mushroom(b, bx, by, stem_h, cap_r, cap_mat, lean, seed):
    base = Vector((bx, by, 0.0))
    top = Vector((bx + lean[0], by + lean[1], stem_h))
    mid = base.lerp(top, 0.55) + Vector((lean[0] * 0.18 + 0.014, lean[1] * 0.18, 0.0))
    stem_r = 0.030 + cap_r * 0.13
    b.add(tube([base, mid, top], [stem_r * 1.35, stem_r * 0.85, stem_r * 0.72],
               sides=6), "Stem_Ivory")

    sides = 10
    rim_z = stem_h - 0.014
    mid_z = rim_z + cap_r * 0.12
    shoulder_z = stem_h + cap_r * 0.30
    apex_z = stem_h + cap_r * 0.48
    rim = []
    mid_ring = []
    shoulder = []
    for i in range(sides):
        a = 2.0 * math.pi * i / sides + seed * 0.3
        rim.append((top.x + math.cos(a) * cap_r, top.y + math.sin(a) * cap_r, rim_z))
        mid_ring.append((top.x + math.cos(a) * cap_r * 0.80,
                         top.y + math.sin(a) * cap_r * 0.80, mid_z))
        shoulder.append((top.x + math.cos(a) * cap_r * 0.64,
                         top.y + math.sin(a) * cap_r * 0.64, shoulder_z))
    apex = (top.x, top.y, apex_z)
    verts = rim + mid_ring + shoulder + [apex]
    faces = []
    mats = []
    for i in range(sides):
        a = i
        bb = (i + 1) % sides
        faces.append((a, bb, sides + bb, sides + a))
        mats.append("Glow_Mushroom_Rim")
        faces.append((sides + a, sides + bb, 2 * sides + bb, 2 * sides + a))
        mats.append(cap_mat)
        faces.append((2 * sides + i, 2 * sides + bb, 3 * sides))
        mats.append(cap_mat)
    # gills underneath: fan from rim to a recessed centre
    gill_center = len(verts)
    verts.append((top.x, top.y, rim_z + 0.010))
    for i in range(sides):
        a = i
        bb = (i + 1) % sides
        faces.append((a, bb, gill_center))
        mats.append("Glow_Mushroom_Gills")
    b.add_multi(verts, faces, mats)


def build_glow_mushroom(b):
    caps = ["Glow_Mushroom_Cap", "Glow_Mushroom_Cap_Pale"]
    cluster = [
        (0.00, 0.00, 0.760, 0.260, 0, (0.020, 0.010)),
        (0.235, 0.105, 0.455, 0.185, 1, (0.045, 0.020)),
        (-0.195, 0.165, 0.545, 0.200, 1, (-0.050, -0.015)),
        (0.095, -0.225, 0.325, 0.150, 0, (0.015, -0.055)),
        (-0.245, -0.115, 0.215, 0.115, 1, (-0.030, -0.035)),
        (0.290, -0.045, 0.155, 0.095, 0, (0.030, 0.010)),
    ]
    for i, (x, y, stem_h, cap_r, ci, lean) in enumerate(cluster):
        _mushroom(b, x, y, stem_h, cap_r, caps[ci], lean, seed=90 + i)

    # drifting glowing spores
    spores = [(-0.10, 0.12, 0.62), (0.30, 0.22, 0.78), (-0.28, -0.06, 0.50),
              (0.16, -0.18, 0.86), (0.02, 0.30, 0.44)]
    for i, p in enumerate(spores):
        b.add(octa(p, 0.008 + 0.003 * (i % 3), scale=(1.0, 1.0, 1.0),
                   rot=(i, i * 0.7, i * 0.3)),
              "Glow_Spore_Gold" if i in (1, 3) else "Glow_Spore")


# ---------------------------------------------------------------------------
# 10. koi -- 0.5 m long, orange-white, forward = -Y, origin at body centre
# ---------------------------------------------------------------------------


def build_koi(b):
    ys = [-0.250, -0.232, -0.180, -0.108, -0.020, 0.060, 0.125, 0.168]
    rx = [0.012, 0.021, 0.032, 0.042, 0.044, 0.038, 0.024, 0.011]
    rz = [0.011, 0.025, 0.042, 0.055, 0.057, 0.050, 0.032, 0.014]
    sides = 6
    verts = []
    for y, a_r, b_r in zip(ys, rx, rz):
        for k in range(sides):
            ang = 2.0 * math.pi * k / sides
            verts.append((math.cos(ang) * a_r, y, math.sin(ang) * b_r))

    faces = []
    mats = []
    for i in range(len(ys) - 1):
        for k in range(sides):
            a = i * sides + k
            bb = i * sides + (k + 1) % sides
            c = (i + 1) * sides + (k + 1) % sides
            d = (i + 1) * sides + k
            faces.append((a, bb, c, d))
            # white koi with an orange head/back cap and an orange tail base
            if i == 0 and k in (1, 2):
                m = "Koi_Orange"
            elif i == 1 and k in (0, 1, 2):
                m = "Koi_Orange"
            elif i == 2 and k in (1, 2):
                m = "Koi_Orange"
            elif i == 4 and k in (0, 1):
                m = "Koi_Orange"
            elif i == 6 and k in (0, 1, 2):
                m = "Koi_Orange"
            else:
                m = "Koi_White"
            mats.append(m)
    faces.append(tuple(range(sides - 1, -1, -1)))
    mats.append("Koi_White")
    base = (len(ys) - 1) * sides
    faces.append(tuple(base + k for k in range(sides)))
    mats.append("Koi_White")
    b.add_multi(verts, faces, mats)

    # caudal fin (vertical fan, double sided)
    tail = [
        (0.000, 0.160, 0.010), (0.000, 0.250, 0.080), (0.000, 0.220, 0.004),
        (0.000, 0.220, -0.004), (0.000, 0.250, -0.080), (0.000, 0.160, -0.010),
    ]
    tail_faces = [(0, 1, 2), (2, 3, 4), (4, 5, 0), (0, 2, 3), (0, 3, 5)]
    b.add((tail, tail_faces), "Koi_Fin")

    # dorsal fin
    dorsal = [
        (0.000, -0.042, 0.048), (0.000, -0.002, 0.082), (0.000, 0.055, 0.074),
        (0.000, 0.100, 0.034), (0.000, -0.030, 0.050),
    ]
    b.add((dorsal, [(0, 1, 2), (0, 2, 3), (0, 3, 4)]), "Koi_Orange")

    # pectoral fins
    for sgn in (1.0, -1.0):
        fin = [
            (sgn * 0.036, -0.135, -0.008),
            (sgn * 0.092, -0.096, -0.028),
            (sgn * 0.084, -0.050, -0.006),
            (sgn * 0.040, -0.108, 0.004),
        ]
        if sgn > 0:
            b.add((fin, [(0, 1, 2), (0, 2, 3)]), "Koi_Fin")
        else:
            b.add((fin, [(0, 2, 1), (0, 3, 2)]), "Koi_Fin")

    # eyes
    for sgn in (1.0, -1.0):
        b.add(octa((sgn * 0.027, -0.198, 0.016), 0.009, scale=(0.65, 0.65, 0.65)),
              "Koi_Ink")


# ---------------------------------------------------------------------------
# asset table
# ---------------------------------------------------------------------------

ASSET_DEFS = [
    {
        "name": "cherry_tree_a",
        "build": build_cherry_tree_a,
        "chapter": "mossgarden",
        "view": {"elev": 22.0, "azim": 34.0, "disc": 0.80, "dist": 3.45},
        "tags": ["tree", "cherry", "blossom", "spring", "mossgarden", "landmark", "hero"],
        "use": "Hero cherry tree for the Mossgarden terrace / the first-lantern memory under the blossoms; canopy shades the koi pond shore.",
    },
    {
        "name": "cherry_tree_b",
        "build": build_cherry_tree_b,
        "chapter": "mossgarden",
        "view": {"elev": 24.0, "azim": 32.0, "disc": 0.85, "dist": 3.40},
        "tags": ["tree", "cherry", "blossom", "spring", "mossgarden", "slanted"],
        "use": "Secondary wind-bent cherry for grove edges and stair overlooks; pairs with cherry_tree_a for variety.",
    },
    {
        "name": "bamboo_cluster",
        "build": build_bamboo_cluster,
        "chapter": "mossgarden",
        "view": {"elev": 21.0, "azim": 36.0, "disc": 0.85, "dist": 3.35},
        "tags": ["bamboo", "cluster", "spring", "mossgarden", "foliage", "wind"],
        "use": "Bamboo screen along the moss garden path and behind the broken torii; gently wind-swayed via the Leaf shader.",
    },
    {
        "name": "azalea_bush",
        "build": build_azalea_bush,
        "chapter": "mossgarden",
        "view": {"elev": 26.0, "azim": 34.0, "disc": 1.0, "dist": 3.05},
        "tags": ["bush", "shrub", "flower", "spring", "mossgarden", "detail"],
        "use": "Path-side azalea clumps and terrace planting; instant pink accents near stone steps.",
    },
    {
        "name": "fern",
        "build": build_fern,
        "chapter": "mossgarden",
        "view": {"elev": 34.0, "azim": 38.0, "disc": 1.0, "dist": 2.95},
        "tags": ["fern", "groundcover", "spring", "mossgarden", "foliage"],
        "use": "Damp groundcover around stone basins, cave mouth and shaded terraces.",
    },
    {
        "name": "grass_tuft",
        "build": build_grass_tuft,
        "chapter": "mossgarden",
        "view": {"elev": 32.0, "azim": 40.0, "disc": 1.0, "dist": 2.85},
        "tags": ["grass", "tuft", "groundcover", "multimesh", "spring", "mossgarden"],
        "use": "MultiMesh ground scatter (36 tris) across moss terraces; scale/rotate per instance for variation.",
    },
    {
        "name": "lilypad",
        "build": build_lilypad,
        "chapter": "mossgarden",
        "view": {"elev": 40.0, "azim": 38.0, "disc": 1.0, "dist": 2.85},
        "tags": ["water", "lilypad", "flower", "koi-pond", "spring", "mossgarden"],
        "use": "Koi pond surface dressing; place at water height, pads lie at z~0 and the flower rises 0.15 m.",
    },
    {
        "name": "glow_tree",
        "build": build_glow_tree,
        "chapter": "starfall",
        "view": {"elev": 22.0, "azim": 34.0, "disc": 0.80, "exposure": -1.05, "dist": 3.40},
        "tags": ["tree", "glow", "emissive", "starfall", "night", "landmark"],
        "use": "Bioluminescent landmark tree for the floating Starfall isles; teal/gold crowns read as local light sources.",
    },
    {
        "name": "glow_mushroom",
        "build": build_glow_mushroom,
        "chapter": "starfall",
        "view": {"elev": 28.0, "azim": 36.0, "disc": 1.0, "exposure": -0.65, "dist": 2.90},
        "tags": ["mushroom", "glow", "emissive", "starfall", "cluster", "detail"],
        "use": "Glowing fungus clusters along Starfall rocks and mirror-lake banks; ivory stems, cyan caps at emission 2.5.",
    },
    {
        "name": "koi",
        "build": build_koi,
        "chapter": "mossgarden",
        "view": {"elev": 20.0, "azim": 42.0, "disc": None, "dist": 3.05},
        "pivot": "center",
        "tags": ["fish", "koi", "creature", "water", "mossgarden", "animated-by-code"],
        "use": "Koi pond swimmer; path/animate in code. Forward is Blender -Y (Godot +Z), origin at body centre, 0.5 m long.",
    },
]


# ---------------------------------------------------------------------------
# preview studio
# ---------------------------------------------------------------------------


def _beige_world():
    w = bpy.data.worlds.new("PreviewWorld")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    mix = nt.nodes.new("ShaderNodeMixShader")
    lp = nt.nodes.new("ShaderNodeLightPath")
    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_cam.inputs["Color"].default_value = (*hex_lin("#E8DFD1"), 1.0)
    bg_cam.inputs["Strength"].default_value = 1.0
    bg_amb = nt.nodes.new("ShaderNodeBackground")
    bg_amb.inputs["Color"].default_value = (*hex_lin("#E8DFD1"), 1.0)
    bg_amb.inputs["Strength"].default_value = 0.32
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg_amb.outputs["Background"], mix.inputs[1])
    nt.links.new(bg_cam.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return w


def _add_sun(name, direction, energy, color, angle):
    data = bpy.data.lights.new(name, "SUN")
    data.energy = energy
    data.color = color
    data.angle = angle
    ob = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (0.0, 0.0, 25.0)
    ob.rotation_euler = (-Vector(direction)).to_track_quat("-Z", "Y").to_euler()
    return ob


def _add_ground_plane():
    """Large studio ground; fills the frame with a soft beige floor."""
    size = 1200.0
    verts = [(-size, -size, -0.004), (size, -size, -0.004),
             (size, size, -0.004), (-size, size, -0.004)]
    faces = [(0, 1, 2, 3)]
    me = bpy.data.meshes.new("PreviewGround")
    me.from_pydata(verts, [], faces)
    me.update()
    for p in me.polygons:
        p.use_smooth = False
    m = bpy.data.materials.new("PreviewGroundMat")
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*hex_lin("#D8CCB9"), 1.0)
    bsdf.inputs["Roughness"].default_value = 0.95
    me.materials.append(m)
    ob = bpy.data.objects.new("PreviewGround", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def setup_preview(center, radius, elev, azim, disc_mult, samples, out_path, view_transform,
                  exposure=0.0, dist_mult=3.55):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 2
    scene.cycles.transmission_bounces = 2
    scene.cycles.use_adaptive_sampling = False
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = out_path
    try:
        scene.view_settings.view_transform = view_transform
        scene.view_settings.look = "None"
    except Exception:
        scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = exposure
    scene.view_settings.gamma = 1.0

    scene.world = _beige_world()

    el = math.radians(elev)
    az = math.radians(azim)
    view_dir = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el),
                       math.sin(el))).normalized()
    target = Vector(center)
    dist = radius * dist_mult
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 50.0
    cam_data.sensor_width = 36.0
    cam_data.sensor_fit = "AUTO"
    cam_data.clip_start = 0.01
    cam_data.clip_end = 500.0
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = target + view_dir * dist
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    front = Vector((math.sin(az), -math.cos(az), 0.0)).normalized()
    right = Vector((math.cos(az), math.sin(az), 0.0)).normalized()
    up = Vector((0.0, 0.0, 1.0))
    key_dir = (front * 0.72 - right * 0.62 + up * 1.15).normalized()
    fill_dir = (front * 0.75 + right * 0.95 + up * 0.30).normalized()
    rim_dir = (-front * 0.85 + right * 0.35 + up * 0.70).normalized()
    _add_sun("KeySun", key_dir, 2.35, (1.0, 0.90, 0.76), 0.10)
    _add_sun("FillSun", fill_dir, 0.85, (0.72, 0.83, 1.0), 0.40)
    _add_sun("RimSun", rim_dir, 1.60, (0.92, 0.95, 1.0), 0.18)

    if disc_mult:
        _add_ground_plane()

    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print("  render %.1fs -> %s" % (time.time() - t0, out_path))


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


def export_glb(obj, path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_animations=False,
    )


# ---------------------------------------------------------------------------
# contact sheet (system python + Pillow, so the whole batch stays reproducible)
# ---------------------------------------------------------------------------

CONTACT_SHEET_SRC = r'''
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

manifest_path = sys.argv[1]
preview_dir = sys.argv[2]
with open(manifest_path, "r", encoding="utf-8") as fh:
    data = json.load(fh)
assets = data["assets"]

cols = 4
cell = 512
gap = 22
margin = 34
label_h = 50
head_h = 92
rows = (len(assets) + cols - 1) // cols
W = margin * 2 + cols * cell + (cols - 1) * gap
H = margin * 2 + head_h + rows * (cell + label_h) + (rows - 1) * gap

bg = (233, 224, 209)
panel = (247, 242, 232)
border = (211, 197, 178)
ink = (58, 46, 38)
sub = (122, 105, 91)

sheet = Image.new("RGB", (W, H), bg)
d = ImageDraw.Draw(sheet)


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


bold = load_font("C:/Windows/Fonts/segoeuib.ttf", 24)
header = load_font("C:/Windows/Fonts/segoeuib.ttf", 30)
small = load_font("C:/Windows/Fonts/segoeui.ttf", 19)

d.text((margin, margin + 4), "FLORA_SPRING  /  MOSSGARDEN & STARFALL",
       font=header, fill=ink)
d.text((margin, margin + 50),
       "10 low-poly flora assets  |  flat shaded  |  Blender 4.2.9  |  Cycles CPU 24 spp",
       font=small, fill=sub)

for i, asset in enumerate(assets):
    r = i // cols
    c = i % cols
    x = margin + c * (cell + gap)
    y = margin + head_h + r * (cell + label_h + gap)
    d.rectangle([x - 5, y - 5, x + cell + 5, y + cell + label_h - 2],
                fill=panel, outline=border, width=2)
    img_path = os.path.join(preview_dir, asset["name"] + ".png")
    if os.path.exists(img_path):
        im = Image.open(img_path).convert("RGB")
        im = im.resize((cell, cell), Image.LANCZOS)
        sheet.paste(im, (x, y))
    else:
        d.rectangle([x, y, x + cell, y + cell], fill=(226, 216, 201))
        d.text((x + 22, y + 22), "missing preview", font=small, fill=ink)
    d.text((x + 14, y + cell + 12), asset["name"], font=bold, fill=ink)
    meta = "%d tris" % asset["tris"]
    tw = d.textlength(meta, font=small)
    d.text((x + cell - 14 - tw, y + cell + 16), meta, font=small, fill=sub)

out = os.path.join(preview_dir, "contact_sheet.png")
sheet.save(out)
print("contact_sheet:", out, W, "x", H)
'''


def build_contact_sheet():
    if not os.path.exists(SYSTEM_PYTHON):
        print("WARNING: system python missing, cannot build contact sheet")
        return
    proc = subprocess.run([SYSTEM_PYTHON, "-", MANIFEST_PATH, PREVIEW_DIR],
                          input=CONTACT_SHEET_SRC, text=True,
                          capture_output=True)
    print(proc.stdout.strip())
    if proc.returncode != 0:
        print("contact sheet failed:")
        print(proc.stderr)
        raise SystemExit(proc.returncode)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def parse_args():
    argv = sys.argv
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    opts = {"only": None, "samples": 24, "render": True, "sheet": True,
            "sheet_only": False, "transform": "Standard"}
    for a in args:
        if a.startswith("--only="):
            opts["only"] = [s.strip() for s in a.split("=", 1)[1].split(",") if s.strip()]
        elif a.startswith("--samples="):
            opts["samples"] = int(a.split("=", 1)[1])
        elif a == "--no-render":
            opts["render"] = False
        elif a == "--no-sheet":
            opts["sheet"] = False
        elif a == "--sheet-only":
            opts["sheet_only"] = True
        elif a.startswith("--transform="):
            opts["transform"] = a.split("=", 1)[1]
    return opts


def main():
    opts = parse_args()
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)

    if opts["sheet_only"]:
        build_contact_sheet()
        return

    selected = [d for d in ASSET_DEFS if not opts["only"] or d["name"] in opts["only"]]
    if not selected:
        raise SystemExit("no assets selected")

    print("=" * 72)
    print("flora_spring: %d assets, samples=%d, transform=%s" %
          (len(selected), opts["samples"], opts["transform"]))
    print("=" * 72)

    results = []
    total_tris = 0
    for definition in selected:
        name = definition["name"]
        print("\n[%s]" % name)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.unit_settings.system = "METRIC"
        scene.unit_settings.scale_length = 1.0
        MATS.clear()
        if not hasattr(bpy.ops.export_scene, "gltf"):
            try:
                bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
            except Exception:
                pass

        builder = MeshBuilder()
        definition["build"](builder)
        stats = finalize(builder, name, pivot=definition.get("pivot", "bottom"))
        obj = stats["obj"]
        print("  tris=%d verts=%d size=%s" %
              (stats["tris"], stats["verts"], stats["bounds"]["size"]))

        glb_path = os.path.join(MODEL_DIR, name + ".glb")
        export_glb(obj, glb_path)
        print("  glb -> %s (%.1f KB)" % (glb_path, os.path.getsize(glb_path) / 1024.0))

        b = stats["bounds"]
        center = ((b["min"][0] + b["max"][0]) * 0.5,
                  (b["min"][1] + b["max"][1]) * 0.5,
                  (b["min"][2] + b["max"][2]) * 0.5)
        radius = 0.5 * math.sqrt(sum((b["max"][i] - b["min"][i]) ** 2 for i in range(3)))
        radius = max(radius, 0.05)

        if opts["render"]:
            preview_path = os.path.join(PREVIEW_DIR, name + ".png")
            view = definition["view"]
            setup_preview(center, radius, view["elev"], view["azim"], view["disc"],
                          opts["samples"], preview_path, opts["transform"],
                          exposure=view.get("exposure", 0.0),
                          dist_mult=view.get("dist", 3.55))
        else:
            preview_path = None

        results.append({
            "name": name,
            "file": "assets/models/foliage/%s.glb" % name,
            "preview": "assets/previews/flora_spring/%s.png" % name,
            "bounds": stats["bounds"],
            "tris": stats["tris"],
            "verts": stats["verts"],
            "materials": stats["materials"],
            "tags": definition["tags"],
            "suggested_use": definition["use"],
            "chapter": definition["chapter"],
            "pivot": "body_center" if definition.get("pivot") == "center" else "bottom_center",
            "forward": "-Y",
        })
        total_tris += stats["tris"]

    manifest = {
        "batch": "flora_spring",
        "title": "Mossgarden / Spring Sleep + Starfall / Homecoming Night",
        "generator": "tools/blender/flora_spring.py",
        "blender": "4.2.9 LTS",
        "units": "meters",
        "up_axis": "Blender +Z (exported glTF +Y with export_yup)",
        "forward": "-Y in Blender (Godot +Z after glTF import)",
        "origin": "bottom-centre, ground at z=0 (koi: body centre)",
        "coordinate_system": {
            "up": "Z",
            "forward": "-Y",
            "note": "bounds are Blender-space metres before glTF Y-up conversion",
        },
        "asset_count": len(results),
        "total_tris": total_tris,
        "assets": results,
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    print("\nmanifest -> %s" % MANIFEST_PATH)
    print("total tris: %d across %d assets" % (total_tris, len(results)))

    if opts["sheet"] and len(selected) == len(ASSET_DEFS):
        build_contact_sheet()
    elif opts["sheet"] and not opts["only"]:
        build_contact_sheet()

    print("\nDONE")


if __name__ == "__main__":
    main()
