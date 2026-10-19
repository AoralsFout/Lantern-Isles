extends Control
class_name CreditsScreen

var _open := false
var _content: VBoxContainer


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false


func open() -> void:
	_open = true
	visible = true
	for c in get_children():
		c.queue_free()
	_build()
	modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 1.0, 0.4)


func close() -> void:
	if not _open:
		return
	_open = false
	AudioDirector.ui("back")
	var tw := create_tween()
	tw.tween_property(self, "modulate:a", 0.0, 0.22)
	await tw.finished
	visible = false


func is_open() -> bool:
	return _open


func _unhandled_input(event: InputEvent) -> void:
	if _open and (event.is_action_pressed("pause") or event.is_action_pressed("ui_cancel")):
		get_viewport().set_input_as_handled()
		close()


func _build() -> void:
	add_child(UIHelper.overlay(true, 0.86))
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(center)
	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(900, 650)
	box.add_theme_constant_override("separation", 12)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	center.add_child(box)

	var eyebrow := ThemeKit.label("C R E D I T S", 12, Color(ThemeKit.GOLD, 0.8), "latin")
	eyebrow.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(eyebrow)
	var title := ThemeKit.label("制作名单", 52, ThemeKit.PAPER, "display")
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(title)
	box.add_child(UIHelper.hline(Color(ThemeKit.GOLD, 0.35), 1))
	box.add_child(ThemeKit.spacer(14))

	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(900, 430)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.add_theme_stylebox_override("panel", ThemeKit.stylebox(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 0, 0, 0))
	box.add_child(scroll)
	_content = VBoxContainer.new()
	_content.custom_minimum_size = Vector2(820, 0)
	_content.add_theme_constant_override("separation", 18)
	_content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_content)

	_add_section("《灯屿行记》", "Lantern Isles · 一场箱庭的梦", true)
	_add_line("在星鲸的梦里，替世界点一盏灯。", Color(ThemeKit.PAPER_2, 0.7), 17)
	_add_gap()
	_add_credit("创意 · 世界 · 故事", "大肥鱼的一场梦")
	_add_credit("设计 · 程序 · 关卡 · 场景组装", "DeepSeek Harness 肌肉团队")
	_add_credit("3D 低模资产", "Blender 模型小队（花木 / 岩石 / 建筑 / 遗物）")
	_add_credit("章节插画 · 主视觉", "图像生成模型 gpt-image-2.5")
	_add_credit("原创音乐 · 环境声 · 音效", "算法合成声景（numpy / ffmpeg）")
	_add_credit("引擎", "Godot 4.7.2 · Forward+")
	_add_credit("建模", "Blender 4.2.9 LTS")
	_add_credit("特别感谢", "大肥鱼、所有还在提灯的人")
	_add_gap()
	_add_line("「后来，没有人再数过海上有多少盏灯。\n因为每一盏，都有人记得。」", Color(ThemeKit.GOLD_BRIGHT, 0.9), 17)
	_add_line("2026 · 星鲸背上的第四版梦", Color(ThemeKit.PAPER_2, 0.35), 13)
	_add_gap()

	var hint := ThemeKit.label("滚轮翻阅 · Esc 返回", 12, Color(ThemeKit.PAPER_2, 0.35), "body")
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(hint)
	var back_btn := ThemeKit.button("回到梦边", "arrow", "chip", 16)
	back_btn.custom_minimum_size = Vector2(220, 42)
	back_btn.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	back_btn.pressed.connect(close)
	box.add_child(back_btn)
	UIHelper.add_close(self, close)

	# slow, optional drift to make the wall of words feel alive
	scroll.scroll_vertical = 0
	var tw := create_tween()
	tw.tween_interval(2.0)
	tw.tween_property(scroll, "scroll_vertical", 260, 18.0).set_trans(Tween.TRANS_SINE)
	tw.set_loops()


func _add_section(title: String, sub: String, big: bool = false) -> void:
	var t := ThemeKit.label(title, 34 if big else 24, ThemeKit.PAPER, "display")
	_content.add_child(t)
	var s := ThemeKit.label(sub, 13, Color(ThemeKit.PAPER_2, 0.7), "body")
	_content.add_child(s)


func _add_credit(role: String, name: String) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 18)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var l := ThemeKit.label(role, 14, Color(ThemeKit.PAPER_2, 0.7))
	l.custom_minimum_size = Vector2(320, 0)
	row.add_child(l)
	var r := ThemeKit.label(name, 16, ThemeKit.PAPER_2)
	row.add_child(r)
	_content.add_child(row)


func _add_line(text: String, color: Color, px: int) -> void:
	var l := ThemeKit.label(text, px, color)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.custom_minimum_size = Vector2(820, 0)
	_content.add_child(l)


func _add_gap() -> void:
	_content.add_child(ThemeKit.spacer(6))
