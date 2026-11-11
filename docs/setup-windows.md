# Windows Development Setup

## Supported baseline

- Windows 10/11 64-bit with current security updates.
- Git.
- Node.js 20, 22, or 24 LTS.
- pnpm 10 via Corepack or a trusted local installation.
- Python 3.11 64-bit.

The target machine may also contain newer Node or Python versions, but Sprint 0 validation uses the supported baseline above. ComfyUI and model downloads are not required.

## Clone and environment

```powershell
git clone <repository-url> ai-sprite-studio
cd ai-sprite-studio
Copy-Item .env.example .env.local
```

Review `.env.local`. Relative workspace and database paths are suitable for development. Keep this file out of Git.

## Frontend

```powershell
corepack enable
corepack prepare pnpm@10.11.0 --activate
pnpm install
pnpm dev:web
```

The frontend runs at `http://127.0.0.1:5173` and proxies `/api` to the local backend.

## Backend

```powershell
cd apps/api
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Check `http://127.0.0.1:8000/api/v1/health` or the interactive API page at `http://127.0.0.1:8000/api/docs`.

If PowerShell blocks virtual-environment activation, run the interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Optional ComfyUI setting

Sprint 0 records `AI_SPRITE_COMFYUI_HTTP_URL` and `AI_SPRITE_COMFYUI_WS_URL`, but does not connect, submit workflows, or download models. ComfyUI support starts behind a mockable adapter in later sprints.

## Troubleshooting

- Use `node --version`, `pnpm --version`, and `py -3.11 --version` to verify tools.
- Install Python 3.11 alongside newer Python versions and always create the virtual environment with `py -3.11`.
- Keep Windows fully updated if a terminal reports Control-flow Enforcement Technology (CET) compatibility errors.
- Ensure ports 5173 and 8000 are free and do not expose them through firewall rules.

