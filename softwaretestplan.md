# DevStat Software Testing Plan

## Why 82 bugs survived "integration testing"

The previous "testing" was superficial — environment verification only:
- Backend imports OK ✓
- Frontend builds OK ✓
- Health endpoint responds OK ✓

**No feature was ever actually exercised end-to-end:**
- No test ever ran a KM curve and checked the result
- No test ever ran a regression with `stepwise` and verified the backend received it
- No test ever opened the Output tab and checked that a chart rendered
- No test ever completed an AI analysis flow

## Testing principles for this project

### 1. One E2E test per feature before marking it done

Each feature must have a test that:
1. Calls the API endpoint with realistic parameters
2. Asserts the response shape is correct (fields exist, types match)
3. Feeds the response into the frontend normalizer
4. Asserts the normalizer produces valid renderable output

**This catches both backend AND frontend bugs in one test.**

### 2. Output tab rendering is the definition of "done"

Any feature whose results don't appear in the Output tab is not done. The pattern of "API works → Output tab is someone else's problem" created:
- The `ChartCard` placeholder text (never rendered a real chart)
- Missing normalizer patterns for crosstab (never checked the response format)
- Silent data loss in `normalizeResult()` (never validated the output)

**Checklist before marking any feature complete:**
```
[ ] API returns correct response shape
[ ] responseNormalizer.ts extracts tables from response
[ ] responseNormalizer.ts extracts charts from response
[ ] OutputPage renders the tables
[ ] OutputPage renders the charts
[ ] Narrative/interpretation displays
```

### 3. Smoke test every parameter path

If a UI control offers N options, test all N — not just the default:
- Regression method: test `enter`, `stepwise`, `forward`, `backward`
- Correlation method: test `pearson`, `spearman`, `kendall`
- Test type: test parametric AND non-parametric variants
- Chart type: test histogram, boxplot, scatter, bar, etc.

**The `method: 'enter'` hardcode survived because only the default was tested.**

### 4. Fix bugs before building features

Every bug found during testing must be fixed before the next feature starts. The 82 bugs accumulated because:
- The project was built feature-by-feature
- No feature was ever revisited after initial implementation
- Technical debt compounded without ever being paid down

**Zero-bug tolerance on existing features while building new ones.**

### 5. Use or delete existing test infrastructure

The codebase already has:
- `frontend/src/utils/contractTests.ts` — 484 lines of renderer contract tests (never run)
- `frontend/src/utils/normalizerValidation.ts` — 71 line validation function (never called)
- `backend/test_e2e.py` — E2E test file (appears unused)
- `backend/.pytest_cache/` — pytest is available

**Action: Wire these into the test runner or delete them.**

## Test categories to implement

### Backend unit tests (pytest)
- Each analysis endpoint returns correct shape for valid input
- Each analysis endpoint returns proper error for invalid input
- R bridge handles missing R gracefully
- JSON serialization handles NaN, Inf, pd.NA, None
- Startup checks handle R unavailable

### Frontend unit tests (vitest)
- responseNormalizer extracts correct fields for each analysis type
- crosstabToPlotly produces valid Plotly traces
- seriesToPlotlyChart handles all chart_types
- Error formatting for all API error shapes

### Integration tests
- Upload CSV → analyze → verify result shape
- R analysis → Python analysis → consistent output format
- AI parse → execute → synthesize flow

### E2E tests (Playwright or similar)
- Load sample data → run KM → see chart in Output tab
- Load sample data → run crosstab → see table in Output tab
- Load sample data → run regression with stepwise → verify method used
- Open test suggestions → select non-primary test → correct payload sent

## How to run tests

```bash
# Backend tests (once written)
cd backend
pytest -v

# Frontend tests (once written)
cd frontend
npx vitest run

# E2E (once written)
cd backend
pytest test_e2e.py -v
```

## Enforcement

- Pull requests should include tests for new features
- Bug fixes should include a test that catches the regression
- No feature is merged unless Output tab rendering is verified
- The test suite is run before every deployment
