# DevStat — Session Context Note

> Onboarding note so any future session can come up to speed fast. Last updated: 2026-08-23.
> Full docs: SETUP.md, README.md, devphilosophy.md, VERIFICATION.md, TEST_CHECKLIST.md.

## What it is
DevStat — medical statistics software (SPSS-like). v1.2.0. Backend FastAPI on port 8150,
React SPA frontend. Analysis engine is pure-Python (no R runtime needed).

## Tech stack
- Backend: Python 3.11+, FastAPI, uvicorn, pandas, numpy, scipy, statsmodels, lifelines,
  scikit-learn, plotly, matplotlib, seaborn, pyreadstat, weasyprint.
- Frontend: React 19, AntD 5, ag-grid, plotly.js (react-plotly), react-router, Vite, TypeScript.

## Architecture map
- backend/app/main.py — app factory, CORS, per-cookie session isolation, health, static SPA.
- backend/app/routers/{data,analysis,charts,output,suggest,transform,wizard,r_status,syntax,eligibility,project,ai} — REST endpoints under /api.
- backend/r/engine.py — AnalysisEngine registry (26 analyses) → app/services/*.py.
- backend/app/services/{descriptive,compare,regression,survival,diagnostic,factor_analysis,cluster,power}.
- backend/app/state.py — in-memory session dataset + undo/redo stack.
- frontend/src/pages/* — one page per menu section (Data, Variable, Transform, Descriptive,
  Compare, Regression, Survival, Diagnostic, Factor, Cluster, Power, Graphs, Output, Syntax,
  Wizard, AI).

## Features
Data import (csv/xlsx/xls/sav), data grid, variable view (SPSS metadata), transforms,
descriptive stats, group comparisons, regression, survival, diagnostic tests, factor/reliability,
cluster, power analysis, charts, output/export, SPSS-style syntax, test wizard, AI assistant (optional).

## Testing & verification
- VERIFICATION.md — golden dataset (golden_data.csv) + reference R values for survival,
  regression, correlation, ANOVA.
- TEST_CHECKLIST.md — 95 manual end-to-end tests.
- backend/tests/* — pytest; frontend has vitest + playwright.

## Current state (2026-08-23)
- Startup: DEGRADED. Missing Python package: `pyreadstat`. Run `pip install -r requirements.txt`.
- Engine: full "py" (pure-Python) — 26 analyses loaded.
- Last observed log activity: 2026-07-21 23:35 (backend/logs/devstat.log).
- Not currently a git repo in this folder.

## Conventions I must follow here
- Pre-edit: create `.bak.{YYYY-MM-DD_HHmmss}` in `_backups/` BEFORE editing any file.
- Never use eval()/exec() on user input; log every exception (no silent catch{}).
- Contract-test data shapes between backend & frontend.
- "If it isn't rendered, it doesn't exist" — always verify Output tab rendering.
- Known cleanup: backend/app/main.py docstring still says "Vue.js SPA" (stale — it's React).
