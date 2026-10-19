extends Area3D
class_name ZoneTrigger

signal player_entered(zone_name: String)

var zone_name := ""
var _cooldown := 0.0


func setup(title: String, pos: Vector3, radius: float) -> void:
	zone_name = title
	position = pos
	collision_layer = 0
	collision_mask = 2
	monitoring = true
	var cs := CollisionShape3D.new()
	var shape := CylinderShape3D.new()
	shape.radius = maxf(3.0, radius)
	shape.height = 44.0
	cs.shape = shape
	add_child(cs)
	body_entered.connect(_on_body_entered)
	set_process(true)


func _on_body_entered(body: Node3D) -> void:
	if _cooldown > 0.0:
		return
	if body.is_in_group("player"):
		_cooldown = 5.0
		player_entered.emit(zone_name)


func _process(delta: float) -> void:
	_cooldown = maxf(0.0, _cooldown - delta)
