# ADR 0029: Resizable Session Workbench Panels

Status: Accepted

Date: 2026-05-11

## Context

The session detail workbench uses three columns for Planner chat, IR validation,
and compile artifacts. The xl layout was fixed at 4:6:2, leaving the compile
column too narrow for artifact cards, download actions, and manual import fields.

The workbench needs manual resizing on xl screens while preserving the existing
md and small-screen stacked grid behavior.

## Decision

Use `react-resizable-panels` for the xl session detail layout. The md and small
breakpoints continue to use the existing Tailwind grid.

The panel layout uses:

- `autoSaveId="fde-session-panels-v1"` so stored preferences are scoped and can
  be versioned by changing the id later.
- `localStorage["react-resizable-panels:fde-session-panels-v1"]`, managed by the
  library.
- Default sizes of 36%, 36%, and 28%, matching the requested 5:5:4 ratio.
- `minSize={20}` per panel. In v3 this value is a percentage, so the minimum is
  about 256 px at a 1280 px viewport and 384 px at a 1920 px viewport.
- Distinct accessible labels for the two resize handles.

## Why react-resizable-panels

The library gives us coordinated multi-panel resizing, pointer and keyboard
interactions, resize handles, and persisted layout state without adding a broad
drag-and-drop framework. It has no runtime dependencies beyond React peer
dependencies and is small enough for this console surface.

Pure CSS `resize` would not coordinate three columns or enforce a shared layout.
A custom implementation would need pointer events, keyboard accessibility,
touch behavior, resize constraints, and storage migration code.

## Version Pin

This decision pins `react-resizable-panels` to `^3.0.6`, the latest v3 release.
The current implementation uses the v3 `PanelGroup`, `Panel`, and
`PanelResizeHandle` API plus `autoSaveId`.

Version 4 changes the package API and layout persistence model. Upgrading to v4
should be handled as a separate dependency migration instead of being coupled to
this UX fix.

## Consequences

- Users can widen the compile column on xl screens and keep that preference
  across reloads.
- Resetting the layout removes the saved key and remounts the panel group to
  restore defaults.
- The workbench now depends on one focused React layout package.
  `package-lock.json` records the exact resolved version.
- The md and small-screen paths remain on the established Tailwind grid, which
  limits responsive regression risk.
