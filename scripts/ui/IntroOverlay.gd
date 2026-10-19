extends Control
class_name IntroOverlay

## Chapter opening card. Sits over a paused, darkened diorama and hands the
## player back control when they step into the dream.

var game: Node
var _open := false


func setup(game_ref: Node) -> void:
	game = game_ref
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false


func open(chapter_index: int, meta: Dictionary, lines: Array) -> void:
	_open = true
	visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	if game and game.get_tree():
		game.get_tree().paused = true
	if game and game.player:
		game.player.set_controls(false)
	if game and game.hud:
		game.hud.set_visible_hud(false)
	_build(chapter_index, meta, lines)
	modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 1.0, 0.9)


func close() -> void:
	if not _open:
		return
	_open = false
	AudioDirector.ui("click")
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 0.0, 0.5)
	await tw.finished
	visible = false
	if game and game.get_tree():
		game.get_tree().paused = false
	if game and game.player:
		game.player.set_controls(true)
	if game and game.hud:
		game.hud.set_visible_hud(true)


func is_open() -> bool:
	return _open


func _unhandled_input(event: InputEvent) -> void:
	if not _open:
		return
	if event.is_action_pressed("interact") or event.is_action_pressed("ui_accept"):
		get_viewport().set_input_as_handled()
		close()


func _build(index: int, meta: Dictionary, lines: Array) -> void:
	for c in get_children():
		c.queue_free()
	var card := str(meta.get("card", ""))
	if ResourceLoader.exists(card):
		add_child(UIHelper.backdrop_art(load(card)))
	else:
		var bg := ColorRect.new()
		bg.color = Color("#101817")
		bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		add_child(bg)
	add_child(UIHelper.gradient(Color(0.015, 0.03, 0.026, 0.94), Color(0.015, 0.03, 0.026, 0.12)))
	add_child(UIHelper.vertical_shade(Color(0, 0, 0, 0.08), Color(0.01, 0.02, 0.016, 0.9)))
	var motes := MoteField.new()
	motes.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	motes.setup(60, 14, 1201 + index)
	add_child(motes)

	var numeral := ThemeKit.label(["I", "II", "III", "IV"][index % 4], 340, Color(ThemeKit.GOLD, 0.08), "latin")
	numeral.position = Vector2(1060, 180)
	add_child(numeral)

	var content := VBoxContainer.new()
	content.position = Vector2(110, 122)
	content.size = Vector2(820, 660)
	content.add_theme_constant_override("separation", 8)
	content.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(content)
	var eyebrow := ThemeKit.label("在 星 鲸 的 梦 里   ·   第 %d 梦" % (index + 1), 12, Color(ThemeKit.GOLD, 0.9), "latin")
	content.add_child(eyebrow)
	var title := ThemeKit.label(str(meta.get("title", "")), 60, ThemeKit.PAPER, "display")
	title.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.55))
	title.add_theme_constant_override("shadow_offset_y", 4)
	content.add_child(title)
	var en := ThemeKit.label(str(meta.get("en", "")).to_upper() + "   ·   " + str(meta.get("subtitle", "")), 13, Color(ThemeKit.GOLD, 0.8), "latin")
	content.add_child(en)
	content.add_child(ThemeKit.spacer(8))
	var poem := ThemeKit.label("「%s」" % str(meta.get("poem", "")), 23, Color(ThemeKit.GOLD_BRIGHT, 0.9), "display")
	content.add_child(poem)
	content.add_child(UIHelper.hline(Color(ThemeKit.GOLD, 0.4), 1))
	content.add_child(ThemeKit.spacer(10))
	var body := VBoxContainer.new()
	body.add_theme_constant_override("separation", 8)
	content.add_child(body)
	for line in lines:
		var l := ThemeKit.label(str(line), 18, Color(ThemeKit.PAPER_2, 0.82))
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.custom_minimum_size = Vector2(780, 0)
		body.add_child(l)
	content.add_child(ThemeKit.spacer(8))
	var obj := HBoxContainer.new()
	obj.add_theme_constant_override("separation", 10)
	content.add_child(obj)
	obj.add_child(ThemeKit.icon_rect("compass", 17, ThemeKit.GOLD))
	var obj_l := ThemeKit.label(str(meta.get("objective", "")), 14, Color(ThemeKit.PAPER_2, 0.62))
	obj.add_child(obj_l)
	content.add_child(ThemeKit.spacer(14))
	var enter := ThemeKit.button("踏 入 此 梦", "play", "primary", 19)
	enter.custom_minimum_size = Vector2(270, 54)
	enter.pressed.connect(close)
	content.add_child(enter)
	var hint := ThemeKit.label("Enter / E 入梦     ·     灯亮着，慢慢走", 11, Color(ThemeKit.PAPER_2, 0.35))
	content.add_child(hint)
	enter.grab_focus()
	UIHelper.fade_in_node(content, 0.15, 1.1)
