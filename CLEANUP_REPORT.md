# DevStat Cleanup Report

## What Was Removed for the Public Release

### AI / API-Key Dependent Features

| Item | Location | Action |
|------|----------|--------|
| AI Assistant module | `backend/app/ai/` (parser.py, synthesizer.py, router.py, scanner.py, charts.py, models.py, prompts/) | **Removed entirely** |
| AI route registration | `backend/app/main.py` | Removed `ai` from router imports and `app.include_router(ai.router)` |
| Frontend AI page | `frontend/src/pages/AiPage.tsx` | Removed route and menu item; frontend rebuilt |
| .env with API key | `backend/.env` | **Excluded from source_clean** |

### Secrets Advisory

**⚠️ An archived `.env` file containing a real DeepSeek API key was found at:**
- `_archive/old_root/devstat-ai/.env`

This archive is **not included** in the release source, but if you have ever committed to Git with this file present, the API key may be in your Git history. **You should rotate (regenerate) the DeepSeek API key** before publishing the repository publicly.

If you plan to push this project to GitHub, run the following to check for secrets in your Git history:

```bash
# If you have Git history with the old repo
git log --all --diff-filter=A -- "*.env"
```

Consider using [git-filter-repo](https://github.com/newren/git-filter-repo) to remove secrets from history if any exist.

### Files and Directories Excluded

| Category | Items Excluded |
|----------|---------------|
| **Caches** | All `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `frontend/node_modules/` |
| **Logs** | `backend/logs/`, `devstat-logs-*.json`, `launch_devstat.log` |
| **Tests** | `backend/tests/`, `frontend/tests/`, `backend/test_*.py`, `backend/r/tests/` |
| **Archived code** | `_archive/` (12 subdirectories of old code, containing real API key) |
| **R artifacts** | `backend/cache/`, `backend/index/`, `backend/binary/`, `backend/renv/`, `backend/renv.lock` |
| **Config files** | `backend/.Rprofile`, `backend/projects` |
| **Developer docs** | `devphilosophy.md`, `repair1.md`, `softwaretestplan.md`, `VERIFICATION.md` |
| **Build tools** | `python-manager-26.2.msix` (14 MB) |
| **Frontend source** | `frontend/src/` (only pre-built `backend/static/` included) |

### What Remains in source_clean/

The cleaned release copy contains only:

- `launcher_gui.py` (modified: uses `sys.executable` instead of `py -3.14`)
- `launch_gui.bat`, `launch_gui.vbs`, `stop_devstat.bat`, `launch_devstat.bat`
- `requirements.txt`
- `sample_100.csv`, `sample_medical_data.csv`
- `.env.example` (placeholder only, no real keys)
- `.gitignore`
- `backend/app/` (without `ai/` subdirectory, without `__pycache__/`)
- `backend/r/` (engine.py, dispatcher.py — pure Python analysis engine)
- `backend/static/` (pre-built frontend bundle)

### Manual Review Items

1. **`backend/.env`** — contains a real DeepSeek API key. Confirm you do NOT want this in the public repo. The source_clean copy excludes it, but double-check before pushing.
2. **`_archive/old_root/devstat-ai/.env`** — contains a real API key. This directory is excluded from the release, but if you ever commit it, the key enters your Git history.
3. **R-related directories** (`backend/cache/`, `backend/index/`, `backend/binary/`) — these are old build artifacts from the R engine days. Confirmed safe to exclude.
4. **Static frontend** — the pre-built bundle in `backend/static/` was built after removing the AI Assistant page. Verify no AI references remain in the UI.
