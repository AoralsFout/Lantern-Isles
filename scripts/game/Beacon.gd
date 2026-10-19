extends Node3D
class_name Beacon

signal requested(beacon: Beacon)

var chapter_index := 0
var required := 3
var lit := false
var _visual: Node3D
var _glow_light: OmniLight3D
var _orb: Node3D
var _t := 0.0
var _core_mat: StandardMaterial3D


func setup(pos: Vector3, ch_index: int, req: int) -> void:
	position = pos
	chapter_index = ch_index
	required = req
	add_to_group("interactables")


func _ready() -> void:
	_visual = Node3D.new()
	add_child(_visual)
	var scene: PackedScene = null
	if ResourceLoader.exists("res://assets/models/relics/beacon_lantern.glb"):
		scene = load("res://assets/models/relics/beacon_lantern.glb")
	var model: Node3D
	if scene:
		model = scene.instantiate()
	else:
		model = _fallback()
	_visual.add_child(model)

	_orb = Node3D.new()
	_orb.position.y = 4.0
	add_child(_orb)
	var orb_mesh := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.5
	sm.height = 1.0
	orb_mesh.mesh = sm
	_core_mat = StandardMaterial3D.new()
	_core_mat.albedo_color = Color("#d7c39a")
	_core_mat.emission_enabled = true
	_core_mat.emission = Color("#ffd58a")
	_core_mat.emission_energy_multiplier = 0.15
	orb_mesh.material_override = _core_mat
	_orb.add_child(orb_mesh)

	_glow_light = OmniLight3D.new()
	_glow_light.position.y = 4.0
	_glow_light.light_color = Color("#ffd18a")
	_glow_light.light_energy = 0.0
	_glow_light.omni_range = 18.0
	_glow_light.omni_attenuation = 1.1
	_glow_light.shadow_enabled = false
	add_child(_glow_light)
	set_process(true)


func _fallback() -> Node3D:
	var root := Node3D.new()
	for i in 4:
		var mi := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(1.8 - i * 0.28, 0.32, 1.8 - i * 0.28)
		mi.mesh = bm
		mi.position.y = 0.2 + i * 0.75
		var m := StandardMaterial3D.new()
		m.albedo_color = Color("#7d8479").lightened(i * 0.05)
		mi.material_override = m
		root.add_child(mi)
	var stem := MeshInstance3D.new()
	var sm := BoxMesh.new()
	sm.size = Vector3(0.32, 3.1, 0.32)
	stem.mesh = sm
	stem.position.y = 3.0
	var stm := StandardMaterial3D.new()
	stm.albedo_color = Color("#8f9689")
	stem.material_override = stm
	root.add_child(stem)
	var bowl := MeshInstance3D.new()
	var bm2 := CylinderMesh.new()
	bm2.top_radius = 1.2
	bm2.bottom_radius = 0.45
	bm2.height = 0.55
	bowl.mesh = bm2
	bowl.position.y = 4.55
	var bm2m := StandardMaterial3D.new()
	bm2m.albedo_color = Color("#b59b68")
	bowl.material_override = bm2m
	root.add_child(bowl)
	return root


func _process(delta: float) -> void:
	_t += delta
	if _orb:
		_orb.rotation.y += delta * (0.5 if not lit else 1.2)
		_orb.position.y = 4.0 + sin(_t * 1.2) * (0.04 if not lit else 0.12)
	if _glow_light and not lit:
		_glow_light.light_energy = 0.12 + 0.06 * sin(_t * 1.7)
	if _core_mat and not lit:
		_core_mat.emission_energy_multiplier = 0.12 + 0.05 * sin(_t * 1.9)


func can_interact() -> bool:
	return not lit


func get_prompt() -> String:
	if lit:
		return "残灯已亮"
	return "点亮残灯"


func interact(player: Node) -> void:
	if lit:
		return
	requested.emit(self)


func ignite() -> void:
	if lit:
		return
	lit = true
	AudioDirector.sfx("beacon", 0.0)
	var tw := create_tween().set_parallel(true)
	tw.tween_property(_glow_light, "light_energy", 7.5, 1.6).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.tween_property(_core_mat, "emission_energy_multiplier", 7.0, 1.4)
	tw.tween_property(_orb, "scale", Vector3.ONE * 1.25, 1.2).set_trans(Tween.TRANS_ELASTIC)
	tw.tween_property(_orb, "position:y", 4.5, 1.6).set_trans(Tween.TRANS_SINE)
	_spawn_ring()
	_spawn_motes()


func _spawn_ring() -> void:
	for i in 3:
		var ring := MeshInstance3D.new()
		var torus := TorusMesh.new()
		torus.inner_radius = 0.8
		torus.outer_radius = 0.84
		torus.rings = 48
		torus.ring_segments = 4
		ring.mesh = torus
		ring.rotation_degrees = Vector3(90, 0, 0)
		ring.position = position + Vector3(0, 4.0, 0)
		var m := StandardMaterial3D.new()
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.albedo_color = Color(1.0, 0.83, 0.5, 0.65)
		m.emission_enabled = true
		m.emission = Color(1.0, 0.78, 0.4)
		m.emission_energy_multiplier = 4.0
		ring.material_override = m
		add_child(ring)
		ring.scale = Vector3.ONE * 0.4
		var tw := create_tween().set_parallel(true)
		tw.tween_property(ring, "scale", Vector3.ONE * (5.0 + i * 1.8), 2.2).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		tw.tween_property(ring, "position:y", position.y + 8.0 + i * 2.0, 2.2).set_trans(Tween.TRANS_SINE)
		tw.tween_property(m, "albedo_color:a", 0.0, 2.2)
		var timer := get_tree().create_timer(2.3)
		timer.timeout.connect(func(): ring.queue_free())


func _spawn_motes() -> void:
	var p := GPUParticles3D.new()
	p.position = position + Vector3(0, 4.0, 0)
	p.amount = 120
	p.lifetime = 4.0
	p.one_shot = false
	p.emitting = true
	p.local_coords = false
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	pm.emission_sphere_radius = 1.0
	pm.direction = Vector3.UP
	pm.spread = 75.0
	pm.initial_velocity_min = 1.0
	pm.initial_velocity_max = 5.0
	pm.gravity = Vector3(0, 0.4, 0)
	pm.scale_min = 0.3
	pm.scale_max = 1.4
	pm.color = Color(1.0, 0.86, 0.55, 1.0)
	p.process_material = pm
	var quad := QuadMesh.new()
	quad.size = Vector2(0.12, 0.12)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.albedo_color = Color(1, 0.88, 0.6)
	m.emission_enabled = true
	m.emission = Color(1, 0.78, 0.4)
	m.emission_energy_multiplier = 6.0
	quad.material = m
	p.draw_pass_1 = quad
	add_child(p)
