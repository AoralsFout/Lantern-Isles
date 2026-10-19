extends Control
class_name PauseMenu

var game: Node
var _open := false
var _panel: Control


func setup(game_ref: Node) -> void:
	game = game_ref
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false


func open() -> void:
	if _open:
		return
	_open = true
	visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	if game and game.get_tree():
		game.get_tree().paused = true
	_build()
	modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 1.0, 0.28)
	AudioDirector.ui("click")
	GameState.save()


func close() -> void:
	if not _open:
		return
	_open = false
	AudioDirector.ui("back")
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 0.0, 0.2)
	await tw.finished
	visible = false
	if game and game.get_tree():
		game.get_tree().paused = false
	GameState.save()


func is_open() -> bool:
	return _open


func _unhandled_input(event: InputEvent) -> void:
	if not _open:
		return
	if game and game.journal and game.journal.is_open():
		return
	if game and game.settings_panel and game.settings_panel.is_open():
		return
	if event.is_action_pressed("pause"):
		get_viewport().set_input_as_handled()
		close()


func _build() -> void:
	for c in get_children():
		c.queue_free()
	add_child(UIHelper.overlay(true, 0.62))
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(center)
	_panel = Panel.new()
	_panel.custom_minimum_size = Vector2(1080, 640)
	_panel.size = Vector2(1080, 640)
	_panel.add_theme_stylebox_override("panel", ThemeKit.stylebox(Color(0.035, 0.05, 0.045, 0.93), Color(ThemeKit.GOLD, 0.5), 1, 3, 0, 0))
	center.add_child(_panel)

	var idx := GameState.current_chapter_index()
	var c := GameState.get_chapter(idx)
	var p := GameState.chapter_progress(idx)

	# chapter art on the left
	var art := TextureRect.new()
	art.texture = load(str(c.get("card", "")))
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	art.position = Vector2(1, 1)
	art.size = Vector2(430, 638)
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_panel.add_child(art)
	var art_shade := UIHelper.vertical_shade(Color(0.02, 0.03, 0.026, 0.15), Color(0.02, 0.03, 0.026, 0.92))
	art_shade.set_anchors_preset(Control.PRESET_TOP_LEFT)
	art_shade.position = Vector2(1, 1)
	art_shade.size = Vector2(430, 638)
	_panel.add_child(art_shade)
	var art_info := VBoxContainer.new()
	art_info.position = Vector2(28, 470)
	art_info.size = Vector2(374, 150)
	art_info.add_theme_constant_override("separation", 3)
	art_info.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_panel.add_child(art_info)
	art_info.add_child(ThemeKit.label(["I", "II", "III", "IV"][idx % 4], 12, ThemeKit.GOLD, "latin"))
	art_info.add_child(ThemeKit.label(str(c.get("title", "")), 27, ThemeKit.PAPER, "display"))
	art_info.add_child(ThemeKit.label(str(c.get("en", "")).to_upper(), 11, Color(ThemeKit.GOLD, 0.8), "latin"))
	var art_quote := ThemeKit.label("「%s」" % str(c.get("poem", "")), 12, Color(ThemeKit.PAPER_2, 0.65))
	art_quote.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	art_info.add_child(art_quote)

	var content := Control.new()
	content.position = Vector2(476, 0)
	content.size = Vector2(604, 640)
	content.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_panel.add_child(content)
	var v := VBoxContainer.new()
	v.position = Vector2(42, 48)
	v.size = Vector2(520, 544)
	v.add_theme_constant_override("separation", 8)
	content.add_child(v)
	var eye := ThemeKit.label("A   M O M E N T   T O   B R E A T H E", 10, Color(ThemeKit.GOLD, 0.75), "latin")
	v.add_child(eye)
	v.add_child(ThemeKit.label("旅途暂歇", 42, ThemeKit.PAPER, "display"))
	var sub := ThemeKit.label("灯还亮着。你可以在这里歇一会儿。", 14, Color(ThemeKit.PAPER_2, 0.55))
	v.add_child(sub)
	v.add_child(ThemeKit.spacer(8))
	v.add_child(UIHelper.hline(Color(ThemeKit.GOLD, 0.38), 1))
	v.add_child(ThemeKit.spacer(10))

	var stats := HBoxContainer.new()
	stats.add_theme_constant_override("separation", 28)
	stats.mouse_filter = Control.MOUSE_FILTER_IGNORE
	v.add_child(stats)
	stats.add_child(ThemeKit.icon_stat("ember", "%d / %d" % [(p.get("embers", []) as Array).size(), int(c.get("total", 5))], "余烬"))
	stats.add_child(ThemeKit.icon_stat("memory", "%d / 2" % (p.get("memories", []) as Array).size(), "记忆"))
	stats.add_child(ThemeKit.icon_stat("compass", GameState.format_time(float(p.get("time", 0.0))), "本章旅程"))

	var objective := ThemeKit.label(str(c.get("objective", "")), 13, Color(ThemeKit.PAPER_2, 0.58))
	objective.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	objective.custom_minimum_size = Vector2(510, 38)
	v.add_child(objective)
	v.add_child(ThemeKit.spacer(10))

	var b_continue := ThemeKit.button("继续旅程", "continue", "primary", 19)
	b_continue.custom_minimum_size = Vector2(430, 50)
	b_continue.pressed.connect(close)
	v.add_child(b_continue)
	var b_journal := ThemeKit.button("翻开灯册", "book", "menu", 18)
	b_journal.custom_minimum_size = Vector2(430, 48)
	b_journal.pressed.connect(func():
		if game and game.journal:
			game.journal.open(true)
	)
	v.add_child(b_journal)
	var b_settings := ThemeKit.button("设置", "gear", "menu", 18)
	b_settings.custom_minimum_size = Vector2(430, 48)
	b_settings.pressed.connect(func():
		if game and game.settings_panel:
			game.settings_panel.open(true)
	)
	v.add_child(b_settings)
	var b_menu := ThemeKit.button("回到主菜单", "home", "ghost", 16)
	b_menu.custom_minimum_size = Vector2(430, 44)
	b_menu.pressed.connect(_to_title)
	v.add_child(b_menu)

	var footer := ThemeKit.label("ESC 返回旅途     ·     进度已自动保存", 11, Color(ThemeKit.PAPER_2, 0.32))
	footer.position = Vector2(476, 604)
	footer.size = Vector2(540, 22)
	_panel.add_child(footer)
	var close_btn := UIHelper.close_button(close)
	close_btn.position = Vector2(1022, 20)
	close_btn.size = Vector2(40, 40)
	_panel.add_child(close_btn)

	var total := GameState.completed_count()
	var tiny := ThemeKit.label("心灯 %d / 4    灯册 %d / 8    余烬 %d / 20" % [
		total, _memory_total(), GameState.total_embers()
	], 11, Color(ThemeKit.PAPER_2, 0.38), "latin")
	tiny.position = Vector2(476, 566)
	tiny.size = Vector2(500, 20)
	_panel.add_child(tiny)

	b_continue.grab_focus()


func _memory_total() -> int:
	var n := 0
	for i in GameState.chapter_count():
		n += (GameState.chapter_progress(i).get("memories", []) as Array).size()
	return n


func _to_title() -> void:
	GameState.save()
	if game and game.get_tree():
		game.get_tree().paused = false
	visible = false
	_open = false
	SceneRouter.goto_title()
