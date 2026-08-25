# DevStat — Setup Environment

## Prerequisites

- **Python**: 3.11+ installed on PATH
- **R**: 4.4+ installed (auto-detected — checks PATH, `C:\Program Files\R\R-*`, Windows registry)
- **Node.js**: 18+ for frontend development builds only

## Quick Start (one command)

### Windows
```
devstat.bat
```

### git-bash
```
./devstat.sh
```

Both launchers auto-detect R, install missing R packages, create a Python venv,
install Python deps, find a free port, and start the server.

## Manual Setup

### 1. Python environment
```bash
python -m venv venv
source venv/bin/activate          # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. R packages (with renv — reproducible)
```bash
cd backend
Rscript -e "if(!require(renv)) install.packages('renv', repos='https://cloud.r-project.org')"
Rscript -e "renv::restore()"
```

This restores the exact package versions from `backend/renv.lock`.

### 3. R packages (without renv — fallback)
```bash
Rscript backend/install_packages.R
```

### 4. Frontend build (once)
```bash
cd frontend
npm install
npx vite build
```

### 5. Start the server
```bash
cd backend
python3 -c "
import sys; sys.path.insert(0, '.')
import uvicorn
from app.main import create_app
app = create_app()
uvicorn.run(app, host='127.0.0.1', port=8150)
"
```

Open http://127.0.0.1:8150 in your browser.

## Startup Self-Check

On every server start, `backend/app/startup_check.py` runs and:

1. Checks all required **Python packages** import correctly
2. Checks R is available and all required **R packages** are installed
3. Reports status as `healthy` / `degraded` / `unhealthy`
4. Prints any missing packages to the console with fix instructions

If something is missing, the app still starts but reports degraded health.
Check `/api/health` and `/api/r-status` for details.

## R Dependency File

| File | Purpose |
|------|---------|
| `backend/renv.lock` | Exact package versions (78 packages) |
| `backend/install_packages.R` | Fallback installer if renv unavailable |

## Python Dependency File

| File | Purpose |
|------|---------|
| `requirements.txt` | Pinned Python dependencies (15 packages) |
