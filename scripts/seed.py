"""Replace the practice collections with fictional invoices.

This drops companies, users, tenders, bids, invoices and counters in the configured
database. It refuses to run unless the database name ends with _practice or _test.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_db
from app.schema import ensure_schema
from app.services import calendar_today, present, totals_match, validate

REMOVED = ["companies", "users", "tenders", "bids", "invoices", "counters", "customers"]

CUSTOMERS = [
    ("C-01", "Northwind Trading LLC", "accounts@northwind.example", "Dubai"),
    ("C-02", "Blue Harbor Cafe", "billing@blueharbor.example", "Abu Dhabi"),
    ("C-03", "Cedar Clinic", "accounts@cedarclinic.example", "Sharjah"),
    ("C-04", "Bright Books LLC", "orders@brightbooks.example", "Dubai"),
    ("C-05", "Palm Studio", "hello@palmstudio.example", "Ajman"),
    ("C-06", "Metro Supplies", "payables@metrosupplies.example", "Dubai"),
    ("C-07", "Harbor Tools", "desk@harbortools.example", "Ras Al Khaimah"),
    ("C-08", "Lumen Print", "jobs@lumenprint.example", "Dubai"),
]


def _day(today: str, offset: int) -> str:
    return (datetime.strptime(today, "%Y-%m-%d").date() + timedelta(days=offset)).isoformat()


def main() -> None:
    db = get_db()
    if not db.name.endswith(("_practice", "_test")):
        sys.exit(f"Refusing to seed '{db.name}': the name must end with _practice or _test.")
    for name in REMOVED:
        db.drop_collection(name)
    ensure_schema(db)

    today = calendar_today()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    people = {}
    for code, name, email, city in CUSTOMERS:
        inserted = db.customers.insert_one({"code": code, "name": name, "email": email, "city": city})
        people[code] = {"_id": inserted.inserted_id, "name": name, "email": email}

    samples = [
        ("INV-1001", "C-01", -10, 20, 0,
         [{"description": "Workshop facilitation", "quantity": 2, "unitPrice": 500}], ""),
        ("INV-1002", "C-02", -8, 10, 250,
         [{"description": "Menu design", "quantity": 3, "unitPrice": 250}], ""),
        ("INV-1003", "C-03", -20, 7, 300,
         [{"description": "Reception desk", "quantity": 1, "unitPrice": 300}], "Paid by bank transfer."),
        ("INV-1004", "C-04", -30, -12, 0,
         [{"description": "Shelf labels", "quantity": 1, "unitPrice": 450}], ""),
        ("INV-1005", "C-05", -20, -4, 400,
         [{"description": "Logo sketches", "quantity": 2, "unitPrice": 200},
          {"description": "Brand guide", "quantity": 1, "unitPrice": 600}], ""),
        ("INV-1006", "C-06", -40, -15, 200,
         [{"description": "Storage boxes", "quantity": 1, "unitPrice": 200}], "Paid after the due date."),
        ("INV-1007", "C-07", -2, 0, 0,
         [{"description": "Safety signs", "quantity": 1, "unitPrice": 80}], ""),
        ("INV-1008", "C-08", -3, 5, 100.25,
         [{"description": "Flyers", "quantity": 4, "unitPrice": 100},
          {"description": "Rush fee", "quantity": 1, "unitPrice": 50.50}], ""),
        ("INV-1009", "C-01", -5, 15, 200,
         [{"description": "Warehouse labels", "quantity": 1, "unitPrice": 800}], ""),
        ("INV-1010", "C-01", -60, -20, 500,
         [{"description": "Archive boxes", "quantity": 2, "unitPrice": 750}], ""),
        ("INV-1011", "C-02", -15, -3, 400,
         [{"description": "Menu reprint", "quantity": 1, "unitPrice": 400}], "Paid after the due date."),
        ("INV-1012", "C-03", -6, 12, 0,
         [{"description": "Waiting-room posters", "quantity": 2, "unitPrice": 150}], ""),
        ("INV-1013", "C-04", -4, 8, 100,
         [{"description": "Bookmark set", "quantity": 1, "unitPrice": 400}], ""),
        ("INV-1014", "C-05", -1, 30, 0,
         [{"description": "Poster", "quantity": 1, "unitPrice": 90}], ""),
        ("INV-1015", "C-06", -9, -1, 0,
         [{"description": "Packing tape", "quantity": 5, "unitPrice": 40}], ""),
        ("INV-1016", "C-08", -12, 2, 220,
         [{"description": "Business cards", "quantity": 2, "unitPrice": 110}], ""),
    ]
    docs = []
    for index, (number, code, issued, due, paid, lines, notes) in enumerate(samples, start=1):
        person = people[code]
        doc = validate({
            "customerName": person["name"], "customerEmail": person["email"],
            "issueDate": _day(today, issued), "dueDate": _day(today, due),
            "amountPaid": paid, "notes": notes, "lineItems": lines,
        })
        doc.update({
            "invoiceNumber": number,
            "customerId": person["_id"],
            "createdAt": now - timedelta(days=len(samples) - index),
            "updatedAt": now - timedelta(days=len(samples) - index),
        })
        if not totals_match(doc):
            sys.exit(f"{number} total does not match its lines.")
        docs.append(doc)
    db.invoices.insert_many(docs)
    db.counters.insert_one({"_id": "invoice", "seq": len(docs)})

    print(f"Seeded database '{db.name}' on {today}:")
    counts = {}
    for doc in db.invoices.find():
        status = present(doc, today)["status"]
        counts[status] = counts.get(status, 0) + 1
        print(f"  {doc['invoiceNumber']}  {status}")
    print("Counts:", counts)


if __name__ == "__main__":
    main()
