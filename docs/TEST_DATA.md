# Test data

`scripts/seed.py` deletes the old tender collections and the invoice collections, then inserts 8 fictional customers and 16 fictional invoices. Dates are relative to the day you run it, using UTC+4. Emails use the reserved `.example` domain.

Several customers have more than one invoice, so a join and a count-by-customer have something to return. Four customers are in Dubai: Northwind Trading LLC, Bright Books LLC, Metro Supplies and Lumen Print.

| Number | Customer | Total (AED) | Paid (AED) | Due | Status on the day it was seeded |
|---|---|---:|---:|---|---|
| INV-1001 | Northwind Trading LLC | 1,000.00 | 0.00 | in 20 days | Unpaid |
| INV-1002 | Blue Harbor Cafe | 750.00 | 250.00 | in 10 days | Partially Paid |
| INV-1003 | Cedar Clinic | 300.00 | 300.00 | in 7 days | Paid |
| INV-1004 | Bright Books LLC | 450.00 | 0.00 | 12 days ago | Overdue |
| INV-1005 | Palm Studio | 1,000.00 | 400.00 | 4 days ago | Overdue |
| INV-1006 | Metro Supplies | 200.00 | 200.00 | 15 days ago | Paid |
| INV-1007 | Harbor Tools | 80.00 | 0.00 | today | Unpaid |
| INV-1008 | Lumen Print | 450.50 | 100.25 | in 5 days | Partially Paid |
| INV-1009 | Northwind Trading LLC | 800.00 | 200.00 | in 15 days | Partially Paid |
| INV-1010 | Northwind Trading LLC | 1,500.00 | 500.00 | 20 days ago | Overdue |
| INV-1011 | Blue Harbor Cafe | 400.00 | 400.00 | 3 days ago | Paid |
| INV-1012 | Cedar Clinic | 300.00 | 0.00 | in 12 days | Unpaid |
| INV-1013 | Bright Books LLC | 400.00 | 100.00 | in 8 days | Partially Paid |
| INV-1014 | Palm Studio | 90.00 | 0.00 | in 30 days | Unpaid |
| INV-1015 | Metro Supplies | 200.00 | 0.00 | yesterday | Overdue |
| INV-1016 | Lumen Print | 220.00 | 220.00 | in 2 days | Paid |

INV-1005 has two lines (400.00 and 600.00). INV-1008 has two lines (400.00 and 50.50), so the balance is 350.25.

INV-1006 and INV-1011 are the “paid late” cases: the due date has passed and the status is still Paid. INV-1007 checks that a due date of today is not Overdue.

On 2026-10-14, after seeding, the counts were Unpaid 4, Partially Paid 4, Paid 4, Overdue 4.
