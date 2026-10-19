"""
relics.py - Lantern Isles / "奇观与遗物" batch (9 narrative assets, 3 hero landmarks)

Run (headless):
  & 'D:\\BlenderPortable\\blender-4.2.9-windows-x64\\blender.exe' -b --python tools/blender/relics.py
  ... -- --only lighthouse,sky_whale       # rebuild/re-render a subset
  ... -- --skip-render                     # build + export GLB only

Contact sheet (system python, has Pillow):
  python tools/blender/relics.py --contact

Outputs:
  assets/models/relics/<name>.glb
  assets/previews/relics/<name>.png (+ <hero>_top.png)
  assets/models/relics/manifest_relics.json
  assets/previews/relics/contact_sheet.png

Conventions: metres, flat shaded low-poly, origin as documented per asset,
front faces Blender -Y, export GLB (Y-up, apply transforms).
"""

import json
import math
import os
import random
import sys

ROOT = r"E:\GodotProjects\xiang-ting-game"
MODEL_DIR = os.path.join(ROOT, "assets", "models", "relics")
PREVIEW_DIR = os.path.join(ROOT, "assets", "previews", "relics")
CONTACT_SHEET = os.path.join(PREVIEW_DIR, "contact_sheet.png")
MANIFEST = os.path.join(MODEL_DIR, "manifest_relics.json")
FONT_DIR = os.path.join(ROOT, "assets", "fonts")

try:
    import bpy
    import bmesh
    from mathutils import Vector, Euler
    HAS_BPY = True
except Exception:  # system python -> contact sheet mode
    HAS_BPY = False


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]


def arg_value(flag, default=None):
    if flag in ARGV:
        i = ARGV.index(flag)
        if i + 1 < len(ARGV):
            return ARGV[i + 1]
    return default


ONLY = set(x for x in (arg_value("--only", "") or "").split(",") if x)
SKIP_RENDER = "--skip-render" in ARGV
CONTACT_MODE = "--contact" in ARGV
RES = int(arg_value("--res", "512"))
SAMPLES = int(arg_value("--samples", "24"))
VIEW = arg_value("--view", "AgX")


# ----------------------------------------------------------------------------
# Colour / material helpers
# ----------------------------------------------------------------------------
def _s2l(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexlin(h):
    h = h.lstrip("#")
    return (_s2l(int(h[0:2], 16)), _s2l(int(h[2:4], 16)), _s2l(int(h[4:6], 16)))


MATS = {}


def make_mat(name, hexcol, rough=0.85, metal=0.0, emit=None, es=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    col = hexlin(hexcol)
    bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit is not None and es > 0:
        ec = hexlin(emit)
        bsdf.inputs["Emission Color"].default_value = (*ec, 1.0)
        bsdf.inputs["Emission Strength"].default_value = es
    m.diffuse_color = (*col, 1.0)
    m.use_backface_culling = False
    MATS[name] = m
    return m


def init_materials():
    MATS.clear()
    # stone / earth
    make_mat("Stone", "9C9688", 0.92)
    make_mat("StoneLight", "B6AE98", 0.9)
    make_mat("StoneDark", "6C6E62", 0.94)
    make_mat("Moss", "50734F", 0.95)
    make_mat("MossLight", "6F8B5B", 0.95)
    make_mat("Gold", "C9A55C", 0.75, 0.3)
    make_mat("GoldDark", "9A7B44", 0.78, 0.3)
    # wood
    make_mat("Wood", "6A4F3C", 0.9)
    make_mat("WoodDark", "48372B", 0.92)
    make_mat("WoodLight", "86654B", 0.88)
    # paper / glow
    make_mat("PaperGlow", "C2A97C", 0.88, 0.0, "A9662D", 0.8)
    make_mat("PaperWarm", "EFDDBB", 0.86, 0.0, "C97A2E", 3.0)
    make_mat("Frame", "3A332C", 0.9)
    make_mat("Tassel", "8E4A3F", 0.9)
    make_mat("EmberCore", "6B2208", 0.8, 0.0, "8E2000", 5.0)
    make_mat("EmberShell", "A9743E", 0.75, 0.0, "7A3E12", 0.45)
    # memory shard
    make_mat("ShardStone", "4B5168", 0.9)
    make_mat("ShardStoneLight", "5C6480", 0.9)
    make_mat("ShardStoneDark", "343949", 0.92)
    make_mat("ShardGlow", "6FC9BE", 0.8, 0.0, "2E9E92", 2.0)
    make_mat("Vine", "3E5B45", 0.92)
    make_mat("LeafVine", "5E7D4E", 0.95)
    # lighthouse
    make_mat("WarmGlass", "F2B15E", 0.8, 0.0, "F2B15E", 2.6)
    make_mat("LampCore", "FFD08A", 0.75, 0.0, "FFC070", 4.0)
    make_mat("Roof", "4C4A48", 0.92)
    # whale bones / sand
    make_mat("Bone", "E7DFC9", 0.9)
    make_mat("BoneStain", "C2A878", 0.92)
    make_mat("BoneDark", "AC9874", 0.92)
    make_mat("Sand", "D2A45F", 0.95)
    make_mat("SandLight", "E0BC82", 0.95)
    make_mat("SandShadow", "B98A4E", 0.95)
    # sky whale
    make_mat("WhaleBack", "39445C", 0.88)
    make_mat("WhaleBelly", "CBD0C8", 0.9)
    make_mat("WhaleFin", "2F3A50", 0.88)
    make_mat("WhaleGroove", "B4BAB1", 0.9)
    make_mat("WhaleMouth", "232A3A", 0.9)
    make_mat("StarGold", "E6C07A", 0.78, 0.0, "E6C07A", 3.0)
    make_mat("WhaleEye", "FFD9A0", 0.75, 0.0, "FFCF8A", 5.0)
    # cloud / bird / studio
    make_mat("Cloud", "F4EDDD", 0.95, 0.0, "FFF3DC", 0.3)
    make_mat("CloudShade", "E8DBC5", 0.95, 0.0, "F2E6CE", 0.15)
    make_mat("BirdDark", "262B35", 0.92)
    make_mat("BirdBeak", "8A6A44", 0.9)
    make_mat("PreviewGround", "D9CFBD", 0.95)


# ----------------------------------------------------------------------------
# Mesh builder
# ----------------------------------------------------------------------------
class MB:
    def __init__(self):
        self.verts = []
        self.faces = []
        self.mats = []

    def add(self, verts, faces, mat):
        base = len(self.verts)
        self.verts.extend([(float(v[0]), float(v[1]), float(v[2])) for v in verts])
        if isinstance(mat, (list, tuple)):
            if len(mat) != len(faces):
                raise ValueError("material list length != face count (%d vs %d)" % (len(mat), len(faces)))
            for f, mm in zip(faces, mat):
                self.faces.append(tuple(base + i for i in f))
                self.mats.append(mm)
        else:
            fn = mat if callable(mat) else None
            for idx, f in enumerate(faces):
                self.faces.append(tuple(base + i for i in f))
                self.mats.append(fn(idx) if fn else mat)

    def add_mb(self, other):
        base = len(self.verts)
        self.verts.extend(other.verts)
        self.faces.extend(tuple(base + i for i in f) for f in other.faces)
        self.mats.extend(other.mats)

    def translate(self, dx, dy, dz):
        self.verts = [(x + dx, y + dy, z + dz) for (x, y, z) in self.verts]

    def bounds(self):
        xs = [v[0] for v in self.verts]
        ys = [v[1] for v in self.verts]
        zs = [v[2] for v in self.verts]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def build(self, name):
        used = []
        for m in self.mats:
            if m not in used:
                used.append(m)
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(self.verts, [], self.faces)
        mesh.update()
        for m in used:
            mesh.materials.append(MATS[m])
        for p, m in zip(mesh.polygons, self.mats):
            p.material_index = used.index(m)
            p.use_smooth = False
        mesh.validate(verbose=False)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()
        for p in mesh.polygons:
            p.use_smooth = False
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        return obj


# ----------------------------------------------------------------------------
# Geometry primitives (all return (verts, faces))
# ----------------------------------------------------------------------------
def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vmul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def lofft(rings, cap_start=True, cap_end=True):
    n = len(rings[0])
    m = len(rings)
    verts = []
    for r in rings:
        verts.extend(r)
    faces = []
    for k in range(m - 1):
        for i in range(n):
            a = k * n + i
            b = k * n + (i + 1) % n
            c = (k + 1) * n + (i + 1) % n
            d = (k + 1) * n + i
            faces.append((a, b, c, d))
    if cap_start:
        faces.append(tuple(reversed(range(n))))
    if cap_end:
        faces.append(tuple(range((m - 1) * n, m * n)))
    return verts, faces


def ngon_ring(r, n, rot=0.0, cx=0.0, cy=0.0, sx=1.0, sy=1.0):
    return [(cx + r * sx * math.cos(rot + 2.0 * math.pi * i / n),
             cy + r * sy * math.sin(rot + 2.0 * math.pi * i / n)) for i in range(n)]


def prism(rings2d, zs, cap_bottom=True, cap_top=True):
    rings = [[(x, y, zs[k]) for (x, y) in rings2d[k]] for k in range(len(rings2d))]
    return lofft(rings, cap_bottom, cap_top)


def ring_prism(cx, cy, z0, z1, r0, r1, n=8, rot0=0.0, rot1=None, sx=1.0, sy=1.0):
    if rot1 is None:
        rot1 = rot0
    rings = [ngon_ring(r0, n, rot0, cx, cy, sx, sy), ngon_ring(r1, n, rot1, cx, cy, sx, sy)]
    return prism(rings, [z0, z1])


def box(x0, x1, y0, y1, z0, z1):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return v, f


def box_c(sx, sy, sz, loc=(0, 0, 0), rot_z=0.0, rot_x=0.0, rot_y=0.0):
    v, f = box(-sx / 2, sx / 2, -sy / 2, sy / 2, -sz / 2, sz / 2)
    return xf(v, loc=loc, rot=(rot_x, rot_y, rot_z)), f


def xf(verts, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    e = Euler(rot, "XYZ")
    out = []
    for v in verts:
        vv = Vector((v[0] * scale[0], v[1] * scale[1], v[2] * scale[2]))
        vv.rotate(e)
        out.append((vv.x + loc[0], vv.y + loc[1], vv.z + loc[2]))
    return out


def tube(points, radii, sides=6, ref=(0, 1, 0), caps=True, twist=0.0):
    pts = [Vector(p) for p in points]
    if len(pts) < 2:
        return [], []
    ts = []
    for i in range(len(pts)):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == len(pts) - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        ts.append(t.normalized())
    n = ts[0].cross(Vector(ref))
    if n.length < 1e-5:
        n = ts[0].cross(Vector((1, 0, 0)))
    n.normalize()
    normals = [n]
    for i in range(1, len(pts)):
        q = ts[i - 1].rotation_difference(ts[i])
        nn = (q @ normals[-1]).normalized()
        nn = (nn - ts[i] * nn.dot(ts[i])).normalized()
        normals.append(nn)
    rings = []
    for i, p in enumerate(pts):
        b = ts[i].cross(normals[i]).normalized()
        ring = []
        for j in range(sides):
            a = 2.0 * math.pi * j / sides + twist * i
            ring.append(tuple(p + normals[i] * (math.cos(a) * radii[i]) + b * (math.sin(a) * radii[i])))
        rings.append(ring)
    return lofft(rings, caps, caps)


def torus(R, r, nmaj=12, nmin=4, center=(0, 0, 0), rot=(0, 0, 0)):
    verts = []
    faces = []
    for i in range(nmaj):
        a = 2.0 * math.pi * i / nmaj
        for j in range(nmin):
            b = 2.0 * math.pi * j / nmin
            rad = R + r * math.cos(b)
            verts.append((rad * math.cos(a), rad * math.sin(a), r * math.sin(b)))
    for i in range(nmaj):
        for j in range(nmin):
            ia = i * nmin + j
            ib = i * nmin + (j + 1) % nmin
            ic = ((i + 1) % nmaj) * nmin + (j + 1) % nmin
            idd = ((i + 1) % nmaj) * nmin + j
            faces.append((ia, ib, ic, idd))
    return xf(verts, loc=center, rot=rot), faces


_ICO_CACHE = {}


def ico_geo(subdiv=1):
    if subdiv in _ICO_CACHE:
        return _ICO_CACHE[subdiv]
    t = (1.0 + math.sqrt(5.0)) / 2.0
    base = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
            (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    verts = []
    for v in base:
        vv = Vector(v).normalized()
        verts.append((vv.x, vv.y, vv.z))
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
             (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
             (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
             (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(subdiv):
        cache = {}
        new_faces = []

        def midpoint(a, b):
            key = (a, b) if a < b else (b, a)
            if key in cache:
                return cache[key]
            va = Vector(verts[a])
            vb = Vector(verts[b])
            vv = (va + vb).normalized()
            verts.append((vv.x, vv.y, vv.z))
            idx = len(verts) - 1
            cache[key] = idx
            return idx

        for (a, b, c) in faces:
            ab = midpoint(a, b)
            bc = midpoint(b, c)
            ca = midpoint(c, a)
            new_faces.extend([(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)])
        faces = new_faces
    _ICO_CACHE[subdiv] = (verts, faces)
    return verts, faces


def icosphere(subdiv=1, radius=1.0, scale=(1, 1, 1), loc=(0, 0, 0), rot=(0, 0, 0), flatten_z=None):
    verts, faces = ico_geo(subdiv)
    out = [(v[0] * radius * scale[0], v[1] * radius * scale[1], v[2] * radius * scale[2]) for v in verts]
    out = xf(out, loc=loc, rot=rot)
    if flatten_z is not None:
        out = [(x, y, max(z, flatten_z)) for (x, y, z) in out]
    return out, faces


def arch_solid(w, h, depth, segs=4):
    r = w / 2.0
    ah = h - r
    pts = [(-r, 0.0), (r, 0.0)]
    for i in range(segs + 1):
        a = math.pi * i / segs
        pts.append((r * math.cos(a), ah + r * math.sin(a)))
    n = len(pts)
    front = [(x, -depth / 2, z) for (x, z) in pts]
    back = [(x, depth / 2, z) for (x, z) in pts]
    verts = front + back
    faces = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return verts, faces


_LEAF_BASE = [(0.0, -0.5), (0.13, -0.42), (0.30, -0.22), (0.38, 0.0), (0.30, 0.22),
              (0.16, 0.38), (0.05, 0.46), (0.0, 0.5)]


def leaf_loop(w, h):
    pts = list(_LEAF_BASE) + [(-x, y) for (x, y) in reversed(_LEAF_BASE[1:-1])]
    return [(x * (w / 0.76), y * h) for (x, y) in pts]


def leaf_solid(w, h, depth, loc=(0, 0, 0), rot=(0, 0, 0)):
    pts = leaf_loop(w, h)
    n = len(pts)
    front = [(x, -depth / 2, z) for (x, z) in pts]
    back = [(x, depth / 2, z) for (x, z) in pts]
    verts = xf(front + back, loc=loc, rot=rot)
    faces = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return verts, faces


def leaf_ring(w, h, inner_w, inner_h, depth, loc=(0, 0, 0), rot=(0, 0, 0)):
    outer = leaf_loop(w, h)
    inner = leaf_loop(inner_w, inner_h)
    n = len(outer)
    verts = []
    for (x, z) in outer:
        verts.append((x, -depth / 2, z))
    for (x, z) in inner:
        verts.append((x, -depth / 2, z))
    for (x, z) in outer:
        verts.append((x, depth / 2, z))
    for (x, z) in inner:
        verts.append((x, depth / 2, z))
    # index blocks: OF=0, IF=n, OB=2n, IB=3n
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))                      # front rim
        faces.append((2 * n + i, 3 * n + i, 3 * n + j, 2 * n + j))  # back rim
        faces.append((i, 2 * n + i, 2 * n + j, j))              # outer wall
        faces.append((n + i, n + j, 3 * n + j, 3 * n + i))      # inner wall
    return xf(verts, loc=loc, rot=rot), faces


def ring_segment_solid(r0, r1, z0, z1, a0, a1, cx=0.0, cy=0.0, cap_ends=True):
    def p(r, a, z):
        return (cx + r * math.cos(a), cy + r * math.sin(a), z)
    verts = [p(r0, a0, z0), p(r1, a0, z0), p(r1, a1, z0), p(r0, a1, z0),
             p(r0, a0, z1), p(r1, a0, z1), p(r1, a1, z1), p(r0, a1, z1)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    if not cap_ends:
        faces = faces[0:4]
    return verts, faces


def thick_strip(leading, trailing, half, axis=(0, 0, 1)):
    """Two rows of matching points -> a slab with thickness along axis."""
    m = len(leading)
    ax = vmul(axis, half)
    top = [vadd(p, ax) for p in leading] + [vadd(p, ax) for p in trailing]
    bot = [vsub(p, ax) for p in leading] + [vsub(p, ax) for p in trailing]
    verts = top + bot
    L = 0
    R = m
    B = 2 * m
    faces = []
    for i in range(m - 1):
        faces.append((L + i, L + i + 1, R + i + 1, R + i))
        faces.append((B + i, B + i + 1, B + R - L + i + 1, B + R - L + i))
    # borders
    for i in range(m - 1):
        faces.append((L + i, L + i + 1, B + i + 1, B + i))                 # leading edge
        faces.append((R + i, B + R - L + i, B + R - L + i + 1, R + i + 1))  # trailing edge
    # end caps
    faces.append((L, R, B + R - L, B))
    faces.append((L + m - 1, B + m - 1, B + 2 * m - 1, R + m - 1))
    return verts, faces


def slab_outline(poly, half_vec):
    """Closed flat-ish polygon extruded by +- half_vec."""
    n = len(poly)
    top = [vadd(p, half_vec) for p in poly]
    bot = [vsub(p, half_vec) for p in poly]
    verts = top + bot
    faces = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return verts, faces


# ----------------------------------------------------------------------------
# Scene / preview pipeline
# ----------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.02
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 3
    scene.cycles.transmission_bounces = 2
    scene.cycles.transparent_max_bounces = 4
    scene.render.resolution_x = RES
    scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = VIEW
    scene.view_settings.exposure = -0.15 if VIEW == "Standard" else -0.20

    # world: flat warm beige backdrop for camera rays, softer ambient for lighting
    world = bpy.data.worlds.new("RelicStudio")
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_cam.inputs[0].default_value = (*hexlin("E9DFCB"), 1.0)
    bg_cam.inputs[1].default_value = 1.8
    bg_amb = nt.nodes.new("ShaderNodeBackground")
    bg_amb.inputs[0].default_value = (*hexlin("CFCBC1"), 1.0)
    bg_amb.inputs[1].default_value = 0.30
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg_amb.outputs["Background"], mix.inputs[1])
    nt.links.new(bg_cam.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    scene.world = world

    # compositor: mild bloom so emissive pieces read as light
    scene.use_nodes = True
    nt = scene.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new("CompositorNodeRLayers")
    glare = nt.nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    glare.quality = "MEDIUM"
    glare.threshold = 0.9
    glare.size = 7
    glare.mix = -0.58
    comp = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(rl.outputs["Image"], glare.inputs["Image"])
    nt.links.new(glare.outputs["Image"], comp.inputs["Image"])
    return scene


def add_light_rig():
    scene = bpy.context.scene
    specs = [
        ("KeyWarm", (0.48, 0.62, -1.0), 2.4, (1.0, 0.88, 0.71), 0.16),
        ("FillCool", (-0.72, 0.42, -0.45), 0.55, (0.66, 0.78, 1.0), 0.3),
        ("Rim", (-0.22, -0.9, -0.35), 3.2, (1.0, 0.94, 0.86), 0.12),
        ("BounceUp", (0.08, 0.0, 1.0), 0.70, (0.72, 0.82, 1.0), 0.6),
    ]
    for name, d, energy, color, angle in specs:
        light = bpy.data.lights.new(name, "SUN")
        light.energy = energy
        light.color = color
        light.angle = angle
        obj = bpy.data.objects.new(name, light)
        obj.rotation_euler = Vector(d).normalized().to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(obj)

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 50
    cam_data.sensor_width = 36
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam


def make_ground(radius):
    size = max(70.0, radius * 40.0)
    mb = MB()
    verts = [(-size, -size, -0.01), (size, -size, -0.01), (size, size, -0.01), (-size, size, -0.01)]
    mb.add(verts, [(0, 1, 2, 3)], "PreviewGround")
    obj = mb.build("PreviewGround")
    return obj


def object_bbox(obj):
    co = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mn = [min(c[i] for c in co) for i in range(3)]
    mx = [max(c[i] for c in co) for i in range(3)]
    return mn, mx


def place_camera(center, radius, elev_deg, azim_deg, dist_factor=3.15):
    scene = bpy.context.scene
    cam = scene.camera
    d = max(0.5, radius * dist_factor)
    el = math.radians(elev_deg)
    az = math.radians(azim_deg)
    loc = Vector((center[0] - d * math.cos(el) * math.sin(az),
                  center[1] - d * math.cos(el) * math.cos(az),
                  center[2] + d * math.sin(el)))
    cam.location = loc
    cam.data.clip_start = max(0.01, d * 0.002)
    cam.data.clip_end = d * 30.0
    direction = (Vector(center) - loc).normalized()
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def render_view(obj, outpath, elev, azim, dist_factor=3.15):
    scene = bpy.context.scene
    mn, mx = object_bbox(obj)
    center = [(mn[i] + mx[i]) / 2 for i in range(3)]
    radius = 0.5 * math.sqrt(sum((mx[i] - mn[i]) ** 2 for i in range(3)))
    place_camera(center, radius, elev, azim, dist_factor)
    scene.render.filepath = outpath
    bpy.ops.render.render(write_still=True)
    print("[render] %s (r=%.2fm d=%.2fm)" % (outpath, radius, radius * dist_factor), flush=True)


def add_point_lights(specs):
    objs = []
    for i, s in enumerate(specs):
        light = bpy.data.lights.new("RelicPoint_%d" % i, "POINT")
        light.energy = s.get("energy", 300.0)
        light.color = s.get("color", (1.0, 0.72, 0.42))
        light.shadow_soft_size = s.get("radius", 0.4)
        obj = bpy.data.objects.new("RelicPoint_%d" % i, light)
        obj.location = s["loc"]
        bpy.context.scene.collection.objects.link(obj)
        objs.append(obj)
    return objs


def remove_objects(objs):
    for o in objs:
        if o is not None:
            try:
                bpy.data.objects.remove(o, do_unlink=True)
            except Exception:
                pass


def tris_of(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


# ----------------------------------------------------------------------------
# Asset builders (part 1: small relics)
# ----------------------------------------------------------------------------
def build_paper_lantern():
    mb = MB()
    rnd = random.Random(11)
    n = 8
    rot0 = math.pi / 8

    # paper shade profile
    zr = [(-0.175, 0.135), (-0.09, 0.185), (0.0, 0.205), (0.09, 0.185), (0.175, 0.135)]
    rings = [ngon_ring(r, n, rot0) for (z, r) in zr]
    mb.add(*prism([[p for p in ring] for ring in rings], [z for (z, r) in zr]), "PaperWarm")

    # top / bottom caps
    mb.add(*ring_prism(0, 0, -0.215, -0.172, 0.10, 0.138, n, rot0), "Frame")
    mb.add(*ring_prism(0, 0, 0.172, 0.215, 0.138, 0.098, n, rot0), "Frame")
    mb.add(*ring_prism(0, 0, 0.215, 0.232, 0.06, 0.045, n, rot0), "Frame")

    # vertical dark ribs following the shade
    for k in range(6):
        a = rot0 + 2 * math.pi * k / 6
        pts = []
        for (z, r) in zr:
            rr = r + 0.012
            pts.append((math.cos(a) * rr, math.sin(a) * rr, z))
        mb.add(*tube(pts, [0.013] * len(pts), sides=4, ref=(math.cos(a), math.sin(a), 0)), "Frame")

    # hanging ring (gold) in XZ plane
    mb.add(*torus(0.045, 0.011, 10, 4, (0, 0, 0.242), (math.pi / 2, 0, 0)), "Gold")
    mb.add(*tube([(0, 0, 0.232), (0, 0, 0.240)], [0.018, 0.018], sides=4), "GoldDark")

    # tassel
    mb.add(*tube([(0, 0, -0.215), (0, 0, -0.252)], [0.011, 0.011], sides=4), "Tassel")
    mb.add(*icosphere(0, 0.036, (1, 1, 1), (0, 0, -0.258), (0, 0, 0.3)), "GoldDark")
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.4
        pts = [(0, 0, -0.262), (math.cos(a) * 0.016, math.sin(a) * 0.016, -0.276),
               (math.cos(a) * 0.030, math.sin(a) * 0.030, -0.300)]
        mb.add(*tube(pts, [0.008, 0.007, 0.005], sides=4), "Tassel")

    return mb


def build_ember_collectible():
    mb = MB()

    # faceted teardrop core (gold-orange, emission 5); tip breaks out of the shell
    zr = [(-0.190, 0.004), (-0.150, 0.045), (-0.088, 0.082), (-0.015, 0.098),
          (0.055, 0.082), (0.118, 0.050), (0.163, 0.019), (0.190, 0.002)]
    rings = [ngon_ring(r, 6, 0.3 + i * 0.17) for i, (z, r) in enumerate(zr)]
    mb.add(*prism(rings, [z for (z, r) in zr], cap_bottom=True, cap_top=True), "EmberCore")

    # shell: six angular, slightly twisted crystal shards (gaps let the core glow through)
    shell_z = [(-0.200, 0.095, 0.145), (-0.115, 0.168, 0.160), (0.005, 0.152, 0.135),
               (0.095, 0.098, 0.100), (0.155, 0.038, 0.050)]
    for k in range(6):
        a0 = 2 * math.pi * k / 6 + 0.34
        rings = []
        for li, (z, r, w) in enumerate(shell_z):
            t = 0.026
            aa = a0 + 0.17 * (li / 4.0) ** 1.5
            rings.append([(r * math.cos(aa - w), r * math.sin(aa - w), z),
                          ((r + t) * math.cos(aa - w), (r + t) * math.sin(aa - w), z),
                          ((r + t) * math.cos(aa + w), (r + t) * math.sin(aa + w), z),
                          (r * math.cos(aa + w), r * math.sin(aa + w), z)])
        mb.add(*lofft(rings, True, True), "EmberShell")

    return mb


def build_bird():
    mb = MB()
    n = 5
    # compact body: rounded head, tapering back, nose to -Y
    stations = [(-0.105, 0.006, 0.012), (-0.085, 0.022, 0.019), (-0.048, 0.034, 0.016),
                (0.0, 0.036, 0.006), (0.048, 0.028, 0.004), (0.092, 0.017, 0.008),
                (0.112, 0.005, 0.010)]
    rings = []
    for (y, r, zc) in stations:
        ring = []
        for i in range(n):
            a = math.pi / 2 + 2 * math.pi * i / n
            ring.append((r * math.cos(a), y, zc + r * 1.08 * math.sin(a)))
        rings.append(ring)
    mb.add(*lofft(rings, True, True), "BirdDark")

    # beak
    mb.add(*tube([(0, -0.105, 0.014), (0, -0.138, 0.010)], [0.010, 0.002], sides=4), "BirdBeak")

    # two clean triangular wings, swept back and slightly raised
    for s in (-1, 1):
        root_front = (s * 0.022, -0.048, 0.020)
        elbow = (s * 0.140, -0.030, 0.026)
        root_back = (s * 0.030, 0.038, 0.010)
        tip = (s * 0.300, 0.088, 0.030)
        mb.add(*slab_outline([root_front, elbow, tip, root_back], (0, 0, 0.007)), "BirdDark")

    # small forked tail
    for s in (-1, 1):
        mb.add(*slab_outline([(0, 0.095, 0.008), (s * 0.060, 0.205, 0.012), (s * 0.012, 0.185, 0.010)],
                             (0, 0, 0.0045)), "BirdDark")

    return mb


def build_cloud_puff():
    mb = MB()
    rnd = random.Random(77)
    lumps = [
        ((0.0, 0.0, 0.1), (3.25, 2.3, 1.7)),
        ((2.95, 0.2, 0.35), (2.35, 1.85, 1.6)),
        ((-3.0, -0.1, 0.25), (2.4, 1.9, 1.55)),
        ((-0.3, -0.1, 1.9), (2.2, 1.7, 1.5)),
        ((0.4, 1.6, 0.85), (2.2, 1.6, 1.3)),
        ((1.1, -1.5, -1.0), (1.9, 1.5, 1.1)),
        ((1.8, 0.5, 1.9), (1.5, 1.3, 1.1)),
    ]
    all_v = []
    all_f = []
    all_m = []
    for (loc, scale) in lumps:
        rot = (rnd.uniform(-0.18, 0.18), rnd.uniform(-0.18, 0.18), rnd.uniform(0, math.pi))
        verts, faces = icosphere(1, 1.0, scale, loc, rot)
        verts = [(x, y, max(z, -2.15)) for (x, y, z) in verts]
        base = len(all_v)
        all_v.extend(verts)
        for f in faces:
            all_f.append(tuple(base + i for i in f))
            va, vb, vc = (all_v[base + f[0]], all_v[base + f[1]], all_v[base + f[2]])
            ux, uy, uz = vb[0] - va[0], vb[1] - va[1], vb[2] - va[2]
            wx, wy, wz = vc[0] - va[0], vc[1] - va[1], vc[2] - va[2]
            nz = ux * wy - uy * wx
            ny = uz * wx - ux * wz
            nx = uy * wz - uz * wy
            nrm = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            all_m.append("CloudShade" if nz / nrm < -0.18 else "Cloud")
    mb.add(all_v, all_f, all_m)

    (mnx, mny, mnz), (mxx, mxy, mxz) = mb.bounds()
    mb.translate(-(mnx + mxx) / 2, -(mny + mxy) / 2, -(mnz + mxz) / 2)
    return mb


def build_beacon_lantern():
    """5.5 m chapter-goal lamp post: stone base, carved shaft, four arms cradling an unlit paper lantern."""
    mb = MB()
    rnd = random.Random(41)

    # stepped stone base (original fantasy silhouette, not a shrine/torii)
    mb.add(*prism([ngon_ring(1.42, 8, 0.18), ngon_ring(1.28, 8, 0.30)], [0.0, 0.26]), "StoneDark")
    mb.add(*prism([ngon_ring(1.10, 7, 0.02), ngon_ring(0.96, 7, 0.14)], [0.26, 0.56]), "Stone")
    mb.add(*prism([ngon_ring(0.70, 6, 0.20), ngon_ring(0.60, 6, 0.30)], [0.56, 0.80]), "StoneLight")

    # entry steps on the front-left face
    mb.add(*box(-1.36, -0.42, -1.30, -0.72, 0.00, 0.16), "StoneLight")
    mb.add(*box(-1.18, -0.50, -1.12, -0.66, 0.16, 0.30), "Stone")

    # angular rubble (subdiv 0 keeps it faceted)
    for (x, y, s, rz) in [(-1.36, 0.25, 0.30, 0.5), (1.30, -0.55, 0.26, 1.3), (1.02, 1.24, 0.34, 2.2),
                          (-1.30, 1.02, 0.24, 3.0), (0.55, -1.55, 0.18, 0.9)]:
        mb.add(*icosphere(0, s, (1.25, 0.95, 0.72), (x, y, 0.03), (0, 0, rz), flatten_z=0.0), "StoneDark")

    # moss creeping in the crevices
    for (x, y, z, s) in [(-1.18, -0.10, 0.16, 0.30), (0.82, 0.72, 0.12, 0.27), (0.16, -1.02, 0.15, 0.22),
                         (-0.62, 0.92, 0.18, 0.24), (0.58, -0.30, 0.48, 0.16), (-0.34, 0.42, 0.70, 0.13)]:
        mb.add(*icosphere(1, s, (1.25, 0.95, 0.12), (x, y, z), (0, 0, rnd.random() * 6.28), flatten_z=z - 0.015), "Moss")

    # carved six-sided shaft, slowly twisting
    sections = [(0.80, 1.42, 0.44, 0.40, 0.00, 0.10), (1.42, 2.08, 0.40, 0.355, 0.10, 0.20),
                (2.08, 2.70, 0.355, 0.315, 0.20, 0.30), (2.70, 3.22, 0.315, 0.285, 0.30, 0.40)]
    for (z0, z1, r0, r1, rot0, rot1) in sections:
        mb.add(*ring_prism(0, 0, z0, z1, r0, r1, 6, rot0=rot0, rot1=rot1), "Stone")
        mb.add(*ring_prism(0, 0, z1 - 0.055, z1 + 0.035, r1 + 0.055, r1 + 0.055, 6, rot0=rot1), "StoneLight")

    # gold inlay band + small carved glyph strips on the front faces
    mb.add(*ring_prism(0, 0, 2.56, 2.64, 0.385, 0.385, 6, rot0=0.20), "Gold")
    for (ang, z, rad, w, h) in [(-1.30, 1.16, 0.40, 0.055, 0.16), (-2.15, 1.92, 0.36, 0.045, 0.13),
                                (-1.62, 2.42, 0.32, 0.040, 0.11)]:
        mb.add(*box_c(w, 0.03, h, (rad * math.cos(ang), rad * math.sin(ang), z), rot_z=ang + math.pi / 2), "GoldDark")
    for (ang, z, rad) in [(0.55, 1.55, 0.42), (2.45, 2.10, 0.37), (4.05, 2.34, 0.34)]:
        mb.add(*icosphere(0, 0.035, (1, 1, 1), (rad * math.cos(ang), rad * math.sin(ang), z)), "Gold")

    # carved spiral groove winding up the shaft (reads as engraving at any angle)
    pts = []
    for i in range(49):
        t = i / 48.0
        z = 0.94 + t * 2.20
        rr = 0.448 - 0.145 * t
        a = -1.2 + t * 3.4 * 2.0 * math.pi
        pts.append((math.cos(a) * (rr + 0.006), math.sin(a) * (rr + 0.006), z))
    mb.add(*tube(pts, [0.017] * len(pts), sides=4), "StoneDark")

    # four arms sweeping up to a cradle ring
    for ang in (0.90, 2.47, 4.04, 5.61):
        ca, sa = math.cos(ang), math.sin(ang)
        prof = [(0.30, 2.88, 0.100), (0.58, 3.02, 0.092), (0.86, 3.36, 0.076),
                (0.94, 3.76, 0.060), (0.805, 4.09, 0.048)]
        pts = [(r * ca, r * sa, z) for (r, z, _) in prof]
        mb.add(*tube(pts, [rr for (_, _, rr) in prof], sides=5), "GoldDark")
        mb.add(*icosphere(0, 0.06, (1, 1, 1), (0.805 * ca, 0.805 * sa, 4.10)), "Gold")

    # cradle ring for the lantern
    mb.add(*torus(0.78, 0.036, 12, 4, (0, 0, 4.10)), "GoldDark")

    # big unlit paper lantern
    lzr = [(4.16, 0.32), (4.28, 0.56), (4.52, 0.69), (4.80, 0.67), (5.00, 0.50), (5.10, 0.32)]
    rings = [ngon_ring(r, 8, math.pi / 8 + 0.10) for (z, r) in lzr]
    mb.add(*prism([[p for p in ring] for ring in rings], [z for (z, r) in lzr]), "PaperGlow")
    mb.add(*ring_prism(0, 0, 4.10, 4.16, 0.36, 0.32, 8, math.pi / 8 + 0.10), "WoodDark")
    mb.add(*ring_prism(0, 0, 5.10, 5.17, 0.32, 0.22, 8, math.pi / 8 + 0.10), "WoodDark")
    mb.add(*ring_prism(0, 0, 5.17, 5.23, 0.16, 0.10, 8, math.pi / 8 + 0.10), "GoldDark")

    # dark ribs over the paper shade
    for k in range(8):
        a = math.pi / 8 + 0.10 + 2 * math.pi * k / 8
        pts = []
        for (z, r) in lzr:
            rr = r + 0.015
            pts.append((math.cos(a) * rr, math.sin(a) * rr, z))
        mb.add(*tube(pts, [0.020] * len(pts), sides=4, ref=(math.cos(a), math.sin(a), 0)), "WoodDark")

    # gold finial: height tops out at 5.50 m
    mb.add(*tube([(0, 0, 5.23), (0, 0, 5.35), (0, 0, 5.50)], [0.055, 0.030, 0.004], sides=6), "Gold")

    return mb


def build_memory_shard():
    """1.8 m standing stone with a leaf-shaped cavity, inner teal glow, moss and vines."""
    prof = [(-0.46, -0.28), (0.46, -0.28), (0.60, -0.02), (0.50, 0.26),
            (0.16, 0.40), (-0.34, 0.34), (-0.60, 0.06), (-0.56, -0.10)]
    levels = [(0.00, 1.00, 0.00, 0.00), (0.22, 1.02, 0.01, 0.00), (0.55, 1.00, 0.02, 0.01),
              (0.95, 0.92, 0.03, 0.00), (1.30, 0.80, 0.04, 0.00), (1.60, 0.60, 0.06, 0.00),
              (1.76, 0.34, 0.08, 0.00)]
    rings = []
    for (z, s, dx, dy) in levels:
        rings.append([(x * s + dx, y * s + dy, z) for (x, y) in prof])
    n = len(prof)
    m = len(levels)
    verts = []
    for r in rings:
        verts.extend(r)
    faces = []
    for k in range(m - 1):
        for i in range(n):
            a = k * n + i
            b = k * n + (i + 1) % n
            c = (k + 1) * n + (i + 1) % n
            d = (k + 1) * n + i
            faces.append((a, b, c, d))
    faces.append(tuple(reversed(range(n))))
    apex = (0.14, 0.02, 1.80)
    verts.append(apex)
    ai = len(verts) - 1
    top0 = (m - 1) * n
    for i in range(n):
        faces.append((top0 + i, top0 + (i + 1) % n, ai))

    stone_mb = MB()
    stone_mb.add(verts, faces, "ShardStone")
    # secondary broken peak gives the monolith a chipped, asymmetric crown
    stone_mb.add(*ring_prism(0.24, 0.01, 1.44, 1.79, 0.19, 0.055, 5, rot0=0.35, rot1=0.95), "ShardStone")
    stone_mb.add(*ring_prism(0.24, 0.01, 1.78, 1.84, 0.07, 0.012, 5, rot0=0.35, rot1=1.15), "ShardStone")
    stone = stone_mb.build("memory_shard")

    # shallow leaf-shaped cavity cut into the front (-Y) face
    cut_mb = MB()
    cut_mb.add(*leaf_solid(0.50, 1.00, 0.40, loc=(0, -0.38, 1.00)), "ShardStone")
    cutter = cut_mb.build("memory_leaf_cut")
    bpy.context.view_layer.objects.active = stone
    mod = stone.modifiers.new("LeafCavity", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cutter
    mod.solver = "EXACT"
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)

    # decorations
    deco = MB()
    deco.add(*leaf_ring(0.585, 1.075, 0.50, 1.00, 0.06, loc=(0, -0.300, 1.00)), "GoldDark")
    deco.add(*leaf_solid(0.46, 0.94, 0.03, loc=(0, -0.205, 1.00)), "ShardGlow")
    # gold leaf veins inside the aperture
    deco.add(*tube([(0, -0.238, 0.62), (0, -0.238, 1.06), (0, -0.238, 1.44)],
                   [0.014, 0.012, 0.008], sides=4), "GoldDark")
    for s in (-1, 1):
        deco.add(*tube([(0, -0.238, 0.84), (s * 0.10, -0.238, 1.00), (s * 0.145, -0.238, 1.10)],
                       [0.010, 0.008, 0.004], sides=4), "GoldDark")
        deco.add(*tube([(0, -0.238, 1.08), (s * 0.075, -0.238, 1.22), (s * 0.105, -0.238, 1.30)],
                       [0.009, 0.007, 0.004], sides=4), "GoldDark")
    for z in (1.61, 0.36):
        deco.add(*icosphere(0, 0.040, (1, 1, 1), (0.0, -0.318, z)), "GoldDark")

    # hairline cracks
    for crack in ([(-0.42, -0.235, 1.38), (-0.35, -0.262, 1.18), (-0.39, -0.272, 0.98), (-0.30, -0.278, 0.86)],
                  [(0.46, -0.160, 0.66), (0.51, -0.150, 0.51), (0.46, -0.228, 0.36)]):
        deco.add(*tube(crack, [0.012] * len(crack), sides=4), "ShardStoneDark")

    rnd = random.Random(13)
    for (x, y, s, rot) in [(-0.66, -0.02, 0.22, 0.4), (0.60, 0.10, 0.18, 1.1), (0.34, -0.44, 0.14, 2.0)]:
        deco.add(*icosphere(0, s, (1.15, 0.95, 0.7), (x, y, 0.03), (0, 0, rot), flatten_z=0.0), "ShardStoneLight")
    for (x, y, z, s) in [(-0.48, -0.16, 0.08, 0.18), (0.46, 0.14, 0.08, 0.17), (0.08, 0.32, 0.08, 0.15),
                         (-0.22, 0.20, 1.55, 0.13), (0.26, 0.03, 1.68, 0.11)]:
        deco.add(*icosphere(1, s, (1.2, 1.0, 0.14), (x, y, z), (0, 0, rnd.random() * 6.28), flatten_z=z - 0.015), "Moss")

    vines = [
        [(0.48, -0.02, 0.02), (0.56, -0.08, 0.35), (0.52, -0.12, 0.78),
         (0.42, -0.08, 1.18), (0.29, -0.02, 1.48), (0.13, 0.00, 1.70)],
        [(-0.50, 0.08, 0.00), (-0.57, 0.11, 0.42), (-0.51, 0.16, 0.86),
         (-0.36, 0.18, 1.22), (-0.19, 0.15, 1.52)],
    ]
    radii = [0.026, 0.024, 0.022, 0.020, 0.016, 0.010]
    for vi, pts in enumerate(vines):
        deco.add(*tube(pts, radii[:len(pts)], sides=5), "Vine")
        for j in range(2, len(pts) - 1):
            p = pts[j]
            s = -1 if vi == 0 else 1
            leaf = [(p[0], p[1], p[2]),
                    (p[0] + 0.050 * s, p[1] - 0.035, p[2] - 0.045),
                    (p[0] + 0.018 * s, p[1] - 0.060, p[2] - 0.085)]
            deco.add(*slab_outline(leaf, (0, 0, 0.0035)), "LeafVine")

    deco_obj = deco.build("memory_shard_deco")

    bpy.ops.object.select_all(action="DESELECT")
    stone.select_set(True)
    deco_obj.select_set(True)
    bpy.context.view_layer.objects.active = stone
    bpy.ops.object.join()
    obj = stone
    obj.name = "memory_shard"
    obj.data.name = "memory_shard"
    for p in obj.data.polygons:
        p.use_smooth = False
    return obj


def _lh_r(t):
    return 2.42 - 0.86 * (max(0.0, min(1.0, t)) ** 0.92)


def _lh_c(t):
    return (0.32 * math.sin(t * 2.3), 0.16 * math.sin(t * 3.1 - 0.4))


def build_lighthouse():
    """16 m broken spiral lighthouse: rocky islet, winding ramp, arched windows, ruined lamp room."""
    mb = MB()
    z0, z1 = 1.25, 11.55
    hgt = z1 - z0

    def lz(t):
        return z0 + hgt * t

    # ---- rocky islet -------------------------------------------------------
    ring0 = []
    for i in range(10):
        a = 2 * math.pi * i / 10
        rr = 3.20 + 0.42 * math.sin(3 * a + 0.7) + 0.22 * math.cos(5 * a + 1.2)
        ring0.append((rr * math.cos(a), rr * math.sin(a)))
    ring1 = [(x * 0.80, y * 0.80) for (x, y) in ring0]
    mb.add(*prism([ring0, ring1], [0.0, 0.55]), "StoneDark")

    rocks = [((3.0, 0.6), 1.55, 1.55, 0.4), ((-2.8, -1.3), 1.50, 1.30, 1.3),
             ((1.1, 2.9), 1.55, 1.45, 2.2), ((-1.7, 2.4), 1.20, 1.00, 0.7),
             ((2.4, -2.3), 1.30, 1.10, 2.8), ((-3.0, 0.4), 1.10, 1.70, 1.7)]

    def boulder(cx, cy, rr, h, rot):
        rings = []
        for (zz, sc) in [(0.0, 0.92), (h * 0.55, 1.0), (h, 0.52)]:
            ring = []
            for i in range(7):
                a = rot + 2 * math.pi * i / 7
                rad = rr * sc * (1.0 + 0.16 * math.sin(i * 2.3 + rot * 3.0))
                ring.append((cx + rad * math.cos(a), cy + rad * math.sin(a), zz))
            rings.append(ring)
        mb.add(*lofft(rings, True, True), "Stone")

    for (loc, rr, h, rot) in rocks:
        boulder(loc[0], loc[1], rr, h, rot)
    for (loc, sc, rot) in [((0.3, -3.2), (0.7, 0.6, 0.5), 0.4), ((-2.4, 2.9), (0.6, 0.55, 0.45), 2.6)]:
        mb.add(*icosphere(0, 1.0, sc, (loc[0], loc[1], 0.15), (0, 0, rot), flatten_z=0.0), "StoneDark")

    # sea stacks
    mb.add(*ring_prism(-3.5, 1.9, 0.10, 2.55, 0.58, 0.07, 5, rot0=0.3, rot1=0.9), "StoneDark")
    mb.add(*ring_prism(3.6, -1.7, 0.10, 1.75, 0.44, 0.06, 5, rot0=1.1, rot1=1.7), "Stone")
    for (x, y, z, s, rot) in [(-2.7, -0.3, 0.55, 0.52, 0.4), (1.9, 1.8, 0.55, 0.44, 1.6),
                              (0.5, -2.9, 0.42, 0.36, 2.4), (-0.4, 2.9, 0.62, 0.34, 3.1)]:
        mb.add(*icosphere(1, s, (1.3, 1.0, 0.16), (x, y, z), (0, 0, rot), flatten_z=z - 0.02), "Moss")

    # ---- plinth + tower body ----------------------------------------------
    mb.add(*ring_prism(0, 0, 0.50, 0.95, 2.88, 2.68, 8, rot0=0.15), "StoneDark")
    mb.add(*ring_prism(0, 0, 0.95, 1.34, 2.64, 2.52, 8, rot0=0.30), "Stone")

    rings = []
    zs = []
    for i in range(9):
        t = i / 8.0
        rings.append(ngon_ring(_lh_r(t), 8, -0.20 + 2.5 * t, *_lh_c(t)))
        zs.append(lz(t))
    mb.add(*prism(rings, zs), lambda i: "StoneLight" if (i // 8) % 3 == 2 else "Stone")

    # protruding masonry belts
    for t in (0.28, 0.55, 0.80):
        cx, cy = _lh_c(t)
        mb.add(*ring_prism(cx, cy, lz(t) - 0.09, lz(t) + 0.09, _lh_r(t) + 0.035, _lh_r(t) + 0.035,
                           8, rot0=-0.20 + 2.5 * t, sx=1.0, sy=1.0), "StoneDark")

    # ---- winding stone ramp + handrail ------------------------------------
    steps = 50
    turns = 1.36
    a0 = math.radians(232)
    inn, out, rail = [], [], []
    for i in range(steps + 1):
        u = i / steps
        zz = 2.30 + 8.35 * u
        aa = a0 + turns * 2 * math.pi * u
        t = (zz - z0) / hgt
        ri = _lh_r(t) + 0.02
        cx, cy = _lh_c(t)
        inn.append((cx + ri * math.cos(aa), cy + ri * math.sin(aa), zz))
        out.append((cx + (ri + 0.82) * math.cos(aa), cy + (ri + 0.82) * math.sin(aa), zz))
        rail.append((cx + (ri + 0.75) * math.cos(aa), cy + (ri + 0.75) * math.sin(aa), zz + 0.86))

    n = len(inn)
    verts = inn + out + [(x, y, z - 0.34) for (x, y, z) in inn] + [(x, y, z - 0.34) for (x, y, z) in out]
    bi = 2 * n
    bo = 3 * n
    faces = []
    for i in range(n - 1):
        faces.append((i, i + 1, n + i + 1, n + i))                     # ramp top
        faces.append((bi + i, bo + i, bo + i + 1, bi + i + 1))         # underside
        faces.append((n + i, n + i + 1, bo + i + 1, bo + i))           # outer face
        faces.append((i, bi + i, bi + i + 1, i + 1))                   # inner face
    faces.append((0, n, bo, bi))                                       # start cap
    faces.append((n - 1, bi + n - 1, bo + n - 1, 2 * n - 1))           # broken end cap
    mb.add(verts, faces, "StoneLight")

    # handrail + posts along the ramp
    mb.add(*tube(rail, [0.030] * len(rail), sides=4), "WoodDark")
    for i in range(2, steps, 6):
        base = out[i]
        top = (base[0] - 0.07 * math.cos(a0 + turns * 2 * math.pi * i / steps),
               base[1] - 0.07 * math.sin(a0 + turns * 2 * math.pi * i / steps),
               base[2] + 0.86)
        mb.add(*tube([(base[0], base[1], base[2] - 0.02), top], [0.038, 0.030], sides=4), "Wood")
    # broken ramp spurs
    mb.add(*tube([out[-1], (out[-1][0] + 0.5, out[-1][1] - 0.2, out[-1][2] + 0.35)], [0.05, 0.02], sides=4), "WoodDark")

    # ---- arched windows ----------------------------------------------------
    def add_window(az_deg, zz, w, h, broken=False):
        th = math.radians(az_deg)
        t = (zz - z0) / hgt
        r = _lh_r(t)
        cx, cy = _lh_c(t)
        phi = th + math.pi / 2
        px, py = cx + (r + 0.02) * math.cos(th), cy + (r + 0.02) * math.sin(th)
        fv, ff = arch_solid(w + 0.30, h + 0.24, 0.46)
        mb.add(xf(fv, loc=(px, py, zz), rot=(0, 0, phi)), ff, "StoneLight")
        gx, gy = cx + (r + 0.27) * math.cos(th), cy + (r + 0.27) * math.sin(th)
        gv, gf = arch_solid(w, h if not broken else h * 0.52, 0.07)
        mb.add(xf(gv, loc=(gx, gy, zz + 0.02), rot=(0, 0, phi)), gf, "StoneDark" if broken else "WarmGlass")
        if broken:
            for bz in (zz + h * 0.46, zz + h * 0.72):
                bv, bf = box_c(w * 1.05, 0.10, 0.12,
                               (cx + (r + 0.34) * math.cos(th), cy + (r + 0.34) * math.sin(th), bz),
                               rot_z=phi + 0.22)
                mb.add(bv, bf, "Wood")
        sv, sf = box_c(w + 0.42, 0.34, 0.14,
                       (cx + (r + 0.14) * math.cos(th), cy + (r + 0.14) * math.sin(th), zz - 0.03), rot_z=phi)
        mb.add(sv, sf, "Stone")
        mv, mf = box_c(0.06, 0.08, h * 0.72,
                       (cx + (r + 0.34) * math.cos(th), cy + (r + 0.34) * math.sin(th), zz + h * 0.35), rot_z=phi)
        mb.add(mv, mf, "WoodDark")

    for (az, zz, w, h) in [(262, 3.00, 0.52, 1.20), (214, 4.65, 0.48, 1.08), (282, 6.20, 0.50, 1.10),
                           (232, 7.75, 0.52, 1.16), (196, 9.15, 0.44, 0.98), (302, 10.35, 0.42, 0.94)]:
        add_window(az, zz, w, h, broken=(az == 214))

    # ---- door --------------------------------------------------------------
    th = math.radians(270)
    phi = th + math.pi / 2
    cx, cy = _lh_c(0.0)
    dr = 2.58
    dv, df = arch_solid(1.70, 2.60, 0.52)
    mb.add(xf(dv, loc=(cx, cy - dr, 1.30), rot=(0, 0, phi)), df, "StoneLight")
    wv, wf = arch_solid(1.16, 2.14, 0.12)
    mb.add(xf(wv, loc=(cx, cy - dr - 0.28, 1.34), rot=(0, 0, phi)), wf, "Wood")
    for dx in (-0.34, 0.0, 0.34):
        pv, pf = box_c(0.055, 0.04, 1.82, (cx + dx, cy - dr - 0.355, 2.20), rot_z=phi)
        mb.add(pv, pf, "WoodDark")
    for zz in (1.66, 2.58):
        bv, bf = box_c(1.06, 0.05, 0.09, (cx, cy - dr - 0.36, zz), rot_z=phi)
        mb.add(bv, bf, "GoldDark")
    mb.add(*torus(0.075, 0.018, 8, 4, (cx + 0.33, cy - dr - 0.39, 2.16), (math.pi / 2, 0, 0)), "GoldDark")
    mb.add(*box(cx - 1.00, cx + 1.00, cy - dr - 1.00, cy - dr - 0.18, 0.10, 0.26), "StoneLight")
    mb.add(*box(cx - 0.84, cx + 0.84, cy - dr - 0.74, cy - dr - 0.12, 0.26, 0.40), "Stone")

    # door lantern on a bracket
    mb.add(*tube([(cx + 0.66, cy - dr - 0.14, 3.32), (cx + 0.66, cy - dr - 0.55, 3.32)],
                 [0.035, 0.035], sides=4), "WoodDark")
    lv, lf = ring_prism(0, 0, 3.06, 3.28, 0.13, 0.10, 6)
    mb.add(xf(lv, loc=(cx + 0.66, cy - dr - 0.55, 0)), lf, "WarmGlass")
    cv, cf = ring_prism(0, 0, 3.28, 3.34, 0.10, 0.03, 6)
    mb.add(xf(cv, loc=(cx + 0.66, cy - dr - 0.55, 0)), cf, "GoldDark")

    # ---- wooden balcony / shores ------------------------------------------
    bth = math.radians(312)
    bz = 7.55
    br = _lh_r((bz - z0) / hgt) + 0.10
    bcx, bcy = _lh_c((bz - z0) / hgt)
    for k in (-0.30, 0.0, 0.30):
        bx = bcx + br * math.cos(bth) - k * math.cos(bth + math.pi / 2)
        by = bcy + br * math.sin(bth) - k * math.sin(bth + math.pi / 2)
        pv, pf = box_c(1.15, 0.24, 0.13,
                       (bx + 0.56 * math.cos(bth), by + 0.56 * math.sin(bth), bz + 0.02), rot_z=bth)
        mb.add(pv, pf, "Wood")
    for k in (-0.34, 0.30):
        px = bcx + (br + 0.94) * math.cos(bth) + k * math.cos(bth + math.pi / 2)
        py = bcy + (br + 0.94) * math.sin(bth) + k * math.sin(bth + math.pi / 2)
        pv, pf = box_c(0.13, 0.13, 0.95, (px, py, bz + 0.52), rot_z=bth)
        mb.add(pv, pf, "WoodDark")
    mb.add(*tube([(bcx + (br + 0.10) * math.cos(bth), bcy + (br + 0.10) * math.sin(bth), bz - 0.68),
                  (bcx + (br + 1.04) * math.cos(bth), bcy + (br + 1.04) * math.sin(bth), bz - 0.02)],
                 [0.11, 0.09], sides=4), "WoodDark")

    for az in (205, 243):
        t = 0.55
        r = _lh_r(t) + 0.05
        ex, ey = _lh_c(t)
        aa = math.radians(az)
        sx, sy = 4.30 * math.cos(aa), 4.30 * math.sin(aa)
        mb.add(*tube([(sx, sy, 0.15), (ex + r * math.cos(aa), ey + r * math.sin(aa), 6.55)],
                     [0.15, 0.10], sides=4), "WoodDark")
        mb.add(*tube([(sx, sy, 0.15), (sx + 0.55 * math.cos(aa + math.pi / 2),
                                       sy + 0.55 * math.sin(aa + math.pi / 2), 0.15)],
                     [0.13, 0.10], sides=4), "Wood")

    # ---- gallery -----------------------------------------------------------
    mb.add(*ring_prism(0, 0, 11.30, 11.72, 2.78, 2.56, 8, rot0=2.15), "StoneLight")
    mb.add(*ring_prism(0, 0, 11.72, 11.95, 2.40, 2.34, 8, rot0=2.20), "Stone")
    for k in range(8):
        aa = 2 * math.pi * k / 8 + 0.2
        mb.add(*ring_segment_solid(1.95, 2.66, 11.00, 11.30, aa, aa + 0.34), "StoneDark")

    post_angles = [2 * math.pi * k / 9 + 0.1 for k in range(9)]
    broken = {6, 7}
    for k, aa in enumerate(post_angles):
        if k in broken:
            continue
        px, py = 2.20 * math.cos(aa), 2.20 * math.sin(aa)
        h = 0.92 if k != 4 else 0.55
        pv, pf = box_c(0.14, 0.14, h, (px, py, 11.95 + h / 2), rot_z=aa)
        mb.add(pv, pf, "Stone")
    for k in range(9):
        if k in broken or (k + 1) % 9 in broken:
            continue
        aa0 = post_angles[k]
        aa1 = post_angles[(k + 1) % 9] + (2 * math.pi if k == 8 else 0)
        mb.add(*ring_segment_solid(2.13, 2.25, 12.80, 12.91, aa0, aa1), "WoodDark")
        if k % 2 == 0:
            mb.add(*ring_segment_solid(2.15, 2.24, 12.36, 12.43, aa0, aa1), "Wood")

    # small lantern hanging from the gallery rail
    lth = math.radians(282)
    lpx, lpy = 2.18 * math.cos(lth), 2.18 * math.sin(lth)
    mb.add(*tube([(lpx, lpy, 12.88), (lpx, lpy, 12.55)], [0.02, 0.02], sides=4), "WoodDark")
    lv, lf = ring_prism(0, 0, 12.30, 12.53, 0.11, 0.14, 6)
    mb.add(xf(lv, loc=(lpx, lpy, 0)), lf, "WarmGlass")
    cv, cf = ring_prism(0, 0, 12.53, 12.57, 0.15, 0.05, 6)
    mb.add(xf(cv, loc=(lpx, lpy, 0)), cf, "GoldDark")

    # ---- ruined lamp room --------------------------------------------------
    mb.add(*ring_prism(0, 0, 11.95, 12.42, 1.68, 1.62, 8, rot0=2.20), "Stone")
    mb.add(*ring_prism(0, 0, 12.42, 12.49, 1.67, 1.63, 8, rot0=2.20), "StoneLight")

    posts_top = []
    post_tops = []
    for k in range(8):
        aa = 2 * math.pi * k / 8 + 0.20
        px, py = 1.47 * math.cos(aa), 1.47 * math.sin(aa)
        h = 2.05
        if k == 4:
            h = 1.60
        elif k == 5:
            h = 1.15
        elif k == 6:
            h = 1.85
        pv, pf = box_c(0.15, 0.15, h, (px, py, 12.49 + h / 2), rot_z=aa)
        mb.add(pv, pf, "Wood")
        posts_top.append((px, py, 12.49 + h))
        post_tops.append(12.49 + h)

    # warm panes only on the back sectors; the seaward side is blown open
    pane_specs = [(0, 14.10), (1, 14.05), (2, 13.75), (3, 13.90), (7, 13.55)]
    for k, top in pane_specs:
        aa0 = 2 * math.pi * k / 8 + 0.20
        aa1 = aa0 + 2 * math.pi / 8
        top = min(top, post_tops[k] - 0.12, post_tops[(k + 1) % 8] - 0.12)
        mb.add(*ring_segment_solid(1.395, 1.435, 12.52, top, aa0 + 0.04, aa1 - 0.04), "WarmGlass")
        # wooden rail across the pane
        mb.add(*ring_segment_solid(1.36, 1.48, top - 0.16, top - 0.08, aa0 + 0.03, aa1 - 0.03), "WoodDark")

    # broken strips of glass still hanging in the open sectors
    for k, zz in [(4, 13.75), (5, 13.30)]:
        aa0 = 2 * math.pi * k / 8 + 0.20
        aa1 = aa0 + 2 * math.pi / 8
        mb.add(*ring_segment_solid(1.395, 1.43, zz, zz + 0.42, aa0 + 0.10, aa1 - 0.22), "WarmGlass")

    # rafters: the seaward half is gone
    apex = (0.20, -0.08, 15.18)
    rafters = {}
    for k in range(8):
        if k in (4, 5):
            continue
        p1 = posts_top[k]
        mb.add(*tube([p1, apex], [0.075, 0.045], sides=4), "WoodDark")
        rafters[k] = p1

    def roof_panel(i, j, lift=0.0):
        p1 = rafters[i]
        p2 = rafters[j]
        ap = (apex[0], apex[1], apex[2] + lift)
        poly = [p1, p2, ap]
        ux, uy, uz = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
        vx, vy, vz = (ap[0] - p1[0], ap[1] - p1[1], ap[2] - p1[2])
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        half = (nx / ln * 0.06, ny / ln * 0.06, nz / ln * 0.06)
        mb.add(*slab_outline(poly, half), "Roof")

    roof_panel(0, 1)
    roof_panel(1, 2)
    roof_panel(2, 3)
    # wind-torn roof shard hanging over the open side
    mb.add(*slab_outline([(0.30, 0.10, 14.95), (1.15, 0.95, 14.05), (1.35, 0.55, 14.62)],
                         (0.05, 0.05, 0.05)), "Roof")

    # residual lamp core, rings and chain
    mb.add(*icosphere(1, 0.40, (1.0, 1.0, 1.0), (0.10, 0.0, 13.30)), "LampCore")
    mb.add(*torus(0.62, 0.045, 10, 4, (0.10, 0.0, 13.30), (math.pi / 2, 0, 0)), "Gold")
    mb.add(*torus(0.52, 0.040, 10, 4, (0.10, 0.0, 13.30), (0.6, 0.4, 0)), "GoldDark")
    mb.add(*tube([(0.14, 0.0, 14.62), (0.10, 0.0, 13.70)], [0.022, 0.022], sides=4), "GoldDark")
    for a in (0.4, 2.4, 4.4):
        mb.add(*icosphere(0, 0.065, (1, 1, 1), (0.10 + 0.88 * math.cos(a), 0.88 * math.sin(a), 13.55)), "Gold")

    # broken mast / weather vane reaching 16 m
    mb.add(*tube([(0.20, -0.08, 15.18), (0.38, -0.18, 15.62), (0.68, -0.36, 16.00)],
                 [0.075, 0.048, 0.012], sides=5), "WoodDark")
    mb.add(*torus(0.10, 0.020, 8, 4, (0.38, -0.18, 15.62), (math.pi / 2, 0, 0)), "Gold")
    mb.add(*slab_outline([(0.44, -0.21, 15.82), (0.44, -0.21, 15.46), (0.98, -0.48, 15.64)],
                         (0.008, 0.0, 0.0)), "Tassel")

    # long crack on the seaward face
    for (az, zz0, zz1) in [(247, 7.9, 9.05), (251, 5.7, 6.75)]:
        aa = math.radians(az)
        t = (zz0 - z0) / hgt
        r = _lh_r(t) + 0.015
        cxx, cyy = _lh_c(t)
        p1 = (cxx + r * math.cos(aa), cyy + r * math.sin(aa), zz0)
        p2 = (cxx + (r + 0.04) * math.cos(aa + 0.04), cyy + (r + 0.04) * math.sin(aa + 0.04), zz1)
        mb.add(*tube([p1, p2], [0.030, 0.012], sides=4), "StoneDark")

    return mb


def build_whale_ribs():
    """14 m long, 8 m high whale ribcage arcade along local Y, half buried in sand."""
    mb = MB()
    rnd = random.Random(29)
    rib_ys = [-5.75, -3.45, -1.15, 1.15, 3.45, 5.75]

    # spine: a chunky bony beam along Y
    spine_pts = []
    spine_radii = []
    for i in range(15):
        t = i / 14.0
        y = -7.0 + 14.0 * t
        z = 6.62 + 0.12 * math.cos(y * 0.7) - 0.26 * (abs(y) / 7.0) ** 3
        spine_pts.append((0.0, y, z))
        spine_radii.append(0.34 + 0.20 * (1.0 - abs(y) / 7.0))
    mb.add(*tube(spine_pts, spine_radii, sides=6, ref=(1, 0, 0)),
           lambda i: "BoneStain" if (i // 6) in (0, 1, 13, 14) else "Bone")

    def spine_z(y):
        return 6.62 + 0.12 * math.cos(y * 0.7) - 0.26 * (abs(y) / 7.0) ** 3

    # vertebra collars and dorsal processes
    collar_ys = []
    for i in range(6):
        collar_ys.append(rib_ys[i])
        if i < 5:
            collar_ys.append((rib_ys[i] + rib_ys[i + 1]) / 2.0)
    for j, cy in enumerate(collar_ys):
        z = spine_z(cy)
        mb.add(*tube([(0, cy - 0.22, z), (0, cy + 0.22, z)], [0.64, 0.64], sides=6, ref=(1, 0, 0)),
               "BoneStain" if j % 3 == 0 else "Bone")
        if j % 2 == 1:
            mb.add(*tube([(0.0, cy, z + 0.30), (0.34, cy + 0.62, 7.05)], [0.20, 0.02], sides=4), "Bone")
        for side in (-1, 1):
            if j % 2 == 0:
                mb.add(*tube([(side * 0.38, cy, z), (side * 1.62, cy + 0.30, z - 0.26)],
                             [0.14, 0.05], sides=4), "BoneStain")

    # six pairs of ribs attaching to the sides of the spine
    spreads = [1.00, 1.04, 1.02, 0.99, 0.94, 0.88]
    heights = [1.00, 1.00, 1.01, 1.00, 0.97, 0.93]
    rib_mat = lambda i: "BoneStain" if (i * 37) % 11 < 3 or (i // 6) == 0 else "Bone"
    for k, y0 in enumerate(rib_ys):
        for side in (-1, 1):
            pts = []
            spread = 5.55 * spreads[k]
            hf = heights[k]
            for i in range(9):
                t = i / 8.0
                ang = t * math.pi / 2.0
                x = side * (0.85 + (spread - 0.85) * math.cos(ang))
                z = 7.50 * hf * math.sin(ang)
                y = y0 + 0.78 * (t ** 1.35)
                pts.append((x, y, z))
            radii = [0.30, 0.36, 0.42, 0.47, 0.50, 0.52, 0.52, 0.50, 0.46]
            mb.add(*tube(pts, radii, sides=6, ref=(0, 1, 0)), rib_mat)
            for ji in (3, 6):
                mb.add(*icosphere(0, radii[ji] * 0.66, (1.0, 1.0, 1.0), pts[ji]),
                       "BoneStain" if ji == 3 else "Bone")
            # flared, buried foot
            mb.add(*icosphere(0, 0.42, (1.0, 1.0, 0.62), (side * spread, y0, 0.18),
                              (0, 0, rnd.random() * 6.28), flatten_z=0.0), "BoneStain")
            # bulky rib head where it meets the spine
            mb.add(*icosphere(0, 0.30, (1.0, 1.0, 1.0), (side * 0.85, y0 + 0.78, 7.50 * hf)), "BoneStain")

    # small sand drifts burying each foot
    for yi, y0 in enumerate(rib_ys):
        for side in (-1, 1):
            mb.add(*icosphere(1, 1.0, (1.25, 1.00, 0.55), (side * 5.45, y0 + 0.05, 0.0),
                              (0, 0, 0), flatten_z=0.0), "Sand" if yi % 2 == 0 else "SandLight")

    # loose bones half-buried in the sand
    for (x, y, a, ln, r) in [(4.3, -3.6, 0.5, 2.4, 0.15), (-4.0, 4.2, 1.1, 2.0, 0.13),
                             (2.8, 5.9, -0.4, 1.7, 0.10)]:
        pts = [(x + math.cos(a) * ln * u, y + math.sin(a) * ln * u, 0.32 + 0.06 * math.sin(u * 3.0))
               for u in (0.0, 0.4, 0.75, 1.0)]
        mb.add(*tube(pts, [r, r * 0.9, r * 0.65, r * 0.35], sides=4), "BoneStain")
    mb.add(*torus(0.50, 0.18, 8, 4, (-3.9, 2.6, 0.34), (0.10, 0.0, 0.0)), "BoneDark")

    return mb


def _whale_stations():
    return [
        (-29.20, 0.55, 0.35, 0.30, 0.05),
        (-28.80, 2.00, 1.10, 1.00, 0.10),
        (-27.60, 3.60, 1.90, 1.60, 0.20),
        (-25.80, 4.90, 2.70, 2.20, 0.30),
        (-23.00, 5.90, 3.40, 2.70, 0.30),
        (-19.50, 6.70, 4.00, 3.20, 0.20),
        (-15.00, 7.05, 4.40, 3.70, 0.00),
        (-9.50, 7.10, 4.50, 3.90, -0.15),
        (-3.50, 6.80, 4.40, 3.90, -0.15),
        (2.50, 6.30, 4.10, 3.80, 0.00),
        (8.00, 5.70, 3.60, 3.40, 0.15),
        (13.00, 4.60, 2.90, 2.80, 0.30),
        (17.50, 3.30, 2.10, 2.00, 0.45),
        (21.00, 2.10, 1.40, 1.30, 0.60),
        (24.00, 1.30, 0.90, 0.85, 0.65),
        (26.00, 0.80, 0.55, 0.50, 0.70),
    ]


def build_sky_whale():
    """60 m low-poly star whale, facing -Y, origin at body centre, <= 8000 tris."""
    mb = MB()
    ST = _whale_stations()

    def interp(y):
        if y <= ST[0][0]:
            return ST[0][1:]
        if y >= ST[-1][0]:
            return ST[-1][1:]
        for i in range(len(ST) - 1):
            if ST[i][0] <= y <= ST[i + 1][0]:
                f = (y - ST[i][0]) / (ST[i + 1][0] - ST[i][0])
                return tuple(ST[i][1 + j] + (ST[i + 1][1 + j] - ST[i][1 + j]) * f for j in range(4))
        return ST[-1][1:]

    def surf(y, deg, off=0.0):
        rx, ru, rd, zc = interp(y)
        a = math.radians(deg)
        ca, sa = math.cos(a), math.sin(a)
        rz = ru if sa >= 0 else rd
        x = rx * ca
        z = zc + rz * sa
        nx, nz = ca / max(rx, 0.01), sa / max(rz, 0.01)
        ln = math.sqrt(nx * nx + nz * nz) or 1.0
        return (x + nx / ln * off, y, z + nz / ln * off)

    # ---- body -------------------------------------------------------------
    SEG = 12
    rings = []
    for (y, rx, ru, rd, zc) in ST:
        ring = []
        for i in range(SEG):
            a = 2 * math.pi * i / SEG
            ca, sa = math.cos(a), math.sin(a)
            rz = ru if sa >= 0 else rd
            ring.append((rx * ca, y, zc + rz * sa))
        rings.append(ring)

    verts = []
    for r in rings:
        verts.extend(r)
    # pointed snout
    tip = (0.0, -29.35, 0.05)
    verts.append(tip)
    ti = len(verts) - 1
    faces = []
    mats = []
    for k in range(len(rings) - 1):
        for i in range(SEG):
            a0 = k * SEG + i
            b0 = k * SEG + (i + 1) % SEG
            c0 = (k + 1) * SEG + (i + 1) % SEG
            d0 = (k + 1) * SEG + i
            faces.append((a0, b0, c0, d0))
            fy = sum(verts[j][1] for j in (a0, b0, c0, d0)) / 4.0
            fz = sum(verts[j][2] for j in (a0, b0, c0, d0)) / 4.0
            rx, ru, rd, zc = interp(fy)
            mats.append("WhaleBelly" if fz < zc + 0.02 * rd else "WhaleBack")
    # snout triangles
    for i in range(SEG):
        faces.append((ti, i, (i + 1) % SEG))
        mats.append("WhaleBack")
    # tail cap
    end0 = (len(rings) - 1) * SEG
    faces.append(tuple(reversed(range(end0, end0 + SEG))))
    mats.append("WhaleBack")
    mb.add(verts, faces, mats)

    # flattened chin ridge under the jaw
    mb.add(*icosphere(1, 1.0, (3.6, 4.8, 0.78), (0.0, -23.2, -2.55)), "WhaleBelly")

    # ---- pectoral fins: long broad blades hanging down and sweeping back --
    for s in (-1, 1):
        lead = [(s * 6.0, -24.0, -0.6), (s * 8.5, -21.0, -3.2),
                (s * 10.8, -17.0, -6.2), (s * 11.8, -13.0, -8.2)]
        trail = [(s * 6.0, -17.0, -2.0), (s * 8.0, -13.5, -5.0),
                 (s * 9.8, -10.5, -7.2), (s * 10.9, -9.6, -8.0)]
        mb.add(*thick_strip(lead, trail, 0.35, (1, 0, 0)), "WhaleFin")

    # ---- tail flukes: wide V, tips lifted so they read in profile -------
    for s in (-1, 1):
        lead = [(s * 0.0, 24.8, 0.60), (s * 3.5, 27.2, 1.40),
                (s * 7.4, 29.0, 3.00), (s * 10.4, 30.2, 4.60)]
        trail = [(s * 0.5, 25.2, 0.55), (s * 5.6, 25.8, 0.90),
                 (s * 8.4, 26.6, 1.80), (s * 9.6, 27.2, 3.00)]
        mb.add(*thick_strip(lead, trail, 0.28, (0, 0, 1)), "WhaleFin")

    # ---- dorsal fin -------------------------------------------------------
    mb.add(*slab_outline([(0.0, 5.5, 3.85), (0.0, 9.8, 6.40), (0.0, 12.8, 3.55)],
                         (0.35, 0.0, 0.0)), "WhaleFin")

    # ---- eyes, mouth, blowhole, throat grooves ---------------------------
    for deg in (18, 162):
        socket = surf(-24.0, deg, 0.02)
        mb.add(*icosphere(0, 0.60, (1.0, 1.0, 0.80), socket), "WhaleMouth")
        eye = surf(-24.0, deg, 0.32)
        mb.add(*icosphere(0, 0.33, (1.0, 1.0, 1.0), eye), "WhaleEye")
    for side in (-1, 1):
        base_deg = -12 if side == 1 else 192
        pts = [surf(-28.6 + 10.6 * u, base_deg - 4 * u, 0.10) for u in (0.0, 0.3, 0.6, 1.0)]
        mb.add(*tube(pts, [0.14, 0.12, 0.09, 0.05], sides=4), "WhaleMouth")
    for deg in (258, 270, 282):
        pts = [surf(-24.0 + 9.0 * u, deg, 0.05) for u in (0.0, 0.35, 0.7, 1.0)]
        mb.add(*tube(pts, [0.07, 0.08, 0.07, 0.05], sides=4), "WhaleGroove")
    bh = surf(-23.0, 90, 0.10)
    mb.add(*icosphere(0, 0.40, (1.4, 0.8, 0.16), (bh[0], bh[1], bh[2])), "WhaleMouth")

    # ---- constellation: gold dots + fine geometric lines on the back ----
    dots = [
        (-20.0, 78, 0.72), (-16.5, 64, 0.55), (-13.0, 98, 0.80), (-9.5, 76, 0.60),
        (-6.0, 110, 0.70), (-2.5, 60, 0.62), (1.0, 88, 0.90), (4.5, 68, 0.56),
        (8.0, 102, 0.66), (11.5, 80, 0.55), (14.5, 112, 0.50), (-11.0, 56, 0.52),
        (-4.0, 120, 0.55), (6.0, 122, 0.50), (12.5, 94, 0.46),
    ]
    dot_pos = []
    for (y, deg, r) in dots:
        p = surf(y, deg, 0.14)
        dot_pos.append(p)
        mb.add(*icosphere(0, r * 0.82, (1.0, 1.0, 1.0), p), "StarGold")
    links = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9),
             (9, 10), (2, 11), (4, 12), (8, 13), (13, 14), (1, 11), (3, 12), (7, 13)]
    for (ia, ib) in links:
        ya, da, _ = dots[ia]
        yb, db, _ = dots[ib]
        pts = []
        for k in range(5):
            u = k / 4.0
            pts.append(surf(ya + (yb - ya) * u, da + (db - da) * u, 0.12))
        mb.add(*tube(pts, [0.075] * 5, sides=4), "StarGold")

    # a few smaller companion stars
    for (y, deg, r) in [(-18.5, 120, 0.30), (-7.5, 45, 0.28), (3.0, 132, 0.26),
                        (10.0, 55, 0.28), (16.0, 85, 0.30)]:
        mb.add(*icosphere(0, r, (1.0, 1.0, 1.0), surf(y, deg, 0.12)), "StarGold")

    return mb


# ----------------------------------------------------------------------------
# Build / export / render driver
# ----------------------------------------------------------------------------
ASSETS = [
    {
        "name": "beacon_lantern", "builder": build_beacon_lantern, "ground": True,
        "elev": 14, "azim": 36, "dist": 2.8,
        "tags": ["landmark", "chapter_goal", "lantern", "stone", "moss", "gold", "emissive"],
        "use": "Chapter-goal beacon on a ridge; light it when the chapter goal completes, add a real light inside the paper shade.",
    },
    {
        "name": "paper_lantern", "builder": build_paper_lantern, "ground": False,
        "elev": 18, "azim": 35, "dist": 3.2,
        "tags": ["collectible", "lantern", "paper", "warm_glow", "floating"],
        "use": "Guiding paper lantern; floats in place, bob and rotate slowly, attach a small warm light.",
    },
    {
        "name": "ember_collectible", "builder": build_ember_collectible, "ground": False,
        "elev": 12, "azim": 40, "dist": 2.9,
        "tags": ["collectible", "ember", "crystal", "emissive", "floating"],
        "use": "Collectible ember; hover, spin and pulse, pickup burst at the player's chest height.",
    },
    {
        "name": "memory_shard", "builder": build_memory_shard, "ground": True,
        "elev": 14, "azim": 38, "dist": 3.05,
        "tags": ["interactive", "memory", "standing_stone", "glow", "moss", "vines"],
        "use": "Memory interaction prop; prompt the memory panel when the player is near the glowing leaf.",
    },
    {
        "name": "lighthouse", "builder": build_lighthouse, "ground": True,
        "elev": 11, "azim": 38, "dist": 2.8,
        "alt_elev": 48, "alt_azim": 56,
        "lights": [
            {"loc": (0.10, 0.0, 13.30), "energy": 460.0, "color": (1.0, 0.70, 0.40), "radius": 0.45},
            {"loc": (0.20, -0.08, 14.75), "energy": 90.0, "color": (1.0, 0.74, 0.46), "radius": 0.5},
        ],
        "tags": ["hero_landmark", "lighthouse", "ruin", "spiral", "broken", "warm_light", "coastal"],
        "use": "Chapter 3/4 hero landmark; use as the distant silhouette and the climbable finale tower, light the lamp room on completion.",
    },
    {
        "name": "whale_ribs", "builder": build_whale_ribs, "ground": True,
        "elev": 11, "azim": 24, "dist": 2.75,
        "alt_elev": 48, "alt_azim": 46,
        "tags": ["hero_landmark", "whale_bone", "desert", "arcade", "sand", "walk_through"],
        "use": "Amberreach desert landmark / whale-bone inn; walk and ride through the archway, camp at its feet.",
    },
    {
        "name": "sky_whale", "builder": build_sky_whale, "ground": False,
        "elev": 18, "azim": 42, "dist": 2.55,
        "alt_elev": 45, "alt_azim": 55, "alt_dist": 2.5,
        "tags": ["hero_landmark", "sky_whale", "star_constellation", "emissive", "creature", "night"],
        "use": "Skybox-scale hero creature drifting above the isles; slow bob and tail sway, constellation readable from below.",
    },
    {
        "name": "cloud_puff", "builder": build_cloud_puff, "ground": False,
        "elev": 18, "azim": 35, "dist": 2.7,
        "tags": ["sky", "cloud", "modular", "environment"],
        "use": "Sky and island-base filler; scale and duplicate to build cloud seas around the isles.",
    },
    {
        "name": "bird", "builder": build_bird, "ground": False,
        "elev": 52, "azim": 32, "dist": 2.6,
        "tags": ["ambient", "bird", "silhouette", "sky"],
        "use": "Ambient flying silhouette; spawn small flocks and move them on simple looping paths.",
    },
]


def run_asset(spec):
    name = spec["name"]
    print("\n=== %s ===" % name, flush=True)
    built = spec["builder"]()
    obj = built.build(name) if isinstance(built, MB) else built
    obj.name = name
    obj.data.name = name
    obj.location = (0, 0, 0)
    obj.rotation_euler = (0, 0, 0)
    obj.scale = (1, 1, 1)

    # seat grounded assets exactly on z=0 without moving the object origin
    if spec.get("ground") and len(obj.data.vertices):
        dz = -min(v.co.z for v in obj.data.vertices)
        if abs(dz) > 1e-4:
            for v in obj.data.vertices:
                v.co.z += dz
            obj.data.update()
            bpy.context.view_layer.update()

    mn, mx = object_bbox(obj)
    tris = tris_of(obj)
    print("[build] %s tris=%d bounds min=(%.2f, %.2f, %.2f) max=(%.2f, %.2f, %.2f)"
          % (name, tris, mn[0], mn[1], mn[2], mx[0], mx[1], mx[2]), flush=True)

    # export only the asset mesh
    os.makedirs(MODEL_DIR, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    out_glb = os.path.join(MODEL_DIR, name + ".glb")
    bpy.ops.export_scene.gltf(
        filepath=out_glb,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
    )
    print("[export] %s" % out_glb, flush=True)

    record = {
        "name": name,
        "file": "assets/models/relics/%s.glb" % name,
        "bounds": {
            "min": [round(v, 3) for v in mn],
            "max": [round(v, 3) for v in mx],
            "size": [round(mx[i] - mn[i], 3) for i in range(3)],
        },
        "tris": tris,
        "tags": spec["tags"],
        "suggested_use": spec["use"],
    }

    if not SKIP_RENDER:
        os.makedirs(PREVIEW_DIR, exist_ok=True)
        radius = 0.5 * math.sqrt(sum((mx[i] - mn[i]) ** 2 for i in range(3)))
        ground = make_ground(radius) if spec.get("ground") else None
        points = add_point_lights(spec.get("lights", []))
        try:
            render_view(obj, os.path.join(PREVIEW_DIR, name + ".png"),
                        spec.get("elev", 18), spec.get("azim", 35), spec.get("dist", 3.15))
            if spec.get("alt_elev") is not None:
                render_view(obj, os.path.join(PREVIEW_DIR, name + "_top.png"),
                            spec["alt_elev"], spec.get("alt_azim", spec.get("azim", 35)),
                            spec.get("alt_dist", 2.95))
        finally:
            remove_objects([ground] + points)

    # clear asset (keep rig)
    remove_objects([obj])
    return record


def write_manifest(records):
    os.makedirs(MODEL_DIR, exist_ok=True)
    existing = {}
    if os.path.exists(MANIFEST):
        try:
            with open(MANIFEST, "r", encoding="utf-8") as f:
                old = json.load(f)
            for a in old.get("assets", []):
                existing[a.get("name")] = a
        except Exception:
            existing = {}
    for r in records:
        existing[r["name"]] = r
    ordered = [existing[s["name"]] for s in ASSETS if s["name"] in existing]
    total = sum(a["tris"] for a in ordered)
    doc = {
        "batch": "relics",
        "description": "Narrative relics and wonder landmarks for Lantern Isles (flat-shaded low poly).",
        "unit": "metre",
        "up_axis_blender": "Z",
        "forward_blender": "-Y",
        "count": len(ordered),
        "total_tris": total,
        "contact_sheet": "assets/previews/relics/contact_sheet.png",
        "assets": ordered,
    }
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print("\n[manifest] %s (%d assets, %d tris)" % (MANIFEST, len(ordered), total), flush=True)


def main():
    reset_scene()
    init_materials()
    add_light_rig()
    records = []
    for spec in ASSETS:
        if ONLY and spec["name"] not in ONLY:
            continue
        records.append(run_asset(spec))
    if records:
        write_manifest(records)


# ----------------------------------------------------------------------------
# Contact sheet (system python / Pillow)
# ----------------------------------------------------------------------------
def make_contact_sheet():
    from PIL import Image, ImageDraw, ImageFont

    os.makedirs(PREVIEW_DIR, exist_ok=True)
    entries = [
        ("01", "beacon_lantern", "beacon_lantern.png", 0),
        ("02", "paper_lantern", "paper_lantern.png", 1),
        ("03", "ember_collectible", "ember_collectible.png", 2),
        ("04", "memory_shard", "memory_shard.png", 3),
        ("05", "lighthouse", "lighthouse.png", 4),
        ("05b", "lighthouse - 45 deg top", "lighthouse_top.png", 4),
        ("06", "whale_ribs", "whale_ribs.png", 5),
        ("06b", "whale_ribs - 45 deg top", "whale_ribs_top.png", 5),
        ("07", "sky_whale", "sky_whale.png", 6),
        ("07b", "sky_whale - 45 deg top", "sky_whale_top.png", 6),
        ("08", "cloud_puff", "cloud_puff.png", 7),
        ("09", "bird", "bird.png", 8),
    ]
    tris_by_name = {}
    if os.path.exists(MANIFEST):
        try:
            with open(MANIFEST, "r", encoding="utf-8") as f:
                for a in json.load(f).get("assets", []):
                    tris_by_name[a["name"]] = a["tris"]
        except Exception:
            pass

    bg = (233, 224, 207)
    ink = (66, 56, 46)
    sub = (128, 114, 96)
    tile = 380
    gap = 18
    margin = 28
    label_h = 42
    header_h = 96
    cols = 4
    rows = (len(entries) + cols - 1) // cols
    width = margin * 2 + cols * tile + (cols - 1) * gap
    height = header_h + margin + rows * (tile + label_h) + (rows - 1) * gap + margin

    img = Image.new("RGB", (width, height), bg)
    d = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype(os.path.join(FONT_DIR, "Marcellus-Regular.ttf"), 30)
        label_font = ImageFont.truetype(os.path.join(FONT_DIR, "Marcellus-Regular.ttf"), 18)
        small_font = ImageFont.truetype(os.path.join(FONT_DIR, "Marcellus-Regular.ttf"), 13)
    except Exception:
        title_font = label_font = small_font = ImageFont.load_default()

    d.text((margin, 24), "LANTERN ISLES  /  RELICS BATCH", font=title_font, fill=ink)
    d.text((margin, 62), "9 narrative assets  -  3 hero landmarks  -  flat-shaded low poly",
           font=small_font, fill=sub)
    d.line([(margin, 86), (width - margin, 86)], fill=(196, 181, 156), width=1)

    total_tris = sum(tris_by_name.get(e[1], 0) for e in entries if e[3] >= 0 and e[0].isdigit() and len(e[0]) == 2)
    d.text((width - margin - 210, 64), "%d tris total" % total_tris, font=small_font, fill=sub)

    for idx, (num, label, fname, asset_idx) in enumerate(entries):
        r, c = divmod(idx, cols)
        x = margin + c * (tile + gap)
        y = header_h + margin + r * (tile + label_h + gap)
        path = os.path.join(PREVIEW_DIR, fname)
        if os.path.exists(path):
            im = Image.open(path).convert("RGB").resize((tile, tile), Image.LANCZOS)
            img.paste(im, (x, y))
        else:
            d.rectangle([x, y, x + tile, y + tile], fill=(220, 210, 193))
            d.text((x + tile // 2, y + tile // 2), "missing", font=label_font, fill=sub, anchor="mm")
        d.rectangle([x, y, x + tile, y + tile], outline=(198, 184, 159), width=1)
        d.text((x + 2, y + tile + 8), "%s  %s" % (num, label), font=label_font, fill=ink)
        t = tris_by_name.get(entries[idx][1])
        if t:
            d.text((x + tile - 2, y + tile + 12), "%s tris" % format(t, ","), font=small_font, fill=sub, anchor="ra")

    img.save(CONTACT_SHEET, quality=95)
    print("[contact] %s (%dx%d)" % (CONTACT_SHEET, width, height))


if not HAS_BPY:
    make_contact_sheet()
elif __name__ == "__main__":
    main()
