extends Control

## Main menu. A quiet, storybook theatre: generated key art, drifting motes,
## hand-set type, custom buttons, and a living chapter select.

var chapter_select: ChapterSelect
var journal: JournalScreen
var settings: SettingsPanel
var credits: CreditsScreen
var prologue: Control

var _bg: TextureRect
var _menu: VBoxContainer
var _primary: Button
var _progress_line: Label
var _sound_button: Button
var _shot_mode := false
var _prologue_page := 0
var _prologue_body: VBoxContainer
var _prologue_continue: Button
var _prologue_overlay: Control
var _title_left: Control
var _top_right: HBoxContainer


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	theme = ThemeKit.make_theme()
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_shot_mode = "--screenshot" in OS.get_cmdline_user_args()
	_build()
	AudioDirector.play_music("title", 2.8)
	AudioDirector.play_ambience("spring_amb", 2.0)
	if _shot_mode:
		_run_shot()


func setup_from_router(_params: Dictionary) -> void:
	# Title screen is also reachable mid-session; refresh the resume line.
	_refresh_progress_label()


func _build() -> void:
	_bg = UIHelper.backdrop_art(load("res://assets/art/keyart_title.png") if ResourceLoader.exists("res://assets/art/keyart_title.png") else null)
	add_child(_bg)
	_bg.modulate = Color(1.02, 0.99, 0.94)
	_bg.pivot_offset = Vector2(800, 450)
	var drift := create_tween().set_loops()
	drift.tween_property(_bg, "scale", Vector2(1.045, 1.045), 32.0).set_trans(Tween.TRANS_SINE)
	drift.tween_property(_bg, "scale", Vector2(1.0, 1.0), 32.0).set_trans(Tween.TRANS_SINE)

	add_child(UIHelper.gradient(Color(0.025, 0.04, 0.035, 0.96), Color(0.025, 0.04, 0.035, 0.0)))
	add_child(UIHelper.vertical_shade(Color(0.0, 0.0, 0.0, 0.08), Color(0.015, 0.025, 0.02, 0.82)))
	var motes := MoteField.new()
	motes.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	motes.setup(70, 22, 311)
	add_child(motes)

	var left := Control.new()
	_title_left = left
	left.set_anchors_preset(Control.PRESET_TOP_LEFT)
	left.offset_left = 82
	left.offset_top = 58
	left.offset_right = 690
	left.offset_bottom = 860
	left.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(left)

	var col := VBoxContainer.new()
	col.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)
	col.offset_right = 590
	col.add_theme_constant_override("separation", 3)
	left.add_child(col)

	var eyebrow := HBoxContainer.new()
	eyebrow.add_theme_constant_override("separation", 12)
	eyebrow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.add_child(eyebrow)
	var line := ColorRect.new()
	line.color = Color(ThemeKit.GOLD, 0.7)
	line.custom_minimum_size = Vector2(34, 1)
	line.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	eyebrow.add_child(line)
	var eye := ThemeKit.label("A  S T O R Y  I N  F O U R  D R E A M S", 11, Color(ThemeKit.GOLD, 0.9), "latin")
	eyebrow.add_child(eye)

	var title_row := HBoxContainer.new()
	title_row.add_theme_constant_override("separation", 18)
	title_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.add_child(title_row)
	var title := ThemeKit.label("灯屿行记", 88, Color("#f5ecd8"), "display")
	title.add_theme_color_override("font_shadow_color", Color(0.0, 0.0, 0.0, 0.55))
	title.add_theme_constant_override("shadow_offset_x", 2)
	title.add_theme_constant_override("shadow_offset_y", 5)
	title_row.add_child(title)
	var seal := TextureRect.new()
	seal.texture = ThemeKit.icon("seal")
	seal.custom_minimum_size = Vector2(58, 58)
	seal.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	seal.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	seal.modulate = Color(1.0, 0.85, 0.8, 0.9)
	seal.pivot_offset = Vector2(29, 29)
	seal.rotation_degrees = 4
	seal.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	title_row.add_child(seal)

	var en := ThemeKit.label("L A N T E R N   I S L E S", 17, Color(ThemeKit.GOLD_BRIGHT, 0.82), "latin")
	en.add_theme_constant_override("letter_spacing", 4)
	col.add_child(en)
	col.add_child(ThemeKit.spacer(8))
	var quote := ThemeKit.label("在星鲸的梦里，\n替世界点一盏灯。", 18, Color(ThemeKit.PAPER_2, 0.78))
	quote.add_theme_constant_override("line_spacing", 6)
	col.add_child(quote)
	col.add_child(ThemeKit.spacer(14))
	col.add_child(UIHelper.hline(Color(ThemeKit.GOLD, 0.28), 1))
	_progress_line = ThemeKit.label("", 12, Color(ThemeKit.PAPER_2, 0.42))
	col.add_child(_progress_line)
	_refresh_progress_label()
	col.add_child(ThemeKit.spacer(12))

	_menu = VBoxContainer.new()
	_menu.add_theme_constant_override("separation", 0)
	col.add_child(_menu)
	_build_menu()

	# below-left footer
	var footer := ThemeKit.label("v1.0   ·   原创音乐 · 建议佩戴耳机", 11, Color(ThemeKit.PAPER_2, 0.34))
	footer.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	footer.position = Vector2(84, -40)
	add_child(footer)
	var credit_hint := ThemeKit.label("神鲸背负四梦 · 2026", 11, Color(ThemeKit.PAPER_2, 0.24), "latin")
	credit_hint.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	credit_hint.position = Vector2(-270, -40)
	add_child(credit_hint)

	# top-right sound / fullscreen
	var top_right := HBoxContainer.new()
	_top_right = top_right
	top_right.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	top_right.offset_left = -130
	top_right.offset_top = 36
	top_right.offset_right = -42
	top_right.offset_bottom = 80
	top_right.alignment = BoxContainer.ALIGNMENT_END
	top_right.add_theme_constant_override("separation", 8)
	add_child(top_right)
	_sound_button = _icon_button("sound", "声音", _toggle_sound)
	top_right.add_child(_sound_button)
	top_right.add_child(_icon_button("fullscreen", "全屏", _toggle_fullscreen))

	chapter_select = ChapterSelect.new()
	add_child(chapter_select)
	chapter_select.chosen.connect(_on_chapter_chosen)
	chapter_select.visibility_changed.connect(_sync_title_chrome)

	# entrance animation
	if _menu.get_child_count() > 0:
		for i in _menu.get_child_count():
			var child := _menu.get_child(i) as CanvasItem
			UIHelper.reveal(child, 0.18 + i * 0.055)
		_menu.get_child(0).grab_focus()


func _build_menu() -> void:
	var has := GameState.has_progress()
	var finished := GameState.is_game_complete()
	var primary_text := "开始旅程" if not has else ("重温梦境" if finished else "继续旅程")
	var primary_icon := "play" if not has else ("chapters" if finished else "continue")
	_primary = _menu_button(primary_text, primary_icon, "primary")
	_primary.pressed.connect(_on_primary)
	_menu.add_child(_primary)
	var ch := _menu_button("章节选择", "chapters")
	ch.pressed.connect(_open_chapters)
	_menu.add_child(ch)
	var jr := _menu_button("灯册", "book")
	jr.pressed.connect(_open_journal)
	_menu.add_child(jr)
	var st := _menu_button("设置", "gear")
	st.pressed.connect(_open_settings)
	_menu.add_child(st)
	var cr := _menu_button("制作名单", "feather")
	cr.pressed.connect(_open_credits)
	_menu.add_child(cr)
	var qt := _menu_button("离开", "exit")
	qt.pressed.connect(_quit)
	_menu.add_child(qt)


func _menu_button(text: String, icon_name: String, kind: String = "menu") -> Button:
	var b := ThemeKit.button(text, icon_name, kind, 21)
	b.custom_minimum_size = Vector2(370, 48)
	b.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	return b


func _icon_button(icon_name: String, tip: String, cb: Callable) -> Button:
	var b := Button.new()
	b.icon = ThemeKit.icon(icon_name)
	b.custom_minimum_size = Vector2(40, 40)
	b.tooltip_text = tip
	b.focus_mode = Control.FOCUS_ALL
	b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	b.add_theme_stylebox_override("normal", ThemeKit.stylebox(Color(0, 0, 0, 0), Color(ThemeKit.PAPER_2, 0.18), 1, 20, 0, 0))
	b.add_theme_stylebox_override("hover", ThemeKit.stylebox(Color(ThemeKit.PAPER, 0.1), Color(ThemeKit.GOLD, 0.6), 1, 20, 0, 0))
	b.add_theme_stylebox_override("pressed", ThemeKit.stylebox(Color(ThemeKit.PAPER, 0.16), ThemeKit.GOLD, 1, 20, 0, 0))
	b.add_theme_stylebox_override("focus", ThemeKit.stylebox(Color(0, 0, 0, 0), Color(ThemeKit.GOLD, 0.6), 1, 20, 0, 0))
	b.pressed.connect(cb)
	return b


func _refresh_progress_label() -> void:
	if _progress_line == null:
		return
	if not GameState.has_progress():
		_progress_line.text = "一段还没有开始的梦"
		return
	var idx := GameState.current_chapter_index()
	var c := GameState.get_chapter(idx)
	var done := GameState.completed_count()
	_progress_line.text = "上次停在 · %s    余烬 %d/20   心灯 %d/4" % [
		str(c.get("title", "")), GameState.total_embers(), done
	]


func _on_primary() -> void:
	if not GameState.has_progress():
		_open_prologue()
		return
	if GameState.is_game_complete():
		_open_chapters()
		return
	AudioDirector.ui("click")
	SceneRouter.goto_game(GameState.current_chapter_index())


func _on_chapter_chosen(index: int) -> void:
	await chapter_select.close()
	SceneRouter.goto_game(index)


func _open_chapters() -> void:
	AudioDirector.ui("click")
	chapter_select.open()
	_sync_title_chrome()


func _open_journal() -> void:
	AudioDirector.ui("click")
	if journal == null:
		journal = JournalScreen.new()
		add_child(journal)
		journal.setup(null)
		journal.visibility_changed.connect(_sync_title_chrome)
	journal.open()
	_sync_title_chrome()


func _open_settings() -> void:
	AudioDirector.ui("click")
	if settings == null:
		settings = SettingsPanel.new()
		add_child(settings)
		settings.setup(null)
		settings.visibility_changed.connect(_sync_title_chrome)
	settings.open()
	_sync_title_chrome()


func _open_credits() -> void:
	AudioDirector.ui("click")
	if credits == null:
		credits = CreditsScreen.new()
		add_child(credits)
		credits.visibility_changed.connect(_sync_title_chrome)
	credits.open()
	_sync_title_chrome()


func _toggle_sound() -> void:
	var muted := float(GameState.get_setting("master", 0.9)) <= 0.01
	GameState.set_setting("master", 0.9 if muted else 0.0)
	AudioDirector.apply_settings()
	_sound_button.icon = ThemeKit.icon("sound" if muted else "mute")
	AudioDirector.ui("click")


func _toggle_fullscreen() -> void:
	GameState.set_setting("fullscreen", not bool(GameState.get_setting("fullscreen", false)))
	AudioDirector.ui("click")


func _quit() -> void:
	AudioDirector.ui("back")
	GameState.save()
	get_tree().quit()


# ---------------------------------------------------------------- prologue ---
func _open_prologue() -> void:
	AudioDirector.ui("click")
	if prologue != null and is_instance_valid(prologue):
		prologue.queue_free()
	prologue = Control.new()
	prologue.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	prologue.mouse_filter = Control.MOUSE_FILTER_STOP
	prologue.process_mode = Node.PROCESS_MODE_ALWAYS
	add_child(prologue)
	var art := UIHelper.backdrop_art(load("res://assets/art/keyart_title.png"))
	art.modulate = Color(0.55, 0.6, 0.58)
	prologue.add_child(art)
	prologue.add_child(UIHelper.gradient(Color(0.02, 0.035, 0.03, 0.96), Color(0.02, 0.035, 0.03, 0.55)))
	var motes := MoteField.new()
	motes.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	motes.setup(50, 12, 507)
	prologue.add_child(motes)
	var panel := Control.new()
	panel.set_anchors_preset(Control.PRESET_TOP_LEFT)
	panel.offset_left = 120
	panel.offset_top = 90
	panel.offset_right = 900
	panel.offset_bottom = 810
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	prologue.add_child(panel)
	_prologue_body = VBoxContainer.new()
	_prologue_body.add_theme_constant_override("separation", 16)
	_prologue_body.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)
	_prologue_body.offset_right = 760
	panel.add_child(_prologue_body)
	var eyebrow := ThemeKit.label("P R O L O G U E   ·   序", 12, Color(ThemeKit.GOLD, 0.85), "latin")
	_prologue_body.add_child(eyebrow)
	var rule := ThemeKit.color_rect(Color(ThemeKit.GOLD, 0.4), Vector2(90, 1))
	_prologue_body.add_child(rule)
	var title := ThemeKit.label("", 50, ThemeKit.PAPER, "display")
	title.name = "PageTitle"
	_prologue_body.add_child(title)
	var text := ThemeKit.label("", 19, Color(ThemeKit.PAPER_2, 0.8))
	text.name = "PageText"
	text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text.custom_minimum_size = Vector2(720, 0)
	text.add_theme_constant_override("line_spacing", 10)
	_prologue_body.add_child(text)
	_prologue_body.add_child(ThemeKit.spacer(16))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	_prologue_body.add_child(row)
	_prologue_continue = ThemeKit.button("继续", "arrow", "primary", 18)
	_prologue_continue.custom_minimum_size = Vector2(220, 50)
	_prologue_continue.pressed.connect(_prologue_next)
	row.add_child(_prologue_continue)
	var skip := ThemeKit.button("跳过序章", "", "ghost", 14)
	skip.pressed.connect(_prologue_finish)
	row.add_child(skip)
	var mark := ThemeKit.label("拾", 150, Color(ThemeKit.GOLD, 0.13), "display")
	mark.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	mark.offset_left = -300
	mark.offset_top = -250
	prologue.add_child(mark)
	_prologue_page = 0
	_sync_title_chrome()
	_show_prologue_page()
	UIHelper.fade_in_node(_prologue_body, 0.1, 0.8)


func _show_prologue_page() -> void:
	var pages := [
		["世界，在一头鲸的梦里。", "世界并不在海上。\n它在一头名叫「大肥鱼」的星鲸的梦里。\n每一盏人间灯火，都会在它的背上浮起一座小小的箱庭。"],
		["后来，灯一盏盏灭了。", "守灯人离开了。四座箱庭的灯火也一盏盏熄灭，\n星鲸沉沉睡去，梦里只剩下风。"],
		["你醒了。", "你是一只刚醒来的小灯灵，叫「拾」。\n怀里抱着一盏只剩最后一粒火种的纸灯。\n去走进它的四段梦，把光找回来。"],
	]
	var page: Array = pages[_prologue_page]
	var t := _prologue_body.get_node("PageTitle") as Label
	var b := _prologue_body.get_node("PageText") as Label
	t.text = str(page[0])
	b.text = str(page[1])
	_prologue_continue.text = "醒来" if _prologue_page >= pages.size() - 1 else "继续"
	AudioDirector.ui("hover")
	var tw := create_tween()
	t.modulate.a = 0.0
	b.modulate.a = 0.0
	tw.tween_property(t, "modulate:a", 1.0, 0.35)
	tw.parallel().tween_property(b, "modulate:a", 1.0, 0.45)
	_prologue_continue.grab_focus()


func _prologue_next() -> void:
	if _prologue_page >= 2:
		_prologue_finish()
		return
	_prologue_page += 1
	_show_prologue_page()


func _prologue_finish() -> void:
	AudioDirector.ui("click")
	GameState.new_game()
	SceneRouter.goto_game(0)


func _unhandled_input(event: InputEvent) -> void:
	if prologue != null and is_instance_valid(prologue) and event.is_action_pressed("ui_accept"):
		_prologue_next()
		get_viewport().set_input_as_handled()


func _sync_title_chrome() -> void:
	var any := chapter_select != null and chapter_select.visible
	if journal != null and is_instance_valid(journal) and journal.visible:
		any = true
	if settings != null and is_instance_valid(settings) and settings.visible:
		any = true
	if credits != null and is_instance_valid(credits) and credits.visible:
		any = true
	if prologue != null and is_instance_valid(prologue):
		any = true
	for c in [_title_left, _top_right]:
		if c == null or not is_instance_valid(c):
			continue
		var tw := create_tween()
		tw.tween_property(c, "modulate:a", 0.0 if any else 1.0, 0.25)


# -------------------------------------------------------------------- shot ---
func _run_shot() -> void:
	var args := OS.get_cmdline_user_args()
	var shot := "ui_title"
	for a in args:
		if a.begins_with("--shot="):
			shot = a.split("=")[1]
	if "--chapter-select" in args:
		await get_tree().create_timer(0.8).timeout
		_open_chapters()
	elif "--credits" in args:
		await get_tree().create_timer(0.8).timeout
		_open_credits()
	elif "--prologue" in args:
		await get_tree().create_timer(0.8).timeout
		_open_prologue()
	await get_tree().create_timer(3.2).timeout
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var dir := ProjectSettings.globalize_path("res://screenshots")
	DirAccess.make_dir_recursive_absolute(dir)
	var path := dir.path_join(shot + ".png")
	img.save_png(path)
	print("UI_SCREENSHOT ", path)
	get_tree().quit()
