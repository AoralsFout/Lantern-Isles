extends Control
class_name DialogueBox

## Bottom-screen story dialogue with a typewriter cadence, soft paper panel and
## a name seal. E / click advances, Esc closes.

var _panel: PanelContainer
var _name_label: Label
var _text_label: Label
var _hint: Label
var _seal: Label
var _lines: Array = []
var _index := 0
var _open := false
var _on_close: Callable = Callable()
var _typing := false
var _type_accum := 0.0
var _blip_accum := 0.0
var _full_text := ""
var _tween: Tween


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false
	_build()


func _build() -> void:
	var shade := ColorRect.new()
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.color = Color(0.02, 0.03, 0.028, 0.36)
	shade.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(shade)

	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	center.offset_top = -310
	center.offset_bottom = -36
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(center)

	_panel = PanelContainer.new()
	_panel.add_theme_stylebox_override("panel", ThemeKit.stylebox(Color(0.04, 0.055, 0.05, 0.93), Color(ThemeKit.GOLD, 0.45), 1, 8, 30, 22))
	_panel.custom_minimum_size = Vector2(1060, 214)
	_panel.mouse_filter = Control.MOUSE_FILTER_STOP
	center.add_child(_panel)

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 26)
	_panel.add_child(row)

	var seal_box := CenterContainer.new()
	seal_box.custom_minimum_size = Vector2(108, 108)
	seal_box.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	row.add_child(seal_box)
	var seal_panel := PanelContainer.new()
	seal_panel.add_theme_stylebox_override("panel", ThemeKit.stylebox(Color(ThemeKit.GOLD, 0.09), Color(ThemeKit.GOLD, 0.5), 1, 54, 0, 0))
	seal_panel.custom_minimum_size = Vector2(92, 92)
	seal_box.add_child(seal_panel)
	_seal = ThemeKit.label("灯", 38, ThemeKit.GOLD_BRIGHT, "display")
	_seal.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_seal.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	seal_panel.add_child(_seal)

	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 8)
	col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(col)
	var name_row := HBoxContainer.new()
	name_row.add_theme_constant_override("separation", 12)
	col.add_child(name_row)
	_name_label = ThemeKit.label("", 22, ThemeKit.GOLD_BRIGHT, "display")
	name_row.add_child(_name_label)
	var line := ColorRect.new()
	line.color = Color(ThemeKit.GOLD, 0.32)
	line.custom_minimum_size = Vector2(70, 1)
	line.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	name_row.add_child(line)
	var role := ThemeKit.label("记 忆 回 声", 11, Color(ThemeKit.PAPER_2, 0.38))
	role.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	name_row.add_child(role)

	_text_label = ThemeKit.label("", 20, ThemeKit.PAPER)
	_text_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_text_label.custom_minimum_size = Vector2(780, 86)
	_text_label.vertical_alignment = VERTICAL_ALIGNMENT_TOP
	_text_label.add_theme_constant_override("line_spacing", 7)
	col.add_child(_text_label)

	var hint_row := HBoxContainer.new()
	hint_row.add_theme_constant_override("separation", 8)
	col.add_child(hint_row)
	hint_row.add_child(ThemeKit.keycap("E"))
	_hint = ThemeKit.label("继续", 12, Color(ThemeKit.PAPER_2, 0.55))
	hint_row.add_child(_hint)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hint_row.add_child(spacer)
	var deco := ThemeKit.label("·  ·  ·", 13, Color(ThemeKit.GOLD, 0.3), "latin")
	hint_row.add_child(deco)


func open(speaker: String, lines: Array, on_close: Callable = Callable()) -> void:
	_lines = lines
	_index = 0
	_on_close = on_close
	_name_label.text = speaker
	_open = true
	visible = true
	_panel.modulate.a = 0.0
	_panel.position.y = 16
	AudioDirector.ui("back")
	var tw := create_tween().set_parallel(true)
	tw.tween_property(_panel, "modulate:a", 1.0, 0.28)
	tw.tween_property(_panel, "position:y", 0.0, 0.36).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	_show_line()


func _show_line() -> void:
	if _index >= _lines.size():
		close()
		return
	_full_text = str(_lines[_index])
	_text_label.text = _full_text
	_text_label.visible_characters = 0
	_typing = true
	_type_accum = 0.0
	_blip_accum = 0.0
	_hint.text = "跳过" if _index < _lines.size() - 1 else "听完"


func _process(delta: float) -> void:
	if not _open:
		return
	if _typing:
		_type_accum += delta * 38.0
		_text_label.visible_characters = int(_type_accum)
		_blip_accum += delta
		if _blip_accum > 0.085 and _text_label.visible_characters < _full_text.length():
			_blip_accum = 0.0
			AudioDirector.sfx("dialogue", -22.0, 0.08)
		if _text_label.visible_characters >= _full_text.length():
			_typing = false
			_text_label.visible_characters = -1


func _unhandled_input(event: InputEvent) -> void:
	if not _open:
		return
	if event.is_action_pressed("interact") or event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		get_viewport().set_input_as_handled()
		_advance()
	elif event.is_action_pressed("pause"):
		get_viewport().set_input_as_handled()
		close()


func _advance() -> void:
	if _typing:
		_typing = false
		_text_label.visible_characters = -1
		return
	_index += 1
	if _index >= _lines.size():
		close()
	else:
		_show_line()


func close() -> void:
	if not _open:
		return
	_open = false
	_typing = false
	var tw := create_tween().set_parallel(true)
	tw.tween_property(_panel, "modulate:a", 0.0, 0.2)
	tw.tween_property(_panel, "position:y", 12.0, 0.2)
	await tw.finished
	visible = false
	if _on_close.is_valid():
		var cb := _on_close
		_on_close = Callable()
		cb.call()


func is_open() -> bool:
	return _open
