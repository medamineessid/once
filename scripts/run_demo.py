"""Reproducible demonstration of the full supervised test-and-fix journey.

Everything happens inside one throwaway directory the user can name: no cloud
calls, no real user data. The demonstration project is a miniature "invoice
extractor" with a known ground truth, a seeded reproducible defect, a
deterministic rule-based fix generator standing in for a coding agent, and the
real hardened controller pipeline (allowlisted verifier, worktree
verification, explicit approval, bounded apply, persisted history).

Run it:  python scripts/run_demo.py
Cancel-safe: approval is demanded from the person running the script; typing
anything except "approve" cancels before any change is applied.

This is a demonstration, not a test: the same flow is asserted by
tests/test_acceptance_journey.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import mkdtemp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.service import WorkflowService
from controller.verifier_config import save_verifier_config

BUGGY_EXTRACTOR = (
    "import json, sys\n"
    "with open(sys.argv[1], encoding='utf-8') as handle:\n"
    "    invoice = json.load(handle)\n"
    "print(json.dumps({'invoice_number': invoice['invoice_number'],\n"
    "    'total': invoice['total']}))\n"
)

FIX_GENERATOR = """import json, sys
# Deterministic rule-based fix generator: reads the ground truth the human
# recorded for the acceptance cases and writes an extractor that applies it.
rules = json.load(open(sys.argv[1], encoding="utf-8"))["totals"]
lines = [
    "import json, sys",
    "with open(sys.argv[1], encoding='utf-8') as handle:",
    "    invoice = json.load(handle)",
    "print(json.dumps({'invoice_number': invoice['invoice_number'],",
    "    'total': " + repr(rules) + ".get(invoice['invoice_number'], -1.0)}))",
]
handle = open("extractor.py", "w", encoding="utf-8")
handle.write(chr(10).join(lines) + chr(10))
handle.close()
print("wrote corrected extractor with ground truth", rules)
"""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603 - demo managed git, exact argv
        ("git", *args),  # noqa: S607 - demo uses managed git
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def step(number: int, text: str) -> None:
    print(f"\n=== {number}. {text}")


def main() -> int:
    workspace = Path(mkdtemp(prefix="once-demo-"))
    app_data = workspace / "appdata"
    app_data.mkdir()
    repo = workspace / "hotix-demo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "demo@example.com")
    _git(repo, "config", "user.name", "Demo")

    step(1, "prepare a controlled test repository")
    (repo / "invoice.json").write_text(
        json.dumps({"invoice_number": "INV-1", "total": 100.0}), encoding="utf-8"
    )
    (repo / "ground_truth.json").write_text(
        json.dumps({"totals": {"INV-1": 105.0}}), encoding="utf-8"
    )
    (repo / "extractor.py").write_text(BUGGY_EXTRACTOR, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed: extractor with a known defect")

    cases_path = workspace / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "INV-1",
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
        ),
        encoding="utf-8",
    )
    evidence_dir = workspace / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "fix.json").write_text(
        json.dumps({"task": "align extraction with the recorded ground truth"}),
        encoding="utf-8",
    )
    print(f"workspace: {workspace}")
    print("ground truth (human-recorded): INV-1 total = 105.0")

    generator_path = workspace / "fix_generator.py"
    generator_path.write_text(FIX_GENERATOR, encoding="utf-8")

    service = WorkflowService.for_app_data(app_data)

    step(2, "configure the allowlisted verifier")
    worktree_root = workspace / "worktrees"
    worktree_root.mkdir()
    save_verifier_config(
        app_data,
        cases_path=str(cases_path),
        argv=[sys.executable, "{checkout}/extractor.py", "{input}"],
        timeout_seconds=10.0,
        worktree_root=str(worktree_root),
    )
    print("verifier.json written to", app_data / "verifier.json")

    step(3, "run verification against the known ground truth")
    failing = service.verify_acceptance(
        cases_path, (sys.executable, str(repo / "extractor.py"), "{input}"), 10.0
    )
    print(f"verification passed: {failing.passed} (expected False: the seeded defect)")
    for case in failing.cases:
        for field in case.fields:
            print(
                f"  case {case.case_id} field {field.field}: "
                f"expected {field.expected!r} got {field.actual!r} -> {field.passed}"
            )

    step(4, "request a proposal from the deterministic fix generator")
    review = service.request_agent_fix(
        repo,
        (sys.executable, str(generator_path), str(repo / "ground_truth.json"), "{evidence}"),
        10.0,
        evidence_dir / "fix.json",
    )
    print("proposal branch:", review.agent_branch)
    print("---- exact proposed diff ----")
    print(review.diff)
    print("----------------------------")

    step(5, "verify the proposal in an isolated worktree")
    bundle = service.verify_proposal_pre_merge(
        review,
        cases_path,
        (sys.executable, "{checkout}/extractor.py", "{input}"),
        10.0,
        worktree_root,
    )
    print(f"isolated verification passed: {bundle.passed}")
    blockers = service.approval_blockers(review)
    print("approval blockers:", blockers or "none - approval is possible")

    step(6, "explicit human approval (this pauses for you)")
    print("Type 'approve' to apply the proposal, anything else to cancel: ", end="", flush=True)
    answer = input().strip().lower()
    if answer != "approve":
        service.close()
        print("\nCANCELLED: nothing was applied. The proposal stays recorded for review.")
        return 0
    approved = service.approve_agent_change(review)
    service.apply_agent_change(approved)
    print("applied; extractor now contains the corrected totals mapping")

    step(7, "rerun verification after the merge")
    post = service.verify_post_merge(
        repo,
        cases_path,
        (sys.executable, "{checkout}/extractor.py", "{input}"),
        10.0,
        review,
    )
    print(f"post-merge verification passed: {post.passed}")
    for case in post.cases:
        fields = ", ".join(f"{f.field}={f.actual!r}" for f in case.fields)
        print(f"  case {case.case_id}: exit={case.exit_code} {fields}")

    step(8, "restart the service: history must survive")
    service.close()
    reopened = WorkflowService.for_app_data(app_data)
    for record in reopened.agent_proposals():
        print(f"proposal {record.review.proposal_id[:8]} status: {record.status}")
    for record in reopened.proposal_verifications(review.proposal_id):
        print(f"verification phase {record.phase}: passed={record.passed}")
    for run in reopened.acceptance_history():
        print(f"verification run {run.run_id[:8]}: passed={run.passed}")
    reopened.close()

    print(f"\nDemonstration complete. Workspace kept at {workspace} for inspection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
