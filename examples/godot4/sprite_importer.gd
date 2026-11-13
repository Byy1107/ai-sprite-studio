extends AnimatedSprite2D

const METADATA_PATH := "res://exports/sprite.json"


func _ready() -> void:
	if not FileAccess.file_exists(METADATA_PATH):
		push_warning("Copy sprite.png and sprite.json into res://exports/ before running.")
		return
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(METADATA_PATH))
	if not parsed is Dictionary:
		push_error("Invalid sprite.json")
		return
	var metadata: Dictionary = parsed
	var meta: Dictionary = metadata.get("meta", {})
	if meta.get("schema_version") != 1 or meta.get("preset_id") != "godot4":
		push_error("Expected AI Sprite Studio Godot 4 export schema v1")
		return
	if meta.get("image") != "sprite.png":
		push_error("Expected sprite.png next to sprite.json")
		return
	var image_path: String = METADATA_PATH.get_base_dir().path_join(meta.get("image", ""))
	var texture = ResourceLoader.load(image_path)
	if not texture is Texture2D:
		push_error("Missing spritesheet PNG: " + image_path)
		return
	var atlas: Texture2D = texture
	var size: Dictionary = meta.get("size", {})
	if size.get("w") != atlas.get_width() or size.get("h") != atlas.get_height():
		push_error("Spritesheet dimensions do not match sprite.json")
		return
	var animations: Dictionary = metadata.get("animations", {})
	var result := SpriteFrames.new()
	if result.has_animation("default"):
		result.remove_animation("default")
	for animation_name in animations:
		var clip: Dictionary = animations[animation_name]
		var fps := float(clip.get("fps", 0))
		var frames: Array = clip.get("frames", [])
		if fps <= 0.0 or frames.is_empty():
			push_error("Invalid animation timing: " + str(animation_name))
			return
		result.add_animation(animation_name)
		result.set_animation_speed(animation_name, fps)
		result.set_animation_loop(animation_name, clip.get("loop_mode") != "once")
		for frame in frames:
			var rect: Dictionary = frame["rect"]
			var region := Rect2(rect["x"], rect["y"], rect["w"], rect["h"])
			if region.position.x < 0 or region.position.y < 0 or region.end.x > atlas.get_width() or region.end.y > atlas.get_height():
				push_error("Frame rectangle is outside spritesheet")
				return
			var cropped := AtlasTexture.new()
			cropped.atlas = atlas
			cropped.region = region
			result.add_frame(animation_name, cropped, float(frame["duration_ms"]) * fps / 1000.0)
		if clip.get("loop_mode") == "ping_pong":
			for index in range(frames.size() - 2, 0, -1):
				var original := result.get_frame_texture(animation_name, index)
				var duration := result.get_frame_duration(animation_name, index)
				result.add_frame(animation_name, original, duration)
	sprite_frames = result
	if not result.get_animation_names().is_empty():
		play(result.get_animation_names()[0])
