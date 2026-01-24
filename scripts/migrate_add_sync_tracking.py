"""
Migration script to add transaction sync tracking fields.

Run this script to add the last_transaction_sync_at column to user_leagues table.
This is safe to run multiple times - it checks if the column already exists.

Usage:
    python scripts/migrate_add_sync_tracking.py
"""

import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings


def get_db_path() -> str:
    """Extract database file path from DATABASE_URL."""
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "")
    raise ValueError(f"Expected SQLite database URL, got: {url}")


def column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate():
    """Run the migration."""
    db_path = get_db_path()
    print(f"Migrating database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        if column_exists(cursor, "user_leagues", "last_transaction_sync_at"):
            print("Column 'last_transaction_sync_at' already exists. Nothing to do.")
            return

        # Add the new column
        print("Adding column 'last_transaction_sync_at' to user_leagues table...")
        cursor.execute("""
            ALTER TABLE user_leagues
            ADD COLUMN last_transaction_sync_at DATETIME NULL
        """)
        conn.commit()
        print("Migration completed successfully!")

    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
