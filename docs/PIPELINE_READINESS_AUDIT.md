# Invoice Tracker — Pipeline Readiness Audit

Audit date: 15 Oct 2026 · Branch: `qa/invoice-checks` at `685a571` · Auditor: Kristina (QA), with AI mentor

## 1. Executive summary

**Readiness: Ready with risks.**

The pipeline (`.github/workflows/invoice-checks.yml`) runs `python -m pytest tests/test_rules.py -q`. In a clean
copy of the branch with a fresh virtual environment and no `.env`, that command passed (14 tests, exit 0), and a
deliberately failing test made it exit 1, so a red build will really show red.

The pipeline itself has **not** been seen running on GitHub yet (no Actions URL available, `gh` not installed,
private repository). That row is `NOT RUN` until the developer opens the pull request.

Main risks:

1. The pipeline checks only the business rules. Pages, API and database code are never started in CI.
2. Two browser checks can change practice data if the app breaks (one could delete a real invoice).
3. Some checks depend on today's date and on the live practice data, so they will start failing on their own.

No secrets were found in tracked files or Git history. No reseed or drop was run. One unplanned database run happened
during fix verification; see section 7.

**After fixes (section 6):** the pipeline now also compiles all code and checks every route and template without a
database. 48 checks pass in CI mode. Findings F-01 to F-04, F-06 to F-08, F-12, F-13 and F-15 are fixed. F-05, F-09,
F-10, F-11, F-14 and F-16 remain open.

## 2. What was checked and how

All checks ran on the local machine. "Clean copy" means `git archive HEAD` extracted to a temporary folder with a new
virtual environment installed from `requirements.txt` and no `.env` file, which is what GitHub Actions sees.

| # | Check | Command (from the clean copy unless stated) | Result | Evidence |
|---|-------|---------------------------------------------|--------|----------|
| 1 | Git state | `git status`, `git log`, `git branch -vv` | PASS | Clean tree; `main` and `qa/invoice-checks` in sync with origin |
| 2 | Secrets in Git | search of tracked files and history for `.env`, `mongodb+srv`, passwords, tokens | PASS | `.env` never committed; no connection string in tracked files |
| 3 | Fresh install | `python -m venv .venv` then `pip install -r requirements.txt` | PASS | Installed; resolved fastapi 0.143.1, pymongo 4.19.0 (local has 0.143.0, 4.18.3) |
| 4 | Dependency conflicts | `python -m pip check` | PASS | "No broken requirements found." |
| 5 | Syntax of all code | `python -m compileall -q app scripts tests` | PASS | exit 0 |
| 6 | Pipeline command | `python -m pytest tests/test_rules.py -q` | PASS | 14 passed, exit 0 |
| 7 | Bare `pytest` | `pytest tests/test_rules.py -q` | FAIL | `ModuleNotFoundError: No module named 'tests'`, exit 4 (finding F-07) |
| 8 | All modules import without a database | `python -c "import app.main, app.web, app.api, app.checks, app.schema"` | PASS | "imports ok"; nothing connects at import |
| 9 | App start with no `.env` | start `app.main` through `TestClient` | PASS | Fails clearly: `RuntimeError: MONGODB_URI is missing...` (no secret printed) |
| 10 | A failing test turns the run red | temporary `test_zz_controlled_fail.py` (`assert 1 + 1 == 3`) in the clean copy only, then deleted | PASS | 1 failed, 14 passed, exit 1; file removed afterwards |
| 11 | Test discovery | `python -m pytest --collect-only -q` | PASS | 31 tests collected (14 rules, 15 browser, 2 flow) |
| 12 | Whole suite without `.env` | `python -m pytest -q` | FAIL | 29 passed, 2 errors (`test_flow.py` cannot find `MONGODB_URI`), exit 1 (finding F-06) |
| 13 | Browser checks with no server (CI situation) | `python -m pytest tests/test_browser.py --base-url http://127.0.0.1:8765` | FAIL | 15 failed, exit 1 (finding F-06) |
| 14 | Browser checks against the local app | ran as part of check 12, against the app already running on port 8000 | PASS | 15 passed; read-only check 15 confirms no data changed |
| 15 | Practice data unchanged | read-only `GET /api/invoices` | PASS | 18 invoices; INV-1001 paid 100; INV-1017 present; 0 leftover test invoices |
| 16 | Unknown filter values | read-only `GET /api/invoices?city=Paris` and `?customer=not-an-id` | FAIL | Both return all 18 invoices (finding F-09) |
| 17 | Database flow tests (`test_flow.py`) against MongoDB | not run | NOT RUN | Writes to the shared practice database; needs approval (finding F-05) |
| 18 | Pipeline on GitHub Actions | not run | NOT RUN | No pull request run available to inspect yet |
| 19 | Separate test database | none exists | BLOCKED | Needs a `mini_tender_test` database or user permission decision |

## 3. Findings

Severity: Critical, High, Medium, Low. "Reproduced" means a check in section 2 showed it; "Potential" means it was
found by reading the code and has not been triggered.

### F-01 · High · CI coverage · `.github/workflows/invoice-checks.yml`

- **What:** The pipeline runs only `tests/test_rules.py`, which imports `app.services` and `app.db`.
- **Why it matters:** A mistake in `app/web.py`, `app/api.py`, `app/main.py`, `app/checks.py`, `app/schema.py`, the
  templates or `scripts/` would still give a green build.
- **How it fails:** A developer breaks an import in `app/api.py`; CI passes; the app does not start for anyone.
- **Evidence:** Checks 5 and 8 show that compiling and importing every module works without a database, so CI could
  run them cheaply but currently does not.
- **Fix:** Add `python -m compileall -q app scripts tests` and a no-database test that imports `app.main` and checks
  the expected routes exist.
- **Status:** Potential.

### F-02 · High · Data safety · `tests/test_browser.py:161-172`, `app/static/app.js:106-113`

- **What:** test_14 clicks a real Delete button and relies on `app.js` showing a confirm box that the test dismisses.
- **Why it matters:** If `app.js` fails to load or the `data-confirm` code breaks, the click submits the form and
  **deletes a real practice invoice**.
- **Fix:** Inside the test, block the delete request with `page.route("**/delete", lambda r: r.abort())` so no delete
  can reach the server even if the dialog breaks.
- **Status:** Potential. Not triggered (check 15 shows nothing was deleted).

### F-03 · High · Test reliability · `tests/test_browser.py:54-61`

- **What:** test_03 needs at least one invoice that is Unpaid today. Status depends on the date, and the practice
  data is not reseeded.
- **Evidence (check 15):** INV-1007 turned Overdue on 15 Oct. Only INV-1012 (due 26 Oct) and INV-1014 (due 13 Nov)
  are still Unpaid.
- **How it fails:** From 14 Nov 2026 (Dubai time) test_03 fails with no code change. test_06 (INV-1001),
  test_12 (Northwind label) and test_15 (Dubai + Overdue rows) also depend on live data.
- **Fix:** Have the test pick its expectations from the API first, or skip with a clear message when no Unpaid invoice
  exists. Longer term, run browser checks against a seeded test database.
- **Status:** Reproduced partly (data shown); failure date predicted.

### F-04 · Medium · Data safety · `tests/test_browser.py:124-140`

- **What:** test_10 and test_11 submit invalid invoices (customer "PW Check Supplies LLC") and expect the server to
  refuse them.
- **How it fails:** If server validation breaks, the invoice is saved, the test fails, and the invoice stays in
  practice data, consuming an invoice number.
- **Fix:** Add a fixture that deletes any "PW Check" invoice afterwards through the API.
- **Status:** Potential. Check 15 found 0 leftovers.

### F-05 · Medium · Database isolation · `tests/test_flow.py:24-25, 56-112`

- **What:** test_flow creates, edits and deletes an invoice in the **shared practice database**. Its guard only checks
  that the name ends with `_practice` or `_test`, and the practice database passes.
- **Why it matters:** Each run consumes invoice numbers permanently, and a crash between create and cleanup would leave
  data behind. The live list jumps from INV-1017 to INV-1020, which matches numbers being consumed.
- **Fix:** Point database tests at a separate `mini_tender_test` database, for example with an env variable
  `MONGODB_TEST_DB` that the test requires, and refuse `mini_tender_practice`.
- **Status:** Potential. Not run in this audit.

### F-06 · Medium · Test setup · `pytest.ini`, `tests/test_flow.py`, `tests/test_browser.py`

- **What:** There are no markers or `testpaths` that separate rule, database and browser tests.
- **Evidence:** Checks 12 and 13: plain `python -m pytest` errors on the database tests and fails all 15 browser tests
  when there is no `.env` or server, instead of skipping with a clear reason.
- **How it fails:** If someone widens the CI command to `pytest`, the pipeline goes red for setup reasons, not bugs.
- **Fix:** Add markers `db` and `browser`, skip them with a clear message when `MONGODB_URI` or the server is missing,
  and keep CI on `-m "not db and not browser"` until a test database exists.
- **Status:** Reproduced.

### F-07 · Medium · Test setup · `pytest.ini`

- **What:** `pytest` on its own cannot import `tests.qa_report` (check 7, exit 4). Only `python -m pytest` works.
- **Fix:** Add `pythonpath = .` to `pytest.ini`.
- **Status:** Reproduced.

### F-08 · Medium · Reproducible builds · `requirements.txt`

- **What:** Every dependency uses `>=`.
- **Evidence:** Check 3: a fresh install today already picks newer FastAPI and PyMongo than the local machine. CI also
  installs Playwright, which the rules job does not use. A `StarletteDeprecationWarning` about httpx appears.
- **Fix:** Pin exact versions, or add a `requirements-lock.txt` from `pip freeze` for CI.
- **Status:** Reproduced (version drift).

### F-09 · Medium · Application logic · `app/services.py:284-292`

- **What:** An unknown city, or a customer id that is not valid, is silently ignored, so the list shows **all**
  invoices.
- **Evidence:** Check 16: `?city=Paris` and `?customer=not-an-id` each return all 18.
- **Why it matters:** A user who filters for a city with no data sees every invoice and may think they are filtered.
- **Fix:** Return an empty list for an unknown value, or show a "filter not recognised" message. This needs a product
  decision.
- **Status:** Reproduced.

### F-10 · Medium · Error handling · `app/services.py:347-360`, `app/main.py:27-34`

- **What:** `create_invoice` takes a number from the counter first, then inserts. A duplicate number or a MongoDB
  validator rejection is not caught.
- **How it fails:** A plain "Internal Server Error" instead of a clear message, and the invoice number is used up.
  Connection errors are also a generic 500.
- **Fix:** Catch `DuplicateKeyError` and `WriteError` and turn them into a friendly error; add a handler for
  `PyMongoError`.
- **Status:** Potential.

### F-11 · Medium · Destructive scripts · `scripts/seed.py:36-39`, `scripts/ui_walk.py:32,148`, `scripts/ten_queries.py:45`

- **What:** These scripts drop collections and reseed. Their only guard is the database name, which the practice
  database passes. `ui_walk.py` and `ten_queries.py` call the seed without saying so.
- **How it fails:** Running one of them wipes the practice invoices, including the INV-1001 edit and INV-1017.
- **Fix:** Require an explicit flag (for example `--yes-wipe mini_tender_practice`) and print what will be dropped.
- **Status:** Potential. Not run.

### F-12 · Low · Hidden warnings · `tests/test_flow.py:11`

- **What:** `warnings.filterwarnings("ignore")` at import hides warnings for the whole run, not only this file.
- **Fix:** Remove it, or use `pytest.mark.filterwarnings` for the specific warning.
- **Status:** Potential.

### F-13 · Low · Pipeline hygiene · `.github/workflows/invoice-checks.yml`

- **What:** The workflow has no `permissions: contents: read`, no `timeout-minutes`, no pip cache, and no test-report
  artifact.
- **Fix:** Add these four. A JUnit XML (`--junitxml=results.xml`) uploaded as an artifact gives the reviewer a file to
  open.
- **Status:** Potential.

### F-14 · Low · Application logic · `app/services.py:300, 381`

- **What:** Invoices sort by number as text, so INV-10000 would sort before INV-2000. `update_invoice` does not check
  that `replace_one` matched a document.
- **Status:** Potential. Not reachable with current data.

### F-15 · Low · Test gaps · `tests/test_rules.py`

- **What:** These edge cases are not covered (an invoice due exactly today is already covered):
  - quantity 10000 or "1.5"
  - price over 1,000,000, or with 3 decimals
  - the date "2026-02-30"
  - 11 lines
  - a currency other than AED
  - `parse_offset`
- **Fix:** Add parametrized cases. They are pure, safe, and run in CI.
- **Status:** Potential.

### F-16 · Low · Naming · `app/checks.py`

- **What:** The `/queries` page compares database answers with the service function, not with the rendered page. Q-10
  is hardcoded to INV-1008. The browser test name "screens agree" overstates what is compared.
- **Status:** Potential.

### What is already good

- No secrets in tracked files or history; `.env` is ignored and `.env.example` has placeholders only.
- The pipeline fails when a test fails (check 10), and there is no `continue-on-error`.
- CI Python 3.12 matches local Python 3.12.4.
- `test_rules.py` uses a fixed TODAY, so its results do not change with the date.
- Missing configuration fails with a clear message and no secret (check 9).
- Status and money rules match `docs/REQUIREMENTS.md` in the cases tested.

## 4. Prioritised action plan

| Order | Finding | Change | Touches data? | Size |
|-------|---------|--------|---------------|------|
| 1 | F-02 | Block delete requests inside test_14 | No | Small |
| 2 | F-01, F-13 | Workflow: compileall, import smoke test, permissions, timeout, JUnit artifact | No | Small |
| 3 | F-07, F-06, F-12 | `pythonpath = .`, markers, clear skips, remove global warnings ignore | No | Small |
| 4 | F-03, F-04 | Make test_03 date-proof; cleanup fixture for test_10/11 | No | Small |
| 5 | F-08 | Pin versions or add a lock file for CI | No | Small |
| 6 | F-15 | Add missing rule edge cases | No | Small |
| 7 | F-05 | Separate `mini_tender_test` database for test_flow | Creates a new database; needs approval | Medium |
| 8 | F-11 | Confirmation flag on destructive scripts | No (adds safety) | Small |
| 9 | F-09, F-10 | App behaviour fixes with regression tests | Changes app behaviour; needs product decision | Medium |
| 10 | F-14, F-16 | Low-priority clean-ups | No | Small |

## 5. Blockers

- **GitHub Actions run:** not visible from this machine. Ask the developer for the Actions run link on the pull request
  from `qa/invoice-checks` to `main`.
- **Test database:** none exists. Creating `mini_tender_test` needs a decision from the database owner. The
  `mtb_app_dev` user currently has rights on the practice database only.

## 6. Fixes made (approved: action plan steps 1–6)

| Finding | Change | File |
|---------|--------|------|
| F-02 | test_14 blocks every `/invoices/*/delete` request, so no delete can reach the server even if the dialog breaks | `tests/test_browser.py` |
| F-01 | New no-database checks: each of the 14 routes answers (not 404/405), an unknown page is 404, all 6 templates compile. `get_db` is replaced with a function that refuses to connect | `tests/test_app_loads.py` |
| F-01, F-13 | Workflow: `permissions: contents: read`, 10-minute timeout, pip cache, `compileall`, runs every non-db, non-browser test, uploads `junit.xml` | `.github/workflows/invoice-checks.yml` |
| F-06, F-07 | `pythonpath = .`, `testpaths`, strict `browser` and `db` markers | `pytest.ini` |
| F-06 | Browser checks skip with "Invoice Tracker is not running" when the app is down; database checks skip when `MONGODB_URI` is missing | `tests/test_browser.py`, `tests/test_flow.py` |
| F-12 | Removed the global `warnings.filterwarnings("ignore")` | `tests/test_flow.py` |
| F-03 | test_03 and test_15 read the full list first and expect exactly those invoices after filtering (empty state if none). test_06 searches the first listed invoice instead of INV-1001 | `tests/test_browser.py` |
| F-04 | test_10 and test_11 remove any invoice saved under "PW Check Supplies LLC" afterwards, through the API, by exact customer name | `tests/test_browser.py` |
| F-08 | Exact versions pinned to the versions tested locally | `requirements.txt` |
| F-15 | 7 new rejection cases, the largest allowed quantity and price, 5 `parse_offset` cases | `tests/test_rules.py` |

No application code was changed.

### Results after fixes (local, 15 Oct 2026)

| Check | Command | Result | Evidence |
|-------|---------|--------|----------|
| Compile | `python -m compileall -q app scripts tests` | PASS | exit 0 |
| CI command | `python -m pytest -m "not db and not browser" -q -rs --junitxml=test-results/junit.xml` | PASS | 48 passed, 17 deselected, exit 0 |
| Bare `pytest` | `pytest tests/test_rules.py -q` | PASS | 27 passed (was exit 4) |
| Delete guard works | temporary probe test: submitted a delete form aimed at the non-existent INV-0000 with the guard on, then deleted the probe | PASS | Request intercepted and aborted; 1 passed |
| Browser checks, app running | `python -m pytest -m browser -q` | PASS | 15 passed (run twice) |
| Browser checks, no app | same with `--base-url http://127.0.0.1:8765` | PASS | 15 skipped with a clear reason (was 15 failed) |
| Database checks, no credentials | `MONGODB_URI` set to a placeholder, `python -m pytest -m db -rs` | PASS | 2 skipped with the missing-setting message (was 2 errors) |
| Practice data unchanged | read-only `GET /api/invoices` | PASS | 18 invoices; INV-1001 paid 100; INV-1017 present; 0 "PW Check" invoices |
| Pipeline on GitHub Actions | push to `qa/invoice-checks`, open the pull request | NOT RUN | Needs the Actions run link |

## 7. Incident during verification

While checking that database tests skip without credentials, `MONGODB_URI` was set to an empty string in PowerShell.
PowerShell removes a variable set to an empty string, so the app loaded `.env` and `tests/test_flow.py` ran against
`mini_tender_practice` without prior approval.

- What it did: created one temporary invoice (notes `ui-audit-temp`), edited it, deleted it. Both checks passed.
- Effect checked afterwards: invoice count 18 (unchanged), INV-1001 paid 100 (unchanged), INV-1017 present, 0 invoices
  with `ui-audit-temp`.
- Lasting effect: the invoice counter moved to 21, so INV-1021 is used up and the next new invoice will be INV-1022.
- Prevention: the skip check was re-run with a placeholder value that `app/db.py` refuses before connecting, verified
  first with a separate one-line check. Finding F-05 (separate test database) would stop this class of mistake.
