extends Node

## Music, ambience and one-shot sound effects. Missing audio files are legal:
## the game stays fully playable while assets are still being generated.

const MUSIC := {
	"title": "res://assets/audio/music/title.ogg",
	"spring": "res://assets/audio/music/spring.ogg",
	"desert": "res://assets/audio/music/desert.ogg",
	"winter": "res://assets/audio/music/winter.ogg",
	"night": "res://assets/audio/music/night.ogg",
	"ending": "res://assets/audio/music/ending.ogg",
}

const AMBIENCE := {
	"spring_amb": "res://assets/audio/ambience/spring_amb.ogg",
	"desert_amb": "res://assets/audio/ambience/desert_amb.ogg",
	"winter_amb": "res://assets/audio/ambience/winter_amb.ogg",
	"night_amb": "res://assets/audio/ambience/night_amb.ogg",
}

const SFX_SINGLE := {
	"jump": "res://assets/audio/sfx/jump.wav",
	"land": "res://assets/audio/sfx/land.wav",
	"splash": "res://assets/audio/sfx/splash.wav",
	"pickup": "res://assets/audio/sfx/pickup_ember.wav",
	"memory": "res://assets/audio/sfx/memory_unlock.wav",
	"beacon": "res://assets/audio/sfx/beacon_ignite.wav",
	"hover": "res://assets/audio/sfx/ui_hover.wav",
	"click": "res://assets/audio/sfx/ui_click.wav",
	"back": "res://assets/audio/sfx/ui_back.wav",
	"error": "res://assets/audio/sfx/ui_error.wav",
	"dialogue": "res://assets/audio/sfx/dialogue.wav",
	"complete": "res://assets/audio/sfx/chapter_complete.wav",
	"gate": "res://assets/audio/sfx/gate_open.wav",
	"wind": "res://assets/audio/sfx/wind_gust.wav",
}

var _music_a: AudioStreamPlayer
var _music_b: AudioStreamPlayer
var _amb_a: AudioStreamPlayer
var _amb_b: AudioStreamPlayer
var _sfx: Array[AudioStreamPlayer] = []
var _sfx_cursor := 0
var _current_music := ""
var _next_music := ""
var _current_amb := ""
var _next_amb := ""
var _music_target_a := 0.0
var _music_target_b := 0.0
var _amb_target_a := 0.0
var _amb_target_b := 0.0
var _pitch_rng := RandomNumberGenerator.new()
var _cache: Dictionary = {}
var _warned: Dictionary = {}


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_setup_buses()
	_pitch_rng.randomize()
	_music_a = _make_player("Music")
	_music_b = _make_player("Music")
	_amb_a = _make_player("Ambience")
	_amb_b = _make_player("Ambience")
	for i in 10:
		_sfx.append(_make_player("SFX"))
	apply_settings()


func _make_player(bus: String) -> AudioStreamPlayer:
	var p := AudioStreamPlayer.new()
	p.bus = bus
	p.process_mode = Node.PROCESS_MODE_ALWAYS
	add_child(p)
	return p


func _setup_buses() -> void:
	for bus_name in ["Music", "SFX", "Ambience"]:
		if AudioServer.get_bus_index(bus_name) == -1:
			var idx := AudioServer.bus_count
			AudioServer.add_bus(idx)
			AudioServer.set_bus_name(idx, bus_name)
			AudioServer.set_bus_send(idx, "Master")


func apply_settings() -> void:
	if not is_inside_tree():
		return
	_set_bus_linear("Master", float(GameState.get_setting("master", 0.9)))
	_set_bus_linear("Music", float(GameState.get_setting("music", 0.72)))
	_set_bus_linear("SFX", float(GameState.get_setting("sfx", 0.82)))
	_set_bus_linear("Ambience", float(GameState.get_setting("ambience", 0.66)))


func _set_bus_linear(bus_name: String, linear: float) -> void:
	var idx := AudioServer.get_bus_index(bus_name)
	if idx < 0:
		return
	linear = clampf(linear, 0.0, 1.0)
	AudioServer.set_bus_volume_db(idx, linear_to_db(maxf(0.0001, linear)))
	AudioServer.set_bus_mute(idx, linear <= 0.001)


func _ogg(path: String):
	if not ResourceLoader.exists(path):
		return null
	if _cache.has(path):
		return _cache[path]
	var stream = load(path)
	if stream is AudioStreamOggVorbis:
		stream.loop = true
	_cache[path] = stream
	return stream


func play_music(id: String, fade: float = 2.4) -> void:
	if id == "":
		return
	if id == _current_music and (_music_a.playing or _music_b.playing):
		return
	var path: String = MUSIC.get(id, "")
	var stream = _ogg(path)
	if stream == null:
		_warn_once("music:" + id)
		return
	_current_music = id
	if _music_a.playing and _music_b.playing:
		# replace the quieter one
		if _music_b.volume_db < _music_a.volume_db:
			_music_target_b = 0.0
			_next_music = id
			_fade_out_then_start(_music_b, _music_a, stream, fade)
		else:
			_music_target_a = 0.0
			_next_music = id
			_fade_out_then_start(_music_a, _music_b, stream, fade)
	elif _music_a.playing:
		_next_music = id
		_fade_out_then_start(_music_a, _music_b, stream, fade)
	elif _music_b.playing:
		_next_music = id
		_fade_out_then_start(_music_b, _music_a, stream, fade)
	else:
		_music_a.stream = stream
		_music_a.volume_db = -60.0
		_music_a.play()
		_music_target_a = db_to_linear(-6.0)
		_music_target_b = 0.0


func _fade_out_then_start(old: AudioStreamPlayer, fresh: AudioStreamPlayer, stream: AudioStream, fade: float) -> void:
	if old == _music_a:
		_music_target_a = 0.0
	else:
		_music_target_b = 0.0
	fresh.stream = stream
	fresh.volume_db = -60.0
	fresh.play()
	if fresh == _music_a:
		_music_target_a = db_to_linear(-6.0)
	else:
		_music_target_b = db_to_linear(-6.0)
	# a timed stop for the old one keeps the crossfade simple and pause-safe
	var timer := get_tree().create_timer(fade, true, false, true)
	timer.timeout.connect(func():
		if old.stream != stream:
			old.stop()
	)


func stop_music(fade: float = 1.6) -> void:
	_current_music = ""
	_music_target_a = 0.0
	_music_target_b = 0.0
	var timer := get_tree().create_timer(fade, true, false, true)
	timer.timeout.connect(func():
		if _music_target_a <= 0.0:
			_music_a.stop()
		if _music_target_b <= 0.0:
			_music_b.stop()
	)


func play_ambience(id: String, fade: float = 2.0) -> void:
	if id == _current_amb:
		return
	var stream = _ogg(AMBIENCE.get(id, ""))
	if stream == null:
		_warn_once("amb:" + id)
		return
	_current_amb = id
	if _amb_a.playing and _amb_b.playing:
		if _amb_b.volume_db < _amb_a.volume_db:
			_amb_target_b = 0.0
			_amb_a.stream = stream
			_amb_a.volume_db = -60.0
			_amb_a.play()
			_amb_target_a = db_to_linear(-8.0)
		else:
			_amb_target_a = 0.0
			_amb_b.stream = stream
			_amb_b.volume_db = -60.0
			_amb_b.play()
			_amb_target_b = db_to_linear(-8.0)
	elif _amb_a.playing:
		_amb_target_a = 0.0
		_amb_b.stream = stream
		_amb_b.volume_db = -60.0
		_amb_b.play()
		_amb_target_b = db_to_linear(-8.0)
	elif _amb_b.playing:
		_amb_target_b = 0.0
		_amb_a.stream = stream
		_amb_a.volume_db = -60.0
		_amb_a.play()
		_amb_target_a = db_to_linear(-8.0)
	else:
		_amb_a.stream = stream
		_amb_a.volume_db = -60.0
		_amb_a.play()
		_amb_target_a = db_to_linear(-8.0)


func stop_ambience(fade: float = 1.2) -> void:
	_current_amb = ""
	_amb_target_a = 0.0
	_amb_target_b = 0.0
	var timer := get_tree().create_timer(fade, true, false, true)
	timer.timeout.connect(func():
		_amb_a.stop()
		_amb_b.stop()
	)


func _process(delta: float) -> void:
	if _music_a:
		var target_db := linear_to_db(maxf(0.0001, _music_target_a))
		_music_a.volume_db = move_toward(_music_a.volume_db, target_db, delta * 26.0)
	if _music_b:
		var target_db := linear_to_db(maxf(0.0001, _music_target_b))
		_music_b.volume_db = move_toward(_music_b.volume_db, target_db, delta * 26.0)
	if _amb_a:
		_amb_a.volume_db = move_toward(_amb_a.volume_db, linear_to_db(maxf(0.0001, _amb_target_a)), delta * 18.0)
	if _amb_b:
		_amb_b.volume_db = move_toward(_amb_b.volume_db, linear_to_db(maxf(0.0001, _amb_target_b)), delta * 18.0)


func sfx(id: String, volume_db: float = 0.0, pitch_variation: float = 0.0) -> void:
	var path: String = SFX_SINGLE.get(id, "")
	if path == "":
		return
	play_file(path, volume_db, 1.0 + _pitch_rng.randf_range(-pitch_variation, pitch_variation))


func step(style: String) -> void:
	var variants := 4
	var idx := _pitch_rng.randi_range(1, variants)
	var path := "res://assets/audio/sfx/step_%s_%d.wav" % [style, idx]
	play_file(path, -8.0, _pitch_rng.randf_range(0.92, 1.08))


func play_file(path: String, volume_db: float = 0.0, pitch: float = 1.0) -> void:
	if not ResourceLoader.exists(path):
		_warn_once(path)
		return
	var stream = _cache.get(path)
	if stream == null:
		stream = load(path)
		_cache[path] = stream
	if _sfx.is_empty():
		return
	var p := _sfx[_sfx_cursor % _sfx.size()]
	_sfx_cursor += 1
	p.stream = stream
	p.volume_db = volume_db
	p.pitch_scale = pitch
	p.play()


func ui(kind: String = "click") -> void:
	match kind:
		"hover":
			sfx("hover", -14.0, 0.03)
		"back":
			sfx("back", -7.0)
		"error":
			sfx("error", -8.0)
		_:
			sfx("click", -6.0, 0.02)


func _warn_once(key: String) -> void:
	if _warned.has(key):
		return
	_warned[key] = true
	push_warning("Audio asset missing (graceful): " + key)
