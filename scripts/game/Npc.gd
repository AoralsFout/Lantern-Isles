extends Node3D
class_name Npc

signal talked(npc: Npc)

var npc_id := ""
var display_name := ""
var role := ""
var lines: Array = []
var memory_id := ""
var chapter_index := 0
var consumed := false
var _visual: Node3D
var _head: Node3D
var _lantern: Node3D
var _face_root: Node3D
var _base_yaw := 0.0
var _t := 0.0
var _player: Node3D
var _talking := false


func setup(data: Dictionary, ch_index: int) -> void:
	npc_id = str(data.get("id", ""))
	display_name = str(data.get("name", "回声"))
	role = str(data.get("role", ""))
	lines = data.get("lines", [])
	memory_id = str(data.get("memory", ""))
	chapter_index = ch_index
	var p: Array = data.get("p", [0, 0, 0])
	position = Vector3(float(p[0]), float(p[1]), float(p[2]))
	_base_yaw = deg_to_rad(float(data.get("rot", 0.0)))
	add_to_group("interactables")


func _ready() -> void:
	rotation.y = _base_yaw
	_visual = Node3D.new()
	add_child(_visual)
	if npc_id == "bell":
		_build_bell()
		return
	_build_capsule()
	_head = _visual

	var label := Label3D.new()
	label.text = display_name
	label.font = ThemeKit.font("body")
	label.font_size = 44
	label.pixel_size = 0.0032
	label.modulate = Color(0.98, 0.92, 0.8, 0.92)
	label.outline_size = 12
	label.outline_modulate = Color(0.08, 0.1, 0.09, 0.85)
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.position.y = 2.35
	add_child(label)

	# name marker: a tiny warm lantern above the label's anchor
	var marker := OmniLight3D.new()
	marker.light_color = Color("#f4cf95")
	marker.light_energy = 0.55
	marker.omni_range = 3.0
	marker.shadow_enabled = false
	marker.position.y = 1.4
	add_child(marker)

	set_process(true)
	_player = get_tree().get_first_node_in_group("player") as Node3D


func _build_capsule() -> void:
	var body_mat := StandardMaterial3D.new()
	var robe := Color("#c9b78e")
	var accent := Color("#6f8d7c")
	match chapter_index:
		1:
			robe = Color("#d6b384"); accent = Color("#b06042")
		2:
			robe = Color("#c8d7d7"); accent = Color("#708c95")
		3:
			robe = Color("#c9c2dd"); accent = Color("#7467a2")
	var is_keeper := npc_id == "aying"
	if is_keeper:
		robe = Color("#f2e3bd")
		accent = Color("#d8b06c")

	body_mat.albedo_color = robe
	body_mat.roughness = 0.85
	if is_keeper:
		body_mat.emission_enabled = true
		body_mat.emission = Color("#ffd98d")
		body_mat.emission_energy_multiplier = 0.55

	var capsule := MeshInstance3D.new()
	var cm := CapsuleMesh.new()
	cm.radius = 0.39
	cm.height = 1.18
	capsule.mesh = cm
	capsule.position.y = 0.82
	capsule.material_override = body_mat
	_visual.add_child(capsule)

	# low pointed hood / cloak
	var hood := MeshInstance3D.new()
	var cone := CylinderMesh.new()
	cone.top_radius = 0.06
	cone.bottom_radius = 0.52
	cone.height = 0.62
	cone.radial_segments = 8
	hood.mesh = cone
	hood.position.y = 1.45
	var hood_mat := StandardMaterial3D.new()
	hood_mat.albedo_color = accent
	hood_mat.roughness = 0.9
	hood_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	hood.material_override = hood_mat
	_visual.add_child(hood)

	# wide straw hat, tilted a little
	var hat_pivot := Node3D.new()
	hat_pivot.position.y = 1.55
	hat_pivot.rotation_degrees = Vector3(-7, 0, 6)
	_visual.add_child(hat_pivot)
	var brim := MeshInstance3D.new()
	var bm := CylinderMesh.new()
	bm.top_radius = 0.56
	bm.bottom_radius = 0.64
	bm.height = 0.09
	bm.radial_segments = 10
	brim.mesh = bm
	var brim_mat := StandardMaterial3D.new()
	brim_mat.albedo_color = Color("#a58a5f")
	brim_mat.roughness = 0.95
	brim.material_override = brim_mat
	hat_pivot.add_child(brim)
	var hat_top := MeshInstance3D.new()
	var ht := CylinderMesh.new()
	ht.top_radius = 0.22
	ht.bottom_radius = 0.3
	ht.height = 0.22
	hat_top.mesh = ht
	hat_top.position.y = 0.14
	hat_top.material_override = brim_mat
	hat_pivot.add_child(hat_top)

	# scarf
	var scarf := MeshInstance3D.new()
	var torus := TorusMesh.new()
	torus.inner_radius = 0.3
	torus.outer_radius = 0.44
	torus.rings = 16
	torus.ring_segments = 5
	scarf.mesh = torus
	scarf.position.y = 1.13
	var scarf_mat := StandardMaterial3D.new()
	scarf_mat.albedo_color = Color("#b45f4c") if not is_keeper else Color("#d2a35e")
	scarf_mat.roughness = 0.9
	scarf.material_override = scarf_mat
	_visual.add_child(scarf)
	var tail := MeshInstance3D.new()
	var tb := BoxMesh.new()
	tb.size = Vector3(0.16, 0.7, 0.04)
	tail.mesh = tb
	tail.position = Vector3(-0.36, 0.82, 0.22)
	tail.rotation_degrees = Vector3(0, 0, 10)
	tail.material_override = scarf_mat
	_visual.add_child(tail)

	# face — two calm little eyes and a warm dot
	var face := Node3D.new()
	face.position = Vector3(0, 1.03, 0.36)
	_visual.add_child(face)
	for sx in [-1, 1]:
		var eye := MeshInstance3D.new()
		var em := SphereMesh.new()
		em.radius = 0.035
		em.height = 0.07
		eye.mesh = em
		eye.position = Vector3(0.13 * sx, 0.03, 0.02)
		var emat := StandardMaterial3D.new()
		emat.albedo_color = Color("#26302c")
		eye.material_override = emat
		face.add_child(eye)

	# little paper lantern held to one side
	_lantern = Node3D.new()
	_lantern.position = Vector3(0.58, 0.86, 0.28)
	_visual.add_child(_lantern)
	var handle := MeshInstance3D.new()
	var hm := CylinderMesh.new()
	hm.top_radius = 0.015
	hm.bottom_radius = 0.015
	hm.height = 0.45
	handle.mesh = hm
	handle.position.y = 0.3
	handle.rotation_degrees = Vector3(0, 0, 18)
	var hmat := StandardMaterial3D.new()
	hmat.albedo_color = Color("#4e4034")
	handle.material_override = hmat
	_lantern.add_child(handle)
	var lant := MeshInstance3D.new()
	var lm := SphereMesh.new()
	lm.radius = 0.16
	lm.height = 0.34
	lant.mesh = lm
	var lmat := StandardMaterial3D.new()
	lmat.albedo_color = Color("#f4d59c")
	lmat.emission_enabled = true
	lmat.emission = Color("#ffbf6d")
	lmat.emission_energy_multiplier = 3.5
	lant.material_override = lmat
	lant.position.y = 0.05
	_lantern.add_child(lant)
	var ll := OmniLight3D.new()
	ll.light_color = Color("#ffd296")
	ll.light_energy = 0.7
	ll.omni_range = 4.0
	ll.shadow_enabled = false
	ll.position.y = 0.05
	_lantern.add_child(ll)


func _build_bell() -> void:
	# the whale-bone bell is a relic rather than a person
	var stone := MeshInstance3D.new()
	var sm := BoxMesh.new()
	sm.size = Vector3(1.2, 2.2, 0.5)
	stone.mesh = sm
	stone.position.y = 1.1
	var stmat := StandardMaterial3D.new()
	stmat.albedo_color = Color("#45445f")
	stmat.roughness = 0.95
	stone.material_override = stmat
	_visual.add_child(stone)
	var hollow := MeshInstance3D.new()
	var hm := BoxMesh.new()
	hm.size = Vector3(0.45, 0.8, 0.08)
	hollow.mesh = hm
	hollow.position = Vector3(0, 1.35, -0.27)
	var hmat := StandardMaterial3D.new()
	hmat.albedo_color = Color("#9fe6dc")
	hmat.emission_enabled = true
	hmat.emission = Color("#72d6cd")
	hmat.emission_energy_multiplier = 2.4
	hollow.material_override = hmat
	_visual.add_child(hollow)
	var label := Label3D.new()
	label.text = display_name
	label.font = ThemeKit.font("body")
	label.font_size = 40
	label.pixel_size = 0.003
	label.modulate = Color(0.9, 0.95, 0.9, 0.85)
	label.outline_size = 10
	label.outline_modulate = Color(0.05, 0.06, 0.08, 0.9)
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.position.y = 2.65
	add_child(label)
	var light := OmniLight3D.new()
	light.light_color = Color("#86e0d7")
	light.light_energy = 0.8
	light.omni_range = 5.0
	light.position.y = 1.3
	add_child(light)
	set_process(true)
	_player = get_tree().get_first_node_in_group("player") as Node3D


func _process(delta: float) -> void:
	if npc_id == "bell":
		_visual.rotation.y = sin(Time.get_ticks_msec() * 0.0003) * 0.02
		return
	_t += delta
	if _visual:
		_visual.position.y = sin(_t * 1.15) * 0.025
	if _lantern:
		_lantern.rotation.z = sin(_t * 1.6) * 0.08
	if _player == null or not is_instance_valid(_player):
		_player = get_tree().get_first_node_in_group("player") as Node3D
	if _player and is_instance_valid(_player):
		var d := global_position.distance_to(_player.global_position)
		if d < 5.5:
			var target_yaw := atan2(_player.global_position.x - global_position.x, _player.global_position.z - global_position.z)
			rotation.y = lerp_angle(rotation.y, target_yaw, delta * 2.4)


func can_interact() -> bool:
	return true


func get_prompt() -> String:
	if npc_id == "bell":
		return "倾听鲸骨钟"
	return "交谈 · " + display_name


func interact(player: Node) -> void:
	_talking = true
	talked.emit(self)
	_talking = false
