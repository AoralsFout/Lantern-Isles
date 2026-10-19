extends Node3D

## Gameplay scene: builds a chapter, runs the player/camera loop, and owns all
## in-game overlays. UI is split into sibling helper scripts to keep this file
## about the journey, not about layout.

var chapter_index := 0
var chapter_meta: Dictionary = {}
var world_data: Dictionary = {}
var builder: WorldBuilder
var player: Player
var camera_rig: CameraRig
var post_layer: CanvasLayer
var ui_layer: CanvasLayer
var hud: Hud
var dialogue: DialogueBox
var pause_menu: PauseMenu
var journal: JournalScreen
var settings_panel: SettingsPanel
var chapter_overlay: ChapterOverlay
var intro_overlay: IntroOverlay

var _nearest: Node = null
var _checkpoint := Vector3.ZERO
var _zone_cooldown := 0.0
var _pending_completion := false
var _photo_mode := false
var _screenshot_mode := false
var _shot_name := "chapter"
var _clean_shot := false
var _world_ready := false
var _smoke_mode := false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	get_tree().paused = false
	_screenshot_mode = "--screenshot" in OS.get_cmdline_user_args()
	_smoke_mode = "--smoke" in OS.get_cmdline_user_args()
	_clean_shot = "--clean" in OS.get_cmdline_user_args()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shot="):
			_shot_name = a.split("=")[1]
	chapter_index = GameState.current_chapter_index()
	chapter_meta = GameState.get_chapter(chapter_index)
	_load_world()
	_build_world()
	_build_player()
	_build_camera()
	_build_post()
	_build_ui()
	_start_audio()
	_connect_interactions()
	_world_ready = true
	GameState.begin_chapter(chapter_index)
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	if _screenshot_mode:
		_run_screenshot()
	else:
		_show_arrival()


func _exit_tree() -> void:
	GameState.save()


func _load_world() -> void:
	var path := str(chapter_meta.get("world", ""))
	if path == "" or not FileAccess.file_exists(path):
		push_error("Missing chapter world: " + path)
		return
	var f := FileAccess.open(path, FileAccess.READ)
	var parsed = JSON.parse_string(f.get_as_text())
	if parsed is Dictionary:
		world_data = parsed


func _build_world() -> void:
	builder = WorldBuilder.new()
	builder.name = "World"
	add_child(builder)
	builder.build(chapter_index, chapter_meta, world_data)
	builder.zone_entered.connect(_on_zone_entered)
	_checkpoint = builder.get_spawn()
	set_process(true)


func _build_player() -> void:
	player = Player.new()
	player.name = "LanternKeeper"
	add_child(player)
	player.teleport(builder.get_spawn())
	player.set_footstep_style(["grass", "sand", "snow", "stone"][chapter_index % 4])
	if player.lantern_light:
		player.lantern_light.light_energy = [0.55, 0.5, 0.7, 1.3][chapter_index % 4]
	player.landed.connect(_on_player_landed)


func _build_camera() -> void:
	var cfg: Dictionary = world_data.get("camera", {})
	camera_rig = CameraRig.new()
	camera_rig.name = "CameraRig"
	add_child(camera_rig)
	camera_rig.setup(player, cfg)
	player.camera_rig = camera_rig


func _build_post() -> void:
	post_layer = CanvasLayer.new()
	post_layer.layer = 4
	add_child(post_layer)
	var rect := ColorRect.new()
	rect.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var warmth: float = [0.16, 0.26, -0.18, -0.1][chapter_index % 4]
	var vig: float = [0.42, 0.38, 0.44, 0.5][chapter_index % 4]
	rect.material = ThemeKit.post_material(vig, 0.028, warmth, 0.02)
	post_layer.add_child(rect)


func _build_ui() -> void:
	ui_layer = CanvasLayer.new()
	ui_layer.layer = 10
	add_child(ui_layer)
	hud = Hud.new()
	hud.setup(self, chapter_index, chapter_meta, world_data)
	ui_layer.add_child(hud)

	dialogue = DialogueBox.new()
	ui_layer.add_child(dialogue)

	pause_menu = PauseMenu.new()
	pause_menu.setup(self)
	ui_layer.add_child(pause_menu)

	journal = JournalScreen.new()
	journal.setup(self)
	ui_layer.add_child(journal)

	settings_panel = SettingsPanel.new()
	settings_panel.setup(self)
	ui_layer.add_child(settings_panel)

	chapter_overlay = ChapterOverlay.new()
	chapter_overlay.setup(self)
	ui_layer.add_child(chapter_overlay)

	intro_overlay = IntroOverlay.new()
	intro_overlay.setup(self)
	ui_layer.add_child(intro_overlay)


func _start_audio() -> void:
	AudioDirector.play_music(str(chapter_meta.get("music", "")), 2.6)
	AudioDirector.play_ambience(str(chapter_meta.get("ambience", "")), 2.2)


func _connect_interactions() -> void:
	for it in builder.interactables:
		if it is Ember:
			it.collected.connect(_on_ember_collected)
		elif it is Npc:
			it.talked.connect(_on_npc_talked)
		elif it is Beacon:
			it.requested.connect(_on_beacon_requested)
	hud.update_embers(GameState.ember_count(chapter_index), int(chapter_meta.get("total", 5)), int(chapter_meta.get("required", 3)))


func _process(delta: float) -> void:
	if not _world_ready:
		return
	if _screenshot_mode:
		return
	if get_tree().paused:
		return
	_zone_cooldown = maxf(0.0, _zone_cooldown - delta)
	if player == null:
		return
	if player.global_position.y < -10.0:
		_respawn()
		return
	_find_nearby_interactable()
	if Input.is_action_just_pressed("interact") and _can_use_input():
		_try_interact()
	if Input.is_action_just_pressed("pause") and not _screenshot_mode:
		if dialogue and dialogue.is_open():
			dialogue.close()
		elif journal and journal.is_open():
			journal.close()
		elif settings_panel and settings_panel.is_open():
			settings_panel.close()
		elif pause_menu and pause_menu.is_open():
			pause_menu.close()
		else:
			pause_menu.open()
	if Input.is_action_just_pressed("journal") and _can_use_input():
		if journal and not journal.is_open():
			journal.open()
	if Input.is_action_just_pressed("photo") and not _screenshot_mode:
		_toggle_photo_mode()
	if Input.is_action_just_pressed("screenshot"):
		_take_screenshot("manual_" + str(Time.get_ticks_msec()))
	if Input.is_action_just_pressed("hide_ui"):
		hud.set_visible_hud(not hud.is_hud_visible())


func _can_use_input() -> bool:
	if get_tree().paused:
		return false
	if pause_menu and pause_menu.is_open():
		return false
	if dialogue and dialogue.is_open():
		return false
	if journal and journal.is_open():
		return false
	if settings_panel and settings_panel.is_open():
		return false
	if intro_overlay and intro_overlay.is_open():
		return false
	if chapter_overlay and chapter_overlay.is_open():
		return false
	return true


func _find_nearby_interactable() -> void:
	var best: Node = null
	var best_d := 3.5
	for it in builder.interactables:
		if not is_instance_valid(it):
			continue
		if it.has_method("can_interact") and not it.can_interact():
			continue
		var d := player.global_position.distance_to(it.global_position)
		if d < best_d:
			best_d = d
			best = it
	if best != _nearest:
		_nearest = best
		if hud:
			hud.show_prompt(_nearest.get_prompt() if _nearest else "")


func _try_interact() -> void:
	if _nearest == null or not is_instance_valid(_nearest):
		return
	if not _nearest.can_interact():
		return
	_nearest.interact(player)
	_nearest = null
	if hud:
		hud.show_prompt("")


func _on_ember_collected(ember: Ember) -> void:
	GameState.collect_ember(chapter_index, ember.ember_id)
	_checkpoint = ember.global_position
	var count := GameState.ember_count(chapter_index)
	var total := int(chapter_meta.get("total", 5))
	var required := int(chapter_meta.get("required", 3))
	hud.update_embers(count, total, required)
	hud.show_toast("拾起余烬 · " + ember.display_name, "ember")
	camera_rig.shake(0.12, 0.25)
	if count == required:
		hud.show_toast(str(chapter_meta.get("beacon_hint", "残灯在等你。")), "beacon")


func _on_npc_talked(npc: Npc) -> void:
	player.set_controls(false)
	var lines := npc.lines.duplicate()
	if GameState.has_memory(npc.memory_id):
		if npc.npc_id == "bell":
			lines = ["（钟声很轻，像有人在你耳边说：别怕。）", "「万灯归海，一灯回家。」"]
		elif npc.npc_id == "aying":
			lines = ["阿萤握着你递过去的纸灯，笑意像一层薄薄的晨光。", "「再往上走一步吧。我们一起，把天叫亮。」"]
		else:
			lines = ["风把" + npc.display_name + "的声音吹得很远。", "「灯还亮着，就很好。」"]
	dialogue.open(npc.display_name, lines, func():
		player.set_controls(true)
		if npc.memory_id != "" and GameState.unlock_memory(npc.memory_id):
			var info := GameState.find_memory(npc.memory_id)
			hud.show_memory(str(info.get("title", "记忆")), str(info.get("caption", "")))
			AudioDirector.sfx("memory", -4.0)
			camera_rig.shake(0.08, 0.3)
	)


func _on_beacon_requested(beacon: Beacon) -> void:
	var count := GameState.ember_count(chapter_index)
	if count < beacon.required:
		AudioDirector.ui("error")
		hud.show_toast("灯芯还差 %d 枚余烬。" % (beacon.required - count), "warning")
		return
	if _pending_completion:
		return
	_pending_completion = true
	player.set_controls(false)
	beacon.ignite()
	camera_rig.focus_on(beacon.global_position + Vector3(0, 3.4, 0), 17.0)
	camera_rig.shake(0.35, 1.4)
	hud.set_visible_hud(false)
	AudioDirector.stop_music(1.6)
	var timer := get_tree().create_timer(4.6)
	timer.timeout.connect(_finish_chapter)


func _finish_chapter() -> void:
	GameState.complete_chapter(chapter_index)
	camera_rig.clear_focus()
	chapter_overlay.open(chapter_index, chapter_meta, GameState.ember_count(chapter_index),
		int(chapter_meta.get("total", 5)), GameState.memory_count(chapter_index))


func _on_zone_entered(zone_name: String) -> void:
	if _zone_cooldown > 0.0 or _screenshot_mode:
		return
	_zone_cooldown = 6.0
	hud.show_zone(zone_name)
	AudioDirector.sfx("wind", -22.0)


func _on_player_landed(impact: float) -> void:
	if impact > 4.0 and GameState.get_setting("camera_shake", true):
		camera_rig.shake(minf(0.08 + impact * 0.012, 0.22), 0.22)


func _respawn() -> void:
	player.set_controls(false)
	AudioDirector.sfx("wind", -6.0)
	hud.fade_screen(true, 0.35)
	await get_tree().create_timer(0.4).timeout
	player.teleport(_checkpoint + Vector3(0, 0.25, 0))
	player.set_controls(true)
	hud.fade_screen(false, 0.5)
	hud.show_toast("风把你送回了灯边。", "wind")


func _show_arrival() -> void:
	var intro: Array = chapter_meta.get("intro", [])
	intro_overlay.open(chapter_index, chapter_meta, intro)


func _toggle_photo_mode() -> void:
	_photo_mode = not _photo_mode
	hud.set_visible_hud(not _photo_mode)
	camera_rig.set_photo_mode(_photo_mode)
	if _photo_mode:
		AudioDirector.play_music(str(chapter_meta.get("music", "")), 1.0)
		hud.show_toast("观景模式 · F 返回", "wind")


func _run_screenshot() -> void:
	if _smoke_mode:
		_run_smoke()
		return
	var early_args := OS.get_cmdline_user_args()
	if "--ending" in early_args:
		for i in GameState.chapter_count():
			GameState.complete_chapter(i)
		chapter_overlay.open(3, GameState.get_chapter(3), 5, 5, 2)
		await get_tree().create_timer(3.2).timeout
		await _take_screenshot("ui_ending")
		get_tree().quit()
		return
	hud.set_visible_hud(false)
	if _clean_shot:
		Input.mouse_mode = Input.MOUSE_MODE_HIDDEN
	player.set_physics_process(false)
	player.teleport(builder.get_spawn())
	camera_rig.clear_focus()
	var args := OS.get_cmdline_user_args()
	var overview := "--overview" in args
	var campos := Vector3.ZERO
	var lookat := Vector3(0, 8, 0)
	for a in args:
		if a.begins_with("--campos="):
			var v := a.split("=")[1].split(",")
			if v.size() == 3:
				campos = Vector3(float(v[0]), float(v[1]), float(v[2]))
				overview = true
		if a.begins_with("--look="):
			var v2 := a.split("=")[1].split(",")
			if v2.size() == 3:
				lookat = Vector3(float(v2[0]), float(v2[1]), float(v2[2]))
	if overview:
		var dbg := Camera3D.new()
		dbg.fov = 52.0
		dbg.far = 700.0
		if campos == Vector3.ZERO:
			campos = Vector3(105, 92, 128)
		dbg.position = campos
		add_child(dbg)
		dbg.look_at(lookat)
		dbg.current = true
		player.visible = false
	var ui_mode := ""
	for a in args:
		if a.begins_with("--ui="):
			ui_mode = a.split("=")[1]
	if ui_mode == "hud":
		hud.set_visible_hud(true, true)
	elif ui_mode == "intro":
		intro_overlay.open(chapter_index, chapter_meta, chapter_meta.get("intro", []))
	elif ui_mode == "pause":
		hud.set_visible_hud(false)
		pause_menu.open()
	elif ui_mode == "journal":
		hud.set_visible_hud(false)
		journal.open()
	elif ui_mode == "settings":
		hud.set_visible_hud(false)
		settings_panel.open()
	elif ui_mode == "dialogue":
		hud.set_visible_hud(false)
		for it in builder.interactables:
			if not is_instance_valid(it):
				continue
			if it is Npc:
				player.teleport(it.global_position + Vector3(0, 0.45, 3.0))
				_on_npc_talked(it)
				break
	elif ui_mode == "chapter":
		hud.set_visible_hud(false)
		game_overlay_shot()
	await get_tree().create_timer(2.8).timeout
	await _take_screenshot(_shot_name)
	get_tree().quit()


func _take_screenshot(shot_name: String) -> void:
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var dir := ProjectSettings.globalize_path("res://screenshots")
	DirAccess.make_dir_recursive_absolute(dir)
	var path := dir.path_join(shot_name + ".png")
	var err := img.save_png(path)
	print("SCREENSHOT ", err, " ", path, " ", img.get_width(), "x", img.get_height())


func game_overlay_shot() -> void:
	var mem := GameState.memory_count(chapter_index)
	chapter_overlay.open(chapter_index, chapter_meta, GameState.ember_count(chapter_index), int(chapter_meta.get("total", 5)), mem)


func _run_smoke() -> void:
	print("SMOKE start chapter=", chapter_index, " player=", player.global_position)
	intro_overlay.open(chapter_index, chapter_meta, chapter_meta.get("intro", []))
	await get_tree().create_timer(0.4).timeout
	print("SMOKE intro_paused=", get_tree().paused, " controls=", player.controls_enabled, " hud=", hud.is_hud_visible())
	await intro_overlay.close()
	await get_tree().create_timer(0.4).timeout
	print("SMOKE intro_closed paused=", get_tree().paused, " controls=", player.controls_enabled, " hud=", hud.is_hud_visible())
	await get_tree().create_timer(0.2).timeout
	var ground := builder.h_world(player.global_position.x, player.global_position.z)
	print("SMOKE ground=", ground, " y=", player.global_position.y, " on_floor=", player.is_on_floor(), " interactables=", builder.interactables.size())
	var start := player.global_position
	Input.action_press("move_forward")
	for i in 20:
		await get_tree().create_timer(0.05).timeout
	Input.action_release("move_forward")
	await get_tree().create_timer(0.2).timeout
	var moved := player.global_position.distance_to(start)
	print("SMOKE moved=", moved, " pos=", player.global_position, " on_floor=", player.is_on_floor(), " vel=", player.velocity)

	var collected := 0
	for it in builder.interactables:
		if it is Ember and not it.consumed:
			player.teleport(it.global_position + Vector3(0, 0.4, 0))
			await get_tree().create_timer(0.06).timeout
			it.interact(player)
			collected += 1
			await get_tree().create_timer(0.08).timeout
	print("SMOKE embers collected=", collected, " save_count=", GameState.ember_count(chapter_index))
	var npc: Npc = null
	for it in builder.interactables:
		if not is_instance_valid(it):
			continue
		if it is Npc:
			npc = it
			break
	if npc:
		player.teleport(npc.global_position + Vector3(0, 0.4, 2.0))
		_on_npc_talked(npc)
		await get_tree().create_timer(0.5).timeout
		print("SMOKE dialogue_open=", dialogue.is_open(), " memory_count=", GameState.memory_count(chapter_index))
		dialogue.close()
		await get_tree().create_timer(0.8).timeout
		print("SMOKE memory_after_dialogue=", GameState.memory_count(chapter_index))
	var beacon: Beacon = null
	for it in builder.interactables:
		if not is_instance_valid(it):
			continue
		if it is Beacon:
			beacon = it
			break
	if beacon:
		player.teleport(beacon.global_position + Vector3(0, 0.4, 3.0))
		await get_tree().create_timer(0.2).timeout
		_on_beacon_requested(beacon)
		await get_tree().create_timer(5.4).timeout
		print("SMOKE beacon_lit=", beacon.lit, " completed=", GameState.completed_count(), " overlay=", chapter_overlay.is_open())
		print("SMOKE save_current=", GameState.current_chapter_index(), " total_embers=", GameState.total_embers())
		await _take_screenshot("smoke_chapter")
	print("SMOKE done")
	get_tree().quit()
