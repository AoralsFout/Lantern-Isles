extends CanvasLayer

## Scene transitions with a paper-dark curtain and a little lantern sigil.

signal scene_changed

var _fade: ColorRect
var _mark: TextureRect
var _hint: Label
var _busy := false
var _overlay_root: Control = null


func _ready() -> void:
	layer = 120
	process_mode = Node.PROCESS_MODE_ALWAYS
	_overlay_root = Control.new()
	_overlay_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_overlay_root.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_overlay_root)

	_fade = ColorRect.new()
	_fade.color = Color("#0b100f")
	_fade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_overlay_root.add_child(_fade)

	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_overlay_root.add_child(center)
	var box := VBoxContainer.new()
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	box.add_theme_constant_override("separation", 14)
	center.add_child(box)
	_mark = TextureRect.new()
	_mark.texture = load("res://assets/ui/icons/lantern.svg")
	_mark.custom_minimum_size = Vector2(46, 46)
	_mark.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_mark.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_mark.modulate = Color("#d9b877")
	box.add_child(_mark)
	_hint = Label.new()
	_hint.text = "灯 还 亮 着"
	_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint.add_theme_font_size_override("font_size", 15)
	_hint.add_theme_color_override("font_color", Color("#c9b992"))
	box.add_child(_hint)
	_fade.modulate.a = 1.0
	_mark.modulate.a = 1.0


func fade_out(duration: float = 0.55) -> void:
	_overlay_root.visible = true
	_overlay_root.mouse_filter = Control.MOUSE_FILTER_STOP
	_fade.modulate.a = 0.0
	_mark.modulate.a = 0.0
	_hint.modulate.a = 0.0
	var tw := create_tween().set_parallel(true).set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	tw.tween_property(_fade, "modulate:a", 1.0, duration).set_ease(Tween.EASE_IN_OUT)
	tw.tween_property(_mark, "modulate:a", 1.0, duration * 0.8).set_delay(duration * 0.35)
	tw.tween_property(_hint, "modulate:a", 0.8, duration * 0.7).set_delay(duration * 0.45)
	await tw.finished


func fade_in(duration: float = 0.7) -> void:
	_fade.modulate.a = 1.0
	_mark.modulate.a = 1.0
	_hint.modulate.a = 0.8
	var tw := create_tween().set_parallel(true).set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	tw.tween_property(_fade, "modulate:a", 0.0, duration).set_ease(Tween.EASE_IN_OUT)
	tw.tween_property(_mark, "modulate:a", 0.0, duration * 0.45)
	tw.tween_property(_hint, "modulate:a", 0.0, duration * 0.4)
	await tw.finished
	_overlay_root.visible = false
	_overlay_root.mouse_filter = Control.MOUSE_FILTER_IGNORE


func goto_title() -> void:
	await _goto("res://scenes/TitleScreen.tscn", {})


func goto_game(index: int, from_boot: bool = false) -> void:
	GameState.begin_chapter(index)
	await _goto("res://scenes/Game.tscn", {"chapter": index, "from_boot": from_boot})


func _goto(path: String, params: Dictionary) -> void:
	if _busy:
		return
	_busy = true
	get_tree().paused = false
	await fade_out(0.55)
	var err := get_tree().change_scene_to_file(path)
	if err != OK:
		push_error("Scene change failed: " + path + " (" + str(err) + ")")
		await fade_in(0.4)
		_busy = false
		return
	await get_tree().process_frame
	await get_tree().process_frame
	var scene := get_tree().current_scene
	if scene and scene.has_method("setup_from_router"):
		scene.setup_from_router(params)
	scene_changed.emit()
	await fade_in(0.8)
	_busy = false


func is_busy() -> bool:
	return _busy
