"""Time-boxed MVP probe: what is in the history DB, esp. recording-draft runs."""

import sqlite3
import sys

DB = r"C:\Users\DELL\AppData\Local\Once\history.db"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

total = con.execute("SELECT COUNT(*) FROM workflow_runs").fetchone()[0]
print("total runs:", total)
rows = con.execute(
    "SELECT run_id, workflow_id, status, started_at FROM workflow_runs"
    " ORDER BY started_at DESC LIMIT 15"
).fetchall()
for r in rows:
    steps = con.execute(
        "SELECT step_id, status, message, evidence FROM workflow_step_results"
        " WHERE run_id=? ORDER BY position",
        (r["run_id"],),
    ).fetchall()
    step_text = " ; ".join("{sid}:{st}".format(sid=s["step_id"], st=s["status"]) for s in steps)[
        :110
    ]
    print(
        r["workflow_id"][:40].ljust(42),
        r["status"].ljust(18),
        r["started_at"][:16],
        step_text,
    )
# Any run rows that are from recorded drafts (any name containing draft/recording markers).
draft_like = con.execute(
    "SELECT workflow_id, COUNT(*) FROM workflow_runs"
    " WHERE workflow_id LIKE '%draft%' OR workflow_id LIKE '%Recording%'"
    " OR workflow_id LIKE '%recording%' GROUP BY workflow_id"
).fetchall()
print("draft-like workflow ids:", [(d[0], d[1]) for d in draft_like])
con.close()
sys.exit(0)
