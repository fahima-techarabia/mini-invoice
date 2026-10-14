"""Ten read-only questions. Each one reads MongoDB and the same invoice functions the pages and API use."""
from decimal import Decimal

from app.db import get_db
from app.services import list_invoices, totals_match

TWOPLACES = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(TWOPLACES)


def _numbers(items) -> str:
    names = []
    for item in items:
        names.append(item["invoiceNumber"] if isinstance(item, dict) else item)
    return ", ".join(sorted(names))


def _row(qid: str, title: str, sql: str, mongo: str, database: str, screens: str) -> dict:
    return {
        "id": qid,
        "title": title,
        "sql": sql,
        "mongo": mongo,
        "database": database,
        "screens": screens,
        "match": database == screens,
    }


def ten_questions(today: str) -> list[dict]:
    db = get_db()
    customers = {doc["code"]: doc for doc in db.customers.find()}
    northwind = customers.get("C-01")
    if northwind is None:
        missing = _row(
            "Q-01", "Sample customers are loaded",
            "SELECT COUNT(*) FROM customers;",
            "db.customers.countDocuments({ code: 'C-01' })",
            "0", "0",
        )
        missing["match"] = False
        return [missing]

    docs = list(db.invoices.find())
    screen_all, _counts, _selected = list_invoices("", "", today)
    screen_by_number = {item["invoiceNumber"]: item for item in screen_all}

    overdue_db = _numbers(db.invoices.find({
        "dueDate": {"$lt": today},
        "$expr": {"$lt": ["$amountPaid", "$total"]},
    }))
    overdue_screen, _, _ = list_invoices("", "Overdue", today)

    paid_db = _numbers(db.invoices.find({"$expr": {"$eq": ["$amountPaid", "$total"]}}))
    paid_screen, _, _ = list_invoices("", "Paid", today)

    northwind_db = _numbers(db.invoices.find({"customerId": northwind["_id"]}))
    northwind_screen, _, _ = list_invoices("", "", today, customer_id=str(northwind["_id"]))

    dubai = list(db.invoices.aggregate([
        {"$lookup": {
            "from": "customers",
            "localField": "customerId",
            "foreignField": "_id",
            "as": "customer",
        }},
        {"$unwind": "$customer"},
        {"$match": {"customer.city": "Dubai"}},
    ]))
    dubai_screen, _, _ = list_invoices("", "", today, city="Dubai")

    grouped = list(db.invoices.aggregate([
        {"$group": {"_id": "$customerId", "n": {"$sum": 1}}},
        {"$lookup": {
            "from": "customers",
            "localField": "_id",
            "foreignField": "_id",
            "as": "customer",
        }},
        {"$unwind": "$customer"},
        {"$match": {"customer.code": "C-01"}},
    ]))
    grouped_count = str(grouped[0]["n"]) if grouped else "0"

    bad_totals = [doc["invoiceNumber"] for doc in docs if not totals_match(doc)]
    screen_bad_totals = []
    for item in screen_all:
        line_total = Decimal("0.00")
        for line in item["lineItems"]:
            line_total += (_money(line["unitPrice"]) * int(line["quantity"])).quantize(TWOPLACES)
        if line_total.quantize(TWOPLACES) != _money(item["total"]):
            screen_bad_totals.append(item["invoiceNumber"])

    over_paid = [
        doc["invoiceNumber"] for doc in docs
        if _money(doc["amountPaid"]) > _money(doc["total"])
    ]
    screen_over_paid = [
        item["invoiceNumber"] for item in screen_all
        if _money(item["amountPaid"]) > _money(item["total"])
    ]

    bad_dates = db.invoices.count_documents({"$expr": {"$lt": ["$dueDate", "$issueDate"]}})
    screen_bad_dates = [
        item["invoiceNumber"] for item in screen_all
        if item["dueDate"] < item["issueDate"]
    ]

    lumen = db.invoices.find_one({"invoiceNumber": "INV-1008"})
    database_balance = str(_money(lumen["total"]) - _money(lumen["amountPaid"])) if lumen else "missing"
    screen_balance = screen_by_number.get("INV-1008", {}).get("balanceText", "missing")

    return [
        _row(
            "Q-01", "Count every invoice",
            "SELECT COUNT(*) FROM invoices;",
            "db.invoices.countDocuments({})",
            str(len(docs)), str(len(screen_all)),
        ),
        _row(
            "Q-02", "Filter overdue invoices",
            "SELECT invoice_number FROM invoices WHERE due_date < today AND amount_paid < total;",
            '{ dueDate: { $lt: today }, $expr: { $lt: ["$amountPaid", "$total"] } }',
            overdue_db, _numbers(overdue_screen),
        ),
        _row(
            "Q-03", "Filter paid invoices",
            "SELECT invoice_number FROM invoices WHERE amount_paid = total;",
            '{ $expr: { $eq: ["$amountPaid", "$total"] } }',
            paid_db, _numbers(paid_screen),
        ),
        _row(
            "Q-04", "Filter one customer",
            "SELECT invoice_number FROM invoices WHERE customer_id = (SELECT id FROM customers WHERE code = 'C-01');",
            "{ customerId: ObjectId('<Northwind>') }",
            northwind_db, _numbers(northwind_screen),
        ),
        _row(
            "Q-05", "Join invoices to customers in Dubai",
            "SELECT i.invoice_number FROM invoices i INNER JOIN customers c ON i.customer_id = c.id WHERE c.city = 'Dubai';",
            "$lookup customers on customerId, then $match customer.city = 'Dubai'",
            _numbers(dubai), _numbers(dubai_screen),
        ),
        _row(
            "Q-06", "Count Northwind invoices after grouping",
            "SELECT c.name, COUNT(*) FROM invoices i INNER JOIN customers c ON i.customer_id = c.id WHERE c.code = 'C-01' GROUP BY c.name;",
            "$group by customerId, then $lookup customers, then $match code C-01",
            grouped_count, str(len(northwind_screen)),
        ),
        _row(
            "Q-07", "Stored total matches the sum of the lines",
            "SELECT invoice_number FROM invoices i JOIN invoice_lines l ON l.invoice_id = i.id GROUP BY i.id, i.total HAVING SUM(l.quantity * l.unit_price) <> i.total;",
            "Read each invoice and compare total with quantity × unitPrice, rounded to 2 decimals",
            str(len(bad_totals)), str(len(screen_bad_totals)),
        ),
        _row(
            "Q-08", "Amount paid is not above the total",
            "SELECT COUNT(*) FROM invoices WHERE amount_paid > total;",
            "Read each invoice and compare amountPaid with total",
            str(len(over_paid)), str(len(screen_over_paid)),
        ),
        _row(
            "Q-09", "Due date is on or after the issue date",
            "SELECT COUNT(*) FROM invoices WHERE due_date < issue_date;",
            '{ $expr: { $lt: ["$dueDate", "$issueDate"] } }',
            str(bad_dates), str(len(screen_bad_dates)),
        ),
        _row(
            "Q-10", "INV-1008 balance is the same in the database and on screen",
            "SELECT total - amount_paid AS balance FROM invoices WHERE invoice_number = 'INV-1008';",
            "Find INV-1008 and subtract amountPaid from total",
            database_balance, screen_balance,
        ),
    ]
