# DevStat — Offline Desktop App (build & run)

The **online** version runs on Cloud Run (data is exam-synthetic only; sign-in,
£25/yr billing and analytics live in the hosted backend).

The **offline desktop** version runs the analysis engine **100% locally** on
127.0.0.1. Your data never leaves the machine. Licensing is enforced with
**Option A — occasional phone-home** (see below).

## Architecture

```
Electron (frontend/electron/main.js)
   ├─ spawns the local engine:  python backend/run_local.py  → http://127.0.0.1:8210
   ├─ loads http://127.0.0.1:8210 in a native window
   └─ licence gate (frontend/electron/licence.js) — Option A
```

- `backend/run_local.py` — uvicorn launcher (`app.main:create_app`, `cloud_run:false`).
  No Cloud Run, Firebase or Stripe needed to compute; the engine is pure Python
  (scipy/statsmodels/lifelines/sklearn).
- `frontend/electron/main.js` — spawns the engine, waits for `/api/health`, loads
  localhost, kills the engine on quit.
- `frontend/electron/licence.js` + `preload.js` — offline licence cache + secure IPC.

## Licence enforcement (Option A — phone-home)

> Plain-English: the engine runs offline, but the **licence** checks the internet
> occasionally — once to *activate*, then roughly every 30 days. Between checks
> it works fully offline; if the sub lapses (or no check in a long time) it
> re-locks to a 3-analysis trial + "renew" prompt. True annual, revocable.

Flow:
1. First launch → **Activate**: opens the hosted `/auth` in your browser; sign in
   (Firebase) → the app phones `/api/license/status` and caches the licence.
2. Cache: `%USERPROFILE%\.devstat\licence.json` holding `{ licensed, licensed_until,
   plan, sessionToken, usageCount }`.
3. On every launch (`licence:state`) it re-checks online; if offline it trusts the
   cache until `licensed_until` (grace). `licence:consume` decrements the local
   3-free-trial; `licence:activate` opens the hosted pay/login.
4. The cached token is only as strong as the server's own session validation — a
   client can't forge a licence without the server secret, and a lapsed sub flips
   `licensed` back to false at the next phone-home.

## Run in dev

```powershell
# 1) start the engine
cd backend; python run_local.py           # → http://127.0.0.1:8210
# 2) run the desktop shell (another terminal)
cd frontend; npm run desktop:start         # electron .  (loads localhost)
```
(If the installer/desktop build is not present, `npm run desktop:build` first.)

## Package for Windows

1. **Bundle the engine** with PyInstaller:
   ```
   cd backend
   pyinstaller devstat_engine.spec --noconfirm
   ```
   (produces `dist/DevStatEngine/DevStatEngine.exe`).
2. **Build the Electron app** pointing at that exe:
   ```
   cd frontend
   $env:DEVSTAT_ENGINE_EXE = "<abs path to DevStatEngine.exe>"
   npm run desktop:build        # electron-builder → release/
   ```
   In main.js, `engineCmd()` uses `DEVSTAT_ENGINE_EXE` if set, else runs
   `python backend/run_local.py` for dev.

## Notes / limitations
- Verified: the local engine boots (`/api/health` → `cloud_run:false`) and
  computes offline (e.g. `power` t-test → n = 63.77; upload parses 120×28).
- Session state (upload→analyse) is per-uid / per-session; the Electron shell holds
  a consistent session, so it behaves like the online app. Raw stateless HTTP
  probes without a cookie won't see one request's upload in another — that is a
  probe artifact, not a product defect.
- A fully offline program can never be 100% copy-protected; this model makes
  paying the only sensible path and supports revocation on lapse.
