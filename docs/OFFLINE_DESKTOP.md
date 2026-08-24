# DevStat — Offline Desktop App (build & download)

DevStat comes in two flavours:

| Version | Where it runs | Data | Licence |
|---|---|---|---|
| **Online** (recommended for exam practice) | cloud (`https://devstat-statistics-app-991466352708.europe-west1.run.app`) | synthetic/exam data only | free trial + £25/yr |
| **Offline desktop** | 100% on your machine (`127.0.0.1:8210`) | stays local — safe for real data | free trial + £25/yr |

The **offline** build runs the full analysis engine locally so your data never
leaves the machine. Licensing is enforced with **Option A — occasional
phone-home**: it needs the internet once to activate, then re-checks roughly
every 30 days; it works fully offline in between and re-locks (to the 3-free-trial
+ "renew" prompt) if the subscription lapses.

## Download / build

The downloadable installer is produced by `build_offline.ps1` (Python + Node +
Electron required). Build once on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File build_offline.ps1
```

It 1) `npm run build`s the frontend, 2) bundles the Python engine with PyInstaller
(`backend/devstat_engine.spec`), and 3) builds the Electron app (electron-builder),
leaving the installer in `frontend/release/`.

For releases, the GitHub Actions `release.yml` workflow publishes the practice
dataset; the desktop installer is built locally with the script above (a CI
Windows build job is a planned follow-up).

## Source layout (offline pieces)
- `backend/run_local.py` — launches the local engine (`app.main:create_app`, `cloud_run:false`).
- `backend/devstat_engine.spec` — PyInstaller spec for the engine.
- `frontend/electron/main.js` — spawns the engine, loads `http://127.0.0.1:8210`, kills it on quit.
- `frontend/electron/licence.js` — offline licence cache + Option A phone-home gate.
- `frontend/electron/preload.js` — secure IPC (`devstatLicence.state/consume/activate`).
- `frontend/electron/README_offline.md` — more detail on the licensing flow.

## Licence (Option A)
Activation: on first launch, open `/auth` (hosted) → sign in (Firebase) → the app
phones `/api/license/status` and caches the licence in `~/.devstat/licence.json`
(`{ licensed, licensed_until, plan, sessionToken, usageCount }`).
Between checks it trusts the cache until `licensed_until`; a lapsed sub flips
`licensed` back to false at the next phone-home.
