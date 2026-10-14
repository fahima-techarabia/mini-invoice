"""Read-only connection check. Never prints the connection string or password."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError

from app.db import get_db

try:
    db = get_db()
    db.command("ping")
    print(f"OK: connected. Database: {db.name}")
    auth = db.command("connectionStatus")["authInfo"]
    for user in auth["authenticatedUsers"]:
        print(f"Logged in as: {user['user']}")
    roles = [f"{role['role']}@{role['db']}" for role in auth["authenticatedUserRoles"]]
    print(f"Roles: {roles or 'none'}")
    print(f"Collections: {', '.join(sorted(db.list_collection_names())) or 'none'}")
    print(f"Invoices: {db.invoices.count_documents({})}")
except RuntimeError as exc:
    print(f"SETUP PROBLEM: {exc}")
except OperationFailure as exc:
    print(f"REFUSED BY ATLAS (code {exc.code}): {exc.details.get('errmsg', 'no message')}")
except ServerSelectionTimeoutError:
    print("CANNOT REACH THE CLUSTER: check Atlas Network Access has your current IP.")
except ConfigurationError:
    print("CONNECTION STRING PROBLEM: check the format in .env.")
