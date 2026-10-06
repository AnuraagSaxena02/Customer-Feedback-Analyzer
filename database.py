"""
All the database work lives here (Lesson 12).

Keeping the database code in its own file makes app.py shorter and easier to
read. app.py just imports these functions and uses them.
"""

import sqlite3

# Our database file. It stores every review we ever analyze.
DB_FILE = "feedback.db"


def init_db():
    """Create the feedback table the first time we run."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY,
            review TEXT,
            label TEXT,
            score INTEGER,
            theme TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_results(results):
    """Write all analyzed reviews into the database."""
    conn = sqlite3.connect(DB_FILE)
    for r in results:
        conn.execute(
            "INSERT INTO feedback (review, label, score, theme) VALUES (?, ?, ?, ?)",
            (r["review"], r["label"], r["score"], r["theme"]),
        )
    conn.commit()
    conn.close()


def load_history():
    """Read every review we have saved so far."""
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute(
        "SELECT review, label, score, theme FROM feedback"
    ).fetchall()
    conn.close()
    return rows