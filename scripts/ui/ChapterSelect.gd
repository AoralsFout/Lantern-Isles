extends Control
class_name ChapterSelect

signal chosen(index: int)
signal closed

var _open := false
var _cards: Array[Button] = []
var _toast: Label


func _ready() -> void:
    set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    mouse_filter = Control.MOUSE_FILTER_STOP
    process_mode = Node.PROCESS_MODE_ALWAYS
    visible = false


func open() -> void:
    _open = true
    visible = true
    mouse_filter = Control.MOUSE_FILTER_STOP
    for c in get_children():
        c.queue_free()
    _build()
    modulate.a = 0.0
    var tw := create_tween()
    tw.tween_property(self, "modulate:a", 1.0, 0.35)
    if not _cards.is_empty():
        _cards[0].grab_focus()


func close() -> void:
    if not _open:
        return
    _open = false
    AudioDirector.ui("back")
    var tw := create_tween()
    tw.tween_property(self, "modulate:a", 0.0, 0.22)
    await tw.finished
    visible = false
    closed.emit()


func is_open() -> bool:
    return _open


func _unhandled_input(event: InputEvent) -> void:
    if not _open:
        return
    if event.is_action_pressed("pause") or event.is_action_pressed("ui_cancel"):
        get_viewport().set_input_as_handled()
        close()


func _build() -> void:
    var bg := UIHelper.overlay(true, 0.8)
    var extra := ColorRect.new()
    extra.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    extra.color = Color(0.012, 0.022, 0.018, 0.3)
    extra.mouse_filter = Control.MOUSE_FILTER_IGNORE
    bg.add_child(extra)
    add_child(bg)

    var top := MarginContainer.new()
    top.set_anchors_preset(Control.PRESET_TOP_LEFT)
    top.offset_left = 58
    top.offset_top = 44
    top.offset_right = 900
    top.offset_bottom = 170
    top.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(top)
    var hv := VBoxContainer.new()
    hv.add_theme_constant_override("separation", 3)
    top.add_child(hv)
    var eye := ThemeKit.label("T H E   F O U R   D R E A M S", 12, Color(ThemeKit.GOLD, 0.85), "latin")
    hv.add_child(eye)
    var title := ThemeKit.label("四段梦", 42, ThemeKit.PAPER, "display")
    hv.add_child(title)
    var sub := ThemeKit.label("选择一段梦，去把还亮着的光找回来。", 14, Color(ThemeKit.PAPER_2, 0.58))
    hv.add_child(sub)

    var close_btn := UIHelper.add_close(self, close)
    close_btn.name = "CloseButton"

    var center := CenterContainer.new()
    center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    center.offset_top = 80
    center.offset_bottom = -76
    center.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(center)
    var cards := HBoxContainer.new()
    cards.add_theme_constant_override("separation", 20)
    cards.alignment = BoxContainer.ALIGNMENT_CENTER
    cards.mouse_filter = Control.MOUSE_FILTER_IGNORE
    center.add_child(cards)
    for i in GameState.chapter_count():
        var card := _make_card(i)
        cards.add_child(card)
        _cards.append(card)

    _toast = ThemeKit.label("", 14, ThemeKit.CORAL)
    _toast.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
    _toast.position = Vector2(-200, -48)
    _toast.custom_minimum_size = Vector2(400, 24)
    _toast.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    _toast.modulate.a = 0.0
    add_child(_toast)

    var footer := ThemeKit.label("← → 选择     Enter 入梦     Esc 返回", 12, Color(ThemeKit.PAPER_2, 0.38), "body")
    footer.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
    footer.position = Vector2(58, -40)
    add_child(footer)


func _make_card(index: int) -> Button:
    var c := GameState.get_chapter(index)
    var card := Button.new()
    card.custom_minimum_size = Vector2(300, 458)
    card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    card.focus_mode = Control.FOCUS_ALL
    card.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
    card.clip_contents = true
    card.text = ""
    card.add_theme_stylebox_override("normal", ThemeKit.stylebox(Color(0.02, 0.035, 0.03, 0.4), Color(ThemeKit.GOLD, 0.18), 1, 4, 0, 0))
    card.add_theme_stylebox_override("hover", ThemeKit.stylebox(Color(0.02, 0.035, 0.03, 0.5), Color(ThemeKit.GOLD, 0.75), 1, 4, 0, 0))
    card.add_theme_stylebox_override("pressed", ThemeKit.stylebox(Color(0.02, 0.035, 0.03, 0.58), ThemeKit.GOLD, 1, 4, 0, 0))
    card.add_theme_stylebox_override("focus", ThemeKit.stylebox(Color(0, 0, 0, 0), Color(ThemeKit.GOLD, 0.85), 1, 4, 0, 0))
    card.add_theme_stylebox_override("disabled", ThemeKit.stylebox(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 4, 0, 0))

    var art := UIHelper.backdrop_art(load(str(c.get("card", ""))))
    card.add_child(art)
    var veil := ColorRect.new()
    veil.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    veil.color = Color(0.02, 0.03, 0.026, 0.12)
    veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
    card.add_child(veil)
    var shade := UIHelper.vertical_shade(Color(0.02, 0.03, 0.028, 0.06), Color(0.01, 0.018, 0.015, 0.97))
    shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    card.add_child(shade)

    var top_row := HBoxContainer.new()
    top_row.set_anchors_preset(Control.PRESET_TOP_WIDE)
    top_row.offset_left = 18
    top_row.offset_right = -18
    top_row.offset_top = 16
    top_row.offset_bottom = 48
    top_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
    card.add_child(top_row)
    var num := ThemeKit.label(["I", "II", "III", "IV"][index % 4], 14, Color(ThemeKit.GOLD_BRIGHT, 0.95), "latin")
    top_row.add_child(num)
    var spacer := Control.new()
    spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    top_row.add_child(spacer)
    var unlocked := GameState.is_chapter_unlocked(index)
    if not unlocked:
        top_row.add_child(ThemeKit.icon_rect("lock", 17, Color(ThemeKit.PAPER_2, 0.55)))
    elif bool(GameState.chapter_progress(index).get("completed", false)):
        top_row.add_child(ThemeKit.icon_rect("check", 18, ThemeKit.GOLD_BRIGHT))

    var bottom := MarginContainer.new()
    bottom.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
    bottom.offset_left = 20
    bottom.offset_right = -20
    bottom.offset_top = -218
    bottom.offset_bottom = -18
    bottom.mouse_filter = Control.MOUSE_FILTER_IGNORE
    card.add_child(bottom)
    var bv := VBoxContainer.new()
    bv.add_theme_constant_override("separation", 4)
    bottom.add_child(bv)
    var en := ThemeKit.label(str(c.get("en", "")).to_upper(), 11, Color(ThemeKit.GOLD, 0.85), "latin")
    bv.add_child(en)
    var title := ThemeKit.label(str(c.get("title", "")), 26, ThemeKit.PAPER, "display")
    bv.add_child(title)
    var poem := ThemeKit.label(str(c.get("poem", "")), 13, Color(ThemeKit.PAPER_2, 0.7))
    poem.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    poem.custom_minimum_size = Vector2(0, 34)
    bv.add_child(poem)
    var rule := UIHelper.hline(Color(ThemeKit.GOLD, 0.35), 1)
    bv.add_child(rule)
    var stat := HBoxContainer.new()
    stat.add_theme_constant_override("separation", 12)
    stat.mouse_filter = Control.MOUSE_FILTER_IGNORE
    bv.add_child(stat)
    var p := GameState.chapter_progress(index)
    var ec := (p.get("embers", []) as Array).size()
    var mc := (p.get("memories", []) as Array).size()
    var total := int(c.get("total", 5))
    stat.add_child(_mini_stat("ember", "%d/%d" % [ec, total]))
    stat.add_child(_mini_stat("memory", "%d/2" % mc))
    if bool(p.get("completed", false)):
        stat.add_child(_mini_stat("check", "梦已入册"))

    if not unlocked:
        var lock_veil := ColorRect.new()
        lock_veil.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
        lock_veil.color = Color(0.015, 0.025, 0.02, 0.68)
        lock_veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
        card.add_child(lock_veil)
        var lc := VBoxContainer.new()
        lc.set_anchors_preset(Control.PRESET_CENTER)
        lc.position = Vector2(-90, -30)
        lc.custom_minimum_size = Vector2(180, 60)
        lc.alignment = BoxContainer.ALIGNMENT_CENTER
        lc.mouse_filter = Control.MOUSE_FILTER_IGNORE
        card.add_child(lc)
        var li := ThemeKit.icon_rect("lock", 24, Color(ThemeKit.PAPER_2, 0.55))
        li.custom_minimum_size = Vector2(0, 28)
        li.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
        lc.add_child(li)
        var ll := ThemeKit.label("尚未入梦", 13, Color(ThemeKit.PAPER_2, 0.6))
        ll.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
        lc.add_child(ll)

    card.pressed.connect(func():
        if GameState.is_chapter_unlocked(index):
            AudioDirector.ui("click")
            chosen.emit(index)
        else:
            AudioDirector.ui("error")
            _show_toast("先点亮上一段梦，才能走到这里。")
    )
    card.mouse_entered.connect(func():
        card.pivot_offset = card.size * 0.5
        var tw := create_tween()
        tw.tween_property(card, "scale", Vector2(1.018, 1.018), 0.18)
    )
    card.mouse_exited.connect(func():
        var tw := create_tween()
        tw.tween_property(card, "scale", Vector2.ONE, 0.18)
    )
    return card


func _mini_stat(icon_name: String, text: String) -> HBoxContainer:
    var row := HBoxContainer.new()
    row.add_theme_constant_override("separation", 5)
    row.mouse_filter = Control.MOUSE_FILTER_IGNORE
    row.add_child(ThemeKit.icon_rect(icon_name, 13, Color(ThemeKit.GOLD, 0.8)))
    var l := ThemeKit.label(text, 11, Color(ThemeKit.PAPER_2, 0.55))
    row.add_child(l)
    return row


func _show_toast(text: String) -> void:
    _toast.text = text
    var tw := create_tween()
    _toast.modulate.a = 1.0
    tw.tween_interval(2.0)
    tw.tween_property(_toast, "modulate:a", 0.0, 0.5)
