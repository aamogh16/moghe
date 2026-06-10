"""
Run once (or on every startup — it's idempotent) to ensure the DB and tables exist.
"""
import sqlite3
import os
from pathlib import Path


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    schema = (Path(__file__).parent / "schema.sql").read_text()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema)
    print(f"[db] initialised at {db_path}")


if __name__ == "__main__":
    from config import DB_PATH
    init_db(DB_PATH)
