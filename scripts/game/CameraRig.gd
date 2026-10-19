extends Node3D
class_name CameraRig

## Fixed oblique perspective follow camera with a soft spring arm and optional
## small orbit. Default framing is a storybook 3/4 diorama view.

signal zoom_changed(value: float)

var target: Node3D
var spring_arm: SpringArm3D
var camera: Camera3D
var yaw := -36.0
var pitch := -38.0
var target_distance := 19.0
var min_distance := 11.0
var max_distance := 27.0
var base_yaw := -36.0
var allow_orbit := true
var photo_mode := false
var _shake_time := 0.0
var _shake_amp := 0.0
var _focus_pos := Vector3.ZERO
var _has_focus := false
var _focus_distance := 22.0
var _mouse_orbiting := false
var _initialized := false


func setup(follow: Node3D, cfg: Dictionary) -> void:
	target = follow
	yaw = float(cfg.get("yaw", -36.0))
	pitch = float(cfg.get("pitch", -38.0))
	base_yaw = yaw
	target_distance = float(cfg.get("distance", 19.0))
	var fov := float(cfg.get("fov", 42.0))
	_build(fov)
	global_position = target.global_position + Vector3(0, 1.3, 0)
	_apply_rotation()
	_initialized = true
	set_process(true)
	set_process_unhandled_input(true)


func _build(fov: float) -> void:
	spring_arm = SpringArm3D.new()
	spring_arm.name = "SpringArm"
	spring_arm.collision_mask = 1
	spring_arm.margin = 0.25
	spring_arm.spring_length = target_distance
	var sphere := SphereShape3D.new()
	sphere.radius = 0.28
	spring_arm.shape = sphere
	add_child(spring_arm)
	camera = Camera3D.new()
	camera.name = "Camera"
	camera.fov = fov
	camera.near = 0.08
	camera.far = 650.0
	camera.current = true
	spring_arm.add_child(camera)


func _apply_rotation() -> void:
	if spring_arm:
		spring_arm.rotation_degrees = Vector3(pitch, yaw, 0.0)


func _process(delta: float) -> void:
	if target and is_instance_valid(target):
		var desired := target.global_position + Vector3(0, 1.35, 0)
		if _has_focus:
			desired = _focus_pos
		var k := 1.0 - exp(-8.0 * delta)
		global_position = global_position.lerp(desired, k)
	if photo_mode:
		yaw += delta * 2.2
	_apply_rotation()
	if spring_arm:
		var length := target_distance
		if _has_focus:
			length = _focus_distance
		var k2 := 1.0 - exp(-5.0 * delta)
		spring_arm.spring_length = lerpf(spring_arm.spring_length, length, k2)
	if camera:
		if _shake_time > 0.0:
			_shake_time -= delta
			var s := _shake_amp * clampf(_shake_time / 0.35, 0.0, 1.0)
			camera.h_offset = randf_range(-s, s)
			camera.v_offset = randf_range(-s, s)
		else:
			camera.h_offset = move_toward(camera.h_offset, 0.0, delta * 2.0)
			camera.v_offset = move_toward(camera.v_offset, 0.0, delta * 2.0)
	if allow_orbit and not photo_mode:
		var orbit := 0.0
		if Input.is_action_pressed("camera_left"):
			orbit += 1.0
		if Input.is_action_pressed("camera_right"):
			orbit -= 1.0
		if orbit != 0.0:
			yaw += orbit * 55.0 * delta
			yaw = clampf(yaw, base_yaw - 62.0, base_yaw + 62.0)
		if Input.is_action_just_pressed("zoom_in"):
			target_distance = maxf(min_distance, target_distance - 1.2)
			zoom_changed.emit(target_distance)
		if Input.is_action_just_pressed("zoom_out"):
			target_distance = minf(max_distance, target_distance + 1.2)
			zoom_changed.emit(target_distance)


func _unhandled_input(event: InputEvent) -> void:
	if not allow_orbit or photo_mode:
		return
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_RIGHT:
			_mouse_orbiting = event.pressed
		elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_UP:
			target_distance = maxf(min_distance, target_distance - 1.4)
			zoom_changed.emit(target_distance)
			get_viewport().set_input_as_handled()
		elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			target_distance = minf(max_distance, target_distance + 1.4)
			zoom_changed.emit(target_distance)
			get_viewport().set_input_as_handled()
	elif event is InputEventMouseMotion and _mouse_orbiting:
		yaw -= event.relative.x * 0.15
		yaw = clampf(yaw, base_yaw - 62.0, base_yaw + 62.0)
		pitch = clampf(pitch - event.relative.y * 0.1, -54.0, -26.0)
		get_viewport().set_input_as_handled()


func shake(amplitude: float = 0.25, duration: float = 0.35) -> void:
	_shake_amp = amplitude
	_shake_time = maxf(_shake_time, duration)


func focus_on(pos: Vector3, distance: float = 22.0) -> void:
	_focus_pos = pos
	_focus_distance = distance
	_has_focus = true


func clear_focus() -> void:
	_has_focus = false


func get_yaw_rad() -> float:
	return deg_to_rad(yaw)


func set_photo_mode(enabled: bool) -> void:
	photo_mode = enabled


func get_camera() -> Camera3D:
	return camera
