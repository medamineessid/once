"""Tests for the bounded diagnose-fix-test loop controller."""

from __future__ import annotations

import json
import sys
from time import monotonic

import pytest

from controller.service import WorkflowService
from engine.errors import ExecutionError, WorkflowValidationError
from engine.loop import DecisionCode, LoopController, LoopPolicy, LoopStatus
from engine.verifier import CaseResult, EvidenceBundle, FieldResult
from storage.database import connect
from storage.history import ExecutionHistory


def failing_bundle(run_id: str, case_id: str = "case-1") -> EvidenceBundle:
    return EvidenceBundle(
        run_id,
        "2026-10-23T10:00:00+00:00",
        "2026-10-23T10:00:01+00:00",
        (
            CaseResult(
                case_id,
                False,
                (FieldResult("total", False, "mismatch", 100.0, 999.0),),
                0,
                False,
                "stdout tail",
                "stderr tail",
            ),
        ),
    )


def passing_bundle() -> EvidenceBundle:
    return EvidenceBundle(
        "run-ok",
        "2026-10-23T10:00:00+00:00",
        "2026-10-23T10:00:01+00:00",
        (
            CaseResult(
                "case-1",
                True,
                (FieldResult("total", True, "matched", 100.0, 100.0),),
                0,
                False,
                "",
                "",
            ),
        ),
    )


class RecordingProposer:
    """A deterministic proposer that records the evidence it was shown."""

    def __init__(self) -> None:
        self.evidence: list[EvidenceBundle] = []

    def propose(self, evidence: EvidenceBundle) -> None:
        self.evidence.append(evidence)


def test_loop_completes_when_verification_passes() -> None:
    calls: list[int] = []

    def verify() -> EvidenceBundle:
        calls.append(1)
        return passing_bundle()

    run = LoopController(verify, stopwatch=lambda: 0.0).run()

    assert run.status is LoopStatus.COMPLETED
    assert len(calls) == 1
    assert [decision.code for decision in run.decisions] == [DecisionCode.VERIFIED_PASS]
    assert run.decisions[0].evidence_run_id == "run-ok"


def test_loop_stops_on_no_progress_without_third_verification() -> None:
    verify_count = 0
    proposer = RecordingProposer()

    def verify() -> EvidenceBundle:
        nonlocal verify_count
        verify_count += 1
        return failing_bundle(f"fail-{verify_count}")

    run = LoopController(verify, proposer, stopwatch=lambda: 0.0).run(
        LoopPolicy(max_attempts=5, max_wall_seconds=3600.0)
    )

    assert run.status is LoopStatus.STOPPED_NO_PROGRESS
    assert verify_count == 2
    assert len(proposer.evidence) == 1
    codes = [decision.code for decision in run.decisions]
    assert codes == [
        DecisionCode.VERIFIED_FAIL,
        DecisionCode.PROPOSER_NOTIFIED,
        DecisionCode.VERIFIED_FAIL,
        DecisionCode.STOP_NO_PROGRESS,
    ]


def test_loop_stops_at_attempt_limit() -> None:
    verify_count = 0

    def verify() -> EvidenceBundle:
        nonlocal verify_count
        verify_count += 1
        if verify_count == 1:
            return failing_bundle("fail-1")
        if verify_count == 2:
            return failing_bundle("fail-2", "case-2")
        return passing_bundle()

    run = LoopController(verify, RecordingProposer(), stopwatch=lambda: 0.0).run(
        LoopPolicy(max_attempts=2, max_wall_seconds=3600.0)
    )

    assert run.status is LoopStatus.STOPPED_MAX_ATTEMPTS
    assert [decision.code for decision in run.decisions][-1] is DecisionCode.STOP_MAX_ATTEMPTS


def test_loop_stops_when_wall_time_budget_is_exhausted() -> None:
    started = monotonic()
    clock_values = iter([started, started + 3601.0])

    def verify() -> EvidenceBundle:
        return failing_bundle("fail-1")

    run = LoopController(verify, RecordingProposer(), stopwatch=lambda: next(clock_values)).run(
        LoopPolicy(max_attempts=5, max_wall_seconds=3600.0)
    )

    assert run.status is LoopStatus.STOPPED_WALL_TIME
    assert run.decisions[-1].code is DecisionCode.STOP_WALL_TIME


def test_loop_stops_without_a_configured_proposer() -> None:
    verify_count = 0

    def verify() -> EvidenceBundle:
        nonlocal verify_count
        verify_count += 1
        return failing_bundle(f"fail-{verify_count}")

    run = LoopController(verify, None, stopwatch=lambda: 0.0).run(
        LoopPolicy(max_attempts=5, max_wall_seconds=3600.0)
    )

    assert run.status is LoopStatus.STOPPED_NO_PROPOSER
    assert verify_count == 1
    assert run.decisions[-1].code is DecisionCode.STOP_NO_PROPOSER


def test_loop_policy_rejects_unbounded_or_zero_limits() -> None:
    with pytest.raises(WorkflowValidationError):
        LoopPolicy(max_attempts=0, max_wall_seconds=10.0)
    with pytest.raises(WorkflowValidationError):
        LoopPolicy(max_attempts=5, max_wall_seconds=0.0)
    with pytest.raises(WorkflowValidationError):
        LoopPolicy(max_attempts=51, max_wall_seconds=10.0)
    with pytest.raises(WorkflowValidationError):
        LoopPolicy(max_attempts=5, max_wall_seconds=3601.0)


def test_loop_run_ids_are_unique() -> None:
    def verify() -> EvidenceBundle:
        return passing_bundle()

    first = LoopController(verify, stopwatch=lambda: 0.0).run()
    second = LoopController(verify, stopwatch=lambda: 0.0).run()

    assert first.loop_id != second.loop_id


def test_service_runs_and_persists_supervised_loop(tmp_path) -> None:
    script = tmp_path / "extractor.py"
    script.write_text('import json,sys\nprint(json.dumps({"total": 999.0}))\n', encoding="utf-8")
    input_file = tmp_path / "invoice.txt"
    input_file.write_text("data", encoding="utf-8")
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "one",
                    "input_file": str(input_file),
                    "expected": {
                        "total": {
                            "value": 100.0,
                            "mode": "numeric_tolerance",
                            "tolerance": 0.1,
                            "required": True,
                        }
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    service = WorkflowService(history=ExecutionHistory(connect(tmp_path / "history.db")))
    proposer = RecordingProposer()

    run = service.run_supervised_loop(
        cases_path,
        (sys.executable, str(script), "{input}"),
        5.0,
        LoopPolicy(max_attempts=3, max_wall_seconds=60.0),
        proposer,
    )

    assert run.status is LoopStatus.STOPPED_NO_PROGRESS
    assert len(service.loop_history()) == 1
    persisted = service.loop_history()[0]
    assert persisted.status is LoopStatus.STOPPED_NO_PROGRESS
    assert persisted.decisions[0].evidence_run_id is not None
    assert service.acceptance_history()  # verification runs persisted too
    service.close()


def test_service_rejects_loop_without_allowlisted_command(tmp_path) -> None:
    cases_path = tmp_path / "cases.json"
    cases_path.write_text("[]", encoding="utf-8")
    service = WorkflowService()

    with pytest.raises(ExecutionError):
        service.run_supervised_loop(
            cases_path,
            (sys.executable, "-c", "print(1)"),
            5.0,
            LoopPolicy(max_attempts=1, max_wall_seconds=10.0),
        )
    service.close()
