"""Compare ten read-only questions across the database, the JSON API and the HTML pages.

The seed at the start loads the fictional invoices. The ten questions do not insert, update or delete.
"""
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import warnings

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from app.checks import ten_questions
from app.db import get_db
from app.main import app
from app.services import calendar_today
from scripts.seed import main as seed_main

TWOPLACES = Decimal("0.01")
failed = 0


def money(value) -> Decimal:
    return Decimal(str(value).replace(",", "").replace(" AED", "").strip()).quantize(TWOPLACES)


def numbers_from(html: str) -> str:
    return ", ".join(sorted(set(re.findall(r'data-number="(INV-\d+)"', html))))


def api_numbers(client, **params) -> str:
    response = client.get("/api/invoices", params=params)
    if response.status_code != 200:
        return f"HTTP {response.status_code}"
    return ", ".join(sorted(item["invoiceNumber"] for item in response.json()["invoices"]))


def main() -> None:
    global failed
    seed_main()
    today = calendar_today()
    client = TestClient(app)
    client.cookies.set("tz_offset_minutes", "-240")
    rows = {row["id"]: row for row in ten_questions(today)}
    northwind = get_db().customers.find_one({"code": "C-01"})
    customer_id = str(northwind["_id"])

    def check(qid: str, api_value: str, page_value: str) -> None:
        global failed
        row = rows[qid]
        ok = row["match"] and row["database"] == api_value == page_value
        label = row["database"]
        if len(label) > 90:
            label = label[:87] + "..."
        if ok:
            print(f"PASS  {qid}  {label}")
        else:
            failed += 1
            print(f"FAIL  {qid}")
            print(f"      database: {row['database']}")
            print(f"      screens:  {row['screens']}")
            print(f"      api:      {api_value}")
            print(f"      page:     {page_value}")

    api_list = client.get("/api/invoices")
    page_list = client.get("/invoices")
    check("Q-01", str(len(api_list.json()["invoices"])), str(page_list.text.count('data-testid="invoice-row"')))
    check("Q-02", api_numbers(client, status="Overdue"), numbers_from(client.get("/invoices", params={"status": "Overdue"}).text))
    check("Q-03", api_numbers(client, status="Paid"), numbers_from(client.get("/invoices", params={"status": "Paid"}).text))
    check("Q-04", api_numbers(client, customer=customer_id), numbers_from(client.get("/invoices", params={"customer": customer_id}).text))
    check("Q-05", api_numbers(client, city="Dubai"), numbers_from(client.get("/invoices", params={"city": "Dubai"}).text))
    northwind_api = client.get("/api/invoices", params={"customer": customer_id}).json()["invoices"]
    northwind_page = client.get("/invoices", params={"customer": customer_id}).text
    check("Q-06", str(len(northwind_api)), str(northwind_page.count('data-testid="invoice-row"')))

    api_invoices = api_list.json()["invoices"]
    api_bad_totals = 0
    api_bad_dates = 0
    page_bad_totals = 0
    page_bad_dates = 0
    for item in api_invoices:
        line_total = Decimal("0.00")
        for line in item["lineItems"]:
            line_total += (money(line["unitPrice"]) * int(line["quantity"])).quantize(TWOPLACES)
        if line_total.quantize(TWOPLACES) != money(item["total"]):
            api_bad_totals += 1
        if item["dueDate"] < item["issueDate"]:
            api_bad_dates += 1
        detail = client.get(f"/invoices/{item['invoiceNumber']}")
        amounts = [money(value) for value in re.findall(r'data-label="Amount">([^<]+)', detail.text)]
        total = re.search(r'data-testid="total">([^<]+)', detail.text)
        issue = re.search(r'data-testid="issue-date">([^<]+)', detail.text)
        due = re.search(r'data-testid="due-date">([^<]+)', detail.text)
        if total is None or sum(amounts, Decimal("0.00")).quantize(TWOPLACES) != money(total.group(1)):
            page_bad_totals += 1
        if issue is None or due is None or due.group(1) < issue.group(1):
            page_bad_dates += 1
    check("Q-07", str(api_bad_totals), str(page_bad_totals))

    api_over = sum(1 for item in api_invoices if money(item["amountPaid"]) > money(item["total"]))
    page_over = 0
    for balance in re.findall(r'data-balance="([^"]+)"', page_list.text):
        if money(balance) < 0:
            page_over += 1
    check("Q-08", str(api_over), str(page_over))
    check("Q-09", str(api_bad_dates), str(page_bad_dates))

    api_balance = client.get("/api/invoices/INV-1008").json()["balanceText"]
    detail_balance = re.search(r'data-testid="balance">([^<]+)', client.get("/invoices/INV-1008").text)
    page_balance = money(detail_balance.group(1)).quantize(TWOPLACES) if detail_balance else Decimal("0")
    check("Q-10", api_balance, f"{page_balance:.2f}")

    queries = client.get("/queries")
    shown = queries.text.count('data-testid="query-row"')
    if queries.status_code == 200 and shown == 10 and "Differ" not in queries.text:
        print("PASS  query page shows 10 matches")
    else:
        failed += 1
        print(f"FAIL  query page — status {queries.status_code}, rows {shown}")

    print(f"\nToday: {today}")
    print(f"{failed} failed")


if __name__ == "__main__":
    main()
    sys.exit(1 if failed else 0)
