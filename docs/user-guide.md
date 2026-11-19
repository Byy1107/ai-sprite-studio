# V1 Quick User Guide (Windows)

## First export without an AI model

1. Follow `docs/setup-windows.md` and start both the API and web app. Leave `AI_SPRITE_AI_PROVIDER=fake`; ComfyUI and a checkpoint are not needed.
2. Open `http://127.0.0.1:5173`, create a project on the dashboard, and open it.
3. In **Asset library**, enter an asset name, choose Character, Item, Environment, or Tileset and a style, select a PNG (up to 16 MB), then click **Import PNG**.
4. Select the imported asset tile. In **Export**, leave Scale at 1×, select its published Version, and click **Export PNG**.
5. Use the new **PNG** link in export history to download the file. Each export has a unique directory; an older export is not replaced.

For a spritesheet, use a **Character** asset: create an animation clip, add at least one frame pinned to a published version, select that clip in **Export**, and click **Export sheet + JSON**. Download both PNG and JSON. The optional Godot 4 target has an importer example at `examples/godot4/`.

## Editing and safety

- The pixel editor makes a local browser draft; use its publish action to create an immutable asset version. An unpublished draft is not included in project ZIP backups.
- Use **Check files** on a project card before backing up. Missing files are reported but never reconstructed automatically.
- Use **Download backup** to capture a project. Restore only into a fresh workspace and SQLite database; existing projects are never overwritten. Keep a separate copy of the original ZIP until the restored project opens and exports correctly.
- Deleted project folders remain under workspace `.trash` and are not purged automatically. **Clear cache** removes only disposable, unreferenced project-cache files after confirmation.
- Generated candidates do not replace an active version until accepted. The fake provider is deterministic test data, not an AI model; real generation needs a separately configured ComfyUI and licensed compatible checkpoint.

## Optional local AI

Read the ComfyUI sections in `docs/setup-windows.md` before switching providers. First verify a baseline job with one candidate. LoRA, ControlNet, and IP-Adapter are optional and require compatible local models or nodes. A successful job alone does not prove visual quality or that LoRA weights affected pixels.
