# DevStat Repair Plan — All Phases

## Purpose

This document is a comprehensive plan to fix the DevStat application's backend and frontend issues. It was created after a full codebase audit that found **42 frontend issues** and **40 backend issues**.

The three original symptoms were:
1. Kaplan-Meier curve API fails with "Network Error" (HTTP 0)
2. Cross-tabulation returns nothing useful
3. Output tab shows nothing

But the audit revealed far more problems — see the full breakdown below.

## How to use this plan

1. Work through phases **in order** — each phase builds on the previous
2. When I (opencode) am told to "fix X", I should check this file for the detailed approach
3. After fixing each item, write a test that catches the regression before moving on
4. Re-build the frontend (`npx vite build`) and test backend startup after each phase
5. Run the full test suite after each phase
6. If the user reports new symptoms, check this plan first — they may be listed here

## Testing philosophy (why 82 bugs survived)

The previous "testing" was superficial — environment verification only:
- Backend imports OK
- Frontend builds OK
- Health endpoint responds OK

**No feature was ever exercised end-to-end.** No test ever ran a KM curve, checked what the regression backend actually received, opened the Output tab to verify chart rendering, or completed an AI analysis flow. See `softwaretestplan.md` for the full testing strategy.

### Rules enforced during this repair

1. **Every fix gets a test.** Before marking any item done, write a test that asserts the correct behavior. This catches regressions immediately.
2. **Output tab rendering is the definition of "done".** A feature is not fixed until its results appear correctly in the Output tab (tables render, charts render, narrative displays).
3. **Smoke test every parameter path.** If a fix involves a dropdown/selector, verify all options work, not just the default.
4. **Fix bugs before building next feature.** No moving to Phase 2 until Phase 1 tests pass.
5. **Use or delete existing test infra.** Wire `contractTests.ts`, `normalizerValidation.ts`, `test_e2e.py` into the test runner or remove them.

---

## Phase 1 — Critical: Backend crashes & security

### 1.1 Fix R bridge crash (KM "Network Error")

**Files:** `backend/r/bridge.py:306-337`

The `_execute()` method calls `subprocess.run([RSCRIPT, ...])`. When R is not found, `RSCRIPT=""` and `subprocess.run([""])` raises `FileNotFoundError` — uncaught, crashes uvicorn worker, frontend gets HTTP 0.

**Fix:**
- Wrap `subprocess.run` in `_execute()` with `try/except FileNotFoundError`
- Return `{"error": "R not available", "status": "unavailable"}` instead of crashing
- Check `app.state.r_ready` in R-based endpoints and return clear error if false
- Fall back to Python implementations where available (`services/survival.py` has `kaplan_meier_python()`)

**Verification:** Start backend without R installed. POST to `/api/analysis/kaplan-meier` should return a descriptive 4xx/5xx error, not crash the worker.
**Test:** Write a pytest test that starts the app, hits `/api/analysis/kaplan-meier` without R, and asserts a 4xx/5xx response (not a crash). Write a second test that mocks R as available and asserts the response shape matches `NormalizedResult` fields (`tables`, `charts`, `narrative`).

---

### 1.2 Fix JSON serialization of `float("inf")` and `float("nan")`

**Files:** `backend/app/main.py:37-69`, `backend/app/services/diagnostic.py:107-108`

`NumpyJSONResponse` has `allow_nan=False`, so `float("inf")` (plain Python float, not np.floating) bypasses the custom encoder and crashes `json.dumps`. The diagnostic test endpoint can produce `float("inf")` from `_safe_div` when specificity == 1.

**Fix:**
- Add `float("inf")`, `float("-inf")`, `float("nan")` handling to `_json_encoder_default` in `main.py`
- Fix `_round()` in `diagnostic.py` to handle `float("inf")` and `float("nan")`

**Verification:** POST to `/api/analysis/diagnostic` with perfect classification data should return a valid JSON response containing `sensitivity`, `specificity`, `confusion_matrix`.
**Test:** Write a pytest test that uploads a diagnostic dataset, calls the diagnostic endpoint with perfect data (sensitivity=1, specificity=1), and asserts the response serializes to valid JSON without crashing. Assert `float("inf")` is never present in the response.

---

### 1.3 Fix `pd.NA` TypeError in R bridge

**Files:** `backend/r/bridge.py:288-290`

`val != val` raises `TypeError` for `pd.NA` because pandas' NA has ambiguous boolean value.

**Fix:**
- Add `pd.NA` check before the NaN check
- Add `np.floating` to the `isinstance` check
- Return `"NA_real_"` for all missing/null sentinel values

---

### 1.4 Fix `params` dict mutation in dispatcher

**Files:** `backend/r/dispatcher.py:70`

`params["data_path"] = csv_path` mutates the caller's dict in-place. If caller retries, stale `data_path` leaks through.

**Fix:** Copy params before mutation: `analysis_params = {**params, "data_path": csv_path}`

---

### 1.5 Remove `eval()` RCE vulnerability

**Files:** `backend/app/routers/data.py:793-825`, `backend/app/routers/transform.py:176`

`eval()` with restricted `__builtins__` can still be bypassed via `np.__class__.__init__.__globals__['os'].system(...)`.

**Fix:** Replace `eval()` with an AST-based expression parser that only allows safe operations (arithmetic, comparisons, column references). Or use `pd.eval()` which is safer.

---

### 1.6 Create missing AI prompt files

**Files:** `backend/app/ai/parser.py:25`, `backend/app/ai/synthesizer.py:16`

The code silently falls back to empty string if `goal_parser.md` or `synthesizer.md` don't exist. They don't exist. LLM calls then use empty system prompts and `json.loads()` crashes on the non-JSON response.

**Fix:** Create `backend/app/ai/prompts/goal_parser.md` and `backend/app/ai/prompts/synthesizer.md` with proper prompts, OR make the code throw a clear startup error if files are missing.

---

### 1.7 Write backend regression tests for Phase 1

**Files:** `backend/tests/`

Create pytest tests that cover all Phase 1 fixes:
- R bridge crash: test endpoint returns error, not crash
- JSON serialization: test `float("inf")`, `float("nan")`, `pd.NA` all serialize cleanly
- AI module: test startup warns if prompt files missing (don't crash)
- `eval()`: test that dangerous input is rejected

Each test must:
1. Set up realistic input data (upload CSV)
2. Call the relevant API endpoint
3. Assert correct HTTP status code
4. Assert response body has expected fields with correct types
5. Assert response serializes to valid JSON

---

## Phase 2 — Critical: Frontend crashes & broken features

### 2.1 Fix `outputStore.appendResult()` not existing (AI page crash)

**Files:** `frontend/src/stores/outputStore.ts`, `frontend/src/pages/AiPage.tsx:140,240`

`outputStore.appendResult()` is called in two places but the method doesn't exist on `OutputStore`. Runtime `TypeError` crash.

**Fix:** Add `appendResult()` method or replace calls with existing `addEntry('ai_assistant', ...)`.

---

### 2.2 Fix Regression method hardcoded to 'enter'

**Files:** `frontend/src/api/client.ts:279-282`

`regressionApi.run()` ignores the `method` parameter and always sends `method: 'enter'`.

**Fix:** Pass through the `method` parameter to the API call instead of hardcoding.

---

### 2.3 Fix DiagnosticPage contingency table rendering

**Files:** `frontend/src/pages/DiagnosticPage.tsx:60-69`

Two rows use different object keys so the table can't align columns. Renders `undefined` values.

**Fix:** Use consistent column keys across all rows, or render as a proper 2x2 grid.

---

### 2.4 Fix SyntaxPage never executing user code

**Files:** `frontend/src/pages/SyntaxPage.tsx:22-29`

`runCode` ignores the user's typed code and always calls a hardcoded cox-predict endpoint.

**Fix:** Send the user's `code` variable to the backend. May need a new `POST /api/syntax/run` endpoint.

---

### 2.5 Fix AI page executing tests multiple times

**Files:** `frontend/src/pages/AiPage.tsx:218-234`

The progressive loop re-executes all previous tests with each iteration. Test N runs N times.

**Fix:** Remove redundant re-executions. Only run each test once.

---

### 2.6 Fix AI Accept button doing nothing

**Files:** `frontend/src/pages/AiPage.tsx:309`

The Accept button has no `onClick` handler.

**Fix:** Add `onClick` handler.

---

### 2.7 Fix AI synthesize called with empty question

**Files:** `frontend/src/pages/AiPage.tsx:236`

`/api/ai/synthesize` is called with `{ question: '' }` instead of the user's actual question.

**Fix:** Pass the user's original question text from `handleSend`.

---

### 2.8 Write frontend unit tests for Phase 2 fixes

**Files:** `frontend/src/utils/responseNormalizer.ts` (test), `frontend/src/pages/` (component tests)

Write vitest tests that cover:
- `regressionApi.run()` passes through the `method` parameter (all 4 methods)
- `outputStore.addEntry()` stores entries with correct category/type fields
- DiagnosticPage table renders 2x2 confusion matrix with all 4 cells visible
- AI page `appendResult()` / `addEntry()` call succeeds without TypeError

For each frontend API function test:
1. Mock the API response
2. Call the function with test parameters
3. Assert the correct endpoint URL was called
4. Assert the correct request body was sent (e.g. `method` field)

---

## Phase 3 — High: Backend data corruption & logic bugs

### 3.1 Fix metadata cache not invalidated on mutations

**Files:** `backend/app/routers/data.py:312-334`

`_cached_metadata` is only cleared on upload. Cell edits, row ops, recode, compute, etc. leave stale cache.

**Fix:** Call `_invalidate_metadata_cache()` after all data mutation operations.

---

### 3.2 Fix R descriptive analysis missing count always 0

**Files:** `backend/r/analyses/descriptive.R:56-58`

`stats_dict` receives data with NAs already removed, then hardcodes `missing <- 0`.

**Fix:** Compute missing count from original data before dropping NAs.

---

### 3.3 Fix Cox PH assumption always "not violated"

**Files:** `backend/app/services/survival.py:407-408`

Interpretation always states PH assumption not violated, even when `ph_test` shows p < 0.05.

**Fix:** Check `ph_test` results and report violation when p < 0.05.

---

### 3.4 Fix KM event_code not respected

**Files:** `backend/r/analyses/kaplan_meier.R:8`

R script doesn't accept `event_code` parameter. Counts all non-zero status values as events.

**Fix:** Add `event_code` parameter and filter `status == event_code` for event counting.

---

### 3.5 Fix crosstab column percentage vector division

**Files:** `backend/r/analyses/crosstab.R:77`

`mat[i, ] / col_totals` uses vector recycling, wrong when rows == cols.

**Fix:** Use per-element division: loop or `sapply` over columns.

---

### 3.6 Fix chi-square interpretation percentage format

**Files:** `backend/app/services/interpreter.py:387`

`:.1%` multiplies by 100, showing e.g. "450.0%" instead of "4.5".

**Fix:** Change to `:.1f` (min_exp is a raw count).

---

### 3.7 Fix cox-predict baseline survival length mismatch

**Files:** `backend/app/services/survival.py:503-512`

Baseline survival and profile predictions use different time grids.

**Fix:** Interpolate all series to a common time grid.

---

### 3.8 Write backend integration tests for Phase 3

**Files:** `backend/tests/`

Write pytest tests that run each analysis end-to-end with a real dataset:
- Upload `sample_100.csv` via POST `/api/data/upload`
- Run descriptive analysis → assert `n`, `mean`, `std` fields present
- Run frequencies → assert count + percent per value
- Run crosstab → assert table has rows × cols structure matching input
- Run KM curve → assert survival probabilities are between 0 and 1
- Run Cox regression → assert coefficients table has expected columns
- Run diagnostic test → assert confusion matrix totals match input

Each integration test must assert:
1. HTTP 200 response
2. Response is valid JSON
3. Required fields exist with correct types
4. No `error` or `detail` fields present (unexpected failure)

---

## Phase 4 — High: Frontend rendering & UX bugs

### 4.1 Fix OutputPage chart rendering (ChartCard is placeholder)

**Files:** `frontend/src/pages/OutputPage.tsx:66-76`

`ChartCard` renders `<Text type="secondary">{chartType} chart</Text>` instead of an actual Plotly chart.

**Fix:** Replace with actual `Plot` component using data from `chart.data.series`. Reuse `seriesToPlotlyChart()` from `ChartRenderer.tsx`.

---

### 4.2 Fix responseNormalizer missing crosstab pattern

**Files:** `frontend/src/utils/responseNormalizer.ts:23-92`

`extractTable()` has no handler for crosstab's list-of-arrays format. Falls through to metadata-only extraction.

**Fix:** Add pattern detection for `[["", "col1", "col2"], ["row1", 5, 3]]` format. Convert to array-of-objects.

---

### 4.3 Fix DataPage delete column always deleting last column

**Files:** `frontend/src/pages/DataPage.tsx:301-305`

`getSelectedRows()` result retrieved but never used. Always deletes `dataset.columns[last]`.

**Fix:** Use the selected variable to determine which column to delete.

---

### 4.4 Fix `.toFixed()` on non-numeric values (DescriptivePage)

**Files:** `frontend/src/pages/DescriptivePage.tsx:174-175,196`

Non-numeric values pass `v === Math.round(v)` (false), then crash on `v.toFixed(3)`.

**Fix:** Add `typeof v === 'number'` guard before `.toFixed()`.

---

### 4.5 Fix false p-value detection in CorrelationPage

**Files:** `frontend/src/pages/CorrelationPage.tsx:76`

`key.includes('p')` matches any column with 'p' in name (e.g. "SPSS version").

**Fix:** Use exact match or whitelist: `['p', 'p_value', 'p-value', 'pval']`.

---

### 4.6 Fix p-value falsy comparison

**Files:** `frontend/src/pages/ComparePage.tsx:122-126`

`data.p_value || data.p` treats p=0 as falsy and falls through. `undefined < 0.05` is `false`.

**Fix:** Use `??` operator and handle null case.

---

### 4.7 Fix TestSuggestionPage sending wrong payload

**Files:** `frontend/src/pages/TestSuggestionPage.tsx:460-461,477-478`

Manual test selection always uses primary recommendation's payload, not the selected test's payload.

**Fix:** Map each test to its own analysis payload from the suggestion response.

---

### 4.8 Fix FactorPage reliability results stored under wrong category

**Files:** `frontend/src/pages/FactorPage.tsx:73`

Reliability (Cronbach Alpha) results stored with type `'factor'` instead of `'reliability'`.

**Fix:** Use `outputStore.addEntry('reliability', ...)` for reliability analyses.

---

### 4.9 Write frontend rendering tests for Phase 4

**Files:** `frontend/src/utils/responseNormalizer.test.ts`, `frontend/src/components/ChartRenderer.test.ts`

Write vitest tests that validate the full rendering pipeline:
- `normalizeResult('crosstab', mockResponse)` returns `tables` with the contingency table rows
- `normalizeResult('kaplan_meier', mockResponse)` returns `charts` with Plotly-compatible series
- `normalizeResult('descriptive', mockResponse)` returns `tables` with descriptive stats rows
- `ChartCard` (or replacement) renders a Plotly `Plot` component when given chart data
- `seriesToPlotlyChart()` produces valid Plotly trace objects for each chart type

For each normalizer test:
1. Create a mock API response that matches the actual backend output shape
2. Run it through `normalizeResult()`
3. Assert tables have correct column headers and row values
4. Assert charts have valid `type` and `data.series`
5. Assert narrative is a non-empty string when interpretation is available

---

## Phase 5 — Medium: Backend quality & correctness

### 5.1 Add R availability check with graceful degradation

**Files:** `backend/app/routers/analysis.py`

Check `app.state.r_ready` at the start of each R-based endpoint. Return clear error if R unavailable.

---

### 5.2 Fix duplicated log format arguments

**Files:** `backend/app/routers/analysis.py:151-153`

Remove duplicated positional args in `log.warning()` call.

---

### 5.3 Add missing prompt files for AI module

**Files:** `backend/app/ai/prompts/`

Create `goal_parser.md` and `synthesizer.md` with appropriate prompts, or add startup warning.

---

### 5.4 Fix `_evaluate_expression` column name substitution

**Files:** `backend/app/routers/data.py:793-810`

Regex substitution can produce overlapping match bugs with similarly-named columns (e.g. `age` vs `age_group`).

**Fix:** Use column indices or safer substitution strategy.

---

### 5.5 Fix `_safe_interpret` silent error swallowing

**Files:** `backend/app/routers/analysis.py:111-116`

Log exception before returning default so bugs can be debugged.

---

### 5.6 Fix CORS for production deployment

**Files:** `backend/app/main.py:108-112`

Read `allow_origins` from environment variable: `os.environ.get("CORS_ORIGINS", "http://localhost:5173,...").split(",")`.

---

## Phase 6 — Medium: Frontend quality & UX

### 6.1 Add error feedback to silent catch blocks

**Files:** All frontend pages with empty `catch {}` blocks.

Add `message.error()` or notification on API failures.

---

### 6.2 Fix WizardPage full page reload

**Files:** `frontend/src/pages/WizardPage.tsx:190-213`

Replace `window.location.href` with `navigate()`.

---

### 6.3 Fix GraphsPage download button

**Files:** `frontend/src/pages/GraphsPage.tsx:123-131`

Use `Plotly.downloadImage()` instead of just showing a tooltip.

---

### 6.4 Fix SurvivalPage predictSurvival parameters

**Files:** `frontend/src/pages/SurvivalPage.tsx:175-178`

Pass Cox model results (coefficients, baseline) instead of raw variable names.

---

### 6.5 Fix OutputPage compare mode state management

**Files:** `frontend/src/pages/OutputPage.tsx:117-119`, `frontend/src/stores/outputStore.ts:200-204`

Call `outputStore.setCompareMode(true)` and fix clear-on-disable logic.

---

### 6.6 Fix RegressionPage to use proper API methods

**Files:** `frontend/src/pages/RegressionPage.tsx:83`

Fix `regressionApi.run()` to pass through the `method` parameter.

---

### 6.7 Remove dead utility code

**Files:** `frontend/src/utils/analysisTimeout.ts`, `frontend/src/hooks/useDatasetTabs.ts`

Delete unused files or exclude from build.

---

## Phase 7 — Low: Cleanup & polish

### 7.1 Fix App.tsx unused imports and duplicate route check

**Files:** `frontend/src/App.tsx`

---

### 7.2 Fix console.log guards in runtime code

**Files:** `frontend/src/pages/DescriptivePage.tsx:13-14`, `SurvivalPage.tsx:13-14`, `GraphsPage.tsx:18-20`, `ChartRenderer.tsx:9-10`

Guard with `process.env.NODE_ENV !== 'production'` or remove.

---

### 7.3 Consolidate `_require_data()` into shared utility

**Files:** All 6 router files

Move to `app/state.py` and import everywhere.

---

### 7.4 Fix ChartRenderer Math.max O(n^2) performance

**Files:** `frontend/src/components/ChartRenderer.tsx:107`

Compute `maxCount` once outside the map.

---

### 7.5 Fix VariableView DOM element ID fragility

**Files:** `frontend/src/components/VariableView.tsx:125-168`

Replace `document.getElementById()` with React `useRef`.

---

## Original Three Symptoms & Their Root Causes

| Symptom | Primary Cause | Other Contributing Causes |
|---------|--------------|--------------------------|
| KM "Network Error" (HTTP 0) | R bridge crash — `FileNotFoundError` in subprocess | No R availability check; NumpyJSONResponse NaN handling; KM event_code not respected |
| Crosstab returns nothing | `responseNormalizer.ts` has no list-of-arrays pattern | Crosstab column % vector division bug; `ChartCard` is text placeholder |
| Output tab shows nothing | KM crashes + crosstab data dropped + chart is placeholder text | Silent catch blocks; missing `appendResult()` method |

## Verification Checklist

After each phase, run through this entire checklist. Any failure means the phase is not complete.

### Environment checks
- [ ] Backend starts without errors: `python -m uvicorn app.main:create_app --factory`
- [ ] Backend health check: `curl http://127.0.0.1:8150/api/health`
- [ ] Frontend builds: `npx vite build`
- [ ] Frontend dev server starts: `npm run dev`

### Feature smoke tests (manual)
- [ ] KM curve runs without crash, returns survival probabilities 0-1
- [ ] Crosstab returns usable table data with correct row/column counts
- [ ] Output tab shows charts (real Plotly charts, not placeholder text)
- [ ] Output tab shows tables with data
- [ ] All AI module features work end-to-end
- [ ] Regression method selection (enter/stepwise/forward/backward) works
- [ ] Syntax editor executes user code
- [ ] Diagnostic test table renders 2x2 confusion matrix correctly
- [ ] DataPage delete column deletes the selected column (not the last one)

### Parameter path testing
- [ ] Regression: test all 4 methods, verify backend receives correct one
- [ ] Correlation: test pearson/spearman/kendall, verify backend receives correct one
- [ ] Charts: test histogram/boxplot/scatter/bar, verify each renders
- [ ] Tests: test parametric AND non-parametric variants where available
- [ ] Upload: test CSV, XLSX file formats

### Automated test suite
- [ ] Backend tests pass: `cd backend && pytest -v`
- [ ] Frontend tests pass: `cd frontend && npx vitest run --reporter=verbose`
- [ ] No "cannot find module" or import errors in test output
- [ ] New tests cover the fixes in this phase (not just pre-existing tests)

### Regression prevention
- [ ] Each fix in this phase has at least one test that would fail if the bug returned
- [ ] The test asserts specific output shape/values, not just HTTP 200
- [ ] Frontend normalizer tests use mock data matching actual backend response shapes
- [ ] No `console.log` / debug artifacts remain in production code
- [ ] No `catch {}` without error logging remains in production code
