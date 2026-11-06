"""Probe once.db (the second DB in the app dir) and list any runs there."""

import sqlite3

DB = r"C:\Users\DELL\AppData\Local\Once\once.db"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
tables = [
    t["name"] for t in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
]
print("tables:", tables)
for table in tables:
    try:
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count}")
    except sqlite3.Error as error:
        print(f"  {table}: <{error}>")
for table in ("workflow_runs", "runs", "history_runs"):
    if table in tables:
        cols = [c["name"] for c in con.execute(f"PRAGMA table_info({table})")]
        print(f"{table} cols:", cols)
        for row in con.execute(f"SELECT * FROM {table} ORDER BY 1 DESC LIMIT 8"):
            print(dict(row))
con.close()
