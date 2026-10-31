"""Read-only canvas scene (P3): draws a LayoutPlan exactly.

No editing, no zoom, no keyboard model yet — those land with the editor
page (P4/P5). Everything here renders the plan that the pure layout
module computed; golden tests pin the item positions.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
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
from ui.styles import ACCENT_TEXT, BORDER, BORDER_STRONG, SURFACE

MARGIN = 40.0
_ARROW_LEN = 9.0
_ARROW_HALF = 5.0


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
        self.setPen(QPen(QColor(BORDER), 1.0))
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
    """Static rendering of a workflow chain: nodes, connectors, arrowheads."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.nodes: dict[str, NodeCard] = {}
        self.edge_items: list[tuple[QGraphicsPathItem, QGraphicsPolygonItem]] = []

    def set_workflow(self, workflow: Workflow | None) -> None:
        """Build the plan from a workflow and render it (read-only)."""
        self.nodes.clear()
        self.edge_items.clear()
        self._scene.clear()
        if workflow is None:
            return
        self.set_model(auto_layout(workflow), self._titles(workflow))

    @staticmethod
    def _titles(workflow: Workflow) -> dict[str, tuple[str, str]]:
        titles: dict[str, tuple[str, str]] = {
            START_ID: ("Start", ""),
            FINISH_ID: ("Finish", ""),
        }
        for step in workflow.steps:
            titles[step.step_id] = (step.name, step.kind.value)
        return titles

    def set_model(self, plan: LayoutPlan, titles: dict[str, tuple[str, str]]) -> None:
        """Render a precomputed plan; every position comes from the plan."""
        self.nodes.clear()
        self.edge_items.clear()
        self._scene.clear()
        bounds = QRectF()
        for slot_id, slot in plan.slots.items():
            title, subtitle = titles.get(slot_id, (slot_id, ""))
            card = NodeCard(slot, title, subtitle)
            self._scene.addItem(card)
            self.nodes[slot_id] = card
            bounds = bounds.united(QRectF(slot.x, slot.y, slot.w, slot.h))

        pen = QPen(QColor(BORDER_STRONG), 1.0)
        for edge in plan.edges:
            if not edge.points:
                continue
            path = QPainterPath(QPointF(edge.points[0][0], edge.points[0][1]))
            for x, y in edge.points[1:]:
                path.lineTo(QPointF(x, y))
            edge_item = QGraphicsPathItem(path)
            edge_item.setPen(pen)
            self._scene.addItem(edge_item)

            arrow_end = edge.points[-1]
            arrow = QGraphicsPolygonItem(_arrow_polygon())
            arrow.setPen(pen)
            arrow.setBrush(QBrush(QColor(BORDER_STRONG)))
            arrow.setPos(arrow_end[0], arrow_end[1])
            self._scene.addItem(arrow)
            self.edge_items.append((edge_item, arrow))
            bounds = bounds.united(
                QRectF(
                    arrow_end[0] - _ARROW_LEN,
                    arrow_end[1] - _ARROW_HALF,
                    _ARROW_LEN + 2.0,
                    2.0 * _ARROW_HALF,
                )
            )

        self._scene.setSceneRect(bounds.adjusted(-MARGIN, -MARGIN, MARGIN, MARGIN))
