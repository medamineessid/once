"""GUI tests for the agent-proposal review journey.

The tests build a real temporary Git repository and use the deterministic
fake agent whose behaviour is selected by the evidence file stem, exactly as
in test_coding_agent.py. No live AI services and no network access.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from controller.service import WorkflowService
from storage.database import connect
from storage.history import ExecutionHistory
from ui.main_window import MainWindow
from ui.review_view import ProposalReviewPanel

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

AGENT_SCRIPT = """\
import pathlib
import sys

evidence = pathlib.Path(sys.argv[1])
behavior = evidence.stem
extractor = pathlib.Path("extractor.py")
if behavior in ("good", "badfix"):
    expected = "105.0" if behavior == "good" else "-1.0"
    extractor.write_text(
        "import json, sys\\n"
        "with open(sys.argv[1], encoding='utf-8') as handle:\\n"
        "    invoice = json.load(handle)\\n"
        f"totals = {{'INV-1': {expected}}}\\n"
        "print(json.dumps({'invoice_number': invoice['invoice_number'],\\n"
        "    'total': totals.get(invoice['invoice_number'], -1)}))\\n",
        encoding="utf-8",
    )
"""

BUGGY_EXTRACTOR = (
    "import json, sys\n"
    "with open(sys.argv[1], encoding='utf-8') as handle:\n"
    "    invoice = json.load(handle)\n"
    "print(json.dumps({'invoice_number': invoice['invoice_number'],\n"
    "    'total': invoice['total']}))\n"
)


def run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),  # noqa: S607 - test fixture uses managed git
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "hotix"
    repo.mkdir()
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test")
    (repo / "extractor.py").write_text(BUGGY_EXTRACTOR, encoding="utf-8")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "v1")
    return repo


def agent_command(tmp_path: Path) -> tuple[str, ...]:
    script = tmp_path / "agent.py"
    script.write_text(AGENT_SCRIPT, encoding="utf-8")
    return (sys.executable, str(script), "{evidence}")


def evidence(tmp_path: Path, behavior: str) -> Path:
    directory = tmp_path / "evidence"
    directory.mkdir(exist_ok=True)
    path = directory / f"{behavior}.json"
    path.write_text(json.dumps({"issue": behavior}), encoding="utf-8")
    return path


def acceptance_setup(tmp_path: Path) -> tuple[Path, tuple[str, ...]]:
    """Return (cases_path, verifier argv) bound to the worktree checkout.

    The check runs the proposed extractor.py committed by the fake agent in
    its worktree against a synthetic Hotix invoice, so pre-merge verification
    exercises the exact proposal commit.
    """
    invoice = tmp_path / "invoice.json"
    invoice.write_text(json.dumps({"invoice_number": "INV-1", "total": 100.0}), encoding="utf-8")
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "inv-1",
                    "input_file": str(invoice),
                    "expected": {
                        "total": {
                            "value": 105.0,
                            "mode": "numeric_tolerance",
                            "tolerance": 0.01,
                            "required": True,
                        }
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    return cases_path, (sys.executable, "{checkout}/extractor.py", "{input}")


def make_panel(
    qtbot: QtBot, tmp_path: Path, repo: Path
) -> tuple[ProposalReviewPanel, WorkflowService]:
    service = WorkflowService(history=ExecutionHistory(connect(tmp_path / "history.db")))
    cases_path, argv = acceptance_setup(tmp_path)
    panel = ProposalReviewPanel(
        service,
        verifier_config=(cases_path, argv, 10.0, tmp_path / "worktrees"),
    )
    qtbot.addWidget(panel)
    return panel, service


def make_main_window(qtbot: QtBot, tmp_path: Path) -> tuple[MainWindow, WorkflowService, Path]:
    service = WorkflowService(history=ExecutionHistory(connect(tmp_path / "history.db")))
    cases_path, argv = acceptance_setup(tmp_path)
    window = MainWindow(service, verifier_config=(cases_path, argv, 10.0, tmp_path / "worktrees"))
    window.show()
    qtbot.addWidget(window)
    return window, service, cases_path


def request_proposal(
    panel: ProposalReviewPanel, service: WorkflowService, tmp_path: Path, repo: Path, behavior: str
) -> None:
    service.request_agent_fix(repo, agent_command(tmp_path), 10.0, evidence(tmp_path, behavior))
    panel.refresh_proposals()


def test_panel_shows_diff_and_enables_approval_after_passing_verification(
    qtbot: QtBot, tmp_path
) -> None:
    repo = make_repo(tmp_path)
    panel, service = make_panel(qtbot, tmp_path, repo)
    request_proposal(panel, service, tmp_path, repo, "good")

    panel._proposal_list.setCurrentRow(0)
    assert "+" in panel._diff_view.toPlainText()
    assert "extractor.py" in panel._changed_files_label.text()

    qtbot.waitSignal(panel._verify_worker_done, timeout=30_000)
    panel._verify_selected()
    qtbot.waitUntil(lambda: "verification" in panel.status_text().lower(), timeout=30_000)

    qtbot.waitUntil(lambda: panel._approve_button.isEnabled(), timeout=10_000)
    panel._approve_and_apply()
    qtbot.waitUntil(lambda: panel.status_text().startswith("Applied"), timeout=10_000)
    qtbot.waitUntil(lambda: "105.0" in (repo / "extractor.py").read_text(encoding="utf-8"))
    qtbot.waitSignal(panel._apply_worker_done, timeout=30_000)
    assert "105.0" in (repo / "extractor.py").read_text(encoding="utf-8")
    records = service.agent_proposals()
    phases = {
        record.phase for record in service.proposal_verifications(records[0].review.proposal_id)
    }
    assert phases == {"PRE_MERGE", "POST_MERGE"}


def test_panel_disables_approval_and_explains_when_checks_fail(qtbot: QtBot, tmp_path) -> None:
    repo = make_repo(tmp_path)
    panel, service = make_panel(qtbot, tmp_path, repo)
    request_proposal(panel, service, tmp_path, repo, "badfix")

    panel._proposal_list.setCurrentRow(0)
    qtbot.waitUntil(lambda: panel._diff_view.toPlainText() != "", timeout=10)
    panel._verify_selected()
    qtbot.waitUntil(lambda: "verification" in panel.status_text().lower(), timeout=30_000)

    assert not panel._approve_button.isEnabled()
    assert "did not pass" in panel._blockers_label.text()
    now_text = (repo / "extractor.py").read_text(encoding="utf-8")
    assert "105.0" not in now_text


def test_panel_rejection_persists_and_blocks_further_decisions(qtbot: QtBot, tmp_path) -> None:
    repo = make_repo(tmp_path)
    panel, service = make_panel(qtbot, tmp_path, repo)
    request_proposal(panel, service, tmp_path, repo, "good")

    panel._proposal_list.setCurrentRow(0)
    qtbot.waitUntil(lambda: panel._diff_view.toPlainText() != "", timeout=10)
    panel._reject_selected()
    qtbot.waitUntil(lambda: "rejected" in panel.status_text().lower(), timeout=10)

    records = service.agent_proposals()
    assert records[0].status == "REJECTED"
    assert not panel._approve_button.isEnabled()
    assert not panel._reject_button.isEnabled()


def test_panel_survives_restart_with_persisted_decisions(qtbot: QtBot, tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    panel, service = make_panel(qtbot, tmp_path, repo)
    request_proposal(panel, service, tmp_path, repo, "good")
    panel._proposal_list.setCurrentRow(0)
    qtbot.waitUntil(lambda: panel._diff_view.toPlainText() != "", timeout=10)
    panel._reject_selected()
    qtbot.waitUntil(lambda: "rejected" in panel.status_text().lower(), timeout=10)
    service.close()

    restarted = WorkflowService(history=ExecutionHistory(connect(tmp_path / "history.db")))
    cases_path, argv = acceptance_setup(tmp_path)
    reborn = ProposalReviewPanel(
        restarted,
        verifier_config=(cases_path, argv, 10.0, tmp_path / "worktrees"),
    )
    qtbot.addWidget(reborn)
    reborn.refresh_proposals()
    reborn._proposal_list.setCurrentRow(0)
    qtbot.waitUntil(lambda: reborn._diff_view.toPlainText() != "", timeout=10)
    assert "REJECTED" in reborn._status_label.text()
    assert not reborn._approve_button.isEnabled()
    restarted.close()


def test_panel_shows_incomplete_when_persisted_evidence_is_missing(
    qtbot: QtBot, tmp_path: Path
) -> None:
    from storage.database import connect as db_connect

    repo = make_repo(tmp_path)
    panel, service = make_panel(qtbot, tmp_path, repo)
    request_proposal(panel, service, tmp_path, repo, "good")
    panel._proposal_list.setCurrentRow(0)
    qtbot.waitUntil(lambda: panel._diff_view.toPlainText() != "", timeout=10)

    # Simulate a corrupted history: a verification row whose run evidence
    # never landed in the acceptance_runs table (FK-persistent records can be
    # broken by a failed migration on an older database).
    with db_connect(tmp_path / "history.db") as database:
        database.execute("PRAGMA foreign_keys = OFF")
        database.execute(
            """
            INSERT INTO proposal_verifications
                (proposal_id, agent_tip, phase, verification_run_id,
                 passed, cancelled, checked_at)
            VALUES (?, ?, 'PRE_MERGE', 'missing-run-id', 1, 0, ?)
            """,
            (
                panel._records[0].review.proposal_id,
                panel._records[0].review.agent_tip,
                "2026-10-24T00:00:00+00:00",
            ),
        )
    panel._load_verifications(panel._records[0].review)

    items = [
        panel._verification_list.item(index).text()
        for index in range(panel._verification_list.count())
    ]
    assert any("INCOMPLETE (evidence is missing)" in item for item in items)
    assert any("Evidence for this run was not found." in item for item in items)
    service.close()


def test_main_window_agent_proposals_tab_completes_the_journey(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, service, _cases = make_main_window(qtbot, tmp_path)
    repo = make_repo(tmp_path)
    service.request_agent_fix(repo, agent_command(tmp_path), 10.0, evidence(tmp_path, "good"))
    panel = window._review_panel
    panel.refresh_proposals()
    panel._proposal_list.setCurrentRow(0)
    qtbot.waitUntil(lambda: panel._diff_view.toPlainText() != "", timeout=10)
    assert not panel._approve_button.isEnabled()

    panel._verify_selected()
    qtbot.waitUntil(lambda: "verification" in panel.status_text().lower(), timeout=120_000)
    qtbot.waitUntil(lambda: panel._approve_button.isEnabled(), timeout=120_000)

    panel._approve_and_apply()
    qtbot.waitUntil(lambda: "Applied" in panel.status_text(), timeout=120_000)
    assert "105.0" in (repo / "extractor.py").read_text(encoding="utf-8")
    records = service.agent_proposals()
    phases = {
        record.phase for record in service.proposal_verifications(records[0].review.proposal_id)
    }
    assert phases == {"PRE_MERGE", "POST_MERGE"}
    service.close()


def test_main_window_requires_configured_checker_for_verification(
    qtbot: QtBot, tmp_path: Path, monkeypatch
) -> None:
    service = WorkflowService(history=ExecutionHistory(connect(tmp_path / "history.db")))
    warnings: list[str] = []
    monkeypatch.setattr(
        "ui.review_view.QMessageBox.warning",
        lambda _parent, _title, message, *args, **kwargs: warnings.append(message),
    )
    window = MainWindow(service)
    qtbot.addWidget(window)
    panel = window._review_panel
    repo = make_repo(tmp_path)
    service.request_agent_fix(repo, agent_command(tmp_path), 10.0, evidence(tmp_path, "good"))
    panel.refresh_proposals()
    panel._proposal_list.setCurrentRow(0)
    panel._verify_selected()
    assert any("No acceptance checker" in message for message in warnings)
    assert not panel._approve_button.isEnabled()
    service.close()
