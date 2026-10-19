extends Control
class_name JournalScreen

var game: Node
var _open := false
var _keep_pause := false
var _on_close: Callable = Callable()
var _selected_chapter := 0
var _selected_memory := 0
var _chapter_rows: Array[Button] = []
var _memory_buttons: Array[Button] = []
var _chapter_title: Label
var _chapter_en: Label
var _chapter_poem: Label
var _objective: Label
var _art: TextureRect
var _art_veil: ColorRect
var _lock_icon: TextureRect
var _lock_text: Label
var _memory_title: Label
var _memory_caption: Label
var _memory_quote: Label
var _total_label: Label
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
	if game and game.get_tree() and not keep_pause:
		game.get_tree().paused = true
	_selected_chapter = clampi(GameState.current_chapter_index(), 0, max(0, GameState.chapter_count() - 1))
	_selected_memory = _first_unlocked_memory(_selected_chapter)
	_build()
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
	tw.tween_property(self, "modulate:a", 0.0, 0.22)
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
	if not _open:
		return
	if event.is_action_pressed("pause") or event.is_action_pressed("ui_cancel") or event.is_action_pressed("journal"):
		get_viewport().set_input_as_handled()
		close()


func _first_unlocked_memory(index: int) -> int:
	var arr: Array = GameState.all_memories_for_chapter(index)
	for i in arr.size():
		if GameState.has_memory(str(arr[i].get("id", ""))):
			return i
	return 0


func _build() -> void:
	for c in get_children():
		c.queue_free()
	_chapter_rows.clear()
	_memory_buttons.clear()
	var layer := UIHelper.overlay(true, 0.82)
	add_child(layer)
	_root = layer
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(center)
	var page := UIHelper.paper_page(Vector2(1320, 760), 44)
	center.add_child(page)
	UIHelper.add_close(self, close)

	var body: VBoxContainer = page.get_meta("body")
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 18)
	body.add_child(header)
	var titles := VBoxContainer.new()
	titles.add_theme_constant_override("separation", -2)
	header.add_child(titles)
	titles.add_child(UIHelper.ink_label("灯册", 40, ThemeKit.INK, "display"))
	var sub := HBoxContainer.new()
	sub.add_theme_constant_override("separation", 10)
	titles.add_child(sub)
	sub.add_child(UIHelper.gold_label("F I E L D   N O T E S", 10))
	sub.add_child(UIHelper.ink_label("拾 的 旅 行 记", 12, Color(ThemeKit.INK, 0.42)))
	var sp := Control.new()
	sp.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(sp)
	_total_label = UIHelper.ink_label("余烬 %d / 20    心灯 %d / 4" % [GameState.total_embers(), GameState.completed_count()], 13, Color(ThemeKit.INK, 0.55), "latin")
	_total_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	header.add_child(_total_label)
	body.add_child(UIHelper.hline(Color(ThemeKit.INK, 0.2), 1))

	var main := HBoxContainer.new()
	main.add_theme_constant_override("separation", 30)
	main.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_child(main)

	var left := VBoxContainer.new()
	left.custom_minimum_size = Vector2(330, 0)
	left.add_theme_constant_override("separation", 5)
	main.add_child(left)
	left.add_child(UIHelper.ink_label("四 段 梦", 18, ThemeKit.INK_2, "display"))
	left.add_child(ThemeKit.spacer(4))
	for i in GameState.chapter_count():
		var row := _make_chapter_row(i)
		left.add_child(row)
		_chapter_rows.append(row)
	var lsp := Control.new()
	lsp.size_flags_vertical = Control.SIZE_EXPAND_FILL
	left.add_child(lsp)
	left.add_child(UIHelper.hline(Color(ThemeKit.INK, 0.14), 1))
	left.add_child(UIHelper.ink_label("梦里拾到的光，不会熄灭。", 12, Color(ThemeKit.INK, 0.4)))
	left.add_child(UIHelper.ink_label("完整收集 20 枚余烬与 8 段记忆。", 11, Color(ThemeKit.INK, 0.32)))

	var right := VBoxContainer.new()
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right.add_theme_constant_override("separation", 6)
	main.add_child(right)
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 12)
	right.add_child(top)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", -2)
	top.add_child(col)
	_chapter_title = UIHelper.ink_label("", 30, ThemeKit.INK, "display")
	col.add_child(_chapter_title)
	_chapter_en = UIHelper.gold_label("", 11)
	col.add_child(_chapter_en)
	var top_sp := Control.new()
	top_sp.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top.add_child(top_sp)
	_chapter_poem = UIHelper.ink_label("", 13, Color(ThemeKit.INK, 0.55))
	_chapter_poem.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_chapter_poem.custom_minimum_size = Vector2(420, 0)
	top.add_child(_chapter_poem)

	_objective = UIHelper.ink_label("", 13, Color(ThemeKit.INK, 0.66))
	right.add_child(_objective)
	right.add_child(ThemeKit.spacer(2))

	var frame := Panel.new()
	frame.custom_minimum_size = Vector2(0, 352)
	frame.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	frame.add_theme_stylebox_override("panel", ThemeKit.stylebox(Color("#1b2420"), Color(ThemeKit.GOLD_DIM, 0.7), 1, 2, 0, 0))
	frame.clip_contents = true
	frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	right.add_child(frame)
	_art = TextureRect.new()
	_art.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_art.offset_left = 6
	_art.offset_top = 6
	_art.offset_right = -6
	_art.offset_bottom = -6
	_art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	_art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.add_child(_art)
	_art_veil = ColorRect.new()
	_art_veil.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_art_veil.color = Color(0.02, 0.035, 0.028, 0.72)
	_art_veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.add_child(_art_veil)
	var lock_box := CenterContainer.new()
	lock_box.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	lock_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	frame.add_child(lock_box)
	var lv := VBoxContainer.new()
	lv.alignment = BoxContainer.ALIGNMENT_CENTER
	lv.add_theme_constant_override("separation", 8)
	lv.mouse_filter = Control.MOUSE_FILTER_IGNORE
	lock_box.add_child(lv)
	_lock_icon = ThemeKit.icon_rect("lock", 26, Color(ThemeKit.PAPER_2, 0.55))
	_lock_icon.custom_minimum_size = Vector2(0, 30)
	_lock_icon.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	lv.add_child(_lock_icon)
	_lock_text = ThemeKit.label("这段记忆还在梦里", 14, Color(ThemeKit.PAPER_2, 0.6))
	_lock_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lv.add_child(_lock_text)

	var mem_row := HBoxContainer.new()
	mem_row.add_theme_constant_override("separation", 8)
	right.add_child(mem_row)
	for i in 2:
		var mb := ThemeKit.small_button("记忆", "memory", 13)
		mb.custom_minimum_size = Vector2(200, 34)
		mb.set_meta("memory_index", i)
		mb.pressed.connect(func(): _select_memory(int(mb.get_meta("memory_index"))))
		mem_row.add_child(mb)
		_memory_buttons.append(mb)
	var msp := Control.new()
	msp.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	mem_row.add_child(msp)
	var mem_note := UIHelper.ink_label("与梦中的回声交谈，可收录记忆", 11, Color(ThemeKit.INK, 0.35))
	mem_note.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	mem_row.add_child(mem_note)

	_memory_title = UIHelper.ink_label("", 19, ThemeKit.INK, "display")
	right.add_child(_memory_title)
	_memory_caption = UIHelper.ink_label("", 14, Color(ThemeKit.INK, 0.66))
	_memory_caption.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_memory_caption.custom_minimum_size = Vector2(0, 40)
	right.add_child(_memory_caption)
	_memory_quote = UIHelper.ink_label("", 13, ThemeKit.GOLD_DIM.darkened(0.22))
	_memory_quote.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.add_child(_memory_quote)

	_select_chapter(_selected_chapter)


func _make_chapter_row(index: int) -> Button:
	var c := GameState.get_chapter(index)
	var b := Button.new()
	b.text = ""
	b.custom_minimum_size = Vector2(330, 64)
	b.focus_mode = Control.FOCUS_ALL
	b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	b.add_theme_stylebox_override("normal", ThemeKit.stylebox(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 3, 10, 6))
	b.add_theme_stylebox_override("hover", ThemeKit.stylebox(Color(ThemeKit.INK, 0.06), Color(ThemeKit.INK, 0.12), 1, 3, 10, 6))
	b.add_theme_stylebox_override("pressed", ThemeKit.stylebox(Color(ThemeKit.INK, 0.1), Color(ThemeKit.GOLD_DIM, 0.4), 1, 3, 10, 6))
	b.add_theme_stylebox_override("focus", ThemeKit.stylebox(Color(ThemeKit.INK, 0.04), Color(ThemeKit.GOLD_DIM, 0.45), 1, 3, 10, 6))
	var h := HBoxContainer.new()
	h.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	h.offset_left = 10
	h.offset_right = -10
	h.add_theme_constant_override("separation", 10)
	h.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(h)
	var num := UIHelper.ink_label(["I", "II", "III", "IV"][index % 4], 12, Color(ThemeKit.GOLD_DIM, 0.9), "latin")
	num.custom_minimum_size = Vector2(24, 0)
	num.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	h.add_child(num)
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_theme_constant_override("separation", -1)
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	h.add_child(v)
	var unlocked := GameState.is_chapter_unlocked(index)
	v.add_child(UIHelper.ink_label(str(c.get("title", "")), 15, ThemeKit.INK if unlocked else Color(ThemeKit.INK, 0.35), "display"))
	v.add_child(UIHelper.gold_label(str(c.get("en", "")).to_upper(), 9))
	var state: TextureRect
	if bool(GameState.chapter_progress(index).get("completed", false)):
		state = ThemeKit.icon_rect("check", 14, ThemeKit.GOLD_DIM)
	else:
		state = ThemeKit.icon_rect("lock" if not unlocked else "compass", 13, Color(ThemeKit.INK, 0.28))
	state.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(state)
	b.pressed.connect(func(): _select_chapter(index))
	return b


func _select_chapter(index: int) -> void:
	if index < 0 or index >= GameState.chapter_count():
		return
	_selected_chapter = index
	_selected_memory = _first_unlocked_memory(index)
	_refresh()
	AudioDirector.ui("hover")


func _select_memory(index: int) -> void:
	_selected_memory = clampi(index, 0, 1)
	_refresh()
	AudioDirector.ui("hover")


func _refresh() -> void:
	var c := GameState.get_chapter(_selected_chapter)
	_chapter_title.text = str(c.get("title", ""))
	_chapter_en.text = str(c.get("en", "")).to_upper() + "   ·   " + str(c.get("subtitle", ""))
	_chapter_poem.text = "「%s」" % str(c.get("poem", ""))
	_objective.text = "心之所向 · " + str(c.get("objective", ""))
	for i in _chapter_rows.size():
		var row := _chapter_rows[i]
		if i == _selected_chapter:
			row.add_theme_stylebox_override("normal", ThemeKit.stylebox(Color(ThemeKit.INK, 0.075), Color(ThemeKit.GOLD_DIM, 0.55), 1, 3, 10, 6))
		else:
			row.add_theme_stylebox_override("normal", ThemeKit.stylebox(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 3, 10, 6))

	var memories: Array = GameState.all_memories_for_chapter(_selected_chapter)
	_selected_memory = clampi(_selected_memory, 0, max(0, memories.size() - 1))
	for i in _memory_buttons.size():
		var b := _memory_buttons[i]
		if i >= memories.size():
			b.visible = false
			continue
		b.visible = true
		var mem: Dictionary = memories[i]
		var unlocked := GameState.has_memory(str(mem.get("id", "")))
		b.text = str(mem.get("title", "记忆")) if unlocked else "记忆 · 未收录"
		b.icon = ThemeKit.icon("memory" if unlocked else "lock")
		b.add_theme_color_override("font_color", ThemeKit.INK_2 if unlocked else Color(ThemeKit.INK, 0.35))
		if i == _selected_memory:
			b.add_theme_stylebox_override("normal", ThemeKit.stylebox(Color(ThemeKit.INK, 0.08), Color(ThemeKit.GOLD_DIM, 0.55), 1, 20, 16, 7))
		else:
			b.add_theme_stylebox_override("normal", ThemeKit.stylebox(Color(0, 0, 0, 0), Color(ThemeKit.INK, 0.16), 1, 20, 16, 7))

	if memories.is_empty():
		_art.texture = load(str(c.get("card", "")))
		_art_veil.visible = true
		_lock_icon.visible = true
		_lock_text.visible = true
		_memory_title.text = "尚未收录记忆"
		_memory_caption.text = "这段梦里还没有留下回声。"
		_memory_quote.text = ""
		return
	var mem: Dictionary = memories[_selected_memory]
	var unlocked := GameState.has_memory(str(mem.get("id", "")))
	if unlocked:
		_art.texture = load(str(mem.get("art", "")))
		_art_veil.visible = false
		_lock_icon.visible = false
		_lock_text.visible = false
		_memory_title.text = "「%s」" % str(mem.get("title", ""))
		_memory_caption.text = str(mem.get("caption", ""))
		_memory_quote.text = "「%s」" % str(mem.get("quote", ""))
	else:
		_art.texture = load(str(c.get("card", "")))
		_art_veil.visible = true
		_lock_icon.visible = true
		_lock_text.visible = true
		_lock_text.text = "与梦中的回声交谈，才能收录这段记忆"
		_memory_title.text = "尚未收录的记忆"
		_memory_caption.text = "它还在某个人、某棵树、某阵风的记忆里。"
		_memory_quote.text = ""
	_total_label.text = "余烬 %d / 20    心灯 %d / 4" % [GameState.total_embers(), GameState.completed_count()]
