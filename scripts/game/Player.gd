extends CharacterBody3D
class_name Player

## The little lantern keeper: a capsule, a straw hat, a scarf and a warm light.

signal landed(impact: float)
signal jumped
signal stepped

const WALK_SPEED := 6.2
const RUN_SPEED := 9.4
const ACCEL := 34.0
const AIR_ACCEL := 12.0
const JUMP_SPEED := 5.1
const GRAVITY := 17.5

var controls_enabled := true
var camera_rig: CameraRig
var footstep_style := "grass"
var visual: Node3D
var lantern: Node3D
var lantern_light: OmniLight3D
var _coyote := 0.0
var _jump_buffer := 0.0
var _step_dist := 0.0
var _walk_phase := 0.0
var _fall_speed := 0.0
var _was_on_floor := true
var _t := 0.0
var _lantern_base: Vector3


func _ready() -> void:
	add_to_group("player")
	collision_layer = 2
	collision_mask = 1
	floor_max_angle = deg_to_rad(50.0)
	floor_snap_length = 0.5
	floor_stop_on_slope = true
	wall_min_slide_angle = deg_to_rad(18.0)
	_build_body()
	_build_visual()
	set_physics_process(true)
	set_process(true)


func _build_body() -> void:
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.36
	capsule.height = 1.32
	shape.shape = capsule
	shape.position.y = 0.78
	add_child(shape)


func _build_visual() -> void:
	visual = Node3D.new()
	visual.name = "Visual"
	add_child(visual)

	var body_mat := StandardMaterial3D.new()
	body_mat.albedo_color = Color("#f0e2c4")
	body_mat.roughness = 0.82
	var body := MeshInstance3D.new()
	var capsule := CapsuleMesh.new()
	capsule.radius = 0.36
	capsule.height = 1.16
	capsule.radial_segments = 12
	capsule.rings = 5
	body.mesh = capsule
	body.position.y = 0.8
	body.material_override = body_mat
	visual.add_child(body)

	# long coat / cloak
	var robe := MeshInstance3D.new()
	var robe_mesh := CylinderMesh.new()
	robe_mesh.top_radius = 0.3
	robe_mesh.bottom_radius = 0.46
	robe_mesh.height = 0.7
	robe_mesh.radial_segments = 10
	robe.mesh = robe_mesh
	robe.position.y = 0.42
	var robe_mat := StandardMaterial3D.new()
	robe_mat.albedo_color = Color("#355f56")
	robe_mat.roughness = 0.9
	robe_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	robe.material_override = robe_mat
	visual.add_child(robe)

	# scarf
	var scarf := MeshInstance3D.new()
	var torus := TorusMesh.new()
	torus.inner_radius = 0.26
	torus.outer_radius = 0.4
	torus.rings = 16
	torus.ring_segments = 5
	scarf.mesh = torus
	scarf.position.y = 1.18
	var scarf_mat := StandardMaterial3D.new()
	scarf_mat.albedo_color = Color("#bf6d56")
	scarf_mat.roughness = 0.9
	scarf.material_override = scarf_mat
	visual.add_child(scarf)
	var scarf_tail := MeshInstance3D.new()
	var tb := BoxMesh.new()
	tb.size = Vector3(0.18, 0.62, 0.04)
	scarf_tail.mesh = tb
	scarf_tail.position = Vector3(-0.33, 0.86, -0.18)
	scarf_tail.rotation_degrees = Vector3(-8, 0, 9)
	scarf_tail.material_override = scarf_mat
	visual.add_child(scarf_tail)

	# straw hat, slightly oversized
	var hat := Node3D.new()
	hat.position.y = 1.48
	hat.rotation_degrees = Vector3(-5, 0, 4)
	visual.add_child(hat)
	var brim := MeshInstance3D.new()
	var bm := CylinderMesh.new()
	bm.top_radius = 0.58
	bm.bottom_radius = 0.66
	bm.height = 0.09
	bm.radial_segments = 12
	brim.mesh = bm
	var straw := StandardMaterial3D.new()
	straw.albedo_color = Color("#c3a26b")
	straw.roughness = 0.95
	brim.material_override = straw
	hat.add_child(brim)
	var crown := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.23
	cm.bottom_radius = 0.32
	cm.height = 0.23
	crown.mesh = cm
	crown.position.y = 0.14
	crown.material_override = straw
	hat.add_child(crown)
	var band := MeshInstance3D.new()
	var bandm := CylinderMesh.new()
	bandm.top_radius = 0.325
	bandm.bottom_radius = 0.325
	bandm.height = 0.055
	band.mesh = bandm
	band.position.y = 0.04
	var band_mat := StandardMaterial3D.new()
	band_mat.albedo_color = Color("#7a3f34")
	band.material_override = band_mat
	hat.add_child(band)

	# eyes, facing +Z so the body can rotate toward movement with atan2(x,z)
	for sx in [-1.0, 1.0]:
		var eye := MeshInstance3D.new()
		var em := SphereMesh.new()
		em.radius = 0.03
		em.height = 0.06
		eye.mesh = em
		eye.position = Vector3(0.12 * sx, 1.03, 0.345)
		var emat := StandardMaterial3D.new()
		emat.albedo_color = Color("#24312d")
		eye.material_override = emat
		visual.add_child(eye)

	# small brass ring on the back
	var ring := MeshInstance3D.new()
	var tm := TorusMesh.new()
	tm.inner_radius = 0.09
	tm.outer_radius = 0.12
	tm.rings = 12
	tm.ring_segments = 5
	ring.mesh = tm
	ring.position = Vector3(0, 1.15, -0.36)
	ring.rotation_degrees = Vector3(90, 0, 0)
	var rm := StandardMaterial3D.new()
	rm.albedo_color = Color("#d1a65e")
	rm.metallic = 0.4
	rm.roughness = 0.4
	ring.material_override = rm
	visual.add_child(ring)

	# lantern on a crook, the little sun of the whole game
	lantern = Node3D.new()
	lantern.position = Vector3(0.58, 0.95, 0.18)
	visual.add_child(lantern)
	_lantern_base = lantern.position
	var hook := MeshInstance3D.new()
	var hm := CylinderMesh.new()
	hm.top_radius = 0.012
	hm.bottom_radius = 0.012
	hm.height = 0.55
	hook.mesh = hm
	hook.position.y = 0.28
	hook.rotation_degrees = Vector3(0, 0, 22)
	var hmat := StandardMaterial3D.new()
	hmat.albedo_color = Color("#4a3c2f")
	hook.material_override = hmat
	lantern.add_child(hook)
	var cage := MeshInstance3D.new()
	var cage_mesh := SphereMesh.new()
	cage_mesh.radius = 0.17
	cage_mesh.height = 0.34
	cage.mesh = cage_mesh
	var cage_mat := StandardMaterial3D.new()
	cage_mat.albedo_color = Color("#ffdba0")
	cage_mat.emission_enabled = true
	cage_mat.emission = Color("#ffc271")
	cage_mat.emission_energy_multiplier = 4.2
	cage.material_override = cage_mat
	lantern.add_child(cage)
	var cage_ring := MeshInstance3D.new()
	var cr := TorusMesh.new()
	cr.inner_radius = 0.17
	cr.outer_radius = 0.19
	cr.rings = 12
	cr.ring_segments = 4
	cage_ring.mesh = cr
	cage_ring.rotation_degrees = Vector3(90, 0, 0)
	var crm := StandardMaterial3D.new()
	crm.albedo_color = Color("#7b5938")
	crm.metallic = 0.3
	cage_ring.material_override = crm
	lantern.add_child(cage_ring)

	lantern_light = OmniLight3D.new()
	lantern_light.light_color = Color("#ffcf8d")
	lantern_light.light_energy = 1.1
	lantern_light.omni_range = 8.0
	lantern_light.omni_attenuation = 1.35
	lantern_light.shadow_enabled = false
	lantern_light.distance_fade_enabled = true
	lantern_light.distance_fade_begin = 40.0
	lantern_light.distance_fade_length = 16.0
	lantern.add_child(lantern_light)


func _physics_process(delta: float) -> void:
	var input_vec := Vector2.ZERO
	if controls_enabled:
		input_vec = Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var dir := Vector3.ZERO
	if input_vec.length() > 0.03:
		var cam := get_viewport().get_camera_3d()
		if cam:
			var b := cam.global_transform.basis
			var right := Vector3(b.x.x, 0, b.x.z).normalized()
			var forward := Vector3(-b.z.x, 0, -b.z.z).normalized()
			dir = (right * input_vec.x + forward * (-input_vec.y)).normalized()
		else:
			dir = Vector3(input_vec.x, 0, input_vec.y).normalized()

	var sprint := controls_enabled and Input.is_action_pressed("sprint")
	var target_speed := RUN_SPEED if sprint else WALK_SPEED
	var target := dir * target_speed
	var accel := ACCEL if is_on_floor() else AIR_ACCEL
	velocity.x = move_toward(velocity.x, target.x, accel * delta)
	velocity.z = move_toward(velocity.z, target.z, accel * delta)
	if dir.length() < 0.01 and is_on_floor():
		velocity.x = move_toward(velocity.x, 0.0, ACCEL * 1.4 * delta)
		velocity.z = move_toward(velocity.z, 0.0, ACCEL * 1.4 * delta)

	_jump_buffer -= delta
	_coyote -= delta
	if is_on_floor():
		_coyote = 0.12
	if controls_enabled and Input.is_action_just_pressed("jump"):
		_jump_buffer = 0.13
	if _jump_buffer > 0.0 and _coyote > 0.0:
		velocity.y = JUMP_SPEED
		_jump_buffer = 0.0
		_coyote = 0.0
		AudioDirector.sfx("jump", -5.0, 0.03)
		jumped.emit()

	_fall_speed = velocity.y
	velocity.y -= GRAVITY * delta
	if is_on_floor() and velocity.y < 0.0:
		velocity.y = -1.0
	move_and_slide()

	var on_floor := is_on_floor()
	if on_floor and not _was_on_floor:
		var impact := clampf(absf(_fall_speed), 0.0, 14.0)
		if impact > 2.2:
			AudioDirector.sfx("land", -11.0 + impact * 0.4, 0.04)
			landed.emit(impact)
	_was_on_floor = on_floor

	var flat_speed := Vector2(velocity.x, velocity.z).length()
	if flat_speed > 0.4 and on_floor:
		_walk_phase += delta * flat_speed
		_step_dist += flat_speed * delta
		if _step_dist > 2.15:
			_step_dist = 0.0
			AudioDirector.step(footstep_style)
			stepped.emit()
	else:
		_step_dist = 0.0

	if dir.length() > 0.05:
		var target_yaw := atan2(dir.x, dir.z)
		visual.rotation.y = lerp_angle(visual.rotation.y, target_yaw, 1.0 - exp(-10.0 * delta))
	_animate_visual(delta, flat_speed, on_floor)


func _process(delta: float) -> void:
	_t += delta
	if lantern_light:
		lantern_light.light_energy = 1.0 + sin(_t * 4.1) * 0.08 + sin(_t * 7.7 + 1.2) * 0.035


func _animate_visual(delta: float, speed: float, on_floor: bool) -> void:
	if visual == null:
		return
	var bob := 0.0
	if on_floor and speed > 0.5:
		bob = sin(_walk_phase * 4.0) * 0.035
	elif on_floor:
		bob = sin(_t * 1.6) * 0.008
	visual.position.y = bob
	if not on_floor:
		visual.rotation.x = lerp_angle(visual.rotation.x, -0.08, 1.0 - exp(-4.0 * delta))
	else:
		var lean := -0.05 * (1.0 if Input.is_action_pressed("sprint") else 0.0)
		visual.rotation.x = lerp_angle(visual.rotation.x, lean, 1.0 - exp(-6.0 * delta))
	if lantern:
		var swing := sin(_walk_phase * 4.0) * 0.09 * clampf(speed / RUN_SPEED, 0.0, 1.0)
		lantern.rotation.z = swing + sin(_t * 1.3) * 0.02
		lantern.position = _lantern_base + Vector3(0, sin(_t * 1.7) * 0.015, 0)


func set_controls(enabled: bool) -> void:
	controls_enabled = enabled
	if not enabled:
		velocity.x = 0.0
		velocity.z = 0.0


func teleport(pos: Vector3) -> void:
	global_position = pos
	velocity = Vector3.ZERO
	_was_on_floor = false


func set_footstep_style(style: String) -> void:
	footstep_style = style
