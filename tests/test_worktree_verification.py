"""Tests for isolated worktree verification of coding-agent proposals."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from controller.service import WorkflowService
from engine.errors import AgentIntegrationError, ExecutionError
from engine.verifier import AcceptanceVerifier, AllowlistedCommand
from integrations.coding_agent import WorktreeCheckout
from storage.database import connect
from storage.history import ExecutionHistory

AGENT_SCRIPT = """
import pathlib
import sys

behavior = pathlib.Path(sys.argv[1]).stem
if behavior == "crash":
    raise SystemExit(4)
extractor = pathlib.Path("extractor.py")
if behavior in ("good", "badfix"):
    expected = "105.0" if behavior == "good" else "-1.0"
    extractor.write_text(
        "import json, sys\\n"
        "with open(sys.argv[1], encoding='utf-8') as handle:\\n"
        "    invoice = json.load(handle)\\n"
        f"totals = {{'INV-1': {expected}}}\\n"
        "print(json.dumps({'invoice_number': invoice['invoice_number'],\\n"
        "    'total': totals.get(invoice['invoice_number'], -1)}))\\\n",
        encoding="utf-8",
        )
"""


def run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),  # noqa: S607 - test fixture uses managed git
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


BUGGY_EXTRACTOR = (
    "import json, sys\n"
    "with open(sys.argv[1], encoding='utf-8') as handle:\n"
    "    invoice = json.load(handle)\n"
    "print(json.dumps({'invoice_number': invoice['invoice_number'],\n"
    "    'total': invoice['total']}))\n"
)

PASSING_VERIFY_ARGV = (
    sys.executable,
    "{checkout}/extractor.py",
    "{input}",
)


def make_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "hotix"
    repo.mkdir()
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test")
    (repo / "extractor.py").write_text(BUGGY_EXTRACTOR, encoding="utf-8")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "v1")
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
                        "invoice_number": {
                            "value": "INV-1",
                            "mode": "exact",
                            "required": True,
                        },
                        "total": {
                            "value": 105.0,
                            "mode": "numeric_tolerance",
                            "tolerance": 0.01,
                            "required": True,
                        },
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    return repo, cases_path


def agent_command(tmp_path: Path) -> tuple[str, ...]:
    script = tmp_path / "agent.py"
    script.write_text(AGENT_SCRIPT, encoding="utf-8")
    return (sys.executable, str(script), "{evidence}")


def evidence_file(tmp_path: Path, behavior: str) -> Path:
    directory = tmp_path / "evidence"
    directory.mkdir(exist_ok=True)
    path = directory / f"{behavior}.json"
    path.write_text(json.dumps({"task": "fix extraction"}), encoding="utf-8")
    return path


def make_service(tmp_path: Path) -> WorkflowService:
    return WorkflowService(history=ExecutionHistory(connect(tmp_path / "history.db")))


def test_allowlisted_command_supports_one_checkout_placeholder() -> None:
    command = AllowlistedCommand(PASSING_VERIFY_ARGV)
    arguments = command.for_input(Path("in.txt"), checkout=Path("wt"))
    assert f"{Path('wt')}/extractor.py" in arguments


def test_allowlisted_command_rejects_double_or_missing_checkout() -> None:
    with pytest.raises(ExecutionError):
        AllowlistedCommand((sys.executable, "{checkout}/a", "{checkout}/b", "{input}"))
    command = AllowlistedCommand(PASSING_VERIFY_ARGV)
    with pytest.raises(ExecutionError):
        command.for_input(Path("in.txt"))


def test_verifier_marks_remaining_cases_cancelled(tmp_path) -> None:
    from engine.acceptance import AcceptanceCase

    script = tmp_path / "extractor.py"
    script.write_text("print(json.dumps({}))".replace("{}", '{"x": 1}'), encoding="utf-8")
    (tmp_path / "in.txt").write_text("ok", encoding="utf-8")
    cases = tuple(
        AcceptanceCase.from_dict(
            {
                "case_id": str(index),
                "input_file": str(tmp_path / "in.txt"),
                "expected": {"x": {"value": 1, "mode": "exact", "required": True}},
            }
        )
        for index in range(3)
    )

    bundle = AcceptanceVerifier(
        AllowlistedCommand((sys.executable, str(script), "{input}"))
    ).verify(cases, cancel_check=lambda: True)

    assert bundle.passed is False
    assert bundle.cancelled is True


def test_worktree_checkouts_binds_exact_commit_and_refuses_stale_dirs(tmp_path) -> None:
    repo, _ = make_repo(tmp_path)
    commit = run_git(repo, "rev-parse", "HEAD")
    worktree_root = tmp_path / "worktrees"
    worktree_root.mkdir()
    checkout = WorktreeCheckout(repo, worktree_root / "proposal-abc12345")
    checkout.create(commit)

    listed = run_git(repo, "worktree", "list", "--porcelain")
    assert "detached" in listed
    assert (worktree_root / "proposal-abc12345").exists()
    assert checkout.close() is True
    assert not (worktree_root / "proposal-abc12345").exists()

    leftover = worktree_root / "proposal-abc12345"
    leftover.mkdir()
    (leftover / "junk.txt").write_text("crash remains", encoding="utf-8")
    worktree = WorktreeCheckout(repo, leftover)
    with pytest.raises(AgentIntegrationError, match="leftover"):
        worktree.create(commit)


def test_pre_merge_verification_runs_in_worktree_and_gates_approval(tmp_path) -> None:
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )

    main_before = (repo / "extractor.py").read_text(encoding="utf-8")
    bundle = service.verify_proposal_pre_merge(
        review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "worktrees"
    )

    assert bundle.passed is True
    assert bundle.cancelled is False
    main_after = (repo / "extractor.py").read_text(encoding="utf-8")
    assert "round(invoice" not in main_after
    assert main_before == main_after
    assert service.approval_blockers(review) == ()

    approved = service.approve_agent_change(review)
    service.apply_agent_change(approved)
    assert "totals.get" in (repo / "extractor.py").read_text(encoding="utf-8")
    post = service.verify_post_merge(repo, cases_path, PASSING_VERIFY_ARGV, 10.0, review)
    assert post.passed is True
    phases = {record.phase for record in service.proposal_verifications(review.proposal_id)}
    assert phases == {"PRE_MERGE", "POST_MERGE"}
    service.close()


def test_approval_refused_without_or_with_failed_verification(tmp_path) -> None:
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "badfix")
    )

    with pytest.raises(AgentIntegrationError, match="pre-merge verification"):
        service.approve_agent_change(review)

    bundle = service.verify_proposal_pre_merge(
        review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "worktrees"
    )
    assert bundle.passed is False  # the badfix agent proposed a wrong extractor
    with pytest.raises(AgentIntegrationError, match="did not pass"):
        service.approve_agent_change(review)
    service.close()


def test_cancelled_verification_cannot_approve(tmp_path) -> None:
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )

    bundle = service.verify_proposal_pre_merge(
        review,
        cases_path,
        PASSING_VERIFY_ARGV,
        10.0,
        tmp_path / "worktrees",
        cancel_check=lambda: True,
    )

    assert bundle.cancelled is True
    with pytest.raises(AgentIntegrationError, match=r"cancelled|verified"):
        service.approve_agent_change(review)
    assert "totals" not in (repo / "extractor.py").read_text(encoding="utf-8")
    service.close()


def test_timed_out_check_blocks_approval_without_evidence_of_passing(tmp_path) -> None:
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    slow = tmp_path / "slow.py"
    slow.write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
    slow_argv = (sys.executable, str(slow), "{input}")

    bundle = service.verify_proposal_pre_merge(
        review, cases_path, slow_argv, 0.2, tmp_path / "worktrees"
    )

    assert bundle.passed is False
    assert bundle.cancelled is False
    assert all(case.timed_out for case in bundle.cases)
    with pytest.raises(AgentIntegrationError, match="did not pass"):
        service.approve_agent_change(review)
    assert not (tmp_path / "worktrees" / f"proposal-{review.proposal_id[:8]}").exists()
    service.close()


def test_duplicate_decisions_are_refused(tmp_path) -> None:
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    service.verify_proposal_pre_merge(
        review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "worktrees"
    )
    service.approve_agent_change(review)

    with pytest.raises(AgentIntegrationError, match="already been approved"):
        service.approve_agent_change(review)
    with pytest.raises(AgentIntegrationError, match="already been approved"):
        service.reject_agent_proposal(review)
    service.close()


def test_rejection_blocks_approval_and_application(tmp_path) -> None:
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    service.verify_proposal_pre_merge(
        review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "worktrees"
    )
    service.reject_agent_proposal(review)
    main_before = (repo / "extractor.py").read_text(encoding="utf-8")

    with pytest.raises(AgentIntegrationError, match=r"already been approved|rejected"):
        service.approve_agent_change(review)
    assert (repo / "extractor.py").read_text(encoding="utf-8") == main_before
    service.close()


def test_worktree_cleanup_state_is_persisted_and_detectable(tmp_path) -> None:
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    service.verify_proposal_pre_merge(
        review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "worktrees"
    )
    assert service.stale_worktrees() == ()

    # Simulate a crash that dirties the disposable worktree after verification.
    leftover = tmp_path / "worktrees" / f"proposal-{review.proposal_id[:8]}"
    leftover.mkdir(parents=True, exist_ok=True)
    (leftover / "crash-output.txt").write_text("partial", encoding="utf-8")
    main_before = (repo / "extractor.py").read_text(encoding="utf-8")
    with pytest.raises(AgentIntegrationError, match="leftover"):
        service.verify_proposal_pre_merge(
            review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "worktrees"
        )
    stale = service.stale_worktrees()
    assert len(stale) == 1
    assert stale[0].status in ("LEFTOVER", "REFUSED")
    assert stale[0].path == str(leftover.resolve())
    assert (repo / "extractor.py").read_text(encoding="utf-8") == main_before
    service.close()


def test_proposal_verification_is_bound_to_the_exact_commit(tmp_path) -> None:
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    bundle = service.verify_proposal_pre_merge(
        review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "worktrees"
    )
    records = service.proposal_verifications(review.proposal_id)
    pre_merge = next(record for record in records if record.phase == "PRE_MERGE")
    assert pre_merge.agent_tip == review.agent_tip
    assert pre_merge.verification_run_id == bundle.run_id
    stored = service.verification_run(pre_merge.verification_run_id)
    assert stored is not None
    assert stored.run_id == bundle.run_id
    assert stored.to_dict() == bundle.to_dict()
    post = service.verify_post_merge(repo, cases_path, PASSING_VERIFY_ARGV, 10.0, review)
    records = service.proposal_verifications(review.proposal_id)
    post_record = next(record for record in records if record.phase == "POST_MERGE")
    assert post_record.agent_tip == review.agent_tip
    assert post_record.verification_run_id == post.run_id
    service.close()


def test_stale_agent_tip_blocks_verification(tmp_path) -> None:
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    run_git(repo, "checkout", review.agent_branch)
    run_git(repo, "commit", "--amend", "-q", "-m", "amended")
    run_git(repo, "checkout", review.base_branch)

    with pytest.raises(AgentIntegrationError, match="tip"):
        service.verify_proposal_pre_merge(
            review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "worktrees"
        )
    with pytest.raises(AgentIntegrationError, match=r"reviewed again|tip"):
        service.approve_agent_change(review)

    amendments = run_git(repo, "rev-list", "--all", "--count")
    assert amendments == "2"
    service.close()


def test_verification_cleanup_failure_leaves_reported_stale_state(tmp_path) -> None:
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    worktree_root = tmp_path / "worktrees"
    worktree_root.mkdir()
    checkout = WorktreeCheckout(repo, worktree_root / f"proposal-{review.proposal_id[:8]}")
    checkout.create(review.agent_tip)
    # Simulate a crash that dirties the disposable worktree after verification.
    (worktree_root / f"proposal-{review.proposal_id[:8]}" / "crash-output.txt").write_text(
        "partial", encoding="utf-8"
    )
    assert checkout.close() is False
    assert (worktree_root / f"proposal-{review.proposal_id[:8]}").exists()
    main_before = (repo / "extractor.py").read_text(encoding="utf-8")

    with pytest.raises(AgentIntegrationError, match="leftover"):
        service.verify_proposal_pre_merge(
            review, cases_path, PASSING_VERIFY_ARGV, 10.0, worktree_root
        )
    assert (repo / "extractor.py").read_text(encoding="utf-8") == main_before
    service.close()
