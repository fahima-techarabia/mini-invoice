"""Fifteen critical browser checks for the practice Invoice Tracker.

These tests only read saved invoices, or submit a form the server refuses.
They do not create, edit, or delete an invoice.
"""

import re
from decimal import Decimal

from playwright.sync_api import Page, expect

STATUSES = {"Paid", "Overdue", "Partially Paid", "Unpaid"}


def money(text: str) -> Decimal:
    match = re.search(r"-?\d[\d,]*\.\d{2}", text)
    assert match, text
    return Decimal(match.group(0).replace(",", ""))


def rows(page: Page):
    return page.get_by_test_id("invoice-row")


def fill_refused_invoice(page: Page, due: str, paid: str) -> None:
    page.goto("/invoices/new")
    page.get_by_test_id("customer-name").fill("PW Check Supplies LLC")
    page.get_by_test_id("customer-email").fill("pw-check@practice.example")
    page.get_by_test_id("issue-date").fill("2026-10-14")
    page.get_by_test_id("due-date").fill(due)
    page.get_by_test_id("description").fill("Browser check")
    page.get_by_test_id("quantity").fill("1")
    page.get_by_test_id("unit-price").fill("50.00")
    page.get_by_test_id("amount-paid").fill(paid)
    page.get_by_test_id("save").click()


def test_01_invoice_list_loads(page: Page):
    page.goto("/invoices")
    expect(page.get_by_role("heading", name="Invoices")).to_be_visible()
    expect(page.get_by_text(re.compile(r"Today is \d{4}-\d{2}-\d{2}"))).to_be_visible()
    total = int(page.get_by_test_id("book-total").inner_text())
    assert total >= 1
    expect(rows(page)).to_have_count(total)


def test_02_every_row_has_a_known_status(page: Page):
    page.goto("/invoices")
    shown = rows(page).get_by_test_id("invoice-status").all_inner_texts()
    assert shown
    assert set(shown) <= STATUSES


def test_03_unpaid_filter_shows_only_unpaid(page: Page):
    page.goto("/invoices")
    page.get_by_test_id("filter-status").select_option("Unpaid")
    page.get_by_test_id("search-button").click()
    expect(page).to_have_url(re.compile(r"status=Unpaid"))
    shown = rows(page).get_by_test_id("invoice-status").all_inner_texts()
    assert shown
    assert set(shown) == {"Unpaid"}


def test_04_search_finds_one_invoice_by_number(page: Page):
    page.goto("/invoices")
    number = rows(page).first.get_attribute("data-number")
    page.get_by_test_id("search").fill(number)
    page.get_by_test_id("search-button").click()
    expect(rows(page)).to_have_count(1)
    expect(rows(page).first).to_have_attribute("data-number", number)


def test_05_dubai_filter_shows_only_dubai(page: Page):
    page.goto("/invoices")
    page.get_by_test_id("filter-city").select_option("Dubai")
    page.get_by_test_id("search-button").click()
    expect(page).to_have_url(re.compile(r"city=Dubai"))
    cities = rows(page).locator("[data-label=City]").all_inner_texts()
    assert cities
    assert set(cities) == {"Dubai"}


def test_06_clear_removes_the_filters(page: Page):
    page.goto("/invoices")
    total = int(page.get_by_test_id("book-total").inner_text())
    page.get_by_test_id("search").fill("INV-1001")
    page.get_by_test_id("search-button").click()
    expect(rows(page)).to_have_count(1)
    page.get_by_test_id("clear-search").click()
    expect(page).to_have_url(re.compile(r"/invoices/?$"))
    expect(page.get_by_test_id("search")).to_have_value("")
    expect(rows(page)).to_have_count(total)


def test_07_detail_balance_is_total_minus_paid(page: Page):
    page.goto("/invoices")
    number = rows(page).first.get_attribute("data-number")
    rows(page).first.get_by_test_id("open-invoice").click()
    expect(page).to_have_url(re.compile(rf"/invoices/{number}$"))
    total = money(page.get_by_test_id("total").inner_text())
    paid = money(page.get_by_test_id("amount-paid").inner_text())
    balance = money(page.get_by_test_id("balance").inner_text())
    assert balance == total - paid
    assert page.get_by_test_id("invoice-status").inner_text() in STATUSES


def test_08_query_checks_match_the_screens(page: Page):
    page.goto("/queries")
    expect(page.get_by_role("heading", name="Query checks")).to_be_visible()
    checks = page.get_by_test_id("query-row")
    expect(checks).to_have_count(10)
    for index in range(10):
        expect(checks.nth(index)).to_have_attribute("data-result", "match")


def test_09_new_invoice_form_marks_required_fields(page: Page):
    page.goto("/invoices/new")
    expect(page.get_by_role("heading", name="New invoice")).to_be_visible()
    for test_id in ("customer-name", "customer-email", "issue-date", "due-date", "description", "quantity", "unit-price"):
        expect(page.get_by_test_id(test_id)).to_have_attribute("required", "")
    expect(page.get_by_text("Amount paid is the total received so far")).to_be_visible()


def test_10_due_date_before_issue_date_is_refused(page: Page):
    fill_refused_invoice(page, due="2026-10-01", paid="0")
    expect(page.get_by_test_id("error")).to_contain_text("Due date must be on or after the issue date.")
    expect(page).to_have_url(re.compile(r"/invoices/new$"))
    page.goto("/invoices?q=PW+Check")
    expect(page.get_by_test_id("empty")).to_be_visible()


def test_11_amount_paid_above_the_total_is_refused(page: Page):
    page.goto("/invoices/new")
    page.get_by_test_id("quantity").fill("1")
    page.get_by_test_id("unit-price").fill("50.00")
    page.get_by_test_id("amount-paid").fill("60")
    expect(page.locator("#balance-warning")).to_be_visible()
    fill_refused_invoice(page, due="2026-11-01", paid="60")
    expect(page.get_by_test_id("error")).to_contain_text("Amount paid cannot be greater than the invoice total.")
    page.goto("/invoices?q=PW+Check")
    expect(page.get_by_test_id("empty")).to_be_visible()


def test_12_saved_customer_fills_name_and_email(page: Page):
    page.goto("/invoices/new")
    page.get_by_test_id("customer-picker").select_option(label="Northwind Trading LLC · Dubai")
    expect(page.get_by_test_id("customer-name")).to_have_value("Northwind Trading LLC")
    expect(page.get_by_test_id("customer-email")).to_have_value("accounts@northwind.example")
    expect(page.get_by_test_id("customer-city")).to_contain_text("Dubai")


def test_13_live_total_is_quantity_times_price(page: Page):
    page.goto("/invoices/new")
    page.get_by_test_id("quantity").fill("2")
    page.get_by_test_id("unit-price").fill("25.50")
    expect(page.get_by_test_id("line-total")).to_have_text("51.00")
    expect(page.locator("#invoice-total")).to_have_text("51.00")
    expect(page.locator("#balance")).to_have_text("51.00")


def test_14_dismissing_delete_keeps_the_invoice(page: Page):
    page.goto("/invoices")
    row = rows(page).first
    number = row.get_attribute("data-number")
    message = {}

    def handle_dialog(dialog):
        message["text"] = dialog.message
        dialog.dismiss()

    page.once("dialog", handle_dialog)
    row.get_by_test_id("delete").click()
    assert number in message["text"]
    assert "cannot be undone" in message["text"]
    expect(page.locator(f'[data-number="{number}"]')).to_have_count(1)


def test_15_city_and_status_filters_apply_together(page: Page):
    page.goto("/invoices")
    page.get_by_test_id("filter-city").select_option("Dubai")
    page.get_by_test_id("filter-status").select_option("Overdue")
    page.get_by_test_id("search-button").click()
    expect(page).to_have_url(re.compile(r"city=Dubai"))
    expect(page).to_have_url(re.compile(r"status=Overdue"))
    expect(page.get_by_test_id("filter-city")).to_have_value("Dubai")
    expect(page.get_by_test_id("filter-status")).to_have_value("Overdue")
    shown = rows(page)
    assert shown.count() >= 1
    assert set(shown.locator("[data-label=City]").all_inner_texts()) == {"Dubai"}
    assert set(shown.get_by_test_id("invoice-status").all_inner_texts()) == {"Overdue"}
