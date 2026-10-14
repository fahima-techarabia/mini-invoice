# Database schema

Database name comes from `MONGODB_DB` in `.env`. This project uses `mini_tender_practice` because that is the database the Atlas user is allowed to write.

## invoices

One document is one invoice. Line items are stored inside it.

| Field | Type | Rules |
|---|---|---|
| `_id` | ObjectId | automatic |
| `invoiceNumber` | string | `INV-` plus digits. Unique index `invoice_number_unique` |
| `customerId` | ObjectId | optional link to a document in `customers` |
| `customerName` | string | 2–100 characters |
| `customerEmail` | string | must contain `@` and a dot in the domain |
| `issueDate`, `dueDate` | string | `YYYY-MM-DD` |
| `currency` | string | `AED` |
| `lineItems` | array | 1–10 objects: `description`, `quantity` (int), `unitPrice` (number greater than 0) |
| `total` | number | stored so a test can compare it with the sum of the lines. The database does not check that sum |
| `amountPaid` | number | 0 or more. The database does not check that it is less than or equal to `total` |
| `notes` | string | at most 500 characters |
| `createdAt`, `updatedAt` | date | UTC timestamps |

There is no `status` field and no `balance` field. Both are calculated when the app reads the document. That way an invoice cannot be stored as Paid while money is still outstanding, and it becomes Overdue on the right day without a nightly job.

## customers

One document is one customer. An invoice points at it with `customerId`. That link is what a SQL `JOIN` would use. In MongoDB the same question is `$lookup`.

| Field | Type | Rules |
|---|---|---|
| `code` | string | `C-` plus two digits. Unique |
| `name` | string | 2–100 characters |
| `email` | string | must contain `@` and a dot in the domain |
| `city` | string | used by the city filter |

The invoice also keeps a copy of the customer name and email, so the invoice can still be read if you don't join.

## counters

| Field | Meaning |
|---|---|
| `_id` | `"invoice"` |
| `seq` | how many numbers have been issued. The next number is `INV-` plus `1000 + seq + 1` |

## Queries you can run in Atlas

Replace `2026-10-14` with the date shown at the top of the invoice list.

Overdue (not fully paid, due before today):

```json
{ "dueDate": { "$lt": "2026-10-14" }, "$expr": { "$lt": ["$amountPaid", "$total"] } }
```

Paid:

```json
{ "$expr": { "$eq": ["$amountPaid", "$total"] } }
```

Invoices for customers in Dubai (the MongoDB form of an inner join):

```javascript
db.invoices.aggregate([
  { $lookup: { from: "customers", localField: "customerId", foreignField: "_id", as: "customer" } },
  { $unwind: "$customer" },
  { $match: { "customer.city": "Dubai" } }
])
```

The free-tier limits checked on 2026-10-14 still apply: 512 MB, 100 operations per second, no backups, and the cluster can pause after 30 days with no connections. Source: https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/
