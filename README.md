# Invoice Tracker

A small practice app for database, API and UI testing. Fictional customers only. Not connected to Fortender.

The folder is still named `mini-tender-bid`. The tender app that used to live here has been removed.

## Stack

Python, FastAPI, PyMongo, and MongoDB Atlas. The pages and the JSON API use the same rules in `app/services.py`.

## Setup

1. Copy `.env.example` to `.env` and set `MONGODB_URI`. Never commit `.env`.
2. `MONGODB_DB` must be a practice database whose name ends with `_practice` or `_test`. The Atlas user `mtb_app_dev` can write to `mini_tender_practice`, so that is the database this project uses.
3. Install and check the connection:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python scripts\check_connection.py
```

4. Load fictional invoices. This **drops** `companies`, `users`, `tenders`, `bids`, `invoices`, `counters` and `customers` in that database, then loads 8 customers and 16 invoices:

```powershell
.\.venv\Scripts\python scripts\seed.py
```

## Run

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

- Pages: http://127.0.0.1:8000
- Query checks: http://127.0.0.1:8000/queries
- API try-it page: http://127.0.0.1:8000/docs

There is no login. Anyone who can open the site can change the practice invoices.

## Rules

Status is calculated, not typed:

| Status | When |
|---|---|
| Paid | Amount paid equals the total |
| Overdue | Not fully paid, and the due date is before today |
| Partially Paid | Some money has been received, and the due date is today or later |
| Unpaid | Nothing has been received, and the due date is today or later |

Today follows your computer's timezone. The practice data is built for UTC+4.

Details are in `docs/REQUIREMENTS.md`, `docs/DATABASE_SCHEMA.md` and `docs/TEST_DATA.md`.

## Browser checks

Fifteen critical checks live in `tests/test_browser.py`. They use Playwright through pytest. The app must already be running at http://127.0.0.1:8000. These checks do not create, edit, or delete an invoice.

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m playwright install chromium
.\.venv\Scripts\python -m pytest tests/test_browser.py --browser chromium
```

Every test run writes a report to `test-report/index.html`, covering whichever tests ran. Open that file in a browser. It is not committed. On GitHub, the same summary appears on the run page and the report is attached to the run as **test-report**.

PowerShell does not recognize a bare `playwright` command. Use the `python -m playwright` line above. That downloads Chromium into `%LOCALAPPDATA%\ms-playwright`.

## Test groups

Tests are marked so each group can run on its own:

```powershell
.\.venv\Scripts\python -m pytest -m "not db and not browser"   # rules, routes, templates; what CI runs
.\.venv\Scripts\python -m pytest -m browser                     # needs the app running
.\.venv\Scripts\python -m pytest -m db                          # writes one temporary invoice to the database in .env
```

Browser checks skip when the app is not running. Database checks skip when `MONGODB_URI` is not set. The `db` group creates, edits and deletes one invoice, which uses up one invoice number.
