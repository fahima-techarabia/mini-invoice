"""Rules that do not touch the database."""
from decimal import Decimal

import pytest

from app.services import DEFAULT_OFFSET_MINUTES, AppError, invoice_status, parse_offset, validate

TODAY = "2026-10-14"


def status(paid, total, due):
    return invoice_status(Decimal(total), Decimal(paid), due, TODAY)


def test_status_uses_payment_before_the_due_date():
    assert status("0.00", "100.00", "2026-10-20") == "Unpaid"
    assert status("0.00", "100.00", "2026-10-13") == "Overdue"
    assert status("40.00", "100.00", "2026-10-20") == "Partially Paid"
    assert status("40.00", "100.00", "2026-10-13") == "Overdue"
    assert status("100.00", "100.00", "2026-10-20") == "Paid"
    assert status("100.00", "100.00", "2026-10-01") == "Paid"
    assert status("0.00", "80.00", TODAY) == "Unpaid"
    assert status("10.00", "80.00", TODAY) == "Partially Paid"


def _invoice(**overrides):
    data = {
        "customerName": "Audit Supplies LLC",
        "customerEmail": "accounts@auditsupplies.example",
        "issueDate": "2026-10-01",
        "dueDate": "2026-10-20",
        "amountPaid": "10.00",
        "lineItems": [
            {"description": "Labels", "quantity": "2", "unitPrice": "25.00"},
            {"description": "Install", "quantity": "1", "unitPrice": "40"},
        ],
    }
    data.update(overrides)
    return data


def test_total_is_the_sum_of_the_lines_and_blank_paid_is_zero():
    saved = validate(_invoice(amountPaid=""))
    assert saved["total"] == 90.0
    assert saved["amountPaid"] == 0.0


def test_amount_paid_replaces_rather_than_adds():
    first = validate(_invoice(amountPaid="10.00"))
    second = validate(_invoice(amountPaid="10.00"))
    assert first["amountPaid"] == 10.0
    assert second["amountPaid"] == 10.0


def test_largest_quantity_and_price_are_allowed():
    saved = validate(_invoice(amountPaid="0", lineItems=[
        {"description": "Bulk", "quantity": "9999", "unitPrice": "1000000"},
    ]))
    assert saved["total"] == 9_999_000_000.0


@pytest.mark.parametrize("cookie, offset", [
    ("-240", -240),
    ("840", 840),
    ("841", DEFAULT_OFFSET_MINUTES),
    ("abc", DEFAULT_OFFSET_MINUTES),
    (None, DEFAULT_OFFSET_MINUTES),
])
def test_timezone_cookie_falls_back_to_dubai(cookie, offset):
    assert parse_offset(cookie) == offset


def test_paid_equal_to_the_total_is_allowed():
    saved = validate(_invoice(amountPaid="90"))
    assert saved["amountPaid"] == 90.0
    assert saved["total"] == 90.0


@pytest.mark.parametrize("changes, message", [
    pytest.param({"customerName": "  "}, "Customer name", id="a blank customer name"),
    pytest.param({"customerEmail": "not-an-email"}, "email", id="a badly formed email"),
    pytest.param({"dueDate": "2026-09-01"}, "Due date must be on or after", id="a due date before the issue date"),
    pytest.param({"amountPaid": "-1"}, "cannot be negative", id="a negative amount paid"),
    pytest.param({"amountPaid": "90.01"}, "cannot be greater than", id="amount paid above the total"),
    pytest.param({"amountPaid": "10.005"}, "at most 2 decimal places", id="amount paid with 3 decimals"),
    pytest.param({"lineItems": [{"description": "Labels", "quantity": "0", "unitPrice": "10"}]},
                 "quantity must be from 1", id="quantity 0"),
    pytest.param({"lineItems": [{"description": "Labels", "quantity": "1", "unitPrice": "-5"}]},
                 "greater than 0", id="a negative price"),
    pytest.param({"notes": "x" * 501}, "at most 500", id="notes over 500 characters"),
    pytest.param({"lineItems": []}, "1 to 10 lines", id="no lines"),
    pytest.param({"lineItems": [{"description": "Labels", "quantity": "1", "unitPrice": "1"}] * 11},
                 "1 to 10 lines", id="11 lines"),
    pytest.param({"lineItems": [{"description": "Labels", "quantity": "10000", "unitPrice": "1"}]},
                 "quantity must be from 1 to 9999", id="quantity 10000"),
    pytest.param({"lineItems": [{"description": "Labels", "quantity": "1.5", "unitPrice": "1"}]},
                 "quantity must be a whole number", id="quantity 1.5"),
    pytest.param({"lineItems": [{"description": "Labels", "quantity": "1", "unitPrice": "1000000.01"}]},
                 "at most 1,000,000", id="a price over 1,000,000"),
    pytest.param({"lineItems": [{"description": "Labels", "quantity": "1", "unitPrice": "10.005"}]},
                 "at most 2 decimal places", id="a price with 3 decimals"),
    pytest.param({"dueDate": "2026-02-30"}, "Due date must be a real date", id="the date 30 February"),
    pytest.param({"currency": "USD"}, "Currency must be AED", id="a currency other than AED"),
])
def test_server_rejects_invalid_invoices(changes, message):
    with pytest.raises(AppError) as caught:
        validate(_invoice(**changes))
    assert caught.value.status == 422
    assert any(message in item for item in caught.value.messages)
