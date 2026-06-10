"""
Conversation history — read and write turns to the conversations table.
"""
import sqlite3
from typing import List, Dict


def get_recent(db_path: str, user_id: str, limit: int = 20) -> List[Dict[str, str]]:
    """Return the last `limit` turns for user_id, oldest-first."""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT role, content FROM (
                SELECT role, content, ts
                FROM conversations
                WHERE user_id = ?
                ORDER BY ts DESC
                LIMIT ?
            ) ORDER BY ts ASC
            """,
            (user_id, limit),
        ).fetchall()
    return [{"role": row[0], "content": row[1]} for row in rows]


def insert_turn(db_path: str, user_id: str, role: str, content: str) -> None:
    """Append a single turn (role: 'user' or 'assistant') to the history."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content),
        )
