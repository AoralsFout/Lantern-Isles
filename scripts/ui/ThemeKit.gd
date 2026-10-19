class_name ThemeKit
extends RefCounted

## Central visual language: paper, ink, brass, jade. All UI is built in code so
## it stays consistent and never falls back to Godot's default controls.

const INK := Color("#1c2522")
const INK_2 := Color("#2b3733")
const INK_3 := Color("#46534d")
const PAPER := Color("#f4ead7")
const PAPER_2 := Color("#e8dcc5")
const PAPER_3 := Color("#d6c7ad")
const PAPER_DARK := Color("#c2b294")
const GOLD := Color("#d5b374")
const GOLD_BRIGHT := Color("#f0d49a")
const GOLD_DIM := Color("#9d8255")
const JADE := Color("#7da18b")
const JADE_DARK := Color("#4f725e")
const CORAL := Color("#ce846d")
const NIGHT := Color("#0c1211")

const CHAPTER_TINTS := [
	Color("#8fb49a"),
	Color("#d4a064"),
	Color("#a9c9d3"),
	Color("#9186c6"),
]

static var _fonts: Dictionary = {}
static var _icons: Dictionary = {}
static var _theme: Theme = null
static var _foliage_mat: ShaderMaterial = null


# ------------------------------------------------------------------ fonts ---
static func font(kind: String = "body") -> Font:
	if _fonts.has(kind):
		return _fonts[kind]
	var f: Font = null
	match kind:
		"display":
			f = _load_font("res://assets/fonts/ZCOOLXiaoWei-Regular.ttf")
		"latin":
			f = _load_font("res://assets/fonts/Marcellus-Regular.ttf")
		"latin_alt":
			f = _load_font("res://assets/fonts/Marcellus-Regular.ttf")
		_:
			f = _load_font("res://assets/fonts/NotoSerifSC-Variable.ttf")
	if f == null:
		var sf := SystemFont.new()
		sf.font_names = PackedStringArray(["Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC"])
		sf.allow_system_fallback = true
		f = sf
	_fonts[kind] = f
	return f


static func _load_font(path: String) -> Font:
	if not ResourceLoader.exists(path):
		return null
	var res = load(path)
	if res is Font:
		return res
	return null


static func serif_var(weight: int = 420, spacing: int = 0) -> FontVariation:
	var fv := FontVariation.new()
	fv.base_font = font("body")
	fv.variation_opentype = {"wght": weight}
	fv.spacing_glyph = spacing
	return fv


# ------------------------------------------------------------------ icons ---
static func icon(name: String) -> Texture2D:
	if _icons.has(name):
		return _icons[name]
	var path := "res://assets/ui/icons/%s.svg" % name
	var tex: Texture2D = null
	if ResourceLoader.exists(path):
		tex = load(path)
	if tex:
		var img := tex.get_image()
		if img:
			img.resize(32, 32, Image.INTERPOLATE_LANCZOS)
			tex = ImageTexture.create_from_image(img)
	_icons[name] = tex
	return tex


static func icon_rect(name: String, px: float, color: Color = PAPER) -> TextureRect:
	var tr := TextureRect.new()
	tr.texture = icon(name)
	tr.custom_minimum_size = Vector2(px, px)
	tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	tr.modulate = color
	tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return tr


# ----------------------------------------------------------------- styles ---
static func stylebox(bg: Color, border_color: Color = Color.TRANSPARENT, border: int = 0, radius: int = 4, margin_h: int = 18, margin_v: int = 12) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.border_color = border_color
	sb.set_border_width_all(border)
	sb.set_corner_radius_all(radius)
	sb.content_margin_left = margin_h
	sb.content_margin_right = margin_h
	sb.content_margin_top = margin_v
	sb.content_margin_bottom = margin_v
	sb.anti_aliasing = true
	return sb


static func make_theme() -> Theme:
	if _theme != null:
		return _theme
	var t := Theme.new()
	t.default_font = font("body")
	t.default_font_size = 18
	t.set_color("font_color", "Label", PAPER)
	t.set_color("font_shadow_color", "Label", Color(0, 0, 0, 0.25))
	t.set_constant("shadow_offset_x", "Label", 1)
	t.set_constant("shadow_offset_y", "Label", 2)

	t.set_color("font_color", "Button", PAPER_2)
	t.set_color("font_hover_color", "Button", GOLD_BRIGHT)
	t.set_color("font_pressed_color", "Button", GOLD)
	t.set_color("font_focus_color", "Button", GOLD_BRIGHT)
	t.set_stylebox("normal", "Button", stylebox(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 4, 18, 10))
	t.set_stylebox("hover", "Button", stylebox(Color(0.96, 0.9, 0.78, 0.07), Color(GOLD, 0.22), 1, 4, 18, 10))
	t.set_stylebox("pressed", "Button", stylebox(Color(0.96, 0.9, 0.78, 0.13), Color(GOLD, 0.5), 1, 4, 18, 10))
	t.set_stylebox("focus", "Button", stylebox(Color(0, 0, 0, 0), Color(GOLD, 0.5), 1, 4, 18, 10))
	t.set_stylebox("disabled", "Button", stylebox(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 4, 18, 10))
	t.set_color("font_disabled_color", "Button", Color(PAPER_2, 0.3))

	t.set_stylebox("panel", "Panel", stylebox(Color(0.07, 0.09, 0.085, 0.86), Color(GOLD, 0.24), 1, 6, 0, 0))
	t.set_stylebox("panel", "PanelContainer", stylebox(Color(0.07, 0.09, 0.085, 0.72), Color(GOLD, 0.2), 1, 6, 0, 0))
	t.set_stylebox("panel", "PopupMenu", stylebox(Color("#101614"), Color(GOLD, 0.25), 1, 4, 8, 8))
	t.set_font_size("font_size", "PopupMenu", 16)

	t.set_stylebox("background", "ProgressBar", stylebox(Color(1, 1, 1, 0.08), Color(0, 0, 0, 0), 0, 2, 0, 0))
	t.set_stylebox("fill", "ProgressBar", stylebox(GOLD, Color(0, 0, 0, 0), 0, 2, 0, 0))

	t.set_stylebox("scroll", "VScrollBar", stylebox(Color(1, 1, 1, 0.04), Color(0, 0, 0, 0), 0, 2, 0, 0))
	t.set_stylebox("grabber", "VScrollBar", stylebox(Color(GOLD, 0.45), Color(0, 0, 0, 0), 0, 2, 0, 0))
	t.set_stylebox("grabber_highlight", "VScrollBar", stylebox(Color(GOLD, 0.7), Color(0, 0, 0, 0), 0, 2, 0, 0))
	t.set_stylebox("grabber_pressed", "VScrollBar", stylebox(GOLD, Color(0, 0, 0, 0), 0, 2, 0, 0))
	_theme = t
	return t


static func label(text: String, px: int = 18, color: Color = PAPER, kind: String = "body") -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", font(kind))
	l.add_theme_font_size_override("font_size", px)
	l.add_theme_color_override("font_color", color)
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.22))
	l.add_theme_constant_override("shadow_offset_x", 1)
	l.add_theme_constant_override("shadow_offset_y", 2)
	return l


static func rich(text: String, px: int = 18, color: Color = PAPER, kind: String = "body") -> RichTextLabel:
	var r := RichTextLabel.new()
	r.bbcode_enabled = true
	r.text = text
	r.fit_content = true
	r.scroll_active = false
	r.add_theme_font_override("normal_font", font(kind))
	r.add_theme_font_size_override("normal_font_size", px)
	r.add_theme_color_override("default_color", color)
	r.add_theme_constant_override("line_separation", 6)
	return r


static func panel(bg: Color = Color(0.07, 0.09, 0.085, 0.72), border: Color = Color(GOLD, 0.2), radius: int = 6) -> PanelContainer:
	var p := PanelContainer.new()
	p.add_theme_stylebox_override("panel", stylebox(bg, border, 1, radius, 26, 22))
	return p


static func hline(color: Color = Color(GOLD, 0.25), height: int = 1) -> ColorRect:
	var c := ColorRect.new()
	c.color = color
	c.custom_minimum_size = Vector2(0, height)
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return c


static func spacer(px: int = 12) -> Control:
	var c := Control.new()
	c.custom_minimum_size = Vector2(0, px)
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return c


static func hspacer(px: int = 12) -> Control:
	var c := Control.new()
	c.custom_minimum_size = Vector2(px, 0)
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return c


static func button(text: String, icon_name: String = "", kind: String = "menu", px: int = 22) -> Button:
	var b := Button.new()
	b.set_script(load("res://scripts/ui/InkButton.gd"))
	b.set("button_kind", kind)
	b.text = text
	b.icon = icon(icon_name) if icon_name != "" else null
	b.add_theme_font_override("font", font("body"))
	b.add_theme_font_size_override("font_size", px)
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.expand_icon = false
	b.add_theme_constant_override("h_separation", 16)
	b.custom_minimum_size = Vector2(0, 52)
	b.focus_mode = Control.FOCUS_ALL
	b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	return b


static func small_button(text: String, icon_name: String = "", px: int = 16) -> Button:
	var b := button(text, icon_name, "chip", px)
	b.custom_minimum_size = Vector2(0, 38)
	return b


static func keycap(text: String) -> PanelContainer:
	var p := PanelContainer.new()
	p.add_theme_stylebox_override("panel", stylebox(Color(0.95, 0.9, 0.8, 0.1), Color(GOLD, 0.5), 1, 4, 9, 5))
	var l := label(text, 14, GOLD_BRIGHT, "latin")
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	p.add_child(l)
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return p


static func dim_text(text: String, px: int = 14) -> Label:
	var l := label(text, px, Color(PAPER_2, 0.58))
	return l


static func full_rect(c: Control) -> void:
	c.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)


static func tint_for_chapter(index: int) -> Color:
	if index >= 0 and index < CHAPTER_TINTS.size():
		return CHAPTER_TINTS[index]
	return GOLD


static func fade_in_node(node: CanvasItem, delay: float = 0.0, duration: float = 0.6) -> void:
	node.modulate.a = 0.0
	var tw := node.create_tween()
	tw.tween_interval(delay)
	tw.tween_property(node, "modulate:a", 1.0, duration).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_SINE)


static func appear(control: Control, delay: float = 0.0, from_scale: float = 0.97) -> void:
	control.modulate.a = 0.0
	control.scale = Vector2(from_scale, from_scale)
	control.pivot_offset = control.size * 0.5
	var tw := control.create_tween().set_parallel(true)
	tw.tween_interval(delay)
	tw.tween_property(control, "modulate:a", 1.0, 0.55).set_ease(Tween.EASE_OUT)
	tw.tween_property(control, "scale", Vector2.ONE, 0.65).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_BACK)


# ------------------------------------------------------------- postprocess ---
static func post_material(vignette: float = 0.42, grain: float = 0.035, warmth: float = 0.06, desat: float = 0.02) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/postprocess.gdshader")
	m.set_shader_parameter("vignette", vignette)
	m.set_shader_parameter("grain", grain)
	m.set_shader_parameter("warmth", warmth)
	m.set_shader_parameter("desat", desat)
	return m


static func color_rect(color: Color, min_size: Vector2 = Vector2.ZERO) -> ColorRect:
	var c := ColorRect.new()
	c.color = color
	c.custom_minimum_size = min_size
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return c


static func icon_stat(icon_name: String, value: String, caption: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var ic := icon_rect(icon_name, 18, GOLD)
	ic.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(ic)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", -3)
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.add_child(label(value, 17, PAPER, "latin"))
	col.add_child(label(caption, 10, Color(PAPER_2, 0.45)))
	row.add_child(col)
	return row
