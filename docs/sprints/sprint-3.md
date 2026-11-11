# Sprint 3: Pixel Editor Manual Core

## Goal

Allow users to edit an active PNG at pixel precision, keep an optional local draft, and publish the result as a new immutable asset version.

## Completed scope

- Canvas 2D editor with nearest-neighbor scaling and transparent checkerboard.
- Pencil, eraser, picker, flood fill, line, rectangle, and pan tools.
- Zoom, optional pixel grid, editable color input, and palette swatches.
- Undo and redo across drawing operations.
- Local browser draft save and restore per asset.
- Active-version PNG content endpoint and manual version publishing API.
- Manual publishes preserve dimensions, update thumbnails, and create checksum-backed immutable versions.

## Deferred scope

- Layers, selection transforms, onion skin, and keyboard shortcut expansion remain later work.
- Animation timeline remains Sprint 8.
- AI-assisted editing and inpainting remain Sprint 7.

## Technical decisions

- The editor uses browser Canvas 2D without a third-party canvas framework.
- Pixel operations live in a pure reducer module independent of React and backend APIs.
- The source canvas remains at native asset resolution; CSS integer zoom and `image-rendering: pixelated` provide crisp display.
- Drafts use local browser storage and are explicitly separate from published asset versions.

## Migration and format changes

- No database migration is required.
- `GET /api/v1/asset-versions/{version_id}/content` serves immutable PNG content.
- `POST /api/v1/assets/{asset_id}/versions` publishes a dimension-preserving manual PNG version.

## Tests and validation

- Backend tests cover manual publishing, parent version metadata, PNG content retrieval, and dimension rejection.
- Frontend reducer tests cover coordinate conversion, drawing, fill, erasing, undo, and redo.
- Frontend component tests cover tool selection and grid control.
- Backend Ruff and mypy pass; all 11 backend tests pass.
- Frontend lint, typecheck, all 9 tests, and production build pass.

## Manual verification

Open a project and select an imported asset. Draw pixels with multiple tools, change zoom and grid, undo and redo, save a draft, reload, then publish. Confirm a new manual version appears without replacing older version files.

## Known issues

- Drafts are browser-local and are not portable with the project folder.
- Very large imported canvases are allowed by asset import but are not yet performance-profiled for editing.
- Tool previews are committed on pointer release; line and rectangle ghost previews are not shown yet.

## Risks and next recommendation

Keep the editor domain independent from AI provider details. Begin Sprint 4 only after pixel-perfect save behavior and full workspace checks pass.
