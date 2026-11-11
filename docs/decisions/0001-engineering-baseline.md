# ADR 0001: Engineering baseline

- Status: Accepted
- Date: 2026-11-11

## Context

The project needs a Windows-friendly offline-first foundation that can grow into project storage, pixel editing, animation, and replaceable local AI providers.

## Decision

Use a pnpm workspace with a React/TypeScript/Vite/Tailwind frontend and a Python 3.11 FastAPI backend. Keep ComfyUI outside the application process and introduce it only through an adapter in a later sprint. Start in a browser on loopback; defer Tauri packaging.

## Consequences

- Frontend and backend can be tested without a GPU or model downloads.
- Local development uses two processes during early sprints.
- Python 3.11 is required even when a newer system Python is installed.
- Desktop packaging and AI dependency management remain explicit future decisions.

