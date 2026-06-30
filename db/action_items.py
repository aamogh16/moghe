"""
Action items — extracted tasks stored in the action_items table.

The orchestrator extracts tasks from user messages and stores them here;
the /tasks command lists open ones and /done marks them complete.
"""
import sqlite3
from typing import List, Dict, Optional


def insert_item(
    db_path: str, user_id: str, description: str, due_at: Optional[str] = None
) -> int:
    """Store a new open action item; return its row id."""
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO action_items (user_id, description, due_at) VALUES (?, ?, ?)",
            (user_id, description, due_at),
        )
        return cur.lastrowid


def get_open(db_path: str, user_id: str) -> List[Dict]:
    """Return open items for user_id, soonest-due first, then oldest-created."""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, description, due_at
            FROM action_items
            WHERE user_id = ? AND status = 'open'
            ORDER BY due_at IS NULL, due_at ASC, id ASC
            """,
            (user_id,),
        ).fetchall()
    return [{"id": r[0], "description": r[1], "due_at": r[2]} for r in rows]


def mark_done(db_path: str, user_id: str, item_id: int) -> bool:
    """Mark an open item done. Return True if a row was actually updated."""
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE action_items
            SET status = 'done'
            WHERE id = ? AND user_id = ? AND status = 'open'
            """,
            (item_id, user_id),
        )
        return cur.rowcount > 0
