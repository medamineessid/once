# Once Desktop Design System (`DESIGN.md`)

Once is a local-first Windows desktop application built with Python and **PySide6 (Qt Widgets)**. Because Once runs natively on Windows without a web browser or Electron runtime, web-only libraries (such as GSAP, Tailwind, or CSS `box-shadow`/`transition`) are not used. Instead, Once implements a Linear/Raycast-inspired light-first desktop aesthetic using Qt Widgets, `QGraphicsScene`, and validated Qt Style Sheets (`ui/styles/__init__.py`).

---

## 1. Aesthetic Direction & Core Principles

1. **Crisp Light-First Surface Hierarchy**:
   - **Window Canvas (`SURFACE_ALT` `#F6F8FA`)**: Cool alabaster background that reduces glare and anchors elevated white cards.
   - **Elevated Cards & Panels (`SURFACE` `#FFFFFF`)**: Pure white surfaces bordered by `1px solid #E1E5EB` (`BORDER`) with `10px–12px` border radius.
   - **Navigation Rail (`#F0F3F7`)**: Subtle cool-slate left sidebar with active pill indicator (`#E8F0FE` fill, `3px solid #1F6FEB` left accent bar).
   - **Interactive Hover (`SURFACE_HOVER` `#EEF2F7`)**: Immediate tactile feedback on cards, list rows, and secondary buttons.

2. **High-Contrast Typography**:
   - **Primary Font Stack**: `"Segoe UI Variable Text", "Segoe UI", "Inter", sans-serif` (`14px` body, `#1D2733` ink).
   - **Page Titles (`#pageTitle`)**: `24px`, weight `700`, `#1D2733`.
   - **Section & Card Titles (`#cardTitle`, `#sectionHeader`)**: `16px`, weight `600`, `#1D2733`.
   - **Captions & Metadata (`#rowCaption`, `#mutedLabel`)**: `12px–13px`, `#5A6572` (never low-contrast light gray on white).

3. **Semantic Status & Trust Signaling**:
   - Every mutating desktop or browser step is visibly distinguished from read-only inspections and observation-only notes.
   - **Primary Accent (`ACCENT` `#1F6FEB`)**: Focused inputs, primary CTAs, active canvas node selection, and running steps.
   - **Success / Verified (`#15803D` on `#DCFCE7`)**: Completed runs and verified postconditions.
   - **Warning / Approval Gate (`#92400E` on `#FEF9C3` / `#FFFBEB`)**: Desktop approval panels (`#approvalPanel`) and observation-only badges.
   - **Danger / Error (`#B91C1C` on `#FEE2E2`)**: Stop recording button (`#dangerButton`), failed steps, and gate rejections.

---

## 2. Visual Workflow Canvas & Inspector Anatomy

- **Node Cards (`NodeCard` in `ui/editor/canvas.py`)**:
  - `10px` rounded rectangles on `QGraphicsScene` with antialiased edges and a live minimap (`#canvasMinimap`).
  - **Title**: Bold `10pt` in `TEXT_STRONG` (`#1D2733`) for instant legibility at any zoom level.
  - **Subtitle (`StepKind`)**: `8pt` in `ACCENT_TEXT` (`#1550B8`).
  - **Terminals (`Start` / `Finish`)**: Anchored pills in `#F2F4F7` with `BORDER_STRONG` (`#D1D5DB`) outlines.
- **Two-Way Selection Synchronization**:
  - Clicking a step in the canvas or in the step list below highlights both views and populates the right-hand `InspectorPanel`.
- **Guided Inspector (`InspectorPanel` in `ui/editor/inspector.py`)**:
  - Displays a tinted summary card (`#inspectorSummary`) showing step name, kind, mutating/read-only badge, target summary, and runtime evidence.
  - Changing the `Kind` selector (`#inspectorKindSelector`) dynamically populates a structured default target template so users never have to guess JSON keys.

---

## 3. Qt Style Sheet Constraints (Enforced by `tests/test_styles.py`)

- Every `#objectName` selector in `ui/styles/__init__.py` must be qualified with its exact Qt widget class (e.g., `QPushButton#primaryActionButton`, `QFrame#approvalPanel`, `QLabel#inspectorSummary`).
- Unsupported web CSS properties (`box-shadow`, `transition`, `transform`, `cursor`, `outline`) are forbidden so Qt never emits `Unknown property` warnings at runtime.
