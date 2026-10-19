extends Node3D
class_name Ember

signal collected(ember: Ember)

var ember_id := ""
var display_name := "余烬"
var chapter_index := 0
var consumed := false
var _visual: Node3D
var _light: OmniLight3D
var _t := 0.0
var _base_y := 0.0
var _burst: GPUParticles3D


func setup(id: String, title: String, pos: Vector3, ch_index: int) -> void:
	ember_id = id
	display_name = title
	position = pos
	chapter_index = ch_index
	add_to_group("interactables")


func _ready() -> void:
	_base_y = position.y
	_visual = Node3D.new()
	add_child(_visual)
	var scene: PackedScene = null
	if ResourceLoader.exists("res://assets/models/relics/ember_collectible.glb"):
		scene = load("res://assets/models/relics/ember_collectible.glb")
	var model: Node3D
	if scene:
		model = scene.instantiate()
	else:
		model = _fallback()
	_visual.add_child(model)
	_visual.scale = Vector3.ONE * 1.35

	_light = OmniLight3D.new()
	_light.light_color = Color("#ffd487")
	_light.light_energy = 1.5
	_light.omni_range = 5.0
	_light.omni_attenuation = 1.6
	_light.shadow_enabled = false
	add_child(_light)

	var ring := MeshInstance3D.new()
	var torus := TorusMesh.new()
	torus.inner_radius = 0.25
	torus.outer_radius = 0.28
	torus.rings = 24
	torus.ring_segments = 6
	ring.mesh = torus
	ring.rotation_degrees = Vector3(90, 0, 0)
	var rm := StandardMaterial3D.new()
	rm.albedo_color = Color("#ffe4a8")
	rm.emission_enabled = true
	rm.emission = Color("#ffca6a")
	rm.emission_energy_multiplier = 3.0
	rm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	ring.material_override = rm
	ring.position.y = 0.02
	_visual.add_child(ring)

	_burst = _make_burst()
	add_child(_burst)
	set_process(true)


func _fallback() -> Node3D:
	var root := Node3D.new()
	var mi := MeshInstance3D.new()
	var gem := CapsuleMesh.new()
	gem.radius = 0.16
	gem.height = 0.42
	mi.mesh = gem
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color("#ffd98d")
	mat.emission_enabled = true
	mat.emission = Color("#ffbf5c")
	mat.emission_energy_multiplier = 5.0
	mi.material_override = mat
	root.add_child(mi)
	return root


func _make_burst() -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = 26
	p.one_shot = true
	p.explosiveness = 0.92
	p.lifetime = 1.0
	p.emitting = false
	p.local_coords = false
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	pm.emission_sphere_radius = 0.3
	pm.direction = Vector3.UP
	pm.spread = 180.0
	pm.initial_velocity_min = 1.2
	pm.initial_velocity_max = 3.8
	pm.gravity = Vector3(0, -2.4, 0)
	pm.scale_min = 0.3
	pm.scale_max = 1.0
	pm.color = Color(1.0, 0.85, 0.5, 1.0)
	p.process_material = pm
	var quad := QuadMesh.new()
	quad.size = Vector2(0.09, 0.09)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.albedo_color = Color(1.0, 0.88, 0.56)
	m.emission_enabled = true
	m.emission = Color(1.0, 0.78, 0.4)
	m.emission_energy_multiplier = 5.0
	quad.material = m
	p.draw_pass_1 = quad
	return p


func _process(delta: float) -> void:
	if consumed:
		return
	_t += delta
	if _visual:
		_visual.position.y = sin(_t * 1.8) * 0.14
		_visual.rotation.y += delta * 0.8
	if _light:
		_light.light_energy = 1.35 + sin(_t * 3.3) * 0.35
	if _burst and not _burst.emitting:
		_burst.position = Vector3(0, 0.35, 0)


func can_interact() -> bool:
	return not consumed


func get_prompt() -> String:
	return "拾起余烬 · " + display_name


func interact(player: Node) -> void:
	if consumed:
		return
	consumed = true
	AudioDirector.sfx("pickup", -2.0)
	if _burst:
		_burst.emitting = true
	var target: Vector3 = player.global_position + Vector3(0, 1.1, 0)
	var tw := create_tween().set_parallel(true)
	tw.tween_property(_visual, "global_position", target, 0.35).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
	tw.tween_property(_visual, "scale", Vector3.ONE * 0.08, 0.35)
	tw.tween_property(_light, "light_energy", 0.0, 0.35)
	collected.emit(self)
	var timer := get_tree().create_timer(0.9)
	timer.timeout.connect(func(): queue_free())
