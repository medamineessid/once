"""Tests for the coding-agent proposal pipeline."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from controller.service import AgentFixProposer, WorkflowService
from engine.agent_change import ApprovedChange, approve_change
from engine.errors import AgentIntegrationError, WorkflowValidationError
from engine.loop import LoopController, LoopPolicy, LoopStatus
from engine.verifier import CaseResult, EvidenceBundle, FieldResult
from storage.database import connect
from storage.history import ExecutionHistory

AGENT_SCRIPT = """
import pathlib
import sys

evidence = pathlib.Path(sys.argv[1])
behavior = evidence.stem
if behavior == "fail":
    raise SystemExit(3)
if behavior == "big":
    with pathlib.Path("bigfile.txt").open("a", encoding="utf-8") as handle:
        handle.write("x" * 200_000)
if behavior == "new":
    pathlib.Path("newfile.txt").write_text("brand new", encoding="utf-8")
with pathlib.Path("fixme.txt").open("a", encoding="utf-8") as handle:
    handle.write("fixed\\n")
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


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test")
    (repo / "fixme.txt").write_text("original\n", encoding="utf-8")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "init")
    return repo


def agent_command(tmp_path: Path) -> tuple[str, ...]:
    script = tmp_path / "agent.py"
    script.write_text(AGENT_SCRIPT, encoding="utf-8")
    return (sys.executable, str(script), "{evidence}")


def evidence(tmp_path: Path, behavior: str = "fix") -> Path:
    path = tmp_path / f"{behavior}.json"
    path.write_text(json.dumps({"issue": behavior}), encoding="utf-8")
    return path


def make_service(tmp_path: Path) -> WorkflowService:
    service = WorkflowService(history=ExecutionHistory(connect(tmp_path / "history.db")))
    return service


def pass_pre_merge(service: WorkflowService, review: object, tmp_path: Path) -> None:
    """Record a passing pre-merge verification for review's exact commit."""
    checker = tmp_path / "checker.py"
    checker.write_text(
        "import json, sys\nimport pathlib\n"
        "assert pathlib.Path(sys.argv[1]).exists()\n"
        "print(json.dumps({'ok': True}))\n",
        encoding="utf-8",
    )
    input_path = tmp_path / "in.json"
    input_path.write_text("{}", encoding="utf-8")
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "c1",
                    "input_file": str(input_path),
                    "expected": {"ok": {"value": True, "mode": "exact", "required": True}},
                }
            ]
        ),
        encoding="utf-8",
    )
    bundle = service.verify_proposal_pre_merge(
        review,
        cases_path,
        (sys.executable, str(checker), "{input}"),
        10.0,
        tmp_path / "worktrees",
    )
    assert bundle.passed, bundle


def current_branch(repo: Path) -> str:
    return run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")


def local_branches(repo: Path) -> set[str]:
    output = run_git(repo, "branch", "--format=%(refname:short)")
    return {line.strip() for line in output.splitlines() if line.strip()}


def test_request_fix_captures_agent_diff_on_a_separate_branch(tmp_path) -> None:
    repo = make_repo(tmp_path)
    service = make_service(tmp_path)
    base_branch = current_branch(repo)

    review = service.request_agent_fix(repo, agent_command(tmp_path), 10.0, evidence(tmp_path))

    assert review.proposal_id
    assert review.agent_branch.startswith("once/agent/")
    assert len(review.agent_branch.split("/")[-1]) == 8
    assert review.base_branch == base_branch
    assert "fixed" in review.diff
    assert review.changed_files == ("fixme.txt",)
    assert review.truncated is False
    assert current_branch(repo) == base_branch
    assert service.agent_proposals()[0].status == "PENDING"
    service.close()


def test_dirty_repository_is_refused_without_a_branch(tmp_path) -> None:
    repo = make_repo(tmp_path)
    (repo / "dirty.txt").write_text("uncommitted", encoding="utf-8")
    before = local_branches(repo)
    service = make_service(tmp_path)

    with pytest.raises(AgentIntegrationError):
        service.request_agent_fix(repo, agent_command(tmp_path), 10.0, evidence(tmp_path))

    assert local_branches(repo) == before
    assert service.agent_proposals() == ()
    service.close()


def test_failing_agent_restores_branch_and_records_no_proposal(tmp_path) -> None:
    repo = make_repo(tmp_path)
    service = make_service(tmp_path)
    base_branch = current_branch(repo)

    with pytest.raises(AgentIntegrationError):
        service.request_agent_fix(repo, agent_command(tmp_path), 10.0, evidence(tmp_path, "fail"))

    assert current_branch(repo) == base_branch
    assert service.agent_proposals() == ()
    service.close()


def test_agent_proposing_no_change_is_refused(tmp_path) -> None:
    repo = make_repo(tmp_path)
    script = tmp_path / "noop.py"
    script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    service = make_service(tmp_path)

    with pytest.raises(AgentIntegrationError, match="did not propose"):
        service.request_agent_fix(
            repo, (sys.executable, str(script), "{evidence}"), 10.0, evidence(tmp_path)
        )
    service.close()


def test_new_files_belong_to_the_reviewed_snapshot(tmp_path) -> None:
    repo = make_repo(tmp_path)
    service = make_service(tmp_path)

    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence(tmp_path, "new")
    )

    assert "brand new" in review.diff
    assert "newfile.txt" in review.changed_files
    assert review.untracked_files == ()
    service.close()


def test_oversized_diffs_are_truncated(tmp_path) -> None:
    repo = make_repo(tmp_path)
    service = make_service(tmp_path)

    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence(tmp_path, "big")
    )

    assert review.truncated is True
    assert len(review.diff) <= 100_000
    service.close()


def test_apply_requires_an_explicitly_approved_change(tmp_path) -> None:
    repo = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(repo, agent_command(tmp_path), 10.0, evidence(tmp_path))

    with pytest.raises(WorkflowValidationError, match="approved"):
        service.apply_agent_change(review)  # type: ignore[arg-type]
    assert "fixed" not in (repo / "fixme.txt").read_text(encoding="utf-8")

    pass_pre_merge(service, review, tmp_path)
    approved = service.approve_agent_change(review)
    service.apply_agent_change(approved)

    text = (repo / "fixme.txt").read_text(encoding="utf-8")
    assert "original" in text and "fixed" in text
    assert current_branch(repo) == review.base_branch
    assert run_git(repo, "rev-parse", "HEAD") == review.agent_tip
    assert service.agent_proposals()[0].status == "APPROVED"
    service.close()


def test_approval_gate_rejects_unapproved_types_and_unknown_gates(tmp_path) -> None:
    with pytest.raises(WorkflowValidationError):
        approve_change(object())  # type: ignore[arg-type]
    with pytest.raises(WorkflowValidationError):
        ApprovedChange("id", object(), "now")  # type: ignore[arg-type]
    service = make_service(tmp_path)
    with pytest.raises(WorkflowValidationError, match="approved"):
        service.apply_agent_change("not-a-change")  # type: ignore[arg-type]
    service.close()


def test_approve_after_reject_is_refused(tmp_path) -> None:
    repo = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(repo, agent_command(tmp_path), 10.0, evidence(tmp_path))

    service.reject_agent_proposal(review)
    with pytest.raises(AgentIntegrationError, match="approved or rejected"):
        service.approve_agent_change(review)
    assert service.agent_proposals()[0].status == "REJECTED"
    service.close()


def test_apply_refuses_when_the_base_branch_has_moved(tmp_path) -> None:
    repo = make_repo(tmp_path)
    service = make_service(tmp_path)
    review = service.request_agent_fix(repo, agent_command(tmp_path), 10.0, evidence(tmp_path))
    pass_pre_merge(service, review, tmp_path)
    approved = service.approve_agent_change(review)
    (repo / "other.txt").write_text("moving on\n", encoding="utf-8")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "moved")

    with pytest.raises(AgentIntegrationError, match="moved"):
        service.apply_agent_change(approved)
    assert "fixed" not in (repo / "fixme.txt").read_text(encoding="utf-8")
    service.close()


def test_agent_fix_proposer_feeds_the_bounded_loop(tmp_path) -> None:
    repo = make_repo(tmp_path)
    service = make_service(tmp_path)
    proposer = AgentFixProposer(service, repo, agent_command(tmp_path), 10.0, tmp_path / "evidence")
    verify_count = 0

    def verify() -> EvidenceBundle:
        nonlocal verify_count
        verify_count += 1
        return EvidenceBundle(
            f"fail-{verify_count}",
            "2026-10-23T10:00:00+00:00",
            "2026-10-23T10:00:01+00:00",
            (
                CaseResult(
                    "case-1",
                    False,
                    (FieldResult("total", False, "mismatch", 100.0, 999.0),),
                    0,
                    False,
                    "",
                    "",
                ),
            ),
        )

    run = LoopController(verify, proposer, stopwatch=lambda: 0.0).run(
        LoopPolicy(max_attempts=5, max_wall_seconds=600.0)
    )

    assert run.status is LoopStatus.STOPPED_NO_PROGRESS
    assert verify_count == 2
    assert len(service.agent_proposals()) == 1
    agent_branches = {name for name in local_branches(repo) if name.startswith("once/agent/")}
    assert len(agent_branches) == 1
    service.close()


def test_unbounded_agent_commands_are_rejected(tmp_path) -> None:
    from integrations.coding_agent import AgentCommand

    with pytest.raises(AgentIntegrationError):
        AgentCommand((sys.executable, "-c", "print(1)"))
    with pytest.raises(AgentIntegrationError):
        AgentCommand((sys.executable, str(tmp_path / "a"), "{evidence}"), 601)


def test_git_calls_reuse_the_resolved_executable(monkeypatch, tmp_path) -> None:
    from integrations import coding_agent

    monkeypatch.setattr(coding_agent, "git_executable", lambda: "/resolved/git")
    argvs: list[tuple[str, ...]] = []

    class FakeCompleted:
        returncode = 0
        stderr = ""

    def fake_run(argv, **kwargs):
        argvs.append(tuple(argv))
        completed = FakeCompleted()
        completed.stdout = "" if "status" in argv else "abc123\n"
        return completed

    monkeypatch.setattr(coding_agent.subprocess, "run", fake_run)

    repository = coding_agent.GitRepository(tmp_path)
    assert repository.run_git("rev-parse", "HEAD") == "abc123"
    repository.create_agent_branch()

    assert argvs[0] == ("/resolved/git", "rev-parse", "HEAD")
    assert argvs[-1][0] == "/resolved/git"
    assert argvs[-1][1:3] == ("checkout", "-b")


def test_missing_git_fails_closed(monkeypatch, tmp_path) -> None:
    from integrations import coding_agent

    def no_git(name):
        return None

    monkeypatch.setattr(coding_agent.shutil, "which", no_git)

    with pytest.raises(AgentIntegrationError, match="Git was not found"):
        coding_agent.git_executable()
    with pytest.raises(AgentIntegrationError, match="Git was not found"):
        coding_agent.GitRepository(tmp_path)
    with pytest.raises(AgentIntegrationError, match="Git was not found"):
        coding_agent.WorktreeCheckout(tmp_path, tmp_path / "worktrees")
