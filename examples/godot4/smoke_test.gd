extends SceneTree


func _initialize() -> void:
	call_deferred("_check")


func _check() -> void:
	var parsed = JSON.parse_string(FileAccess.get_file_as_string("res://exports/sprite.json"))
	if not parsed is Dictionary:
		_fail("Missing or invalid sprite.json")
		return
	var metadata: Dictionary = parsed
	var animations: Dictionary = metadata.get("animations", {})
	if animations.is_empty():
		_fail("No animations in sprite.json")
		return
	var animation_name: String = animations.keys()[0]
	var clip: Dictionary = animations[animation_name]
	var frames: Array = clip["frames"]
	var scene := load("res://main.tscn").instantiate() as AnimatedSprite2D
	root.add_child(scene)
	var imported := scene.sprite_frames
	if not imported.has_animation(animation_name):
		_fail("Animation was not imported")
		return
	var expected_count := frames.size()
	if clip["loop_mode"] == "ping_pong":
		expected_count += max(0, frames.size() - 2)
	if imported.get_frame_count(animation_name) != expected_count:
		_fail("Frame count does not match metadata")
		return
	var fps := float(clip["fps"])
	if imported.get_animation_speed(animation_name) != fps:
		_fail("FPS does not match metadata")
		return
	if imported.get_animation_loop(animation_name) != (clip["loop_mode"] != "once"):
		_fail("Loop mode does not match metadata")
		return
	var frame: Dictionary = frames[0]
	if not is_equal_approx(
		imported.get_frame_duration(animation_name, 0),
		float(frame["duration_ms"]) * fps / 1000.0
	):
		_fail("Frame duration does not match metadata")
		return
	var texture := imported.get_frame_texture(animation_name, 0) as AtlasTexture
	var rect: Dictionary = frame["rect"]
	if texture == null or texture.region != Rect2(rect["x"], rect["y"], rect["w"], rect["h"]):
		_fail("Frame rectangle does not match metadata")
		return
	print("Godot 4.4 import smoke passed")
	quit(0)


func _fail(message: String) -> void:
	push_error(message)
	quit(1)
