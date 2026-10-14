"""Exercise the invoice pages, API and database rules. Rewrites the practice data at the end."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import warnings
warnings.filterwarnings("ignore")

from pymongo.errors import DuplicateKeyError, WriteError
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.services import totals_match
from scripts.seed import main as seed_main

failed = 0


def check(name, ok, detail=""):
    global failed
    if not ok:
        failed += 1
        print(f"FAIL  {name} — {detail}")
    else:
        print(f"PASS  {name}")


def run():
    seed_main()
    db = get_db()
    client = TestClient(app)
    client.cookies.set("tz_offset_minutes", "-240")

    names = set(db.list_collection_names())
    check("old tender collections removed", not names.intersection({"companies", "users", "tenders", "bids"}))
    check("sixteen invoices", db.invoices.count_documents({}) == 16)
    check("stored totals match lines", all(totals_match(doc) for doc in db.invoices.find()))
    try:
        db.invoices.insert_one({"invoiceNumber": "INV-1001"})
        check("database rejects an incomplete invoice", False, "insert succeeded")
    except WriteError:
        check("database rejects an incomplete invoice", True)
    original = db.invoices.find_one({"invoiceNumber": "INV-1001"})
    clone = {key: value for key, value in original.items() if key != "_id"}
    try:
        db.invoices.insert_one(clone)
        check("duplicate invoice number rejected", False, "insert succeeded")
        db.invoices.delete_one({"invoiceNumber": "INV-1001", "_id": {"$ne": original["_id"]}})
    except DuplicateKeyError:
        check("duplicate invoice number rejected", True)

    check("stylesheet", client.get("/static/app.css").status_code == 200)
    check("home redirects", client.get("/", follow_redirects=False).headers["location"] == "/invoices")
    page = client.get("/invoices")
    check("list has 16", page.status_code == 200 and page.text.count('data-testid="invoice-row"') == 16)
    overdue = client.get("/invoices?status=Overdue")
    overdue_numbers = set(re.findall(r'data-number="(INV-\d+)"', overdue.text))
    check("overdue filter", overdue_numbers == {"INV-1004", "INV-1005", "INV-1010", "INV-1015"}, str(sorted(overdue_numbers)))
    paid = client.get("/invoices?status=Paid")
    paid_numbers = set(re.findall(r'data-number="(INV-\d+)"', paid.text))
    check("paid includes the late payment", paid_numbers == {"INV-1003", "INV-1006", "INV-1011", "INV-1016"}, str(sorted(paid_numbers)))
    harbor = client.get("/invoices?q=harbor")
    check("search is case-insensitive", harbor.text.count('data-testid="invoice-row"') == 3)
    narrowed = client.get("/invoices?q=harbor&status=Unpaid")
    narrowed_numbers = re.findall(r'data-number="(INV-\d+)"', narrowed.text)
    check("search and filter together", narrowed_numbers == ["INV-1007"], str(narrowed_numbers))
    check("no matches", 'data-testid="empty"' in client.get("/invoices?q=zzzz-not-a-customer").text)
    nasty = client.get("/invoices?notice=saved&number=<script>alert(1)</script>")
    check("notice is not echoed", "<script>" not in nasty.text)

    late = client.get("/invoices/INV-1006")
    check("paid late stays Paid", 'data-testid="invoice-status">Paid' in late.text and "before today" not in late.text)
    partial_late = client.get("/invoices/INV-1005")
    check("partial past due is Overdue", "Overdue" in partial_late.text and "400.00" in partial_late.text and "600.00" in partial_late.text)
    due_today = client.get("/invoices/INV-1007")
    check("due today is Unpaid", 'data-testid="invoice-status">Unpaid' in due_today.text)
    decimals = client.get("/invoices/INV-1008")
    check("balance is total minus paid", 'data-testid="balance">350.25' in decimals.text)
    missing = client.get("/invoices/INV-9999")
    check("missing invoice is 404", missing.status_code == 404 and "INV-9999" not in missing.text)

    form = client.get("/invoices/new")
    check("new form", 'data-testid="customer-name"' in form.text and 'data-testid="add-line"' in form.text)
    kept = client.post("/invoices/new", data={
        "customer_name": "A <b>bold</b> name", "customer_email": "not-an-email",
        "issue_date": "2026-10-01", "due_date": "2026-09-01", "amount_paid": "nan",
        "description": "", "quantity": "0", "unit_price": "10.005",
    })
    check("invalid form kept and escaped", kept.status_code == 422 and "<b>" not in kept.text and "&lt;b&gt;" in kept.text
          and "Due date must be on or after" in kept.text and "at most 2 decimal places" in kept.text)
    check("invalid form did not save", db.invoices.count_documents({}) == 16)

    created = client.post("/invoices/new", data={
        "customer_name": "Quiz Supplies LLC", "customer_email": "accounts@quizsupplies.example",
        "issue_date": "2026-10-01", "due_date": "2026-11-01", "amount_paid": "10.50", "notes": "Window test",
        "description": ["Window lettering", "Install"], "quantity": ["2", "1"], "unit_price": ["25.00", "40"],
    }, follow_redirects=False)
    check("create redirects", created.status_code == 303 and "INV-1017" in created.headers["location"])
    opened = client.get(created.headers["location"])
    check("saved notice and total", "Invoice INV-1017 saved." in opened.text and 'data-testid="total">90.00' in opened.text)
    stored = db.invoices.find_one({"invoiceNumber": "INV-1017"})
    check("database matches the page", stored and stored["customerName"] == "Quiz Supplies LLC" and totals_match(stored)
          and stored["amountPaid"] == 10.5 and stored["invoiceNumber"] == "INV-1017")

    edited = client.post("/invoices/INV-1017/edit", data={
        "customer_name": "Quiz Supplies LLC", "customer_email": "accounts@quizsupplies.example",
        "issue_date": "2026-10-01", "due_date": "2026-11-01", "amount_paid": "90",
        "description": "Window lettering", "quantity": "2", "unit_price": "45",
    }, follow_redirects=True)
    check("edit can mark it paid", "Invoice INV-1017 updated." in edited.text and 'data-testid="invoice-status">Paid' in edited.text)
    check("edit keeps the number", db.invoices.count_documents({"invoiceNumber": "INV-1017"}) == 1)

    removed = client.post("/invoices/INV-1017/delete", follow_redirects=False)
    check("delete redirects", removed.status_code == 303)
    check("deleted invoice is gone", db.invoices.find_one({"invoiceNumber": "INV-1017"}) is None
          and db.invoices.find_one({"invoiceNumber": "INV-1001"}) is not None)
    check("unknown delete is 404", client.post("/invoices/INV-9999/delete").status_code == 404)

    api = client.get("/api/invoices")
    check("api list", api.status_code == 200 and api.json()["counts"]["Overdue"] == 4 and len(api.json()["invoices"]) == 16)
    high = client.post("/api/invoices", json={
        "customerName": "Too Much LLC", "customerEmail": "a@too.example", "issueDate": "2026-10-01",
        "dueDate": "2026-10-20", "amountPaid": 50, "currency": "USD",
        "lineItems": [{"description": "Item", "quantity": 1, "unitPrice": 10}],
    })
    check("api rejects another currency and a high payment", high.status_code == 422 and db.invoices.find_one({"customerName": "Too Much LLC"}) is None)
    many = [{"description": f"Line {i}", "quantity": 1, "unitPrice": 1} for i in range(11)]
    check("api rejects 11 lines", client.post("/api/invoices", json={
        "customerName": "Many Lines LLC", "customerEmail": "a@many.example", "issueDate": "2026-10-01",
        "dueDate": "2026-10-02", "lineItems": many,
    }).status_code == 422)
    changed = client.put("/api/invoices/INV-1002", json={
        "customerName": "Blue Harbor Cafe", "customerEmail": "billing@blueharbor.example",
        "issueDate": db.invoices.find_one({"invoiceNumber": "INV-1002"})["issueDate"],
        "dueDate": db.invoices.find_one({"invoiceNumber": "INV-1002"})["dueDate"],
        "amountPaid": 250, "lineItems": [{"description": "Menu design", "quantity": 3, "unitPrice": 250}],
    })
    check("api update keeps INV-1002", changed.status_code == 200 and changed.json()["invoiceNumber"] == "INV-1002")


if __name__ == "__main__":
    try:
        run()
    finally:
        seed_main()
    print(f"\n{failed} failed")
    sys.exit(1 if failed else 0)
