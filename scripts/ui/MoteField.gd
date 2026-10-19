extends Control
class_name MoteField

## Cheap, deterministic drifting motes and petals. Purely a 2D canvas effect.

var _motes: Array = []
var _petals: Array = []
var _t := 0.0
var _rng := RandomNumberGenerator.new()


func setup(count: int = 64, petal_count: int = 16, seed_value: int = 7) -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_rng.seed = seed_value
	for i in count:
		_motes.append({
			"x": _rng.randf(),
			"y": _rng.randf(),
			"r": _rng.randf_range(0.7, 2.2),
			"vx": _rng.randf_range(-0.006, 0.012),
			"vy": _rng.randf_range(-0.012, -0.003),
			"ph": _rng.randf() * TAU,
			"a": _rng.randf_range(0.15, 0.7),
			"warm": _rng.randf(),
		})
	for i in petal_count:
		_petals.append({
			"x": _rng.randf(),
			"y": _rng.randf(),
			"vx": _rng.randf_range(-0.02, 0.005),
			"vy": _rng.randf_range(0.006, 0.02),
			"rot": _rng.randf() * TAU,
			"sp": _rng.randf_range(-0.4, 0.4),
			"a": _rng.randf_range(0.18, 0.5),
			"size": _rng.randf_range(2.4, 5.2),
		})
	set_process(true)


func _process(delta: float) -> void:
	_t += delta
	queue_redraw()


func _draw() -> void:
	var w := size.x
	var h := size.y
	if w < 10.0 or h < 10.0:
		return
	for p in _motes:
		p["x"] += float(p["vx"]) * (delta_safe() * 60.0) / maxf(1.0, w)
		p["y"] += float(p["vy"]) * (delta_safe() * 60.0) / maxf(1.0, h)
		if p["x"] < -0.02: p["x"] = 1.02
		if p["x"] > 1.02: p["x"] = -0.02
		if p["y"] < -0.02: p["y"] = 1.02
		if p["y"] > 1.02: p["y"] = -0.02
		var px := float(p["x"]) * w + sin(_t * 0.7 + float(p["ph"])) * 6.0
		var py := float(p["y"]) * h + cos(_t * 0.5 + float(p["ph"])) * 4.0
		var col := Color("#f0d49a") if float(p["warm"]) > 0.45 else Color("#c9e5d8")
		col.a = float(p["a"]) * (0.6 + 0.4 * sin(_t * 1.3 + float(p["ph"])))
		draw_circle(Vector2(px, py), float(p["r"]), col)
	for p in _petals:
		p["x"] += float(p["vx"]) * (delta_safe() * 60.0) / maxf(1.0, w)
		p["y"] += float(p["vy"]) * (delta_safe() * 60.0) / maxf(1.0, h)
		p["rot"] += float(p["sp"]) * delta_safe()
		if p["y"] > 1.04:
			p["y"] = -0.04
			p["x"] = _rng.randf()
		if p["x"] < -0.04: p["x"] = 1.04
		if p["x"] > 1.04: p["x"] = -0.04
		var px := float(p["x"]) * w
		var py := float(p["y"]) * h
		var s := float(p["size"])
		var rot := float(p["rot"])
		var pts := PackedVector2Array([
			Vector2(px + cos(rot) * s, py + sin(rot) * s * 0.5),
			Vector2(px + cos(rot + 1.7) * s * 0.7, py + sin(rot + 1.7) * s * 0.5),
			Vector2(px + cos(rot + 3.2) * s, py + sin(rot + 3.2) * s * 0.5),
			Vector2(px + cos(rot + 4.8) * s * 0.6, py + sin(rot + 4.8) * s * 0.5),
		])
		draw_colored_polygon(pts, Color(0.93, 0.68, 0.67, float(p["a"]) * 0.8))


var _last_delta := 0.016


func delta_safe() -> float:
	# using a stable small step keeps the drift independent from frame timing
	_last_delta = _last_delta * 0.9 + 0.016 * 0.1
	return 0.016
