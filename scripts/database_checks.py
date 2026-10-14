"""Database checks for the practice invoices. Read-only first, then rejected writes.

A temporary invoice is inserted only for the 'amount paid above the total' probe,
and that one document is deleted before the script finishes.
"""
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymongo.errors import DuplicateKeyError, WriteError

from app.db import get_db
from app.services import calendar_today, invoice_status, totals_match

failed = 0
today = calendar_today()


def check(name, ok, detail=""):
    global failed
    if not ok:
        failed += 1
        print(f"FAIL  {name}" + (f" — {detail}" if detail else ""))
    else:
        print(f"PASS  {name}" + (f" — {detail}" if detail else ""))


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


db = get_db()
if not db.name.endswith(("_practice", "_test")):
    sys.exit(f"Refusing to test '{db.name}': name must end with _practice or _test.")

before = db.invoices.count_documents({})
docs = list(db.invoices.find().sort("invoiceNumber", 1))
print(f"Database: {db.name}")
print(f"Today (UTC+4): {today}")
print(f"Invoices found: {before}\n")

check("DB-01 sixteen invoices", before == 16, f"found {before}")
names = set(db.list_collection_names())
check("DB-02 tender collections are gone", not names.intersection({"companies", "users", "tenders", "bids"}))

numbers = [doc["invoiceNumber"] for doc in docs]
check("DB-03 invoice numbers are unique", len(numbers) == len(set(numbers)), ", ".join(numbers))

bad_totals = [doc["invoiceNumber"] for doc in docs if not totals_match(doc)]
check("DB-04 stored total equals the sum of the lines", not bad_totals, ", ".join(bad_totals))

over_paid = [
    doc["invoiceNumber"] for doc in docs
    if money(doc["amountPaid"]) > money(doc["total"])
]
check("DB-05 amount paid is not above the total", not over_paid, ", ".join(over_paid))

bad_dates = [doc["invoiceNumber"] for doc in docs if doc["dueDate"] < doc["issueDate"]]
check("DB-06 due date is on or after the issue date", not bad_dates, ", ".join(bad_dates))

bad_lines = []
for doc in docs:
    for line in doc["lineItems"]:
        if int(line["quantity"]) < 1 or money(line["unitPrice"]) <= 0:
            bad_lines.append(doc["invoiceNumber"])
check("DB-07 quantities and prices are above zero", not bad_lines, ", ".join(bad_lines))

required = ["invoiceNumber", "customerName", "customerEmail", "issueDate", "dueDate", "currency", "lineItems", "total", "amountPaid", "notes", "createdAt", "updatedAt"]
missing = [doc["invoiceNumber"] for doc in docs if any(field not in doc for field in required)]
check("DB-08 required fields are present", not missing, ", ".join(missing))
check("DB-09 every currency is AED", all(doc["currency"] == "AED" for doc in docs))
check("DB-10 no stored status field", all("status" not in doc for doc in docs))

print("\nCalculated status:")
counts = {}
for doc in docs:
    status = invoice_status(money(doc["total"]), money(doc["amountPaid"]), doc["dueDate"], today)
    counts[status] = counts.get(status, 0) + 1
    balance = money(doc["total"]) - money(doc["amountPaid"])
    print(f"  {doc['invoiceNumber']}  {status:<15} due {doc['dueDate']}  paid {money(doc['amountPaid'])} of {money(doc['total'])}  balance {balance}")

check("DB-11 status counts are 4 / 4 / 4 / 4",
      counts.get("Unpaid") == 4 and counts.get("Partially Paid") == 4 and counts.get("Paid") == 4 and counts.get("Overdue") == 4,
      str(counts))

by_number = {doc["invoiceNumber"]: doc for doc in docs}
late = by_number.get("INV-1006")
check("DB-12 INV-1006 is paid even though the due date has passed",
      late is not None and late["dueDate"] < today and money(late["amountPaid"]) == money(late["total"]))
due_today = by_number.get("INV-1007")
check("DB-13 INV-1007 is due today and is not overdue",
      due_today is not None and due_today["dueDate"] == today and money(due_today["amountPaid"]) == 0)
palm = by_number.get("INV-1005")
check("DB-14 INV-1005 is partly paid and overdue",
      palm is not None and palm["dueDate"] < today and 0 < money(palm["amountPaid"]) < money(palm["total"]))
lumen = by_number.get("INV-1008")
check("DB-15 INV-1008 balance is 350.25",
      lumen is not None and money(lumen["total"]) - money(lumen["amountPaid"]) == Decimal("350.25"))

query_overdue = {doc["invoiceNumber"] for doc in db.invoices.find({
    "dueDate": {"$lt": today},
    "$expr": {"$lt": ["$amountPaid", "$total"]},
})}
python_overdue = {
    doc["invoiceNumber"] for doc in docs
    if invoice_status(money(doc["total"]), money(doc["amountPaid"]), doc["dueDate"], today) == "Overdue"
}
check("DB-16 Atlas overdue query matches the rule", query_overdue == python_overdue,
      f"query {sorted(query_overdue)} rule {sorted(python_overdue)}")

query_paid = {doc["invoiceNumber"] for doc in db.invoices.find({"$expr": {"$eq": ["$amountPaid", "$total"]}})}
python_paid = {
    doc["invoiceNumber"] for doc in docs
    if invoice_status(money(doc["total"]), money(doc["amountPaid"]), doc["dueDate"], today) == "Paid"
}
check("DB-17 Atlas paid query matches the rule", query_paid == python_paid,
      f"query {sorted(query_paid)} rule {sorted(python_paid)}")

indexes = list(db.invoices.list_indexes())
unique = [index["name"] for index in indexes if index.get("unique") and "invoiceNumber" in index.get("key", {})]
check("DB-18 unique index on invoiceNumber", unique == ["invoice_number_unique"], str(unique))

try:
    db.invoices.insert_one({"invoiceNumber": "INV-1001"})
    check("DB-19 validator rejects an incomplete invoice", False, "the insert was accepted")
except WriteError as exc:
    check("DB-19 validator rejects an incomplete invoice", exc.code == 121, f"code {exc.code}")

source = by_number["INV-1001"]
negative = {key: value for key, value in source.items() if key != "_id"}
negative["invoiceNumber"] = "INV-1098"
negative["amountPaid"] = -1
try:
    db.invoices.insert_one(negative)
    db.invoices.delete_one({"invoiceNumber": "INV-1098"})
    check("DB-20 validator rejects a negative amount paid", False, "the insert was accepted")
except WriteError as exc:
    check("DB-20 validator rejects a negative amount paid", True, f"code {exc.code}")

duplicate = {key: value for key, value in source.items() if key != "_id"}
try:
    db.invoices.insert_one(duplicate)
    db.invoices.delete_one({"invoiceNumber": "INV-1001", "_id": {"$ne": source["_id"]}})
    check("DB-21 unique index rejects a duplicate number", False, "the insert was accepted")
except DuplicateKeyError:
    check("DB-21 unique index rejects a duplicate number", True)

probe = {key: value for key, value in source.items() if key != "_id"}
probe.update({
    "invoiceNumber": "INV-1099",
    "customerName": "Database Probe LLC",
    "total": 10,
    "amountPaid": 50,
    "lineItems": [{"description": "Probe", "quantity": 1, "unitPrice": 10}],
    "createdAt": datetime.now(timezone.utc),
    "updatedAt": datetime.now(timezone.utc),
})
inserted = False
try:
    db.invoices.insert_one(probe)
    inserted = True
except WriteError as exc:
    check("DB-22 database upper bound on amount paid", False, f"rejected with code {exc.code}; the API is documented as the layer that enforces this")
if inserted:
    found = db.invoices.find_one({"invoiceNumber": "INV-1099"})
    check("DB-22 database allows amount paid above the total",
          found is not None and money(found["amountPaid"]) > money(found["total"]),
          "API rule only; test document removed after this check")
    db.invoices.delete_one({"invoiceNumber": "INV-1099"})

after = db.invoices.count_documents({})
check("DB-23 sample invoices are unchanged", after == before and db.invoices.find_one({"invoiceNumber": "INV-1099"}) is None,
      f"before {before}, after {after}")

print(f"\n{failed} failed")
sys.exit(1 if failed else 0)
