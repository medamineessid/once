"""Probe step rows for the recording draft runs."""

import sqlite3

DB = r"C:\Users\DELL\AppData\Local\Once\once.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
for run_id in (
    "ee50003a-bf46-4e44-bfdb-f1b8abff7418",
    "9cbdb327-afd8-4df7-b3b9-5891ba6c93f7",
):
    rows = con.execute(
        "SELECT position, step_id, status, message, evidence FROM workflow_step_results"
        " WHERE run_id=? ORDER BY position",
        (run_id,),
    ).fetchall()
    print(f"--- {run_id}")
    for row in rows:
        print(
            row["position"],
            row["step_id"],
            row["status"],
            (row["message"] or "")[:80],
            (row["evidence"] or "")[:80],
        )
con.close()
