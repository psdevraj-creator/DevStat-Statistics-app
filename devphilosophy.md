# Development Philosophy & Lessons Learned

> This document captures engineering lessons from the DevStat project. It serves as a reference for current and future projects to avoid repeating the same mistakes. It should be updated after every significant lesson learned.

---

## Table of Contents

1. [Testing Is Not Optional](#1-testing-is-not-optional)
2. ["Works on My Machine" Is Not Done](#2-works-on-my-machine-is-not-done)
3. Every Feature Has a Rendering Path](#3-every-feature-has-a-rendering-path)
4. Smoke Test Every Parameter Path](#4-smoke-test-every-parameter-path)
5. Fix Bugs Before Building Features](#5-fix-bugs-before-building-features)
6. Integration Is Where Things Break](#6-integration-is-where-things-break)
7. Error Handling Is a Feature](#7-error-handling-is-a-feature)
8. The Output Tab Rule](#8-the-output-tab-rule)
9. Data Shapes Must Be Contract-Tested](#9-data-shapes-must-be-contract-tested)
10. Never Trust a Silent Catch](#10-never-trust-a-silent-catch)
11. Hardcoding Is Technical Debt](#11-hardcoding-is-technical-debt)
12. Copy-Paste Is a Bug Factory](#12-copy-paste-is-a-bug-factory)
13. Security Is Not Optional](#13-security-is-not-optional)
14. Stale Cache = Wrong Answers](#14-stale-cache--wrong-answers)
15. The Developer's Bill of Rights](#15-the-developers-bill-of-rights)
16. Final Axioms](#16-final-axioms)

---

## 1. Testing Is Not Optional

### The mistake
82 bugs survived into what was considered a "tested" application. The "testing" was superficial — backend imports check, frontend build check, health endpoint ping. No feature was ever exercised end-to-end.

### The rule
**Environment verification is NOT feature testing.** Checking that the server starts and the frontend compiles tells you nothing about whether the features work.

### What to do instead
- Every feature must have a test that calls its API endpoint with realistic data and asserts the response shape
- Every feature must have a test that feeds the response through the frontend rendering pipeline and asserts the user can see the result
- "The build passes" is the starting line, not the finish line

### Signs you're doing it wrong
- You can list 20+ features but can't point to a test for each one
- Your test suite only covers infrastructure (server starts, imports work)
- The person who built the feature has never manually exercised it end-to-end

---

## 2. "Works on My Machine" Is Not Done

### The mistake
Features were considered complete when the developer could make them work in their local environment. No verification was done in clean conditions, without R installed, without the full dataset, or with edge-case inputs.

### The rule
A feature is not done until it has been verified under adverse conditions:
- Missing dependencies (no R, no Python packages)
- Empty datasets
- Datasets with missing values (NaN, NA, null)
- Datasets with extreme values (infinity, very large numbers)
- Network failures (backend unavailable)
- Invalid inputs (wrong types, missing fields)

### What to do instead
- Test with R installed AND without R installed
- Test with NaN/NA/inf values in the dataset
- Test with a 1-row dataset and a 100K-row dataset
- Test with the backend offline (frontend should show a clear error, not spin forever)

### Signs you're doing it wrong
- You've never seen the error message a user gets when a dependency is missing
- You assume all inputs will be clean
- Error handling is "the backend will always be available"

---

## 3. Every Feature Has a Rendering Path

### The mistake
The Output tab's `ChartCard` rendered `<Text type="secondary">{chartType} chart</Text>` — a text placeholder instead of an actual Plotly chart. This was never caught because nobody ever opened the Output tab after wiring up the chart data. The rendering path was assumed to work without ever being visually verified.

### The rule
Every data-producing feature must be verified at the final rendering stage — the screen the user actually looks at.

### What to do instead
- When building a feature, trace the data from API response → normalizer → component props → rendered DOM/Canvas
- Verify each transformation step with a unit test
- Visually confirm the final rendered output at least once
- Automate this with screenshot/visual regression tests for critical paths

### Signs you're doing it wrong
- You've tested the API but never opened the page that displays the result
- Your normalizer runs without errors but produces empty output
- A component renders `<SomeType>{value}</SomeType>` without checking what `value` actually is

---

## 4. Smoke Test Every Parameter Path

### The mistake
The regression method dropdown offered `enter`, `stepwise`, `forward`, and `backward`. The backend always received `enter` because the API client was hardcoded. Only the default was ever tested.

### The rule
If a UI control offers N options, you must verify ALL N produce the correct behavior — not just the default.

### What to do instead
- For every dropdown, radio group, or selector, write a test for each option
- Don't just test that the UI renders the options — test that the correct value reaches the backend
- Use a network mocking layer to intercept the actual API call and assert the payload

### Signs you're doing it wrong
- A UI dropdown has 4 options but your tests only cover 1
- You've never checked what the backend actually receives for non-default selections
- You trust that "the UI sends the right thing" without verification

---

## 5. Fix Bugs Before Building Features

### The mistake
The project was built feature-by-feature without ever stabilizing. 82 bugs accumulated because:
- No feature was revisited after initial implementation
- Known issues were deferred indefinitely
- Each new feature was built on top of broken foundations

### The rule
**Zero-bug tolerance on existing features while building new ones.** A known bug in a completed feature blocks any new feature work until fixed.

### What to do instead
- When a bug is found in an existing feature, fix it before starting the next feature
- Maintain a bug tracker with severity levels. Block new work on Critical/High items
- Every sprint/iteration should include bug-fixing capacity proportional to the bug count

### Signs you're doing it wrong
- Your bug list keeps growing while feature count keeps growing
- You can't remember what the oldest unfixed bug is
- New features are built on code paths known to be broken

---

## 6. Integration Is Where Things Break

### The mistake
Individual components worked in isolation but broke when connected:
- The API returned crosstab data as a list-of-arrays, but the normalizer expected array-of-objects
- The R bridge worked when tested directly but crashed when called from the analysis router
- The AI module accepted tests but the execution router only handled 5 of 20+ test types

### The rule
Integration points between systems are where the majority of bugs live. Test the seams, not the components.

### What to do instead
- Write integration tests that exercise the full pipeline: upload → analyze → normalize → render
- Use contract tests that assert the API response shape matches what the frontend expects
- When changing an API response, update the frontend contract AND the backend contract simultaneously

### Signs you're doing it wrong
- Frontend and backend teams use different example data
- The API response has fields the frontend ignores; the frontend expects fields the API doesn't return
- You've never run the frontend against the real backend (only mock data)

---

## 7. Error Handling Is a Feature

### The mistake
- `eval()` on user input with insufficient sandboxing — security vulnerability
- `subprocess.run()` without catching `FileNotFoundError` — worker crash
- `json.dumps(allow_nan=False)` without sanitizing plain Python floats — serialization crash
- Empty `catch {}` blocks throughout the frontend — silent failures
- `_safe_interpret()` swallowing all exceptions — debugging impossible

### The rule
Error handling is not a separate task. It is part of the feature. A feature is not complete until all error states are handled gracefully.

### What to do instead
- Every API endpoint must handle: invalid input, missing dependencies, internal errors, and edge-case data
- Every `try/except` must log the error, even if you think it "can't happen"
- No `catch {}` without at least error logging
- User-facing errors must be descriptive: "R is not installed" not "Internal server error"

### Signs you're doing it wrong
- Your code has empty `except:` or `catch {}` blocks
- Users see "Something went wrong" or HTTP 500 with no detail
- You can't reproduce a bug because the error was silently swallowed

---

## 8. The Output Tab Rule

### The mistake
Several features had working APIs but broken output rendering. The Output tab was treated as a separate concern rather than as an integral part of each feature.

### The rule
**A feature is not done until its output appears correctly in the final user-facing display.** For this project: if it doesn't render in the Output tab, it doesn't work.

### What to do instead
- Before starting a feature, define what the output should look like (tables, charts, narrative text)
- Build the output renderer alongside the API endpoint, not after
- Verify the full pipeline end-to-end before moving on

### Signs you're doing it wrong
- "The API works, the frontend is a separate ticket"
- Output display is built generically without testing each analysis type
- You have to guess what a feature's output looks like

---

## 9. Data Shapes Must Be Contract-Tested

### The mistake
The backend returned crosstab data as a list-of-arrays `[["", "col"], ["row", 5]]`. The frontend normalizer had no handler for this shape. The data was silently dropped. The contract between backend and frontend was implicit — documented only in the developer's head.

### The rule
Every API response must have an explicit, tested contract that both backend and frontend agree on. Changes to the contract must update both sides simultaneously.

### What to do instead
- Define response types/schemas explicitly (OpenAPI/Swagger, TypeScript interfaces, or Pydantic models)
- Write contract tests that assert the backend response matches the schema
- Write normalizer tests that assert the frontend can consume the schema
- When the schema changes, all contract tests must update in the same commit

### Signs you're doing it wrong
- The frontend uses `result?.data ?? result?.results ?? result` to guess the response shape
- Backend changes break the frontend without any test failing
- You discover API response fields by reading network tab, not documentation

---

## 10. Never Trust a Silent Catch

### The mistake
Throughout the frontend, API calls were wrapped in try/catch with empty catch blocks. Network failures, validation errors, and backend crashes produced no user feedback. The application appeared broken or unresponsive.

### The rule
Every caught exception must be handled in one of three ways:
1. **Show a user-facing error message** (toast, notification, inline error)
2. **Log it** (console, logging service)
3. Both

### What to do instead
- Add `message.error()` or equivalent to every catch block that handles API failures
- Add `console.error()` with the full error object for debugging
- Show loading states that time out with an error message if no response arrives

### Signs you're doing it wrong
- Search your codebase for `catch {` or `catch { }` or `except: pass`
- Your users see a blank page or spinner when something fails
- You rely on the browser dev tools to notice API errors

---

## 11. Hardcoding Is Technical Debt

### The mistake
- CORS origins hardcoded to localhost — blocks production deployment
- R library path hardcoded to version 4.6 — breaks on R upgrade
- Regression method hardcoded to `'enter'` — ignores user selection
- R_HOME not set but registry fallback assumed — breaks in headless/CI environments

### The rule
Every hardcoded value that could reasonably vary between environments or over time is technical debt. Configuration must be externalized.

### What to do instead
- Use environment variables for: API URLs, ports, dependency paths, feature flags, environment names
- Use configuration files for: analysis parameters, default values, timeouts
- Fall back to sensible defaults after checking env vars, not before

### Signs you're doing it wrong
- You modify code to change a URL, port, or path
- A version number is embedded in a string literal
- You have to edit source files for each deployment environment

---

## 12. Copy-Paste Is a Bug Factory

### The mistake
- `_require_data()` was duplicated in 6 router files with slightly different docstrings
- Error formatting was inconsistent across pages (some used `formatApiError`, others did raw string concat)
- The same `.toFixed()` bug existed in two places in the same file
- Multiple AI prompt files had the same fallback-to-empty-string pattern

### The rule
Every piece of logic should exist in exactly one place. Duplication guarantees inconsistency.

### What to do instead
- Extract shared logic into utility functions or base classes
- When you find yourself copying code, stop and refactor first
- Use linters to detect duplication

### Signs you're doing it wrong
- You make the same fix in multiple files
- A bug appears in some instances of a pattern but not others
- You search for "how do we handle X" and find 3 different approaches

---

## 13. Security Is Not Optional

### The mistake
`eval()` on user input with `{"__builtins__": {}}` restriction. This sandbox is trivially bypassed: `np.__class__.__init__.__globals__['os'].system('rm -rf /')`. Any user with access to the compute or transform endpoints could execute arbitrary system commands.

### The rule
Every user input path must be treated as an attack vector. "But only admins can access it" is not a security strategy.

### What to do instead
- Never use `eval()` on user input. Ever. There is no safe way to sandbox `eval()`.
- Use language-specific safe evaluators (e.g. `pd.eval()` for pandas, `numexpr` for numeric expressions)
- For user-provided expressions, parse the AST and whitelist allowed operations
- Run security-critical components in isolated processes or containers

### Signs you're doing it wrong
- You use `eval()`, `exec()`, or `Function()` with user input
- You have a comment "TODO: improve security"
- You assume users won't find the admin panel

---

## 14. Stale Cache = Wrong Answers

### The mistake
The metadata cache was only invalidated on file upload. Cell edits, row operations, column operations, recode, compute, and date fixes all bypassed cache invalidation. Users who edited data after upload would see stale column metadata.

### The rule
Every cache must have a complete invalidation strategy. If you can enumerate the invalidation points and miss one, the cache will produce wrong answers.

### What to do instead
- Every data mutation operation must explicitly invalidate affected caches
- Use cache keys that include relevant state (e.g. dataset hash + last-modified timestamp)
- Consider time-based expiration as a safety net
- When in doubt, miss the cache (correct > fast)

### Signs you're doing it wrong
- Your cache invalidation strategy is "clear it here and hope the other places remember to clear it too"
- You have a single cache-clear function that's called from some mutation paths but not all
- Users complain that data doesn't update after editing

---

## 15. Keep the User Informed — Update the Todo List

### The mistake
Work was done without updating the shared todo list or asking for confirmation before proceeding. The user had no way to know what had been completed, what was in progress, or what was pending. This created distrust and confusion.

### The rule
**Every significant action must be preceded by an updated todo list and a brief status message.** Before starting work, the todo list must reflect the current plan. After completing work, it must be updated immediately. If a step requires user input, ask before proceeding.

### What to do instead
- Update the todo list before starting any new task
- After each task completes, mark it done and post a brief summary
- If the next step depends on user choice, stop and ask
- If something unexpected takes a long time, send a status update

### Signs you're doing it wrong
- The user asks "what are you doing?" or "what's happening?"
- The todo list is stale or missing
- Work continues past a natural decision point without asking
- The user discovers completed work by accident

---

## 16. The Developer's Bill of Rights

Every developer working on this project has the right to:

1. **Know if a feature works.** Test results are published, not hidden in a local branch.
2. **Know if a change breaks something.** The test suite runs before every merge.
3. **Know the state of the system.** Monitoring, logging, and error tracking are in place from day one.
4. **Say no to feature pressure.** Bugs are fixed before new features are built.
5. **See the output.** The final rendered result is verified before a feature is marked done.
6. **Understand the contract.** API schemas are documented, not reverse-engineered from network traffic.
7. **Trust the cache.** Invalidation is complete and auditable.
8. **Deploy with confidence.** The test suite covers the features, not just the infrastructure.

---

## 16. Final Axioms

1. **If it isn't tested, it's broken.** You just haven't noticed yet.
2. **If it isn't rendered, it doesn't exist.** Data that doesn't reach the user's screen is worthless.
3. **If it can fail, it will.** Design for failure at every layer.
4. **If it's duplicated, it will diverge.** Extract shared logic or accept the inconsistency.
5. **If it's hardcoded, it will break.** Externalize configuration.
6. **If it runs on user input, it's an attack surface.** Validate, sanitize, isolate.
7. **If it's caught silently, it's undebuggable.** Log every exception.
8. **If the default works, the non-defaults are broken.** Test every path.

---

*This document was first created on 2026-06-13 after the DevStat codebase audit revealed 82 bugs that had survived integration testing. It should be reviewed and updated at the start of every new project phase or when a significant new lesson is learned.*
