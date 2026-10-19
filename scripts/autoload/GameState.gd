extends Node

## Persistent progress, settings, save file and input map for the whole game.

signal progress_changed
signal settings_changed
signal ember_collected(chapter_id: String, ember_id: String, count: int)
signal memory_unlocked(memory_id: String)
signal chapter_completed(chapter_id: String)

const CHAPTERS_PATH := "res://data/chapters.json"
const SAVE_PATH := "user://lantern_save.json"
const SAVE_VERSION := 1

const DEFAULT_SETTINGS := {
	"master": 0.9,
	"music": 0.72,
	"sfx": 0.82,
	"ambience": 0.66,
	"fullscreen": false,
	"camera_shake": true,
	"reduced_motion": false,
	"show_hints": true,
	"ui_scale": 1.0,
}

var chapters: Array = []
var save_data: Dictionary = {}
var debug_chapter: int = -1
var session_start: float = 0.0
var pending_shot_name: String = ""


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_load_chapters()
	_load_save()
	session_start = Time.get_unix_time_from_system()
	set_process(true)


func _process(delta: float) -> void:
	if startup_complete():
		save_data["total_time"] = float(save_data.get("total_time", 0.0)) + delta
		var ch := current_chapter_index()
		var cid := chapter_id(ch)
		if cid != "" and save_data["chapters"].has(cid):
			save_data["chapters"][cid]["time"] = float(save_data["chapters"][cid].get("time", 0.0)) + delta


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		save()


# ---------------------------------------------------------------- input ----
func install_input_actions() -> void:
	var bindings := {
		"move_forward": [KEY_W, KEY_UP],
		"move_back": [KEY_S, KEY_DOWN],
		"move_left": [KEY_A, KEY_LEFT],
		"move_right": [KEY_D, KEY_RIGHT],
		"sprint": [KEY_SHIFT],
		"jump": [KEY_SPACE],
		"interact": [KEY_E, KEY_ENTER],
		"pause": [KEY_ESCAPE],
		"journal": [KEY_TAB],
		"photo": [KEY_F],
		"hide_ui": [KEY_H],
		"screenshot": [KEY_F12],
		"camera_left": [KEY_Q],
		"camera_right": [KEY_R],
		"zoom_in": [KEY_EQUAL, KEY_KP_ADD],
		"zoom_out": [KEY_MINUS, KEY_KP_SUBTRACT],
	}
	for action in bindings:
		if not InputMap.has_action(action):
			InputMap.add_action(action)
		for key in bindings[action]:
			var ev := InputEventKey.new()
			ev.physical_keycode = key
			if not InputMap.action_has_event(action, ev):
				InputMap.action_add_event(action, ev)
		# gamepad parity for movement / jump / interact
		if action in ["move_forward", "move_back", "move_left", "move_right"]:
			var joy := InputEventJoypadMotion.new()
			joy.axis = JOY_AXIS_LEFT_Y if action in ["move_forward", "move_back"] else JOY_AXIS_LEFT_X
			joy.axis_value = -1.0 if action in ["move_forward", "move_left"] else 1.0
			InputMap.action_add_event(action, joy)
		if action == "jump":
			var jb := InputEventJoypadButton.new()
			jb.button_index = JOY_BUTTON_A
			InputMap.action_add_event(action, jb)
		if action == "interact":
			var xb := InputEventJoypadButton.new()
			xb.button_index = JOY_BUTTON_X
			InputMap.action_add_event(action, xb)
		if action == "pause":
			var sb := InputEventJoypadButton.new()
			sb.button_index = JOY_BUTTON_START
			InputMap.action_add_event(action, sb)


# -------------------------------------------------------------- chapters ----
func _load_chapters() -> void:
	var f := FileAccess.open(CHAPTERS_PATH, FileAccess.READ)
	if f == null:
		push_error("Missing chapters.json")
		return
	var parsed = JSON.parse_string(f.get_as_text())
	if parsed is Array:
		chapters = parsed


func chapter_count() -> int:
	return chapters.size()


func get_chapter(index: int) -> Dictionary:
	if index < 0 or index >= chapters.size():
		return {}
	return chapters[index]


func chapter_id(index: int) -> String:
	var c := get_chapter(index)
	return str(c.get("id", ""))


func index_for_id(id: String) -> int:
	for i in chapters.size():
		if str(chapters[i].get("id", "")) == id:
			return i
	return -1


func current_chapter_index() -> int:
	return int(save_data.get("current_chapter", 0))


func current_chapter() -> Dictionary:
	return get_chapter(current_chapter_index())


func unlocked_count() -> int:
	return int(save_data.get("unlocked", 1))


func is_chapter_unlocked(index: int) -> bool:
	return index < unlocked_count()


# ------------------------------------------------------------------ save ----
func _default_save() -> Dictionary:
	var ch := {}
	for c in chapters:
		ch[str(c.get("id", ""))] = {
			"embers": [],
			"memories": [],
			"completed": false,
			"time": 0.0,
		}
	return {
		"version": SAVE_VERSION,
		"started": false,
		"current_chapter": 0,
		"unlocked": 1,
		"chapters": ch,
		"settings": DEFAULT_SETTINGS.duplicate(),
		"total_time": 0.0,
		"created": Time.get_unix_time_from_system(),
	}


func _load_save() -> void:
	save_data = _default_save()
	if FileAccess.file_exists(SAVE_PATH):
		var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
		if f:
			var parsed = JSON.parse_string(f.get_as_text())
			if parsed is Dictionary:
				_merge_save(parsed)
	_apply_settings_later()


func _merge_save(parsed: Dictionary) -> void:
	if int(parsed.get("version", 0)) != SAVE_VERSION:
		# only ever additive; keep unknown chapters out of the way
		pass
	save_data["started"] = bool(parsed.get("started", false))
	save_data["current_chapter"] = clampi(int(parsed.get("current_chapter", 0)), 0, max(0, chapters.size() - 1))
	save_data["unlocked"] = clampi(int(parsed.get("unlocked", 1)), 1, max(1, chapters.size()))
	save_data["total_time"] = float(parsed.get("total_time", 0.0))
	save_data["created"] = float(parsed.get("created", Time.get_unix_time_from_system()))
	var parsed_ch: Dictionary = parsed.get("chapters", {}) if parsed.get("chapters", {}) is Dictionary else {}
	for c in chapters:
		var cid := str(c.get("id", ""))
		var base: Dictionary = save_data["chapters"].get(cid, {})
		var src: Dictionary = parsed_ch.get(cid, {}) if parsed_ch.get(cid, {}) is Dictionary else {}
		base["embers"] = src.get("embers", []) if src.get("embers", []) is Array else []
		base["memories"] = src.get("memories", []) if src.get("memories", []) is Array else []
		base["completed"] = bool(src.get("completed", false))
		base["time"] = float(src.get("time", 0.0))
		save_data["chapters"][cid] = base
	var st: Dictionary = parsed.get("settings", {}) if parsed.get("settings", {}) is Dictionary else {}
	for k in DEFAULT_SETTINGS:
		save_data["settings"][k] = st.get(k, DEFAULT_SETTINGS[k])


func save() -> void:
	if save_data.is_empty():
		return
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(save_data, "\t"))
		f.close()


func has_progress() -> bool:
	if not bool(save_data.get("started", false)):
		return false
	return true


func startup_complete() -> bool:
	return bool(save_data.get("started", false))


func new_game() -> void:
	var settings: Dictionary = save_data.get("settings", DEFAULT_SETTINGS.duplicate())
	save_data = _default_save()
	save_data["settings"] = settings
	save_data["started"] = true
	save_data["current_chapter"] = 0
	save_data["unlocked"] = 1
	save()
	progress_changed.emit()
	_apply_settings_later()


func begin_chapter(index: int) -> void:
	save_data["started"] = true
	save_data["current_chapter"] = clampi(index, 0, max(0, chapters.size() - 1))
	save()
	progress_changed.emit()


func chapter_progress(index: int) -> Dictionary:
	var cid := chapter_id(index)
	if cid == "":
		return {}
	if not save_data["chapters"].has(cid):
		save_data["chapters"][cid] = {"embers": [], "memories": [], "completed": false, "time": 0.0}
	return save_data["chapters"][cid]


func ember_count(index: int) -> int:
	var p := chapter_progress(index)
	return (p.get("embers", []) as Array).size()


func memory_count(index: int) -> int:
	var p := chapter_progress(index)
	return (p.get("memories", []) as Array).size()


func total_embers() -> int:
	var total := 0
	for i in chapters.size():
		total += ember_count(i)
	return total


func completed_count() -> int:
	var n := 0
	for i in chapters.size():
		if chapter_progress(i).get("completed", false):
			n += 1
	return n


func collect_ember(index: int, ember_id: String) -> bool:
	var p := chapter_progress(index)
	var arr: Array = p.get("embers", [])
	if ember_id in arr:
		return false
	arr.append(ember_id)
	p["embers"] = arr
	save()
	ember_collected.emit(chapter_id(index), ember_id, arr.size())
	progress_changed.emit()
	return true


func has_ember(index: int, ember_id: String) -> bool:
	var p := chapter_progress(index)
	return ember_id in (p.get("embers", []) as Array)


func unlock_memory(memory_id: String) -> bool:
	if memory_id == "":
		return false
	var info := find_memory(memory_id)
	if info.is_empty():
		return false
	var idx := int(info["chapter_index"])
	var p := chapter_progress(idx)
	var arr: Array = p.get("memories", [])
	if memory_id in arr:
		return false
	arr.append(memory_id)
	p["memories"] = arr
	save()
	memory_unlocked.emit(memory_id)
	progress_changed.emit()
	return true


func has_memory(memory_id: String) -> bool:
	var info := find_memory(memory_id)
	if info.is_empty():
		return false
	return memory_id in (chapter_progress(int(info["chapter_index"])).get("memories", []) as Array)


func find_memory(memory_id: String) -> Dictionary:
	for i in chapters.size():
		for m in chapters[i].get("memories", []):
			if str(m.get("id", "")) == memory_id:
				var d: Dictionary = m.duplicate()
				d["chapter_index"] = i
				d["chapter_title"] = chapters[i].get("title", "")
				return d
	return {}


func all_memories_for_chapter(index: int) -> Array:
	return get_chapter(index).get("memories", [])


func complete_chapter(index: int) -> void:
	var p := chapter_progress(index)
	if p.get("completed", false):
		return
	p["completed"] = true
	save_data["unlocked"] = clampi(max(unlocked_count(), index + 2), 1, chapters.size())
	if index + 1 < chapters.size():
		save_data["current_chapter"] = index + 1
	save()
	chapter_completed.emit(chapter_id(index))
	progress_changed.emit()


func is_game_complete() -> bool:
	return completed_count() >= chapters.size() and chapters.size() > 0


# -------------------------------------------------------------- settings ----
func get_setting(key: String, fallback = null):
	return save_data.get("settings", {}).get(key, fallback)


func set_setting(key: String, value) -> void:
	if not save_data.has("settings"):
		save_data["settings"] = DEFAULT_SETTINGS.duplicate()
	save_data["settings"][key] = value
	_apply_settings()
	save()
	settings_changed.emit()


func _apply_settings_later() -> void:
	await get_tree().process_frame
	_apply_settings()


func _apply_settings() -> void:
	var args := OS.get_cmdline_user_args() + OS.get_cmdline_args()
	var no_fs := "--screenshot" in args
	if not no_fs:
		var want_fs := bool(get_setting("fullscreen", false))
		var mode := DisplayServer.window_get_mode()
		if want_fs and mode != DisplayServer.WINDOW_MODE_FULLSCREEN:
			DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
		elif not want_fs and mode == DisplayServer.WINDOW_MODE_FULLSCREEN:
			DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	var audio := get_node_or_null("/root/AudioDirector")
	if audio and audio.has_method("apply_settings"):
		audio.apply_settings()


func format_time(seconds: float) -> String:
	var s := int(max(0.0, seconds))
	var h := s / 3600
	var m := (s % 3600) / 60
	if h > 0:
		return "%d 时 %02d 分" % [h, m]
	return "%d 分" % m
