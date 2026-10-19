extends Control
class_name SettingsPanel

var game: Node
var _open := false
var _keep_pause := false
var _on_close: Callable = Callable()
var _page: Control
var _sliders: Dictionary = {}
var _toggles: Dictionary = {}
var _root: Control


func setup(game_ref: Node) -> void:
	game = game_ref
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false


func open(keep_pause: bool = false, on_close: Callable = Callable()) -> void:
	if _open:
		return
	_open = true
	_keep_pause = keep_pause
	_on_close = on_close
	visible = true
	_build()
	if game and game.get_tree() and not keep_pause:
		game.get_tree().paused = true
	modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 1.0, 0.3)
	AudioDirector.ui("click")


func close() -> void:
	if not _open:
		return
	_open = false
	AudioDirector.ui("back")
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 0.0, 0.2)
	await tw.finished
	visible = false
	if game and game.get_tree() and not _keep_pause:
		game.get_tree().paused = false
	if _on_close.is_valid():
		var cb := _on_close
		_on_close = Callable()
		cb.call()


func is_open() -> bool:
	return _open


func _unhandled_input(event: InputEvent) -> void:
	if _open and (event.is_action_pressed("pause") or event.is_action_pressed("ui_cancel")):
		get_viewport().set_input_as_handled()
		close()


func _build() -> void:
	for c in get_children():
		c.queue_free()
	_sliders.clear()
	_toggles.clear()
	var layer := UIHelper.overlay(true, 0.82)
	add_child(layer)
	_root = layer
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(center)
	var page := UIHelper.paper_page(Vector2(1000, 720), 48)
	center.add_child(page)
	_page = page
	UIHelper.add_close(self, close)

	var body: VBoxContainer = page.get_meta("body")
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 16)
	body.add_child(header)
	var titles := VBoxContainer.new()
	titles.add_theme_constant_override("separation", -2)
	header.add_child(titles)
	titles.add_child(UIHelper.ink_label("设置", 40, ThemeKit.INK, "display"))
	titles.add_child(UIHelper.gold_label("S E T T I N G S", 11))
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(spacer)
	var hint := UIHelper.ink_label("改动会自动保存", 12, Color(ThemeKit.INK, 0.42))
	hint.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	header.add_child(hint)
	body.add_child(UIHelper.hline(Color(ThemeKit.INK, 0.2), 1))

	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.add_theme_stylebox_override("panel", ThemeKit.stylebox(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 0, 0, 0))
	body.add_child(scroll)
	var content := VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 12)
	scroll.add_child(content)

	_section(content, "声音", "将灯提近一点，听见风声和鲸鸣。")
	var audio := GridContainer.new()
	audio.columns = 2
	audio.add_theme_constant_override("h_separation", 32)
	audio.add_theme_constant_override("v_separation", 6)
	content.add_child(audio)
	for spec in [
		["master", "总音量", 0.9],
		["music", "音乐", 0.72],
		["sfx", "音效", 0.82],
		["ambience", "环境声", 0.66],
	]:
		var s := InkSlider.new()
		var key := str(spec[0])
		var initial := float(GameState.get_setting(key, spec[2]))
		s.setup(str(spec[1]), 0.0, 1.0, 0.01, initial, "%")
		s.on_paper = true
		s.value_changed.connect(func(v: float):
			GameState.set_setting(key, v)
			AudioDirector.apply_settings()
		)
		audio.add_child(s)
		_sliders[key] = s

	content.add_child(ThemeKit.spacer(8))
	_section(content, "画面与镜头", "让镜头和粒子更温柔一点。")
	var visual := VBoxContainer.new()
	visual.add_theme_constant_override("separation", 2)
	content.add_child(visual)
	for spec in [
		["fullscreen", "全屏显示", false],
		["camera_shake", "镜头轻震", true],
		["reduced_motion", "柔化动态", false],
	]:
		var key := str(spec[0])
		var tg := InkToggle.new()
		tg.setup(str(spec[1]), bool(GameState.get_setting(key, spec[2])))
		tg.on_paper = true
		tg.toggled.connect(func(v: bool): GameState.set_setting(key, v))
		visual.add_child(tg)
		_toggles[key] = tg

	content.add_child(ThemeKit.spacer(8))
	_section(content, "操作", "一张可以夹在灯册里的字条。")
	var keys := GridContainer.new()
	keys.columns = 2
	keys.add_theme_constant_override("h_separation", 40)
	keys.add_theme_constant_override("v_separation", 8)
	content.add_child(keys)
	for spec in [
		["W A S D", "行走 / 奔跑"], ["Shift", "奔跑"],
		["Space", "跳跃"], ["E", "互动 / 继续"],
		["Tab", "打开灯册"], ["Esc", "暂停"],
		["Q R", "旋转镜头"], ["滚轮", "拉近 / 推远"],
		["F", "观景模式"], ["F12", "截图"],
	]:
		keys.add_child(_ink_key(str(spec[0]), str(spec[1])))

	content.add_child(ThemeKit.spacer(6))
	body.add_child(UIHelper.hline(Color(ThemeKit.INK, 0.16), 1))
	var footer := HBoxContainer.new()
	footer.add_theme_constant_override("separation", 12)
	body.add_child(footer)
	var reset := ThemeKit.button("恢复默认", "", "chip", 14)
	reset.custom_minimum_size = Vector2(140, 42)
	reset.add_theme_color_override("font_color", ThemeKit.INK_3)
	reset.add_theme_color_override("font_hover_color", ThemeKit.INK)
	reset.add_theme_stylebox_override("normal", ThemeKit.stylebox(Color(ThemeKit.INK, 0.06), Color(ThemeKit.INK, 0.2), 1, 18, 18, 6))
	reset.add_theme_stylebox_override("hover", ThemeKit.stylebox(Color(ThemeKit.INK, 0.1), Color(ThemeKit.INK, 0.35), 1, 18, 18, 6))
	reset.pressed.connect(_reset_defaults)
	footer.add_child(reset)
	var sp := Control.new()
	sp.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	footer.add_child(sp)
	var done := ThemeKit.button("完成", "check", "chip", 15)
	done.custom_minimum_size = Vector2(140, 42)
	done.add_theme_color_override("font_color", ThemeKit.INK)
	done.add_theme_color_override("font_hover_color", ThemeKit.INK)
	done.add_theme_color_override("font_focus_color", ThemeKit.INK)
	done.pressed.connect(close)
	footer.add_child(done)


func _section(parent: VBoxContainer, title: String, subtitle: String) -> void:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 12)
	parent.add_child(h)
	h.add_child(UIHelper.ink_label(title, 21, ThemeKit.INK, "display"))
	var s := UIHelper.ink_label(subtitle, 12, Color(ThemeKit.INK, 0.48))
	s.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	h.add_child(s)


func _ink_key(keys: String, desc: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var key := PanelContainer.new()
	key.add_theme_stylebox_override("panel", ThemeKit.stylebox(Color(ThemeKit.INK, 0.07), Color(ThemeKit.INK, 0.24), 1, 3, 9, 3))
	key.custom_minimum_size = Vector2(64, 0)
	var kl := UIHelper.ink_label(keys, 11, ThemeKit.INK_2, "latin")
	kl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	key.add_child(kl)
	row.add_child(key)
	var l := UIHelper.ink_label(desc, 13, Color(ThemeKit.INK, 0.68))
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	row.add_child(l)
	return row


func _reset_defaults() -> void:
	for key in GameState.DEFAULT_SETTINGS:
		GameState.set_setting(key, GameState.DEFAULT_SETTINGS[key])
	for key in _sliders:
		var s: InkSlider = _sliders[key]
		s.set_value(float(GameState.get_setting(key, 0.7)), true)
	for key in _toggles:
		var t: InkToggle = _toggles[key]
		t.set_value(bool(GameState.get_setting(key, false)), true)
	AudioDirector.apply_settings()
