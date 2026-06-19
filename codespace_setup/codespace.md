# DevStat — GitHub Codespaces Reference

## Overview

DevStat is configured to run instantly in GitHub Codespaces — users click a badge
and DevStat opens in their browser. No installation, no manual steps.

## Repository

- **URL:** https://github.com/psdevraj-creator/DevStat-Statistics-app
- **Branch:** `main`

## Files Created

### `.devcontainer/devcontainer.json`
Defines the Codespaces container:
- **Base image:** `mcr.microsoft.com/devcontainers/python:3.11`
- **Features:** Node.js 20 (inactive but available)
- **`postCreateCommand`:** Runs `.devcontainer/setup.sh` on first create
- **`postStartCommand`:** Runs `codespace_setup/start.sh` every start (incl. restart)
- **`forwardPorts`:** 8150 auto-forwarded with browser auto-open
- **VS Code extensions:** Python, Pylance, ESLint, Prettier

### `.devcontainer/setup.sh`
Runs once on container creation:
1. Creates Python venv at `backend/venv/`
2. `pip install -r requirements.txt`
3. Prints completion message

### `codespace_setup/start.sh`
Runs every container start:
1. Activates venv
2. Starts uvicorn on `0.0.0.0:8150`

### `codespace_setup/README.md`
User-facing guide explaining how to open in Codespaces and use the app.

### `codespace_setup/codespace.md`
This file — technical reference for the developer.

## User Experience

1. Click **"Open in GitHub Codespaces"** badge on README
2. Wait ~15s (prebuilt) or ~2min (first time)
3. DevStat loads automatically in browser — ready to use

## Prebuilds (Recommended)

**To enable:** Repo → Settings → Codespaces → Set up prebuild → `main` branch
Prebuilds cache the container so users skip the build step entirely (~15s vs ~2min).

## Git Commits

| Hash | Message |
|------|---------|
| `a01eebc` | Initial commit with Codespaces support |
| `9dc72e8` | Auto-start server on container start |

## Important Notes

- **R is skipped** — the Python-only engine runs fully without R
- **Frontend is pre-built** — no `frontend/` source in this repo; static files are
  in `backend/static/` and committed directly
- **`source_clean/`** is the GitHub source root. The parent `C:\DevStat\` is the
  development workspace and has its own gitignore (not pushed to GitHub).
- **CORS** is already configured in `backend/app/main.py` to allow Codespaces URLs.
- **Data privacy** — all data stays in the Codespace container; no external calls.

## OneDrive Copy

`codespace_setup/` is mirrored at:
`C:\Users\dpsri\OneDrive\Desktop\DevStat-Codespace-Setup\`
