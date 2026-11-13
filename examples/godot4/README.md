# Godot 4 export sample

This minimal project reads the **Godot 4** spritesheet preset from AI Sprite Studio. It does not import `.tres` or alter the source export.

1. In AI Sprite Studio, make a character clip and choose **Godot 4** in the export panel. Export the sheet + JSON.
2. Download both files. Rename them `sprite.png` and `sprite.json`, then put them together in this project's `exports/` directory.
3. Open `project.godot` in Godot 4.4 and run the scene. `sprite_importer.gd` creates `SpriteFrames` from each JSON rectangle and plays the first animation.
4. Set the PNG import filter to **Nearest** or keep the scene's nearest texture filter. Check the visible frame order and timing against the editor timeline.

To repeat the automated Godot 4.4 check after copying the two files, run from this directory:

```powershell
godot --headless --editor --path . --quit
godot --headless --path . --script res://smoke_test.gd
```

The second command should print `Godot 4.4 import smoke passed` and exit with code 0. The script checks animation name, frame count, FPS, loop mode, first-frame duration, and spritesheet rectangle against the exported metadata.

Durations are converted from milliseconds to Godot's relative frame duration using the clip FPS. `once` does not loop, `loop` loops, and `ping_pong` duplicates interior frames in reverse. Frame events, pivot, and offset remain in the JSON but are **not applied automatically** to `AnimatedSprite2D`; handle these in your game logic. This sample supports schema v1 only.

If Godot is not installed, backend integration tests still verify the PNG and JSON contract, but they do not prove that the scene runs.
