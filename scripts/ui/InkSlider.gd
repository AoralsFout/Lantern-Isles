extends Control
class_name InkSlider

signal value_changed(value: float)

var label_text := ""
var min_value := 0.0
var max_value := 1.0
var step := 0.01
var value := 0.0
var suffix := ""
var on_paper := true
var _dragging := false
var _font: Font


func setup(title: String, min_v: float, max_v: float, step_v: float, initial: float, suffix_text: String = "") -> void:
	label_text = title
	min_value = min_v
	max_value = max_v
	step = maxf(0.001, step_v)
	value = clampf(initial, min_value, max_value)
	suffix = suffix_text
	custom_minimum_size = Vector2(360, 55)
	mouse_filter = Control.MOUSE_FILTER_STOP
	focus_mode = Control.FOCUS_ALL
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_font = ThemeKit.font("body")
	set_process(false)


func set_value(v: float, silent: bool = false) -> void:
	var nv := clampf(snapped(v, step), min_value, max_value)
	if is_equal_approx(nv, value):
		value = nv
		queue_redraw()
		return
	value = nv
	queue_redraw()
	if not silent:
		value_changed.emit(value)


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			_dragging = true
			grab_focus()
			_set_from_x(event.position.x)
			accept_event()
		else:
			_dragging = false
			accept_event()
	elif event is InputEventMouseMotion and _dragging:
		_set_from_x(event.position.x)
		accept_event()
	elif event is InputEventKey and event.pressed:
		if event.is_action_pressed("ui_left"):
			set_value(value - step)
			accept_event()
		elif event.is_action_pressed("ui_right"):
			set_value(value + step)
			accept_event()


func _set_from_x(x: float) -> void:
	var pad := 7.0
	var track := size.x - pad * 2.0
	var ratio := clampf((x - pad) / maxf(1.0, track), 0.0, 1.0)
	set_value(lerpf(min_value, max_value, ratio))


func _draw() -> void:
	var ink := ThemeKit.INK
	var muted := Color(ThemeKit.INK, 0.55)
	var gold := ThemeKit.GOLD_DIM
	if not on_paper:
		ink = ThemeKit.PAPER
		muted = Color(ThemeKit.PAPER_2, 0.55)
		gold = ThemeKit.GOLD
	draw_string(_font, Vector2(0, 14), label_text, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, ink)
	var pct := ""
	if suffix == "%":
		pct = "%d%%" % int(round(value * 100.0))
	else:
		pct = "%s%s" % [str(snapped(value, step)), suffix]
	var tw := _font.get_string_size(pct, HORIZONTAL_ALIGNMENT_LEFT, -1, 13).x
	draw_string(_font, Vector2(size.x - tw, 14), pct, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, muted)
	var pad := 7.0
	var track_y := 35.0
	var w := size.x - pad * 2.0
	draw_rect(Rect2(pad, track_y, w, 3), Color(ink, 0.16))
	var ratio := (value - min_value) / maxf(0.0001, max_value - min_value)
	draw_rect(Rect2(pad, track_y, w * ratio, 3), gold)
	var kx := pad + w * ratio
	draw_circle(Vector2(kx, track_y + 1.5), 6.0, gold)
	draw_circle(Vector2(kx, track_y + 1.5), 2.2, Color("#f7ecd6") if on_paper else Color("#16201d"))
	if has_focus():
		draw_arc(Vector2(kx, track_y + 1.5), 9.0, 0, TAU, 24, Color(gold, 0.4), 1.0)
