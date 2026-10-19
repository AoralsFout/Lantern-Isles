extends Button
class_name InkButton

## Custom menu button: typographic, quiet, with a growing brass rule and a small
## chevron instead of Godot's default chrome.

@export var button_kind: String = "menu"
var _rule: ColorRect
var _arrow: Label
var _hovered := false
var _tween: Tween


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	_apply_style()
	_rule = ColorRect.new()
	_rule.color = ThemeKit.GOLD
	_rule.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_rule.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	_rule.offset_left = 20
	_rule.offset_right = 20
	_rule.offset_top = -2
	_rule.offset_bottom = -1
	_rule.pivot_offset = Vector2.ZERO
	_rule.scale.x = 0.0
	add_child(_rule)

	_arrow = Label.new()
	_arrow.text = "›"
	_arrow.add_theme_font_override("font", ThemeKit.font("latin"))
	_arrow.add_theme_font_size_override("font_size", 30)
	_arrow.add_theme_color_override("font_color", ThemeKit.GOLD)
	_arrow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_arrow.modulate.a = 0.0
	add_child(_arrow)
	_arrow.set_anchors_preset(Control.PRESET_CENTER_RIGHT)
	_arrow.position = Vector2(size.x - 38, size.y * 0.5 - 21)
	resized.connect(_place_arrow)

	mouse_entered.connect(_on_hover.bind(true))
	mouse_exited.connect(_on_hover.bind(false))
	focus_entered.connect(_on_hover.bind(true))
	focus_exited.connect(_on_hover.bind(false))
	button_down.connect(_on_down)
	button_up.connect(_on_up)
	pressed.connect(_on_pressed)


func _place_arrow() -> void:
	_arrow.position = Vector2(size.x - 40, size.y * 0.5 - 22)
	_rule.offset_right = 20


func _apply_style() -> void:
	var pad_h := 22
	match button_kind:
		"primary":
			add_theme_stylebox_override("normal", ThemeKit.stylebox(Color(ThemeKit.GOLD, 0.14), Color(ThemeKit.GOLD, 0.6), 1, 5, pad_h, 12))
			add_theme_stylebox_override("hover", ThemeKit.stylebox(Color(ThemeKit.GOLD, 0.26), ThemeKit.GOLD_BRIGHT, 1, 5, pad_h, 12))
			add_theme_stylebox_override("pressed", ThemeKit.stylebox(Color(ThemeKit.GOLD, 0.34), ThemeKit.GOLD_BRIGHT, 1, 5, pad_h, 12))
			add_theme_stylebox_override("focus", ThemeKit.stylebox(Color(ThemeKit.GOLD, 0.22), ThemeKit.GOLD_BRIGHT, 1, 5, pad_h, 12))
			add_theme_color_override("font_color", ThemeKit.GOLD_BRIGHT)
			add_theme_color_override("font_hover_color", Color.WHITE)
		"chip":
			add_theme_stylebox_override("normal", ThemeKit.stylebox(Color(0.95, 0.9, 0.8, 0.06), Color(ThemeKit.GOLD, 0.24), 1, 20, 16, 7))
			add_theme_stylebox_override("hover", ThemeKit.stylebox(Color(0.95, 0.9, 0.8, 0.14), Color(ThemeKit.GOLD, 0.6), 1, 20, 16, 7))
			add_theme_stylebox_override("pressed", ThemeKit.stylebox(Color(0.95, 0.9, 0.8, 0.2), ThemeKit.GOLD, 1, 20, 16, 7))
			add_theme_stylebox_override("focus", ThemeKit.stylebox(Color(0.95, 0.9, 0.8, 0.14), Color(ThemeKit.GOLD, 0.6), 1, 20, 16, 7))
		"ghost":
			add_theme_stylebox_override("normal", ThemeKit.stylebox(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 4, 10, 6))
			add_theme_stylebox_override("hover", ThemeKit.stylebox(Color(0.95, 0.9, 0.8, 0.08), Color(0, 0, 0, 0), 0, 4, 10, 6))
			add_theme_stylebox_override("pressed", ThemeKit.stylebox(Color(0.95, 0.9, 0.8, 0.14), Color(0, 0, 0, 0), 0, 4, 10, 6))
			add_theme_stylebox_override("focus", ThemeKit.stylebox(Color(0.95, 0.9, 0.8, 0.08), Color(ThemeKit.GOLD, 0.3), 1, 4, 10, 6))
		_:
			add_theme_stylebox_override("normal", ThemeKit.stylebox(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 4, pad_h, 10))
			add_theme_stylebox_override("hover", ThemeKit.stylebox(Color(0.95, 0.9, 0.8, 0.075), Color(ThemeKit.GOLD, 0.3), 1, 4, pad_h, 10))
			add_theme_stylebox_override("pressed", ThemeKit.stylebox(Color(0.95, 0.9, 0.8, 0.14), Color(ThemeKit.GOLD, 0.55), 1, 4, pad_h, 10))
			add_theme_stylebox_override("focus", ThemeKit.stylebox(Color(0.95, 0.9, 0.8, 0.07), Color(ThemeKit.GOLD, 0.4), 1, 4, pad_h, 10))
			add_theme_color_override("font_color", ThemeKit.PAPER_2)
			add_theme_color_override("font_hover_color", ThemeKit.GOLD_BRIGHT)
			add_theme_color_override("font_focus_color", ThemeKit.GOLD_BRIGHT)


func _on_hover(on: bool) -> void:
	if _hovered == on:
		return
	_hovered = on
	if _tween:
		_tween.kill()
	_tween = create_tween().set_parallel(true)
	_tween.tween_property(_rule, "scale:x", 1.0 if on else 0.0, 0.32).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_CUBIC)
	_tween.tween_property(_arrow, "modulate:a", 1.0 if on else 0.0, 0.24)
	_tween.tween_property(self, "modulate", Color(1.03, 1.02, 1.0) if on else Color.WHITE, 0.25)
	if on:
		AudioDirector.ui("hover")


func _on_down() -> void:
	scale = Vector2(0.992, 0.992)


func _on_up() -> void:
	scale = Vector2.ONE


func _on_pressed() -> void:
	AudioDirector.ui("click")
	scale = Vector2.ONE
