extends Control
class_name ChapterOverlay

var game: Node
var _open := false
var _credits: CreditsScreen


func setup(game_ref: Node) -> void:
	game = game_ref
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false


func open(chapter_index: int, meta: Dictionary, embers: int, total: int, memories: int) -> void:
	_open = true
	visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	if game and game.get_tree():
		game.get_tree().paused = true
	_build(chapter_index, meta, embers, total, memories)
	modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 1.0, 0.8)


func is_open() -> bool:
	return _open


func _build(index: int, meta: Dictionary, embers: int, total: int, memories: int) -> void:
	for c in get_children():
		c.queue_free()
	var final := GameState.is_game_complete()
	AudioDirector.sfx("complete", -2.0)
	if final:
		AudioDirector.play_music("ending", 3.0)
		AudioDirector.stop_ambience(2.0)
	var art_path := "res://assets/art/ending_dawn.png" if final else str(meta.get("card", ""))
	var art := UIHelper.backdrop_art(load(art_path))
	add_child(art)
	art.pivot_offset = Vector2(800, 450)
	var drift := create_tween().set_loops()
	drift.tween_property(art, "scale", Vector2(1.04, 1.04), 26.0).set_trans(Tween.TRANS_SINE)
	drift.tween_property(art, "scale", Vector2(1.0, 1.0), 26.0).set_trans(Tween.TRANS_SINE)
	add_child(UIHelper.gradient(Color(0.018, 0.032, 0.028, 0.94), Color(0.018, 0.032, 0.028, 0.28)))
	add_child(UIHelper.vertical_shade(Color(0, 0, 0, 0.0), Color(0.012, 0.022, 0.018, 0.85)))
	var motes := MoteField.new()
	motes.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	motes.setup(80, 26, 880 + index)
	add_child(motes)

	var numeral := ThemeKit.label(["I", "II", "III", "IV"][index % 4], 360, Color(ThemeKit.GOLD, 0.075), "latin")
	numeral.position = Vector2(-32, 220)
	add_child(numeral)

	var content := VBoxContainer.new()
	content.position = Vector2(108, 112)
	content.size = Vector2(830, 680)
	content.add_theme_constant_override("separation", 10)
	content.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(content)
	var eyebrow := ThemeKit.label("第 %d 盏心灯  ·  已点亮" % (index + 1) if not final else "灯 屿 行 记  ·  终", 12, Color(ThemeKit.GOLD, 0.9), "latin")
	content.add_child(eyebrow)
	var title_text := str(meta.get("epilogue_title", "心灯")) if not final else "归航"
	var title := ThemeKit.label(title_text, 58, ThemeKit.PAPER, "display")
	title.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.55))
	title.add_theme_constant_override("shadow_offset_y", 4)
	content.add_child(title)
	var poem := ThemeKit.label("「%s」" % str(meta.get("poem", "")), 20, Color(ThemeKit.GOLD_BRIGHT, 0.88))
	content.add_child(poem)
	content.add_child(UIHelper.hline(Color(ThemeKit.GOLD, 0.45), 1))
	content.add_child(ThemeKit.spacer(8))
	var epi := str(meta.get("epilogue", ""))
	if final:
		epi += "\n\n后来，没有人再数过海上有多少盏灯。\n因为每一盏，都有人记得。"
	var body := ThemeKit.label(epi, 19, Color(ThemeKit.PAPER_2, 0.88))
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.custom_minimum_size = Vector2(780, 150)
	body.add_theme_constant_override("line_spacing", 10)
	content.add_child(body)
	content.add_child(ThemeKit.spacer(6))
	var stats := HBoxContainer.new()
	stats.add_theme_constant_override("separation", 30)
	content.add_child(stats)
	stats.add_child(UIHelper.stat_chip("ember", "%d / %d" % [embers, total], "余烬"))
	stats.add_child(UIHelper.stat_chip("memory", "%d / 2" % memories, "记忆"))
	var p := GameState.chapter_progress(index)
	stats.add_child(UIHelper.stat_chip("compass", GameState.format_time(float(p.get("time", 0.0))), "本章旅程"))
	content.add_child(ThemeKit.spacer(16))

	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 14)
	content.add_child(buttons)
	if not final:
		var b := ThemeKit.button("继续入梦", "continue", "primary", 19)
		b.custom_minimum_size = Vector2(260, 52)
		b.pressed.connect(func(): _next(index))
		buttons.add_child(b)
		var b2 := ThemeKit.button("回到主菜单", "home", "ghost", 15)
		b2.pressed.connect(_to_title)
		buttons.add_child(b2)
		b.grab_focus()
	else:
		var b := ThemeKit.button("醒 来", "play", "primary", 19)
		b.custom_minimum_size = Vector2(240, 52)
		b.pressed.connect(_to_title)
		buttons.add_child(b)
		var b3 := ThemeKit.button("制作名单", "feather", "ghost", 15)
		b3.pressed.connect(_show_credits)
		buttons.add_child(b3)
		b.grab_focus()
		var end_line := ThemeKit.label("大肥鱼，醒醒。", 13, Color(ThemeKit.GOLD, 0.7))
		content.add_child(end_line)

	# right-side illustration
	var art_path2 := "res://assets/art/ending_dawn.png" if final else _chapter_memory_art(index)
	if art_path2 != "" and ResourceLoader.exists(art_path2):
		var pic := UIHelper.framed_image(load(art_path2), Vector2(560, 360), true)
		pic.position = Vector2(970, 245)
		add_child(pic)
		var caption := ThemeKit.label("「%s」" % ("后来" if final else str(meta.get("poem", ""))), 12, Color(ThemeKit.PAPER_2, 0.55))
		caption.position = Vector2(974, 620)
		add_child(caption)
		var pic_glow := ColorRect.new()
		pic_glow.color = Color(0, 0, 0, 0)
		pic_glow.position = pic.position - Vector2(2, 2)
		pic_glow.size = pic.size + Vector2(4, 4)
		pic_glow.mouse_filter = Control.MOUSE_FILTER_IGNORE

	# credits overlay
	_credits = CreditsScreen.new()
	add_child(_credits)

	UIHelper.fade_in_node(content, 0.25, 1.2)


func _chapter_memory_art(index: int) -> String:
	var c := GameState.get_chapter(index)
	var arr: Array = c.get("memories", [])
	if arr.is_empty():
		return ""
	return str(arr[0].get("art", ""))


func _next(index: int) -> void:
	AudioDirector.ui("click")
	if game and game.get_tree():
		game.get_tree().paused = false
	visible = false
	_open = false
	SceneRouter.goto_game(index + 1)


func _to_title() -> void:
	AudioDirector.ui("back")
	if game and game.get_tree():
		game.get_tree().paused = false
	visible = false
	_open = false
	SceneRouter.goto_title()


func _show_credits() -> void:
	_credits.open()
