"""Rules that do not touch the database."""
from decimal import Decimal

import pytest

from app.services import AppError, invoice_status, validate

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


def test_paid_equal_to_the_total_is_allowed():
    saved = validate(_invoice(amountPaid="90"))
    assert saved["amountPaid"] == 90.0
    assert saved["total"] == 90.0


@pytest.mark.parametrize("changes, message", [
    ({"customerName": "  "}, "Customer name"),
    ({"customerEmail": "not-an-email"}, "email"),
    ({"dueDate": "2026-09-01"}, "Due date must be on or after"),
    ({"amountPaid": "-1"}, "cannot be negative"),
    ({"amountPaid": "90.01"}, "cannot be greater than"),
    ({"amountPaid": "10.005"}, "at most 2 decimal places"),
    ({"lineItems": [{"description": "Labels", "quantity": "0", "unitPrice": "10"}]}, "quantity must be from 1"),
    ({"lineItems": [{"description": "Labels", "quantity": "1", "unitPrice": "-5"}]}, "greater than 0"),
    ({"notes": "x" * 501}, "at most 500"),
    ({"lineItems": []}, "1 to 10 lines"),
])
def test_server_rejects_invalid_invoices(changes, message):
    with pytest.raises(AppError) as caught:
        validate(_invoice(**changes))
    assert caught.value.status == 422
    assert any(message in item for item in caught.value.messages)
