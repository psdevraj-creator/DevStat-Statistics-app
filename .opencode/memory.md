# DevStat — project memory

## HARD RULE #0 — NEVER GUESS ANYTHING. LOOK IT UP + QA-VERIFY.
For ANY instruction: don't invent analysis names, endpoint/router names, registry keys,
param field names, menu labels, column names, page routes, or result VALUES. Read the real
code/data first (registry = `r/engine.py` `_build_registry()`; params = service function
signatures; columns = the CSV; menus = the menu config in App.tsx). Run the real analysis via
`run_analysis(name, params)` on the dataset and copy TRUE numbers. A "You should see" line
must be a REAL computed result. Only reference menu options that exist. Guessing is the #1
cause of hours of rework.

Known real registry names (from r/engine.py): descriptive(columns,group_col),
frequencies(column), crosstab(row,col), explore(column,group_col), means(dependent,group,layers),
ttest(column1,column2,test_type=independent|paired), mannwhitney(column,group_var),
wilcoxon(column1,column2), anova(dv,between), anova_twoway(dv,factor1,factor2),
kruskal_wallis(column,group_var), chisquare(row,col), correlation(columns,method),
partial_correlation(columns,control,method), linear_regression(dv,predictors),
logistic_regression(dv,predictors), kaplan_meier(time_col,status_col,event_code,group_col),
cox_regression(time_col,status_col,covariates,event_code), cox_adjusted_survival(...),
diagnostic(test_col,gold_col,positive_code), roc_analysis(test_col,gold_col,positive_code),
factor_analysis(columns,n_factors,rotation), reliability(columns).

## What this app is
Paid medical-statistics web tool (Cloud Run `devstat-statistics-app`, GCP `devstat-499409`, region `europe-west1`).
Auth + Firestore live in a **separate Firebase project** `devstat-fb-789999` (SA `devstat-admin@devstat-fb-789999.iam.gserviceaccount.com`).
Stripe = shared account with pubmed (same `STRIPE_SECRET_KEY`), £25/yr licence + £1 teaching cases + £5 question banks, region-priced.

## HARD TRAPS (each cost hours — do NOT repeat)

### 1. Cross-project Firestore on Cloud Run = use the REST API, NOT the gcf client
- Symptom: every Firestore op fails `400 Invalid database id (default)`.
- Why: `firebase_admin.get_app().credential.get_credential()` resolves to the **runtime** GCP project (`devstat-499409`), which has **no Firestore**.
- **Pinning `gcf.Client(project=sa_project, ...)` does NOT fix it** — the REST/client still targets the runtime project. I tried it; `mark_qb_owned` STILL failed.
- **The fix that actually works: call Firestore's REST API directly, pinned to the SA's project.** Handlers:
  - `_sa_info()` → SA creds; `_firebase_project` = `"devstat-fb-789999"` (NOT the runtime project).
  - GET/PATCH `https://firestore.googleapis.com/v1/projects/{project}/databases/(default)/documents/{collection}/{doc}` with an OAuth2 Bearer token from the SA.
  - `find_by_customer` → runQuery POST. `_doc_get`/`_doc_patch` wrap the above.
- Proof: REST probe → `devstat-fb-789999` returns 404 (valid path), runtime project returns 403 "Firestore API not used". Webhook → Firestore write persists on container = works.
- Lesson: to find the "owning" Firestore project, probe `firestore.googleapis.com/v1/projects/{candidate}/databases` — the one that lists `(default)` is it.
- Pubmed works because its app + Firestore share ONE project. DevStat does not.

### 2. Admin/Owner is STILL asked to pay if only the auth role is admin
- Problem: the owner always saw "Buy £5" for the question banks (and "Pay" for £1 cases).
- Cause: `auth.py` sets `role:admin`/`licensed:true` for `ADMIN_EMAILS`, but the **resource-ownership** checks (`qb_owned`, `teaching_owned`) return empty for the admin → they don't OWN the paid content → Buy.
- Fix: ONE shared gate. `firebase_store.is_admin(uid)` (email in `ADMIN_EMAILS`, memoized). Honour it in EVERY gate:
  - `licence_live(uid)` → short-circuit True
  - `questionbank._owns(uid,qid)` + `/list` owned+licensed
  - `teaching._owns(uid,sid)` + `/scenarios` owned+licensed
  - (do the same for any future paid resource)
- `ADMIN_EMAILS` in `app/config.py` (env `DEVSTAT_ADMIN_EMAILS`, default `psdevraj@gmail.com`).

### 3. "Buy" goes to sandboxed Stripe = still TEST mode
- `rk_test_` = sandbox. `rk_live_` = real money.
- **Live flip runbook:**
  1. Read live key: `STRIPE_SECRET_KEY=rk_live_...` in `...\pubmed-search\.env`.
  2. Create LIVE prices (per region tier × product) via `stripe.Price.create(currency="gbp", unit_amount=<pence>, recurring={"interval":"year"} for sub, product_data={"name":...})`. sub=RECURRING (subscription mode), teach+qb=ONE-TIME (payment mode).
  3. Create LIVE webhook: `stripe.WebhookEndpoint.create(url="https://<service>.run.app/api/license/webhook", enabled_events=["checkout.session.completed","customer.subscription.created","customer.subscription.updated","customer.subscription.deleted"])` → capture `secret` (`whsec_...`).
  4. Update `app/services/pricing.py` `STRIPE_PRICES` map to the live ids; set the env vars (`DEVSTAT_STRIPE_SECRET_KEY`, `DEVSTAT_STRIPE_PRICE_ID`=high sub, `DEVSTAT_TEACHING_PRICE_ID`=high teach, `DEVSTAT_QB_PRICE_ID`=high qb, `DEVSTAT_STRIPE_WEBHOOK_SECRET`).
  5. Update BOTH `.env` and `devstat_envvars.json` (Python UTF-8, never PowerShell `-replace|Set-Content`).
  6. Rebuild + redeploy.

### 4. Do NOT reinvent content the user already has
- When a feature "needs questions/exercises," VERIFY the existing authoritative content FIRST. For DevStat the default practice questions already exist at `https://dpsoncology.com/medstat/learn-as-you-do.html` (112 exercises, 10 topics). I wrongly started building a *new* bank. Reuse/convert the existing content (I extracted it with a parser into `frontend/src/data/learnExercises.json`).
- Ask ONE crisp question (with options) if the intended data model is unclear, instead of assuming and building.

### 5. Understand the existing architecture BEFORE coding the feature
- The right pane was ALREADY `<QuestionBanks/>` inline in `App.tsx` (~line 684) that only loaded practice **data**. The design: default dataset → its practice questions; other datasets → their questions. Confirm the intended UX first.
- Vite frontend build outputs straight into `backend/static/` → the backend image serves the SPA. Deploy flow = `npm run build` (frontend) then `gcloud builds submit` + `gcloud run deploy` (backend).

### 6. Remove exactly the banners the user flags (not nearby ones)
- I removed BOTH the "Exam-mode warning" AND the "Live/confidential Cloud Run" banner, but only the exam warning was unwanted. Remove precisely what's asked; confirm scope when multiple similar banners exist.

## Current trusted state (after live flip, revision 00099)
- Firestore on container: WORKS (REST).
- Admin waiver: works (admin owns qb + teaching, always licensed).
- Live Stripe prices + webhook `whsec_REDACTED` created. Deployed live.
- Default pane = 112 practice exercises (10 free for guests, then sign in + subscribe); survival-qb + qol-qb = £5 MCQ banks (100 each).

## Verify checklist for a new deploy
1. Signed-in admin: `/api/questionbank/list` → both banks `owned:true`; open them → 100 questions render.
2. Webhook probe → Firestore write persists → `get_user(uid).qb_owned` set.
3. `/api/pricing` → region price shows; Stripe checkout points to `checkout.stripe.com` (LIVE), not `sandbox`.
4. Right pane `?learn=1` → practice exercises render for a guest (10 free), then subscribe.
