"""Pure auto-layout for the workflow canvas (no Qt imports — design 2.3).

Geometry: rows read left-to-right; after ROW_LIMIT step cards the next
member starts a new row brought back to the canvas left edge, and the
row transition is an explicit wrap connector from the row-end card's
bottom port, 20 px down into the wrap channel, horizontally across, then
down into the next row's first card's left port. Terminals (Start /
Finish) participate as chain members but do not count towards the row
limit; all members align on their top edge.

Saved positions override the grid per node (the node keeps its spot);
a grid slot colliding with any placed member is nudged down by V_GAP in
chain order, deterministically.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from engine.errors import WorkflowValidationError
from engine.workflow import Workflow

CARD_W = 232.0
CARD_H = 88.0
H_GAP = 56.0
V_GAP = 96.0
TERMINAL_W = 88.0
TERMINAL_H = 44.0
ROW_LIMIT = 6
WRAP_DROP = 20.0

START_ID = "__start__"
FINISH_ID = "__finish__"

Member = tuple[str, str, float, float]


@dataclass(frozen=True)
class NodeSlot:
    """Where one member is drawn (float coordinates, top-left origin)."""

    step_id: str
    x: float
    y: float
    w: float
    h: float

    @property
    def left_port(self) -> tuple[float, float]:
        return (self.x, self.y + self.h / 2)

    @property
    def right_port(self) -> tuple[float, float]:
        return (self.x + self.w, self.y + self.h / 2)

    @property
    def bottom_port(self) -> tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h)


@dataclass(frozen=True)
class LayoutEdge:
    """One connector as an exact polyline; the arrowhead ends at the last point."""

    from_id: str
    to_id: str
    points: tuple[tuple[float, float], ...]
    wrap: bool


@dataclass(frozen=True)
class LayoutPlan:
    """Everything the canvas needs to draw, with exact float coordinates."""

    slots: dict[str, NodeSlot]
    edges: tuple[LayoutEdge, ...]
    wrap_edges: frozenset[str]


def _chain_members(workflow: Workflow) -> tuple[Member, ...]:
    """(id, subtitle, width, height) members in chain order."""
    members: list[Member] = [(START_ID, "Start", TERMINAL_W, TERMINAL_H)]
    for step in workflow.steps:
        members.append((step.step_id, step.kind.value, CARD_W, CARD_H))
    members.append((FINISH_ID, "Finish", TERMINAL_W, TERMINAL_H))
    return tuple(members)


def _coerce_xy(entry: object) -> tuple[float, float]:
    """Saved record value -> (x, y): accepts {"x","y"} or a 2-item sequence."""
    if isinstance(entry, Mapping):
        if "x" not in entry or "y" not in entry:
            raise WorkflowValidationError("saved position needs 'x' and 'y'")
        return (float(entry["x"]), float(entry["y"]))
    if isinstance(entry, Sequence) and not isinstance(entry, str):
        if len(entry) != 2:
            raise WorkflowValidationError("saved position needs two coordinates")
        return (float(entry[0]), float(entry[1]))
    raise WorkflowValidationError("saved position must be a mapping or a pair")


def _overlaps(box: tuple[float, float, float, float], other: NodeSlot) -> bool:
    x, y, w, h = box
    return x < other.x + other.w and other.x < x + w and y < other.y + other.h and other.y < y + h


def _grid_slots(members: tuple[Member, ...]) -> dict[str, NodeSlot]:
    """Chain-index grid positions, independent of any saved overrides."""
    n = len(members)
    slots: dict[str, NodeSlot] = {}
    x = 0.0
    y = 0.0
    steps_in_row = 0
    for index, (member_id, _subtitle, width, height) in enumerate(members):
        if index not in (0, n - 1) and steps_in_row >= ROW_LIMIT:
            x = 0.0
            y += CARD_H + V_GAP
            steps_in_row = 0
        slots[member_id] = NodeSlot(member_id, x, y, width, height)
        x += width + H_GAP
        if index not in (0, n - 1):
            steps_in_row += 1
    return slots


def auto_layout(
    workflow: Workflow,
    saved_positions: Mapping[str, Mapping[str, float] | Sequence[float]] | None = None,
) -> LayoutPlan:
    """Chain-order grid layout with per-node saved overrides."""
    members = _chain_members(workflow)
    grid = _grid_slots(members)

    saved = {sid: _coerce_xy(entry) for sid, entry in (saved_positions or {}).items()}
    placed: dict[str, NodeSlot] = {}
    # Saved positions own their coordinates first, so a colliding grid slot
    # can be nudged away from them (design: the grid slot moves, never the
    # saved node).
    for member_id, _subtitle, width, height in members:
        if member_id in saved:
            saved_x, saved_y = saved[member_id]
            placed[member_id] = NodeSlot(member_id, saved_x, saved_y, width, height)
    for member_id, _subtitle, _width, _height in members:
        if member_id in placed:
            continue
        slot = grid[member_id]
        while any(_overlaps((slot.x, slot.y, slot.w, slot.h), other) for other in placed.values()):
            slot = NodeSlot(member_id, slot.x, slot.y + V_GAP, slot.w, slot.h)
        placed[member_id] = slot

    edges: list[LayoutEdge] = []
    wrap_edges: set[str] = set()
    for before, after in itertools.pairwise(members):
        prev_slot = placed[before[0]]
        next_slot = placed[after[0]]
        grid_prev = grid[before[0]]
        grid_next = grid[after[0]]
        is_wrap = grid_prev.y != grid_next.y or grid_next.x != grid_prev.x + grid_prev.w + H_GAP
        if is_wrap:
            start = prev_slot.bottom_port
            channel_y = start[1] + WRAP_DROP
            end = next_slot.left_port
            points = (
                start,
                (start[0], channel_y),
                (end[0], channel_y),
                end,
            )
            wrap_edges.add(before[0])
        else:
            points = (prev_slot.right_port, next_slot.left_port)
        edges.append(LayoutEdge(from_id=before[0], to_id=after[0], points=points, wrap=is_wrap))

    return LayoutPlan(slots=dict(placed), edges=tuple(edges), wrap_edges=frozenset(wrap_edges))
