"""HTTP checks against the practice database.

Creates one invoice and deletes only that invoice. Does not reseed.
"""
import warnings

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

warnings.filterwarnings("ignore")

from app.db import get_db
from app.main import app
from app.services import totals_match

CUSTOMER = "Audit Supplies LLC"
MARKER = "ui-audit-temp"


@pytest.fixture()
def client():
    db = get_db()
    if not db.name.endswith(("_practice", "_test")):
        pytest.skip("Refusing to write outside a practice database.")
    http = TestClient(app)
    http.cookies.set("tz_offset_minutes", "-240")
    before = db.invoices.count_documents({})
    northwind = db.invoices.find_one({"invoiceNumber": "INV-1001"})
    try:
        yield http
    finally:
        db.invoices.delete_many({"notes": MARKER})
        assert db.invoices.count_documents({}) == before
        kept = db.invoices.find_one({"invoiceNumber": "INV-1001"})
        assert kept["amountPaid"] == northwind["amountPaid"]
        assert kept["total"] == northwind["total"]


def test_filters_keep_each_criterion_and_clear_resets_them(client):
    narrowed = client.get("/invoices", params={"city": "Dubai", "status": "Overdue", "q": "books"})
    numbers = narrowed.text
    assert 'data-number="INV-1004"' in numbers
    assert 'data-number="INV-1015"' not in numbers
    assert 'data-number="INV-1005"' not in numbers
    cleared = client.get("/invoices")
    assert 'data-testid="filter-due"' in cleared.text
    assert 'name="due" value=""' in cleared.text or 'name="due" value=""' in cleared.text.replace("  ", " ")
    assert 'data-number="INV-1001"' in cleared.text
    assert "No invoices match" not in cleared.text


def test_saved_customer_replaces_typed_contact_and_payment_is_not_added(client):
    db = get_db()
    northwind = db.customers.find_one({"code": "C-01"})
    created = client.post("/invoices/new", data={
        "customer_id": str(northwind["_id"]),
        "customer_name": "Wrong Name",
        "customer_email": "wrong@auditsupplies.example",
        "issue_date": "2026-10-01",
        "due_date": "2026-11-01",
        "amount_paid": "10.00",
        "notes": MARKER,
        "description": "Shelf card",
        "quantity": "2",
        "unit_price": "15.00",
    }, follow_redirects=False)
    assert created.status_code == 303
    number = created.headers["location"].split("/")[-1].split("?")[0]
    stored = db.invoices.find_one({"invoiceNumber": number})
    assert stored["customerName"] == "Northwind Trading LLC"
    assert stored["customerEmail"] == "accounts@northwind.example"
    assert stored["customerId"] == northwind["_id"]
    assert stored["amountPaid"] == 10.0
    assert totals_match(stored)

    edited = client.post(f"/invoices/{number}/edit", data={
        "customer_name": stored["customerName"],
        "customer_email": stored["customerEmail"],
        "issue_date": stored["issueDate"],
        "due_date": stored["dueDate"],
        "amount_paid": "10.00",
        "notes": MARKER,
        "description": "Shelf card",
        "quantity": "2",
        "unit_price": "15.00",
    }, follow_redirects=True)
    assert f"Invoice {number} updated." in edited.text
    updated = db.invoices.find_one({"invoiceNumber": number})
    assert updated["amountPaid"] == 10.0
    assert updated["invoiceNumber"] == number
    assert db.invoices.count_documents({"invoiceNumber": number}) == 1

    clone = {key: value for key, value in updated.items() if key != "_id"}
    with pytest.raises(DuplicateKeyError):
        db.invoices.insert_one(clone)

    invalid = client.post("/invoices/new", data={
        "customer_name": CUSTOMER,
        "customer_email": "not-an-email",
        "issue_date": "2026-10-01",
        "due_date": "2026-09-01",
        "amount_paid": "1",
        "description": "Bad",
        "quantity": "1",
        "unit_price": "10",
    })
    assert invalid.status_code == 422
    assert "Due date must be on or after" in invalid.text
    assert db.invoices.find_one({"customerName": CUSTOMER, "customerEmail": "not-an-email"}) is None

    removed = client.post(f"/invoices/{number}/delete", follow_redirects=False)
    assert removed.status_code == 303
    assert db.invoices.find_one({"invoiceNumber": number}) is None
