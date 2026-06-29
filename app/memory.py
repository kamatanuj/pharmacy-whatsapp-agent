"""
Memory Management — SQLite
Stores chat history per phone number with 2-hour TTL auto-wipe.
"""

import sqlite3
import os
import time
from datetime import datetime, timedelta

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "chat.db"
)

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_db() -> sqlite3.Connection:
    """Get a SQLite connection (creates DB if needed)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the chat history table if it doesn't exist."""
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phone_timestamp
        ON chat_history (phone_number, timestamp DESC)
        """
    )
    conn.commit()
    conn.close()


def get_chat_history(phone_number: str, limit: int = 15) -> list:
    """
    Fetch last N messages for a phone number.
    Auto-wipes messages older than 2 hours (TTL).
    """
    conn = get_db()

    # TTL wipe — delete messages older than 2 hours
    cutoff = (datetime.now() - timedelta(hours=2)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    conn.execute(
        "DELETE FROM chat_history WHERE timestamp < ? AND phone_number = ?",
        (cutoff, phone_number),
    )
    conn.commit()

    # Fetch last N messages (oldest first for conversation order)
    rows = conn.execute(
        """
        SELECT role, content FROM chat_history
        WHERE phone_number = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (phone_number, limit),
    ).fetchall()

    conn.close()

    # Reverse to get chronological order
    messages = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    return messages


def save_to_history(phone_number: str, role: str, content: str):
    """Save a message to chat history."""
    conn = get_db()
    conn.execute(
        "INSERT INTO chat_history (phone_number, role, content) VALUES (?, ?, ?)",
        (phone_number, role, content),
    )
    conn.commit()
    conn.close()


def clear_session_memory(phone_number: str):
    """Clear all chat history for a phone number (restart command)."""
    conn = get_db()
    conn.execute(
        "DELETE FROM chat_history WHERE phone_number = ?", (phone_number,)
    )
    conn.commit()
    conn.close()


def cleanup_all_expired():
    """Wipe all expired messages across all phone numbers (for cron/maintenance)."""
    conn = get_db()
    cutoff = (datetime.now() - timedelta(hours=2)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    conn.execute(
        "DELETE FROM chat_history WHERE timestamp < ?", (cutoff,)
    )
    conn.commit()
    conn.close()