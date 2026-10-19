class_name WorldBuilder
extends Node3D

## Assembles a chapter from the generated heightfield data + Blender kit.
## Everything here is runtime-generated so the same builder can host all four
## chapters and any future additions.

signal interactable_built(node: Node3D)
signal zone_entered(zone_name: String)

const MODEL_PATHS := {
	"cherry_tree_a": "res://assets/models/foliage/cherry_tree_a.glb",
	"cherry_tree_b": "res://assets/models/foliage/cherry_tree_b.glb",
	"bamboo_cluster": "res://assets/models/foliage/bamboo_cluster.glb",
	"azalea_bush": "res://assets/models/foliage/azalea_bush.glb",
	"fern": "res://assets/models/foliage/fern.glb",
	"grass_tuft": "res://assets/models/foliage/grass_tuft.glb",
	"lilypad": "res://assets/models/foliage/lilypad.glb",
	"glow_tree": "res://assets/models/foliage/glow_tree.glb",
	"glow_mushroom": "res://assets/models/foliage/glow_mushroom.glb",
	"koi": "res://assets/models/foliage/koi.glb",
	"palm_tree": "res://assets/models/foliage/palm_tree.glb",
	"desert_shrub": "res://assets/models/foliage/desert_shrub.glb",
	"cactus": "res://assets/models/foliage/cactus.glb",
	"reeds": "res://assets/models/foliage/reeds.glb",
	"pine_tree_a": "res://assets/models/foliage/pine_tree_a.glb",
	"pine_tree_b": "res://assets/models/foliage/pine_tree_b.glb",
	"snow_bush": "res://assets/models/foliage/snow_bush.glb",
	"bare_tree": "res://assets/models/foliage/bare_tree.glb",
	"ice_crystal": "res://assets/models/foliage/ice_crystal.glb",
	"glow_grass": "res://assets/models/foliage/glow_grass.glb",
	"rock_a": "res://assets/models/rocks/rock_a.glb",
	"rock_b": "res://assets/models/rocks/rock_b.glb",
	"rock_c": "res://assets/models/rocks/rock_c.glb",
	"cliff_spire": "res://assets/models/rocks/cliff_spire.glb",
	"sandstone_arch": "res://assets/models/rocks/sandstone_arch.glb",
	"floating_rock": "res://assets/models/rocks/floating_rock.glb",
	"crystal_cluster": "res://assets/models/rocks/crystal_cluster.glb",
	"stump": "res://assets/models/rocks/stump.glb",
	"driftwood": "res://assets/models/rocks/driftwood.glb",
	"torii_gate": "res://assets/models/architecture/torii_gate.glb",
	"stone_lantern": "res://assets/models/architecture/stone_lantern.glb",
	"moss_shrine": "res://assets/models/architecture/moss_shrine.glb",
	"wooden_cabin": "res://assets/models/architecture/wooden_cabin.glb",
	"market_tent": "res://assets/models/architecture/market_tent.glb",
	"rope_bridge": "res://assets/models/architecture/rope_bridge.glb",
	"stone_bridge": "res://assets/models/architecture/stone_bridge.glb",
	"ruin_pillar": "res://assets/models/architecture/ruin_pillar.glb",
	"signpost": "res://assets/models/architecture/signpost.glb",
	"well": "res://assets/models/architecture/well.glb",
	"beacon_lantern": "res://assets/models/relics/beacon_lantern.glb",
	"paper_lantern": "res://assets/models/relics/paper_lantern.glb",
	"ember_collectible": "res://assets/models/relics/ember_collectible.glb",
	"memory_shard": "res://assets/models/relics/memory_shard.glb",
	"lighthouse": "res://assets/models/relics/lighthouse.glb",
	"whale_ribs": "res://assets/models/relics/whale_ribs.glb",
	"sky_whale": "res://assets/models/relics/sky_whale.glb",
	"cloud_puff": "res://assets/models/relics/cloud_puff.glb",
	"bird": "res://assets/models/relics/bird.glb",
}

const ALIASES := {
	"big_cherry": "cherry_tree_a",
	"beacon": "beacon_lantern",
	"ember": "ember_collectible",
}

const TREE_TYPES := [
	"cherry_tree_a", "cherry_tree_b", "big_cherry", "bamboo_cluster", "glow_tree", "palm_tree",
	"pine_tree_a", "pine_tree_b", "bare_tree", "snow_bush", "azalea_bush",
]

const COLLIDERS := {
	"cherry_tree_a": ["cyl", 0.36, 2.8],
	"big_cherry": ["cyl", 0.5, 3.4],
	"cherry_tree_b": ["cyl", 0.5, 2.4],
	"bamboo_cluster": ["cyl", 0.45, 3.0],
	"pine_tree_a": ["cyl", 0.38, 3.4],
	"pine_tree_b": ["cyl", 0.3, 2.7],
	"palm_tree": ["cyl", 0.32, 3.2],
	"bare_tree": ["cyl", 0.3, 2.4],
	"glow_tree": ["cyl", 0.35, 2.8],
	"rock_a": ["cyl", 0.95, 1.4],
	"rock_c": ["cyl", 1.2, 1.0],
	"stone_lantern": ["cyl", 0.32, 2.2],
	"ruin_pillar": ["cyl", 0.45, 3.0],
	"signpost": ["cyl", 0.22, 2.0],
	"well": ["cyl", 1.1, 1.8],
	"cactus": ["cyl", 0.5, 2.8],
	"wooden_cabin": ["box", 4.2, 3.4, 3.6],
	"market_tent": ["box", 3.6, 2.6, 3.0],
	"lighthouse": ["box", 4.2, 12.0, 4.2],
	"moss_shrine": ["box", 2.4, 2.8, 2.0],
	"torii_gate": [],
	"rope_bridge": [],
	"stone_bridge": [],
}

var world: Dictionary = {}
var chapter: Dictionary = {}
var chapter_index: int = 0
var grid_n: int = 100
var cell: float = 1.6
var heights: PackedFloat32Array = PackedFloat32Array()
var road: PackedFloat32Array = PackedFloat32Array()

var env_data: Dictionary = {}
var spawn_position: Vector3 = Vector3.ZERO
var spawn_yaw: float = 0.0

var props_root: Node3D
var multi_root: Node3D
var interact_root: Node3D
var distant_root: Node3D
var collision_body: StaticBody3D
var terrain_instance: MeshInstance3D

var interactables: Array = []
var zones: Array = []
var _whale: Node3D
var _whale_base: Vector3
var _koi: Array = []
var _rng := RandomNumberGenerator.new()
var _mat_cache: Dictionary = {}
var _foliage_cache: Dictionary = {}
var _missing: Dictionary = {}
var _lantern_lights: Array = []
var _time := 0.0


func build(index: int, meta: Dictionary, data: Dictionary) -> void:
	chapter_index = index
	chapter = meta
	world = data
	env_data = data.get("env", {})
	grid_n = int(data.get("n", 100))
	cell = float(data.get("cell", 1.6))
	var flat_h: Array = data.get("h", [])
	var flat_r: Array = data.get("road", [])
	heights.resize(flat_h.size())
	for i in flat_h.size():
		heights[i] = float(flat_h[i])
	road.resize(flat_r.size())
	for i in flat_r.size():
		road[i] = float(flat_r[i])
	var sp: Array = data.get("spawn", [0, 0, 0])
	spawn_position = Vector3(float(sp[0]), float(sp[1]), float(sp[2]))
	spawn_yaw = float(data.get("spawn_yaw", 0.0))
	_rng.seed = 7000 + index * 991

	props_root = Node3D.new()
	props_root.name = "Props"
	add_child(props_root)
	multi_root = Node3D.new()
	multi_root.name = "Details"
	add_child(multi_root)
	interact_root = Node3D.new()
	interact_root.name = "Interactables"
	add_child(interact_root)
	distant_root = Node3D.new()
	distant_root.name = "Distant"
	add_child(distant_root)
	collision_body = StaticBody3D.new()
	collision_body.name = "PropCollision"
	collision_body.collision_layer = 1
	collision_body.collision_mask = 0
	add_child(collision_body)

	_build_environment()
	_build_terrain()
	_build_paths()
	_build_water()
	_build_props()
	_build_petals()
	_build_multi()
	_build_bridges()
	_build_interactables()
	_build_skyline()
	_build_particles()
	set_process(true)



# ------------------------------------------------------------------ data ----
func h_at(u: int, v: int) -> float:
	u = clampi(u, 0, grid_n)
	v = clampi(v, 0, grid_n)
	return heights[v * (grid_n + 1) + u]


func h_world(x: float, z: float) -> float:
	var fx := (x / cell) + grid_n * 0.5
	var fz := (z / cell) + grid_n * 0.5
	fx = clampf(fx, 0.0, grid_n - 0.001)
	fz = clampf(fz, 0.0, grid_n - 0.001)
	var u := int(fx)
	var v := int(fz)
	var tx := fx - u
	var tz := fz - v
	return lerpf(
		lerpf(h_at(u, v), h_at(u + 1, v), tx),
		lerpf(h_at(u, v + 1), h_at(u + 1, v + 1), tx),
		tz
	)


func road_at(u: int, v: int) -> float:
	u = clampi(u, 0, grid_n)
	v = clampi(v, 0, grid_n)
	return road[v * (grid_n + 1) + u]


func _palette(key: String, fallback: Color) -> Color:
	var v = world.get("palette", {}).get(key, "")
	if v is String and v != "":
		return Color(v)
	return fallback


# ------------------------------------------------------------ environment ---
func _build_environment() -> void:
	var sky_mat := ShaderMaterial.new()
	sky_mat.shader = load("res://shaders/sky.gdshader")
	sky_mat.set_shader_parameter("top_color", Color(str(env_data.get("sky_top", "#8fbdb8"))))
	sky_mat.set_shader_parameter("horizon_color", Color(str(env_data.get("sky_horizon", "#f9e4c4"))))
	sky_mat.set_shader_parameter("bottom_color", Color(str(env_data.get("sky_bottom", "#5e8f86"))))
	sky_mat.set_shader_parameter("sun_color", Color(str(env_data.get("sun_color", "#ffe3b0"))))
	sky_mat.set_shader_parameter("cloud_color", Color(str(env_data.get("fog", "#cfe4d8"))).lightened(0.12))
	var ang: Array = env_data.get("sun_angle", [-42, -38])
	var sun_rot := Vector3(deg_to_rad(float(ang[0])), deg_to_rad(float(ang[1])), 0.0)
	var sun_dir := -Vector3.UP.rotated(Vector3.RIGHT, sun_rot.x).rotated(Vector3.UP, sun_rot.y)
	sky_mat.set_shader_parameter("sun_direction", sun_dir)
	sky_mat.set_shader_parameter("sun_glow", 1.1)
	sky_mat.set_shader_parameter("star_amount", float(env_data.get("star", 0.0)))
	sky_mat.set_shader_parameter("aurora_amount", float(env_data.get("aurora", 0.0)))
	sky_mat.set_shader_parameter("cloud_amount", 0.32)

	var sky := Sky.new()
	sky.sky_material = sky_mat
	sky.process_mode = Sky.PROCESS_MODE_REALTIME
	sky.radiance_size = Sky.RADIANCE_SIZE_256

	var e := Environment.new()
	e.background_mode = Environment.BG_SKY
	e.sky = sky
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(str(env_data.get("ambient", "#a9c4b3")))
	e.ambient_light_energy = float(env_data.get("ambient_energy", 0.62))
	e.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	e.tonemap_mode = Environment.TONE_MAPPER_ACES
	e.tonemap_exposure = float(env_data.get("exposure", 1.05))
	e.tonemap_white = 6.0

	e.fog_enabled = true
	e.fog_light_color = Color(str(env_data.get("fog", "#cfe4d8")))
	e.fog_light_energy = 0.8
	e.fog_density = float(env_data.get("fog_density", 0.003))
	e.fog_sky_affect = 0.22
	e.fog_height = 6.0
	e.fog_height_density = 0.012

	e.volumetric_fog_enabled = true
	e.volumetric_fog_density = clampf(float(env_data.get("fog_density", 0.003)) * 0.62, 0.0012, 0.0032)
	e.volumetric_fog_albedo = Color(str(env_data.get("fog", "#cfe4d8")))
	e.volumetric_fog_emission = Color(0, 0, 0)
	e.volumetric_fog_length = 96.0
	e.volumetric_fog_detail_spread = 2.0
	e.volumetric_fog_anisotropy = 0.25
	e.volumetric_fog_ambient_inject = 0.2

	e.glow_enabled = true
	e.glow_intensity = float(env_data.get("glow", 0.85))
	e.glow_strength = 1.1
	e.glow_bloom = 0.09
	e.glow_hdr_threshold = 0.9
	e.glow_blend_mode = Environment.GLOW_BLEND_MODE_SCREEN

	e.ssao_enabled = true
	e.ssao_radius = 1.3
	e.ssao_intensity = 2.0
	e.ssao_power = 1.4
	e.ssao_detail = 0.7
	e.ssil_enabled = false

	e.adjustment_enabled = true
	e.adjustment_brightness = 1.0
	e.adjustment_contrast = 1.04
	e.adjustment_saturation = float(env_data.get("saturation", 1.0))

	var we := WorldEnvironment.new()
	we.environment = e
	add_child(we)

	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.rotation_degrees = Vector3(float(ang[0]), float(ang[1]), 0.0)
	sun.light_color = Color(str(env_data.get("sun_color", "#ffe3b0")))
	sun.light_energy = float(env_data.get("sun_energy", 1.45))
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sun.directional_shadow_max_distance = 80.0
	sun.directional_shadow_fade_start = 0.8
	sun.shadow_blur = 3.2
	sun.shadow_bias = 0.04
	sun.shadow_opacity = 0.48
	sun.shadow_normal_bias = 1.6
	sun.light_angular_distance = 1.5
	add_child(sun)

	var fill := DirectionalLight3D.new()
	fill.name = "SkyFill"
	fill.rotation_degrees = Vector3(-24, float(ang[1]) + 150.0, 0.0)
	fill.light_color = Color(str(env_data.get("ambient", "#a9c4b3"))).lightened(0.15)
	fill.light_energy = 0.55
	fill.shadow_enabled = false
	add_child(fill)

	var rim := DirectionalLight3D.new()
	rim.name = "Rim"
	rim.rotation_degrees = Vector3(-12, float(ang[1]) - 90.0, 0.0)
	rim.light_color = Color(str(env_data.get("sun_color", "#ffe3b0"))).lerp(Color.WHITE, 0.4)
	rim.light_energy = 0.18
	rim.shadow_enabled = false
	add_child(rim)


# --------------------------------------------------------------- terrain ---
func _face_color(center: Vector3, normal: Vector3) -> Color:
	var slope := 1.0 - clampf(normal.y, 0.0, 1.0)
	var grass_a := _palette("grass_a", Color("#6f9468"))
	var grass_b := _palette("grass_b", Color("#89a86f"))
	var grass_c := _palette("grass_c", Color("#a9bc7c"))
	var rock := _palette("rock", Color("#7e8878"))
	var rock_dark := _palette("rock_dark", Color("#5b665c"))
	var path := _palette("path", Color("#c9b994"))
	var path_dark := _palette("path_dark", Color("#a89978"))
	var shore := _palette("shore", Color("#d8c9a5"))
	var accent := _palette("accent", Color("#e7b0ae"))

	var n1 := _hash(Vector2(center.x * 0.071, center.z * 0.071))
	var n2 := _hash(Vector2(center.x * 0.17 + 7.7, center.z * 0.17 + 3.1))
	var n3 := _hash(Vector2(center.x * 0.43 + 2.2, center.z * 0.43 + 9.4))
	var col := grass_a.lerp(grass_b, n1)
	col = col.lerp(grass_c, smoothstep(0.55, 0.95, n2) * 0.55)
	# warm/cool per-triangle mosaic
	col = col * (0.94 + 0.1 * n3)
	# exposed rock on steep faces
	var rocky := smoothstep(0.26, 0.62, slope)
	col = col.lerp(rock.lerp(rock_dark, n2 * 0.7), rocky)
	col = col.lerp(rock_dark, smoothstep(0.72, 0.95, slope) * 0.45)
	# path
	var rmask := _road_sample(center.x, center.z)
	if rmask > 0.05:
		var pcol := path.lerp(path_dark, n2 * 0.55)
		col = col.lerp(pcol, clampf(rmask * 0.97, 0.0, 0.97))
	# water shore
	for w in world.get("water", []):
		var wx := float(w.get("x", 0.0))
		var wz := float(w.get("z", 0.0))
		var wr := float(w.get("r", 0.0))
		var wl := float(w.get("level", 0.0))
		var d := Vector2(center.x - wx, center.z - wz).length()
		if d < wr * 1.55 and center.y < wl + 1.7:
			var shore_w := smoothstep(wr * 1.55, wr * 0.9, d) * 0.72
			col = col.lerp(shore, shore_w)
	# spring blossom dust on flat warm patches
	if chapter_index == 0:
		col = col.lerp(accent, smoothstep(0.86, 1.0, n1) * 0.1 * (1.0 - rocky))
	if chapter_index == 3:
		col = col.lerp(Color("#6d6590"), smoothstep(0.65, 0.9, n3) * 0.12)

	# subtle altitude lift so high ridges read pale
	var alt := clampf((center.y - 2.0) / 26.0, 0.0, 1.0)
	col = col.lerp(col.lightened(0.1), alt * 0.3)
	col = col * 0.96
	return col.srgb_to_linear()


func _road_sample(x: float, z: float) -> float:
	var fx := (x / cell) + grid_n * 0.5
	var fz := (z / cell) + grid_n * 0.5
	fx = clampf(fx, 0.0, grid_n - 0.001)
	fz = clampf(fz, 0.0, grid_n - 0.001)
	var u := int(fx)
	var v := int(fz)
	var tx := fx - u
	var tz := fz - v
	return lerpf(
		lerpf(road_at(u, v), road_at(u + 1, v), tx),
		lerpf(road_at(u, v + 1), road_at(u + 1, v + 1), tx),
		tz
	)


func _hash(p: Vector2) -> float:
	var v := sin(p.dot(Vector2(127.1, 311.7))) * 43758.5453
	return v - floor(v)


func _build_terrain() -> void:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var faces := PackedVector3Array()
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/terrain.gdshader")
	mat.set_shader_parameter("night_glow", 1.0 if chapter_index == 3 else 0.0)
	mat.set_shader_parameter("moisture", 0.45 if chapter_index == 0 else (0.18 if chapter_index == 1 else 0.3))
	st.set_material(mat)

	var n := grid_n
	var thresh := -5.5
	for v in n:
		for u in n:
			if not _cell_drawn(u, v):
				continue
			var h00 := h_at(u, v)
			var h10 := h_at(u + 1, v)
			var h01 := h_at(u, v + 1)
			var h11 := h_at(u + 1, v + 1)
			var x0 := (u - n * 0.5) * cell
			var x1 := (u + 1 - n * 0.5) * cell
			var z0 := (v - n * 0.5) * cell
			var z1 := (v + 1 - n * 0.5) * cell
			var a := Vector3(x0, h00, z0)
			var b := Vector3(x1, h10, z0)
			var c := Vector3(x0, h01, z1)
			var d := Vector3(x1, h11, z1)
			_add_top_tri(st, faces, a, b, c)
			_add_top_tri(st, faces, b, d, c)
			# outer skirts: draw wherever the neighbour cell is void
			_skirt_edge(st, faces, u, v, 0)
			_skirt_edge(st, faces, u, v, 1)
			_skirt_edge(st, faces, u, v, 2)
			_skirt_edge(st, faces, u, v, 3)

	var mesh := st.commit()
	terrain_instance = MeshInstance3D.new()
	terrain_instance.name = "Terrain"
	terrain_instance.mesh = mesh
	terrain_instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	add_child(terrain_instance)

	var body := StaticBody3D.new()
	body.name = "TerrainCollision"
	body.collision_layer = 1
	body.collision_mask = 0
	var shape := CollisionShape3D.new()
	var concave := ConcavePolygonShape3D.new()
	concave.backface_collision = true
	concave.set_faces(faces)
	shape.shape = concave
	body.add_child(shape)
	add_child(body)


func _add_top_tri(st: SurfaceTool, faces: PackedVector3Array, a: Vector3, b: Vector3, c: Vector3) -> void:
	var nrm := (c - a).cross(b - a).normalized()
	if nrm.y < 0.0:
		nrm = -nrm
	var center := (a + b + c) / 3.0
	var col := _face_color(center, nrm)
	# Godot's SurfaceTool is a stream; normals/colors apply to following vertices.
	st.set_normal(nrm)
	st.set_color(col)
	st.add_vertex(a)
	st.set_normal(nrm)
	st.set_color(col)
	st.add_vertex(b)
	st.set_normal(nrm)
	st.set_color(col)
	st.add_vertex(c)
	faces.append(a)
	faces.append(b)
	faces.append(c)


func _cell_drawn(u: int, v: int) -> bool:
	if u < 0 or v < 0 or u >= grid_n or v >= grid_n:
		return false
	var a := h_at(u, v)
	var b := h_at(u + 1, v)
	var c := h_at(u, v + 1)
	var d := h_at(u + 1, v + 1)
	return min(min(a, b), min(c, d)) > -5.5


func _skirt_edge(st: SurfaceTool, faces: PackedVector3Array, u: int, v: int, direction: int) -> void:
	var n := grid_n
	var nu := u
	var nv := v
	match direction:
		0: nu = u - 1
		1: nu = u + 1
		2: nv = v - 1
		3: nv = v + 1
	if _cell_drawn(nu, nv):
		return
	var x0 := (u - n * 0.5) * cell
	var x1 := (u + 1 - n * 0.5) * cell
	var z0 := (v - n * 0.5) * cell
	var z1 := (v + 1 - n * 0.5) * cell
	var p0: Vector3
	var p1: Vector3
	var out_normal: Vector3
	match direction:
		0:
			p0 = Vector3(x0, h_at(u, v), z0)
			p1 = Vector3(x0, h_at(u, v + 1), z1)
			out_normal = Vector3.LEFT
		1:
			p0 = Vector3(x1, h_at(u + 1, v), z0)
			p1 = Vector3(x1, h_at(u + 1, v + 1), z1)
			out_normal = Vector3.RIGHT
		2:
			p0 = Vector3(x0, h_at(u, v), z0)
			p1 = Vector3(x1, h_at(u + 1, v), z0)
			out_normal = Vector3.FORWARD
		_:
			p0 = Vector3(x0, h_at(u, v + 1), z1)
			p1 = Vector3(x1, h_at(u + 1, v + 1), z1)
			out_normal = Vector3.BACK
	var bottom := -26.0 + _hash(Vector2(float(u), float(v))) * 5.0
	var q0 := Vector3(p0.x, bottom, p0.z)
	var q1 := Vector3(p1.x, bottom, p1.z)
	var rock := _palette("rock_dark", Color("#5b665c")).srgb_to_linear()
	var rock2 := _palette("rock", Color("#7e8878")).srgb_to_linear()
	var c0 := rock.lerp(rock2, 0.15 + _hash(Vector2(u, v)) * 0.25)
	var c1 := rock.lerp(rock2, 0.3 + _hash(Vector2(v, u)) * 0.2)
	# draw both windings so cliffs never disappear
	for order in [[p0, q0, p1], [p1, q0, q1], [p0, q1, p1], [p0, q0, q1]]:
		st.set_normal(out_normal)
		st.set_color(c0 if order[0] == p0 else c1)
		for p in order:
			st.add_vertex(p)
			faces.append(p)


# ---------------------------------------------------------------- paths ---
func _path_material() -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/path_stone.gdshader")
	var cols := [
		[Color("#7E806E"), Color("#A19C83"), Color("#50564B"), Color("#5A754F"), Color("#A98C61")],
		[Color("#A9794E"), Color("#C29A68"), Color("#69442F"), Color("#6F7B47"), Color("#C39B67")],
		[Color("#73868A"), Color("#A8B8B8"), Color("#465A5F"), Color("#7F9C9A"), Color("#C6D3D0")],
		[Color("#4B4764"), Color("#6E6889"), Color("#2C2940"), Color("#557F7D"), Color("#5A5168")],
	]
	var c: Array = cols[chapter_index % 4]
	mat.set_shader_parameter("stone_a", c[0])
	mat.set_shader_parameter("stone_b", c[1])
	mat.set_shader_parameter("mortar", c[2])
	mat.set_shader_parameter("moss_color", c[3])
	mat.set_shader_parameter("edge_dirt", c[4])
	mat.set_shader_parameter("glow", 0.55 if chapter_index == 3 else 0.0)
	return mat


func _build_paths() -> void:
	_build_plaza()
	_build_stepping_stones()


func _path_tri(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3,
		ua: Vector2, ub: Vector2, uc: Vector2) -> void:
	var n: Vector3 = (b - a).cross(c - a).normalized()
	if n.y < 0.0:
		n = -n
	st.set_normal(n)
	st.set_uv(ua)
	st.add_vertex(a)
	st.set_normal(n)
	st.set_uv(ub)
	st.add_vertex(b)
	st.set_normal(n)
	st.set_uv(uc)
	st.add_vertex(c)


func _build_stepping_stones() -> void:
	var paths: Array = world.get("paths", [])
	if paths.is_empty():
		return
	var transforms: Array = []
	for path in paths:
		var pts_raw: Array = path.get("pts", [])
		if pts_raw.size() < 2:
			continue
		var pts: Array[Vector2] = []
		for p in pts_raw:
			pts.append(Vector2(float(p[0]), float(p[1])))
		var accum := 0.0
		var next := 2.6
		var side := 1.0
		for i in pts.size() - 1:
			var a := pts[i]
			var b := pts[i + 1]
			var seg := a.distance_to(b)
			if seg < 0.05:
				continue
			while next <= accum + seg:
				var t: float = (next - accum) / seg
				var pos := a.lerp(b, t)
				var dir := (b - a).normalized()
				var perp := Vector2(-dir.y, dir.x)
				var off := perp * 0.75 * side * sin(next * 0.23)
				var wp := pos + off
				var gy := h_world(wp.x, wp.y) + 0.035
				var near_spawn := Vector2(wp.x - spawn_position.x, wp.y - spawn_position.z).length() < 7.0
				var near_bridge := false
				for br in world.get("bridges", []):
					if Vector2(wp.x - float(br["x"]), wp.y - float(br["z"])).length() < 8.0:
						near_bridge = true
						break
				if not near_spawn and not near_bridge and gy > -1.0:
					transforms.append([wp.x, gy, wp.y, _rng.randf() * TAU, _rng.randf_range(0.8, 1.25)])
					side *= -1.0
				next += 2.6
			accum += seg
	if transforms.is_empty():
		return
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var n := 7
	var radii: Array[float] = []
	for i in n:
		radii.append(0.62 + _rng.randf_range(-0.1, 0.14))
	for i in n:
		var a0 := TAU * float(i) / float(n)
		var a1 := TAU * float(i + 1) / float(n)
		var r0: float = radii[i]
		var r1: float = radii[(i + 1) % n]
		var p0 := Vector3(cos(a0) * r0, 0.07, sin(a0) * r0)
		var p1 := Vector3(cos(a1) * r1, 0.07, sin(a1) * r1)
		for tri in [[Vector3(0, 0.07, 0), p0, p1]]:
			st.set_normal(Vector3.UP)
			for v in tri:
				st.add_vertex(v)
		# short side
		var q0 := Vector3(p0.x, 0.0, p0.z)
		var q1 := Vector3(p1.x, 0.0, p1.z)
		for tri in [[p0, q0, p1], [p1, q0, q1]]:
			var ta: Vector3 = tri[0]
			var tb: Vector3 = tri[1]
			var tc: Vector3 = tri[2]
			var nrm: Vector3 = (tb - ta).cross(tc - ta).normalized()
			st.set_normal(nrm)
			for v in tri:
				st.add_vertex(v)
	var stone_mesh := st.commit()
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(str(world.get("palette", {}).get("rock", "#7E8878"))).lightened(0.04)
	mat.roughness = 0.95
	stone_mesh.surface_set_material(0, mat)
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = stone_mesh
	mm.instance_count = transforms.size()
	for i in transforms.size():
		var tr: Array = transforms[i]
		var basis := Basis(Vector3.UP, float(tr[3])).scaled(Vector3(float(tr[4]), 1.0, float(tr[4])))
		mm.set_instance_transform(i, Transform3D(basis, Vector3(float(tr[0]), float(tr[1]), float(tr[2]))))
	var mmi := MultiMeshInstance3D.new()
	mmi.name = "SteppingStones"
	mmi.multimesh = mm
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mmi)


func _build_plaza() -> void:
	var center := spawn_position
	var radius := 6.2
	var seg := 40
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var cpos := Vector3(center.x, h_world(center.x, center.z) + 0.055, center.z)
	for i in seg:
		var a0 := TAU * float(i) / float(seg)
		var a1 := TAU * float(i + 1) / float(seg)
		var rr0 := radius * (0.93 + 0.05 * sin(a0 * 6.0 + chapter_index))
		var rr1 := radius * (0.93 + 0.05 * sin(a1 * 6.0 + chapter_index))
		var p0 := Vector3(center.x + cos(a0) * rr0, 0.0, center.z + sin(a0) * rr0)
		var p1 := Vector3(center.x + cos(a1) * rr1, 0.0, center.z + sin(a1) * rr1)
		p0.y = h_world(p0.x, p0.z) + 0.06
		p1.y = h_world(p1.x, p1.z) + 0.06
		_path_tri(st, cpos, p0, p1, Vector2(0.5, 0.5), Vector2(0.5, 0.0), Vector2(0.5, 1.0))
	var mi := MeshInstance3D.new()
	mi.name = "Plaza"
	mi.mesh = st.commit()
	var mat := _path_material()
	mat.set_shader_parameter("edge_dirt", Color(str(world.get("palette", {}).get("path", "#A98C61"))))
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	# a flat apron of darker stone around the plaza edge
	var ring_st := SurfaceTool.new()
	ring_st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var ring_seg := 36
	for i in ring_seg:
		var a0 := TAU * float(i) / float(ring_seg)
		var a1 := TAU * float(i + 1) / float(ring_seg)
		var inner := radius - 0.05
		var outer := radius + 0.72
		var i0 := Vector3(center.x + cos(a0) * inner, 0, center.z + sin(a0) * inner)
		var i1 := Vector3(center.x + cos(a1) * inner, 0, center.z + sin(a1) * inner)
		var o0 := Vector3(center.x + cos(a0) * outer, 0, center.z + sin(a0) * outer)
		var o1 := Vector3(center.x + cos(a1) * outer, 0, center.z + sin(a1) * outer)
		i0.y = h_world(i0.x, i0.z) + 0.028
		i1.y = h_world(i1.x, i1.z) + 0.028
		o0.y = h_world(o0.x, o0.z) + 0.028
		o1.y = h_world(o1.x, o1.z) + 0.028
		_path_tri(ring_st, i0, o0, i1, Vector2(0.0, 0.0), Vector2(0.0, 1.0), Vector2(1.0, 1.0))
		_path_tri(ring_st, i1, o0, o1, Vector2(1.0, 1.0), Vector2(0.0, 1.0), Vector2(1.0, 0.0))
	var ring_mesh := ring_st.commit()
	var ring_mat := StandardMaterial3D.new()
	ring_mat.albedo_color = Color(str(world.get("palette", {}).get("rock", "#7E806E"))).darkened(0.12)
	ring_mat.roughness = 0.96
	ring_mesh.surface_set_material(0, ring_mat)
	var ring := MeshInstance3D.new()
	ring.name = "PlazaApron"
	ring.mesh = ring_mesh
	ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(ring)


# ---------------------------------------------------------------- water ---
func _build_water() -> void:
	for w in world.get("water", []):
		var style := str(w.get("style", "pond"))
		var cx := float(w.get("x", 0.0))
		var cz := float(w.get("z", 0.0))
		var r := float(w.get("r", 4.0))
		var level := float(w.get("level", 0.0))
		var seg := 48
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		var center := Vector3(cx, level, cz)
		for i in seg:
			var a0 := TAU * float(i) / float(seg)
			var a1 := TAU * float(i + 1) / float(seg)
			var r0 := r * (1.0 + 0.045 * sin(a0 * 5.0 + chapter_index * 1.7))
			var r1 := r * (1.0 + 0.045 * sin(a1 * 5.0 + chapter_index * 1.7))
			var p0 := Vector3(cx + cos(a0) * r0, level, cz + sin(a0) * r0)
			var p1 := Vector3(cx + cos(a1) * r1, level, cz + sin(a1) * r1)
			st.set_normal(Vector3.UP)
			st.add_vertex(center)
			st.add_vertex(p1)
			st.add_vertex(p0)
		var mesh := st.commit()
		var mat := ShaderMaterial.new()
		mat.shader = load("res://shaders/water.gdshader")
		var is_ice := style == "frozen_lake" or style == "creek"
		var deep := Color("#2f6f6b")
		var shallow := Color("#7bb9ad")
		var glow := 0.0
		var flow := 0.5
		match style:
			"oasis", "grotto":
				deep = Color("#2f7f79"); shallow = Color("#86cfbf"); flow = 0.7
			"hotspring":
				deep = Color("#4b8d80"); shallow = Color("#b7e0cc"); flow = 0.35
			"frozen_lake", "creek":
				deep = Color("#6e9aa5"); shallow = Color("#c6e1e2"); flow = 0.0
			"mirror":
				deep = Color("#203f56"); shallow = Color("#5c9ba7"); glow = 0.45; flow = 0.18
		mat.set_shader_parameter("deep_color", deep)
		mat.set_shader_parameter("shallow_color", shallow)
		mat.set_shader_parameter("glow_color", Color("#9fe6dc"))
		mat.set_shader_parameter("flow_speed", flow)
		mat.set_shader_parameter("ripple_strength", 0.18 if is_ice else 0.65)
		mat.set_shader_parameter("ice", 1.0 if is_ice else 0.0)
		mat.set_shader_parameter("glow", glow)
		mat.set_shader_parameter("opacity", 0.96 if is_ice else 0.82)
		var mi := MeshInstance3D.new()
		mi.name = "Water_" + style
		mi.mesh = mesh
		mi.material_override = mat
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mi)
		if style == "hotspring":
			_add_steam(Vector3(cx, level + 0.4, cz), r)
		if style == "mirror":
			_add_mirror_sparkles(Vector3(cx, level + 0.3, cz), r)


func _add_steam(pos: Vector3, radius: float) -> void:
	var p := GPUParticles3D.new()
	p.amount = 42
	p.lifetime = 4.0
	p.preprocess = 2.0
	p.position = pos
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	pm.emission_sphere_radius = radius * 0.6
	pm.direction = Vector3.UP
	pm.spread = 18.0
	pm.initial_velocity_min = 0.35
	pm.initial_velocity_max = 0.9
	pm.gravity = Vector3(0, 0.12, 0)
	pm.scale_min = 0.4
	pm.scale_max = 1.1
	pm.color = Color(0.82, 0.92, 0.87, 0.24)
	pm.damping_min = 0.1
	pm.damping_max = 0.3
	p.process_material = pm
	var quad := QuadMesh.new()
	quad.size = Vector2(1.5, 1.5)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.albedo_color = Color(0.9, 0.97, 0.93, 0.16)
	m.vertex_color_use_as_albedo = true
	quad.material = m
	p.draw_pass_1 = quad
	add_child(p)


func _add_mirror_sparkles(pos: Vector3, radius: float) -> void:
	var p := GPUParticles3D.new()
	p.amount = 80
	p.lifetime = 6.0
	p.preprocess = 4.0
	p.position = pos
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	pm.emission_sphere_radius = radius
	pm.direction = Vector3.UP
	pm.spread = 30.0
	pm.initial_velocity_min = 0.02
	pm.initial_velocity_max = 0.15
	pm.gravity = Vector3(0, 0.02, 0)
	pm.scale_min = 0.3
	pm.scale_max = 1.0
	pm.color = Color(0.65, 0.95, 0.9, 0.8)
	p.process_material = pm
	var quad := QuadMesh.new()
	quad.size = Vector2(0.28, 0.28)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.albedo_color = Color(0.7, 0.98, 0.9, 0.8)
	m.emission_enabled = true
	m.emission = Color(0.55, 0.95, 0.85)
	m.emission_energy_multiplier = 3.0
	quad.material = m
	p.draw_pass_1 = quad
	add_child(p)


# ----------------------------------------------------------------- props ---
func _model_path(type: String) -> String:
	var t := type
	if ALIASES.has(t):
		t = ALIASES[t]
	return MODEL_PATHS.get(t, "")


func _load_scene(type: String) -> PackedScene:
	var path := _model_path(type)
	if path == "" or not ResourceLoader.exists(path):
		return null
	var res = load(path)
	if res is PackedScene:
		return res
	return null


func _missing_warn(type: String) -> void:
	if _missing.has(type):
		return
	_missing[type] = true
	push_warning("Model missing, using placeholder: " + type)


func _fallback_mesh(type: String) -> Node3D:
	_missing_warn(type)
	var root := Node3D.new()
	var body := MeshInstance3D.new()
	var mesh: PrimitiveMesh
	var col := Color("#7e8878")
	var height := 1.0
	var radius := 0.5
	match type:
		"cherry_tree_a", "cherry_tree_b", "big_cherry":
			height = 5.5
			body.mesh = CylinderMesh.new()
			(body.mesh as CylinderMesh).top_radius = 0.18
			(body.mesh as CylinderMesh).bottom_radius = 0.38
			(body.mesh as CylinderMesh).height = 4.2
			body.position.y = 2.1
			col = Color("#5d4a3e")
			root.add_child(body)
			var crown := MeshInstance3D.new()
			var cm := SphereMesh.new()
			cm.radius = 2.2
			cm.height = 3.2
			crown.mesh = cm
			crown.position.y = 5.2
			var mat := _mat(Color("#e7b0ae"))
			crown.material_override = mat
			root.add_child(crown)
			return root
		"pine_tree_a", "pine_tree_b":
			height = 7.0
			body.mesh = CylinderMesh.new()
			(body.mesh as CylinderMesh).top_radius = 0.1
			(body.mesh as CylinderMesh).bottom_radius = 0.3
			(body.mesh as CylinderMesh).height = 3.4
			body.position.y = 1.7
			col = Color("#4c453b")
			root.add_child(body)
			for i in 3:
				var cone := MeshInstance3D.new()
				var co := CylinderMesh.new()
				co.top_radius = 0.05
				co.bottom_radius = 1.5 - i * 0.28
				co.height = 2.4
				cone.mesh = co
				cone.position.y = 3.0 + i * 1.35
				cone.material_override = _mat(Color("#2f5450").lightened(i * 0.035))
				root.add_child(cone)
			return root
		"rock_a", "rock_b", "rock_c":
			height = 1.2
			var sphere := SphereMesh.new()
			sphere.radius = 0.9
			sphere.height = 1.4
			body.mesh = sphere
			body.position.y = 0.55
			body.scale = Vector3(1.0, 0.55, 0.8)
			col = Color("#7e8878")
		"torii_gate":
			root.add_child(_box(Vector3(0.28, 4.6, 0.28), Color("#a9503f"), Vector3(-1.8, 2.3, 0)))
			root.add_child(_box(Vector3(0.28, 4.6, 0.28), Color("#a9503f"), Vector3(1.8, 2.3, 0)))
			root.add_child(_box(Vector3(5.0, 0.28, 0.38), Color("#8d4436"), Vector3(0, 4.7, 0)))
			root.add_child(_box(Vector3(4.2, 0.18, 0.3), Color("#8d4436"), Vector3(0, 3.8, 0)))
			return root
		"stone_lantern":
			root.add_child(_box(Vector3(0.7, 0.28, 0.7), Color("#8f9689"), Vector3(0, 0.14, 0)))
			root.add_child(_box(Vector3(0.26, 1.3, 0.26), Color("#8f9689"), Vector3(0, 0.85, 0)))
			root.add_child(_box(Vector3(0.7, 0.55, 0.7), Color("#a0a795"), Vector3(0, 1.75, 0)))
			var glow := _box(Vector3(0.4, 0.3, 0.4), Color("#f2b15e"), Vector3(0, 1.75, 0), true)
			root.add_child(glow)
			root.add_child(_box(Vector3(0.9, 0.16, 0.9), Color("#7e8878"), Vector3(0, 2.15, 0)))
			return root
		"moss_shrine":
			root.add_child(_box(Vector3(2.6, 0.4, 2.2), Color("#7e8878"), Vector3(0, 0.2, 0)))
			root.add_child(_box(Vector3(2.0, 1.8, 1.7), Color("#65584a"), Vector3(0, 1.3, 0)))
			root.add_child(_box(Vector3(2.8, 0.3, 2.4), Color("#4c5c4e"), Vector3(0, 2.35, 0)))
			root.add_child(_box(Vector3(0.5, 0.8, 0.1), Color("#f2b15e"), Vector3(0, 1.3, -0.9), true))
			return root
		"wooden_cabin":
			root.add_child(_box(Vector3(5.2, 3.2, 4.0), Color("#6b5548"), Vector3(0, 1.6, 0)))
			root.add_child(_box(Vector3(5.8, 0.35, 4.6), Color("#dde6e2"), Vector3(0, 3.4, 0)))
			root.add_child(_box(Vector3(0.9, 1.0, 0.1), Color("#f2b15e"), Vector3(-1.2, 1.8, -2.03), true))
			root.add_child(_box(Vector3(0.9, 1.0, 0.1), Color("#f2b15e"), Vector3(1.2, 1.8, -2.03), true))
			return root
		"market_tent":
			root.add_child(_box(Vector3(5.0, 0.25, 4.2), Color("#d9a45e"), Vector3(0, 2.8, 0)))
			for x in [-2.2, 2.2]:
				root.add_child(_box(Vector3(0.16, 2.8, 0.16), Color("#6b5548"), Vector3(x, 1.4, -1.8)))
				root.add_child(_box(Vector3(0.16, 2.8, 0.16), Color("#6b5548"), Vector3(x, 1.4, 1.8)))
			root.add_child(_box(Vector3(0.9, 0.7, 0.9), Color("#8a5f42"), Vector3(-1.4, 0.35, 1.0)))
			return root
		"ruin_pillar":
			root.add_child(_box(Vector3(0.8, 0.3, 0.8), Color("#8f9689"), Vector3(0, 0.15, 0)))
			root.add_child(_box(Vector3(0.55, 2.8, 0.55), Color("#9aa195"), Vector3(0, 1.65, 0)))
			return root
		"well":
			root.add_child(_box(Vector3(1.8, 0.8, 1.8), Color("#8f9689"), Vector3(0, 0.4, 0)))
			root.add_child(_box(Vector3(1.4, 0.1, 1.4), Color("#3f6f70"), Vector3(0, 0.8, 0)))
			root.add_child(_box(Vector3(0.15, 1.5, 0.15), Color("#6b5548"), Vector3(-0.7, 1.55, 0)))
			root.add_child(_box(Vector3(0.15, 1.5, 0.15), Color("#6b5548"), Vector3(0.7, 1.55, 0)))
			root.add_child(_box(Vector3(1.7, 0.15, 0.15), Color("#6b5548"), Vector3(0, 2.25, 0)))
			return root
		"signpost":
			root.add_child(_box(Vector3(0.15, 1.8, 0.15), Color("#6b5548"), Vector3(0, 0.9, 0)))
			root.add_child(_box(Vector3(1.2, 0.3, 0.1), Color("#8a6b4c"), Vector3(0.45, 1.55, 0)))
			return root
		"lighthouse":
			height = 14.0
			var cyl := CylinderMesh.new()
			cyl.top_radius = 0.9
			cyl.bottom_radius = 2.0
			cyl.height = 12.0
			body.mesh = cyl
			body.position.y = 6.0
			col = Color("#7d8e8e")
			root.add_child(body)
			var top := MeshInstance3D.new()
			var tm := CylinderMesh.new()
			tm.top_radius = 1.15
			tm.bottom_radius = 1.15
			tm.height = 1.4
			top.mesh = tm
			top.position.y = 12.4
			top.material_override = _mat(Color("#f2b15e"), 2.0)
			root.add_child(top)
			return root
		"whale_ribs":
			var bone := Color("#e7dfc9")
			for i in 6:
				var z := -4.5 + i * 1.8
				var r0: float = 1.2 + abs(i - 2.5) * 0.45
				var curve := Node3D.new()
				curve.position = Vector3(0, 0, z)
				root.add_child(curve)
				for s in [-1, 1]:
					var rib := MeshInstance3D.new()
					var tor := TorusMesh.new()
					tor.inner_radius = r0 * 0.85
					tor.outer_radius = r0
					tor.rings = 16
					tor.ring_segments = 5
					rib.mesh = tor
					rib.rotation_degrees = Vector3(0, 0, 90)
					rib.scale = Vector3(1.0, 1.0, 0.28)
					rib.position = Vector3(s * r0 * 0.83, 3.2, 0)
					rib.rotation_degrees = Vector3(0, 0, s * 74)
					rib.material_override = _mat(bone)
					curve.add_child(rib)
			return root
		"beacon_lantern", "beacon":
			root.add_child(_box(Vector3(1.6, 0.4, 1.6), Color("#7d8479"), Vector3(0, 0.2, 0)))
			root.add_child(_box(Vector3(0.55, 3.0, 0.55), Color("#8f9689"), Vector3(0, 1.9, 0)))
			root.add_child(_box(Vector3(1.2, 0.25, 1.2), Color("#c9a45e"), Vector3(0, 3.45, 0)))
			var orb := MeshInstance3D.new()
			var om := SphereMesh.new(); om.radius = 0.55; om.height = 1.1
			orb.mesh = om
			orb.position.y = 4.0
			orb.material_override = _mat(Color("#f2d49a"), 3.0)
			root.add_child(orb)
			return root
		"lilypad":
			var pad := MeshInstance3D.new()
			var pm := CylinderMesh.new(); pm.top_radius = 0.35; pm.bottom_radius = 0.35; pm.height = 0.02
			pad.mesh = pm
			pad.material_override = _mat(Color("#4f765b"))
			root.add_child(pad)
			return root
		"paper_lantern":
			var orb2 := MeshInstance3D.new()
			var om2 := SphereMesh.new(); om2.radius = 0.28; om2.height = 0.55
			orb2.mesh = om2
			orb2.material_override = _mat(Color("#f2d49a"), 3.0)
			root.add_child(orb2)
			return root
		"ember", "ember_collectible":
			var orb3 := MeshInstance3D.new()
			var om3 := SphereMesh.new(); om3.radius = 0.17; om3.height = 0.34
			orb3.mesh = om3
			orb3.material_override = _mat(Color("#ffd684"), 5.0)
			root.add_child(orb3)
			return root
		"memory_shard":
			root.add_child(_box(Vector3(0.8, 1.6, 0.3), Color("#4a4864"), Vector3(0, 0.8, 0)))
			root.add_child(_box(Vector3(0.2, 0.6, 0.05), Color("#9fe6dc"), Vector3(0, 0.95, -0.17), true))
			return root
		"cloud_puff":
			for i in 3:
				var puff := MeshInstance3D.new()
				var sm := SphereMesh.new(); sm.radius = 2.4 - i * 0.4; sm.height = 1.8
				puff.mesh = sm
				puff.position = Vector3(i * 1.8 - 1.8, i * 0.3, 0)
				puff.material_override = _mat(Color("#f2efe4"), 0.0)
				root.add_child(puff)
			return root
		"sky_whale":
			var whale_body := MeshInstance3D.new()
			var wm := SphereMesh.new(); wm.radius = 1.0; wm.height = 2.0
			whale_body.mesh = wm
			whale_body.scale = Vector3(4.0, 2.4, 14.0)
			whale_body.material_override = _mat(Color("#33415c"))
			root.add_child(whale_body)
			var tail := MeshInstance3D.new()
			tail.mesh = PrismMesh.new()
			tail.scale = Vector3(5.0, 3.0, 1.4)
			tail.position = Vector3(0, 0.5, 15.5)
			tail.material_override = _mat(Color("#33415c"))
			root.add_child(tail)
			return root
		"floating_rock":
			body.mesh = SphereMesh.new()
			(body.mesh as SphereMesh).radius = 2.0
			(body.mesh as SphereMesh).height = 3.0
			body.scale = Vector3(1.0, 0.7, 0.9)
			col = Color("#7d8479")
		_:
			height = 1.0
			var boxm := BoxMesh.new()
			boxm.size = Vector3(1, 1, 1)
			body.mesh = boxm
			body.position.y = 0.5
	body.material_override = _mat(col)
	root.add_child(body)
	return root


func _box(size: Vector3, color: Color, pos: Vector3, glow: bool = false) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.position = pos
	mi.material_override = _mat(color, 2.5 if glow else 0.0)
	return mi


func _mat(color: Color, emission: float = 0.0, roughness: float = 0.9) -> StandardMaterial3D:
	var key := "%s|%.1f|%.2f" % [color.to_html(), emission, roughness]
	if _mat_cache.has(key):
		return _mat_cache[key]
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = roughness
	m.metallic = 0.0
	if emission > 0.0:
		m.emission_enabled = true
		m.emission = color
		m.emission_energy_multiplier = emission
	_mat_cache[key] = m
	return m


func _instantiate_prop(type: String) -> Node3D:
	var scene := _load_scene(type)
	if scene == null:
		return _fallback_mesh(type)
	var node := scene.instantiate()
	if node is not Node3D:
		var wrap := Node3D.new()
		wrap.add_child(node)
		return wrap
	return node


func _apply_foliage(node: Node3D, type: String, sway: float = 0.05, glow_boost: float = 0.0) -> void:
	if not (type in TREE_TYPES or type in ["grass_tuft", "glow_grass", "reeds", "fern", "azalea_bush", "snow_bush", "glow_mushroom", "ice_crystal"]):
		return
	for mi in _all_mesh_instances(node):
		for i in mi.mesh.get_surface_count():
			var src: Material = mi.mesh.surface_get_material(i)
			var color := Color.WHITE
			var emission := 0.0
			if src is StandardMaterial3D:
				color = src.albedo_color
				if src.emission_enabled:
					emission = maxf(emission, src.emission_energy_multiplier * 0.6)
			color = color if color.a > 0.0 else Color.WHITE
			var key := "%s|%.2f|%.2f" % [color.to_html(), emission + glow_boost, sway]
			var mat: ShaderMaterial
			if _foliage_cache.has(key):
				mat = _foliage_cache[key]
			else:
				mat = ShaderMaterial.new()
				mat.shader = load("res://shaders/foliage.gdshader")
				mat.set_shader_parameter("albedo", color)
				mat.set_shader_parameter("sway", sway)
				mat.set_shader_parameter("glow", emission + glow_boost)
				_foliage_cache[key] = mat
			mi.set_surface_override_material(i, mat)


func _all_mesh_instances(node: Node) -> Array:
	var out: Array = []
	if node is MeshInstance3D:
		out.append(node)
	for c in node.get_children():
		out.append_array(_all_mesh_instances(c))
	return out


func _build_props() -> void:
	var lantern_i := 0
	for p in world.get("props", []):
		var t := str(p.get("t", ""))
		if t == "" or t == "ember" or t.begins_with("npc_") or t == "beacon" or t == "beacon_lantern":
			continue
		var pos := Vector3(float(p["p"][0]), float(p["p"][1]), float(p["p"][2]))
		var rot := float(p.get("r", 0.0))
		var scl := float(p.get("s", 1.0))
		var node := _instantiate_prop(t)
		node.position = pos
		node.rotation.y = rot
		node.scale = Vector3.ONE * scl
		var sway := 0.035
		if t in ["cherry_tree_a", "cherry_tree_b", "glow_tree", "pine_tree_a", "pine_tree_b", "bare_tree", "palm_tree"]:
			sway = 0.055
		elif t in ["bamboo_cluster", "reeds"]:
			sway = 0.07
		_apply_foliage(node, t, sway, 0.4 if t in ["glow_tree", "glow_grass"] else 0.0)
		props_root.add_child(node)
		var c = p.get("c", "none")
		if c != "none":
			_add_prop_collision(t, pos, rot, scl)
		if t == "stone_lantern" or t == "paper_lantern":
			lantern_i += 1
			if lantern_i % 2 == 0:
				_add_lantern_glow(pos + Vector3(0, 1.7 if t == "stone_lantern" else 0.0, 0), t)


func _add_prop_collision(type: String, pos: Vector3, rot: float, scl: float) -> void:
	if not COLLIDERS.has(type):
		return
	var spec: Array = COLLIDERS[type]
	if spec.is_empty():
		return
	if spec[0] == "cyl":
		var shape := CylinderShape3D.new()
		shape.radius = float(spec[1]) * scl
		shape.height = float(spec[2]) * scl
		var cs := CollisionShape3D.new()
		cs.shape = shape
		cs.position = pos + Vector3(0, shape.height * 0.5, 0)
		collision_body.add_child(cs)
	elif spec[0] == "box":
		var size := Vector3(float(spec[1]), float(spec[2]), float(spec[3])) * scl
		var shape := BoxShape3D.new()
		shape.size = size
		var cs := CollisionShape3D.new()
		cs.shape = shape
		cs.position = pos + Vector3(0, size.y * 0.5, 0)
		cs.rotation.y = rot
		collision_body.add_child(cs)


func _add_lantern_glow(pos: Vector3, kind: String) -> void:
	if _lantern_lights.size() > 26:
		return
	var light := OmniLight3D.new()
	light.position = pos
	light.light_color = Color("#f4c988") if kind == "stone_lantern" else Color("#ffdca8")
	light.light_energy = 0.85 if kind == "stone_lantern" else 0.55
	light.omni_range = 5.2 if kind == "stone_lantern" else 3.6
	light.omni_attenuation = 1.4
	light.shadow_enabled = false
	light.distance_fade_enabled = true
	light.distance_fade_begin = 55.0
	light.distance_fade_length = 24.0
	add_child(light)
	_lantern_lights.append(light)


# ---------------------------------------------------------------- petals ---
func _build_petals() -> void:
	if chapter_index != 0:
		return
	var spots: Array = []
	for p in world.get("props", []):
		var t: String = str(p.get("t", ""))
		if t not in ["cherry_tree_a", "cherry_tree_b", "big_cherry"]:
			continue
		var cx := float(p["p"][0])
		var cz := float(p["p"][2])
		for i in 10:
			var ang := _rng.randf() * TAU
			var rad := _rng.randf_range(0.8, 5.4)
			var x := cx + cos(ang) * rad
			var z := cz + sin(ang) * rad
			var y := h_world(x, z)
			if y < -1.0:
				continue
			spots.append([x, y + 0.035, z, _rng.randf() * TAU, _rng.randf_range(0.7, 1.5)])
	# extra petals scattered over the plaza and the first steps of the path
	for i in 70:
		var ang := _rng.randf() * TAU
		var rad := sqrt(_rng.randf()) * 6.0
		var x := spawn_position.x + cos(ang) * rad
		var z := spawn_position.z + sin(ang) * rad
		spots.append([x, h_world(x, z) + 0.035, z, _rng.randf() * TAU, _rng.randf_range(0.7, 1.3)])
	var petal_st := SurfaceTool.new()
	petal_st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var pa := Vector3(-0.07, 0, 0)
	var pb := Vector3(0, 0, 0.045)
	var pc := Vector3(0.07, 0, 0)
	var pd := Vector3(0, 0, -0.035)
	for tri in [[pa, pb, pc], [pa, pc, pd]]:
		for v in tri:
			petal_st.set_normal(Vector3.UP)
			petal_st.add_vertex(v)
	var petal_mesh := petal_st.commit()
	var m := StandardMaterial3D.new()
	m.albedo_color = Color("#e9b0ad")
	m.roughness = 0.95
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
	petal_mesh.surface_set_material(0, m)
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = petal_mesh
	mm.instance_count = spots.size()
	for i in spots.size():
		var sp: Array = spots[i]
		var basis := Basis(Vector3.UP, float(sp[3]))
		basis = basis.scaled(Vector3(float(sp[4]), float(sp[4]), float(sp[4])))
		mm.set_instance_transform(i, Transform3D(basis, Vector3(float(sp[0]), float(sp[1]), float(sp[2]))))
	var mmi := MultiMeshInstance3D.new()
	mmi.name = "FallenPetals"
	mmi.multimesh = mm
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mmi)


# ------------------------------------------------------------------ multi ---
func _build_multi() -> void:
	for group in world.get("multi", []):
		var t := str(group.get("t", ""))
		var transforms: Array = group.get("p", [])
		if transforms.is_empty():
			continue
		if t == "koi":
			_spawn_koi(transforms)
			continue
		var mesh: Mesh = null
		var material: Material = null
		if t.begins_with("flower_"):
			mesh = _flower_mesh(t)
			if mesh:
				material = mesh.surface_get_material(0)
		else:
			var scene := _load_scene(t)
			if scene:
				var probe := scene.instantiate()
				var mis := _all_mesh_instances(probe)
				if not mis.is_empty():
					mesh = mis[0].mesh
					if mesh.get_surface_count() > 0:
						material = mesh.surface_get_material(0)
				probe.queue_free()
		if mesh == null:
			_missing_warn(t)
			continue
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = mesh
		mm.instance_count = transforms.size()
		for i in transforms.size():
			var p: Array = transforms[i]
			var pos := Vector3(float(p[0]), float(p[1]), float(p[2]))
			var rot := float(p[3])
			var scl := float(p[4])
			var basis := Basis(Vector3.UP, rot).scaled(Vector3(scl, scl, scl))
			mm.set_instance_transform(i, Transform3D(basis, pos))
		var mmi := MultiMeshInstance3D.new()
		mmi.name = "Multi_" + t
		mmi.multimesh = mm
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if material:
			mmi.material_override = material
		if t == "grass_tuft" or t == "glow_grass":
			var fm := ShaderMaterial.new()
			fm.shader = load("res://shaders/foliage.gdshader")
			var base_col := Color("#7d9a6a") if chapter_index != 3 else Color("#6fc8bd")
			fm.set_shader_parameter("albedo", base_col)
			fm.set_shader_parameter("sway", 0.06)
			fm.set_shader_parameter("glow", 0.8 if t == "glow_grass" else 0.0)
			mmi.material_override = fm
		multi_root.add_child(mmi)


func _flower_mesh(type: String) -> Mesh:
	var petal := Color("#e7b0ae")
	var heart := Color("#f4d9a0")
	var glow := false
	var stem := Color("#56704e")
	match type:
		"flower_spring_a":
			petal = Color("#e7b0ae"); heart = Color("#ffe0a8")
		"flower_spring_b":
			petal = Color("#f2e3c8"); heart = Color("#d7b46d")
		"flower_desert":
			petal = Color("#e6a25e"); heart = Color("#7d4c37")
		"flower_snow":
			petal = Color("#d8e9ea"); heart = Color("#b7d4d9")
		"flower_night":
			petal = Color("#79cfc9"); heart = Color("#f0d49a"); glow = true; stem = Color("#3d5a5c")
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	# stem (two thin triangles)
	_flower_tri(st, Vector3(-0.012, 0, 0), Vector3(0.012, 0, 0), Vector3(0.0, 0.3, 0), stem)
	_flower_tri(st, Vector3(0.012, 0, 0), Vector3(0, 0.3, 0.02), Vector3(0.0, 0.3, 0), stem)
	# five petals around a low cone
	for i in 5:
		var a := TAU * float(i) / 5.0
		var b := a + TAU / 10.0
		var center := Vector3(0, 0.3, 0)
		var p0 := Vector3(cos(a) * 0.09, 0.34, sin(a) * 0.09)
		var p1 := Vector3(cos(b) * 0.14, 0.37, sin(b) * 0.14)
		var p2 := Vector3(cos(a + 0.35) * 0.07, 0.42, sin(a + 0.35) * 0.07)
		_flower_tri(st, center, p0, p1, petal)
		_flower_tri(st, center, p1, p2, petal.lightened(0.06))
	_flower_tri(st, Vector3(-0.03, 0.4, 0), Vector3(0.03, 0.4, 0), Vector3(0, 0.46, 0.02), heart)
	var mesh := st.commit()
	var m := StandardMaterial3D.new()
	m.vertex_color_use_as_albedo = true
	m.roughness = 0.9
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	if glow:
		m.emission_enabled = true
		m.emission = Color("#59b9b2")
		m.emission_energy_multiplier = 1.2
	mesh.surface_set_material(0, m)
	return mesh


func _flower_tri(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, color: Color) -> void:
	var nrm := (b - a).cross(c - a).normalized()
	if nrm == Vector3.ZERO:
		nrm = Vector3.UP
	st.set_normal(nrm)
	st.set_color(color.srgb_to_linear())
	st.add_vertex(a)
	st.add_vertex(b)
	st.add_vertex(c)


func _spawn_koi(transforms: Array) -> void:
	for p in transforms:
		var pos := Vector3(float(p[0]), float(p[1]), float(p[2]))
		var scene := _load_scene("koi")
		var node: Node3D
		if scene:
			node = scene.instantiate()
		else:
			node = _fallback_mesh("koi")
		node.position = pos
		add_child(node)
		# find nearest water to orbit
		var best := {}
		var best_d := 1e20
		for w in world.get("water", []):
			var d := Vector2(pos.x - float(w["x"]), pos.z - float(w["z"])).length()
			if d < best_d:
				best_d = d
				best = w
		_koi.append({
			"node": node,
			"center": Vector3(float(best.get("x", pos.x)), float(best.get("level", pos.y)) - 0.14, float(best.get("z", pos.z))),
			"radius": clampf(best_d, 1.2, 5.0),
			"phase": _rng.randf() * TAU,
			"speed": _rng.randf_range(0.12, 0.28) * (1.0 if _rng.randf() > 0.5 else -1.0),
		})


# --------------------------------------------------------------- bridges ---
func _build_bridges() -> void:
	for b in world.get("bridges", []):
		var t := str(b.get("type", "stone_bridge"))
		var pos := Vector3(float(b["x"]), float(b["y"]), float(b["z"]))
		var angle := float(b.get("angle", 0.0))
		var span := float(b.get("span", 10.0))
		var width := float(b.get("width", 3.0))
		var node := _instantiate_prop(t)
		node.position = pos
		node.rotation.y = angle
		add_child(node)
		var body := StaticBody3D.new()
		body.collision_layer = 1
		body.collision_mask = 0
		var cs := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = Vector3(width, 0.4, span)
		cs.shape = box
		cs.position = pos + Vector3(0, -0.2, 0)
		cs.rotation.y = angle
		body.add_child(cs)
		add_child(body)
		# hidden side rails to make the bridge forgiving but not boxy
		for side in [-1.0, 1.0]:
			var rail := StaticBody3D.new()
			rail.collision_layer = 1
			var rc := CollisionShape3D.new()
			var rb := BoxShape3D.new()
			rb.size = Vector3(0.14, 1.0, span)
			rc.shape = rb
			var offset := Vector3(cos(angle) * width * 0.5 * side, 0.5, -sin(angle) * width * 0.5 * side)
			rc.position = pos + offset
			rc.rotation.y = angle
			rail.add_child(rc)
			add_child(rail)


# ---------------------------------------------------------- interactables ---
func _build_interactables() -> void:
	# embers
	for e in world.get("embers", []):
		var id := str(e.get("id", ""))
		if GameState.has_ember(chapter_index, id):
			continue
		var node := Ember.new()
		node.setup(id, str(e.get("name", "余烬")), Vector3(float(e["p"][0]), float(e["p"][1]), float(e["p"][2])), chapter_index)
		interact_root.add_child(node)
		interactables.append(node)
		interactable_built.emit(node)
	# npcs
	for n in world.get("npcs", []):
		var npc := Npc.new()
		npc.setup(n, chapter_index)
		interact_root.add_child(npc)
		interactables.append(npc)
		interactable_built.emit(npc)
	# beacon
	var b: Array = world.get("beacon", [0, 0, 0])
	var beacon := Beacon.new()
	beacon.setup(Vector3(float(b[0]), float(b[1]), float(b[2])), chapter_index, int(chapter.get("required", 3)))
	interact_root.add_child(beacon)
	interactables.append(beacon)
	interactable_built.emit(beacon)
	# zones
	for z in world.get("zones", []):
		var zt := ZoneTrigger.new()
		zt.setup(str(z.get("name", "")), Vector3(float(z["x"]), 10.0, float(z["z"])), float(z.get("r", 10.0)))
		add_child(zt)
		zt.player_entered.connect(_on_zone_entered)
		zones.append(zt)


func _on_zone_entered(zone_name: String) -> void:
	zone_entered.emit(zone_name)


func _find_nearest_interactable(player_pos: Vector3, max_dist: float = 3.2) -> Node:
	var best: Node = null
	var best_d := max_dist
	for it in interactables:
		if not is_instance_valid(it) or it.get("consumed"):
			continue
		var d: float = (it.global_position - player_pos).length()
		if d < best_d and it.has_method("can_interact"):
			best_d = d
			best = it
	return best


# -------------------------------------------------------------- skyline ----
func _disable_shadows(node: Node) -> void:
	if node is GeometryInstance3D:
		(node as GeometryInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for c in node.get_children():
		_disable_shadows(c)


func _build_skyline() -> void:
	# star whale, front-left/right depending on chapter
	var whale_scene := _load_scene("sky_whale")
	var whale: Node3D
	if whale_scene:
		whale = whale_scene.instantiate()
	else:
		whale = _fallback_mesh("sky_whale")
	var whale_pos := Vector3(145, 78, -235)
	if chapter_index == 1:
		whale_pos = Vector3(-210, 83, -190)
	elif chapter_index == 2:
		whale_pos = Vector3(185, 65, 175)
	elif chapter_index == 3:
		whale_pos = Vector3(-105, 58, -172)
	whale.position = whale_pos
	whale.rotation_degrees = Vector3(2, -26, -4)
	whale.scale = Vector3.ONE * (1.5 if chapter_index < 3 else 2.3)
	_disable_shadows(whale)
	distant_root.add_child(whale)
	_whale = whale
	_whale_base = whale_pos
	# constellation dust around the whale
	var dust := GPUParticles3D.new()
	dust.amount = 90
	dust.lifetime = 10.0
	dust.preprocess = 5.0
	dust.position = whale_pos
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	pm.emission_sphere_radius = 55.0
	pm.direction = Vector3.UP
	pm.spread = 80.0
	pm.initial_velocity_min = 0.02
	pm.initial_velocity_max = 0.3
	pm.gravity = Vector3.ZERO
	pm.scale_min = 0.4
	pm.scale_max = 1.4
	pm.color = Color(1.0, 0.86, 0.58, 0.8)
	dust.process_material = pm
	var quad := QuadMesh.new()
	quad.size = Vector2(0.8, 0.8)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.albedo_color = Color(1.0, 0.87, 0.6, 0.7)
	m.emission_enabled = true
	m.emission = Color(1.0, 0.78, 0.45)
	m.emission_energy_multiplier = 3.0
	quad.material = m
	dust.draw_pass_1 = quad
	distant_root.add_child(dust)

	# floating islands
	var island_specs := []
	match chapter_index:
		0:
			island_specs = [
				[Vector3(82, 32, -128), 4.2, 0.3], [Vector3(-132, 44, -98), 5.5, 1.3],
				[Vector3(168, 20, 60), 3.4, 2.2], [Vector3(-70, 14, 155), 3.0, 3.3],
			]
		1:
			island_specs = [
				[Vector3(130, 24, 95), 5.2, 0.8], [Vector3(-155, 36, 85), 4.0, 1.7],
				[Vector3(95, 50, -160), 5.8, 2.5], [Vector3(-90, 18, -155), 3.2, 3.1],
			]
		2:
			island_specs = [
				[Vector3(-120, 28, -118), 4.4, 0.2], [Vector3(140, 42, -80), 5.0, 1.9],
				[Vector3(80, 15, 150), 3.2, 2.9], [Vector3(-165, 50, 45), 5.5, 3.7],
			]
		3:
			island_specs = [
				[Vector3(95, 30, -130), 4.6, 0.4], [Vector3(-120, 42, -95), 5.2, 1.1],
				[Vector3(150, 22, 30), 3.6, 2.1], [Vector3(-75, 38, 130), 4.2, 3.0],
				[Vector3(60, 12, 110), 3.0, 4.0], [Vector3(-42, 54, -58), 2.8, 4.8],
			]
	for spec in island_specs:
		_build_sky_island(spec[0], float(spec[1]), float(spec[2]))

	# a few loose clouds under and around the island
	for i in 10:
		var cloud_scene := _load_scene("cloud_puff")
		var cloud: Node3D
		if cloud_scene:
			cloud = cloud_scene.instantiate()
		else:
			cloud = _fallback_mesh("cloud_puff")
		var ang := _rng.randf() * TAU
		var rad := _rng.randf_range(80, 190)
		cloud.position = Vector3(cos(ang) * rad, _rng.randf_range(-18, 8), sin(ang) * rad)
		cloud.scale = Vector3.ONE * _rng.randf_range(1.5, 2.8)
		cloud.rotation.y = _rng.randf() * TAU
		_disable_shadows(cloud)
		distant_root.add_child(cloud)

	# birds
	_spawn_birds()


func _build_sky_island(pos: Vector3, scale: float, variant: float) -> void:
	var root := Node3D.new()
	root.position = pos
	root.rotation.y = variant * 1.6
	root.scale = Vector3.ONE * scale
	var rock_scene := _load_scene("floating_rock")
	var rock: Node3D
	if rock_scene:
		rock = rock_scene.instantiate()
	else:
		rock = _fallback_mesh("floating_rock")
	root.add_child(rock)
	var tree_types := ["pine_tree_a", "pine_tree_b"] if (chapter_index == 2 or chapter_index == 1) else ["cherry_tree_a", "bamboo_cluster", "glow_tree"]
	for i in 3:
		var tt: String = tree_types[i % tree_types.size()]
		var ts := _load_scene(tt)
		if ts == null:
			continue
		var tree := ts.instantiate()
		tree.position = Vector3(_rng.randf_range(-1.8, 1.8), 0.4, _rng.randf_range(-1.8, 1.8))
		tree.scale = Vector3.ONE * _rng.randf_range(0.5, 0.9)
		tree.rotation.y = _rng.randf() * TAU
		root.add_child(tree)
	_disable_shadows(root)
	distant_root.add_child(root)


func _spawn_birds() -> void:
	for i in 4:
		var bird_scene := _load_scene("bird")
		var bird: Node3D
		if bird_scene:
			bird = bird_scene.instantiate()
		else:
			var b := Node3D.new()
			var mi := MeshInstance3D.new()
			var pm := PrismMesh.new()
			pm.size = Vector3(1.0, 0.15, 0.25)
			mi.mesh = pm
			mi.material_override = _mat(Color("#2e3c3a"))
			b.add_child(mi)
			bird = b
		bird.position = Vector3(_rng.randf_range(-50, 50), _rng.randf_range(28, 42), _rng.randf_range(-50, 50))
		bird.scale = Vector3.ONE * _rng.randf_range(0.8, 1.4)
		distant_root.add_child(bird)
		var tw := create_tween().set_loops()
		var start := bird.position
		var end := start + Vector3(_rng.randf_range(10, 22), 0, _rng.randf_range(-12, 12))
		tw.tween_property(bird, "position", end, _rng.randf_range(9, 14)).set_trans(Tween.TRANS_SINE)
		tw.tween_property(bird, "position", start, _rng.randf_range(9, 14)).set_trans(Tween.TRANS_SINE)


# ------------------------------------------------------------- particles ---
func _build_particles() -> void:
	var petal_color := Color(str(env_data.get("petals", "#f3c9c5")))
	if chapter_index == 2:
		_make_weather(900, Color(0.93, 0.97, 1.0, 0.9), Vector2(0.045, 0.04), 1.4, Vector3(0, -1.2, 0), false, 26)
	elif chapter_index == 1:
		_make_weather(420, Color(0.95, 0.82, 0.6, 0.55), Vector2(0.05, 0.02), 1.0, Vector3(0.2, -0.5, 0.1), false, 20)
		_make_fireflies(80, Color(1.0, 0.85, 0.48, 0.8), 1.0)
	elif chapter_index == 3:
		_make_weather(280, Color(0.65, 0.95, 0.9, 0.7), Vector2(0.06, 0.04), 0.7, Vector3(0.1, 0.12, 0), true, 28)
		_make_fireflies(160, Color(0.58, 0.95, 0.9, 0.9), 1.0)
		_make_falling_stars()
	else:
		_make_weather(420, petal_color, Vector2(0.08, 0.1), 1.2, Vector3(0.35, -0.55, 0.15), false, 24)
		_make_fireflies(110, Color(1.0, 0.83, 0.46, 0.8), 0.9)


func _make_weather(amount: int, color: Color, size: Vector2, speed: float, gravity: Vector3, emissive: bool, height: int) -> void:
	var p := GPUParticles3D.new()
	p.amount = amount
	p.lifetime = 18.0
	p.preprocess = 8.0
	p.position = Vector3(0, 30, 0)
	p.visibility_aabb = AABB(Vector3(-130, -60, -130), Vector3(260, 120, 260))
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = Vector3(78, float(height), 78)
	pm.direction = Vector3.DOWN
	pm.spread = 35.0
	pm.gravity = gravity
	pm.initial_velocity_min = speed * 0.6
	pm.initial_velocity_max = speed * 1.5
	pm.scale_min = 0.5
	pm.scale_max = 1.5
	pm.color = color
	pm.angular_velocity_min = -120.0
	pm.angular_velocity_max = 120.0
	pm.turbulence_enabled = true
	pm.turbulence_noise_strength = 0.35
	pm.turbulence_noise_scale = 3.0
	pm.turbulence_influence_min = 0.04
	pm.turbulence_influence_max = 0.12
	p.process_material = pm
	var quad := QuadMesh.new()
	quad.size = size
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.albedo_color = color
	m.vertex_color_use_as_albedo = true
	if emissive:
		m.emission_enabled = true
		m.emission = color
		m.emission_energy_multiplier = 1.8
	quad.material = m
	p.draw_pass_1 = quad
	add_child(p)


func _make_fireflies(amount: int, color: Color, size: float) -> void:
	var p := GPUParticles3D.new()
	p.amount = amount
	p.lifetime = 9.0
	p.preprocess = 6.0
	p.position = Vector3(0, 6, 0)
	p.visibility_aabb = AABB(Vector3(-90, -20, -90), Vector3(180, 80, 180))
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = Vector3(68, 11, 68)
	pm.direction = Vector3.UP
	pm.spread = 180.0
	pm.initial_velocity_min = 0.05
	pm.initial_velocity_max = 0.35
	pm.gravity = Vector3(0, 0.03, 0)
	pm.scale_min = 0.55
	pm.scale_max = 1.4
	pm.color = color
	pm.turbulence_enabled = true
	pm.turbulence_noise_strength = 0.2
	pm.turbulence_influence_min = 0.02
	pm.turbulence_influence_max = 0.06
	p.process_material = pm
	var quad := QuadMesh.new()
	quad.size = Vector2(0.12, 0.12) * size
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.albedo_color = color
	m.emission_enabled = true
	m.emission = color
	m.emission_energy_multiplier = 5.0
	quad.material = m
	p.draw_pass_1 = quad
	add_child(p)


func _make_falling_stars() -> void:
	var p := GPUParticles3D.new()
	p.amount = 70
	p.lifetime = 2.8
	p.preprocess = 2.0
	p.position = Vector3(0, 48, 0)
	p.visibility_aabb = AABB(Vector3(-100, -60, -100), Vector3(200, 120, 200))
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = Vector3(62, 8, 62)
	pm.direction = Vector3(0.2, -1.0, 0.1)
	pm.spread = 7.0
	pm.gravity = Vector3(0, -5.0, 0)
	pm.initial_velocity_min = 10.0
	pm.initial_velocity_max = 19.0
	pm.scale_min = 0.7
	pm.scale_max = 1.8
	pm.color = Color(0.75, 0.92, 1.0, 0.9)
	p.process_material = pm
	var quad := QuadMesh.new()
	quad.size = Vector2(0.09, 1.6)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.albedo_color = Color(0.75, 0.92, 1.0, 0.75)
	m.emission_enabled = true
	m.emission = Color(0.7, 0.9, 1.0)
	m.emission_energy_multiplier = 4.0
	quad.material = m
	p.draw_pass_1 = quad
	add_child(p)


# ------------------------------------------------------------------ tick ---
func _process(delta: float) -> void:
	_time += delta
	if _whale:
		_whale.position = _whale_base + Vector3(0, sin(_time * 0.12) * 3.0, 0)
		_whale.rotation.z = deg_to_rad(-4.0 + sin(_time * 0.09) * 1.6)
	for k in _koi:
		var node: Node3D = k["node"]
		if not is_instance_valid(node):
			continue
		k["phase"] += delta * k["speed"]
		var ang: float = k["phase"]
		var center: Vector3 = k["center"]
		var radius: float = k["radius"]
		var p := center + Vector3(cos(ang) * radius, sin(_time * 1.2 + ang) * 0.04, sin(ang) * radius)
		node.position = p
		var dir := Vector3(-sin(ang), 0, cos(ang)) * signf(k["speed"])
		node.rotation.y = atan2(dir.x, dir.z)


func get_spawn() -> Vector3:
	return spawn_position + Vector3(0, 0.3, 0)


