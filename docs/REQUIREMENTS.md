# Requirements — Invoice Tracker v1

Practice app. Fictional data only. Each rule has an ID so a test can point to it.

**Enforced by** says which layer stops a bad request:

- **API**: `app/services.py`, used by both the pages and `/api/invoices`
- **DB**: the MongoDB validator or the unique index in `app/schema.py`

## Invoice fields

| ID | Rule | Enforced by |
|---|---|---|
| INV-01 | Customer name is required, 2–100 characters after trimming spaces | API and DB |
| INV-02 | Customer email is required and must look like `name@company.example` | API and DB |
| INV-03 | Issue date and due date are required real dates, and the due date is on or after the issue date | API (both); DB (the date shape only) |
| INV-04 | 1 to 10 lines. Description is required, at most 200 characters. Quantity is a whole number from 1 to 9999. Unit price is greater than 0, at most 1,000,000, with at most 2 decimal places | API and DB |
| INV-05 | Line amount = quantity × unit price. Invoice total = the sum of the line amounts. Both are calculated | API |
| INV-06 | Amount paid is blank or 0 or more, at most 2 decimal places, and cannot be greater than the total. Blank means 0. It replaces the amount received; it does not add a new payment | API (all); DB (0 or more) |
| INV-07 | Currency is AED | API and DB |
| INV-08 | Notes are optional, at most 500 characters | API and DB |
| INV-09 | The app assigns `INV-1001`, `INV-1002`, and so on. The number is unique and does not change on edit | API and DB (unique index) |
| INV-10 | Delete asks for confirmation, then removes that one invoice | API |

## Status

The user cannot type a status. One function calculates it.

| ID | Rule |
|---|---|
| STA-01 | Paid when amount paid equals the total, including an invoice paid after its due date |
| STA-02 | Overdue when it is not fully paid and the due date is before today |
| STA-03 | Partially Paid when some money has been received and the due date is today or later |
| STA-04 | Unpaid when nothing has been received and the due date is today or later |
| STA-05 | A partial payment past the due date is Overdue. The page still shows the amount paid |
| STA-06 | Balance = total − amount paid, and it is calculated, not stored |

Today is the calendar date on the computer using the app. The page says which date that is.

## Screens

| Screen | What it must do |
|---|---|
| List | Search by number or customer, filter by the four statuses, show counts, and show a different empty message when nothing matches |
| View | Show every field, the lines, total, amount paid, balance, and one sentence explaining the status |
| Create / Edit | Keep what you typed when a rule fails. Cancel does not save. Edit cannot change the invoice number |
| Delete | Name the invoice in the confirmation. Dismissing it leaves the invoice in place |

## Out of scope

Login, PDF files, email, payment gateways, VAT, and a history of individual payments.
