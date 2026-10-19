extends Control
class_name InkToggle

signal toggled(value: bool)

var label_text := ""
var value := false
var on_paper := true
var _font: Font


func setup(title: String, initial: bool) -> void:
	label_text = title
	value = initial
	custom_minimum_size = Vector2(300, 40)
	mouse_filter = Control.MOUSE_FILTER_STOP
	focus_mode = Control.FOCUS_ALL
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_font = ThemeKit.font("body")


func set_value(v: bool, silent: bool = false) -> void:
	v = bool(v)
	if v == value:
		return
	value = v
	queue_redraw()
	if not silent:
		toggled.emit(value)


func _gui_input(event: InputEvent) -> void:
	var trigger := false
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		trigger = true
	if event is InputEventKey and event.pressed and (event.is_action_pressed("ui_accept") or event.keycode == KEY_SPACE):
		trigger = true
	if trigger:
		grab_focus()
		set_value(not value)
		accept_event()


func _draw() -> void:
	var ink := ThemeKit.INK
	if not on_paper:
		ink = ThemeKit.PAPER
	draw_string(_font, Vector2(0, 24), label_text, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, ink)
	var tw := 44.0
	var th := 22.0
	var x := size.x - tw
	var y := 9.0
	var bg := Color(ink, 0.16)
	if value:
		bg = ThemeKit.JADE_DARK
	draw_style_box(_pill(bg), Rect2(x, y, tw, th))
	draw_circle(Vector2(x + (tw - 8.0 if value else 8.0), y + th * 0.5), 7.5, Color("#f6ecd8") if value else Color(ink, 0.55))
	if has_focus():
		draw_style_box(_focus_pill(), Rect2(x - 3, y - 3, tw + 6, th + 6))


func _pill(bg: Color) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.set_corner_radius_all(12)
	return sb


func _focus_pill() -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0, 0, 0, 0)
	sb.border_color = Color(ThemeKit.GOLD_DIM, 0.55)
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(14)
	return sb
