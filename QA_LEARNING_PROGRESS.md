# QA Learning Progress — Invoice Tracker

The tender practice app that was in this folder was replaced on 2026-10-14. The folder name is unchanged.

## Decisions

| Date | Decision |
|---|---|
| 2026-10-14 | Build an Invoice Tracker instead of Mini Tender & Bid, in this same folder |
| 2026-10-14 | One collection, `invoices`, with line items inside each document. No login, PDF, email or payment gateway |
| 2026-10-14 | Added a `customers` collection so an invoice can point at a customer. That link is the join. The list filters by customer, city, status and due date |
| 2026-10-14 | Status is calculated from the total, the amount paid and the due date. It is not stored |
| 2026-10-14 | Keep using Atlas database `mini_tender_practice`, because `mtb_app_dev` can write only to that database |
| 2026-10-14 | Stack stays Python, FastAPI and PyMongo |

## Setup

| Item | Status |
|---|---|
| Atlas cluster `mtb-practice` (Free) | Already created |
| Database user `mtb_app_dev` | `readWrite@mini_tender_practice` |
| `.env` | Present and not committed. The connection string is not in source code |
| Seed on 2026-10-14 | Ran again for the database module. Loaded 8 customers and 16 invoices. Counts: Unpaid 4, Partially Paid 4, Paid 4, Overdue 4 |

## Checks that were actually run

`scripts/ui_walk.py` on 2026-10-14, after the data grew to 16 invoices: **34 passed, 0 failed.** It created INV-1017, deleted it, and seeded the 16 sample invoices again.

`scripts/ten_queries.py` on 2026-10-14: **10 passed, 0 failed.** Each check compared the database, the JSON API and the HTML page. The query page showed 10 matches. Today for those checks was 2026-10-14.

| Check | Agreed value |
|---|---|
| Q-01 count | 16 |
| Q-02 overdue | INV-1004, INV-1005, INV-1010, INV-1015 |
| Q-03 paid | INV-1003, INV-1006, INV-1011, INV-1016 |
| Q-04 Northwind | INV-1001, INV-1009, INV-1010 |
| Q-05 Dubai join | INV-1001, INV-1004, INV-1006, INV-1008, INV-1009, INV-1010, INV-1013, INV-1015, INV-1016 |
| Q-06 Northwind count | 3 |
| Q-07 line totals that do not match | 0 |
| Q-08 amount paid above the total | 0 |
| Q-09 due date before issue date | 0 |
| Q-10 INV-1008 balance | 350.25 |

The run covered the list, search, status filters, overdue versus paid-late, the 350.25 balance, create, edit, delete, rejected invalid input, escaped HTML, the unique invoice number, the database validator, and the JSON API.

Browser check on 2026-10-14, at http://127.0.0.1:8000: the list, overdue filter, search for "harbor", Palm Studio detail, and Metro Supplies detail all rendered. Creating an invoice with a due date before the issue date kept the typed values and showed the error. Correcting the date saved INV-1009, and deleting it returned the list to the 8 sample invoices. A narrow window still showed the invoice details stacked and readable.

`scripts/database_checks.py` on 2026-10-14, after the larger seed: **23 passed, 0 failed.** The 16 sample invoices were still there at the end. One temporary document, INV-1099, was inserted to see whether MongoDB itself blocks an amount paid above the total, and it was deleted in the same run.

After those checks, INV-1001 (Northwind Trading LLC) was edited in the app. Amount paid is now 100 of 1,000. Read back from `mini_tender_practice.invoices` at 12:52 (UTC+4): `amountPaid` 100, `total` 1000, `updatedAt` 2026-10-14T08:52:30Z. The page calculates Partially Paid and a balance of 900. Status is not stored. The ten query results above were taken when this invoice was still unpaid.
