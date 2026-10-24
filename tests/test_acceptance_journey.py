"""End-to-end acceptance test of the user journey at the controller level.

One test walks the real flow with real subprocesses and a real temporary Git
repository: configure the acceptance checker through the persisted
configuration path, save and reload a workflow, run it against controlled
inputs, verify against the buggy extractor, capture an agent proposal, inspect
the exact diff, verify it in an isolated worktree, approve and apply, verify
after the merge, then restart the service and recover everything. A second
test shows a failed agent run leaves the repository untouched and records
nothing. Graphical interactions (panels, dialogs, buttons) are covered
separately in tests/test_review_ui.py with real Qt widgets.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from controller.service import WorkflowService
from controller.verifier_config import load_verifier_config, save_verifier_config
from engine.errors import AgentIntegrationError, ExecutionError
from engine.verifier import AllowlistedCommand
from engine.workflow import StepKind, Workflow, WorkflowStatus, WorkflowStep

AGENT_SCRIPT = """
import pathlib, sys

behavior = pathlib.Path(sys.argv[1]).stem
if behavior == "crash":
    raise SystemExit(7)
if behavior == "rewrite-fail":
    pathlib.Path("extractor.py").write_text("import broken syntax", encoding="utf-8")
    raise SystemExit(7)
if behavior == "fix":
    extract = pathlib.Path("extractor.py")
    extract.write_text(
        "import json, sys\\n"
        "with open(sys.argv[1], encoding='utf-8') as handle:\\n"
        "    invoice = json.load(handle)\\n"
        "print(json.dumps({'invoice_number': invoice['invoice_number'],\\n"
        "    'total': {'INV-1': 105.0}.get(invoice['invoice_number'], -1.0)}))\\n",
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

CHECK_ARGV = (sys.executable, "{checkout}/extractor.py", "{input}")


def run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),  # noqa: S607 - test fixture uses managed git
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def controlled_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create the repo, the acceptance cases, and the evidence directory."""
    repo = tmp_path / "hotix"
    repo.mkdir()
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test")
    (repo / "extractor.py").write_text(BUGGY_EXTRACTOR, encoding="utf-8")
    (repo / "invoice.json").write_text(
        json.dumps({"invoice_number": "INV-1", "total": 100.0}), encoding="utf-8"
    )
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "v1")

    cases = [
        {
            "case_id": "inv-1",
            "input_file": str(repo / "invoice.json"),
            "expected": {
                "invoice_number": {"value": "INV-1", "mode": "exact", "required": True},
                "total": {
                    "value": 105.0,
                    "mode": "numeric_tolerance",
                    "tolerance": 0.01,
                    "required": True,
                },
            },
        }
    ]
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(cases), encoding="utf-8")

    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "fix.json").write_text(json.dumps({"task": "fix"}), encoding="utf-8")
    (evidence_dir / "crash.json").write_text(json.dumps({"task": "crash"}), encoding="utf-8")
    return repo, cases_path, evidence_dir


def agent_command(tmp_path: Path) -> tuple[str, ...]:
    script = tmp_path / "agent.py"
    script.write_text(AGENT_SCRIPT, encoding="utf-8")
    return (sys.executable, str(script), "{evidence}")


def test_acceptance_journey_configures_runs_proposes_approves_applies_and_recovers(
    tmp_path: Path,
) -> None:
    repo, cases_path, evidence_dir = controlled_inputs(tmp_path)
    app_data = tmp_path / "appdata"
    app_data.mkdir()
    worktree_root = tmp_path / "worktrees"
    worktree_root.mkdir()
    service = WorkflowService.for_app_data(app_data)

    # 1. Persistent checker configuration through the real save/load pair.
    save_verifier_config(
        app_data,
        cases_path=str(cases_path),
        argv=list(CHECK_ARGV),
        timeout_seconds=10.0,
        worktree_root=str(worktree_root),
    )
    reloaded_config = load_verifier_config(app_data)
    assert reloaded_config is not None
    assert reloaded_config.cases_path == cases_path
    assert reloaded_config.argv == CHECK_ARGV
    assert reloaded_config.worktree_root == worktree_root

    # 2. A workflow is saved through the storage boundary and reopened.
    workflow = Workflow(
        "inspect-invoices",
        "Inspect prepared invoices",
        (
            WorkflowStep(
                "check-input",
                "Check input",
                StepKind.INSPECT_PATH,
                "Input present",
                str(repo / "invoice.json"),
            ),
        ),
    )
    saved_path = service.save(workflow)
    assert service.list_saved() == (saved_path,)
    reopened = WorkflowService.load(saved_path)
    assert reopened.name == "Inspect prepared invoices"
    assert reopened.steps[0].kind is StepKind.INSPECT_PATH

    # 3. The workflow runs against the controlled input and is recorded.
    run = service.run_workflow(reopened, allowed_root=repo)
    assert run.status is WorkflowStatus.SUCCEEDED
    assert tuple(record.run_id for record in service.history()) == (run.run_id,)

    # 4. Verification with the configured command proves the bug is real.
    failing = service.verify_acceptance(
        reloaded_config.cases_path, reloaded_config.argv, 10.0, checkout=repo
    )
    assert failing.passed is False
    assert failing.cancelled is False

    # 5. The coding agent proposes a fix; the review shows the exact diff.
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_dir / "fix.json"
    )
    assert "{'INV-1': 105.0}" in review.diff
    assert "invoice['total']" in review.diff  # the changed line is the broken one
    records = service.agent_proposals()
    assert len(records) == 1 and records[0].status == "PENDING"

    # 6. Pre-merge verification runs in an isolated worktree at the recorded tip.
    bundle = service.verify_proposal_pre_merge(
        review,
        reloaded_config.cases_path,
        reloaded_config.argv,
        reloaded_config.timeout_seconds,
        reloaded_config.worktree_root,
    )
    assert bundle.passed is True and bundle.cancelled is False

    # 7. Explicit human approval, then a merge that only applies that commit.
    approved = service.approve_agent_change(review)
    applied = service.apply_agent_change(approved)
    assert applied
    assert "{'INV-1': 105.0}" in (repo / "extractor.py").read_text(encoding="utf-8")
    assert (repo / "invoice.json").read_text(encoding="utf-8").count('"total"') == 1

    # 8. Post-merge rerun of the exact acceptance cases passes.
    post = service.verify_post_merge(
        repo,
        reloaded_config.cases_path,
        reloaded_config.argv,
        10.0,
        review,
    )
    assert post.passed is True

    # 9. The application restarts; every decision survives with real content.
    restarted = WorkflowService.for_app_data(app_data)
    proposals = restarted.agent_proposals()
    assert len(proposals) == 1 and proposals[0].status == "APPROVED"
    assert proposals[0].review.diff == review.diff
    phases = {record.phase for record in restarted.proposal_verifications(review.proposal_id)}
    assert phases == {"PRE_MERGE", "POST_MERGE"}
    for record in restarted.proposal_verifications(review.proposal_id):
        stored = restarted.verification_run(record.verification_run_id)
        assert stored is not None and stored.run_id == record.verification_run_id
    with pytest.raises(AgentIntegrationError, match="already been approved"):
        restarted.reject_agent_proposal(review)
    restarted.close()
    service.close()


def test_failed_agent_run_records_nothing_and_cannot_corrupt_the_repository(
    tmp_path: Path,
) -> None:
    repo, _cases, evidence_dir = controlled_inputs(tmp_path)
    app_data = tmp_path / "appdata"
    app_data.mkdir()
    service = WorkflowService.for_app_data(app_data)
    original_head = run_git(repo, "rev-parse", "HEAD")
    original_branch = run_git(repo, "branch", "--show-current")

    with pytest.raises(AgentIntegrationError):
        service.request_agent_fix(repo, agent_command(tmp_path), 10.0, evidence_dir / "crash.json")

    assert service.agent_proposals() == ()
    assert run_git(repo, "rev-parse", "HEAD") == original_head
    assert run_git(repo, "branch", "--show-current") == original_branch
    assert (repo / "extractor.py").read_text(encoding="utf-8") == BUGGY_EXTRACTOR


def test_agent_that_writes_garbage_then_fails_leaves_only_a_parked_branch(
    tmp_path: Path,
) -> None:
    """A crashed agent's partial output is parked, never applied or deleted."""
    repo, _cases, evidence_dir = controlled_inputs(tmp_path)
    app_data = tmp_path / "appdata"
    app_data.mkdir()
    service = WorkflowService.for_app_data(app_data)
    original_branch = run_git(repo, "branch", "--show-current")
    script = tmp_path / "writer_then_failer.py"
    script.write_text(
        "import pathlib, sys\n"
        "pathlib.Path('extractor.py').write_text('import broken syntax\\n'"
        ", encoding='utf-8')\n"
        "raise SystemExit(9)\n",
        encoding="utf-8",
    )

    with pytest.raises(AgentIntegrationError):
        service.request_agent_fix(
            repo,
            (sys.executable, str(script), "{evidence}"),
            10.0,
            evidence_dir / "crash.json",
        )

    # the user's checkout carries none of the broken content
    assert run_git(repo, "branch", "--show-current") == original_branch
    assert "broken syntax" not in (repo / "extractor.py").read_text(encoding="utf-8")
    assert service.agent_proposals() == ()
    # the partial output survives on the disposable agent branch for inspection
    assert run_git(repo, "branch", "--list", "once/agent/*").split(), (
        "the partial output was destroyed instead of parked"
    )


def test_stale_agent_tip_cannot_be_verified_after_a_commit_amendment(tmp_path: Path) -> None:
    """Identity is fundamental: an amended agent branch is a different proposal."""
    repo, cases_path, evidence_dir = controlled_inputs(tmp_path)
    app_data = tmp_path / "appdata"
    app_data.mkdir()
    service = WorkflowService.for_app_data(app_data)
    review = service.request_agent_fix(
        repo, agent_command(tmp_path), 10.0, evidence_dir / "fix.json"
    )
    original_branch = run_git(repo, "branch", "--show-current")
    run_git(repo, "checkout", review.agent_branch)
    run_git(repo, "commit", "--amend", "-q", "-m", "amended")
    run_git(repo, "checkout", original_branch)

    with pytest.raises(AgentIntegrationError, match="tip"):
        service.verify_proposal_pre_merge(
            review, cases_path, CHECK_ARGV, 10.0, tmp_path / "worktrees"
        )
    assert service.agent_proposals()[0].status == "PENDING"
    service.close()


def test_acceptance_command_allowlist_rejects_unbounded_shapes() -> None:
    """The checker's argv is structural: empty parts, wrong placeholders, bad timeouts.

    Characters are not banned one by one: the guarantee is that the command
    runs as an exact argv through subprocess without any shell, so metacha-
    racters stay inert data.
    """
    bad_argv = (
        (sys.executable, "", "{input}"),  # empty argument
        (sys.executable),  # no {input} at all
        (sys.executable, "{input}", "{input}"),  # two {input} placeholders
        (sys.executable, "{checkout}/a.py", "{checkout}/b.py", "{input}"),
    )
    for argv in bad_argv:
        with pytest.raises(ExecutionError):
            AllowlistedCommand(argv)
    with pytest.raises(ExecutionError):
        AllowlistedCommand((sys.executable, "{input}"), 301.0)  # over the bound
    # inert-looking metacharacters are allowed BECAUSE no shell is invoked
    AllowlistedCommand((sys.executable, "a;rm -rf /", "{input}"))
