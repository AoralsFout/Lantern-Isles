extends Node

## Entry point. Installs input actions, prepares the persistent state and hands
## control to the title screen (or directly to a chapter for automated shots).

func _ready() -> void:
	GameState.install_input_actions()
	await get_tree().process_frame
	var uargs := OS.get_cmdline_user_args()
	if "--screenshot" in uargs or "--screenshot" in OS.get_cmdline_args():
		var args := uargs
		if "--ui=title" in args or "--chapter-select" in args or "--prologue" in args or "--credits" in args:
			SceneRouter.goto_title()
			return
		var chapter := 1
		for a in args:
			if a.begins_with("--chapter="):
				chapter = clampi(int(a.split("=")[1]) - 1, 0, 3)
		GameState.debug_chapter = chapter
		GameState.new_game()
		SceneRouter.goto_game(chapter, true)
		return
	SceneRouter.goto_title()

