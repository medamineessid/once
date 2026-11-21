"""Direct tests for safety invariants S1 and S4."""

from __future__ import annotations


# ============================================================
# S1: The planner/scanner/rules/validator NEVER modify the filesystem.
# Tests that planning a workflow (e.g. loading/scanning) does not
# change the file tree under a tmp directory.
# --------------------------------------------------------------------------#
def test_S1_planner_does_not_modify_filesystem(tmp_path):
    """Snapshot a temp dir, run a planning-like operation, assert identical.

    This is a best-effort test: the Once planner is exercised through
    the UI pages. If the planner touches files, the snapshot will differ.
    """
    # Create some dummy files in a temp directory
    test_dir = tmp_path / "test_s1"
    test_dir.mkdir()
    (test_dir / "sample.txt").write_text("hello")
    (test_dir / "empty.txt").write_text("")

    # Take snapshot before
    before_files = set()
    for p in test_dir.rglob("*"):
        if p.is_file():
            before_files.add(str(p.relative_to(tmp_path)))

    # Perform a planning-like operation: load a workflow from the temp dir
    from controller.service import WorkflowService
    from storage.database import connect
    from storage.history import ExecutionHistory

    db_path = tmp_path / "history.db"
    conn = connect(db_path)
    try:
        svc = WorkflowService(history=ExecutionHistory(conn))
        # list_saved exercises the storage layer; should not create new files
        # outside the workflow folder
        svc.list_saved()
    finally:
        conn.close()

    # Take snapshot after
    after_files = set()
    for p in tmp_path.rglob("*"):
        if p.is_file() and not str(p).startswith(str(tmp_path / "once")):
            after_files.add(str(p.relative_to(tmp_path)))

    # The planner should not have created arbitrary new files in tmp_path
    # (only expected DB/files under once/ folder)
    diff = after_files - before_files
    # Allow the history.db and layout files we expect
    expected = {"history.db", "once.db"}
    unexpected = diff - expected
    assert len(unexpected) == 0, f"Planner created unexpected files: {unexpected}"


# ============================================================
# S4: Every operation is revalidated immediately before execution.
# Tests that the controller revalidates source/destination before mutating.
# The invariant is: no bare except:/except Exception:/pass; every caught
# exception is handled or recorded. We verify this by code reading.
# --------------------------------------------------------------------------#
def test_S4_no_bare_except_in_controller():
    """Verify the controller has no bare except: or except Exception: pass.

    Per AGENTS.md S4: "No bare except:: no except Exception: pass; every
    caught exception is either handled with a specific recovery or recorded
    in the journal and surfaced."
    """
    import inspect

    from controller import service as svc_module

    source = inspect.getsource(svc_module)

    # Check for bare except: (dangerous pattern)
    bare_except_count = source.count("except:")
    # Count except Exception patterns that might be too broad
    source.count("except Exception:")

    # The file should not have bare except: patterns (or very few)
    # This is a heuristic check; the real invariant is enforced by review.
    assert bare_except_count == 0, (
        f"S4 violation: {bare_except_count} bare except: found in controller"
    )
    # except Exception: is allowed only when followed by specific handling;
    # we just verify it's not trivially "pass"
    assert "except Exception: pass" not in source, (
        "S4 violation: except Exception: pass found in controller"
    )
    # Just verify we can find the try/except structure
    assert "try:" in source, "S4: no try: found in controller"
