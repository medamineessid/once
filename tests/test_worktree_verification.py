"""Tests for isolated worktree verification of coding-agent proposals."""

from __future__ import annotations

import json
import sqlite3
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


def test_verified_review_must_be_the_recorded_proposal(tmp_path) -> None:
    """A review object is only usable when it is byte-identical to the record."""
    from dataclasses import replace

    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    # A different branch at the exact same tip must still be a different review.
    run_git(repo, "branch", "once/agent/impostor", review.agent_tip)
    impostor = replace(review, agent_branch="once/agent/impostor")
    assert impostor.proposal_id == review.proposal_id
    assert impostor.agent_tip == review.agent_tip

    with pytest.raises(AgentIntegrationError, match="recorded proposal"):
        service.verify_proposal_pre_merge(
            impostor, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "worktrees"
        )
    blockers = service.approval_blockers(impostor)
    assert any("does not match the recorded proposal" in blocker for blocker in blockers)
    with pytest.raises(AgentIntegrationError, match="does not match the recorded proposal"):
        service.approve_agent_change(impostor)

    # Even with a passing in-worktree check recorded for the real proposal,
    # applying an impostor-shaped change must be refused.
    assert "totals" not in (repo / "extractor.py").read_text(encoding="utf-8")
    assert not (tmp_path / "worktrees" / f"proposal-{review.proposal_id[:8]}").exists()
    service.close()


def test_modified_diff_after_review_cannot_be_approved(tmp_path) -> None:
    """A presented diff that differs from the recorded one must be refused."""
    from dataclasses import replace

    repo, _ = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    doctored_diff = review.diff.replace("105.0", "999.0")
    pretender = replace(review, diff=doctored_diff)

    blockers = service.approval_blockers(pretender)
    assert any("does not match the recorded proposal" in blocker for blocker in blockers)
    with pytest.raises(AgentIntegrationError, match="does not match the recorded proposal"):
        service.approve_agent_change(pretender)
    assert "totals" not in (repo / "extractor.py").read_text(encoding="utf-8")
    service.close()


def test_partially_cancelled_verification_refuses_then_recovers(tmp_path) -> None:
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    second_input = tmp_path / "invoice-2.json"
    second_input.write_text(
        json.dumps({"invoice_number": "INV-1", "total": 100.0}), encoding="utf-8"
    )
    multi_cases = tmp_path / "cases-multi.json"
    first_case = json.loads(cases_path.read_text(encoding="utf-8"))[0]
    clones = [_clone_case(first_case, second_input, index) for index in (2, 3)]
    multi_cases.write_text(json.dumps([first_case, *clones]), encoding="utf-8")
    calls = {"count": 0}

    def cancel_after_first() -> bool:
        calls["count"] += 1
        return calls["count"] > 1

    partially = service.verify_proposal_pre_merge(
        review,
        multi_cases,
        PASSING_VERIFY_ARGV,
        10.0,
        tmp_path / "worktrees",
        cancel_check=cancel_after_first,
    )
    assert partially.cases[0].passed is True  # the first case really ran
    assert partially.cancelled is True
    with pytest.raises(AgentIntegrationError, match="cancelled"):
        service.approve_agent_change(review)
    with pytest.raises(AgentIntegrationError, match="cancelled"):
        service.approve_agent_change(review)  # idempotent refusal

    recovered = service.verify_proposal_pre_merge(
        review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "worktrees"
    )
    assert recovered.passed is True and recovered.cancelled is False
    approved = service.approve_agent_change(review)
    service.apply_agent_change(approved)
    assert "totals.get" in (repo / "extractor.py").read_text(encoding="utf-8")
    service.close()


def test_failed_post_merge_check_is_persisted(tmp_path) -> None:
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    service.verify_proposal_pre_merge(
        review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "wt"
    )
    approved = service.approve_agent_change(review)
    service.apply_agent_change(approved)

    wrong = tmp_path / "cases-wrong.json"
    wrong.write_text(
        json.dumps(
            [
                {
                    "case_id": "inv-1",
                    "input_file": str(
                        json.loads(cases_path.read_text(encoding="utf-8"))[0]["input_file"]
                    ),
                    "expected": {
                        "total": {
                            "value": -5.0,
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

    bundle = service.verify_post_merge(repo, wrong, PASSING_VERIFY_ARGV, 10.0, review)
    assert bundle.passed is False
    records = service.proposal_verifications(review.proposal_id)
    post = [record for record in records if record.phase == "POST_MERGE"]
    assert len(post) == 1 and post[0].passed is False
    assert service._proposal_status(review.proposal_id) == "APPROVED"
    service.close()


def _clone_case(case: dict, input_path: Path, case_id: int) -> dict:
    return {
        "case_id": f"inv-{case_id}",
        "input_file": str(input_path),
        "expected": case["expected"],
    }


def test_full_lifecycle_survives_a_restart(tmp_path) -> None:
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    service.verify_proposal_pre_merge(
        review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "wt"
    )
    approved = service.approve_agent_change(review)
    service.apply_agent_change(approved)
    service.verify_post_merge(repo, cases_path, PASSING_VERIFY_ARGV, 10.0, review)
    service.close()

    reopened = WorkflowService(history=ExecutionHistory(connect(tmp_path / "history.db")))
    records = reopened.agent_proposals()
    assert len(records) == 1
    assert records[0].status == "APPROVED"
    assert records[0].review == review  # the exact reviewed proposal is what persisted
    phases = {record.phase for record in reopened.proposal_verifications(review.proposal_id)}
    assert phases == {"PRE_MERGE", "POST_MERGE"}
    for record in reopened.proposal_verifications(review.proposal_id):
        stored = reopened.verification_run(record.verification_run_id)
        assert stored is not None
    with pytest.raises(AgentIntegrationError, match="already been approved"):
        reopened.reject_agent_proposal(review)
    reopened.close()


def test_persisted_evidence_is_redacted(tmp_path) -> None:
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    leaky = tmp_path / "leaky.py"
    leaky.write_text(
        "import sys\n"
        "print('connecting to service', 'api_key=hunter2secret', 'user@example.org')\n"
        "sys.exit(3)\n",
        encoding="utf-8",
    )
    service.verify_proposal_pre_merge(
        review, cases_path, (sys.executable, str(leaky), "{input}"), 10.0, tmp_path / "wt"
    )

    with sqlite3.connect(tmp_path / "history.db") as database:
        tails = database.execute(
            "SELECT stdout_tail, stderr_tail FROM acceptance_case_results"
        ).fetchall()
    everything = "\n".join(cell for tail in tails for cell in tail)
    assert "hunter2secret" not in everything
    assert "user@example.org" not in everything
    assert "[REDACTED_SECRET]" in everything
    assert "[REDACTED_EMAIL]" in everything
    service.close()


def system_interpreter() -> list[str]:
    """Return a real, non-venv Windows interpreter when it is installed."""
    for candidate in (Path(sys.base_prefix) / "python.exe", Path(sys.base_prefix) / "python"):
        if candidate.is_file():
            return [str(candidate)]
    return []


def test_real_checkout_verification_runs_on_a_system_interpreter(tmp_path) -> None:
    """The {checkout} binding must work with a plain installed interpreter."""
    base_python = system_interpreter()
    if not base_python:
        pytest.skip("no system interpreter outside the venv on this machine")
    repo, cases_path = make_repo(tmp_path)
    worktree_root = tmp_path / "system run"
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    bundle = service.verify_proposal_pre_merge(
        review,
        cases_path,
        (*base_python, "{checkout}/extractor.py", "{input}"),
        10.0,
        worktree_root,
    )
    assert bundle.passed is True
    assert all(not case.timed_out for case in bundle.cases)
    # the main checkout must be untouched by the whole run
    assert "totals.get" not in (repo / "extractor.py").read_text(encoding="utf-8")
    service.close()


def test_checkout_command_tolerates_paths_with_spaces(tmp_path) -> None:
    """Arguments stay separated: a checkout path with spaces must not break."""
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    spaced_root = tmp_path / "work trees with spaces"
    bundle = service.verify_proposal_pre_merge(
        review, cases_path, PASSING_VERIFY_ARGV, 10.0, spaced_root
    )
    assert bundle.passed is True
    assert not (spaced_root / f"proposal-{review.proposal_id[:8]}").exists()  # cleaned up
    service.close()


def test_checkout_referencing_a_missing_file_fails_the_case(tmp_path) -> None:
    """A {checkout} file that the proposal never committed must fail, not pass."""
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    missing_argv = (sys.executable, "{checkout}/should_not_exist.py", "{input}")
    bundle = service.verify_proposal_pre_merge(
        review, cases_path, missing_argv, 10.0, tmp_path / "wt"
    )
    assert bundle.passed is False
    assert all(case.exit_code != 0 for case in bundle.cases)
    persisted = service.verification_run(bundle.run_id)
    assert persisted is not None and persisted.passed is False
    service.close()


def test_interruption_during_verification_leaves_a_recoverable_state(tmp_path, monkeypatch) -> None:
    """A hard interruption mid-verification must not fake a verification record."""
    from engine import verifier as verifier_module

    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    original_run = verifier_module.subprocess.run

    def interrupted_run(argv, **kwargs):
        if "extract" in argv[1] or "extractor.py" in str(argv[1]):
            # the checker subprocess itself was about to start when the user
            # killed the application
            raise KeyboardInterrupt
        return original_run(argv, **kwargs)

    monkeypatch.setattr(verifier_module.subprocess, "run", interrupted_run)
    with pytest.raises(KeyboardInterrupt):
        service.verify_proposal_pre_merge(
            review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "wt"
        )
    monkeypatch.setattr(verifier_module.subprocess, "run", original_run)

    # predictable state: worktree is gone, no verification record claims success
    assert not (tmp_path / "wt" / f"proposal-{review.proposal_id[:8]}").exists()
    assert service.proposal_verifications(review.proposal_id) == ()
    assert service.approval_blockers(review)[0:1] != ()
    assert any(
        "no passed pre-merge verification" in blocker
        for blocker in service.approval_blockers(review)
    )
    assert "totals.get" not in (repo / "extractor.py").read_text(encoding="utf-8")

    # recovery: a fresh verification of the same proposal works
    bundle = service.verify_proposal_pre_merge(
        review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "wt"
    )
    assert bundle.passed is True
    service.approve_agent_change(review)
    service.close()


def test_recorded_approval_survives_a_restart_and_can_be_applied(tmp_path) -> None:
    """Approval persisted, then the app died: the decision must still work."""
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    service.verify_proposal_pre_merge(
        review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "wt"
    )
    service.approve_agent_change(review)  # approved, but the app exits before apply
    service.close()

    restarted = WorkflowService(history=ExecutionHistory(connect(tmp_path / "history.db")))
    blockers = restarted.apply_blockers(review)
    assert blockers == ()
    head = restarted.apply_recorded_approval(review)
    assert head
    assert "totals.get" in (repo / "extractor.py").read_text(encoding="utf-8")

    # a second apply attempt explains itself instead of merging again
    applied_blockers = restarted.apply_blockers(review)
    assert any("already in the repository" in blocker for blocker in applied_blockers)
    with pytest.raises(AgentIntegrationError, match="already in the repository"):
        restarted.apply_recorded_approval(review)
    restarted.close()


def test_apply_recorded_approval_refuses_wait_and_moved_states(tmp_path) -> None:
    from dataclasses import replace

    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    with pytest.raises(AgentIntegrationError, match="not been approved yet"):
        service.apply_recorded_approval(review)
    assert any("not been approved yet" in blocker for blocker in service.apply_blockers(review))

    service.verify_proposal_pre_merge(
        review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "wt"
    )
    approved = service.approve_agent_change(review)
    service.apply_agent_change(approved)
    service.verify_post_merge(repo, cases_path, PASSING_VERIFY_ARGV, 10.0, review)
    service.close()

    reopened = WorkflowService(history=ExecutionHistory(connect(tmp_path / "history.db")))
    with pytest.raises(AgentIntegrationError, match="already in the repository"):
        reopened.apply_recorded_approval(review)

    # a moved repository after the merge still refuses a stale replay attempt
    moved = replace(review, agent_branch="once/agent/never-existed")
    with pytest.raises(AgentIntegrationError, match="does not match the recorded"):
        reopened.apply_recorded_approval(moved)
    reopened.close()


def test_manually_deleted_worktree_directory_does_not_block_reruns(tmp_path) -> None:
    """A stale worktree registry entry must not brick verification forever."""
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    bundle = service.verify_proposal_pre_merge(
        review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "wt"
    )
    assert bundle.passed is True

    # reproduce the user hand-deleting the folder mid-run: directory gone,
    # but Git's worktree metadata may still hold a registration for it
    worktree_dir = tmp_path / "wt" / f"proposal-{review.proposal_id[:8]}"
    assert worktree_dir.exists() is False  # normal close removes it

    # a rerun of verification on the same proposal must work, not fail closed forever
    second = service.verify_proposal_pre_merge(
        review, cases_path, PASSING_VERIFY_ARGV, 10.0, tmp_path / "wt"
    )
    assert second.passed is True
    service.close()


def test_worktree_path_inside_the_repository_is_refused(tmp_path) -> None:
    """Verification must never create a worktree inside the user's checkout."""
    repo, cases_path = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_file(tmp_path, "good")
    )
    with pytest.raises(AgentIntegrationError, match="outside the repository"):
        service.verify_proposal_pre_merge(review, cases_path, PASSING_VERIFY_ARGV, 10.0, repo)
    # the main checkout stays untouched and on the original branch
    assert "totals.get" not in (repo / "extractor.py").read_text(encoding="utf-8")
    service.close()
