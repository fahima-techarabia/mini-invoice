import os
from functools import lru_cache

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()


def _setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or "<" in value:
        raise RuntimeError(f"{name} is missing or still has a <placeholder>. Edit your .env file.")
    return value


@lru_cache
def get_client() -> MongoClient:
    return MongoClient(_setting("MONGODB_URI"), serverSelectionTimeoutMS=10000, tz_aware=True)


def get_db():
    return get_client()[_setting("MONGODB_DB")]
