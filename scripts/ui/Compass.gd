extends Control
class_name Compass

## A hand-drawn brass compass ribbon. Cardinal ticks rotate with the camera and
## the current beacon is marked with a small lantern diamond.

const WIDTH := 460.0
const RANGE_DEG := 62.0
const PX_PER_DEG := 460.0 / (RANGE_DEG * 2.0)

var game
var world: Dictionary = {}
var beacon := Vector3.ZERO
var _font: Font
var _roman_font: Font
var _pulse := 0.0


func setup(game_ref: Node, world_data: Dictionary) -> void:
	game = game_ref
	world = world_data
	var b: Array = world.get("beacon", [0, 0, 0])
	beacon = Vector3(float(b[0]), float(b[1]), float(b[2]))
	_font = ThemeKit.font("latin")
	_roman_font = ThemeKit.font("body")
	clip_contents = true
	set_process(true)


func _process(delta: float) -> void:
	_pulse += delta
	queue_redraw()


func _camera_heading() -> float:
	var cam := get_viewport().get_camera_3d()
	if cam == null:
		return 0.0
	var f := -cam.global_transform.basis.z
	var flat := Vector2(f.x, f.z)
	if flat.length() < 0.01:
		return 0.0
	# 0° = north = -Z, positive clockwise to +X
	return atan2(flat.x, -flat.y)


func _draw() -> void:
	var sb := ThemeKit.stylebox(Color(0.014, 0.026, 0.021, 0.82), Color(ThemeKit.GOLD, 0.4), 1, 28, 0, 0)
	draw_style_box(sb, Rect2(0, 12, WIDTH, 34))
	# hairline top / bottom
	draw_line(Vector2(64, 12), Vector2(WIDTH - 64, 12), Color(ThemeKit.GOLD, 0.4), 1.0)
	draw_line(Vector2(64, 46), Vector2(WIDTH - 64, 46), Color(ThemeKit.GOLD, 0.22), 1.0)

	var heading := _camera_heading()
	var center := WIDTH * 0.5
	var range_rad := deg_to_rad(RANGE_DEG)
	# ticks at fixed world bearings, sliding under the fixed centre caret
	for bearing in range(0, 360, 5):
		var rel := wrapf(deg_to_rad(float(bearing)) - heading, -PI, PI)
		if absf(rel) > range_rad:
			continue
		var x := center + rad_to_deg(rel) * PX_PER_DEG
		var major := bearing % 30 == 0
		var col := Color(ThemeKit.PAPER_2, 0.9 if major else 0.42)
		if major:
			draw_line(Vector2(x, 31), Vector2(x, 37), col, 1.0)
		else:
			draw_line(Vector2(x, 34), Vector2(x, 37), col, 1.0)
		if bearing % 90 == 0:
			var label: String = ["N", "E", "S", "W"][bearing / 90]
			var fs := 13
			var w := _font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
			draw_string(_font, Vector2(x - w * 0.5, 27), label, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color(ThemeKit.GOLD_BRIGHT, 1.0))

	# center caret
	var tri := PackedVector2Array([Vector2(center - 5, 3), Vector2(center + 5, 3), Vector2(center, 10)])
	draw_colored_polygon(tri, ThemeKit.GOLD_BRIGHT)
	draw_line(Vector2(center, 10), Vector2(center, 17), Color(ThemeKit.GOLD, 0.4), 1.0)

	# beacon marker, clamped to the visible ribbon
	if game != null and game.player:
		var to_player: Vector3 = game.player.global_position - beacon
		var dist := Vector2(to_player.x, to_player.z).length()
		var bearing := atan2(-to_player.x, to_player.z)
		var rel := wrapf(bearing - heading, -PI, PI)
		var clamped := clampf(rel, -range_rad, range_rad)
		var x := center + rad_to_deg(clamped) * PX_PER_DEG
		var a := 1.0 if absf(rel) < range_rad else 0.32
		var pulse := 0.7 + 0.3 * sin(_pulse * 2.4)
		var dia := PackedVector2Array([Vector2(x, 22), Vector2(x + 5, 29), Vector2(x, 36), Vector2(x - 5, 29)])
		draw_colored_polygon(dia, Color(ThemeKit.GOLD_BRIGHT, a * pulse))
		draw_circle(Vector2(x, 29), 2.0, Color("#fff3d2"))
		var dt := "%d m" % int(dist)
		var wd := _font.get_string_size(dt, HORIZONTAL_ALIGNMENT_LEFT, -1, 11).x
		draw_string(_font, Vector2(center - wd * 0.5, 58), dt, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(ThemeKit.PAPER_2, 0.36))


func _cardinal(angle: float) -> String:
	var deg := rad_to_deg(angle)
	var idx := int(round(deg / 90.0)) % 4
	return ["N", "E", "S", "W"][posmod(idx, 4)]

