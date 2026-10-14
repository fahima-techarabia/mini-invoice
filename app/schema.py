"""MongoDB rules for the invoices and customers collections.

Business rules that need more than one field (due date vs issue date, total vs
lines, amount paid vs total) live in app/services.py.
"""

CUSTOMER_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["code", "name", "email", "city"],
        "properties": {
            "code": {"bsonType": "string", "pattern": "^C-[0-9]{2}$"},
            "name": {"bsonType": "string", "minLength": 2, "maxLength": 100},
            "email": {"bsonType": "string", "pattern": "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$"},
            "city": {"bsonType": "string", "minLength": 2, "maxLength": 80},
        },
    }
}

VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "invoiceNumber", "customerName", "customerEmail", "issueDate", "dueDate",
            "currency", "lineItems", "total", "amountPaid", "notes", "createdAt", "updatedAt",
        ],
        "properties": {
            "invoiceNumber": {"bsonType": "string", "pattern": "^INV-[0-9]+$"},
            "customerId": {"bsonType": "objectId"},
            "customerName": {"bsonType": "string", "minLength": 2, "maxLength": 100},
            "customerEmail": {"bsonType": "string", "pattern": "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$"},
            "issueDate": {"bsonType": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
            "dueDate": {"bsonType": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
            "currency": {"enum": ["AED"]},
            "lineItems": {
                "bsonType": "array",
                "minItems": 1,
                "maxItems": 10,
                "items": {
                    "bsonType": "object",
                    "required": ["description", "quantity", "unitPrice"],
                    "properties": {
                        "description": {"bsonType": "string", "minLength": 1, "maxLength": 200},
                        "quantity": {"bsonType": "int", "minimum": 1, "maximum": 9999},
                        "unitPrice": {
                            "bsonType": ["double", "int", "decimal"],
                            "minimum": 0,
                            "exclusiveMinimum": True,
                            "maximum": 1000000,
                        },
                    },
                },
            },
            "total": {"bsonType": ["double", "int", "decimal"], "minimum": 0},
            "amountPaid": {"bsonType": ["double", "int", "decimal"], "minimum": 0},
            "notes": {"bsonType": "string", "maxLength": 500},
            "createdAt": {"bsonType": "date"},
            "updatedAt": {"bsonType": "date"},
        },
    }
}


def ensure_schema(db) -> None:
    # readWrite on Atlas cannot run collMod, so the validator is set only when the
    # collection is created. scripts/seed.py drops and recreates it.
    if "customers" not in db.list_collection_names():
        db.create_collection("customers", validator=CUSTOMER_VALIDATOR, validationAction="error")
    if "invoices" not in db.list_collection_names():
        db.create_collection("invoices", validator=VALIDATOR, validationAction="error")
    db.customers.create_index("code", unique=True, name="customer_code_unique")
    db.customers.create_index("city", name="customer_city")
    db.invoices.create_index("invoiceNumber", unique=True, name="invoice_number_unique")
    db.invoices.create_index("customerName", name="customer_name")
    db.invoices.create_index("customerId", name="customer_id")
