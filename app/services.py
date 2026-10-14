"""Invoice rules. Status is calculated here and nowhere else."""
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument

from app.db import get_db

STATUSES = ["Unpaid", "Partially Paid", "Paid", "Overdue"]
# Practice machine is UTC+4. The browser sends the same offset in a cookie.
DEFAULT_OFFSET_MINUTES = -240
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
INVOICE_NUMBER = re.compile(r"^INV-\d+$")
MAX_PRICE = Decimal("1000000")
TWOPLACES = Decimal("0.01")


class AppError(Exception):
    def __init__(self, status: int, messages):
        self.status = status
        self.messages = [messages] if isinstance(messages, str) else list(messages)

    @property
    def message(self) -> str:
        return self.messages[0]


def calendar_today(offset_minutes: int = DEFAULT_OFFSET_MINUTES) -> str:
    local = datetime.now(timezone.utc) - timedelta(minutes=offset_minutes)
    return local.date().isoformat()


def parse_offset(value) -> int:
    try:
        offset = int(value)
    except (TypeError, ValueError):
        return DEFAULT_OFFSET_MINUTES
    if abs(offset) > 14 * 60:
        return DEFAULT_OFFSET_MINUTES
    return offset


def money_text(value) -> str:
    return f"{Decimal(str(value)).quantize(TWOPLACES):,.2f}"


def _decimal(value, label: str, errors: list[str]) -> Decimal | None:
    if isinstance(value, bool) or value is None or str(value).strip() == "":
        errors.append(f"{label} is required.")
        return None
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation:
        errors.append(f"{label} must be a number.")
        return None
    if not number.is_finite():
        errors.append(f"{label} must be a number.")
        return None
    if number.as_tuple().exponent < -2:
        errors.append(f"{label} can have at most 2 decimal places.")
        return None
    return number.quantize(TWOPLACES)


def invoice_status(total: Decimal, amount_paid: Decimal, due_date: str, today: str) -> str:
    if amount_paid == total:
        return "Paid"
    if due_date < today:
        return "Overdue"
    if amount_paid > 0:
        return "Partially Paid"
    return "Unpaid"


def status_reason(invoice: dict) -> str:
    if invoice["status"] == "Paid":
        return "Paid, because the amount received equals the total."
    if invoice["status"] == "Overdue":
        return (
            f"Overdue, because the due date {invoice['dueDate']} is before today "
            f"and {invoice['balanceText']} AED is still unpaid."
        )
    if invoice["status"] == "Partially Paid":
        return (
            f"Partially paid: {invoice['amountPaidText']} AED of {invoice['totalText']} AED "
            "has been received, and the due date is today or later."
        )
    return f"Unpaid. Nothing has been received yet. Due {invoice['dueDate']}."


def present(doc: dict, today: str) -> dict:
    total = Decimal(str(doc["total"])).quantize(TWOPLACES)
    paid = Decimal(str(doc["amountPaid"])).quantize(TWOPLACES)
    lines = []
    for line in doc["lineItems"]:
        qty = int(line["quantity"])
        price = Decimal(str(line["unitPrice"])).quantize(TWOPLACES)
        amount = (price * qty).quantize(TWOPLACES)
        lines.append({
            "description": line["description"],
            "quantity": qty,
            "unitPrice": float(price),
            "unitPriceText": f"{price:,.2f}",
            "amount": float(amount),
            "amountText": f"{amount:,.2f}",
        })
    balance = (total - paid).quantize(TWOPLACES)
    status = invoice_status(total, paid, doc["dueDate"], today)
    view = {
        "id": str(doc["_id"]),
        "invoiceNumber": doc["invoiceNumber"],
        "customerId": str(doc["customerId"]) if doc.get("customerId") else "",
        "customerName": doc["customerName"],
        "customerEmail": doc["customerEmail"],
        "city": "",
        "issueDate": doc["issueDate"],
        "dueDate": doc["dueDate"],
        "currency": doc["currency"],
        "lineItems": lines,
        "total": float(total),
        "totalText": f"{total:,.2f}",
        "amountPaid": float(paid),
        "amountPaidText": f"{paid:,.2f}",
        "balance": float(balance),
        "balanceText": f"{balance:,.2f}",
        "notes": doc.get("notes", ""),
        "status": status,
        "createdAt": doc["createdAt"].isoformat(),
        "updatedAt": doc["updatedAt"].isoformat(),
    }
    view["reason"] = status_reason(view)
    return view


def validate(data: dict) -> dict:
    errors: list[str] = []
    name = str(data.get("customerName") or "").strip()
    if not 2 <= len(name) <= 100:
        errors.append("Customer name must be 2 to 100 characters.")
    email = str(data.get("customerEmail") or "").strip()
    if not EMAIL.fullmatch(email):
        errors.append("Customer email must look like name@company.example.")
    issue = _date(data.get("issueDate"), "Issue date", errors)
    due = _date(data.get("dueDate"), "Due date", errors)
    if issue and due and due < issue:
        errors.append("Due date must be on or after the issue date.")
    notes = str(data.get("notes") or "").strip()
    if len(notes) > 500:
        errors.append("Notes must be at most 500 characters.")
    if str(data.get("currency") or "AED") != "AED":
        errors.append("Currency must be AED.")

    raw_lines = data.get("lineItems") or []
    if not 1 <= len(raw_lines) <= 10:
        errors.append("An invoice needs 1 to 10 lines.")
    lines = []
    total = Decimal("0.00")
    for index, raw in enumerate(raw_lines[:10], start=1):
        description = str(raw.get("description") or "").strip()
        if not 1 <= len(description) <= 200:
            errors.append(f"Line {index}: description is required and must be at most 200 characters.")
        quantity = _quantity(raw.get("quantity"), index, errors)
        price = _decimal(raw.get("unitPrice"), f"Line {index} price", errors)
        if description and quantity and price is not None:
            if price <= 0 or price > MAX_PRICE:
                errors.append(f"Line {index}: price must be greater than 0 and at most 1,000,000.")
            else:
                amount = (price * quantity).quantize(TWOPLACES)
                total += amount
                lines.append({
                    "description": description,
                    "quantity": quantity,
                    "unitPrice": float(price),
                })
    total = total.quantize(TWOPLACES)
    paid = _decimal(0 if str(data.get("amountPaid") or "").strip() == "" else data.get("amountPaid"), "Amount paid", errors)
    if paid is not None:
        if paid < 0:
            errors.append("Amount paid cannot be negative.")
        elif lines and paid > total:
            errors.append("Amount paid cannot be greater than the invoice total.")
    if errors:
        raise AppError(422, errors)
    return {
        "customerName": name,
        "customerEmail": email,
        "issueDate": issue,
        "dueDate": due,
        "currency": "AED",
        "lineItems": lines,
        "total": float(total),
        "amountPaid": float(paid),
        "notes": notes,
    }


def _date(value, label, errors) -> str | None:
    text = str(value or "").strip()
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        errors.append(f"{label} must be a real date.")
        return None
    return parsed.date().isoformat()


def _quantity(value, index, errors) -> int | None:
    text = str(value if value is not None else "").strip()
    if not text or isinstance(value, bool):
        errors.append(f"Line {index}: quantity is required.")
        return None
    if not re.fullmatch(r"\d+", text):
        errors.append(f"Line {index}: quantity must be a whole number.")
        return None
    number = int(text)
    if not 1 <= number <= 9999:
        errors.append(f"Line {index}: quantity must be from 1 to 9999.")
        return None
    return number


def _next_number(db) -> str:
    doc = db.counters.find_one_and_update(
        {"_id": "invoice"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return f"INV-{1000 + doc['seq']}"


def customer_choices() -> tuple[list[dict], list[str]]:
    rows = []
    cities = set()
    for doc in get_db().customers.find().sort("name", 1):
        rows.append({
            "id": str(doc["_id"]),
            "name": doc["name"],
            "email": doc["email"],
            "city": doc["city"],
        })
        cities.add(doc["city"])
    return rows, sorted(cities)


def _known_cities(db) -> set[str]:
    return {doc["city"] for doc in db.customers.find({}, {"city": 1})}


def book_summary(today: str) -> dict:
    """Counts for every invoice, ignoring list filters."""
    invoices, counts, _selected = list_invoices("", "", today)
    outstanding = Decimal("0.00")
    for item in invoices:
        outstanding += Decimal(item["balanceText"].replace(",", ""))
    return {
        "total": len(invoices),
        "counts": counts,
        "outstanding": f"{outstanding.quantize(TWOPLACES):,.2f}",
    }


def list_invoices(
    query_text: str,
    status: str | None,
    today: str,
    customer_id: str = "",
    due_on_or_before: str = "",
    city: str = "",
):
    db = get_db()
    query: dict = {}
    text = (query_text or "").strip()
    if text:
        safe = re.escape(text)
        query["$or"] = [
            {"invoiceNumber": {"$regex": safe, "$options": "i"}},
            {"customerName": {"$regex": safe, "$options": "i"}},
        ]
    ids = None
    if city and city in _known_cities(db):
        ids = [doc["_id"] for doc in db.customers.find({"city": city}, {"_id": 1})]
    if customer_id:
        try:
            chosen = ObjectId(customer_id)
        except InvalidId:
            chosen = None
        if chosen is not None and db.customers.find_one({"_id": chosen}, {"_id": 1}):
            ids = [chosen] if ids is None or chosen in ids else []
    if ids is not None:
        query["customerId"] = {"$in": ids}
    due = (due_on_or_before or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
        query["dueDate"] = {"$lte": due}

    by_id = {doc["_id"]: doc for doc in db.customers.find()}
    found = list(db.invoices.find(query).sort("invoiceNumber", 1))
    shown = []
    for doc in found:
        item = present(doc, today)
        customer = by_id.get(doc.get("customerId"))
        item["city"] = customer["city"] if customer else ""
        shown.append(item)
    counts = {name: sum(1 for item in shown if item["status"] == name) for name in STATUSES}
    selected = status if status in STATUSES else ""
    if selected:
        shown = [item for item in shown if item["status"] == selected]
    return shown, counts, selected


def get_invoice(number: str, today: str) -> dict:
    if not INVOICE_NUMBER.fullmatch(number or ""):
        raise AppError(404, "Invoice not found.")
    db = get_db()
    doc = db.invoices.find_one({"invoiceNumber": number})
    if not doc:
        raise AppError(404, "Invoice not found.")
    view = present(doc, today)
    if doc.get("customerId"):
        customer = db.customers.find_one({"_id": doc["customerId"]})
        view["city"] = customer["city"] if customer else ""
    return view


def apply_customer(data: dict) -> dict:
    """If a saved customer was chosen, copy that customer's name and email."""
    raw = str(data.get("customerId") or "").strip()
    if not raw:
        data.pop("customerId", None)
        return data
    try:
        customer_id = ObjectId(raw)
    except InvalidId:
        raise AppError(422, "Choose a customer from the list.")
    customer = get_db().customers.find_one({"_id": customer_id})
    if not customer:
        raise AppError(422, "Choose a customer from the list.")
    data["customerName"] = customer["name"]
    data["customerEmail"] = customer["email"]
    data["customerId"] = customer_id
    return data


def create_invoice(data: dict, today: str) -> dict:
    data = apply_customer(dict(data))
    customer_id = data.get("customerId")
    cleaned = validate(data)
    if isinstance(customer_id, ObjectId):
        cleaned["customerId"] = customer_id
    now = datetime.now(timezone.utc)
    db = get_db()
    cleaned.update({
        "invoiceNumber": _next_number(db),
        "createdAt": now,
        "updatedAt": now,
    })
    cleaned["_id"] = db.invoices.insert_one(cleaned).inserted_id
    return present(cleaned, today)


def update_invoice(number: str, data: dict, today: str) -> dict:
    if not INVOICE_NUMBER.fullmatch(number or ""):
        raise AppError(404, "Invoice not found.")
    db = get_db()
    current = db.invoices.find_one({"invoiceNumber": number})
    if not current:
        raise AppError(404, "Invoice not found.")
    data = apply_customer(dict(data))
    customer_id = data.get("customerId")
    cleaned = validate(data)
    if isinstance(customer_id, ObjectId):
        cleaned["customerId"] = customer_id
    cleaned.update({
        "invoiceNumber": current["invoiceNumber"],
        "createdAt": current["createdAt"],
        "updatedAt": datetime.now(timezone.utc),
    })
    db.invoices.replace_one({"_id": current["_id"]}, cleaned)
    cleaned["_id"] = current["_id"]
    return present(cleaned, today)


def delete_invoice(number: str) -> str:
    if not INVOICE_NUMBER.fullmatch(number or ""):
        raise AppError(404, "Invoice not found.")
    result = get_db().invoices.delete_one({"invoiceNumber": number})
    if result.deleted_count != 1:
        raise AppError(404, "Invoice not found.")
    return number


def blank_form() -> dict:
    return {
        "customerId": "", "customerName": "", "customerEmail": "", "issueDate": "", "dueDate": "",
        "notes": "", "amountPaid": "", "lineItems": [
            {"description": "", "quantity": "1", "unitPrice": ""},
        ],
    }


def form_from_invoice(invoice: dict) -> dict:
    return {
        "customerId": invoice.get("customerId") or "",
        "customerName": invoice["customerName"],
        "customerEmail": invoice["customerEmail"],
        "issueDate": invoice["issueDate"],
        "dueDate": invoice["dueDate"],
        "notes": invoice["notes"],
        "amountPaid": f"{invoice['amountPaid']:.2f}",
        "lineItems": [
            {
                "description": line["description"],
                "quantity": str(line["quantity"]),
                "unitPrice": f"{line['unitPrice']:.2f}",
            }
            for line in invoice["lineItems"]
        ],
    }


def form_from_request(data: dict) -> dict:
    lines = data.get("lineItems") or []
    return {
        "customerId": str(data.get("customerId") or ""),
        "customerName": str(data.get("customerName") or ""),
        "customerEmail": str(data.get("customerEmail") or ""),
        "issueDate": str(data.get("issueDate") or ""),
        "dueDate": str(data.get("dueDate") or ""),
        "notes": str(data.get("notes") or ""),
        "amountPaid": str(data.get("amountPaid") or ""),
        "lineItems": [
            {
                "description": str(line.get("description") or ""),
                "quantity": str(line.get("quantity") if line.get("quantity") is not None else ""),
                "unitPrice": str(line.get("unitPrice") if line.get("unitPrice") is not None else ""),
            }
            for line in lines
        ] or blank_form()["lineItems"],
    }


def totals_match(doc: dict) -> bool:
    total = Decimal("0.00")
    for line in doc["lineItems"]:
        total += (Decimal(str(line["unitPrice"])) * int(line["quantity"])).quantize(TWOPLACES)
    return total.quantize(TWOPLACES) == Decimal(str(doc["total"])).quantize(TWOPLACES)
