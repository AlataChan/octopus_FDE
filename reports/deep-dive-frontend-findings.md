# Deep-Dive Frontend Review — Findings Report

> **Scope**: `web/` — React/Vite frontend console for FDE (Octopus FDE Console)
> **Branch**: `codex/fde-design-agent-mvp` (4 commits ahead of main)
> **Date**: 2026-07-15
> **Test Suite**: 52 tests, 18 files, all passing

---

## Executive Summary

The FDE Console frontend is a **well-structured, cleanly-organized React 18 application** with disciplined component composition, consistent Tailwind token usage, and proper i18n coverage. The codebase shows strong engineering fundamentals: TypeScript strict mode, react-query for server state, react-resizable-panels for layout, and a custom UI kit that avoids heavy third-party design systems.

**Key strengths**: Consistent CSS variable token system across dark/light themes, proper ARIA roles on tabs/panels, thorough i18n coverage in both zh/en, and a well-designed IR → flow graph converter with proper error boundaries.

**High-priority risks**: The main page component (`[id].tsx`) is a 323-line "god component" that owns too many concerns; the `zustand` dependency is dead weight; no tests exist for the core chat interaction flow or the flow visualization, and the `flow-layout.ts` module (472 lines of complex graph logic) has zero dedicated tests.

**Verdict**: Production-ready for MVP usage, but the test coverage gaps and god-component pattern will become maintenance bottlenecks as features accumulate.

---

## Findings by Severity

### Critical

None identified. No security vulnerabilities, no broken core flows, no type errors.

### High

#### H1 — `[id].tsx` god component (323 lines)
- **File**: `web/src/pages/sessions/[id].tsx:35-323`
- **Issue**: The SessionDetailPage owns: 6 useMutation hooks, 4 useQuery hooks, mobile sidebar state, template modal state, LLM config dismissal flag, layout reset state, diff computation, flow diff summary construction, node selection state, download logic, and all layout JSX for desktop/mobile variants.
- **Failure scenario**: Adding any new interactive element (e.g., a settings drawer) forces touching this file, increasing merge conflict surface and mental overhead for every contributor.
- **Suggested fix**: Extract the desktop layout, mobile layout, and all mutation logic into custom hooks or dedicated sub-components. The `useSession` hook already exists — extend it to include turns mutations, or create a `useSessionWorkbench` hook that encapsulates all mutation + derived state.

#### H2 — Zero test coverage for core interaction components
- **Files**: `web/src/components/console/ChatPanel.tsx` (173 lines), `web/src/components/console/FlowCanvas.tsx` (158 lines), `web/src/components/console/FlowNode.tsx` (138 lines), `web/src/components/console/CompileBar.tsx` (246 lines), `web/src/components/console/ClarifyBubble.tsx` (89 lines), `web/src/components/console/QuestionnaireBubble.tsx` (108 lines)
- **Issue**: These are the most user-facing, stateful components in the app, and **none have dedicated tests**. The ChatPanel manages turn rendering decision logic (clarify/plan/brief_review branches), message submission, and sending state — all untested. FlowCanvas has complex error/empty/loaded state branches — all untested.
- **Failure scenario**: A refactor of `isInteractiveTurn()` breaks the clarify flow; no test catches it until manual QA.
- **Suggested fix**: Prioritize: (1) ChatPanel turn rendering tests (mock API, assert correct bubble renders for each `kind`), (2) FlowCanvas error-state tests using `FlowLayoutError`, (3) CompileBar form submission tests.

#### H3 — `flow-layout.ts` has no dedicated tests (472 lines)
- **File**: `web/src/lib/flow-layout.ts`
- **Issue**: This module contains the entire IR-to-flow-graph pipeline: normalization, edge collection (explicit + implicit from `next`/`default`/`branches`), cycle detection via DFS, dagre layout delegation, diff summary computation, error classification, and node-field rendering. There is **no test file** for this module despite `tests/fixtures/malformed-ir.yaml` existing in the repo.
- **Failure scenario**: A change to `collectEdges()` that mishandles branch edges silently produces wrong flow visualizations; no test catches it.
- **Suggested fix**: Create `web/src/lib/flow-layout.test.ts` consuming `malformed-ir.yaml` fixtures. Test: valid IR produces correct nodes/edges, cycle detection throws, missing trigger throws, invalid node type throws, diff summary correctly identifies added/removed/modified nodes.

#### H4 — `zustand` is an unused dependency
- **File**: `web/package.json:25`
- **Evidence**: `depcheck` flags it as unused; `grep -r "zustand" web/src/` returns zero matches.
- **Impact**: Adds ~9KB to the bundle unnecessarily; misleading for new contributors who expect zustand-based state management.
- **Suggested fix**: Remove from `dependencies` in `package.json` and run `npm install`.

### Medium

#### M1 — `ChatColumn` and `CompileColumn` are pass-through wrappers
- **Files**: `web/src/components/console/ChatColumn.tsx` (12 lines), `web/src/components/console/CompileColumn.tsx` (32 lines)
- **Issue**: Both components are thin wrappers that rename props and delegate directly to `ChatPanel` and `CompileBar` respectively, adding zero logic.
- **Suggested fix**: Either (a) eliminate the wrappers and use ChatPanel/CompileBar directly in `[id].tsx`, or (b) move the prop-renaming concern into the parent. Preference: eliminate — fewer files to traverse.

#### M2 — Duplicated `relativeTime()` and `sessionTitle()` functions
- **Files**: `web/src/components/console/SessionsSidebar.tsx:424-440` and `web/src/pages/sessions/list.tsx:230-247` (relativeTime); `SessionsSidebar.tsx:246-248` and `sessions/list.tsx:213-215` (sessionTitle)
- **Issue**: Identical implementations copied across two components. Any change (e.g., time formatting) requires updating both locations.
- **Suggested fix**: Extract to `web/src/lib/format.ts` and import in both places.

#### M3 — `useIsLg` and `useIsXl` are duplicate implementations
- **Files**: `web/src/hooks/useIsLg.ts` (29 lines), `web/src/hooks/useIsXl.ts` (29 lines)
- **Issue**: Identical logic except for the media query string.
- **Suggested fix**: Create `web/src/hooks/useMediaQuery.ts`: `function useMediaQuery(query: string): boolean` using `useSyncExternalStore`, then `export const useIsLg = () => useMediaQuery("(min-width: 1024px)")`.

#### M4 — `apiFetch` / `apiFetchNoContent` / `apiBlob` duplicate header logic
- **File**: `web/src/lib/api.ts:25-81`
- **Issue**: Three nearly-identical functions with the same header setup pattern, actor ID injection, and 401 redirect. The only difference is the response handling (`.json()` vs void vs `.blob()`).
- **Suggested fix**: Extract shared logic: `function createRequestInit(init: RequestInit): RequestInit` and `async function handleResponse(response: Response): Promise<void>` (for 401/error handling). The three functions then differ only in their response body extraction.

#### M5 — No focus trapping in Modal
- **File**: `web/src/components/ui/Modal.tsx:39-65`
- **Issue**: The modal handles Escape key dismissal and backdrop-click dismissal, but does not trap focus within the modal. Tab/Shift+Tab can navigate to elements behind the overlay.
- **Suggested fix**: Implement a `useEffect` that queries focusable elements within the dialog and implements a roving tabIndex or focus-trap pattern. Alternatively, use `inert` attribute on the app root when modal is open (simpler).

#### M6 — `TurnBubble` is a local sub-component inside `ChatPanel.tsx`, not exportable for testing
- **File**: `web/src/components/console/ChatPanel.tsx:86-152`
- **Issue**: `TurnBubble` is defined locally inside `ChatPanel.tsx`. It cannot be imported for isolated unit testing, and its complex rendering logic (5 conditional branches based on `kind`) can only be tested through the full `ChatPanel` integration test.
- **Suggested fix**: Extract `TurnBubble` to its own file `web/src/components/console/TurnBubble.tsx` with explicit exported type props.

#### M7 — `tests/` directory outside `src/` not type-checked by `tsc`
- **File**: `web/tsconfig.json:19` (`"include": ["src"]`)
- **Issue**: The TypeScript compiler only checks `src/`. Tests in `web/tests/` (and `src/**/*.test.ts`) are excluded from type-checking by the build script (`tsc --noEmit`). This means type errors in tests are only caught when `vitest` runs, not during `npm run build`.
- **Suggested fix**: Either (a) add `"tests"` to the `include` array, or (b) create a separate `tsconfig.test.json` that extends the base and includes `tests/`, run as a separate CI step.

#### M8 — `gen:types` script is not portable
- **File**: `web/package.json:12`
- **Issue**: `"gen:types": "openapi-typescript http://localhost:18080/openapi.json -o src/lib/types.generated.ts"` hardcodes `localhost:18080`. This fails in CI or when the backend runs on a different port.
- **Suggested fix**: Use an environment variable: `"${VITE_API_BASE_URL:-http://localhost:18080}/openapi.json"`.

#### M9 — `vite.config.ts` `test.exclude` blocks `tests/console/**` but directory doesn't exist
- **File**: `web/vite.config.ts:13`
- **Issue**: The config excludes `tests/console/**` from vitest, but this directory does not exist. This is either dead config or a placeholder for E2E tests that were never created.
- **Suggested fix**: Remove the exclusion or add a comment explaining the intent.

#### M10 — `ClarifyOptionButton` accessibility: no radiogroup semantics
- **File**: `web/src/components/console/ClarifyOptionButton.tsx` and `web/src/components/console/ClarifyBubble.tsx:54-66`
- **Issue**: `ClarifyOptionButton` uses `aria-pressed` (toggle button pattern) for single-select behavior. The correct pattern for exclusive selection is `role="radiogroup"` on the container and `role="radio"` + `aria-checked` on each button. This is semantically misleading for screen readers.
- **Suggested fix**: Change `aria-pressed` to `aria-checked`, add `role="radio"` to each button, add `role="radiogroup"` to the grid container.

### Low

#### L1 — `hardcoded English aria-label on Modal close button`
- **File**: `web/src/components/ui/Modal.tsx:54`
- **Issue**: `aria-label="Close modal"` is hardcoded in English, not using i18n.
- **Suggested fix**: Accept a `closeLabel` prop or use `useTranslation()`.

#### L2 — No `title` attribute on `<html>` element for accessible page description
- **File**: `web/index.html:2`
- **Issue**: `<html lang="zh-CN">` lacks a corresponding `<meta name="description">` or descriptive `<title>` beyond "Octopus FDE Console".
- **Suggested fix**: Add `<meta name="description" content="AI-assisted workflow engineering console for Hiagent and Dify runtimes">`.

#### L3 — `apiBlob` doesn't extract error body on failure
- **File**: `web/src/lib/api.ts:66-81`
- **Issue**: When `apiBlob` gets a non-OK response, it throws `Error("API request failed: ${status}")` without attempting to read the error body. If the server returns a JSON error message (which it does for most routes), this information is lost.
- **Suggested fix**: On non-OK, attempt to read the response as JSON first; fall back to the status-only error if that fails.

#### L4 — `CompileBar.tsx` unused `Mode` prop when target is `dify`
- **File**: `web/src/components/console/CompileBar.tsx:57`
- **Issue**: When `target === "dify"`, `mode` is set to `null`, but the mode select dropdown remains enabled with `chatflow`/`chat` options (it doesn't visually appear disabled for Dify). Actually looking again, line 92 correctly `disabled={target !== "hiagent"}` — this is handled. No issue.

#### L5 — `BriefPanel.sectionKeys` is a const array but `WorkflowBriefSnapshot` has an index signature
- **File**: `web/src/components/console/BriefPanel.tsx:13-23`
- **Issue**: `WorkflowBriefSnapshot` is defined with `[key: string]: unknown` in `types.ts:87`, meaning any key is valid. The `sectionKeys` array in `BriefPanel` only displays 9 specific keys. Any server-added fields beyond these 9 are silently hidden from the user.
- **Suggested fix**: Document this as intentional (brief is a preview, not a full dump) and add a comment, OR iterate `Object.keys(brief)` instead of a hardcoded array.

#### L6 — `BrandMark.tsx` exports `BRAND_LOGO_SRC` but it's only used internally
- **File**: `web/src/components/BrandMark.tsx:4`
- **Issue**: `BRAND_LOGO_SRC` is exported but never imported elsewhere. If it's meant to be a public constant for other components, it's unused. If not, it should not be exported.
- **Suggested fix**: Remove the `export` keyword or keep it with a comment documenting its intent.

#### L7 — `useActor()` always returns a hardcoded constant
- **File**: `web/src/lib/useActor.ts:11-13`
- **Issue**: The hook is called as `useActor()` in `TopBar` but always returns `{ id: "single-user", role: "fde" }`. It adds zero dynamism.
- **Suggested fix**: Either make it configurable (e.g., read from context or localStorage) or replace it with a direct import of `DEFAULT_ACTOR`.

#### L8 — `FlowNode.tsx` `iconForType` uses chained if-statements instead of a map
- **File**: `web/src/components/console/FlowNode.tsx:106-138`
- **Issue**: 10 chained `if` statements for type-to-icon mapping. A `Record<string, Icon>` lookup would be more performant and maintainable.
- **Suggested fix**: Create a `const NODE_ICONS: Record<string, typeof Play>` map and look up with fallback to `TerminalSquare`.

---

## Test Coverage Gaps

### Current Coverage (52 tests, 18 files)
| Area | Tested? | Notes |
|---|---|---|
| API fetch layer | Partial | `api.test.ts` covers `apiFetch` and `deleteSession` only |
| Login page | Yes | 2 tests: brand render + form submit |
| Session list page | Yes | 1 test: delete session flow |
| TopBar | Yes | 1 test: brand navigation |
| ChatPanel / TurnBubble | **No** | Core interaction — zero tests |
| ClarifyBubble | **No** | New component — zero tests |
| QuestionnaireBubble | **No** | New component — zero tests |
| BriefPanel | **No** | Zero tests |
| FlowCanvas | **No** | Complex state — zero tests |
| FlowNode | **No** | Zero tests |
| IRColumn (tabs, drawer) | **No** | Zero tests |
| IRView / IRDiffView | Partial | IRDiffView has 2 tests; IRView has none |
| NodeInspectDrawer | Yes | 2 tests |
| CompileBar / ArtifactCard | **No** | Form + deployment marking — zero tests |
| FlowErrorPanel | Yes | 1 test |
| StateStepper | Yes | 6 tests |
| LLMConfigModal | Yes | 1 test |
| ChatPanel (clarify integration) | Yes | 1 test for ClarifyBubble integration |
| Session detail page | Partial | Only ResetLayout test (tests layout, not mutations) |
| flow-layout.ts (472 lines) | **No** | Zero tests despite complex logic |
| yaml.ts (45 lines) | **No** | Zero tests |
| session-diff.ts (17 lines) | Yes | 2 tests |
| useSession / usePlannerTurn hooks | **No** | Zero hook-level tests |
| SessionsSidebar | **No** | Zero tests (441 lines of complex list/menu/rename logic) |
| TemplateModal | **No** | Zero tests |

### Critical Gaps (prioritized)
1. **`flow-layout.ts`** — Test `irToFlowGraph` with valid IR, cycle, missing trigger, invalid type, edge validation
2. **`ChatPanel.tsx` + `TurnBubble`** — Test all 5 turn `kind` branches: clarify, questionnaire, brief_review, design_preview, plan (with and without errors)
3. **`CompileBar.tsx`** — Test form submission, target/mode/binding selection, artifact download, deployment marking
4. **`SessionsSidebar.tsx`** — Test collapse/expand, rename flow, delete flow, session list rendering

---

## Docs-vs-UI Consistency Notes

| Doc Reference | Claim | Actual UI | Match? |
|---|---|---|---|
| `fde-console-zh.md` §2 | "点击'新建 Session'" | Template modal appears with blank/template tabs | ✅ Match |
| `fde-console-zh.md` §3 | "首次进入 session 会弹出 LLM 配置" | `LLMConfigModal` opens when `llm_model` is null | ✅ Match |
| `fde-console-zh.md` §4 | "在左侧输入业务意图" | Chat panel on left in horizontal PanelGroup | ✅ Match |
| `fde-console-zh.md` §5 | "两次成功 turn 后可展开 IR 变更列表" | `selectIRDiffTurnIds` filters for 2+ succeeded turns | ✅ Match |
| `fde-console-zh.md` §6 | "在底部 Compile Bar" | Compile is in bottom-right panel (vertical split), not a "bar" at page bottom | ⚠️ Minor terminology mismatch |
| `fde-console-zh.md` §8 | "填入平台 App ID 和备注，点击'标记已导入'" | `ArtifactCard` has platform_app_id input + deployment note + "标记已导入/交接" button | ✅ Match |
| `2026-05-23-self-design-clarify` §9.2 | `ClarifyBubble` + `QuestionnaireBubble` components | Both components exist and are rendered via `TurnBubble` based on `turn.kind` | ✅ Match |
| `2026-05-23-self-design-clarify` §9.3 | i18n keys `clarify.title`, `clarify.send`, etc. | All specified i18n keys exist in `zh.json`/`en.json` | ✅ Match |
| `fde-console-en.md` §8 | "click 'Mark imported'" | Button says "Mark imported/handed off" (slight wording difference) | ⚠️ Minor wording drift |
| User guide: "把 ZIP 拖入 Hiagent" | Manual import described | `downloadArtifact` creates a blob download link — no drag target | ⚠️ Docs describe user action, not UI feature |

### Docs-vs-UI Summary
The docs accurately describe the current UI flow. Two minor issues:
1. The "Compile Bar" terminology in the user guide suggests a persistent bottom bar, but the implementation is a resizable panel in the bottom-right split. Consider updating docs to say "右侧下方交付面板" (lower-right delivery panel).
2. The English guide says "Mark imported" while the button now reads "Mark imported/handed off" — a minor drift from the original spec but arguably an improvement.

---

## Build/Tooling Config Sanity

### Overall Assessment: Healthy

- **Vite 6.x** with React plugin — modern and correctly configured
- **TypeScript 5.5** with `strict: true` — all strict checks enabled
- **Vitest 2.x** with jsdom environment — appropriate for component testing
- **Tailwind CSS 3.4** with CSS variable token system — well-structured theming
- **ESLint 8.x** with typescript-eslint + react-hooks plugin — standard setup

### Issues Found

| # | Issue | Severity |
|---|---|---|
| 1 | `zustand` is an unused dependency (confirmed by depcheck + code grep) | Medium |
| 2 | `tsconfig.json` `include` only covers `src/`, excluding `tests/` from type-checking | Medium |
| 3 | `gen:types` script hardcodes `localhost:18080` — not portable to CI | Low |
| 4 | `vite.config.ts:13` excludes nonexistent `tests/console/**` directory | Low |
| 5 | No `.prettierrc` or `.editorconfig` — relying solely on ESLint for formatting | Low |
| 6 | `package-lock.json` has npm audit warnings (from `npm install` output) | Low |
| 7 | `test.setupFiles` points to `src/test/setup.ts` which only imports `@testing-library/jest-dom/vitest` — minimal but sufficient | Note |

### Version Drift Assessment
- `react` / `react-dom` at 18.3.1 — latest React 18 stable ✅
- `@tanstack/react-query` at 5.51.23 — current major version ✅
- `@xyflow/react` at 12.10.2 — latest stable ✅
- `vite` at 6.4.2 — latest major ✅
- `vitest` at 2.1.9 — stable (v3 is available but not necessary) ✅
- `eslint` at 8.57.0 — ESLint 9 is available; migration to flat config is a future task

No concerning version drift. All packages are within their current major versions.

---

## Open Questions

1. **Why is `zustand` installed but unused?** Was it intended for session/workflow state management that was later moved to react-query? If so, the plan may have shifted mid-implementation and zustand was not cleaned up.

2. **Is the `tests/console/**` exclusion in `vite.config.ts` for planned E2E tests?** The directory doesn't exist. If Playwright/Cypress E2E tests are planned, they should be documented or the exclusion should be removed.

3. **Why does `ChatColumn` exist?** It's a 1:1 pass-through to `ChatPanel`. Was it intended to add sidebar-specific chat features (e.g., a different header or styling) that were never implemented? Same question for `CompileColumn` → `CompileBar`.

4. **Should `BriefPanel.sectionKeys` be derived from `WorkflowBriefSnapshot` keys dynamically?** Currently it's a hardcoded array. If the backend starts sending new brief fields (e.g., `persona` or `environment`), they'll be silently hidden.

5. **Is the 30-minute Planner timeout in `ChatPanel` subtitle ("最多等待 120 秒") accurate?** The subtitle says 120 seconds, but the Planner can run longer. A hard timeout mismatch could confuse users.

6. **Should the `vi.mock` patterns in `ResetLayout.test.tsx` be extracted to shared test utilities?** The test file contains 80+ lines of mock setup that would be useful for other integration tests.

---

## Appendix A: File Inventory

### Components (34 files in `web/src/components/console/`)
- **Layout/Page**: `ChatColumn`, `ChatPanel`, `CompileColumn`, `CompileBar`, `IRColumn`, `IRView`, `IRDiffView`, `FlowCanvas`, `FlowNode`, `FlowErrorPanel`
- **Interaction**: `ClarifyBubble`, `ClarifyOptionButton`, `QuestionnaireBubble`, `BriefPanel`
- **Modals/Dialogs**: `LLMConfigModal`, `TemplateModal`, `DeleteSessionDialog`, `NodeInspectDrawer`
- **Navigation**: `SessionsSidebar`, `StateStepper`, `WorkbenchHeader`
- **Validation**: `ValidatorPanel`

### Hooks (6 files)
- `useAuth`, `useTheme`, `useSession`, `usePlannerTurn`, `useIsLg`, `useIsXl`

### Library (12 files in `web/src/lib/`)
- `api.ts` (225 lines), `types.ts` (212 lines), `flow-layout.ts` (472 lines), `yaml.ts` (45 lines), `session-diff.ts` (17 lines), `cn.ts` (3 lines), `i18n.ts` (18 lines), `useActor.ts` (13 lines), `types.generated.ts` (auto-generated)

### UI Kit (8 files in `web/src/components/ui/`)
- `Button`, `Card`, `Chip`, `Input`, `Select`, `Textarea`, `Badge`, `Modal`

### Test Files (18 test files)
- Total: 52 tests, all passing

---

## Appendix B: Test Run Output

```
Test Files  18 passed (18)
     Tests  52 passed (52)
  Duration  37.74s
```

All tests pass on the `codex/fde-design-agent-mvp` branch.
