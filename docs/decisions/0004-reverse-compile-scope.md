# ADR 0004 — Reverse-compile default scope

**Status:** Accepted
**Date:** 2026-05-06

## Decision

The reverse compiler operates by the rules in PRD §6:

1. **Recognized constructs round-trip** under canonical IR equality (PRD §6).
2. **Unrecognized constructs hard-block** with an actionable error naming the offending runtime, node type, and parameter set.
3. **No silent IR extension.** New IR node types only via deliberate IR-version bumps.
4. **Hard-block remediation UX:**
   a. Surface the exact runtime node type + parameter set that triggered the block.
   b. One-click "revert to last known IR-clean draft."
   c. "Request IR extension" button → templated issue with the offending construct.
   d. Fast-path "use `code` escape hatch" wizard with I/O schemas pre-filled.

## My recommendation

Keep the first reverse compiler deliberately narrow:
- Accept parameter edits on nodes FDE emitted.
- Accept node additions only when the node type is in IR v0.3 and the adapter can prove canonical equality.
- Reject runtime-native nodes outside IR v0.3 instead of inferring new IR shape.

This protects the Git source of truth and avoids a large reverse-engineering project before product fit is proven.

## Consequences

- The Phase 1 narrow reverse compiler implements (1) for the deep-coverage archetypes only; (2) is a hard error.
- Phase 2A's full reverse compiler implements (1) for all v0.3 constructs and (2)–(4) end-to-end.
- The Phase 0 gate criterion "Reverse-compile spike on one archetype" (PRD §7) proves (1) is feasible before MVP code is written.
