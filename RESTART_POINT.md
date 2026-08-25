# DevStat — Restart Point
> Updated 2026-08-25 (session 2). Read this first in a new session. HARD RULE: **never guess any name/option/column/value — read the real code/data and QA-verify** (see `AGENTS.md` #0).

## WHAT THE APP IS
FastAPI backend (pure-Python stats engine: scipy/statsmodels/lifelines/sklearn) + React SPA
(Vite build → `backend/static`). Containerised in `backend/Dockerfile`. Deployed to Cloud Run.

## LIVE STATE — **DEPLOYED & VERIFIED (revision `devstat-statistics-app-00101-mkr`)**
Everything below is live and tested, including Firestore (container), LIVE Stripe, admin waiver, and the "learn as you do" right-pane with all three datasets.
- Cloud Run `devstat-statistics-app`, project `devstat-499409`, region `europe-west1`.
- Deploy: `cd backend && gcloud builds submit . --tag gcr.io/devstat-499409/devstat --project devstat-499409 --timeout=1800s`
  then `gcloud run deploy devstat-statistics-app --project devstat-499409 --region europe-west1 --image gcr.io/devstat-499409/devstat --platform managed --allow-unauthenticated --min-instances 1 --max-instances 1 --memory 512Mi --cpu 1 --timeout 300 --env-vars-file devstat_envvars.json`
- Frontend: `cd frontend && npm run build` (writes into `backend/static/`), then deploy the backend image.
- `.dockerignore` excludes `devstat-firebase-sa.json`, `devstat_envvars.json`, `*.bak*`, `_archive`.

## FIREBASE — CROSS-PROJECT (FIXED THIS SESSION)
- Auth + Firestore live in project **`devstat-fb-789999`**; the app runs on GCP **`devstat-499409`** (has NO Firestore). SA = `devstat-admin@devstat-fb-789999.iam.gserviceaccount.com`.
- **Root cause of all Firestore failures:** `firebase_admin.get_app().credential.get_credential()` resolves to the RUNTIME project (no Firestore) → `400 Invalid database id (default)`. Pinning `gcf.Client(project=B)` did **NOT** fix it.
- **Working fix (in `app/services/firebase_store.py`):** call the **Firestore REST API** pinned to `devstat-fb-789999` (`_firebase_project`), with an OAuth2 Bearer from the SA. Helpers: `_sa_info`, `_rest_bearer`, `_doc_url`, `_rest_call`, `_fields_to_dict`, `_dict_to_fields`, `_doc_get`, `_doc_patch`, `find_by_customer` (runQuery). `_init()` inits firebase_admin for AUTH only (`_firestore=None`). Verified: webhook → Firestore write **persists on the container**.
- Note: pubmed works because its app+Firestore share one project; DevStat does not.

## STRIPE — LIVE (FLIPPED THIS SESSION)
- **LIVE** key `rk_live_...` (shared account with pubmed, from `pubmed-search\.env`). NOT test.
- **LIVE prices created** (12: 4 tiers × sub/teach/qb) — `STRIPE_PRICES` in `app/services/pricing.py` now holds the live ids (high sub `price_1U89c1RgNTPfknVQFEvcvgsF`, high teach `price_1U89c1RgNTPfknVQoFZBzkSW`, high qb `price_1U89c1RgNTPfknVQzRKR042B`, etc.).
- **LIVE webhook** created → `https://devstat-statistics-app-991466352708.europe-west1.run.app/api/license/webhook`, secret `whsec_REDACTED` (see `backend/.env`). Enabled: checkout.session.completed, customer.subscription.created/updated/deleted.
- Env vars now live in BOTH `backend/.env` and `devstat_envvars.json`: `DEVSTAT_STRIPE_SECRET_KEY`, `DEVSTAT_STRIPE_PRICE_ID` (high sub), `DEVSTAT_TEACHING_PRICE_ID` (high teach), `DEVSTAT_QB_PRICE_ID` (high qb), `DEVSTAT_STRIPE_WEBHOOK_SECRET`.
- `checkout.stripe.com` (LIVE) confirmed for a real checkout.
- **REMINDER (dr-dev):** Managed Payments is ON by default for this Stripe account. **Every new Stripe Product/Price MUST have a product `tax_code` set** (digital goods/services) or `checkout.Session.create` returns `400 "product tax code is missing"` → the app returns 502 → "Upgrade not working". Set tax codes manually in the Stripe dashboard whenever you create a new product/price; no code override is in place (we removed `managed_payments[enabled]=false`).

## ADMIN / OWNER WAIVER (ADDED THIS SESSION)
- `ADMIN_EMAILS = ['psdevraj@gmail.com']` (env `DEVSTAT_ADMIN_EMAILS`, `app/config.py`).
- New shared `firebase_store.is_admin(uid)` (email allowlist, memoized). Honoured in EVERY gate:
  `licence_live`, `questionbank._owns`+`/list` (owned+licensed), `teaching._owns`+`/scenarios` (owned+licensed).
- Effect: owner auto-owns all £5 question banks + £1 teaching cases and is always licensed — never asked to pay. (Without this, auth set `role:admin` but ownership maps were empty → owner still saw "Buy".)

## RIGHT PANE — "LEARN AS YOU DO" (REBUILT THIS SESSION)
- Inline `<aside>` (400px) with a sticky pane header ("Learn as you do · Do the task in the app, then check.") + close. Layout is `height:100vh; overflow:hidden` + inner `overflowY:auto` so the two panes scroll independently (fixed a "data disappears when scrolling" bug; was `minHeight:100vh`).
- **All three datasets are one-at-a-time exercises** (task + real menu path + variables + Check→"You should see" real answer), NOT multiple-choice:
  - **Practice dataset** (`learnExercises.json`): 112 exercises, first **10 free**, then £25/yr (honest wording — no misleading "free").
  - **Survival** (`scenario2_perioperative.csv`): 100 exercises, £5.
  - **QoL** (`scenario3_radiotherapy.csv`): 100 exercises, £5.
  - Both paid datasets live in `frontend/src/data/learnByDataset.json` keyed by the **bank id** (`survival-qb`/`qol-qb`). (Bug fixed: keys were `survival`/`qol` → nothing opened.)
- Every number + menu option was produced by running the real engine (`r/engine.py _build_registry` + `run_analysis`) — nothing guessed. Real registry names/params there.
- Viewer: `Question N of N`, topic+number, task, `📍 <real menu path>` chip, `vars:` chip, `Check` (reveals real answer), Prev/Next + jump + Back to datasets. 10-free counter persists in `localStorage` (`devstat_practice_used`).
- Banners: **Exam-mode warning banner REMOVED**; **Cloud Run "Live / confidential mode" banner KEPT** (the other was kept; I initially removed both — only the exam warning was unwanted).

## KEY BACKEND DETAILS (unchanged)
- `state.py` contextvars (uid/device/client_ip/mode/teaching); free tier = 5 analyses + 5 charts per machine+IP, fail-closed; `licence_live` cached; `r/dispatcher.py run_analysis` + `charts.py` gate.
- Teaching mode `/teaching`: 3 scenarios (1 free, 2 paid £1 buy-after-subscription). Question banks: 2 (£5 buy-after-subscription).
- Session guard (`session_guard.py`): max 3 devices, HMAC-signed tokens.

## NEXT / PENDING
1. Optional hardening: full device-registry check on `/api/analysis` instead of HMAC-only `peek_uid`.
2. Live-test a real £1/£5 purchase + the free paywall with an actual card (surface checkout confirmed LIVE already; Firestore write verified).

## CLOUD BUILD ISSUE — INVESTIGATE NEXT VISIT
**Status: live app (`devstat-statistics-app`, europe-west1) is fine and untouched.** But a fresh build+deploy is currently failing.
- Symptom: `gcloud builds submit .` fails at the Docker step with `unable to evaluate symlinks in Dockerfile path: lstat /workspace/Dockerfile: no such file or directory`.
- Deploy process that SHOULD work (from this doc): `cd frontend && npm run build` (→ `backend/static`) then `cd backend && gcloud builds submit . --tag gcr.io/devstat-499409/devstat --project devstat-499409` then `gcloud run deploy devstat-statistics-app --project devstat-499409 --region europe-west1 --image gcr.io/devstat-499409/devstat --min-instances 1 --max-instances 1 --memory 512Mi --cpu 1 --timeout 300 --env-vars-file devstat_envvars.json`.
- Likely causes to check: (a) build context not picking up `backend/Dockerfile` (try submitting with an explicit absolute source path; avoid `cmd /c` wrappers which change CWD); (b) the OLD **root** `cloudbuild.yaml` + **root multi-stage** `Dockerfile` (service `devstat`, region `us-central1`) were removed in the Desktop Edition push — verify nothing still references them; (c) **default gcloud project is `pubmed-search-504823`** — always pass `--project devstat-499409`.
- Reconcile: backend/Dockerfile expects `static` pre-built; the root multi-stage Dockerfile built the frontend inside Docker. Decide which is canonical for the live app and keep the files + workflow consistent.

## SESSION 2026-08-25 — DESKTOP EDITION (Option #2) + DEPLOYS — READ NEXT SESSION
### Architecture now (Option #2: account ONLINE, analysis OFFLINE)
- **Desktop = same online account.** The desktop SPA sends `login/register/subscription` to the LIVE Cloud Run app (cloud origin), so Firebase/Stripe creds stay OUT of the desktop build.
- **Login flow (desktop):** header "Sign in" → `window.open(<cloud>/auth?desktop=1)` popup → user logs in on the online app → AuthPage `postMessage({type:'devstat-login', session})` to the opener → desktop stores session (`storeDevStatSession`) + syncs local licence → reloads. No cross-origin API calls from the desktop.
- **Analysis (desktop):** runs on the local engine, token-validated (`peek_uid` → uid). Gate uses a LOCAL store `app/services/desktop_licence.py` (5 analyses + 5 charts per uid+machine; licensed-until synced from cloud). No teaching/question-bank on desktop (`main.py` mounts teaching/license/questionbank ONLY when `not OFFLINE`).
- **Close guard (desktop):** `beforeunload` confirm if unsaved output; `pagehide` → `navigator.sendBeacon('/api/desktop/shutdown')` → engine `os._exit(0)` → launcher (waiting on engine) exits. No Ctrl+C needed.

### Key files changed
- Frontend: `src/api/client.ts` (`accountApi` = ACCOUNT_API_URL = `https://devstat-statistics-app-991466352708.europe-west1.run.app`, `attachInterceptors` for both instances, `desktopLicenceApi`), `src/api/authApi.ts` (uses `accountApi`), `src/App.tsx` (desktop login popup + postMessage listener + close guard + licence sync), `src/pages/AuthPage.tsx` (postMessage hand-off when `?desktop=1` + `window.opener`).
- Backend: `app/services/desktop_licence.py` (new, local store), `app/routers/desktop.py` (new: `/api/desktop/licence-status`, `/sync-licence`, `/shutdown`), `app/main.py` (mount desktop router; mount license/teaching/questionbank only when `not OFFLINE`), `r/dispatcher.py` + `app/routers/charts.py` (OFFLINE gate uses `desktop_licence`), `backend/devstat_engine.spec` (datas include `("static","static")`).
- Launcher: `desktop/launcher.py` — frees port 8210 before starting (kills stale engine), sets `DEVSTAT_AUTH_SECRET` (cloud value) so the local engine validates the cloud login token (LOW RISK: local-only paywall bypass; data never leaves machine).

### Online app — DEPLOYED & HEALTHY
- Live revision `devstat-statistics-app-00103-4f2` runs the NEW image `gcr.io/devstat-499409/devstat@sha256:88f7c77165779a293c2ebd0899f2e0f319c9e64d1a1c879d4e4ad56e7c6e4d95`.
- Health on `https://devstat-statistics-app-991466352708.europe-west1.run.app/api/health` = 200, `desktop:false`, `cloud_run:true`. **Online app unchanged/unbroken** (all desktop changes are `isDesktop`/`OFFLINE`-gated).
- Deployed with `gcloud run deploy ... --image <digest> --min-instances 1 --max-instances 1 --memory 512Mi --cpu 1 --timeout 300` (no env flags → existing env preserved).

### CLOUD BUILD — NOW FIXED (read this)
- The earlier `/workspace/Dockerfile: no such file` was caused by (a) running via `cmd /c` (wrong CWD → context lacked `backend/Dockerfile`) and (b) an **815 MB build context** (PyInstaller `dist/` + `build/` not excluded; project lives in OneDrive which locks files).
- Fix applied: `backend/.gcloudignore` + `.dockerignore` now exclude `dist/`, `build/`, `*.log`, pid files. Builds now SUCCEED when run DIRECTLY (not `cmd /c`): `cd backend && gcloud builds submit . --project devstat-499409 --tag gcr.io/devstat-499409/devstat:latest`.
- **PyInstaller rebuild for the desktop zip must use `--distpath`/`--workpath` OUTSIDE OneDrive** (temp), else PyInstaller's clean of the old `dist/DevStatEngine` hits `PermissionError: Access is denied` (OneDrive holds the file handles). Working: `python -m PyInstaller devstat_engine.spec --noconfirm --log-level WARN --distpath C:\Users\DELL73~1\AppData\Local\Temp\opencode\dsdist --workpath C:\Users\DELL73~1\AppData\Local\Temp\opencode\dsbuild`. This produced `dsdist\DevStatEngine\DevStatEngine.exe` (78 MB, written 19:30).
- **Zip packaging trap:** `desktop/package.py` writing the zip straight into the OneDrive `downloads/` folder → OneDrive truncates/locks the in-progress zip → CORRUPT zip ("End of Central Directory not found"). FIX: run `package.py --out <TEMP non-OneDrive dir>` to produce a VALID zip, THEN copy the single zip into `hostinger_deployment\downloads\`. (The last run to `C:\Users\DELL73~1\AppData\Local\Temp\opencode\pkgout` needs verification — check for a valid `DevStat-Desktop-win.zip` there before copying.)

### Progress helper scripts (new, global)
- `OneDrive\opencode-config\scripts\progress.ps1` (run a job in background, write progress JSON to `~/.opencode/progress/<name>.json` every 5s) + `watch-progress.ps1` (live bar). Usage: `powershell -File progress.ps1 -Name X -Run "cmd" -WorkDir D -EstimateSecs N`.

### Global AGENTS.md (OneDrive opencode-config) — added
- **#0 HARD RULE:** check for + USE skills and MCPs before ANY action; never bypass (non-negotiable).
- **Model escalation:** default coder `deepseek-v4-flash`; if 3 attempts at the same problem fail → switch to `deepseek-v4-pro`, revert to flash when solved; v4-flash paired with experimental v4 vision.

### PENDING / NEXT
1. ✅ DONE (session 2 continuation): Windows zip rebuilt + shipped. With OneDrive flicked OFF, all PyInstaller builds run **in-place** (no distpath/workpath redirect needed); engine `dist\DevStatEngine\DevStatEngine.exe` (78 MB) rebuilt clean (exit 0; was failing on OneDrive handle locks), launcher `desktop\dist\DevStatDesktopLauncher.exe` (8.2 MB) built, engine smoke-tested (`/api/health` ok). Packaged to temp then copied to `...\Systemic Therapy Explorer\hostinger_deployment\downloads\DevStat-Desktop-win.zip` (257.3 MB, 6323 entries, valid central dir). Corrupt 173 MB zip + stale unpacked folder archived to temp `deploy_ckpt`. Site link `./downloads/DevStat-Desktop-win.zip` is the only reference.
2. ✅ DONE: macOS intentionally dropped (user: too complex/tedious; no false promises). macOS removed from `STATS_MANUAL.html`, `desktop-edition.html` (card/tile/CTA/JS), `index.html`, `learn-as-you-do.html`. Might re-add if ever built on a Mac.
3. ✅ DONE: desktop.py double-prefix bug fixed (`APIRouter(prefix="")`) — was `/api/desktop/api/desktop/...`; `/api/desktop/shutdown` returned 405 via SPA catch-all and `licence-status` silently returned HTML. Now correct. Console hidden (`CREATE_NO_WINDOW`) in launcher.py. Login popup opens full (`openDesktopLogin` uses full screen size).
4. ✅ DONE: transient "Backend is not running" on first launch — caused by `main.py` loading the analysis engine in a background thread, so the first `/api/health` could exceed the frontend's 3s timeout. Fixed in `App.tsx`: health timeout 6000ms + tolerate 2 consecutive failures before flagging down; banner softened to "Starting the statistics engine…" (warning) with wait/F5/reopen guidance; notes added to `STATS_MANUAL.html` and `desktop-edition.html` FAQ. Final zip rebuilt (258 MB, 6351 entries) + shipped; warm-up banner verified present in bundled JS.
5. Commit + push the current source changes to GitHub ONLY after the regenerated desktop zip is verified (user: "bypass GitHub — build directly, push only when all good, same as pubmed").
6. Optional: CORS_ORIGINS on Cloud Run — NOT needed for the popup-login flow (all account calls are same-origin in the cloud popup). The earlier `--update-env-vars` attempt fails on gcloud dict-arg escaping; use a flags-file if ever needed.


