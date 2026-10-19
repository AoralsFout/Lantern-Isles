"""
architecture.py -- batch "architecture" for Lantern Isles / 灯屿行记.

10 low-poly building / structure assets, modelled procedurally in Blender 4.2 LTS,
exported as GLB (Y-up) at assets/models/architecture/, preview-rendered with Cycles
CPU at 512x512 into assets/previews/architecture/, plus a labeled contact sheet.

Conventions
-----------
* metres, unit scale 1.0
* every asset is a single flat-shaded mesh with semantic material slots
* origin at the centre of the footprint on the ground plane (bridges: deck centre)
* assets face Blender -Y (exported to Godot +Z)
* glowing parts use the material named "Glow" (Principled emission 2.5)

Run:
  & 'D:\\BlenderPortable\\blender-4.2.9-windows-x64\\blender.exe' -b --python tools/blender/architecture.py
Optional:
  -- --only=torii_gate,well --samples=8 --no-sheet
  -- --sheet-only
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

# ----------------------------------------------------------------------------
# paths / globals
# ----------------------------------------------------------------------------

ROOT = r"E:\GodotProjects\xiang-ting-game"
MODEL_DIR = os.path.join(ROOT, "assets", "models", "architecture")
PREVIEW_DIR = os.path.join(ROOT, "assets", "previews", "architecture")
MANIFEST = os.path.join(MODEL_DIR, "manifest_architecture.json")
PIL_PYTHON = r"C:\Users\32506\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

for _d in (MODEL_DIR, PREVIEW_DIR):
    os.makedirs(_d, exist_ok=True)

# sRGB hex, roughness, metallic, emission strength
MATERIAL_DEFS = {
    "Stone":        ("#8C9480", 0.90, 0.0, 0.0),
    "StoneLight":   ("#A7A996", 0.90, 0.0, 0.0),
    "StoneDark":    ("#6F786B", 0.92, 0.0, 0.0),
    "StoneWarm":    ("#B39A7A", 0.90, 0.0, 0.0),
    "Wood":         ("#6B5548", 0.86, 0.0, 0.0),
    "WoodDark":     ("#4E3E34", 0.90, 0.0, 0.0),
    "WoodLight":    ("#8A6E56", 0.86, 0.0, 0.0),
    "Timber":       ("#7A5C3F", 0.88, 0.0, 0.0),
    "TimberGrey":   ("#8A7A66", 0.92, 0.0, 0.0),
    "Roof":         ("#554A3F", 0.88, 0.0, 0.0),
    "RoofEdge":     ("#3A322C", 0.90, 0.0, 0.0),
    "Vermilion":    ("#A9503F", 0.86, 0.0, 0.0),
    "VermilionDark": ("#8A4034", 0.90, 0.0, 0.0),
    "VermilionPale": ("#BD705C", 0.88, 0.0, 0.0),
    "Moss":         ("#4F765B", 0.95, 0.0, 0.0),
    "MossLight":    ("#86A87C", 0.95, 0.0, 0.0),
    "Vine":         ("#5E7D4E", 0.95, 0.0, 0.0),
    "Snow":         ("#ECF2EF", 0.85, 0.0, 0.0),
    "Ice":          ("#B8D9DF", 0.55, 0.0, 0.0),
    "Cream":        ("#E8DCC0", 0.90, 0.0, 0.0),
    "Ochre":        ("#C89A55", 0.90, 0.0, 0.0),
    "OchreDark":    ("#8A4F3A", 0.90, 0.0, 0.0),
    "Sand":         ("#DDBB7E", 0.92, 0.0, 0.0),
    "CanvasDark":   ("#B49B76", 0.92, 0.0, 0.0),
    "Teal":         ("#4E9A8F", 0.90, 0.0, 0.0),
    "Rope":         ("#C2A36B", 0.95, 0.0, 0.0),
    "Metal":        ("#4A4A46", 0.60, 0.30, 0.0),
    "Gold":         ("#E6C07A", 0.50, 0.35, 0.0),
    "Water":        ("#2F5450", 0.45, 0.0, 0.0),
    "Plaster":      ("#DCD3BF", 0.90, 0.0, 0.0),
    "Clay":         ("#B57B57", 0.90, 0.0, 0.0),
    "AgedPaper":    ("#CFC4AC", 0.90, 0.0, 0.0),
    "Glow":         ("#F2B15E", 0.60, 0.0, 2.5),
}


def srgb_to_linear(c):
    c = max(0.0, min(1.0, c))
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_linear(hex_code):
    h = hex_code.lstrip("#")
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def make_material(name):
    spec = MATERIAL_DEFS[name]
    hex_code, rough, metal, emis = spec
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.use_backface_culling = False
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    col = hex_linear(hex_code)
    bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emis > 0.0:
        bsdf.inputs["Emission Color"].default_value = (*col, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emis
    mat.diffuse_color = (*col, 1.0)
    return mat


# ----------------------------------------------------------------------------
# geometry builder
# ----------------------------------------------------------------------------

def _rad(rot):
    return Euler(tuple(math.radians(a) for a in rot), "XYZ").to_matrix()


def _basis(axis):
    """two unit vectors perpendicular to axis (not necessarily axis-orthonormal order)."""
    u = axis.normalized()
    ref = Vector((0.0, 0.0, 1.0)) if abs(u.z) < 0.95 else Vector((1.0, 0.0, 0.0))
    a = u.cross(ref).normalized()
    b = u.cross(a).normalized()
    return u, a, b


ICO_V = None
ICO_F = None


def _icosahedron():
    global ICO_V, ICO_F
    if ICO_V is not None:
        return ICO_V, ICO_F
    t = (1.0 + math.sqrt(5.0)) / 2.0
    verts = [
        (-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
        (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
        (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1),
    ]
    faces = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    ]
    ICO_V = [Vector(v).normalized() for v in verts]
    ICO_F = faces
    return ICO_V, ICO_F


class Builder:
    def __init__(self, seed=1):
        self.verts = []
        self.faces = []
        self.fmats = []
        self.mat_names = []
        self.rng = random.Random(seed)

    # -- low level ---------------------------------------------------------
    def add(self, verts, faces, mat):
        if mat not in self.mat_names:
            self.mat_names.append(mat)
        mi = self.mat_names.index(mat)
        base = len(self.verts)
        self.verts.extend((float(v[0]), float(v[1]), float(v[2])) for v in verts)
        for f in faces:
            self.faces.append(tuple(base + int(i) for i in f))
            self.fmats.append(mi)

    def add_multi(self, verts, faces, mats):
        """one shared vertex block, per-face materials (keeps a roof one closed shell)."""
        base = len(self.verts)
        self.verts.extend((float(v[0]), float(v[1]), float(v[2])) for v in verts)
        for f, mat in zip(faces, mats):
            if mat not in self.mat_names:
                self.mat_names.append(mat)
            mi = self.mat_names.index(mat)
            self.faces.append(tuple(base + int(i) for i in f))
            self.fmats.append(mi)

    def rotate_z(self, deg):
        R = _rad((0, 0, deg))
        self.verts = [tuple(R @ Vector(v)) for v in self.verts]

    def translate(self, d):
        dx, dy, dz = d
        self.verts = [(x + dx, y + dy, z + dz) for x, y, z in self.verts]

    def jitter_verts(self, amp=0.01):
        r = self.rng
        self.verts = [(x + r.uniform(-amp, amp),
                       y + r.uniform(-amp, amp),
                       z + r.uniform(-amp, amp)) for x, y, z in self.verts]

    # -- primitives --------------------------------------------------------
    def box(self, c, s, mat, rot=(0, 0, 0), taper=1.0, taper_y=None, top_off=(0.0, 0.0)):
        sx, sy, sz = s
        tx = taper
        ty = taper if taper_y is None else taper_y
        ox, oy = top_off
        L = [
            (-sx / 2, -sy / 2, -sz / 2), (sx / 2, -sy / 2, -sz / 2),
            (sx / 2, sy / 2, -sz / 2), (-sx / 2, sy / 2, -sz / 2),
            (-sx / 2 * tx + ox, -sy / 2 * ty + oy, sz / 2),
            (sx / 2 * tx + ox, -sy / 2 * ty + oy, sz / 2),
            (sx / 2 * tx + ox, sy / 2 * ty + oy, sz / 2),
            (-sx / 2 * tx + ox, sy / 2 * ty + oy, sz / 2),
        ]
        R = _rad(rot)
        V = [R @ Vector(v) + Vector(c) for v in L]
        F = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        self.add(V, F, mat)

    def cylinder(self, c, r, h, mat, sides=8, rtop=None, rot=(0, 0, 0), phase=0.0):
        if rtop is None:
            rtop = r
        L = []
        steps = sides
        for k in range(2):
            rad = r if k == 0 else rtop
            z = -h / 2 if k == 0 else h / 2
            for i in range(steps):
                a = phase + 2.0 * math.pi * i / steps
                L.append((rad * math.cos(a), rad * math.sin(a), z))
        F = []
        for i in range(steps):
            j = (i + 1) % steps
            F.append((i, j, steps + j, steps + i))
        F.append(tuple(range(steps - 1, -1, -1)))
        F.append(tuple(range(steps, 2 * steps)))
        R = _rad(rot)
        V = [R @ Vector(v) + Vector(c) for v in L]
        self.add(V, F, mat)

    def tube(self, p1, p2, r1, r2, mat, sides=6, phase=0.0, caps=True):
        p1 = Vector(p1)
        p2 = Vector(p2)
        axis = p2 - p1
        if axis.length < 1e-7:
            return
        u, a, b = _basis(axis)
        L = []
        for rad, p in ((r1, p1), (r2, p2)):
            for i in range(sides):
                ang = phase + 2.0 * math.pi * i / sides
                L.append(p + a * (math.cos(ang) * rad) + b * (math.sin(ang) * rad))
        F = []
        for i in range(sides):
            j = (i + 1) % sides
            F.append((i, j, sides + j, sides + i))
        if caps:
            F.append(tuple(range(sides - 1, -1, -1)))
            F.append(tuple(range(sides, 2 * sides)))
        self.add(L, F, mat)

    def spike(self, base, tip, r, mat, sides=6, phase=0.0):
        base = Vector(base)
        tip = Vector(tip)
        axis = tip - base
        if axis.length < 1e-7:
            return
        u, a, b = _basis(axis)
        L = []
        for i in range(sides):
            ang = phase + 2.0 * math.pi * i / sides
            L.append(base + a * (math.cos(ang) * r) + b * (math.sin(ang) * r))
        apex = len(L)
        L.append(tip)
        F = [(i, (i + 1) % sides, apex) for i in range(sides)]
        F.append(tuple(range(sides - 1, -1, -1)))
        self.add(L, F, mat)

    def annulus(self, c, ro, ri, h, mat, sides=12, phase=0.0, rot=(0, 0, 0)):
        L = []
        for z in (-h / 2, h / 2):
            for rad in (ro, ri):
                for i in range(sides):
                    ang = phase + 2.0 * math.pi * i / sides
                    L.append((rad * math.cos(ang), rad * math.sin(ang), z))
        ob, ot, ib, it = 0, sides, 2 * sides, 3 * sides
        F = []
        for i in range(sides):
            j = (i + 1) % sides
            F.append((ob + i, ob + j, ot + j, ot + i))
            F.append((ib + i, it + i, it + j, ib + j))
            F.append((ot + i, ot + j, it + j, it + i))
            F.append((ob + i, ib + i, ib + j, ob + j))
        R = _rad(rot)
        V = [R @ Vector(v) + Vector(c) for v in L]
        self.add(V, F, mat)

    def ico(self, c, radius, mat, scale=(1.0, 1.0, 1.0), subdiv=0,
            rot=(0, 0, 0), jitter=0.0):
        verts, faces = _icosahedron()
        verts = [v.copy() for v in verts]
        faces = list(faces)
        if subdiv > 0:
            for _ in range(subdiv):
                cache = {}
                new_faces = []

                def mid(a, b):
                    key = (a, b) if a < b else (b, a)
                    if key in cache:
                        return cache[key]
                    m = (verts[a] + verts[b]).normalized()
                    verts.append(m)
                    cache[key] = len(verts) - 1
                    return cache[key]

                for a, b, cc in faces:
                    ab = mid(a, b)
                    bc = mid(b, cc)
                    ca = mid(cc, a)
                    new_faces += [(a, ab, ca), (b, bc, ab), (cc, ca, bc), (ab, bc, ca)]
                faces = new_faces
        R = _rad(rot)
        V = []
        for v in verts:
            p = v.normalized()
            rr = radius * (1.0 + self.rng.uniform(-jitter, jitter))
            p = Vector((p.x * scale[0] * rr, p.y * scale[1] * rr, p.z * scale[2] * rr))
            V.append(R @ p + Vector(c))
        self.add(V, faces, mat)

    def swept_beam(self, points, width, height, mat):
        pts = [Vector(p) for p in points]
        n = len(pts)
        L = []
        for i, p in enumerate(pts):
            if i == 0:
                tan = (pts[1] - pts[0]).normalized()
            elif i == n - 1:
                tan = (pts[-1] - pts[-2]).normalized()
            else:
                tan = (pts[i + 1] - pts[i - 1]).normalized()
            side = Vector((0.0, 1.0, 0.0))
            up = tan.cross(side).normalized()
            c1 = p - side * (width / 2) - up * (height / 2)
            c2 = p + side * (width / 2) - up * (height / 2)
            c3 = p + side * (width / 2) + up * (height / 2)
            c4 = p - side * (width / 2) + up * (height / 2)
            L += [c1, c2, c3, c4]
        F = []
        for i in range(n - 1):
            a = i * 4
            b = (i + 1) * 4
            F += [(a, a + 1, b + 1, b), (a + 1, a + 2, b + 2, b + 1),
                  (a + 2, a + 3, b + 3, b + 2), (a + 3, a, b, b + 3)]
        F.append((0, 3, 2, 1))
        last = (n - 1) * 4
        F.append((last, last + 1, last + 2, last + 3))
        self.add(L, F, mat)

    # -- roofs -------------------------------------------------------------
    def hip_roof(self, cx, cy, eave_z, ex, ey, rise, ridge_half, thickness,
                 corner_lift=0.0, mid_lift=0.0, mat_top="Roof", mat_under="RoofEdge",
                 mat_edge="RoofEdge", ridge_mat="RoofEdge", ridge_beam=True):
        z0 = eave_z
        ring = [
            (cx - ex, cy - ey, z0 + corner_lift), (cx, cy - ey, z0 + mid_lift),
            (cx + ex, cy - ey, z0 + corner_lift), (cx + ex, cy, z0 + mid_lift),
            (cx + ex, cy + ey, z0 + corner_lift), (cx, cy + ey, z0 + mid_lift),
            (cx - ex, cy + ey, z0 + corner_lift), (cx - ex, cy, z0 + mid_lift),
        ]
        r1 = (cx - ridge_half, cy, z0 + rise)
        r2 = (cx + ridge_half, cy, z0 + rise)
        top = ring + [r1, r2]
        bottom = [(x, y, z - thickness) for (x, y, z) in top]
        top_faces = [
            (0, 1, 8), (1, 2, 9, 8), (2, 3, 9), (3, 4, 9),
            (4, 5, 9, 8), (5, 6, 8), (6, 7, 8), (7, 0, 8),
        ]
        bottom_faces = [tuple(i + 10 for i in reversed(f)) for f in top_faces]
        fascia = [(i, (i + 1) % 8, (i + 1) % 8 + 10, i + 10) for i in range(8)]
        V = top + bottom
        self.add_multi(V, top_faces + bottom_faces + fascia,
                       [mat_top] * 8 + [mat_under] * 8 + [mat_edge] * 8)
        if ridge_beam:
            self.box((cx, cy, z0 + rise + 0.02), (ridge_half * 2 + 0.16, 0.16, 0.12),
                     ridge_mat)

    def pyramid_roof(self, cx, cy, eave_z, ex, ey, rise, thickness,
                     corner_lift=0.0, mid_lift=0.0, mat_top="Roof",
                     mat_under="RoofEdge", mat_edge="RoofEdge"):
        z0 = eave_z
        ring = [
            (cx - ex, cy - ey, z0 + corner_lift), (cx, cy - ey, z0 + mid_lift),
            (cx + ex, cy - ey, z0 + corner_lift), (cx + ex, cy, z0 + mid_lift),
            (cx + ex, cy + ey, z0 + corner_lift), (cx, cy + ey, z0 + mid_lift),
            (cx - ex, cy + ey, z0 + corner_lift), (cx - ex, cy, z0 + mid_lift),
        ]
        apex = (cx, cy, z0 + rise)
        top = ring + [apex]
        bottom = [(x, y, z - thickness) for (x, y, z) in top]
        top_faces = [(i, (i + 1) % 8, 8) for i in range(8)]
        bottom_faces = [tuple(i + 9 for i in reversed(f)) for f in top_faces]
        fascia = [(i, (i + 1) % 8, (i + 1) % 8 + 9, i + 9) for i in range(8)]
        V = top + bottom
        self.add_multi(V, top_faces + bottom_faces + fascia,
                       [mat_top] * 8 + [mat_under] * 8 + [mat_edge] * 8)

    def gable_roof(self, cx, cy, eave_z, ex, ey, rise, thickness,
                   mat_top="Roof", mat_under="RoofEdge", mat_edge="RoofEdge",
                   corner_lift=0.0):
        z0 = eave_z + corner_lift
        A = (cx - ex, cy - ey, z0)
        C = (cx + ex, cy - ey, z0)
        E = (cx + ex, cy + ey, z0)
        G = (cx - ex, cy + ey, z0)
        R1 = (cx - ex, cy, z0 + rise)
        R2 = (cx + ex, cy, z0 + rise)
        top = [A, C, E, G, R1, R2]
        bottom = [(x, y, z - thickness) for (x, y, z) in top]
        top_faces = [(0, 1, 5, 4), (3, 2, 5, 4)]
        bottom_faces = [tuple(i + 6 for i in reversed(f)) for f in top_faces]
        edges = [(0, 1, 7, 6), (1, 2, 8, 7), (2, 3, 9, 8), (3, 0, 6, 9),
                 (2, 5, 11, 8), (5, 1, 7, 11),
                 (0, 4, 10, 6), (4, 3, 9, 10)]
        V = top + bottom
        self.add_multi(V, top_faces + bottom_faces + edges,
                       [mat_top] * 2 + [mat_under] * 2 + [mat_edge] * 8)
        # bargeboards along the four sloped roof edges
        for a, b in ((C, R2), (E, R2), (A, R1), (G, R1)):
            pa, pb = Vector(a), Vector(b)
            mid = (pa + pb) * 0.5 + Vector((0.0, 0.0, 0.035))
            self.tube(mid - (pb - pa) * 0.5, mid + (pb - pa) * 0.5, 0.055, 0.055,
                      mat_edge, sides=4, phase=math.pi / 4)

    # -- decoration --------------------------------------------------------
    def moss(self, c, r, mat="Moss", flat=0.38, subdiv=0, jitter=0.22, scale=(1.0, 1.0)):
        self.ico(c, r, mat, scale=(scale[0], scale[1], flat), subdiv=subdiv,
                 jitter=jitter)

    def snow_blob(self, c, r, flat=0.4):
        self.ico(c, r, "Snow", scale=(1.15, 1.0, flat), subdiv=0, jitter=0.2)

    def ice_sickle(self, base, length=0.16, r=0.025, mat="Ice"):
        base = Vector(base)
        tip = base + Vector((0.0, 0.0, -length))
        self.spike(base, tip, r, mat, sides=5)

    def vine(self, points, r=0.018, mat="Vine", leaves=0, leaf_mat="MossLight"):
        pts = [Vector(p) for p in points]
        for i in range(len(pts) - 1):
            self.tube(pts[i], pts[i + 1], r, r * 0.85, mat, sides=4)
            if leaves and i % 2 == 1:
                self.ico(pts[i] + Vector((0.02, 0.01, 0.0)), r * 2.6, leaf_mat,
                         scale=(1.0, 0.55, 0.35), subdiv=0, jitter=0.25)
        if leaves:
            self.ico(pts[-1], r * 2.8, leaf_mat, scale=(1.0, 0.6, 0.4),
                     subdiv=0, jitter=0.25)

    def rope_wrap(self, c, major_r, minor_r, mat="Rope", major=8, minor=4):
        """torus lying in the XY plane at c (for lashing around a vertical post)."""
        c = Vector(c)
        L = []
        for i in range(major):
            a = 2.0 * math.pi * i / major
            ca, sa = math.cos(a), math.sin(a)
            for j in range(minor):
                b = 2.0 * math.pi * j / minor
                rr = major_r + minor_r * math.cos(b)
                L.append((c.x + rr * ca, c.y + rr * sa, c.z + minor_r * math.sin(b)))
        F = []
        for i in range(major):
            i2 = (i + 1) % major
            for j in range(minor):
                j2 = (j + 1) % minor
                F.append((i * minor + j, i2 * minor + j, i2 * minor + j2, i * minor + j2))
        self.add(L, F, mat)

    # -- object ------------------------------------------------------------
    def to_object(self, name):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.verts, [], self.faces)
        me.update()
        for mat_name in self.mat_names:
            me.materials.append(make_material(mat_name))
        for i, poly in enumerate(me.polygons):
            if i < len(self.fmats):
                poly.material_index = self.fmats[i]
        me.validate(verbose=False)
        obj = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(obj)

        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=list(bm.edges))
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(me)
        bm.free()
        me.update()
        for poly in me.polygons:
            poly.use_smooth = False
        obj.location = (0.0, 0.0, 0.0)
        obj.rotation_euler = (0.0, 0.0, 0.0)
        obj.scale = (1.0, 1.0, 1.0)
        me.name = name
        return obj


# ----------------------------------------------------------------------------
# scene / export / render pipeline
# ----------------------------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    return sc


def object_bounds(obj):
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def tri_count(obj):
    return sum(max(0, len(p.vertices) - 2) for p in obj.data.polygons)


def export_glb(obj, name):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    out = os.path.join(MODEL_DIR, name + ".glb")
    bpy.ops.export_scene.gltf(
        filepath=out,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
        export_extras=False,
    )
    return out


GROUND_MAT = None


def beige_ground_material():
    mat = bpy.data.materials.new(name="PreviewGround")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    col = hex_linear("#C9C1B2")
    bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.95
    return mat


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def add_area(sc, name, center, direction, energy, color, size):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.color = color
    data.size = size
    data.shape = "SQUARE"
    obj = bpy.data.objects.new(name, data)
    sc.collection.objects.link(obj)
    obj.location = Vector(center) + Vector(direction)
    look_at(obj, center)
    return obj


def setup_stage(sc, name, bounds, az_deg, el_deg, margin, ground_z, is_bridge):
    mn, mx = bounds
    center = (mn + mx) * 0.5
    radius = max(0.35, (mx - mn).length * 0.5)

    # world
    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    sc.world = world
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (*hex_linear("#CFC5B4"), 1.0)
    bg.inputs["Strength"].default_value = 0.62

    # ground
    if ground_z is not None:
        bpy.ops.mesh.primitive_plane_add(size=400.0, location=(0.0, 0.0, ground_z))
        ground = bpy.context.active_object
        ground.name = "PreviewGround"
        ground.data.materials.append(beige_ground_material())

    # lights (warm key, cool fill, warm rim)
    r = radius
    key_e = 680.0 * (r / 3.0) ** 2
    fill_e = 215.0 * (r / 3.0) ** 2
    rim_e = 420.0 * (r / 3.0) ** 2
    add_area(sc, "Key", center, Vector((-1.05, -1.35, 2.0)).normalized() * (r * 3.1),
             key_e, hex_linear("#FFE3C4"), r * 1.4)
    add_area(sc, "Fill", center, Vector((2.1, -0.7, 0.9)).normalized() * (r * 3.4),
             fill_e, hex_linear("#C4DCE4"), r * 1.7)
    add_area(sc, "Rim", center, Vector((0.5, 2.1, 1.5)).normalized() * (r * 3.3),
             rim_e, hex_linear("#FFF0D8"), r * 1.2)

    # camera
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 50.0
    cam_data.sensor_width = 36.0
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    sc.collection.objects.link(cam)
    az = math.radians(az_deg)
    el = math.radians(el_deg)
    direction = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el),
                        math.sin(el)))
    fov = 2.0 * math.atan(cam_data.sensor_width / (2.0 * cam_data.lens))
    dist = radius / math.sin(fov / 2.0) * margin
    cam.location = center + direction * dist
    cam.data.clip_end = dist * 6.0 + 50.0
    look_at(cam, center)
    sc.camera = cam

    # render settings
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = RENDER_SAMPLES
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    sc.cycles.max_bounces = 5
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 2
    sc.render.resolution_x = 512
    sc.render.resolution_y = 512
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.fps = 24
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    sc.view_settings.exposure = 0.32
    return center, radius


def render_preview(sc, name):
    sc.render.filepath = os.path.join(PREVIEW_DIR, name + ".png")
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print("  render %.1fs -> %s" % (time.time() - t0, sc.render.filepath))


# ----------------------------------------------------------------------------
# assets
# ----------------------------------------------------------------------------

def build_torii_gate(b):
    """5.5 m tall, 5 m wide faded vermilion torii, blank plaque, moss, slight lean."""
    rng = b.rng
    # stone footings
    for sx in (-1, 1):
        b.ico((sx * 1.96, 0.02, 0.13), 0.38, "Stone",
              scale=(1.15, 1.0, 0.28), subdiv=0, jitter=0.16)
        b.box((sx * 1.96, 0.02, 0.09), (0.78, 0.66, 0.18), "StoneDark",
              rot=(0, 0, rng.uniform(-8, 8)), taper=0.88)
        b.box((sx * 1.96, 0.02, 0.20), (0.66, 0.56, 0.10), "StoneLight",
              rot=(0, 0, rng.uniform(-6, 6)), taper=0.94)

    # pillars (slightly asymmetric lean)
    b.tube((-1.96, 0.02, 0.10), (-1.79, 0.05, 4.64), 0.245, 0.19,
           "Vermilion", sides=8, phase=math.pi / 8)
    b.tube((1.96, 0.02, 0.10), (1.83, -0.01, 4.64), 0.245, 0.19,
           "Vermilion", sides=8, phase=math.pi / 8)

    # lower tie beam (nuki), passes through pillars
    b.box((0, 0.0, 3.36), (4.62, 0.28, 0.26), "VermilionDark", rot=(0, 0, 0.5))
    for sx in (-1, 1):
        b.box((sx * 2.34, 0.0, 3.36), (0.18, 0.34, 0.34), "WoodDark",
              rot=(0, sx * 4.0, 0))

    # central strut + blank plaque
    b.box((0, 0.01, 4.02), (0.30, 0.24, 0.96), "VermilionDark", taper=0.84)
    b.box((0, -0.02, 4.26), (0.98, 0.14, 0.66), "WoodDark", rot=(0, 0, 0.8))
    b.box((0, -0.10, 4.26), (0.82, 0.05, 0.50), "AgedPaper", rot=(0, 0, 0.8))
    # wooden pegs on the plaque frame
    for sx in (-1, 1):
        b.cylinder((sx * 0.38, -0.135, 4.50), 0.035, 0.03, "WoodDark",
                   sides=6, rot=(90, 0, 0))

    # second (upper) straight beam
    b.box((0, 0.0, 4.80), (4.42, 0.34, 0.24), "VermilionPale", rot=(0, 0, -0.4))
    # short struts from pillars to shimaki
    for sx in (-1, 1):
        b.box((sx * 1.80, 0.0, 4.55), (0.20, 0.30, 0.28), "VermilionDark",
              rot=(0, sx * 3.0, 0))

    # top curved lintel (kasagi)
    pts = []
    for i in range(11):
        x = -2.44 + 4.88 * i / 10.0
        z = 5.13 + 0.19 * (abs(x) / 2.44) ** 2.5
        pts.append((x, 0.0, z))
    b.swept_beam(pts, width=0.44, height=0.36, mat="Vermilion")
    # end grain caps
    for sx in (-1, 1):
        b.box((sx * 2.47, 0.0, 5.32), (0.06, 0.46, 0.36), "VermilionDark",
              rot=(0, 0, 0))

    # short spacers visually tie the floating top lintel to the second beam
    for x in (-1.45, 0.0, 1.45):
        b.box((x, 0.0, 5.01), (0.16, 0.27, 0.20), "VermilionDark")
    # moss / weathering patches
    b.moss((-1.96, -0.20, 0.30), 0.30, "Moss", flat=0.35)
    b.moss((-1.82, 0.22, 0.52), 0.18, "MossLight", flat=0.5, scale=(0.8, 1.5))
    b.moss((1.92, -0.22, 0.26), 0.26, "Moss", flat=0.3)
    b.moss((1.84, -0.02, 1.35), 0.14, "Moss", flat=0.45, scale=(0.7, 1.8))
    b.moss((-1.70, 0.02, 2.55), 0.16, "MossLight", flat=0.4, scale=(0.7, 1.6))
    b.moss((-1.55, 0.00, 5.32), 0.22, "Moss", flat=0.3)
    b.moss((-1.05, 0.12, 5.31), 0.16, "MossLight", flat=0.3)
    b.moss((1.92, 0.08, 4.94), 0.18, "Moss", flat=0.3)
    b.moss((0.65, 0.10, 4.93), 0.13, "MossLight", flat=0.28)
    b.moss((0.15, 0.02, 3.50), 0.18, "Moss", flat=0.25)
    b.moss((-0.95, -0.01, 3.50), 0.15, "MossLight", flat=0.3)
    b.moss((1.35, 0.06, 3.50), 0.14, "Moss", flat=0.3)
    b.moss((-1.68, -0.16, 3.51), 0.16, "Moss", flat=0.25)
    b.moss((1.68, -0.15, 3.51), 0.15, "MossLight", flat=0.25)
    b.moss((2.28, 0.0, 5.18), 0.11, "Moss", flat=0.3)
    b.moss((-1.20, 0.08, 5.345), 0.18, "MossLight", flat=0.25)
    b.moss((1.58, 0.04, 5.38), 0.16, "Moss", flat=0.25)
    b.moss((0.42, -0.05, 5.27), 0.11, "MossLight", flat=0.3)
    b.moss((-0.34, -0.13, 4.04), 0.12, "Moss", flat=0.25)

    # a slightly crooked whole silhouette
    b.rotate_z(1.4)


def build_stone_lantern(b):
    """2.4 m stone lantern: base / shaft / lit chamber / stone roof / jewel finial."""
    # base
    b.box((0, 0, 0.07), (0.90, 0.90, 0.14), "StoneLight", rot=(0, 0, 4), taper=0.92)
    b.box((0, 0, 0.20), (0.74, 0.74, 0.12), "Stone", rot=(0, 0, -2), taper=0.86)
    b.box((0, 0, 0.31), (0.56, 0.56, 0.12), "StoneDark", taper=0.9)
    b.cylinder((0, 0, 0.40), 0.24, 0.07, "StoneLight", sides=8)
    # shaft
    b.cylinder((0, 0, 0.80), 0.135, 0.72, "Stone", sides=8, rtop=0.115,
               phase=math.pi / 8)
    b.cylinder((0, 0, 0.50), 0.18, 0.08, "StoneDark", sides=8, rtop=0.15)
    b.cylinder((0, 0, 1.17), 0.22, 0.07, "StoneLight", sides=8, phase=math.pi / 8)
    # middle platform
    b.box((0, 0, 1.27), (0.58, 0.58, 0.12), "Stone", taper=1.06, rot=(0, 0, 3))
    # lit chamber
    glow_c = (0, 0, 1.54)
    b.box(glow_c, (0.40, 0.40, 0.36), "Glow", rot=(0, 0, 3))
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((sx * 0.235, sy * 0.235, 1.55), (0.10, 0.10, 0.46), "StoneDark",
                  rot=(0, 0, 3), taper=0.92)
    b.box((0, 0, 1.335), (0.62, 0.62, 0.09), "Stone", rot=(0, 0, 3), taper=0.9)
    b.box((0, 0, 1.765), (0.64, 0.64, 0.09), "StoneLight", rot=(0, 0, 3), taper=1.0)
    # little sills under each opening
    for ang in (0, 90, 180, 270):
        a = math.radians(ang)
        b.box((math.sin(a) * 0.29, -math.cos(a) * 0.29, 1.36), (0.34, 0.09, 0.05),
              "StoneLight", rot=(0, 0, -ang))
    # roof
    b.pyramid_roof(0, 0, 1.80, 0.46, 0.46, 0.24, 0.10,
                   corner_lift=0.10, mid_lift=0.0, mat_top="Stone",
                   mat_under="StoneDark", mat_edge="StoneDark")
    # finial
    b.cylinder((0, 0, 2.03), 0.15, 0.06, "StoneLight", sides=8, rtop=0.12)
    b.ico((0, 0, 2.12), 0.105, "Stone", scale=(1.0, 1.0, 0.95), subdiv=1)
    b.spike((0, 0, 2.20), (0, 0, 2.355), 0.075, "StoneLight", sides=6)
    b.ico((0, 0, 2.376), 0.028, "Stone", subdiv=0)
    # moss
    b.moss((-0.40, -0.38, 0.10), 0.17, "Moss", flat=0.22)
    b.moss((0.38, -0.34, 0.14), 0.12, "MossLight", flat=0.22)
    b.moss((0.16, 0.43, 0.30), 0.13, "Moss", flat=0.25)
    b.moss((0.02, -0.14, 0.74), 0.075, "MossLight", flat=0.4,
           scale=(0.7, 1.6))
    b.moss((0.28, -0.28, 1.39), 0.10, "Moss", flat=0.28)
    b.moss((0.18, -0.24, 1.875), 0.15, "Moss", flat=0.25)
    b.moss((-0.31, -0.12, 1.878), 0.10, "MossLight", flat=0.25)
    b.moss((0.24, 0.20, 1.885), 0.10, "MossLight", flat=0.28)
    b.moss((-0.20, 0.04, 1.995), 0.085, "Moss", flat=0.35)
    b.moss((0.0, -0.32, 0.24), 0.08, "Moss", flat=0.3)


def build_moss_shrine(b):
    """3.2 m small moss shrine: stone base, timber body, glowing shoji, upturned roof."""
    rng = b.rng
    # stone base / steps
    b.box((0, 0.02, 0.08), (2.16, 1.76, 0.16), "Stone", rot=(0, 0, 1.5), taper=0.97)
    b.box((0, 0.02, 0.23), (1.92, 1.52, 0.14), "StoneLight", rot=(0, 0, -1.0), taper=0.96)
    for i, (w, d, top, y) in enumerate(((1.14, 0.20, 0.12, -1.28),
                                       (1.28, 0.20, 0.22, -1.11),
                                       (1.44, 0.20, 0.32, -0.95))):
        b.box((0, y, top / 2), (w, d, top), "StoneLight" if i % 2 else "Stone",
              taper=0.96)
    # stone steps moss
    for sx in (-0.55, 0.55):
        b.moss((sx, -1.22, 0.14), 0.11, "Moss", flat=0.25)
    b.moss((-0.95, -0.78, 0.28), 0.13, "MossLight", flat=0.25)

    # veranda deck
    b.box((0, -0.38, 0.38), (1.92, 1.36, 0.10), "WoodDark")
    for i in range(5):
        x = -0.76 + i * 0.38
        b.box((x, -0.45, 0.44), (0.02, 1.16, 0.012), "RoofEdge")
    # body platform
    b.box((0, 0.05, 0.47), (1.62, 1.24, 0.10), "WoodDark")

    # walls
    b.box((0, 0.66, 1.14), (1.58, 0.10, 1.30), "WoodDark")
    for sx in (-1, 1):
        b.box((sx * 0.775, 0.05, 1.14), (0.08, 1.22, 1.30), "Wood")
    # front upper beam and side plaster strips
    b.box((0, -0.56, 1.82), (1.58, 0.10, 0.18), "WoodDark")
    for sx in (-1, 1):
        b.box((sx * 0.775, -0.56, 1.20), (0.08, 0.10, 1.34), "Wood")

    # shoji doors (emissive panes + wooden lattice)
    for sx in (-1, 1):
        cx = sx * 0.30
        b.box((cx, -0.605, 1.15), (0.50, 0.035, 0.95), "Glow")
        # frame
        b.box((cx, -0.64, 1.66), (0.56, 0.09, 0.08), "WoodDark")
        b.box((cx, -0.64, 0.64), (0.56, 0.09, 0.08), "WoodDark")
        b.box((cx - sx * 0.28, -0.64, 1.15), (0.06, 0.09, 1.06), "WoodDark")
        b.box((cx + sx * 0.28, -0.64, 1.15), (0.06, 0.09, 1.06), "WoodDark")
        # lattice
        for k in (-1, 1):
            b.box((cx + k * 0.17, -0.632, 1.15), (0.025, 0.02, 0.93), "Wood")
        for k in (-1, 0, 1):
            b.box((cx, -0.632, 1.15 + k * 0.30), (0.47, 0.02, 0.025), "Wood")
    # central door post
    b.box((0, -0.63, 1.15), (0.08, 0.10, 1.10), "WoodDark")
    # small transom above doors
    b.box((0, -0.60, 1.73), (1.20, 0.04, 0.12), "Glow")

    # corner posts
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((sx * 0.78, 0.05 + sy * 0.62, 1.22), (0.13, 0.13, 1.56),
                  "WoodDark", taper=0.9)
            b.box((sx * 0.78, 0.05 + sy * 0.62, 0.46), (0.20, 0.20, 0.12),
                  "WoodDark", taper=0.85)

    # side plank seams on the body
    for sx in (-1, 1):
        for k in range(4):
            b.box((sx * 0.815, -0.38 + k * 0.28, 1.14), (0.012, 0.035, 1.24),
                  "WoodDark")
    # small railing posts at the veranda corners (kept minimal)
    for sx in (-1, 1):
        b.box((sx * 0.94, -0.78, 0.58), (0.07, 0.07, 0.37), "Wood", taper=0.9)
        b.box((sx * 0.94, -0.78, 0.78), (0.10, 0.10, 0.05), "WoodDark")

    # roof (hip, gently upturned corners)
    b.hip_roof(0, 0.03, 1.94, 1.30, 1.12, 0.72, 0.48, 0.12,
               corner_lift=0.22, mid_lift=-0.015,
               mat_top="Roof", mat_under="RoofEdge", mat_edge="RoofEdge",
               ridge_mat="RoofEdge", ridge_beam=True)
    # exposed rafter ends under the eaves
    for sx in (-1, 1):
        for i in range(4):
            y = -0.72 + i * 0.48
            b.box((sx * 1.12, y, 1.855), (0.34, 0.07, 0.07), "WoodDark",
                  rot=(0, 0, 0))
    # katsuogi (logs across the ridge)
    for x in (-0.28, 0.0, 0.28):
        b.cylinder((x, 0.03, 2.72), 0.055, 0.40, "WoodDark", sides=6,
                   rot=(90, 0, 0))
        b.moss((x, 0.03, 2.775), 0.08, "Moss", flat=0.4)
    # chigi (crossed finials at both ridge ends, full X above the ridge)
    for sx in (-1, 1):
        for sgn in (-1, 1):
            b.box((sx * 0.60, 0.03 + sgn * 0.075, 2.982), (0.12, 0.07, 0.44),
                  "WoodDark", rot=(sgn * 30, 0, 0), taper=0.7)
        b.cylinder((sx * 0.60, 0.03, 2.66), 0.075, 0.16, "RoofEdge", sides=6,
                   rot=(90, 0, 0))

    # offering box (beside the steps, clear of the veranda)
    b.box((0.98, -1.34, 0.15), (0.50, 0.32, 0.30), "Wood", rot=(0, 0, -4), taper=0.92)
    for i in range(3):
        b.box((0.98, -1.34 + (i - 1) * 0.095, 0.31), (0.52, 0.032, 0.032), "WoodDark")
    for sx in (-1, 1):
        b.box((0.98 + sx * 0.19, -1.34, 0.04), (0.06, 0.28, 0.08), "WoodDark")

    # moss everywhere
    b.moss((-0.95, 0.70, 2.55), 0.17, "Moss", flat=0.35)
    b.moss((-0.62, 0.05, 2.72), 0.15, "MossLight", flat=0.35)
    b.moss((0.10, 0.02, 2.75), 0.18, "Moss", flat=0.3)
    b.moss((0.46, 0.03, 2.69), 0.12, "MossLight", flat=0.35)
    b.moss((0.98, -0.55, 2.23), 0.16, "Moss", flat=0.3)
    b.moss((-1.14, 0.40, 2.19), 0.13, "MossLight", flat=0.3)
    b.moss((-0.55, -0.95, 2.14), 0.12, "Moss", flat=0.3)
    b.moss((1.16, 0.60, 2.11), 0.10, "Moss", flat=0.3)
    b.moss((-1.05, -0.52, 0.34), 0.16, "Moss", flat=0.2)
    b.moss((1.02, 0.65, 0.34), 0.12, "MossLight", flat=0.2)
    b.moss((-0.86, 0.60, 0.52), 0.10, "Moss", flat=0.25)
    b.moss((0.22, -0.88, 0.50), 0.09, "MossLight", flat=0.3)
    # hanging moss under the front eave
    b.moss((-0.95, -1.02, 1.84), 0.10, "Moss", flat=0.7, scale=(0.6, 1.2))
    b.moss((0.86, -1.04, 1.86), 0.09, "MossLight", flat=0.6, scale=(0.6, 1.2))


def build_wooden_cabin(b):
    """6 x 4.5 x 4 m log cabin, snow roof, warm windows, porch, stone chimney, faces -Y."""
    rng = b.rng
    # stone foundation
    b.box((0, 0.63, 0.16), (5.4, 3.24, 0.32), "StoneDark", taper=0.98)
    for i in range(5):
        x = -2.2 + i * 1.1
        b.box((x, -1.02, 0.13), (0.62, 0.16, 0.24), "Stone",
              rot=(0, 0, rng.uniform(-5, 5)), taper=0.94)
    # porch deck
    b.box((0, -1.47, 0.35), (5.16, 1.34, 0.16), "Timber")
    for i in range(5):
        x = -2.0 + i * 1.0
        b.box((x, -1.47, 0.435), (0.015, 1.26, 0.008), "RoofEdge")
    # porch steps
    b.box((0, -2.125, 0.09), (1.55, 0.25, 0.18), "Stone", taper=0.96)
    b.box((0, -1.99, 0.19), (1.35, 0.22, 0.20), "StoneLight", taper=0.96)
    b.box((0, -2.08, 0.20), (1.42, 0.08, 0.04), "Snow", taper=0.9)

    # log walls
    ys_front, ys_back = -0.85, 2.08
    xs_side = 2.55
    log_r = 0.115
    for course in range(8):
        z = 0.44 + course * 0.225
        ext = 0.18 + rng.uniform(-0.02, 0.03)
        b.tube((-xs_side - ext, ys_front, z), (xs_side + ext, ys_front, z),
               log_r, log_r, "Wood" if course % 2 else "WoodLight", sides=6)
        b.tube((-xs_side - ext, ys_back, z), (xs_side + ext, ys_back, z),
               log_r, log_r, "WoodLight" if course % 2 else "Wood", sides=6)
        b.tube((-xs_side, ys_front - ext, z), (-xs_side, ys_back + 0.02, z),
               log_r, log_r, "Wood" if course % 2 else "WoodLight", sides=6)
        b.tube((xs_side, ys_front - ext, z), (xs_side, ys_back + 0.02, z),
               log_r, log_r, "WoodLight" if course % 2 else "Wood", sides=6)

    # door (right of centre)
    door_x = 0.72
    b.box((door_x, -0.955, 1.20), (0.94, 0.10, 1.58), "WoodDark", taper=0.99)
    b.box((door_x, -1.015, 1.20), (0.78, 0.055, 1.44), "Wood", taper=0.99)
    for i in (-1, 0, 1):
        b.box((door_x + i * 0.25, -1.045, 1.20), (0.02, 0.02, 1.38), "WoodDark")
    # little glowing window in the door
    b.box((door_x, -1.05, 1.68), (0.30, 0.03, 0.24), "Glow")
    b.box((door_x, -1.06, 1.68), (0.10, 0.025, 0.26), "WoodDark")
    b.box((door_x, -1.06, 1.68), (0.32, 0.025, 0.03), "WoodDark")
    b.box((door_x + 0.30, -1.06, 1.13), (0.05, 0.06, 0.10), "Metal")

    # windows: (x, width, height, z)
    for wx, ww, wh, wz in ((-1.55, 1.08, 0.80, 1.47), (1.98, 0.62, 0.72, 1.50)):
        b.box((wx, -1.005, wz), (ww, 0.11, wh), "WoodDark")
        b.box((wx, -1.065, wz), (ww - 0.14, 0.03, wh - 0.14), "Glow")
        b.box((wx, -1.085, wz), (0.035, 0.035, wh - 0.10), "WoodDark")
        b.box((wx, -1.085, wz), (ww - 0.10, 0.035, 0.035), "WoodDark")
        b.box((wx, -1.075, wz - wh / 2), (ww + 0.10, 0.18, 0.06), "WoodLight")
        b.box((wx, -1.08, wz - wh / 2 + 0.10), (ww + 0.06, 0.18, 0.05), "Snow",
              taper=0.9)
    # side window on +X (frame sits proud of the log wall)
    b.box((2.685, 0.75, 1.50), (0.10, 0.78, 0.74), "WoodDark")
    b.box((2.74, 0.75, 1.50), (0.03, 0.64, 0.62), "Glow")
    b.box((2.76, 0.75, 1.50), (0.035, 0.035, 0.64), "WoodDark")
    b.box((2.76, 0.75, 1.50), (0.035, 0.63, 0.035), "WoodDark")
    b.box((2.71, 0.75, 1.12), (0.16, 0.86, 0.06), "WoodLight")
    b.box((2.71, 0.75, 1.22), (0.15, 0.80, 0.05), "Snow")

    # gable walls (proper triangular prisms, x = +/- 2.55 .. 2.65)
    for sx in (-1, 1):
        x0, x1 = sx * 2.55, sx * 2.65
        y0, y1, yp, zb, zp = -0.85, 2.08, 0.52, 2.13, 2.96
        V = [(x0, y0, zb), (x0, y1, zb), (x0, yp, zp),
             (x1, y0, zb), (x1, y1, zb), (x1, yp, zp)]
        F = [(3, 4, 5), (0, 2, 1), (0, 1, 4, 3), (0, 3, 5, 2), (1, 2, 5, 4)]
        b.add(V, F, "Wood")
        # plastered gable panel inside the timber triangle
        xa, xb = sx * 2.655, sx * 2.675
        py0, py1, pyP = -0.62, 1.95, 0.52
        pzb, pzp = 2.22, 2.80
        Vp = [(xa, py0, pzb), (xa, py1, pzb), (xa, pyP, pzp),
              (xb, py0, pzb), (xb, py1, pzb), (xb, pyP, pzp)]
        Fp = [(3, 4, 5), (0, 2, 1), (0, 1, 4, 3), (0, 3, 5, 2), (1, 2, 5, 4)]
        b.add(Vp, Fp, "Plaster")
        # dark timber frame over the plaster
        b.box((sx * 2.69, yp, 2.25), (0.07, 2.55, 0.12), "WoodDark")
        b.box((sx * 2.69, yp, 2.55), (0.07, 0.07, 0.62), "WoodDark")
        # small round attic window
        b.cylinder((sx * 2.70, -0.10, 2.45), 0.19, 0.05, "WoodDark",
                   sides=8, rot=(0, 90, 0))
        b.cylinder((sx * 2.735, -0.10, 2.45), 0.14, 0.03, "Glow",
                   sides=8, rot=(0, 90, 0))
        b.box((sx * 2.755, -0.10, 2.45), (0.02, 0.025, 0.30), "WoodDark")
        b.box((sx * 2.755, -0.10, 2.45), (0.02, 0.30, 0.025), "WoodDark")

    # roof + snow roof
    b.gable_roof(0, 0.52, 2.06, 2.961, 1.70, 1.02, 0.14,
                 mat_top="Roof", mat_under="RoofEdge", mat_edge="RoofEdge",
                 corner_lift=0.04)
    b.gable_roof(0, 0.52, 2.09, 2.941, 1.70, 1.05, 0.12,
                 mat_top="Snow", mat_under="Snow", mat_edge="Snow",
                 corner_lift=0.05)
    # snow ridge lumps
    for i in range(7):
        x = -2.4 + i * 0.8
        b.snow_blob((x, 0.52, 3.20), 0.17, flat=0.42)
    # snow on the eaves / icicles
    for i in range(7):
        x = -2.55 + i * 0.85
        b.snow_blob((x, -1.11, 2.11), 0.11, flat=0.35)
        b.snow_blob((x + 0.3, 2.10, 2.11), 0.08, flat=0.35)
    for i in range(5):
        x = -2.45 + i * 1.22
        b.ice_sickle((x, -1.12, 2.04), 0.20 + (i % 3) * 0.05, 0.021)

    # porch roof (lean-to, high at the wall, low at the front)
    porch_ang = 12.5
    b.box((0, -1.50, 2.02), (5.30, 1.46, 0.10), "Roof", rot=(porch_ang, 0, 0))
    b.box((0, -1.50, 2.09), (5.34, 1.50, 0.11), "Snow", rot=(porch_ang, 0, 0))
    for i in range(5):
        x = -2.45 + i * 1.22
        b.snow_blob((x, -2.12, 1.83), 0.11, flat=0.4)
    # porch posts
    for sx in (-1, 1):
        b.box((sx * 2.45, -1.98, 1.17), (0.13, 0.13, 1.52), "WoodDark", taper=0.92)
        b.box((sx * 2.45, -1.98, 1.96), (0.17, 0.17, 0.10), "Wood")
        b.moss((sx * 2.43, -2.02, 0.47), 0.10, "Moss", flat=0.25)
        b.box((sx * 2.38, -0.95, 1.88), (0.10, 0.10, 0.36), "WoodDark",
              rot=(0, sx * 42, 0))
        # railing
        b.box((sx * 2.40, -1.45, 0.95), (0.07, 0.95, 0.06), "Wood")
        b.box((sx * 2.40, -1.94, 0.62), (0.06, 0.06, 0.55), "Wood")
        b.box((sx * 2.40, -1.45, 0.64), (0.05, 0.92, 0.05), "Wood")
        for k in range(3):
            b.box((sx * 2.40, -1.68 + k * 0.26, 0.80), (0.05, 0.05, 0.34), "Wood")
        b.box((sx * 2.40, -1.45, 0.985), (0.09, 0.94, 0.035), "Snow")

    # porch lantern
    b.box((1.58, -1.92, 1.70), (0.03, 0.03, 0.30), "Metal")
    b.box((1.58, -1.92, 1.50), (0.20, 0.20, 0.26), "WoodDark", taper=0.9)
    b.box((1.58, -1.92, 1.50), (0.15, 0.15, 0.19), "Glow", taper=0.9)
    b.box((1.58, -1.92, 1.355), (0.21, 0.21, 0.04), "WoodDark")
    b.box((1.58, -1.92, 1.635), (0.23, 0.23, 0.04), "WoodDark", taper=0.8)

    # wall lantern beside the door (clearly visible from -Y)
    b.box((1.35, -1.03, 1.72), (0.16, 0.09, 0.24), "WoodDark", taper=0.9)
    b.box((1.35, -1.085, 1.72), (0.10, 0.02, 0.17), "Glow")
    b.box((1.35, -1.10, 1.60), (0.18, 0.05, 0.035), "Metal")
    b.box((1.35, -1.10, 1.84), (0.18, 0.05, 0.035), "Metal")
    b.box((1.35, -1.10, 1.70), (0.02, 0.06, 0.14), "Metal")

    # bench on the porch
    b.box((-1.95, -1.52, 0.56), (1.10, 0.32, 0.07), "Wood")
    b.box((-1.95, -1.68, 0.78), (1.10, 0.06, 0.28), "Wood")
    for sx in (-1, 1):
        b.box((-1.95 + sx * 0.44, -1.52, 0.49), (0.08, 0.28, 0.14), "WoodDark")
        b.box((-1.95 + sx * 0.44, -1.68, 0.64), (0.06, 0.06, 0.30), "WoodDark")
    b.box((-1.95, -1.52, 0.605), (1.12, 0.34, 0.03), "Snow")

    # stone chimney (emerges through the snow roof; reaches z=4.0)
    ch_x, ch_y = -1.88, 1.32
    for i in range(7):
        z = 0.28 + i * 0.55
        w = 0.60 - i * 0.010
        b.box((ch_x + rng.uniform(-0.02, 0.02), ch_y, z),
              (w, w, 0.55), ["Stone", "StoneLight", "StoneDark"][i % 3],
              rot=(0, 0, rng.uniform(-4, 4)), taper=0.97)
    b.box((ch_x, ch_y, 2.75), (0.70, 0.70, 0.12), "StoneDark", taper=0.92)
    b.box((ch_x, ch_y, 3.30), (0.66, 0.66, 0.09), "StoneDark", taper=0.92)
    b.box((ch_x, ch_y, 3.90), (0.68, 0.68, 0.10), "StoneDark", taper=0.9)
    # visible stone blocks on the front face of the chimney
    for z, xo, mat, w in ((2.95, 0.0, "StoneLight", 0.20),
                          (3.18, -0.14, "StoneDark", 0.16),
                          (3.45, 0.10, "StoneLight", 0.17),
                          (3.68, -0.06, "Stone", 0.15)):
        b.box((ch_x + xo, ch_y - 0.31, z), (w, 0.06, 0.13), mat, rot=(0, 0, 4))
    # dark rain rim under the snow cap
    b.box((ch_x, ch_y, 3.955), (0.52, 0.52, 0.02), "Metal", taper=0.9)
    for i in range(4):
        a = math.radians(i * 90 + 20)
        b.box((ch_x + math.cos(a) * 0.28, ch_y + math.sin(a) * 0.28, 3.35 + i * 0.12),
              (0.12, 0.10, 0.16), "StoneLight" if i % 2 else "Stone",
              rot=(0, 0, math.degrees(a)))
    b.snow_blob((ch_x, ch_y, 3.96), 0.15, flat=0.28)
    b.snow_blob((ch_x - 0.12, ch_y + 0.08, 3.90), 0.10, flat=0.3)

    # icicles under the porch eave
    for i in range(4):
        x = -2.1 + i * 1.4
        b.ice_sickle((x, -2.22, 1.80), 0.16 + (i % 2) * 0.04, 0.018)

    # snow drifts around the foundation
    for x, y, r in ((-2.5, -0.55, 0.26), (2.45, -0.4, 0.23), (-0.1, 2.02, 0.20),
                    (2.2, 1.98, 0.18), (-2.6, -1.95, 0.16), (2.5, -2.10, 0.14)):
        b.snow_blob((x, y, 0.10), r, flat=0.35)
    # a little moss peeking out by the porch
    b.moss((-2.25, -1.15, 0.42), 0.11, "Moss", flat=0.2)


def build_market_tent(b):
    """5 x 4 x 3.2 m ochre/cream striped market tent, wood poles, rug, crates, warm lanterns."""
    # ---- rug ----
    b.box((0.05, 0.25, 0.012), (4.30, 2.90, 0.024), "OchreDark", rot=(0, 0, 3), taper=0.99)
    b.box((0.05, 0.25 - 1.38, 0.027), (4.30, 0.13, 0.014), "Cream", rot=(0, 0, 3))
    b.box((0.05, 0.25 + 1.38, 0.027), (4.30, 0.13, 0.014), "Cream", rot=(0, 0, 3))
    b.box((0.05 - 2.08, 0.25, 0.027), (0.13, 2.90, 0.014), "Cream", rot=(0, 0, 3))
    b.box((0.05 + 2.08, 0.25, 0.027), (0.13, 2.90, 0.014), "Cream", rot=(0, 0, 3))
    b.box((0.05, 0.25 - 1.18, 0.030), (3.72, 0.055, 0.010), "Teal", rot=(0, 0, 3))
    b.box((0.05, 0.25 + 1.18, 0.030), (3.72, 0.055, 0.010), "Teal", rot=(0, 0, 3))
    b.box((0.05 - 1.82, 0.25, 0.030), (0.055, 2.28, 0.010), "Teal", rot=(0, 0, 3))
    b.box((0.05 + 1.82, 0.25, 0.030), (0.055, 2.28, 0.010), "Teal", rot=(0, 0, 3))
    b.box((0.05, 0.25, 0.032), (0.92, 0.92, 0.010), "Teal", rot=(0, 0, 48))
    b.box((0.05, 0.25, 0.038), (0.58, 0.58, 0.010), "Cream", rot=(0, 0, 48))
    b.box((0.05, 0.25, 0.043), (0.22, 0.22, 0.010), "Ochre", rot=(0, 0, 48))
    for sx, sy, cmat in ((-1.35, 0.95, "Teal"), (1.35, -0.45, "Ochre"),
                         (-1.30, -0.85, "Teal")):
        b.box((0.05 + sx, 0.25 + sy, 0.034), (0.28, 0.28, 0.008), cmat,
              rot=(0, 0, 48))

    # ---- poles ----
    for px, py in ((-2.2, -1.7), (2.2, -1.7), (-2.2, 1.7), (2.2, 1.7)):
        top = (px * 0.985, py * 0.985, 2.40)
        b.tube((px, py, 0.0), top, 0.085, 0.068, "Wood", sides=6)
        b.ico((px, py, 0.09), 0.15, "Stone", scale=(1.2, 1.2, 0.35), subdiv=0,
              jitter=0.18)
        b.rope_wrap((px * 0.985, py * 0.985, 2.26), 0.09, 0.019, major=6, minor=4)
        b.rope_wrap((px * 0.985, py * 0.985, 2.15), 0.09, 0.019, major=6, minor=4)
        sx, sy = math.copysign(2.42, px), math.copysign(1.84, py)
        mid = ((px + sx) * 0.5, (py + sy) * 0.5, 1.18)
        b.tube(top, mid, 0.018, 0.018, "Rope", sides=4)
        b.tube(mid, (sx, sy, 0.02), 0.018, 0.018, "Rope", sides=4)
        b.box((sx, sy, 0.08), (0.05, 0.05, 0.16), "WoodDark", rot=(0, 0, 20))

    # ---- canopy ----
    xs = [-2.5, -1.667, -0.833, 0.0, 0.833, 1.667, 2.5]
    z_corner, z_mid, ridge_z = 2.42, 2.36, 3.0
    def eave_z(x):
        return 2.36 + 0.06 * (abs(x) / 2.5) ** 2.2
    front = [(x, -2.0, eave_z(x)) for x in xs]
    back = [(x, 2.0, eave_z(x)) for x in xs]
    ridge = [(x * 0.54, 0.0, ridge_z) for x in xs]
    mats = ["Ochre", "Cream"]
    thick = 0.065
    for i in range(len(xs) - 1):
        m = mats[i % 2]
        b.add([front[i], front[i + 1], ridge[i + 1], ridge[i]],
              [(0, 1, 2, 3)], m)
        b.add([back[i], back[i + 1], ridge[i + 1], ridge[i]],
              [(0, 1, 2, 3)], m)
        f = [(p[0], p[1], p[2] - thick) for p in front]
        r = [(p[0], p[1], p[2] - thick) for p in ridge]
        bk = [(p[0], p[1], p[2] - thick) for p in back]
        b.add([f[i], f[i + 1], r[i + 1], r[i]], [(0, 1, 2, 3)], "CanvasDark")
        b.add([bk[i], bk[i + 1], r[i + 1], r[i]], [(0, 1, 2, 3)], "CanvasDark")
    # side hips
    for sx in (-1, 1):
        lf = (sx * 2.5, -2.0, z_corner)
        lm = (sx * 2.5, 0.0, z_mid)
        lb = (sx * 2.5, 2.0, z_corner)
        lr = (sx * 1.35, 0.0, ridge_z)
        for a, bb in ((lf, lm), (lm, lb)):
            b.add([a, bb, lr], [(0, 1, 2)], "Ochre")
            b.add([(a[0], a[1], a[2] - thick), (bb[0], bb[1], bb[2] - thick),
                   (lr[0], lr[1], lr[2] - thick)], [(0, 1, 2)], "CanvasDark")
    # eave fascia
    for arr in (front, back):
        for i in range(len(xs) - 1):
            b.add([arr[i], arr[i + 1],
                   (arr[i + 1][0], arr[i + 1][1], arr[i + 1][2] - thick),
                   (arr[i][0], arr[i][1], arr[i][2] - thick)],
                  [(0, 1, 2, 3)], "OchreDark")
    for sx in (-1, 1):
        for y0, y1, za0, za1 in ((-2.0, 0.0, z_corner, z_mid),
                                 (0.0, 2.0, z_mid, z_corner)):
            b.add([(sx * 2.5, y0, za0), (sx * 2.5, y1, za1),
                   (sx * 2.5, y1, za1 - thick), (sx * 2.5, y0, za0 - thick)],
                  [(0, 1, 2, 3)], "OchreDark")
    # valances
    for i in range(6):
        x = -1.75 + i * 0.70
        m = "Cream" if i % 2 == 0 else "OchreDark"
        for y in (-1.985, 1.985):
            b.box((x, y, eave_z(x) - 0.095), (0.66, 0.028, 0.19), m, taper=0.85)
    for sx in (-1, 1):
        for j, y in enumerate((-1.15, 0.0, 1.15)):
            b.box((sx * 2.486, y, z_mid - 0.095), (0.028, 0.60, 0.19),
                  "Cream" if j % 2 == 0 else "OchreDark", taper=0.85)
    # ridge cap + finials
    b.box((0, 0, 3.025), (2.92, 0.14, 0.07), "Cream", taper=0.85)
    b.spike((0, 0, 3.05), (0, 0, 3.20), 0.055, "Gold", sides=6)
    for sx in (-1, 1):
        b.ico((sx * 1.45, 0, 3.03), 0.06, "Gold", subdiv=0)

    # ---- crates ----
    def crate(cx, cy, cz, s, ang):
        b.box((cx, cy, cz), (s, s, s), "Wood", rot=(0, 0, ang), taper=0.985)
        for k in (-0.29, 0.29):
            b.box((cx, cy, cz + k * s), (s * 1.03, s * 1.03, 0.045),
                  "WoodDark", rot=(0, 0, ang))
        wx = cx + (s / 2) * math.sin(math.radians(ang))
        wy = cy - (s / 2) * math.cos(math.radians(ang))
        b.box((wx, wy, cz), (s * 1.12, 0.018, 0.055), "TimberGrey",
              rot=(0, 42, ang))
        b.ico((cx, cy, cz + s / 2 + 0.01), 0.05, "Rope", subdiv=0)
    crate(1.55, 1.10, 0.34, 0.68, 12)
    crate(1.55, 1.10, 0.93, 0.50, -8)
    crate(-1.78, 1.20, 0.26, 0.52, 19)

    # ---- clay jars ----
    for px, py, sc in ((-1.95, -0.62, 1.0), (-1.52, -0.93, 0.78)):
        b.cylinder((px, py, 0.15 * sc), 0.15 * sc, 0.30 * sc, "Clay", sides=8,
                   rtop=0.18 * sc)
        b.cylinder((px, py, 0.34 * sc), 0.10 * sc, 0.08 * sc, "Clay", sides=8)
        b.cylinder((px, py, 0.385 * sc), 0.13 * sc, 0.035 * sc, "OchreDark",
                   sides=8, rtop=0.12 * sc)
        b.moss((px + 0.08, py - 0.10, 0.03), 0.08, "Moss", flat=0.25)

    # ---- rolled rug leaning on the front-left pole ----
    p1 = (-2.03, -1.32, 0.14)
    p2 = (-2.20, -1.02, 1.08)
    b.tube(p1, p2, 0.125, 0.125, "Cream", sides=8)
    for t, cmat in ((0.28, "Ochre"), (0.64, "OchreDark")):
        q1 = tuple(p1[k] + (p2[k] - p1[k]) * (t - 0.055) for k in range(3))
        q2 = tuple(p1[k] + (p2[k] - p1[k]) * (t + 0.055) for k in range(3))
        b.tube(q1, q2, 0.132, 0.132, cmat, sides=8)

    # ---- low market table with bowls ----
    b.box((0.72, 0.72, 0.26), (0.92, 0.54, 0.08), "Wood", rot=(0, 0, 6))
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((0.72 + sx * 0.36, 0.72 + sy * 0.19, 0.12), (0.07, 0.07, 0.24),
                  "WoodDark")
    for i, (bx, by, br) in enumerate(((0.52, 0.66, 0.075), (0.76, 0.78, 0.065),
                                      (0.96, 0.64, 0.055))):
        b.cylinder((bx, by, 0.335), br, 0.075, "Clay", sides=8, rtop=br * 1.2)
        b.cylinder((bx, by, 0.365), br * 0.8, 0.02, "OchreDark", sides=8)
    b.box((1.02, 0.52, 0.325), (0.24, 0.30, 0.025), "Teal", rot=(0, 0, 20))

    # ---- hanging lanterns under the front eave ----
    for sx in (-1, 1):
        x = sx * 1.05
        b.box((x, -1.70, 2.20), (0.022, 0.022, 0.32), "Rope")
        b.box((x, -1.70, 2.03), (0.25, 0.25, 0.045), "WoodDark", taper=0.85)
        b.box((x, -1.70, 1.91), (0.22, 0.22, 0.25), "Glow", taper=0.9)
        b.box((x, -1.70, 1.775), (0.19, 0.19, 0.045), "WoodDark", taper=0.9)


def build_rope_bridge(b):
    """10 m rope bridge along Z, width 2.4, deck top nominally z=0, origin deck centre."""
    rng = b.rng
    # deck planks (top height varies downwards, max 0 at the centre)
    n = 19
    for i in range(n):
        y = -4.75 + 9.5 * i / (n - 1)
        if i == n // 2:
            top = 0.0
        else:
            top = -0.008 - 0.036 * abs(math.sin(i * 1.9))
        th = 0.075 + 0.022 * abs(math.sin(i * 2.7))
        b.box((rng.uniform(-0.004, 0.004), y, top - th / 2),
              (2.39, 0.47, th), ["Timber", "TimberGrey", "Wood"][i % 3],
              rot=(0, 0, rng.uniform(-0.8, 0.8)), taper=0.99)
    # longitudinal support ropes and cross beams under the deck
    for sx in (-1, 1):
        b.tube((sx * 0.95, -4.965, -0.18), (sx * 0.95, 4.965, -0.18),
               0.035, 0.035, "Rope", sides=5)
    for i in range(7):
        y = -4.5 + i * 1.5
        b.box((0, y, -0.20), (2.30, 0.13, 0.13), "WoodDark", rot=(0, 0, rng.uniform(-1, 1)))
        for sx in (-1, 1):
            b.rope_wrap((sx * 0.95, y, -0.20), 0.055, 0.018, major=5, minor=3)
    # end posts
    for sy in (-1, 1):
        for sx in (-1, 1):
            py = sy * 4.83
            b.box((sx * 1.08, py, 0.57), (0.15, 0.15, 1.14), "WoodDark",
                  taper=0.9, rot=(0, 0, rng.uniform(-2, 2)))
            b.ico((sx * 1.08, py, 0.07), 0.10, "Stone", scale=(1.0, 1.0, 0.4),
                  subdiv=0, jitter=0.2)
            b.tube((sx * 1.08, py, 0.98), (sx * 1.08, py - sy * 0.55, 0.02),
                   0.035, 0.03, "Wood", sides=5)
            for z in (0.88, 0.70):
                b.rope_wrap((sx * 1.08, py, z), 0.09, 0.020, major=6, minor=4)
        # top crossbeam between the end posts
        b.box((0, sy * 4.83, 1.10), (2.35, 0.14, 0.12), "WoodDark",
              taper=0.95, rot=(0, 0, rng.uniform(-1, 1)))
        # loose rope ends
        b.tube((1.02, sy * 4.76, 0.95), (1.10, sy * 4.68, 0.62), 0.018, 0.015,
               "Rope", sides=4)
        b.ico((1.10, sy * 4.68, 0.60), 0.035, "Rope", subdiv=0)

    # handrail and lower rope, with sag
    for sx in (-1, 1):
        zs_top = []
        zs_low = []
        ys = [-4.83 + 9.66 * i / 8 for i in range(9)]
        for y in ys:
            sag = 1.0 - (y / 4.83) ** 2
            zs_top.append(1.02 - 0.25 * sag)
            zs_low.append(0.58 - 0.14 * sag)
        for i in range(8):
            b.tube((sx * 1.08, ys[i], zs_top[i]),
                   (sx * 1.08, ys[i + 1], zs_top[i + 1]),
                   0.028, 0.028, "Rope", sides=5)
            b.tube((sx * 1.08, ys[i], zs_low[i]),
                   (sx * 1.08, ys[i + 1], zs_low[i + 1]),
                   0.023, 0.023, "Rope", sides=5)
        # vertical hangers
        for k in range(1, 8):
            y = ys[k]
            sag = 1.0 - (y / 4.83) ** 2
            zl = 0.58 - 0.14 * sag
            b.tube((sx * 1.08, y, zl), (sx * 1.08, y, -0.005),
                   0.015, 0.015, "Rope", sides=4)
            b.ico((sx * 1.08, y, 0.01), 0.028, "Rope", subdiv=0)
    # fine end lashings on the handrail
    for sy in (-1, 1):
        for sx in (-1, 1):
            b.rope_wrap((sx * 1.08, sy * 4.83, 0.99), 0.055, 0.016,
                        major=5, minor=3)


def build_stone_bridge(b):
    """9 m stone arch bridge along Z, deck top z=0, arch down to -2.5, moss and snow."""
    n = 10
    us = [-3.1 + 6.2 * i / n for i in range(n + 1)]
    zs = [-2.5 + 2.0 * math.sqrt(max(0.0, 1.0 - (u / 3.1) ** 2)) for u in us]
    top_z = -0.30

    # deck slabs (top exactly z=0)
    for i in range(7):
        y = -3.87 + i * 1.29
        b.box((0, y, -0.16), (3.0, 1.26, 0.32),
              "Stone" if i % 2 == 0 else "StoneLight", taper=0.995)

    # spandrel walls
    for side in (-1, 1):
        xo, xi = side * 1.44, side * 1.08
        V = []
        for u, z in zip(us, zs):
            V.append((xo, u, z))
            V.append((xo, u, top_z))
        base = 2 * (n + 1)
        for u, z in zip(us, zs):
            V.append((xi, u, z))
            V.append((xi, u, top_z))
        F = []
        for i in range(n):
            o = 2 * i
            ii = base + 2 * i
            F.append((o, o + 2, o + 3, o + 1))
            F.append((ii, ii + 1, ii + 3, ii + 2))
            F.append((o, ii, ii + 2, o + 2))
            F.append((o + 1, o + 3, ii + 3, ii + 1))
        F.append((0, 1, base + 1, base))
        F.append((2 * n, base + 2 * n, base + 2 * n + 1, 2 * n + 1))
        b.add(V, F, "Stone")

    # arch soffit across the tunnel
    V = []
    for u, z in zip(us, zs):
        V.append((-1.08, u, z))
        V.append((1.08, u, z))
    F = [(2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2) for i in range(n)]
    b.add(V, F, "StoneDark")

    # protruding voussoir band on both outer faces
    for side in (-1, 1):
        for i in range(n):
            du = us[i + 1] - us[i]
            dz = zs[i + 1] - zs[i]
            ln = max(1e-6, math.hypot(dz, du))
            nu, nz = -dz / ln, du / ln
            x = side * 1.50
            p0 = (x, us[i], zs[i])
            p1 = (x, us[i + 1], zs[i + 1])
            p2 = (x, us[i + 1] + nu * 0.22, zs[i + 1] + nz * 0.22)
            p3 = (x, us[i] + nu * 0.22, zs[i] + nz * 0.22)
            b.add([p0, p1, p2, p3], [(0, 1, 2, 3)],
                  "StoneDark" if i % 3 == 1 else "StoneLight")
        b.box((side * 1.49, 0, -0.60), (0.02, 0.36, 0.32), "StoneLight", taper=0.9)

    # abutments
    for sy in (-1, 1):
        b.box((0, sy * 3.8, -1.40), (2.92, 1.4, 2.2), "Stone", taper=0.96)
        for j, (x, z) in enumerate(((-0.95, -2.1), (0.0, -1.45), (0.95, -0.8))):
            b.box((x, sy * 4.48, z), (0.86, 0.04, 0.34),
                  "StoneLight" if j % 2 == 0 else "StoneDark")
        for side in (-1, 1):
            for j, (y, z) in enumerate(((3.45, -1.9), (3.8, -1.25), (4.15, -0.65))):
                b.box((side * 1.47, sy * y, z), (0.04, 0.34, 0.30),
                      "StoneLight" if j % 2 == 0 else "StoneDark", taper=0.96)
        b.ico((-0.95, sy * 4.48, -1.85), 0.24, "Moss",
              scale=(1.0, 0.06, 0.55), subdiv=0, jitter=0.2)
        b.snow_blob((0.92, sy * 4.40, -0.34), 0.06, flat=0.35)
    # shallow masonry band under the deck on the spandrel faces
    for side in (-1, 1):
        for j, y in enumerate((-2.2, 0.0, 2.2)):
            b.box((side * 1.485, y, -0.36), (0.02, 0.34, 0.10),
                  "StoneLight" if j % 2 == 0 else "StoneDark")

    # parapets
    for side in (-1, 1):
        b.box((side * 1.36, 0, 0.21), (0.22, 8.4, 0.42), "Stone", taper=0.96)
        for j, y in enumerate((-3.36, -1.68, 0.0, 1.68, 3.36)):
            b.box((side * 1.36, y, 0.44), (0.28, 1.56, 0.08),
                  "StoneLight" if j % 2 == 0 else "Stone")
            b.box((side * 1.36, y, 0.505), (0.28, 1.50, 0.055), "Snow", taper=0.9)
            b.snow_blob((side * 1.37, y + 0.45, 0.53), 0.10, flat=0.4)
        for y, z in ((-2.5, -0.55), (-0.9, -0.60), (1.9, -0.62)):
            b.ico((side * 1.44, y, z), 0.21, "Moss",
                  scale=(0.08, 1.0, 0.6), subdiv=0, jitter=0.22)
        b.ico((side * 1.36, 3.9, 0.27), 0.16, "Moss",
              scale=(0.8, 0.6, 1.0), subdiv=0, jitter=0.2)
        # end piers
        for sy in (-1, 1):
            b.box((side * 1.36, sy * 4.2, 0.30), (0.28, 0.40, 0.60), "StoneDark",
                  taper=0.94)
            b.spike((side * 1.36, sy * 4.2, 0.60), (side * 1.36, sy * 4.2, 0.72),
                    0.19, "Stone", sides=4, phase=math.pi / 4)
            b.snow_blob((side * 1.36, sy * 4.2, 0.70), 0.09, flat=0.35)

    # moss along the deck edges and snow drifts
    for side in (-1, 1):
        for y, z in ((-4.0, 0.03), (-1.5, 0.02), (1.7, 0.02), (3.8, 0.03)):
            b.ico((side * 1.42, y, z), 0.16, "Moss",
                  scale=(0.35, 1.2, 0.28), subdiv=0, jitter=0.2)
        b.snow_blob((side * 1.22, 2.7, 0.03), 0.16, flat=0.28)
        b.snow_blob((side * 1.24, -2.2, 0.03), 0.14, flat=0.28)
    # moss on the arch ring / spandrel faces (kept above the arch curve)
    for side in (-1, 1):
        b.ico((side * 1.46, -1.20, -0.50), 0.18, "Moss",
              scale=(0.06, 0.65, 0.55), subdiv=0, jitter=0.2)
        b.ico((side * 1.46, 1.40, -0.62), 0.15, "Moss",
              scale=(0.06, 0.65, 0.55), subdiv=0, jitter=0.2)


def build_ruin_pillar(b):
    """3.5 m broken fluted stone pillar with base, jagged break, moss and ivy."""
    rng = b.rng
    # plinth
    b.box((0, 0, 0.08), (1.10, 1.10, 0.16), "StoneDark", rot=(0, 0, 3), taper=0.94)
    b.box((0, 0, 0.23), (0.90, 0.90, 0.14), "StoneLight", rot=(0, 0, -2), taper=0.93)
    b.cylinder((0, 0, 0.35), 0.42, 0.10, "Stone", sides=10)
    b.box((0, 0, 0.44), (0.66, 0.66, 0.08), "StoneDark", rot=(0, 0, 2), taper=0.96)

    n = 12
    angles = [2.0 * math.pi * i / n for i in range(n)]
    low, mid = [], []
    for i, a in enumerate(angles):
        r_lo = 0.36 if i % 2 == 0 else 0.23
        r_mi = 0.34 if i % 2 == 0 else 0.22
        low.append((r_lo * math.cos(a), r_lo * math.sin(a), 0.48))
        mid.append((r_mi * math.cos(a + 0.10) + 0.035,
                    r_mi * math.sin(a + 0.10) - 0.018, 2.56))
    # lower shaft faces (deep flutes; alternating tone reads the grooves)
    for i in range(n):
        j = (i + 1) % n
        mat = "StoneDark" if i % 2 == 0 else "Stone"
        if i in (1, 7):
            mat = "StoneLight"
        b.add([low[i], low[j], mid[j], mid[i]], [(0, 1, 2, 3)], mat)

    # broad broken crown: high on one side, notched low on the other
    top = []
    for i, a in enumerate(angles):
        z = 3.06 + 0.30 * math.cos(a + 0.35) + rng.uniform(-0.05, 0.04)
        r = 0.30 if i % 2 == 0 else 0.20
        x = r * math.cos(a + 0.16) + 0.075
        y = r * math.sin(a + 0.16) - 0.032
        top.append((x, y, max(2.66, min(z, 3.42))))
    top[2] = (top[2][0], top[2][1], 3.50)
    top[1] = (top[1][0], top[1][1], 3.39)
    top[3] = (top[3][0], top[3][1], 3.32)
    top[6] = (top[6][0], top[6][1], 2.64)
    top[7] = (top[7][0], top[7][1], 2.71)
    top[8] = (top[8][0], top[8][1], 2.79)
    for i in range(n):
        j = (i + 1) % n
        mat = "StoneLight" if i == 1 else (
            "StoneDark" if i % 2 == 0 else "Stone")
        b.add([mid[i], mid[j], top[j], top[i]], [(0, 1, 2, 3)], mat)
    # rough, recessed dark break surface
    cap_c = (0.05, -0.02, 2.93)
    for i in range(n):
        j = (i + 1) % n
        b.add([top[i], top[j], cap_c], [(0, 1, 2)],
              "StoneDark" if i % 3 else "Stone")
    # broken chunk wedged on the crown
    b.ico((0.12, 0.10, 3.22), 0.21, "Stone", scale=(1.0, 0.85, 0.45),
          subdiv=0, jitter=0.3)
    b.ico((-0.20, 0.04, 3.04), 0.15, "StoneLight", scale=(0.9, 0.8, 0.5),
          subdiv=0, jitter=0.25)

    # a couple of chips lying at the base
    b.ico((0.72, -0.42, 0.15), 0.26, "Stone", scale=(1.1, 0.9, 0.55),
          subdiv=0, jitter=0.25)
    b.tube((0.40, 0.10, 0.14), (1.15, 0.35, 0.14), 0.13, 0.11, "Stone",
           sides=6, phase=0.3)
    b.box((0.98, -0.18, 0.08), (0.30, 0.24, 0.16), "StoneDark",
          rot=(0, 0, 28), taper=0.85)
    b.moss((0.78, -0.55, 0.05), 0.15, "Moss", flat=0.3)
    b.moss((1.05, 0.35, 0.06), 0.12, "MossLight", flat=0.28)

    # climbing vines
    vine1 = []
    for i in range(16):
        t = i / 15.0
        ang = 0.8 + t * 5.3
        rad = 0.345 - 0.02 * t
        vine1.append((rad * math.cos(ang) + 0.02 * t,
                      rad * math.sin(ang) - 0.01 * t,
                      0.52 + t * 2.15))
    b.vine(vine1, r=0.024, leaves=10)
    vine2 = []
    for i in range(7):
        t = i / 6.0
        ang = 3.4 - t * 2.6
        rad = 0.325 - 0.02 * t
        vine2.append((rad * math.cos(ang) + 0.01,
                      rad * math.sin(ang),
                      0.58 + t * 0.95))
    b.vine(vine2, r=0.018, leaves=4, leaf_mat="Moss")
    # hanging tendril over the break
    vine3 = [(0.26, 0.16, 3.20), (0.38, 0.04, 2.96), (0.33, -0.08, 2.74),
             (0.42, -0.16, 2.50), (0.35, -0.20, 2.28)]
    b.vine(vine3, r=0.020, leaves=4)
    for p in ((0.42, -0.16, 2.50), (0.35, -0.20, 2.28)):
        b.tube(p, (p[0] + 0.05, p[1] - 0.02, p[2] - 0.26), 0.012, 0.005,
               "Vine", sides=4)

    # moss
    b.moss((-0.36, -0.30, 0.12), 0.19, "Moss", flat=0.25)
    b.moss((0.34, -0.32, 0.17), 0.15, "MossLight", flat=0.25)
    b.moss((-0.22, 0.28, 0.47), 0.13, "Moss", flat=0.3)
    b.moss((0.02, -0.32, 0.56), 0.16, "Moss", flat=0.35, scale=(1.4, 0.8))
    b.moss((0.18, 0.26, 1.42), 0.10, "Moss", flat=0.3, scale=(0.7, 1.6))
    b.ico((0.03, -0.31, 0.82), 0.13, "Moss",
          scale=(0.45, 0.20, 1.6), subdiv=0, jitter=0.25)
    b.moss((0.20, -0.26, 1.85), 0.09, "MossLight", flat=0.35,
           scale=(0.5, 0.6))
    b.moss((-0.16, -0.12, 3.06), 0.17, "Moss", flat=0.3)
    b.moss((0.24, 0.12, 3.20), 0.12, "MossLight", flat=0.3)
    b.moss((-0.30, 0.20, 3.09), 0.10, "Moss", flat=0.3)
    b.moss((-0.42, 0.18, 0.13), 0.14, "MossLight", flat=0.22)


def build_signpost(b):
    """2 m wooden signpost with 3 blank arrow boards, hemp lashings, no text."""
    rng = b.rng
    # base stones
    b.ico((0, 0, 0.13), 0.28, "Stone", scale=(1.25, 1.15, 0.25), subdiv=0,
          jitter=0.15)
    b.box((0.18, -0.20, 0.05), (0.30, 0.26, 0.10), "StoneDark",
          rot=(0, 0, 22), taper=0.92)
    b.moss((-0.16, -0.12, 0.08), 0.13, "Moss", flat=0.3)
    b.moss((0.24, 0.16, 0.05), 0.10, "MossLight", flat=0.25)
    # post (slightly leaning)
    b.tube((0, 0, 0.0), (0.05, -0.02, 1.94), 0.095, 0.078, "Wood", sides=8)
    b.cylinder((0.05, -0.02, 1.925), 0.11, 0.05, "WoodDark", sides=8)
    b.box((0.05, -0.02, 1.955), (0.23, 0.23, 0.035), "WoodDark",
          rot=(0, 0, 45), taper=0.9)
    b.spike((0.05, -0.02, 1.972), (0.05, -0.02, 2.0), 0.135, "WoodDark",
            sides=4, phase=math.pi / 4)
    b.moss((-0.02, 0.06, 0.62), 0.10, "Moss", flat=0.45, scale=(0.6, 1.4))

    def arrow_board(cz, angle_deg, length, width, thick=0.065):
        ca = math.cos(math.radians(angle_deg))
        sa = math.sin(math.radians(angle_deg))
        outline = [(-0.02, -width / 2), (length - 0.22, -width / 2),
                   (length, 0.0), (length - 0.22, width / 2),
                   (-0.02, width / 2), (-0.14, 0.0)]

        def xf(u, v, wi):
            return (u * ca - wi * sa, u * sa + wi * ca, cz + v)

        nb = len(outline)
        V = []
        for wi in (-thick / 2, thick / 2):
            for u, v in outline:
                V.append(xf(u, v, wi))
        F = [tuple(range(nb)), tuple(range(2 * nb - 1, nb - 1, -1))]
        for i in range(nb):
            j = (i + 1) % nb
            F.append((i, j, nb + j, nb + i))
        b.add(V, F, "WoodDark")
        # blank inset faces (no text)
        cu = sum(p[0] for p in outline) / nb
        inner = [(cu + (u - cu) * 0.84, v * 0.62) for u, v in outline]
        for sgn in (-1, 1):
            w0 = sgn * thick / 2
            w1 = sgn * (thick / 2 + 0.014)
            Vi = [xf(u, v, w0) for u, v in inner] + [xf(u, v, w1) for u, v in inner]
            Fi = [tuple(range(nb)), tuple(range(2 * nb - 1, nb - 1, -1))]
            for i in range(nb):
                j = (i + 1) % nb
                Fi.append((i, j, nb + j, nb + i))
            b.add(Vi, Fi, "WoodLight")
        # wooden pegs on both blank faces
        for v in (-width * 0.26, width * 0.26):
            b.tube(xf(0.03, v, thick / 2 + 0.03), xf(0.03, v, thick / 2 - 0.02),
                   0.018, 0.018, "WoodDark", sides=5)
        # rope lashings around post and board tail
        for dz in (-0.045, 0.045):
            b.rope_wrap((0.04, -0.01, cz + dz), 0.118, 0.023, major=8, minor=4)
        b.tube((0.02, -0.08, cz - 0.09),
               (0.02 + 0.18 * ca, -0.08 + 0.18 * sa, cz + 0.02),
               0.016, 0.016, "Rope", sides=4)
        b.ico((0.03, -0.11, cz - 0.09), 0.035, "Rope", subdiv=0)

    arrow_board(1.06, 20, 0.95, 0.21)
    arrow_board(1.39, 150, 0.82, 0.19)
    arrow_board(1.70, 205, 0.72, 0.17)

    # hanging rope ends
    b.tube((0.02, -0.10, 1.02), (0.08, -0.16, 0.78), 0.016, 0.014, "Rope", sides=4)
    b.tube((0.08, -0.16, 0.78), (0.03, -0.10, 0.62), 0.014, 0.012, "Rope", sides=4)
    b.ico((0.03, -0.10, 0.60), 0.035, "Rope", subdiv=0)
    b.moss((0.10, -0.12, 0.03), 0.09, "Moss", flat=0.25)


def build_well(b):
    """2 m stone well with wood frame, rope and bucket, moss; oasis or village."""
    # paving
    for i in range(6):
        a = math.radians(i * 60 + 12)
        b.box((math.cos(a) * 0.98, math.sin(a) * 0.98, 0.03),
              (0.60, 0.42, 0.06), "StoneLight" if i % 2 else "Stone",
              rot=(0, 0, math.degrees(a) + 90), taper=0.95)
    b.moss((0.62, 0.62, 0.07), 0.12, "Moss", flat=0.25)
    b.moss((-0.70, -0.45, 0.07), 0.10, "MossLight", flat=0.25)

    # well ring: two courses + rim
    b.annulus((0, 0, 0.18), 0.74, 0.53, 0.36, "Stone", sides=12, phase=math.pi / 12)
    b.annulus((0, 0, 0.52), 0.71, 0.52, 0.34, "StoneLight", sides=12,
              phase=math.pi / 12 + 0.15)
    b.annulus((0, 0, 0.75), 0.78, 0.47, 0.09, "Stone", sides=12,
              phase=math.pi / 12)
    # stone blocks around the rim
    for i in range(8):
        a = math.radians(i * 45 + 8)
        b.box((math.cos(a) * 0.72, math.sin(a) * 0.72, 0.40 + (i % 2) * 0.16),
              (0.30, 0.11, 0.22), "StoneLight" if i % 3 else "Stone",
              rot=(0, 0, math.degrees(a) + 90), taper=0.95)
    for i in range(4):
        a = math.radians(i * 90 + 20)
        b.box((math.cos(a) * 0.66, math.sin(a) * 0.66, 0.81),
              (0.38, 0.22, 0.10), "StoneDark" if i % 2 else "Stone",
              rot=(0, 0, math.degrees(a) + 90), taper=0.92)
    # water inside
    b.cylinder((0, 0, 0.30), 0.50, 0.02, "Water", sides=12)
    # inner moss / damp
    b.ico((0.50, -0.30, 0.72), 0.16, "Moss", scale=(0.9, 0.5, 0.25),
          subdiv=0, jitter=0.2)
    b.moss((-0.60, 0.28, 0.78), 0.12, "MossLight", flat=0.2)

    # frame posts
    for sx in (-1, 1):
        b.tube((sx * 0.86, 0, 0.78), (sx * 0.80, 0, 1.62), 0.085, 0.072,
               "WoodDark", sides=6)
        b.box((sx * 0.84, 0, 0.79), (0.24, 0.22, 0.08), "Wood", taper=0.9)
        b.tube((sx * 0.81, 0, 1.50), (sx * 0.84, 0, 1.16), 0.035, 0.03,
               "Wood", sides=5)
    # crossbeam + axle
    b.box((0, 0, 1.60), (2.02, 0.14, 0.13), "WoodDark", taper=0.94)
    b.box((0, 0, 1.50), (0.56, 0.12, 0.08), "Wood")
    b.cylinder((0, 0, 1.38), 0.055, 1.76, "Wood", sides=8, rot=(0, 90, 0))
    b.cylinder((0, 0, 1.38), 0.095, 0.34, "Rope", sides=8, rot=(0, 90, 0))
    # crank
    b.box((0.94, 0, 1.28), (0.05, 0.05, 0.28), "WoodDark", rot=(0, 0, 0))
    b.cylinder((1.00, 0, 1.14), 0.035, 0.14, "WoodDark", sides=6, rot=(0, 90, 0))
    # roof
    b.gable_roof(0, 0, 1.64, 0.97, 0.56, 0.28, 0.08,
                 mat_top="Roof", mat_under="RoofEdge", mat_edge="RoofEdge")
    # small wooden gable boards close the roof ends
    for sx in (-1, 1):
        xa, xb = sx * 0.91, sx * 0.94
        Vg = [(xa, -0.48, 1.66), (xa, 0.48, 1.66), (xa, 0.0, 1.90),
              (xb, -0.48, 1.66), (xb, 0.48, 1.66), (xb, 0.0, 1.90)]
        Fg = [(3, 4, 5), (0, 2, 1), (0, 1, 4, 3), (0, 3, 5, 2), (1, 2, 5, 4)]
        b.add(Vg, Fg, "Wood")
    b.box((0, 0, 1.925), (1.96, 0.10, 0.05), "RoofEdge", taper=0.8)
    b.spike((0, 0, 1.955), (0, 0, 2.0), 0.045, "WoodDark", sides=6)
    # roof moss
    b.moss((-0.42, -0.24, 1.805), 0.12, "Moss", flat=0.3)
    b.moss((0.26, 0.18, 1.815), 0.10, "MossLight", flat=0.3)
    b.moss((0.55, -0.18, 1.75), 0.08, "Moss", flat=0.3)
    b.moss((-0.12, 0.30, 1.76), 0.08, "MossLight", flat=0.3)
    b.moss((0.36, 0.0, 1.925), 0.10, "Moss", flat=0.25)
    b.moss((-0.28, -0.06, 1.905), 0.08, "MossLight", flat=0.25)
    b.moss((-0.55, 0.03, 0.83), 0.10, "Moss", flat=0.2)
    b.moss((0.52, -0.35, 0.80), 0.08, "MossLight", flat=0.2)

    # rope and bucket
    b.tube((0, 0, 1.38), (0, -0.02, 1.24), 0.018, 0.018, "Rope", sides=5)
    b.cylinder((0, -0.02, 1.00), 0.13, 0.28, "Wood", sides=8, rtop=0.19)
    b.cylinder((0, -0.02, 1.135), 0.192, 0.020, "WoodDark", sides=8)
    b.cylinder((0, -0.02, 0.91), 0.135, 0.03, "Metal", sides=8)
    b.cylinder((0, -0.02, 1.065), 0.178, 0.028, "Metal", sides=8)
    b.cylinder((0, -0.02, 1.115), 0.165, 0.012, "Water", sides=8)
    b.tube((-0.19, -0.02, 1.14), (-0.16, -0.02, 1.24), 0.010, 0.010, "Metal", sides=4)
    b.tube((-0.16, -0.02, 1.24), (0.16, -0.02, 1.24), 0.010, 0.010, "Metal", sides=4)
    b.tube((0.16, -0.02, 1.24), (0.19, -0.02, 1.14), 0.010, 0.010, "Metal", sides=4)
    b.tube((0, -0.02, 1.24), (0, -0.02, 1.20), 0.012, 0.012, "Rope", sides=4)
    # clay jug by the well
    b.cylinder((1.00, -0.36, 0.16), 0.15, 0.32, "Clay", sides=8, rtop=0.19)
    b.cylinder((1.00, -0.36, 0.36), 0.10, 0.08, "Clay", sides=8)
    b.cylinder((1.00, -0.36, 0.405), 0.13, 0.035, "OchreDark", sides=8,
               rtop=0.12)
    b.moss((0.92, -0.46, 0.03), 0.08, "Moss", flat=0.22)
    # extra moss on the base
    b.moss((-0.55, -0.58, 0.06), 0.12, "Moss", flat=0.25)
    b.moss((0.40, 0.68, 0.05), 0.10, "MossLight", flat=0.22)


# ----------------------------------------------------------------------------
# asset registry
# ----------------------------------------------------------------------------

ASSETS = [
    dict(name="torii_gate", build=build_torii_gate, az=32, el=8, margin=1.04,
         ground=0.0, tags=["mossgarden", "landmark", "gate", "torii", "vermillion"],
         use="苔庭地标：穿过式鸟居，行人在本地 Y 轴方向从门下通过。"),
    dict(name="stone_lantern", build=build_stone_lantern, az=42, el=9, margin=1.15,
         ground=0.0, tags=["mossgarden", "shrine", "lantern", "glow", "stone"],
         use="苔庭/神社参道的暖光石灯笼，可重复摆放。"),
    dict(name="moss_shrine", build=build_moss_shrine, az=33, el=14, margin=1.07,
         ground=0.0, tags=["mossgarden", "shrine", "glow", "moss", "wood"],
         use="苔庭深处的小神社，纸门透光，作为祈祷点/记忆触发点。"),
    dict(name="wooden_cabin", build=build_wooden_cabin, az=36, el=13, margin=1.05,
         ground=0.0, tags=["frostvale", "house", "cabin", "snow", "glow"],
         use="霜枝谷雪村木屋，暖窗+石烟囱，门廊朝向 -Y。"),
    dict(name="market_tent", build=build_market_tent, az=34, el=18, margin=1.06,
         ground=0.0, tags=["amberreach", "market", "tent", "fabric", "glow"],
         use="琥珀沙海绿洲集市的条纹帐篷摊位，正面开放朝向 -Y。"),
    dict(name="rope_bridge", build=build_rope_bridge, az=64, el=15, margin=1.02,
         ground=-0.55, tags=["amberreach", "bridge", "rope", "desert", "crossing"],
         use="沙海峡谷绳桥，跨度 10 m，沿 Z 轴，桥面顶面 z=0，游戏侧加碰撞。"),
    dict(name="stone_bridge", build=build_stone_bridge, az=58, el=8, margin=1.06,
         ground=-2.62, tags=["frostvale", "bridge", "stone", "arch", "snow"],
         use="霜枝谷石拱桥，跨度 9 m，沿 Z 轴，桥面顶面 z=0，下方拱到 -2.5 m。"),
    dict(name="ruin_pillar", build=build_ruin_pillar, az=35, el=15, margin=1.08,
         ground=0.0, tags=["mossgarden", "ruin", "pillar", "stone", "vines"],
         use="苔庭遗迹的断裂石柱，可与断墙/断鸟居组合成废墟。"),
    dict(name="signpost", build=build_signpost, az=26, el=9, margin=1.14,
         ground=0.0, tags=["amberreach", "village", "signpost", "wood", "blank"],
         use="无字木指路牌，空白箭头牌，麻绳绑扎；路口/营地指示物。"),
    dict(name="well", build=build_well, az=31, el=12, margin=1.12,
         ground=0.0, tags=["amberreach", "village", "well", "stone", "water"],
         use="石砌水井，木架绳桶，可放在绿洲集市或霜枝谷村庄。"),
]


# ----------------------------------------------------------------------------
# contact sheet (external Pillow python)
# ----------------------------------------------------------------------------

CONTACT_SHEET_PY = r'''
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

folder = sys.argv[1]
entries = json.loads(sys.argv[2])
out = os.path.join(folder, "contact_sheet.png")

cols = 4
cell = 512
label_h = 48
gap = 18
margin = 30
title_h = 84
rows = (len(entries) + cols - 1) // cols
W = margin * 2 + cols * cell + (cols - 1) * gap
H = title_h + margin + rows * (cell + label_h) + (rows - 1) * gap + margin

bg = (239, 232, 216)
ink = (59, 53, 45)
muted = (123, 112, 96)
line = (214, 202, 181)

img = Image.new("RGB", (W, H), bg)
d = ImageDraw.Draw(img)

def font(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()

bold_paths = [r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf",
              r"C:\Windows\Fonts\consolab.ttf", r"C:\Windows\Fonts\msyhbd.ttc"]
reg_paths = [r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf",
             r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\msyh.ttc"]
f_title = font(bold_paths, 27)
f_sub = font(reg_paths, 15)
f_name = font(bold_paths, 20)
f_meta = font(reg_paths, 14)
f_num = font(bold_paths, 15)

d.text((margin, margin), "ARCHITECTURE BATCH  /  LANTERN ISLES", font=f_title, fill=ink)
d.text((margin, margin + 37), "10 low-poly building assets  ·  Cycles CPU 24 spp  ·  512 x 512  ·  origin at base centre, facing -Y",
       font=f_sub, fill=muted)
d.line([(margin, title_h + 4), (W - margin, title_h + 4)], fill=line, width=2)

for i, e in enumerate(entries):
    r, c = divmod(i, cols)
    x = margin + c * (cell + gap)
    y = title_h + margin + r * (cell + label_h + gap)
    p = os.path.join(folder, e["name"] + ".png")
    if os.path.exists(p):
        im = Image.open(p).convert("RGB")
        if im.size != (cell, cell):
            im = im.resize((cell, cell), Image.LANCZOS)
        img.paste(im, (x, y))
        d.rectangle([x, y, x + cell - 1, y + cell - 1], outline=line, width=1)
    else:
        d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(232, 224, 209), outline=line)
        d.text((x + 18, y + 18), "missing", font=f_name, fill=(170, 90, 80))
    # number chip
    d.rectangle([x + 12, y + 12, x + 42, y + 36], fill=(239, 232, 216))
    d.text((x + 19, y + 15), "%02d" % (i + 1), font=f_num, fill=ink)
    # labels
    ly = y + cell + 8
    d.text((x + 2, ly), e["name"], font=f_name, fill=ink)
    meta = "%d tris   ·   bounds %.2f x %.2f x %.2f m" % (
        e.get("tris", 0),
        e.get("size", [0, 0, 0])[0], e.get("size", [0, 0, 0])[1],
        e.get("size", [0, 0, 0])[2])
    d.text((x + 2, ly + 25), meta, font=f_meta, fill=muted)

img.save(out, "PNG")
print("contact sheet:", out, img.size)
'''


def make_contact_sheet(entries):
    payload = json.dumps([
        dict(name=e["name"], tris=e["tris"], size=e["size"]) for e in entries
    ])
    if not os.path.exists(PIL_PYTHON):
        print("!! Pillow python missing, skipping contact sheet")
        return
    subprocess.run([PIL_PYTHON, "-c", CONTACT_SHEET_PY, PREVIEW_DIR, payload],
                   check=True)


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

RENDER_SAMPLES = 24


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {"only": None, "samples": 24, "render": True, "export": True,
            "sheet": True, "sheet_only": False, "manifest": True}
    for a in argv:
        if a.startswith("--only="):
            opts["only"] = set(a.split("=", 1)[1].split(","))
        elif a.startswith("--samples="):
            opts["samples"] = int(a.split("=", 1)[1])
        elif a == "--no-render":
            opts["render"] = False
        elif a == "--no-export":
            opts["export"] = False
        elif a == "--no-sheet":
            opts["sheet"] = False
        elif a == "--no-manifest":
            opts["manifest"] = False
        elif a == "--sheet-only":
            opts["sheet_only"] = True
    return opts


def write_manifest(entries):
    assets = []
    for e in entries:
        assets.append({
            "name": e["name"],
            "file": "assets/models/architecture/%s.glb" % e["name"],
            "bounds": {
                "min": [round(v, 3) for v in e["min"]],
                "max": [round(v, 3) for v in e["max"]],
                "size": [round(v, 3) for v in e["size"]],
            },
            "tris": e["tris"],
            "tags": e["tags"],
            "suggested_use": e["use"],
        })
    data = {
        "batch": "architecture",
        "version": 1,
        "unit": "meter",
        "forward_axis_blender": "-Y",
        "forward_axis_godot": "+Z",
        "origin": "footprint centre on ground plane (bridges: deck centre, deck top z=0)",
        "materials": "Principled BSDF, no textures; emissive material is named 'Glow'",
        "asset_count": len(assets),
        "total_tris": sum(a["tris"] for a in assets),
        "assets": assets,
    }
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print("manifest:", MANIFEST, "(%d assets, %d tris)" %
          (data["asset_count"], data["total_tris"]))


def run():
    global RENDER_SAMPLES
    opts = parse_args()
    RENDER_SAMPLES = opts["samples"]

    if opts["sheet_only"]:
        with open(MANIFEST, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        entries = [dict(name=a["name"], tris=a["tris"], size=a["bounds"]["size"])
                   for a in data["assets"]]
        make_contact_sheet(entries)
        return

    entries = []
    selected = [a for a in ASSETS if opts["only"] is None or a["name"] in opts["only"]]
    print("building %d asset(s), %d samples" % (len(selected), RENDER_SAMPLES))
    for entry in selected:
        name = entry["name"]
        print("\n== %s ==" % name)
        t0 = time.time()
        sc = reset_scene()
        b = Builder(seed=ASSETS.index(entry) * 7919 + 13)
        entry["build"](b)
        obj = b.to_object(name)
        # ground assets: clamp anything that dipped below z=0, keep the designed height
        if "bridge" not in entry["tags"]:
            mn0, _mx0 = object_bounds(obj)
            if -0.08 < mn0.z < 0.0:
                for v in obj.data.vertices:
                    if v.co.z < 0.0:
                        v.co.z = 0.0
                obj.data.update()
            elif mn0.z >= 0.02:
                print("  !! warning: asset floats %.3f m above ground" % mn0.z)
        mn, mx = object_bounds(obj)
        tris = tri_count(obj)
        size = mx - mn
        print("  tris=%d  bounds min=(%.3f, %.3f, %.3f) max=(%.3f, %.3f, %.3f)" %
              (tris, mn.x, mn.y, mn.z, mx.x, mx.y, mx.z))
        print("  materials:", ", ".join(b.mat_names))
        if opts["export"]:
            path = export_glb(obj, name)
            print("  glb:", path, "%.0f KB" % (os.path.getsize(path) / 1024.0))
        if opts["render"]:
            setup_stage(sc, name, (mn, mx), entry["az"], entry["el"], entry["margin"],
                        entry["ground"], "bridge" in entry["tags"])
            render_preview(sc, name)

        entries.append(dict(
            name=name, min=tuple(mn), max=tuple(mx), size=tuple(size), tris=tris,
            tags=entry["tags"], use=entry["use"],
        ))
        print("  total %.1fs" % (time.time() - t0))

    full_run = opts["only"] is None
    if full_run:
        if opts["manifest"]:
            write_manifest(entries)
        if opts["sheet"]:
            make_contact_sheet(entries)
    else:
        print("\npartial run: manifest/contact sheet left untouched")
        if opts["sheet"]:
            make_contact_sheet(entries)


if __name__ == "__main__":
    run()
