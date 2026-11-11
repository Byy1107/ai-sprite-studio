# AI Sprite Studio Agent Guide

- Read `AI_SPRITE_STUDIO_MASTER_PLAN.md` and the active sprint document before changing code.
- Implement one sprint at a time and do not pull future-sprint features forward.
- Keep the domain independent from React, FastAPI routes, and ComfyUI workflow details.
- Preserve offline-first behavior. Never require cloud services or telemetry.
- Do not add model binaries, generated user assets, databases, or private environment files to Git.
- Update tests and documentation with behavior changes.
- Run the narrowest relevant checks first, followed by the workspace checks before completion.

