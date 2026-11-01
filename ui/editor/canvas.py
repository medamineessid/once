"""Canvas scene: draws a LayoutPlan exactly, with click/keyboard selection.

Selection (A2a) follows docs/specs/visual_workflow_editor.md section 4:
clicking a node selects it (accent outline, both adjacent edges
highlighted); an empty click or Esc deselects; Tab and the arrow keys
walk along the chain edges, Enter activates. The canvas never re-centres
when the user selects by mouse; keyboard moves only scroll when the node
is not on screen.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QKeyEvent, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QWidget,
)

from engine.workflow import Workflow
from ui.editor.layout import (
    FINISH_ID,
    START_ID,
    LayoutPlan,
    NodeSlot,
    auto_layout,
)
from ui.styles import ACCENT, ACCENT_TEXT, BORDER, BORDER_STRONG, SURFACE

MARGIN = 40.0
_ARROW_LEN = 9.0
_ARROW_HALF = 5.0
_SELECTION_PEN_WIDTH = 2.0
_NORMAL_PEN_WIDTH = 1.0


def _arrow_polygon() -> QPolygonF:
    """Right-pointing arrowhead anchored at the (0, 0) entry port."""
    return QPolygonF(
        [
            QPointF(0.0, 0.0),
            QPointF(-_ARROW_LEN, -_ARROW_HALF),
            QPointF(-_ARROW_LEN, _ARROW_HALF),
        ]
    )


class NodeCard(QGraphicsPathItem):
    """One rounded card with a child title and subtitle."""

    def __init__(self, slot: NodeSlot, title: str, subtitle: str) -> None:
        super().__init__()
        self.slot = slot
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.0, 0.0, slot.w, slot.h), 10.0, 10.0)
        self.setPos(slot.x, slot.y)
        self.setPen(QPen(QColor(BORDER), _NORMAL_PEN_WIDTH))
        self.setBrush(QBrush(QColor(SURFACE)))
        self.setPath(path)

        title_item = QGraphicsTextItem(self)
        title_item.setDefaultTextColor(QColor(BORDER_STRONG))
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_item.setFont(title_font)
        title_item.setPlainText(title)
        title_item.setPos(12.0, 10.0)

        subtitle_item = QGraphicsTextItem(self)
        subtitle_item.setDefaultTextColor(QColor(ACCENT_TEXT))
        subtitle_font = QFont()
        subtitle_font.setPointSize(8)
        subtitle_item.setFont(subtitle_font)
        subtitle_item.setPlainText(subtitle)
        subtitle_item.setPos(12.0, slot.h - 26.0)


class CanvasView(QGraphicsView):
    """Workflow chain renderer with node selection (mouse and keyboard)."""

    #: Emitted when the selected node changes: the step id, or None.
    node_selected = Signal(object)
    #: Emitted on Enter over a selected node (keyboard activation).
    step_activated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.nodes: dict[str, NodeCard] = {}
        self.edge_items: list[tuple[QGraphicsPathItem, QGraphicsPolygonItem]] = []
        self.edge_lookup: dict[tuple[str, str], tuple[QGraphicsPathItem, QGraphicsPolygonItem]] = {}
        self.chain: tuple[str, ...] = ()
        self._selected_id: str | None = None

    @property
    def selected_id(self) -> str | None:
        """The currently selected member id (Start/Finish included), or None."""
        return self._selected_id

    def set_workflow(self, workflow: Workflow | None) -> None:
        """Build the plan from a workflow and render it."""
        self.nodes.clear()
        self.edge_items.clear()
        self.edge_lookup.clear()
        self._scene.clear()
        if workflow is None:
            self.chain = ()
            self._selected_id = None
            return
        self.set_model(auto_layout(workflow), self._titles(workflow))

    def set_model(self, plan: LayoutPlan, titles: dict[str, tuple[str, str]]) -> None:
        """Render a precomputed plan; every position comes from the plan."""
        previous = self._selected_id
        self.nodes.clear()
        self.edge_items.clear()
        self.edge_lookup.clear()
        self._scene.clear()
        bounds = QRectF()
        for slot_id, slot in plan.slots.items():
            title, subtitle = titles.get(slot_id, (slot_id, ""))
            card = NodeCard(slot, title, subtitle)
            self._scene.addItem(card)
            self.nodes[slot_id] = card
            bounds = bounds.united(QRectF(slot.x, slot.y, slot.w, slot.h))

        self.chain = tuple(plan.slots)  # plan order: Start, steps, Finish

        for edge in plan.edges:
            if not edge.points:
                continue
            path = QPainterPath(QPointF(edge.points[0][0], edge.points[0][1]))
            for x, y in edge.points[1:]:
                path.lineTo(QPointF(x, y))
            edge_item = QGraphicsPathItem(path)
            edge_item.setPen(QPen(QColor(BORDER_STRONG), _NORMAL_PEN_WIDTH))
            self._scene.addItem(edge_item)

            arrow_end = edge.points[-1]
            arrow = QGraphicsPolygonItem(_arrow_polygon())
            arrow.setPen(QPen(QColor(BORDER_STRONG), _NORMAL_PEN_WIDTH))
            arrow.setBrush(QBrush(QColor(BORDER_STRONG)))
            arrow.setPos(arrow_end[0], arrow_end[1])
            self._scene.addItem(arrow)
            self.edge_items.append((edge_item, arrow))
            self.edge_lookup[(edge.from_id, edge.to_id)] = (edge_item, arrow)
            bounds = bounds.united(
                QRectF(
                    arrow_end[0] - _ARROW_LEN,
                    arrow_end[1] - _ARROW_HALF,
                    _ARROW_LEN + 2.0,
                    2.0 * _ARROW_HALF,
                )
            )

        self._scene.setSceneRect(bounds.adjusted(-MARGIN, -MARGIN, MARGIN, MARGIN))
        # Selection survives a rebuild (any edit) when the member still exists.
        self._selected_id = previous if previous in self.nodes else None
        self._apply_selection_visuals()

    @staticmethod
    def _titles(workflow: Workflow) -> dict[str, tuple[str, str]]:
        titles: dict[str, tuple[str, str]] = {
            START_ID: ("Start", ""),
            FINISH_ID: ("Finish", ""),
        }
        for step in workflow.steps:
            titles[step.step_id] = (step.name, step.kind.value)
        return titles

    # --------------------------------------------------------------- selection

    def select_node(self, node_id: str | None) -> None:
        """Select one member by id; None clears. Selecting the already
        selected member again clears the selection instead."""
        if node_id is not None and node_id not in self.nodes:
            node_id = None
        if node_id == self._selected_id:
            if node_id is None:
                return  # empty click with nothing selected: no-op
            node_id = None  # second click on the selected node deselects
        self._selected_id = node_id
        self._apply_selection_visuals()
        self.node_selected.emit(node_id)

    def _apply_selection_visuals(self) -> None:
        """Restyle the selected card plus its incoming and outgoing edges."""
        for member_id, card in self.nodes.items():
            selected = member_id == self._selected_id
            card.setPen(
                QPen(
                    QColor(ACCENT if selected else BORDER),
                    _SELECTION_PEN_WIDTH if selected else _NORMAL_PEN_WIDTH,
                )
            )
        for (from_id, to_id), (edge_item, arrow) in self.edge_lookup.items():
            highlighted = self._selected_id is not None and self._selected_id in (from_id, to_id)
            color = ACCENT if highlighted else BORDER_STRONG
            width = _SELECTION_PEN_WIDTH if highlighted else _NORMAL_PEN_WIDTH
            edge_item.setPen(QPen(QColor(color), width))
            arrow.setPen(QPen(QColor(color), width))
            arrow.setBrush(QBrush(QColor(color)))

    def _node_at_scene_position(self, position: QPointF) -> str | None:
        """A member whose planned rectangle contains the scene point."""
        for member_id, card in self.nodes.items():
            slot = card.slot
            if (
                slot.x <= position.x() <= slot.x + slot.w
                and slot.y <= position.y() <= slot.y + slot.h
            ):
                return member_id
        return None

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt name
        if event.button() == Qt.MouseButton.LeftButton:
            scene_position = self.mapToScene(event.position().toPoint())
            target = self._node_at_scene_position(scene_position)
            clicked_selection = target == self._selected_id
            self.select_node(None if clicked_selection else target)
            event.accept()
            return
        super().mousePressEvent(event)

    def _toggle_or_step(self, key: Qt.Key, backwards: bool) -> None:
        """Walk the chain one member along the edges from the selection."""
        if not self.chain:
            return
        if self._selected_id is None:
            self.select_node(self.chain[0] if not backwards else self.chain[-1])
            self._ensure_visible(self._selected_id)
            return
        index = self.chain.index(self._selected_id)
        target_index = index - 1 if backwards else index + 1
        if not 0 <= target_index < len(self.chain):
            return  # already at the chain end; no wrap
        self.select_node(self.chain[target_index])
        self._ensure_visible(self._selected_id)

    def _ensure_visible(self, member_id: str | None) -> None:
        card = self.nodes.get(member_id) if member_id is not None else None
        if card is not None:
            self.ensureVisible(card, 50, 50)

    def focusNextPrevChild(self, next: bool) -> bool:  # noqa: N802 - Qt name
        """Tab moves forward along the chain; Shift+Tab moves back. Qt never
        runs keyPressEvent for Tab, so focus processing is the hook."""
        if self.chain:
            self._toggle_or_step(None, not next)
            return True
        return super().focusNextPrevChild(next)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt name
        key = event.key()
        if key == Qt.Key_Escape:
            self.select_node(None)
            event.accept()
            return
        if key == Qt.Key_Right:
            self._toggle_or_step(key, False)
            event.accept()
            return
        if key == Qt.Key_Left:
            self._toggle_or_step(key, True)
            event.accept()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self._selected_id is not None:
                self.step_activated.emit(self._selected_id)
            event.accept()
            return
        super().keyPressEvent(event)
