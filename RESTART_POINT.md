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
