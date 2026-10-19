extends Control
class_name Hud

## Minimal, quiet HUD: chapter name, ember tally, compass, prompts, zone titles
## and soft toast messages. No default Godot controls are used.

var game: Node
var chapter_index := 0
var chapter_meta: Dictionary = {}
var world: Dictionary = {}

var _root: Control
var _hud_group: Control
var _chapter_label: Label
var _title_label: Label
var _objective_label: Label
var _ember_text: Label
var _pips: Array[Label] = []
var _prompt_panel: PanelContainer
var _prompt_label: Label
var _zone_panel: VBoxContainer
var _zone_label: Label
var _toast_panel: PanelContainer
var _toast_title: Label
var _toast_caption: Label
var _toast_icon: TextureRect
var _fade: ColorRect
var _compass: Compass
var _hint: Label
var _toast_tween: Tween
var _zone_tween: Tween
var _hud_visible := true
var _hud_tween: Tween


func setup(game_ref: Node, ch_index: int, meta: Dictionary, world_data: Dictionary) -> void:
	game = game_ref
	chapter_index = ch_index
	chapter_meta = meta
	world = world_data
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build()
	set_visible_hud(true)


func _build() -> void:
	_hud_group = Control.new()
	_hud_group.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_hud_group.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_hud_group)

	# chapter plaque -----------------------------------------------------------------
	var tl := MarginContainer.new()
	tl.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)
	tl.offset_left = 44
	tl.offset_top = 34
	tl.offset_right = 620
	tl.offset_bottom = 240
	tl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud_group.add_child(tl)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 4)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tl.add_child(box)

	var eyebrow := HBoxContainer.new()
	eyebrow.add_theme_constant_override("separation", 12)
	eyebrow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(eyebrow)
	var roman: String = ["I", "II", "III", "IV"][chapter_index % 4]
	var num := ThemeKit.label(roman, 13, ThemeKit.GOLD, "latin")
	num.add_theme_constant_override("outline_size", 0)
	eyebrow.add_child(num)
	var line := ColorRect.new()
	line.color = Color(ThemeKit.GOLD, 0.5)
	line.custom_minimum_size = Vector2(30, 1)
	line.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	eyebrow.add_child(line)
	var en := ThemeKit.label(str(chapter_meta.get("en", "")).to_upper(), 12, Color(ThemeKit.PAPER_2, 0.56), "latin")
	en.add_theme_constant_override("letter_spacing", 3)
	eyebrow.add_child(en)

	_title_label = ThemeKit.label(str(chapter_meta.get("title", "")), 34, ThemeKit.PAPER, "display")
	_title_label.add_theme_color_override("font_shadow_color", Color(0.02, 0.03, 0.03, 0.8))
	_title_label.add_theme_constant_override("shadow_offset_y", 3)
	_title_label.add_theme_color_override("font_outline_color", Color(0.02, 0.03, 0.025, 0.9))
	_title_label.add_theme_constant_override("outline_size", 4)
	box.add_child(_title_label)

	var obj_row := HBoxContainer.new()
	obj_row.add_theme_constant_override("separation", 9)
	obj_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(obj_row)
	var diamond := ThemeKit.icon_rect("compass", 15, Color(ThemeKit.GOLD, 0.9))
	diamond.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	obj_row.add_child(diamond)
	_objective_label = ThemeKit.label(str(chapter_meta.get("objective", "")), 15, Color(ThemeKit.PAPER_2, 0.92))
	_objective_label.add_theme_color_override("font_outline_color", Color(0.02, 0.03, 0.025, 0.85))
	_objective_label.add_theme_constant_override("outline_size", 3)
	obj_row.add_child(_objective_label)

	# ember tally ---------------------------------------------------------------------
	var tr := MarginContainer.new()
	tr.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	tr.offset_left = -240
	tr.offset_top = 36
	tr.offset_right = -44
	tr.offset_bottom = 150
	tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud_group.add_child(tr)
	var tally := VBoxContainer.new()
	tally.alignment = BoxContainer.ALIGNMENT_END
	tally.add_theme_constant_override("separation", 6)
	tally.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tr.add_child(tally)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_END
	row.add_theme_constant_override("separation", 9)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tally.add_child(row)
	var ember_icon := ThemeKit.icon_rect("ember", 21, ThemeKit.GOLD_BRIGHT)
	ember_icon.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(ember_icon)
	_ember_text = ThemeKit.label("0 / 5", 26, ThemeKit.PAPER, "latin")
	_ember_text.add_theme_color_override("font_outline_color", Color(0.02, 0.03, 0.025, 0.85))
	_ember_text.add_theme_constant_override("outline_size", 3)
	row.add_child(_ember_text)
	var pip_row := HBoxContainer.new()
	pip_row.alignment = BoxContainer.ALIGNMENT_END
	pip_row.add_theme_constant_override("separation", 5)
	pip_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tally.add_child(pip_row)
	for i in 5:
		var pip := ThemeKit.label("◆", 9, Color(ThemeKit.PAPER_2, 0.18), "body")
		pip_row.add_child(pip)
		_pips.append(pip)

	# compass -------------------------------------------------------------------------
	_compass = Compass.new()
	_compass.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_compass.position = Vector2(-230, 34)
	_compass.custom_minimum_size = Vector2(460, 56)
	_compass.size = Vector2(460, 56)
	_compass.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud_group.add_child(_compass)
	_compass.setup(game, world)

	# pause hint ----------------------------------------------------------------------
	var esc := HBoxContainer.new()
	esc.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	esc.offset_left = -150
	esc.offset_top = 154
	esc.offset_right = -46
	esc.offset_bottom = 180
	esc.alignment = BoxContainer.ALIGNMENT_END
	esc.add_theme_constant_override("separation", 6)
	esc.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud_group.add_child(esc)
	esc.add_child(ThemeKit.keycap("esc"))
	var esc_l := ThemeKit.label("暂停", 12, Color(ThemeKit.PAPER_2, 0.46))
	esc.add_child(esc_l)

	# interaction prompt ---------------------------------------------------------------
	_prompt_panel = PanelContainer.new()
	_prompt_panel.add_theme_stylebox_override("panel", ThemeKit.stylebox(Color(0.045, 0.06, 0.055, 0.86), Color(ThemeKit.GOLD, 0.4), 1, 8, 18, 10))
	_prompt_panel.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_prompt_panel.position = Vector2(-190, -126)
	_prompt_panel.custom_minimum_size = Vector2(380, 48)
	_prompt_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_prompt_panel.modulate.a = 0.0
	_hud_group.add_child(_prompt_panel)
	var ph := HBoxContainer.new()
	ph.alignment = BoxContainer.ALIGNMENT_CENTER
	ph.add_theme_constant_override("separation", 12)
	ph.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_prompt_panel.add_child(ph)
	ph.add_child(ThemeKit.keycap("E"))
	_prompt_label = ThemeKit.label("", 15, ThemeKit.PAPER_2)
	_prompt_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	ph.add_child(_prompt_label)

	# zone name -----------------------------------------------------------------------
	var zc := CenterContainer.new()
	zc.set_anchors_preset(Control.PRESET_CENTER_TOP)
	zc.position = Vector2(0, 138)
	zc.offset_left = -400
	zc.offset_right = 400
	zc.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud_group.add_child(zc)
	_zone_panel = VBoxContainer.new()
	_zone_panel.alignment = BoxContainer.ALIGNMENT_CENTER
	_zone_panel.add_theme_constant_override("separation", 6)
	_zone_panel.modulate.a = 0.0
	zc.add_child(_zone_panel)
	_zone_label = ThemeKit.label("", 40, Color(ThemeKit.PAPER, 0.94), "display")
	_zone_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_zone_label.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.5))
	_zone_label.add_theme_constant_override("shadow_offset_y", 3)
	_zone_panel.add_child(_zone_label)
	var zline := ColorRect.new()
	zline.color = Color(ThemeKit.GOLD, 0.55)
	zline.custom_minimum_size = Vector2(46, 1)
	zline.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_zone_panel.add_child(zline)

	# toast ---------------------------------------------------------------------------
	_toast_panel = PanelContainer.new()
	_toast_panel.add_theme_stylebox_override("panel", ThemeKit.stylebox(Color(0.04, 0.055, 0.05, 0.88), Color(ThemeKit.GOLD, 0.32), 1, 6, 18, 12))
	_toast_panel.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_toast_panel.position = Vector2(-240, -214)
	_toast_panel.custom_minimum_size = Vector2(480, 54)
	_toast_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_toast_panel.modulate.a = 0.0
	_hud_group.add_child(_toast_panel)
	var th := HBoxContainer.new()
	th.add_theme_constant_override("separation", 12)
	th.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_toast_panel.add_child(th)
	_toast_icon = ThemeKit.icon_rect("ember", 22, ThemeKit.GOLD_BRIGHT)
	_toast_icon.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	th.add_child(_toast_icon)
	var tv := VBoxContainer.new()
	tv.add_theme_constant_override("separation", 1)
	tv.mouse_filter = Control.MOUSE_FILTER_IGNORE
	th.add_child(tv)
	_toast_title = ThemeKit.label("", 16, ThemeKit.PAPER)
	tv.add_child(_toast_title)
	_toast_caption = ThemeKit.label("", 12, Color(ThemeKit.PAPER_2, 0.6))
	tv.add_child(_toast_caption)

	# controls hint -------------------------------------------------------------------
	var bl := MarginContainer.new()
	bl.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	bl.offset_left = 44
	bl.offset_top = -54
	bl.offset_right = 700
	bl.offset_bottom = -30
	bl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud_group.add_child(bl)
	_hint = ThemeKit.label("W A S D 行走    Space 跳跃    Shift 奔跑    E 互动    Tab 灯册    F 观景", 13, Color(ThemeKit.PAPER_2, 0.72))
	bl.add_child(_hint)
	var hint_tw := create_tween()
	hint_tw.tween_interval(14.0)
	hint_tw.tween_property(_hint, "modulate:a", 0.0, 2.0)

	# fade ---------------------------------------------------------------------------
	_fade = ColorRect.new()
	_fade.color = Color("#0b100f")
	_fade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_fade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_fade.modulate.a = 0.0
	add_child(_fade)


func update_embers(count: int, total: int, required: int) -> void:
	_ember_text.text = "%d / %d" % [count, total]
	for i in _pips.size():
		_pips[i].modulate = Color(ThemeKit.GOLD_BRIGHT, 1.0) if i < count else Color(ThemeKit.PAPER_2, 0.16)
	if count >= required:
		_objective_label.text = "前往残灯，点亮它"
	else:
		_objective_label.text = str(chapter_meta.get("objective", ""))


func show_prompt(text: String) -> void:
	var has := text != ""
	_prompt_label.text = text
	if has:
		_prompt_panel.custom_minimum_size = Vector2(maxf(300.0, _prompt_label.get_theme_font("font").get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x + 110.0), 48)
		_prompt_panel.position.x = -_prompt_panel.custom_minimum_size.x * 0.5
	var tw := create_tween()
	tw.tween_property(_prompt_panel, "modulate:a", 1.0 if has else 0.0, 0.2)


func show_zone(title: String) -> void:
	if title == "":
		return
	_zone_label.text = title
	if _zone_tween:
		_zone_tween.kill()
	_zone_panel.modulate.a = 0.0
	_zone_tween = create_tween()
	_zone_tween.set_parallel(true)
	_zone_tween.tween_property(_zone_panel, "modulate:a", 1.0, 0.6)
	_zone_tween.tween_property(_zone_panel, "position:y", 0.0, 0.8).from(8.0).set_ease(Tween.EASE_OUT)
	_zone_tween.chain().tween_interval(2.6)
	_zone_tween.chain().tween_property(_zone_panel, "modulate:a", 0.0, 1.0)


func show_toast(title: String, subtitle: String = "", icon_name: String = "ember", duration: float = 3.2) -> void:
	_toast_title.text = title
	_toast_caption.text = subtitle
	_toast_caption.visible = subtitle != ""
	_toast_icon.texture = ThemeKit.icon(icon_name)
	if _toast_tween:
		_toast_tween.kill()
	_toast_panel.modulate.a = 0.0
	_toast_tween = create_tween()
	_toast_tween.tween_property(_toast_panel, "modulate:a", 1.0, 0.3)
	_toast_tween.tween_interval(duration)
	_toast_tween.tween_property(_toast_panel, "modulate:a", 0.0, 0.5)


func show_memory(title: String, caption: String) -> void:
	_toast_icon.texture = ThemeKit.icon("memory")
	_toast_title.text = "记忆已收录 · " + title
	_toast_caption.text = caption
	_toast_caption.visible = true
	if _toast_tween:
		_toast_tween.kill()
	_toast_panel.modulate.a = 0.0
	_toast_tween = create_tween()
	_toast_tween.tween_property(_toast_panel, "modulate:a", 1.0, 0.4)
	_toast_tween.tween_interval(4.4)
	_toast_tween.tween_property(_toast_panel, "modulate:a", 0.0, 0.7)


func FadeOut():
	pass


func fade_screen(in_out: bool, duration: float = 0.4) -> void:
	var tw := create_tween()
	tw.tween_property(_fade, "modulate:a", 1.0 if in_out else 0.0, duration)


func set_visible_hud(visible: bool, instant: bool = false) -> void:
	_hud_visible = visible
	if _hud_group:
		if _hud_tween:
			_hud_tween.kill()
		if instant:
			_hud_group.modulate.a = 1.0 if visible else 0.0
		else:
			_hud_tween = create_tween()
			_hud_tween.tween_property(_hud_group, "modulate:a", 1.0 if visible else 0.0, 0.35)
		_hud_group.mouse_filter = Control.MOUSE_FILTER_IGNORE


func is_hud_visible() -> bool:
	return _hud_visible
