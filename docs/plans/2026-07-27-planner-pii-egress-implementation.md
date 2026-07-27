# Planner PII Egress Guard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent PII-bearing Planner intents and non-load-bearing draft free
text from reaching any third-party Planner call.

**Architecture:** Introduce one typed outbound payload builder in
`loom/fde_session/planner_payload.py`. Both service Planner call paths use it,
and the service maps its typed block error to a value-free 422 response while
recording only the field and category.

**Tech Stack:** Python 3.11+, Pydantic v2, FastAPI, pytest

---

### Task 1: Specify detector and payload behavior

**Files:**

- Create: `tests/fde_session/test_planner_payload.py`
- Reference: `loom/fde_session/brief.py`
- Reference: `loom/fde_session/redaction.py`

**Step 1: Write failing category tests**

Add parametrized tests proving that seeded markers for an existing secret,
email, CN mobile, checksum-valid CN resident ID, and long digit run each raise
a typed block error identifying `intent` and the expected category.

**Step 2: Write the failing outbound-string test**

Build a rich `WorkflowBriefDraft`, call the planned chokepoint, and assert on
the returned outbound string itself. Assert that every allowed structured field
is present and every dropped marker, input description, and dropped key is
absent.

**Step 3: Write the failing detector-error test**

Replace the detector function with one that raises and assert the chokepoint
raises a typed block with category `detector_error`.

**Step 4: Verify RED**

Run:

```bash
python -m pytest -q tests/fde_session/test_planner_payload.py
```

Expected: collection/import failure because the outbound module does not exist.

### Task 2: Implement the pure outbound security boundary

**Files:**

- Create: `loom/fde_session/planner_payload.py`
- Test: `tests/fde_session/test_planner_payload.py`

**Step 1: Add the typed contract**

Add immutable `PreparedPlannerPayload` and `PlannerPayloadBlocked` types. The
exception must retain only `field_path` and `category`, never the input.

**Step 2: Add minimal detectors**

Implement the required patterns, including the standard mainland resident-ID
checksum. Wrap detector execution so any exception becomes a
`detector_error` block.

**Step 3: Add allowlist serialization**

Serialize only the approved brief fields and strip input descriptions. Sanitize
an edit context's nested `workflow_brief` through the same function.

**Step 4: Assemble exact outbound payloads**

Render fresh-draft and existing-workflow prompts in their current formats while
using only sanitized data. Return sanitized `extra_context` alongside the
message.

**Step 5: Verify GREEN**

Run:

```bash
python -m pytest -q tests/fde_session/test_planner_payload.py
```

Expected: all tests pass.

### Task 3: Prove and wire both service call paths

**Files:**

- Modify: `tests/service/test_routes_sessions.py`
- Modify: `loom/service/routes/sessions.py`

**Step 1: Write failing API tests**

Cover fresh generation and planner-assisted edit generation. Assert a seeded
intent marker returns HTTP 422, names `intent` and the category, never echoes
the marker, and never invokes the Planner.

**Step 2: Write a failing clean-generation payload test**

Capture the Planner's actual `user_message` and `extra_context`. Assert dropped
draft markers are absent, allowed structured values remain, and a clean brief
still produces the same IR result.

**Step 3: Verify RED**

Run:

```bash
python -m pytest -q tests/service/test_routes_sessions.py -k "planner_payload or outbound"
```

Expected: tests fail because the routes still use their local renderers and
return generic Planner failures.

**Step 4: Route every Planner call through the chokepoint**

Replace both local outbound render paths with
`prepare_outbound_planner_payload()`. Pass its message and sanitized context to
the Planner and remove obsolete render helpers.

**Step 5: Add the value-free 422 adapter**

Catch `PlannerPayloadBlocked` before generic Planner exceptions, fail the turn,
log/archive only its error code, field, and category, and raise a 422 response.

**Step 6: Verify GREEN**

Run:

```bash
python -m pytest -q tests/service/test_routes_sessions.py -k "planner_payload or outbound"
```

Expected: all focused tests pass.

### Task 4: Regression and quality gates

**Files:**

- Verify: `tests/fde_session/test_redaction.py`
- Verify: repository-wide Python and optional web sources

**Step 1: Run focused security tests**

```bash
python -m pytest -q tests/fde_session/test_planner_payload.py tests/fde_session/test_redaction.py tests/service/test_routes_sessions.py
```

**Step 2: Run required full gates**

```bash
python -m pytest -q
ruff check .
mypy loom
```

If web types or web sources changed, also run the package's web build command.

**Step 3: Inspect the final diff and branch ancestry**

Confirm the feature branch started at `main`, no unrelated files changed, and
no test/log/error payload contains a seeded detected value.

**Step 4: Commit**

Commit the verified implementation on the current feature branch. Do not merge
or push.
