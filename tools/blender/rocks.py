#!/usr/bin/env python3
"""Rocks / natural forms batch for Lantern Isles.

Run inside Blender (headless) to build, export and render all nine assets:

    blender -b --python tools/blender/rocks.py

Then compose the labelled contact sheet with the project Python:

    python tools/blender/rocks.py --sheet

The Blender half deliberately keeps every asset in a single mesh object, with
identity transforms, origin at the centre of the base and front facing -Y.
Only procedural geometry and Principled materials are used.
"""

from __future__ import annotations

import json
import math
import random
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = PROJECT_ROOT / "assets" / "models" / "rocks"
PREVIEW_DIR = PROJECT_ROOT / "assets" / "previews" / "rocks"
MANIFEST_PATH = ASSET_DIR / "manifest_rocks.json"
CONTACT_SHEET_PATH = PREVIEW_DIR / "contact_sheet.png"

ASSET_ORDER = [
    "rock_a",
    "rock_b",
    "rock_c",
    "cliff_spire",
    "sandstone_arch",
    "floating_rock",
    "crystal_cluster",
    "stump",
    "driftwood",
]

ASSET_META = {
    "rock_a": {
        "tags": ["rock", "boulder", "moss", "chapter1", "mossgarden", "landmark"],
        "use": "苔庭·春眠的苔藓地标巨石，可作苔婆婆栖身石、路径端景或可攀爬大石。",
        "camera": (1.35, -1.80, 0.95),
    },
    "rock_b": {
        "tags": ["rock", "weathered", "sharp", "multimesh", "chapter2", "canyon", "reusable"],
        "use": "琥珀沙海与霜枝谷的批量散布风化石，面数低，可用 MultiMesh 大量实例化。",
        "camera": (1.15, -1.90, 1.00),
    },
    "rock_c": {
        "tags": ["rock", "slab", "stratified", "standable", "chapter1", "chapter2"],
        "use": "带层理的扁平岩板，顶面可站立，适合作为低台阶、观景点或路径边缘。",
        "camera": (1.35, -1.80, 1.25),
    },
    "cliff_spire": {
        "tags": ["cliff", "spire", "landmark", "chapter2", "canyon", "wind_eroded"],
        "use": "琥珀沙海狭缝峡谷的 6m 风蚀岩柱地标，双柱剪影，可数根一组构成石柱阵。",
        "camera": (0.85, -2.20, 1.00),
    },
    "sandstone_arch": {
        "tags": ["arch", "sandstone", "landmark", "chapter2", "gateway", "walkthrough"],
        "use": "跨越路径的厚重砂岩拱门，形成穿行框景；拱洞沿 Blender Y 轴，正面朝 -Y。",
        "camera": (0.95, -2.20, 0.85),
    },
    "floating_rock": {
        "tags": ["floating", "sky_island", "rock", "chapter4", "starfall", "magic"],
        "use": "星坠之穹的漂浮岩块，草苔顶面加撕裂岩锥；可在 Godot 中整体缓浮。",
        "camera": (1.25, -1.90, 1.05),
    },
    "crystal_cluster": {
        "tags": ["crystal", "glow", "emission", "chapter4", "starfall", "landmark"],
        "use": "星坠之穹的紫青双色发光晶簇，可作夜光路标、镜湖岸饰或空间焦点。",
        "camera": (1.30, -1.90, 1.00),
    },
    "stump": {
        "tags": ["stump", "wood", "moss", "chapter1", "mossgarden", "prop"],
        "use": "苔庭·春眠的林间砍伐树桩，年轮顶面清楚，可作坐凳或路径点缀。",
        "camera": (1.20, -1.75, 1.40),
    },
    "driftwood": {
        "tags": ["driftwood", "wood", "bleached", "chapter2", "amberreach", "waterside"],
        "use": "沙海绿洲、水边或霜枝谷岸线的灰白浮木，可平放作坐凳、路障或构图引导线。",
        "camera": (0.95, -2.15, 0.90),
    },
}

ASSET_TARGETS = {
    "rock_a": {"target_x": 2.40},
    "rock_b": {"target_z": 1.50},
    "rock_c": {"target_x": 2.80},
    "cliff_spire": {"target_z": 6.00},
    "sandstone_arch": {"target_x": 7.00, "target_z": 6.50},
    "floating_rock": {"target_x": 4.00},
    "crystal_cluster": {"target_z": 2.20},
    "stump": {"target_z": 1.00},
    "driftwood": {"target_x": 2.20},
}


try:  # Blender-only imports.  The sheet mode runs under the regular Python.
    import bpy
    import bmesh
    from mathutils import Vector

    HAS_BPY = True
except ImportError:  # pragma: no cover - exercised by the contact-sheet mode
    bpy = None
    bmesh = None
    Vector = None
    HAS_BPY = False


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------


def srgb(hex_value: str):
    """Convert #RRGGBB to linear-linear RGBA for Blender's shader inputs."""
    text = hex_value.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"bad colour: {hex_value}")
    values = [int(text[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]

    def linear(v: float) -> float:
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    return (linear(values[0]), linear(values[1]), linear(values[2]), 1.0)


def vec(value):
    return Vector((float(value[0]), float(value[1]), float(value[2])))


if HAS_BPY:

    class MeshBuilder:
        def __init__(self):
            self.verts = []
            self.faces = []
            self.mats = []

        def v(self, x, y=None, z=None):
            if y is None:
                x, y, z = x
            self.verts.append((float(x), float(y), float(z)))
            return len(self.verts) - 1

        def face(self, ids, material=0):
            ids = tuple(int(i) for i in ids)
            if len(set(ids)) < 3:
                return
            self.faces.append(ids)
            self.mats.append(int(material))

    def make_material(
        name,
        hex_value,
        roughness=0.88,
        metallic=0.0,
        emission_hex=None,
        emission_strength=0.0,
        base_hex=None,
    ):
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        mat.use_backface_culling = False
        mat.diffuse_color = srgb(base_hex or hex_value)
        nodes = mat.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        if bsdf is None:
            for node in nodes:
                if node.type == "BSDF_PRINCIPLED":
                    bsdf = node
                    break
        if bsdf is None:
            raise RuntimeError(f"no Principled BSDF in material {name}")
        bsdf.inputs["Base Color"].default_value = srgb(base_hex or hex_value)
        bsdf.inputs["Roughness"].default_value = float(roughness)
        bsdf.inputs["Metallic"].default_value = float(metallic)
        if emission_hex:
            emission_socket = bsdf.inputs.get("Emission Color")
            if emission_socket is None:
                emission_socket = bsdf.inputs.get("Emission")
            if emission_socket is None:
                raise RuntimeError("Principled BSDF has no emission colour input")
            emission_socket.default_value = srgb(emission_hex)
            strength_socket = bsdf.inputs.get("Emission Strength")
            if strength_socket is None:
                raise RuntimeError("Principled BSDF has no emission strength input")
            strength_socket.default_value = float(emission_strength)
        else:
            strength_socket = bsdf.inputs.get("Emission Strength")
            if strength_socket is not None:
                strength_socket.default_value = 0.0
        mat.use_fake_user = False
        return mat

    def create_object(name, builder, materials):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(builder.verts, [], builder.faces)
        mesh.update(calc_edges=True)
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        for mat in materials:
            mesh.materials.append(mat)
        if len(mesh.polygons) != len(builder.faces):
            raise RuntimeError(
                f"{name}: from_pydata lost faces ({len(mesh.polygons)}/{len(builder.faces)})"
            )
        for index, polygon in enumerate(mesh.polygons):
            polygon.material_index = builder.mats[index]
            polygon.use_smooth = False

        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.normal_update()
        if bm.faces:
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        if bm.faces:
            bmesh.ops.triangulate(
                bm,
                faces=list(bm.faces),
                quad_method="BEAUTY",
                ngon_method="BEAUTY",
            )
        bm.to_mesh(mesh)
        bm.free()
        for polygon in mesh.polygons:
            polygon.use_smooth = False
        mesh.update()
        obj.location = (0.0, 0.0, 0.0)
        obj.rotation_euler = (0.0, 0.0, 0.0)
        obj.scale = (1.0, 1.0, 1.0)
        return obj

    def mesh_bounds(obj):
        mesh = obj.data
        if not mesh.vertices:
            raise RuntimeError(f"{obj.name}: empty mesh")
        min_x = min(v.co.x for v in mesh.vertices)
        max_x = max(v.co.x for v in mesh.vertices)
        min_y = min(v.co.y for v in mesh.vertices)
        max_y = max(v.co.y for v in mesh.vertices)
        min_z = min(v.co.z for v in mesh.vertices)
        max_z = max(v.co.z for v in mesh.vertices)
        return (
            (min_x, min_y, min_z),
            (max_x, max_y, max_z),
        )

    def finalize_asset(obj, target_x=None, target_z=None):
        mesh = obj.data
        if target_x is not None:
            min_b, max_b = mesh_bounds(obj)
            width = max_b[0] - min_b[0]
            if width > 0:
                factor = float(target_x) / width
                for vertex in mesh.vertices:
                    vertex.co.x *= factor
        if target_z is not None:
            min_b, max_b = mesh_bounds(obj)
            height = max_b[2] - min_b[2]
            if height > 0:
                factor = float(target_z) / height
                for vertex in mesh.vertices:
                    vertex.co.z *= factor
        mesh.update()
        min_b, max_b = mesh_bounds(obj)
        center_x = (min_b[0] + max_b[0]) * 0.5
        center_y = (min_b[1] + max_b[1]) * 0.5
        floor_z = min_b[2]
        for vertex in mesh.vertices:
            vertex.co.x -= center_x
            vertex.co.y -= center_y
            vertex.co.z -= floor_z
        mesh.update()
        for polygon in mesh.polygons:
            polygon.use_smooth = False
        obj.location = (0.0, 0.0, 0.0)
        obj.rotation_euler = (0.0, 0.0, 0.0)
        obj.scale = (1.0, 1.0, 1.0)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        obj.select_set(False)

    def bounds_dict(obj):
        min_b, max_b = mesh_bounds(obj)
        return {
            "min": [round(v, 4) for v in min_b],
            "max": [round(v, 4) for v in max_b],
            "size": [round(max_b[i] - min_b[i], 4) for i in range(3)],
        }

    def tri_count(obj):
        return sum(max(0, len(p.vertices) - 2) for p in obj.data.polygons)

    def ring_points(
        n,
        rx,
        ry,
        z,
        phase=0.0,
        seed=0.0,
        amp=0.06,
        cx=0.0,
        cy=0.0,
        z_amp=0.0,
    ):
        points = []
        for i in range(n):
            angle = 2.0 * math.pi * i / n + phase
            wobble = 1.0 + amp * (
                0.58 * math.sin(3.0 * angle + seed)
                + 0.42 * math.sin(5.0 * angle + seed * 1.73)
            )
            points.append(
                (
                    cx + math.cos(angle) * rx * wobble,
                    cy + math.sin(angle) * ry * wobble,
                    z + z_amp * math.sin(2.0 * angle + seed * 0.81),
                )
            )
        return points

    def _triangle_normal(p0, p1, p2):
        n = (p1 - p0).cross(p2 - p0)
        length = n.length
        if length < 1e-12:
            return Vector((0.0, 0.0, 1.0))
        return n / length

    def add_loft(
        builder,
        rings,
        mat_fn,
        bottom_mat=0,
        cap_top=True,
        top_center=None,
        top_mat=0,
        n=None,
    ):
        """Build a faceted skin through rings (bottom -> top).

        Side quads are split into triangles to keep the surfaces crisp.
        The material callback receives (centre, normal, band, segment).
        """
        if n is None:
            n = len(rings[0])
        indices = []
        for ring in rings:
            indices.append([builder.v(p) for p in ring])
        for band in range(len(rings) - 1):
            lower = rings[band]
            upper = rings[band + 1]
            for i in range(n):
                j = (i + 1) % n
                a = indices[band][i]
                b = indices[band][j]
                c = indices[band + 1][j]
                d = indices[band + 1][i]
                pa, pb, pc, pd = (
                    vec(lower[i]),
                    vec(lower[j]),
                    vec(upper[j]),
                    vec(upper[i]),
                )
                if (band + i) % 2 == 0:
                    tris = [(a, b, c), (a, c, d)]
                    coords = [(pa, pb, pc), (pa, pc, pd)]
                else:
                    tris = [(a, b, d), (b, c, d)]
                    coords = [(pa, pb, pd), (pb, pc, pd)]
                for tri, points in zip(tris, coords):
                    normal = _triangle_normal(*points)
                    center = (points[0] + points[1] + points[2]) / 3.0
                    builder.face(tri, mat_fn(center, normal, band, i))

        # Bottom cap (downward-facing fan). Mostly hidden on grounded props.
        base_z = rings[0][0][2]
        center_x = sum(p[0] for p in rings[0]) / n
        center_y = sum(p[1] for p in rings[0]) / n
        bottom_center = builder.v(center_x, center_y, base_z)
        for i in range(n):
            j = (i + 1) % n
            builder.face((bottom_center, indices[0][j], indices[0][i]), bottom_mat)

        if cap_top:
            if top_center is None:
                top_center_pt = Vector(
                    (
                        sum(p[0] for p in rings[-1]) / n,
                        sum(p[1] for p in rings[-1]) / n,
                        sum(p[2] for p in rings[-1]) / n,
                    )
                )
            else:
                top_center_pt = vec(top_center)
            top_index = builder.v(top_center_pt)
            for i in range(n):
                j = (i + 1) % n
                pa = vec(rings[-1][i])
                pb = vec(rings[-1][j])
                normal = _triangle_normal(top_center_pt, pa, pb)
                center = (top_center_pt + pa + pb) / 3.0
                material = top_mat(center, normal, len(rings) - 1, i) if callable(top_mat) else top_mat
                builder.face((top_index, indices[-1][i], indices[-1][j]), material)
        return indices

    def add_tetra_blade(builder, base, height, lean, width, mat):
        """A tiny closed tetrahedron used as a stylised grass blade."""
        base = vec(base)
        lean = vec(lean)
        direction = lean.normalized() if lean.length > 1e-8 else Vector((0.0, 0.0, 1.0))
        helper = direction.cross(Vector((0.0, 1.0, 0.0)))
        if helper.length < 1e-6:
            helper = direction.cross(Vector((1.0, 0.0, 0.0)))
        helper.normalize()
        helper2 = direction.cross(helper).normalized()
        p0 = base + helper * width + helper2 * (width * 0.28)
        p1 = base - helper * width * 0.85 + helper2 * (width * 0.22)
        p2 = base - helper2 * (width * 0.58)
        tip = base + direction * height
        v0 = builder.v(p0)
        v1 = builder.v(p1)
        v2 = builder.v(p2)
        vt = builder.v(tip)
        builder.face((v0, v1, v2), mat)
        builder.face((v0, vt, v1), mat)
        builder.face((v1, vt, v2), mat)
        builder.face((v2, vt, v0), mat)

    def add_grass_tuft(builder, x, y, z, seed, mat, scale=1.0):
        rng = random.Random(seed)
        blades = 6
        for i in range(blades):
            angle = 2.0 * math.pi * i / blades + rng.uniform(-0.28, 0.28)
            lean = (
                math.cos(angle) * rng.uniform(0.06, 0.16),
                math.sin(angle) * rng.uniform(0.06, 0.16),
                rng.uniform(1.0, 1.35),
            )
            height = rng.uniform(0.15, 0.27) * scale
            width = rng.uniform(0.011, 0.020) * scale
            offset = 0.012 * scale
            add_tetra_blade(
                builder,
                (x + math.cos(angle) * offset, y + math.sin(angle) * offset, z),
                height,
                lean,
                width,
                mat,
            )

    def add_hanging_shard(builder, top, tip, base_radius, mid_radius, mat, seed, n=5):
        rng = random.Random(seed)
        top = vec(top)
        tip = vec(tip)
        axis = tip - top
        length = axis.length
        if length < 1e-6:
            return
        direction = axis.normalized()
        helper = direction.cross(Vector((0.0, 0.0, 1.0)))
        if helper.length < 1e-6:
            helper = direction.cross(Vector((1.0, 0.0, 0.0)))
        helper.normalize()
        helper2 = direction.cross(helper).normalized()
        base_points = []
        mid_points = []
        for i in range(n):
            angle = 2.0 * math.pi * i / n + rng.uniform(-0.12, 0.12)
            wobble = 1.0 + rng.uniform(-0.20, 0.20)
            base_points.append(
                top
                + helper * (math.cos(angle) * base_radius * wobble)
                + helper2 * (math.sin(angle) * base_radius * wobble)
            )
            mid_points.append(
                top
                + direction * length * rng.uniform(0.48, 0.62)
                + helper * (math.cos(angle) * mid_radius * wobble)
                + helper2 * (math.sin(angle) * mid_radius * wobble)
            )
        top_center_idx = builder.v(top - direction * 0.03)
        base_idx = [builder.v(p) for p in base_points]
        mid_idx = [builder.v(p) for p in mid_points]
        tip_idx = builder.v(tip)
        for i in range(n):
            j = (i + 1) % n
            builder.face((top_center_idx, base_idx[i], base_idx[j]), mat)
            builder.face((base_idx[i], mid_idx[i], mid_idx[j]), mat)
            builder.face((base_idx[i], mid_idx[j], base_idx[j]), mat)
            builder.face((mid_idx[i], tip_idx, mid_idx[j]), mat)

    # -----------------------------------------------------------------------
    # Asset builders
    # -----------------------------------------------------------------------

    def build_rock_a():
        mats = [
            make_material("Stone", "#7E8D7A", 0.91),
            make_material("Moss", "#6E8B5A", 0.95),
            make_material("StoneCrevice", "#697868", 0.93),
            make_material("MossLight", "#86A87C", 0.95),
        ]
        b = MeshBuilder()
        n = 11
        rings = [
            ring_points(n, 1.13, 0.94, 0.00, phase=0.04, seed=0.4, amp=0.055),
            ring_points(n, 1.23, 1.00, 0.14, phase=0.10, seed=1.7, amp=0.090, z_amp=0.012, cx=0.03, cy=0.01),
            ring_points(n, 1.18, 0.99, 0.47, phase=0.15, seed=3.1, amp=0.105, z_amp=0.025, cx=0.05, cy=-0.02),
            ring_points(n, 1.06, 0.89, 0.82, phase=0.34, seed=4.8, amp=0.110, z_amp=0.030, cx=0.02, cy=0.02),
            ring_points(n, 0.88, 0.74, 1.14, phase=0.51, seed=6.2, amp=0.100, z_amp=0.030, cx=0.08, cy=0.00),
            ring_points(n, 0.61, 0.52, 1.40, phase=0.72, seed=7.6, amp=0.095, z_amp=0.022, cx=0.06, cy=-0.02),
            ring_points(n, 0.32, 0.28, 1.57, phase=0.88, seed=9.0, amp=0.080, z_amp=0.012, cx=0.03, cy=0.00),
        ]

        def mat_fn(center, normal, band, segment):
            h = 1.66
            # Broad green cap with irregular, downward-reaching fingers.
            if center.z > 0.60 * h and normal.z > 0.02:
                if (segment + band * 2) % 7 == 0:
                    return 3
                return 1
            if center.z > 0.42 * h and normal.z > -0.20:
                angles = math.atan2(center.y, center.x)
                if math.sin(angles * 3.0 + 0.7) > 0.35 or (segment + band * 3) % 17 in (0, 4):
                    return 1 if (segment + band) % 5 else 3
            if center.z < 0.25 and normal.z < -0.05:
                return 2
            if center.z < 0.12:
                return 2
            return 0

        def top_mat(center, normal, band, segment):
            if segment in (2, 3):
                return 0
            if segment in (7, 8):
                return 3
            return 1

        add_loft(
            b,
            rings,
            mat_fn,
            bottom_mat=2,
            top_center=(0.10, -0.04, 1.66),
            top_mat=top_mat,
            n=n,
        )
        return b, mats

    def build_rock_b():
        mats = [
            make_material("Stone", "#A49280", 0.90),
            make_material("StoneCut", "#B7A58F", 0.86),
            make_material("StoneDark", "#877A6A", 0.93),
        ]
        b = MeshBuilder()
        n = 7
        # A leaning, wind-sheared shard.  The big planar bands at the top read
        # as fresh fracture faces rather than a rounded pebble.
        rings = [
            ring_points(n, 0.80, 0.58, 0.00, phase=0.04, seed=1.1, amp=0.10),
            ring_points(n, 0.76, 0.56, 0.25, phase=0.16, seed=2.6, amp=0.10, z_amp=0.010),
            ring_points(n, 0.63, 0.46, 0.53, phase=0.34, seed=4.0, amp=0.12, z_amp=0.012),
            ring_points(n, 0.48, 0.34, 0.86, phase=0.48, seed=5.4, amp=0.13, z_amp=0.016),
            ring_points(n, 0.32, 0.23, 1.16, phase=0.62, seed=6.9, amp=0.14, z_amp=0.012),
            ring_points(n, 0.18, 0.13, 1.38, phase=0.78, seed=8.1, amp=0.13, z_amp=0.008),
        ]

        def main_mat(center, normal, band, segment):
            if center.z < 0.13 or normal.z < -0.34:
                return 2
            if center.z > 0.62 and normal.z > 0.30:
                return 1
            if normal.y < -0.50 and center.z > 0.30:
                return 1
            if band == 3 and segment in (2, 3):
                return 1
            return 0

        add_loft(
            b,
            rings,
            main_mat,
            bottom_mat=2,
            top_center=(0.16, -0.04, 1.50),
            top_mat=1,
            n=n,
        )

        # A second, smaller splinter leaning against the main shard.  It is
        # rooted in the same base, adding a readable fork to the silhouette.
        fn = 5
        flake_rings = [
            ring_points(fn, 0.27, 0.20, 0.00, phase=0.08, seed=11.1, amp=0.14, cx=-0.38, cy=-0.16),
            ring_points(fn, 0.23, 0.17, 0.33, phase=0.21, seed=12.5, amp=0.13, cx=-0.44, cy=-0.20),
            ring_points(fn, 0.15, 0.11, 0.66, phase=0.36, seed=13.8, amp=0.12, cx=-0.51, cy=-0.24),
            ring_points(fn, 0.06, 0.04, 0.90, phase=0.52, seed=15.2, amp=0.10, cx=-0.57, cy=-0.28),
        ]

        def flake_mat(center, normal, band, segment):
            if center.z < 0.10:
                return 2
            if normal.y < -0.35 or normal.z > 0.35:
                return 1
            return 0

        add_loft(
            b,
            flake_rings,
            flake_mat,
            bottom_mat=2,
            top_center=(-0.60, -0.30, 1.02),
            top_mat=1,
            n=fn,
        )

        # Two low broken flakes hugging the base keep the form grounded and
        # give the silhouette a chipped foot.
        chip_specs = [
            ((0.49, -0.41), 0.23, 0.16, 0.35, 21.1),
            ((-0.53, 0.35), 0.25, 0.20, 0.18, 22.7),
        ]
        for (cx, cy), radius, height, phase, seed in chip_specs:
            chip_rings = [
                ring_points(5, radius, radius * 0.72, 0.0, phase=phase, seed=seed, amp=0.17, cx=cx, cy=cy),
                ring_points(5, radius * 0.62, radius * 0.45, height * 0.72, phase=phase + 0.2, seed=seed + 1.2, amp=0.13, cx=cx + 0.02, cy=cy),
            ]
            add_loft(
                b,
                chip_rings,
                lambda center, normal, band, segment: 1 if normal.z > 0.3 else (2 if center.z < 0.04 else 0),
                bottom_mat=2,
                top_center=(cx + 0.01, cy + 0.01, height),
                top_mat=1,
                n=5,
            )
        return b, mats

    def build_rock_c():
        mats = [
            make_material("Stone", "#8B927F", 0.92),
            make_material("StrataWarm", "#9F937C", 0.91),
            make_material("StrataDark", "#747C6B", 0.93),
            make_material("Moss", "#6E8B5A", 0.96),
            make_material("MossLight", "#86A87C", 0.95),
        ]
        b = MeshBuilder()
        n = 10
        # Small bedding lips instead of dramatic overhangs: the slab reads as
        # one sedimentary block, not a stack of plates.  Numbers are metres.
        rings = [
            ring_points(n, 1.40, 1.07, 0.000, phase=0.02, seed=1.2, amp=0.040),
            ring_points(n, 1.42, 1.09, 0.130, phase=0.10, seed=2.4, amp=0.050),
            ring_points(n, 1.35, 1.03, 0.145, phase=0.15, seed=3.1, amp=0.045),
            ring_points(n, 1.37, 1.04, 0.290, phase=0.23, seed=4.3, amp=0.055),
            ring_points(n, 1.27, 0.97, 0.305, phase=0.27, seed=5.2, amp=0.045),
            ring_points(n, 1.29, 0.985, 0.450, phase=0.36, seed=6.1, amp=0.055),
            ring_points(n, 1.18, 0.90, 0.465, phase=0.40, seed=7.2, amp=0.045),
            ring_points(n, 1.20, 0.92, 0.600, phase=0.49, seed=8.3, amp=0.050),
            ring_points(n, 1.09, 0.83, 0.615, phase=0.53, seed=9.1, amp=0.040),
            ring_points(n, 1.02, 0.78, 0.720, phase=0.62, seed=10.2, amp=0.040),
            ring_points(n, 0.91, 0.69, 0.780, phase=0.70, seed=11.4, amp=0.035),
            ring_points(n, 0.72, 0.55, 0.805, phase=0.77, seed=12.5, amp=0.030),
        ]
        band_materials = [0, 2, 1, 2, 0, 2, 1, 2, 0, 1, 0]
        moss_bands = {5, 7, 8, 9, 10}

        def mat_fn(center, normal, band, segment):
            if center.z > 0.53 and normal.z > 0.18:
                angle = math.atan2(center.y, center.x)
                if math.sin(angle * 2.0 + 0.9) > 0.15 and (segment + band) % 7 in (0, 1, 2, 4):
                    return 3
            if center.z > 0.72 and normal.z > -0.05 and band in moss_bands:
                if (segment + band * 2) % 9 in (0, 1, 5):
                    return 3
            if center.z < 0.14:
                return 2
            return band_materials[min(band, len(band_materials) - 1)]

        def top_mat(center, normal, band, segment):
            # Two contiguous moss islands, not camouflage speckle.
            if segment in (0, 1, 2):
                return 4 if segment == 1 else 3
            if segment == 7:
                return 3
            return 0 if segment % 3 else 1

        add_loft(
            b,
            rings,
            mat_fn,
            bottom_mat=2,
            top_center=(0.08, -0.02, 0.825),
            top_mat=top_mat,
            n=n,
        )
        return b, mats

    def add_scree(builder, cx, cy, radius, height, seed, materials, n=6):
        rng = random.Random(seed)
        rings = []
        for k, (factor, zfactor) in enumerate(
            ((1.0, 0.0), (0.86, 0.52), (0.45, 0.84), (0.05, 1.0))
        ):
            points = []
            phase = rng.uniform(0.0, math.pi)
            for i in range(n):
                angle = 2.0 * math.pi * i / n + phase
                wobble = 1.0 + rng.uniform(-0.16, 0.16)
                points.append(
                    (
                        cx + math.cos(angle) * radius * factor * wobble + rng.uniform(-0.015, 0.015),
                        cy + math.sin(angle) * radius * 0.82 * factor * wobble,
                        height * zfactor,
                    )
                )
            rings.append(points)

        def mat_fn(center, normal, band, segment):
            if center.z < height * 0.22:
                return materials[2]
            if normal.z > 0.45:
                return materials[1]
            return materials[0]

        top_center = (cx - radius * 0.10, cy + radius * 0.08, height)
        add_loft(
            builder,
            rings,
            mat_fn,
            bottom_mat=materials[2],
            top_center=top_center,
            top_mat=materials[1],
            n=n,
        )

    def build_cliff_spire():
        mats = [
            make_material("Sandstone", "#B18563", 0.91),
            make_material("SandstonePale", "#C09A76", 0.90),
            make_material("SandstoneDark", "#88614C", 0.93),
            make_material("Weathered", "#9A8872", 0.92),
        ]
        b = MeshBuilder()
        n = 9
        rings_spec = [
            (0.00, 1.28, 1.02, 0.00, 0.00, 0.02),
            (0.24, 1.39, 1.09, 0.02, 0.01, 0.10),
            (0.86, 1.02, 0.82, 0.07, 0.02, 0.18),
            (0.905, 1.20, 0.95, 0.075, 0.02, 0.23),
            (1.52, 0.86, 0.68, 0.12, 0.00, 0.32),
            (1.57, 1.02, 0.80, 0.125, 0.00, 0.38),
            (2.20, 0.72, 0.58, 0.17, -0.02, 0.47),
            (2.25, 0.94, 0.73, 0.175, -0.02, 0.53),
            (2.86, 0.61, 0.49, 0.23, -0.03, 0.61),
            (2.91, 0.78, 0.61, 0.235, -0.03, 0.67),
            (3.52, 0.50, 0.40, 0.30, -0.05, 0.75),
            (3.57, 0.64, 0.51, 0.305, -0.05, 0.81),
            (4.18, 0.40, 0.32, 0.37, -0.06, 0.89),
            (4.23, 0.54, 0.42, 0.375, -0.06, 0.95),
            (4.84, 0.30, 0.24, 0.45, -0.08, 1.03),
            (4.89, 0.42, 0.34, 0.455, -0.08, 1.09),
            (5.45, 0.22, 0.18, 0.52, -0.10, 1.17),
            (5.50, 0.31, 0.25, 0.525, -0.10, 1.23),
            (5.88, 0.15, 0.12, 0.57, -0.11, 1.31),
            (5.92, 0.23, 0.18, 0.575, -0.11, 1.37),
        ]
        rings = []
        for z, rx, ry, cx, cy, phase in rings_spec:
            # Base and ledge rings remain crisp; only the body wiggles.
            rings.append(
                ring_points(
                    n, rx, ry, z, phase=phase, seed=phase * 5.1 + 2.0, amp=0.105, cx=cx, cy=cy
                )
            )
        # Two deep gashes on the front-right shoulder prevent a perfectly
        # turned silhouette and read as wind-scoured fractures.
        for ring_index in (8, 9, 11, 13):
            ring = rings[ring_index]
            target_angle = -0.75
            best = min(
                range(n),
                key=lambda j: abs(
                    math.atan2(
                        math.sin(2 * math.pi * j / n + rings_spec[ring_index][5] - target_angle),
                        math.cos(2 * math.pi * j / n + rings_spec[ring_index][5] - target_angle),
                    )
                ),
            )
            x, y, z = ring[best]
            cx = rings_spec[ring_index][3]
            cy = rings_spec[ring_index][4]
            ring[best] = (cx + (x - cx) * 0.78, cy + (y - cy) * 0.78, z)

        # Hurl a few ledges further out on alternating sides.  This breaks the
        # turned-cone read of a simple tier stack.
        bulges = [
            (3, 2.35, 1.20, 0.95),
            (5, -0.25, 1.24, 0.85),
            (7, -1.35, 1.30, 0.80),
            (9, 2.75, 1.18, 0.90),
            (11, 1.15, 1.22, 0.75),
            (13, -2.25, 1.16, 0.70),
        ]
        for ring_index, target_angle, factor, spread in bulges:
            ring = rings[ring_index]
            cx = rings_spec[ring_index][3]
            cy = rings_spec[ring_index][4]
            for j, (x, y, z) in enumerate(ring):
                angle = math.atan2(y - cy, x - cx)
                delta = math.atan2(math.sin(angle - target_angle), math.cos(angle - target_angle))
                if abs(delta) < spread:
                    weight = math.cos((delta / spread) * math.pi * 0.5) ** 2
                    scale = 1.0 + (factor - 1.0) * weight
                    ring[j] = (cx + (x - cx) * scale, cy + (y - cy) * scale, z)

        body_bands = {0, 1, 3, 5, 7, 9, 11, 13, 15, 17}
        body_colors = {0: 0, 1: 1, 3: 1, 5: 3, 7: 0, 9: 1, 11: 3, 13: 0, 15: 1, 17: 3}

        def mat_fn(center, normal, band, segment):
            if band in body_bands:
                return body_colors.get(band, 0)
            return 2 if (band // 2) % 3 else 3

        add_loft(
            b,
            rings,
            mat_fn,
            bottom_mat=2,
            top_center=(0.62, -0.13, 6.00),
            top_mat=1,
            n=n,
        )

        # A lower secondary needle forks out to the left, giving the landmark
        # a memorable silhouette from the path rather than a simple cone.
        sn = 6
        secondary_specs = [
            (0.00, -1.00, -0.14, 0.66, 0.51, 0.03),
            (0.20, -1.08, -0.16, 0.59, 0.46, 0.15),
            (0.82, -1.20, -0.19, 0.46, 0.36, 0.27),
            (0.88, -1.25, -0.20, 0.51, 0.40, 0.34),
            (1.45, -1.35, -0.22, 0.35, 0.28, 0.45),
            (1.52, -1.40, -0.23, 0.40, 0.32, 0.51),
            (2.08, -1.52, -0.25, 0.27, 0.21, 0.61),
            (2.16, -1.56, -0.26, 0.31, 0.25, 0.67),
            (2.78, -1.68, -0.28, 0.19, 0.15, 0.76),
            (2.85, -1.72, -0.29, 0.23, 0.18, 0.82),
            (3.48, -1.84, -0.31, 0.12, 0.09, 0.90),
            (3.56, -1.88, -0.32, 0.075, 0.06, 0.96),
        ]
        secondary_rings = []
        for z, cx, cy, rx, ry, phase in secondary_specs:
            secondary_rings.append(
                ring_points(
                    sn, rx, ry, z, phase=phase, seed=phase * 7.3 + 19.0, amp=0.12, cx=cx, cy=cy
                )
            )

        def secondary_mat(center, normal, band, segment):
            if band in (2, 4, 6, 8, 10):
                return 3 if band % 4 else 2
            return 1 if band % 4 == 1 else 0

        add_loft(
            b,
            secondary_rings,
            secondary_mat,
            bottom_mat=2,
            top_center=(-2.08, -0.35, 4.20),
            top_mat=3,
            n=sn,
        )

        # Larger broken slabs and boulders around the foot sell the canyon
        # scale and keep the bottom from looking like a clean cut.
        scree = [
            (-1.72, -0.72, 0.62, 0.52, 1.2),
            (1.72, -0.65, 0.54, 0.40, 2.6),
            (-1.22, 0.98, 0.46, 0.31, 3.9),
            (1.82, 0.46, 0.42, 0.31, 5.1),
            (-0.25, -1.52, 0.58, 0.46, 6.4),
            (-1.78, 0.12, 0.36, 0.25, 7.6),
            (1.60, 1.05, 0.45, 0.28, 8.8),
            (0.92, -1.12, 0.34, 0.22, 10.1),
            (-2.05, -0.20, 0.30, 0.37, 11.6),
        ]
        for i, (x, y, radius, height, seed) in enumerate(scree):
            add_scree(b, x, y, radius, height, seed, [0, 1, 2, 3], n=5 + (i % 2))
        return b, mats

    def _add_arch_block(b, x_inner_bottom, x_outer_bottom, x_inner_top, x_outer_top, z0, z1, yf, yb, mat):
        """A closed layered block in the XZ plane extruded along Y.

        The front face is a trapezoid so the arch curve remains legible while
        every stratum still reads as a separate horizontal bed.
        """
        if abs(x_outer_top - x_inner_top) < 1e-4 and abs(x_outer_bottom - x_inner_bottom) < 1e-4:
            return
        obf = b.v(x_outer_bottom, yf, z0)
        ibf = b.v(x_inner_bottom, yf, z0)
        itf = b.v(x_inner_top, yf, z1)
        otf = b.v(x_outer_top, yf, z1)
        obb = b.v(x_outer_bottom, yb, z0)
        ibb = b.v(x_inner_bottom, yb, z0)
        itb = b.v(x_inner_top, yb, z1)
        otb = b.v(x_outer_top, yb, z1)
        b.face((obf, ibf, itf, otf), mat)  # front
        b.face((obb, otb, itb, ibb), mat)  # back
        b.face((obf, obb, ibb, ibf), mat)  # bottom
        b.face((otf, itf, itb, otb), mat)  # top
        b.face((obf, otf, otb, obb), mat)  # outer cheek
        b.face((ibf, ibb, itb, itf), mat)  # tunnel cheek

    def _add_arch_cap_block(b, x_left_bottom, x_right_bottom, x_left_top, x_right_top, z0, z1, yf, yb, mat):
        lbf = b.v(x_left_bottom, yf, z0)
        rbf = b.v(x_right_bottom, yf, z0)
        rtf = b.v(x_right_top, yf, z1)
        ltf = b.v(x_left_top, yf, z1)
        lbb = b.v(x_left_bottom, yb, z0)
        rbb = b.v(x_right_bottom, yb, z0)
        rtb = b.v(x_right_top, yb, z1)
        ltb = b.v(x_left_top, yb, z1)
        b.face((lbf, rbf, rtf, ltf), mat)
        b.face((lbb, ltb, rtb, rbb), mat)
        b.face((lbf, lbb, rbb, rbf), mat)
        b.face((ltf, rtf, rtb, ltb), mat)
        b.face((lbf, ltf, ltb, lbb), mat)
        b.face((rbf, rbb, rtb, rtf), mat)

    def build_sandstone_arch():
        mats = [
            make_material("SandstoneLight", "#C5A17F", 0.9),
            make_material("Sandstone", "#B68B69", 0.91),
            make_material("SandstoneWarm", "#A77B5C", 0.92),
            make_material("SandstoneDark", "#906A50", 0.93),
        ]
        b = MeshBuilder()
        rng = random.Random(1874)

        outer_radius = 3.50
        inner_radius = 2.30
        spring_z = 3.00
        crown_z = spring_z + inner_radius  # 5.30
        top_z = 6.50

        def outer_half(z):
            if z <= spring_z:
                return outer_radius
            left = max(0.0, outer_radius * outer_radius - (z - spring_z) ** 2)
            return math.sqrt(left)

        def inner_half(z):
            if z <= spring_z:
                return inner_radius
            if z >= crown_z:
                return 0.0
            return math.sqrt(max(0.0, inner_radius * inner_radius - (z - spring_z) ** 2))

        z_bounds = [
            0.00,
            0.48,
            1.02,
            1.55,
            2.10,
            2.62,
            3.00,
            3.46,
            3.90,
            4.32,
            4.70,
            5.02,
            5.30,
            5.80,
            6.18,
            top_z,
        ]
        palette = [0, 0, 1, 1, 2, 0, 1, 2, 0, 3, 1, 0, 2, 0, 1]

        for course in range(len(z_bounds) - 1):
            z0 = z_bounds[course]
            z1 = z_bounds[course + 1]
            if z1 <= 0.0:
                continue
            # Each course is its own thin slab, giving a pronounced horizontal
            # sedimentary bed.  Subtle independent jitter creates natural lips
            # without turning the silhouette into masonry.
            jitter = rng.uniform(-0.026, 0.026)
            depth = 2.18 + rng.uniform(-0.09, 0.09)
            yf = -depth * 0.5 + rng.uniform(-0.040, 0.040)
            yb = depth * 0.5 + rng.uniform(-0.040, 0.040)
            mat = palette[min(course, len(palette) - 1)]

            outer_b = max(0.30, outer_half(z0) + jitter - (0.02 if course == 0 else 0.0))
            outer_t = max(0.20, outer_half(z1) + jitter)
            if z1 >= top_z - 0.02:
                outer_t = 0.18
            has_hole = z0 < crown_z - 0.015

            if has_hole:
                inner_b = max(0.04, inner_half(z0) - 0.015 + rng.uniform(-0.015, 0.015))
                inner_t = max(0.02, inner_half(z1) - 0.01 + rng.uniform(-0.012, 0.012))
                # Keep the opening open on all courses below the crown.
                _add_arch_block(
                    b,
                    -inner_b,
                    -outer_b,
                    -inner_t,
                    -outer_t,
                    z0,
                    z1,
                    yf,
                    yb,
                    mat,
                )
                _add_arch_block(
                    b,
                    inner_b,
                    outer_b,
                    inner_t,
                    outer_t,
                    z0,
                    z1,
                    yf,
                    yb,
                    mat,
                )
            else:
                left_b = -outer_b
                right_b = outer_b
                left_t = -outer_t
                right_t = outer_t
                # Slight asymmetry on the solid cap.
                left_b -= rng.uniform(0.0, 0.035)
                right_t += rng.uniform(0.0, 0.025)
                _add_arch_cap_block(b, left_b, right_b, left_t, right_t, z0, z1, yf, yb, mat)

        return b, mats

    def build_floating_rock():
        mats = [
            make_material("Stone", "#76716E", 0.91),
            make_material("StoneLight", "#8C8580", 0.89),
            make_material("StoneDark", "#565251", 0.94),
            make_material("Grass", "#7E9B5D", 0.95),
            make_material("Moss", "#5F7D50", 0.95),
        ]
        b = MeshBuilder()
        n = 9
        rings = [
            ring_points(n, 0.34, 0.27, 1.00, phase=0.08, seed=1.0, amp=0.15, z_amp=0.02),
            ring_points(n, 0.59, 0.45, 1.22, phase=0.18, seed=2.2, amp=0.14, z_amp=0.03),
            ring_points(n, 0.88, 0.69, 1.47, phase=0.32, seed=3.4, amp=0.12, z_amp=0.04),
            ring_points(n, 1.22, 0.95, 1.73, phase=0.44, seed=4.6, amp=0.10, z_amp=0.05),
            ring_points(n, 1.55, 1.22, 2.00, phase=0.58, seed=5.9, amp=0.08, z_amp=0.05),
            ring_points(n, 1.82, 1.36, 2.22, phase=0.70, seed=7.0, amp=0.065, z_amp=0.035),
            ring_points(n, 1.96, 1.45, 2.40, phase=0.82, seed=8.2, amp=0.055, z_amp=0.02),
            ring_points(n, 2.00, 1.46, 2.52, phase=0.93, seed=9.1, amp=0.050, z_amp=0.01),
            ring_points(n, 1.84, 1.33, 2.56, phase=1.05, seed=10.3, amp=0.055, z_amp=0.0),
            ring_points(n, 0.92, 0.70, 2.605, phase=1.16, seed=11.5, amp=0.045, z_amp=0.0),
        ]

        def top_patch(angle):
            # Small scattered green islands, not a lawn: the brief asks for
            # only a little grass and moss on the stone crown.
            return (
                math.sin(angle * 2.0 + 1.1) > 0.68
                or math.sin(angle * 3.0 - 0.7) > 0.86
            )

        def mat_fn(center, normal, band, segment):
            if center.z > 2.47 and normal.z > 0.23:
                angle = math.atan2(center.y, center.x)
                if top_patch(angle) and segment % 2 == 0:
                    return 3 if (segment + band) % 4 else 4
                return 0 if segment % 3 else 1
            if center.z > 2.30 and normal.z > 0.05 and (segment + band) % 7 == 0:
                return 4
            if center.z < 1.20 or normal.z < -0.42:
                return 2
            if normal.z > 0.38 and (segment + band) % 7 == 0:
                return 1
            if (segment + band) % 19 == 0:
                return 1
            return 0

        def top_mat(center, normal, band, segment):
            angle = math.atan2(center.y, center.x)
            if segment == 1:
                return 3
            if segment == 5:
                return 4
            if top_patch(angle) and segment % 2 == 0:
                return 3
            return 0 if segment % 3 else 1

        add_loft(
            b,
            rings,
            mat_fn,
            bottom_mat=2,
            top_center=(0.12, -0.08, 2.64),
            top_mat=top_mat,
            n=n,
        )

        shards = [
            ((0.02, -0.02, 1.45), (0.00, -0.04, 0.00), 0.48, 0.25, 4.0, 2),
            ((-0.55, -0.34, 1.25), (-0.95, -0.90, 0.28), 0.34, 0.14, 8.1, 0),
            ((0.70, -0.10, 1.25), (1.10, -0.25, 0.25), 0.36, 0.14, 9.7, 2),
            ((0.20, 0.55, 1.15), (0.30, 0.95, 0.42), 0.30, 0.11, 13.6, 0),
            ((-0.70, 0.20, 1.10), (-1.15, 0.30, 0.50), 0.30, 0.11, 15.2, 2),
            ((0.10, -0.65, 1.18), (0.25, -1.10, 0.55), 0.28, 0.10, 17.8, 0),
            ((-0.30, 0.45, 0.98), (-0.55, 0.72, 0.34), 0.23, 0.08, 19.4, 1),
        ]
        for top, tip, base_radius, mid_radius, seed, mat in shards:
            add_hanging_shard(b, top, tip, base_radius, mid_radius, mat, seed, n=5)

        # A handful of emergent grass tufts, embedded just below the crown.
        for x, y, seed, scale in [
            (-1.20, -0.28, 21.0, 1.85),
            (0.55, 0.55, 22.1, 1.70),
            (1.05, -0.36, 23.2, 1.45),
            (-0.25, -1.00, 24.3, 1.45),
            (-0.35, 0.55, 25.4, 1.35),
            (0.20, -0.25, 26.5, 1.25),
        ]:
            add_grass_tuft(b, x, y, 2.54, seed, 3, scale)
        return b, mats

    def add_crystal(builder, base, height, radius, lean, rotation, body_mat, shadow_mat, seed, n=6):
        base = vec(base)
        axis = Vector((lean[0], lean[1], 1.0)).normalized()
        helper = axis.cross(Vector((0.0, 1.0, 0.0)))
        if helper.length < 1e-6:
            helper = axis.cross(Vector((1.0, 0.0, 0.0)))
        helper.normalize()
        helper2 = axis.cross(helper).normalized()
        rng = random.Random(seed)
        levels = [
            (0.00, radius * 0.72),
            (0.13, radius),
            (0.72, radius * 0.92),
            (0.86, radius * 0.58),
        ]
        ring_ids = []
        for level, t, r in ((0, 0.0, radius * 0.72), (1, 0.13, radius), (2, 0.72, radius * 0.92), (3, 0.86, radius * 0.58)):
            ring = []
            phase = rotation + 0.06 * math.sin(seed)
            for i in range(n):
                angle = 2.0 * math.pi * i / n + phase + 0.04 * level
                wobble = 1.0 + rng.uniform(-0.08, 0.08)
                p = (
                    base
                    + axis * (height * t)
                    + helper * (math.cos(angle) * r * wobble)
                    + helper2 * (math.sin(angle) * r * wobble)
                )
                ring.append(builder.v(p))
            ring_ids.append(ring)
        cap = builder.v(base - axis * (height * 0.015))
        # Root cap is buried inside the rock.
        for i in range(n):
            j = (i + 1) % n
            builder.face((cap, ring_ids[0][j], ring_ids[0][i]), body_mat)
        for level in range(3):
            for i in range(n):
                j = (i + 1) % n
                material = shadow_mat if (i == 1 and level < 2) else body_mat
                builder.face(
                    (
                        ring_ids[level][i],
                        ring_ids[level][j],
                        ring_ids[level + 1][j],
                        ring_ids[level + 1][i],
                    ),
                    material,
                )
        shoulder = ring_ids[3]
        tip = builder.v(base + axis * height)
        for i in range(n):
            j = (i + 1) % n
            material = shadow_mat if i == 1 else body_mat
            builder.face((shoulder[i], shoulder[j], tip), material)

    def build_crystal_cluster():
        mats = [
            make_material("Rock", "#3F3B50", 0.9),
            make_material("RockEdge", "#514B64", 0.87),
            make_material(
                "CrystalShadow",
                "#544D6B",
                0.82,
                0.0,
                emission_hex="#6A5C97",
                emission_strength=1.15,
            ),
            make_material(
                "Glow_Purple",
                "#352A52",
                0.82,
                0.0,
                emission_hex="#5B3EAD",
                emission_strength=2.5,
            ),
            make_material(
                "Glow_Cyan",
                "#173E3E",
                0.82,
                0.0,
                emission_hex="#1FB7AE",
                emission_strength=2.5,
            ),
        ]
        b = MeshBuilder()
        n = 8
        rings = [
            ring_points(n, 0.82, 0.68, 0.00, phase=0.06, seed=1.2, amp=0.12),
            ring_points(n, 0.86, 0.72, 0.12, phase=0.18, seed=2.3, amp=0.13, z_amp=0.015),
            ring_points(n, 0.61, 0.51, 0.31, phase=0.35, seed=3.7, amp=0.11, z_amp=0.025),
            ring_points(n, 0.44, 0.37, 0.45, phase=0.52, seed=4.9, amp=0.10, z_amp=0.018),
        ]

        def mat_fn(center, normal, band, segment):
            if normal.z > 0.4 and center.z > 0.25:
                return 1
            if center.z < 0.10:
                return 0
            return 0 if (segment + band) % 5 else 1

        add_loft(
            b,
            rings,
            mat_fn,
            bottom_mat=0,
            top_center=(-0.03, 0.02, 0.48),
            top_mat=1,
            n=n,
        )

        # Clustered crystals: two purple heroes, three cyan companions, two
        # small fillers.  Their roots are buried in the rocky pedestal.
        crystals = [
            ((-0.05, 0.02, 0.29), 1.88, 0.20, (0.10, -0.08), 0.00, 3, 2, 31.1),
            ((0.33, -0.22, 0.28), 1.48, 0.16, (0.20, -0.10), 0.55, 4, 2, 32.3),
            ((-0.38, -0.22, 0.26), 1.20, 0.145, (-0.24, 0.10), 0.20, 3, 2, 33.4),
            ((0.30, 0.30, 0.25), 1.30, 0.14, (0.25, 0.16), 0.83, 4, 2, 34.5),
            ((-0.44, 0.28, 0.24), 0.88, 0.115, (-0.22, 0.22), 0.36, 3, 2, 35.6),
            ((0.08, 0.43, 0.22), 0.68, 0.10, (0.12, 0.25), 0.68, 4, 2, 36.7),
            ((0.55, 0.02, 0.22), 0.55, 0.08, (0.30, -0.04), 1.02, 4, 2, 37.8),
            ((-0.58, -0.02, 0.22), 0.46, 0.075, (-0.28, -0.05), 0.42, 3, 2, 38.9),
        ]
        for base, height, radius, lean, rotation, body_mat, shadow_mat, seed in crystals:
            add_crystal(
                b,
                base,
                height,
                radius,
                lean,
                rotation,
                body_mat,
                shadow_mat,
                seed,
                n=6,
            )
        return b, mats

    def build_stump():
        mats = [
            make_material("Bark", "#5D4A3E", 0.94),
            make_material("WoodLight", "#C4A378", 0.88),
            make_material("WoodDark", "#987751", 0.9),
            make_material("Moss", "#6E8B5A", 0.95),
            make_material("BarkDark", "#49382F", 0.95),
        ]
        b = MeshBuilder()
        n = 10
        rings = [
            ring_points(n, 0.53, 0.48, 0.00, phase=0.02, seed=1.0, amp=0.17),
            ring_points(n, 0.49, 0.45, 0.10, phase=0.08, seed=2.2, amp=0.15),
            ring_points(n, 0.41, 0.38, 0.26, phase=0.19, seed=3.4, amp=0.11),
            ring_points(n, 0.355, 0.33, 0.44, phase=0.28, seed=4.6, amp=0.09),
            ring_points(n, 0.335, 0.315, 0.64, phase=0.36, seed=5.8, amp=0.08),
            ring_points(n, 0.335, 0.315, 0.82, phase=0.45, seed=6.9, amp=0.08),
            ring_points(n, 0.32, 0.30, 0.955, phase=0.52, seed=8.1, amp=0.075),
            ring_points(n, 0.34, 0.315, 1.00, phase=0.58, seed=9.4, amp=0.06),
        ]

        def bark_mat(center, normal, band, segment):
            if center.z < 0.22 and (segment + band * 2) % 8 in (0, 2, 5):
                return 3
            if center.z < 0.10:
                return 4
            if center.z > 0.76 and normal.y < -0.1 and (segment + band) % 9 in (0, 1, 2):
                return 3
            if (segment + band * 3) % 19 == 0:
                return 4
            return 0

        add_loft(
            b,
            rings,
            bark_mat,
            bottom_mat=4,
            top_mat=0,
            n=n,
        )

        # Top face: concentric growth rings, a hair above the bark cap.
        rng = random.Random(62.1)
        top_z = 1.002
        center_x, center_y = 0.015, -0.01
        ring_radii = [0.065, 0.115, 0.175, 0.235, 0.285, 0.315]
        cap_rings = []
        for ring_index, radius in enumerate(ring_radii):
            points = []
            for i in range(n):
                angle = 2.0 * math.pi * i / n + 0.06 + ring_index * 0.022
                wobble = 1.0 + 0.035 * math.sin(3.0 * angle + ring_index * 1.7)
                # Slightly imperfect growth rings, never radically deformed.
                points.append(
                    (
                        center_x + math.cos(angle) * radius * wobble,
                        center_y + math.sin(angle) * radius * wobble * 0.95,
                        top_z,
                    )
                )
            cap_rings.append([b.v(p) for p in points])
        pith = b.v(center_x - 0.012, center_y + 0.006, top_z - 0.002)
        for i in range(n):
            j = (i + 1) % n
            b.face((pith, cap_rings[0][i], cap_rings[0][j]), 2)
        ring_materials = [1, 2, 1, 2, 1]
        for ring_index in range(len(cap_rings) - 1):
            inner = cap_rings[ring_index]
            outer = cap_rings[ring_index + 1]
            for i in range(n):
                j = (i + 1) % n
                material = ring_materials[ring_index]
                if ring_index == len(cap_rings) - 2 and i in (5, 6):
                    material = 3
                b.face((inner[i], outer[i], outer[j], inner[j]), material)

        return b, mats

    def sweep_tube(builder, points, radii, sides, material_fn, cap_material, seed, twist=0.35):
        rng = random.Random(seed)
        point_vecs = [vec(p) for p in points]
        rings = []
        tangents = []
        for i, p in enumerate(point_vecs):
            if i == 0:
                tangent = point_vecs[1] - p
            elif i == len(point_vecs) - 1:
                tangent = p - point_vecs[-2]
            else:
                tangent = point_vecs[i + 1] - point_vecs[i - 1]
            if tangent.length < 1e-8:
                tangent = Vector((1.0, 0.0, 0.0))
            tangents.append(tangent.normalized())
        for i, (p, tangent, radius) in enumerate(zip(point_vecs, tangents, radii)):
            helper = tangent.cross(Vector((0.0, 0.0, 1.0)))
            if helper.length < 1e-6:
                helper = tangent.cross(Vector((0.0, 1.0, 0.0)))
            helper.normalize()
            helper2 = helper.cross(tangent).normalized()
            phase = twist * i / max(1, len(point_vecs) - 1)
            ring = []
            for k in range(sides):
                angle = 2.0 * math.pi * k / sides + phase
                wobble = 1.0 + rng.uniform(-0.055, 0.055)
                ring.append(
                    p
                    + helper * (math.cos(angle) * radius * wobble)
                    + helper2 * (math.sin(angle) * radius * wobble)
                )
            rings.append(ring)

        # Build rings / side faces.
        ring_ids = []
        for ring in rings:
            ring_ids.append([builder.v(p) for p in ring])
        for band in range(len(ring_ids) - 1):
            for i in range(sides):
                j = (i + 1) % sides
                pa = rings[band][i]
                pb = rings[band][j]
                pc = rings[band + 1][j]
                pd = rings[band + 1][i]
                n1 = _triangle_normal(pa, pb, pc)
                c1 = (pa + pb + pc) / 3.0
                n2 = _triangle_normal(pa, pc, pd)
                c2 = (pa + pc + pd) / 3.0
                builder.face(
                    (ring_ids[band][i], ring_ids[band][j], ring_ids[band + 1][j]),
                    material_fn(c1, n1),
                )
                builder.face(
                    (ring_ids[band][i], ring_ids[band + 1][j], ring_ids[band + 1][i]),
                    material_fn(c2, n2),
                )
        # Shallow, faceted end caps: water-worn rather than sawn.
        start_center = point_vecs[0] - tangents[0] * 0.025
        start_idx = builder.v(start_center)
        for i in range(sides):
            j = (i + 1) % sides
            builder.face((start_idx, ring_ids[0][j], ring_ids[0][i]), cap_material)
        end_center = point_vecs[-1] + tangents[-1] * 0.025
        end_idx = builder.v(end_center)
        for i in range(sides):
            j = (i + 1) % sides
            builder.face((end_idx, ring_ids[-1][i], ring_ids[-1][j]), cap_material)

    def build_driftwood():
        mats = [
            make_material("Driftwood", "#A4A6A0", 0.91),
            make_material("DriftwoodDark", "#7A7C77", 0.94),
            make_material("DriftwoodCut", "#C2C4BD", 0.87),
        ]
        b = MeshBuilder()
        main_points = [
            (-1.10, -0.04, 0.180),
            (-0.86, 0.07, 0.215),
            (-0.52, 0.00, 0.245),
            (-0.12, -0.11, 0.235),
            (0.28, 0.02, 0.265),
            (0.66, 0.17, 0.250),
            (0.94, 0.11, 0.215),
            (1.10, 0.02, 0.180),
        ]
        main_radii = [0.095, 0.150, 0.180, 0.190, 0.185, 0.158, 0.118, 0.103]

        def drift_mat(center, normal):
            if normal.z < -0.34:
                return 1
            if normal.z < -0.08 and center.z < 0.17:
                return 1
            # Intermittent water staining / knots along the silvered bark.
            # Keep the top dry and pale; the darker streaks sit on the cheeks.
            stripe = (
                math.sin(center.x * 8.3 + center.y * 5.1 + center.z * 9.7)
                + 0.55 * math.sin(center.x * 14.1 - center.z * 6.7 + 0.8)
            )
            if normal.z < 0.38 and stripe > 0.62:
                return 1
            if normal.z > 0.58 and center.z > 0.30:
                return 0
            return 0

        sweep_tube(
            b,
            main_points,
            main_radii,
            7,
            drift_mat,
            2,
            seed=71.3,
            twist=0.55,
        )
        branches = [
            (
                [
                    (-0.52, 0.01, 0.27),
                    (-0.66, -0.18, 0.42),
                    (-0.78, -0.34, 0.60),
                    (-0.84, -0.40, 0.74),
                    (-0.80, -0.36, 0.85),
                ],
                [0.120, 0.095, 0.065, 0.035, 0.012],
                6,
                72.8,
            ),
            (
                [(0.31, 0.04, 0.28), (0.47, 0.24, 0.37), (0.60, 0.36, 0.44), (0.71, 0.42, 0.47)],
                [0.085, 0.060, 0.030, 0.012],
                5,
                74.2,
            ),
            (
                [(0.91, 0.09, 0.22), (1.04, -0.06, 0.30), (1.11, -0.12, 0.34)],
                [0.070, 0.040, 0.012],
                5,
                75.6,
            ),
        ]
        for points, radii, sides, seed in branches:
            sweep_tube(b, points, radii, sides, drift_mat, 2, seed=seed, twist=0.3)
        return b, mats

    # -----------------------------------------------------------------------
    # Export / preview
    # -----------------------------------------------------------------------

    def setup_preview_scene():
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 24
        scene.cycles.use_adaptive_sampling = False
        scene.cycles.use_denoising = True
        scene.cycles.max_bounces = 4
        scene.cycles.diffuse_bounces = 2
        scene.cycles.glossy_bounces = 2
        scene.cycles.transmission_bounces = 0
        scene.cycles.volume_bounces = 0
        scene.render.resolution_x = 512
        scene.render.resolution_y = 512
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"
        scene.render.image_settings.compression = 15
        scene.render.film_transparent = False
        scene.render.use_file_extension = True
        scene.render.filepath = ""
        scene.unit_settings.system = "METRIC"
        scene.unit_settings.scale_length = 1.0
        scene.unit_settings.length_unit = "METERS"
        try:
            scene.view_settings.view_transform = "AgX"
            scene.view_settings.look = "AgX - Medium High Contrast"
        except Exception:
            scene.view_settings.view_transform = "AgX"
        scene.view_settings.exposure = 0.12

        world = bpy.data.worlds.new("RocksPreviewWorld")
        world.use_nodes = True
        scene.world = world
        background = world.node_tree.nodes.get("Background")
        background.inputs["Color"].default_value = srgb("#D9CFBE")
        background.inputs["Strength"].default_value = 0.42

        ground_mat = make_material("PreviewGround", "#D4C9B6", 0.95)
        ground_mesh = bpy.data.meshes.new("PreviewGround")
        half = 800.0
        ground_mesh.from_pydata(
            [(-half, -half, 0.0), (half, -half, 0.0), (half, half, 0.0), (-half, half, 0.0)],
            [],
            [(0, 1, 2, 3)],
        )
        ground_mesh.materials.append(ground_mat)
        ground = bpy.data.objects.new("PreviewGround", ground_mesh)
        scene.collection.objects.link(ground)
        ground.location.z = -0.010

        sun_specs = [
            ("Key_Warm", (1.25, 1.55, -2.30), "#FFE1BD", 2.7, 0.16),
            ("Fill_Cool", (-1.75, 1.10, -1.10), "#C6DDE8", 0.75, 0.45),
            ("Rim_Warm", (1.20, -1.85, -1.55), "#FFE8C8", 1.35, 0.28),
            # A very soft sky bounce from below keeps torn undersides and
            # arch intradoses from crushing to black.
            ("Bounce_Cool", (0.22, -0.18, 1.00), "#B9CFDC", 0.30, 0.70),
        ]
        for name, travel, color_hex, energy, angle in sun_specs:
            data = bpy.data.lights.new(name=name, type="SUN")
            data.color = srgb(color_hex)[:3]
            data.energy = energy
            data.angle = angle
            light = bpy.data.objects.new(name, data)
            scene.collection.objects.link(light)
            direction = vec(travel).normalized()
            light.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

        camera_data = bpy.data.cameras.new("PreviewCamera")
        camera_data.lens = 50.0
        camera_data.sensor_width = 36.0
        camera_data.clip_start = 0.02
        camera_data.clip_end = 300.0
        camera = bpy.data.objects.new("PreviewCamera", camera_data)
        scene.collection.objects.link(camera)
        scene.camera = camera
        return {"ground": ground, "camera": camera}

    def frame_and_render(obj, name, rig, camera_dir, floor_z):
        scene = bpy.context.scene
        ground = rig["ground"]
        camera = rig["camera"]
        ground.location.z = floor_z
        min_b, max_b = mesh_bounds(obj)
        center = Vector(
            (
                (min_b[0] + max_b[0]) * 0.5,
                (min_b[1] + max_b[1]) * 0.5,
                (min_b[2] + max_b[2]) * 0.5,
            )
        )
        radius = max(
            (max_b[0] - min_b[0]) * 0.5,
            (max_b[1] - min_b[1]) * 0.5,
            (max_b[2] - min_b[2]) * 0.5,
        )
        radius = max(radius, 0.40)
        # Keep the top frame ray below the floor horizon: the preview must stay
        # on the warm paper backdrop, never on the world colour.  A generous
        # 23-degree elevation also reads as a proper 3/4 asset turntable view.
        dir_x, dir_y, dir_z = camera_dir
        horizontal = math.hypot(dir_x, dir_y)
        min_z = math.tan(math.radians(23.0)) * horizontal
        dir_z = max(dir_z, min_z)
        direction = Vector((dir_x, dir_y, dir_z)).normalized()
        distance = radius * 3.25
        camera.location = center + direction * distance
        look_at = center
        camera.rotation_euler = (look_at - camera.location).to_track_quat("-Z", "Y").to_euler()
        # A 50 mm lens on a 36 mm sensor gives a comfortable 3/4 framing;
        # the extra distance leaves breathing room for the floor shadow.
        scene.render.filepath = str(PREVIEW_DIR / f"{name}.png")
        bpy.ops.render.render(write_still=True)

    def export_glb(obj, name):
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        filepath = ASSET_DIR / f"{name}.glb"
        bpy.ops.export_scene.gltf(
            filepath=str(filepath),
            export_format="GLB",
            use_selection=True,
            export_apply=True,
            export_yup=True,
            export_animations=False,
        )
        obj.select_set(False)
        return filepath

    def flatten_low_base(obj, threshold):
        """Sink a few lowest vertices to Z=0 so a lying prop has real contact."""
        for vertex in obj.data.vertices:
            if vertex.co.z < threshold:
                vertex.co.z = 0.0
        obj.data.update()
        for polygon in obj.data.polygons:
            polygon.use_smooth = False

    def cleanup_asset(obj, materials):
        mesh = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        for mat in materials:
            if mat.users == 0:
                bpy.data.materials.remove(mat)

    def build_one(name):
        builders = {
            "rock_a": build_rock_a,
            "rock_b": build_rock_b,
            "rock_c": build_rock_c,
            "cliff_spire": build_cliff_spire,
            "sandstone_arch": build_sandstone_arch,
            "floating_rock": build_floating_rock,
            "crystal_cluster": build_crystal_cluster,
            "stump": build_stump,
            "driftwood": build_driftwood,
        }
        builder, materials = builders[name]()
        obj = create_object(name, builder, materials)
        targets = ASSET_TARGETS[name]
        finalize_asset(obj, target_x=targets.get("target_x"), target_z=targets.get("target_z"))
        if name == "driftwood":
            flatten_low_base(obj, 0.040)
        obj.data.name = name
        return obj, materials

    def main_blender():
        ASSET_DIR.mkdir(parents=True, exist_ok=True)
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        rig = setup_preview_scene()
        started_all = time.time()
        manifest = []
        for index, name in enumerate(ASSET_ORDER, start=1):
            started = time.time()
            print(f"\n[{index}/{len(ASSET_ORDER)}] building {name} ...", flush=True)
            obj, materials = build_one(name)
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            stats = {
                "name": name,
                "file": f"assets/models/rocks/{name}.glb",
                "preview": f"assets/previews/rocks/{name}.png",
                "bounds": bounds_dict(obj),
                "tris": tri_count(obj),
                "verts": len(obj.data.vertices),
                "materials": [mat.name for mat in materials],
                "tags": ASSET_META[name]["tags"],
                "suggested_use": ASSET_META[name]["use"],
            }
            print(f"  bounds={stats['bounds']} tris={stats['tris']} verts={stats['verts']}", flush=True)
            export_glb(obj, name)
            floor_z = -1.15 if name == "floating_rock" else -0.010
            frame_and_render(obj, name, rig, ASSET_META[name]["camera"], floor_z)
            manifest.append(stats)
            cleanup_asset(obj, materials)
            print(f"  done in {time.time() - started:.1f}s", flush=True)

        with MANIFEST_PATH.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
        print(
            f"\nAll {len(manifest)} rocks exported. Total tris: "
            f"{sum(item['tris'] for item in manifest)}. "
            f"Elapsed: {time.time() - started_all:.1f}s",
            flush=True,
        )
        print(f"Manifest: {MANIFEST_PATH}", flush=True)
        print("Now run: python tools/blender/rocks.py --sheet", flush=True)


# ---------------------------------------------------------------------------
# Contact sheet (regular Python + Pillow)
# ---------------------------------------------------------------------------


def build_contact_sheet():
    from PIL import Image, ImageDraw, ImageFont

    if not MANIFEST_PATH.exists():
        raise SystemExit(f"manifest missing: {MANIFEST_PATH}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_name = {item["name"]: item for item in manifest}

    font_path = PROJECT_ROOT / "assets" / "fonts" / "Marcellus-Regular.ttf"
    if not font_path.exists():
        font_path = None

    def font(size):
        if font_path:
            return ImageFont.truetype(str(font_path), size)
        return ImageFont.load_default()

    title_font = font(44)
    sub_font = font(20)
    label_font = font(27)
    meta_font = font(17)
    small_font = font(15)
    card_title_font = font(30)
    card_font = font(19)

    bg = (236, 226, 210)
    tile_bg = (246, 238, 224)
    tile_outline = (200, 185, 163)
    text_dark = (73, 58, 45)
    text_mid = (113, 96, 78)
    accent = (121, 91, 67)

    cols = 4
    rows = 3
    margin = 28
    gap = 20
    image_size = 512
    pad = 16
    label_height = 66
    cell_w = image_size + pad * 2
    cell_h = image_size + pad + label_height
    header_h = 112
    sheet_w = margin * 2 + cols * cell_w + (cols - 1) * gap
    sheet_h = header_h + margin + rows * cell_h + (rows - 1) * gap + margin
    sheet = Image.new("RGB", (sheet_w, sheet_h), bg)
    draw = ImageDraw.Draw(sheet)

    draw.text((margin + 10, 26), "LANTERN ISLES  /  ROCKS & NATURAL FORMS", font=title_font, fill=text_dark)
    draw.text(
        (margin + 12, 77),
        "9 low-poly assets  |  4 chapters  |  flat shading  |  origin at base centre  |  facing -Y",
        font=sub_font,
        fill=text_mid,
    )
    draw.line((margin, header_h - 10, sheet_w - margin, header_h - 10), fill=tile_outline, width=2)

    for index in range(cols * rows):
        row = index // cols
        col = index % cols
        x = margin + col * (cell_w + gap)
        y = header_h + row * (cell_h + gap)
        draw.rounded_rectangle(
            (x, y, x + cell_w, y + cell_h),
            radius=8,
            fill=tile_bg,
            outline=tile_outline,
            width=1,
        )
        if index < len(ASSET_ORDER):
            name = ASSET_ORDER[index]
            item = by_name.get(name)
            num_cards = cols * rows - len(ASSET_ORDER)
            item = by_name.get(name)
            preview_path = PREVIEW_DIR / f"{name}.png"
            image_x = x + pad
            image_y = y + pad
            if preview_path.exists():
                with Image.open(preview_path) as image:
                    image = image.convert("RGB")
                    if image.size != (image_size, image_size):
                        image = image.resize((image_size, image_size), Image.Resampling.LANCZOS)
                    sheet.paste(image, (image_x, image_y))
                    draw.rectangle(
                        (image_x, image_y, image_x + image_size - 1, image_y + image_size - 1),
                        outline=(180, 165, 144),
                        width=1,
                    )
            else:
                draw.rectangle(
                    (image_x, image_y, image_x + image_size, image_y + image_size),
                    fill=(222, 213, 198),
                    outline=tile_outline,
                )
                draw.text((image_x + 24, image_y + 24), "MISSING PREVIEW", font=label_font, fill=text_mid)

            number = f"{index + 1:02d}"
            label_y = image_y + image_size + 8
            draw.text((x + pad, label_y), f"{number}   {name}", font=label_font, fill=text_dark)
            meta = "low-poly natural prop"
            if item:
                size = item["bounds"]["size"]
                meta = (
                    f"{size[0]:.2f} x {size[1]:.2f} x {size[2]:.2f} m  |  "
                    f"{item['tris']} tris"
                )
            draw.text((x + pad + 4, label_y + 35), meta, font=meta_font, fill=text_mid)
        else:
            # The three spare cells become useful, non-repeating batch cards.
            left = x + 28
            top = y + 36
            card_number = index - len(ASSET_ORDER)
            draw.line((left, top + 48, x + cell_w - 28, top + 48), fill=tile_outline, width=2)
            if card_number == 0:
                draw.text((left, top), "BATCH NOTES", font=card_title_font, fill=accent)
                lines = [
                    "9 procedural low-poly assets",
                    "Four chapters, one quiet world",
                    "Flat shaded / Principled only",
                    "No image textures",
                    "Cycles CPU - 24 samples",
                    "GLB: Y-up, applied transforms",
                ]
                cursor = top + 72
                for line in lines:
                    draw.text((left, cursor), line, font=card_font, fill=text_mid)
                    cursor += 33
            elif card_number == 1:
                draw.text((left, top), "SPEC CHECK", font=card_title_font, fill=accent)
                lines = [
                    ("Objects", "1 mesh each"),
                    ("Shading", "flat / all faces"),
                    ("Origin", "base centre, Z=0"),
                    ("Facing", "Blender -Y"),
                    ("Materials", "Principled, no maps"),
                    ("Emission", "2.5 on Glow_*"),
                ]
                cursor = top + 72
                for key, value in lines:
                    draw.text((left, cursor), key, font=meta_font, fill=text_mid)
                    draw.text((left + 116, cursor), value, font=card_font, fill=text_dark)
                    cursor += 33
            else:
                draw.text((left, top), "CHAPTER PALETTE", font=card_title_font, fill=accent)
                chapters = [
                    ("Mossgarden", (79, 118, 91), (134, 168, 124)),
                    ("Amberreach", (221, 187, 126), (192, 124, 82)),
                    ("Frostvale", (236, 242, 239), (184, 217, 223)),
                    ("Starfall", (106, 87, 144), (114, 214, 205)),
                ]
                cursor = top + 74
                for chapter, swatch_a, swatch_b in chapters:
                    draw.rounded_rectangle(
                        (left, cursor + 2, left + 28, cursor + 24),
                        radius=3,
                        fill=swatch_a,
                        outline=(160, 145, 124),
                    )
                    draw.rounded_rectangle(
                        (left + 34, cursor + 2, left + 62, cursor + 24),
                        radius=3,
                        fill=swatch_b,
                        outline=(160, 145, 124),
                    )
                    draw.text((left + 78, cursor), chapter, font=card_font, fill=text_dark)
                    draw.text(
                        (left + 78, cursor + 25),
                        f"#{swatch_a[0]:02X}{swatch_a[1]:02X}{swatch_a[2]:02X}   "
                        f"#{swatch_b[0]:02X}{swatch_b[1]:02X}{swatch_b[2]:02X}",
                        font=small_font,
                        fill=text_mid,
                    )
                    cursor += 63
            footer = "previews 512 x 512  /  contact sheet 4 columns"
            draw.text((left, y + cell_h - 54), footer, font=small_font, fill=text_mid)

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    sheet.save(CONTACT_SHEET_PATH, format="PNG", optimize=True)
    print(f"Contact sheet: {CONTACT_SHEET_PATH} ({sheet_w}x{sheet_h})")


if __name__ == "__main__":
    if "--sheet" in sys.argv:
        build_contact_sheet()
    elif HAS_BPY:
        main_blender()
    else:
        print("This script must be run in Blender, or with --sheet under regular Python.")
