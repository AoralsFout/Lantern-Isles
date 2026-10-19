class_name UIHelper
extends RefCounted

## Shared building blocks for the game's screens. These are hand-built from
## Controls and StyleBoxes so no default Godot chrome leaks through.

static var _paper_tex: Texture2D = null


static func paper_texture() -> Texture2D:
	if _paper_tex == null and ResourceLoader.exists("res://assets/art/paper_texture.png"):
		_paper_tex = load("res://assets/art/paper_texture.png")
	return _paper_tex


static func overlay(blur: bool = true, darken: float = 0.55) -> Control:
	var root := Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_STOP
	root.process_mode = Node.PROCESS_MODE_ALWAYS
	if blur:
		var backdrop := ColorRect.new()
		backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var mat := ShaderMaterial.new()
		mat.shader = load("res://shaders/backdrop_blur.gdshader")
		mat.set_shader_parameter("darken", darken)
		backdrop.material = mat
		root.add_child(backdrop)
	else:
		var veil := ColorRect.new()
		veil.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		veil.color = Color(0.03, 0.045, 0.04, darken)
		veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
		root.add_child(veil)
	return root


static func paper_page(min_size: Vector2, pad: int = 46, dark: bool = false) -> Control:
	var root := Control.new()
	root.custom_minimum_size = min_size
	root.size = min_size
	root.mouse_filter = Control.MOUSE_FILTER_STOP
	root.clip_contents = false

	var shadow := Panel.new()
	shadow.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shadow.offset_left = 8
	shadow.offset_top = 10
	shadow.offset_right = 8
	shadow.offset_bottom = 10
	shadow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	shadow.add_theme_stylebox_override("panel", ThemeKit.stylebox(Color(0, 0, 0, 0.35), Color(0, 0, 0, 0), 0, 4, 0, 0))
	root.add_child(shadow)

	var bg := Panel.new()
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var bg_color := Color("#121917") if dark else ThemeKit.PAPER
	var border := Color(ThemeKit.GOLD, 0.55) if dark else Color(ThemeKit.GOLD_DIM, 0.8)
	bg.add_theme_stylebox_override("panel", ThemeKit.stylebox(bg_color, border, 1, 3, 0, 0))
	root.add_child(bg)

	if not dark:
		var tex := TextureRect.new()
		tex.texture = paper_texture()
		tex.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		tex.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tex.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		tex.modulate = Color(1, 0.98, 0.92, 0.5)
		tex.mouse_filter = Control.MOUSE_FILTER_IGNORE
		root.add_child(tex)
		var wash := ColorRect.new()
		wash.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		wash.color = Color(0.96, 0.91, 0.81, 0.16)
		wash.mouse_filter = Control.MOUSE_FILTER_IGNORE
		root.add_child(wash)

	# fine double rule near the edge
	var rule := Panel.new()
	rule.position = Vector2(18, 18)
	rule.size = min_size - Vector2(36, 36)
	rule.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var rule_color := Color(ThemeKit.GOLD, 0.22) if dark else Color(ThemeKit.INK, 0.18)
	rule.add_theme_stylebox_override("panel", ThemeKit.stylebox(Color(0, 0, 0, 0), rule_color, 1, 1, 0, 0))
	root.add_child(rule)

	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	margin.add_theme_constant_override("margin_left", pad)
	margin.add_theme_constant_override("margin_right", pad)
	margin.add_theme_constant_override("margin_top", pad - 8)
	margin.add_theme_constant_override("margin_bottom", pad - 8)
	margin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(margin)
	var body := VBoxContainer.new()
	body.add_theme_constant_override("separation", 12)
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	margin.add_child(body)
	root.set_meta("body", body)
	root.set_meta("bg", bg)
	root.set_meta("margin", margin)
	return root


static func ink_label(text: String, px: int = 17, color: Color = ThemeKit.INK, kind: String = "body") -> Label:
	return ThemeKit.label(text, px, color, kind)


static func gold_label(text: String, px: int = 13) -> Label:
	var l := ThemeKit.label(text, px, ThemeKit.GOLD_DIM, "latin")
	return l


static func close_button(callback: Callable) -> Button:
	var b := ThemeKit.button("", "close", "ghost", 16)
	b.custom_minimum_size = Vector2(44, 44)
	b.alignment = HORIZONTAL_ALIGNMENT_CENTER
	b.pressed.connect(callback)
	return b


static func add_close(root: Control, callback: Callable) -> Button:
	var b := close_button(callback)
	b.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	b.offset_left = -62
	b.offset_top = 20
	b.offset_right = -20
	b.offset_bottom = 62
	root.add_child(b)
	return b


static func hline(color: Color = Color(ThemeKit.GOLD_DIM, 0.45), h: int = 1) -> ColorRect:
	return ThemeKit.hline(color, h)


static func backdrop_art(texture: Texture2D) -> TextureRect:
	var art := TextureRect.new()
	art.texture = texture
	art.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return art


static func gradient(left: Color, right: Color) -> TextureRect:
	var g := Gradient.new()
	g.colors = PackedColorArray([left, right])
	g.offsets = PackedFloat32Array([0.0, 1.0])
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.width = 512
	gt.height = 2
	gt.fill = GradientTexture2D.FILL_LINEAR
	gt.fill_from = Vector2(0, 0)
	gt.fill_to = Vector2(1, 0)
	var tr := TextureRect.new()
	tr.texture = gt
	tr.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	tr.stretch_mode = TextureRect.STRETCH_SCALE
	tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return tr


static func vertical_shade(top: Color, bottom: Color) -> TextureRect:
	var g := Gradient.new()
	g.colors = PackedColorArray([top, bottom])
	g.offsets = PackedFloat32Array([0.0, 1.0])
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.width = 2
	gt.height = 512
	gt.fill = GradientTexture2D.FILL_LINEAR
	gt.fill_from = Vector2(0, 0)
	gt.fill_to = Vector2(0, 1)
	var tr := TextureRect.new()
	tr.texture = gt
	tr.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	tr.stretch_mode = TextureRect.STRETCH_SCALE
	tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return tr


static func framed_image(tex: Texture2D, size: Vector2, bare: bool = false) -> Control:
	var root := Control.new()
	root.custom_minimum_size = size
	root.size = size
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.clip_contents = true
	var frame := Panel.new()
	frame.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	frame.add_theme_stylebox_override("panel", ThemeKit.stylebox(Color("#141b18"), Color(ThemeKit.GOLD, 0.45), 1, 2, 0, 0))
	root.add_child(frame)
	var art := TextureRect.new()
	art.texture = tex
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	art.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	art.offset_left = 4
	art.offset_top = 4
	art.offset_right = -4
	art.offset_bottom = -4
	root.add_child(art)
	if not bare:
		var shade := vertical_shade(Color(0, 0, 0, 0), Color(0.02, 0.03, 0.025, 0.62))
		root.add_child(shade)
	return root


static func stat_chip(icon_name: String, value: String, caption: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(ThemeKit.icon_rect(icon_name, 18, ThemeKit.GOLD))
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", -1)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(ThemeKit.label(value, 17, ThemeKit.PAPER, "latin"))
	box.add_child(ThemeKit.label(caption, 10, Color(ThemeKit.PAPER_2, 0.45)))
	row.add_child(box)
	return row


static func key_hint(keys: String, desc: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var key := ThemeKit.keycap(keys)
	key.custom_minimum_size = Vector2(58, 0)
	row.add_child(key)
	var l := ThemeKit.label(desc, 13, Color(ThemeKit.PAPER_2, 0.65))
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	row.add_child(l)
	return row


static func reveal(control: CanvasItem, delay: float = 0.0, from_y: float = 10.0) -> void:
	control.modulate.a = 0.0
	var tw := control.create_tween().set_parallel(true)
	tw.tween_interval(delay)
	tw.tween_property(control, "modulate:a", 1.0, 0.55).set_ease(Tween.EASE_OUT)


static func fade_in_node(node: CanvasItem, delay: float = 0.0, duration: float = 0.6) -> void:
	node.modulate.a = 0.0
	var tw := node.create_tween()
	tw.tween_interval(delay)
	tw.tween_property(node, "modulate:a", 1.0, duration).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_SINE)


