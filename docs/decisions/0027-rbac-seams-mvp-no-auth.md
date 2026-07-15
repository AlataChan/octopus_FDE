# ADR 0027: RBAC Seams Without MVP Authentication

Status: Accepted

Date: 2026-05-11

## Context

Phase 2 is single-tenant and multi-user, but real authentication and RBAC are
out of MVP scope. We still need every API surface to carry an actor identity so
future RBAC can be added without changing endpoint shapes.

## Decision

Keep an explicit actor seam in both frontend and backend.

- The frontend exposes `useActor()` and currently returns
  `{id: "single-user", role: "fde"}`.
- The typed API client sends `X-Actor-Id` on every request.
- The backend `get_actor()` dependency reads `X-Actor-Id` or defaults to
  `single-user`.
- Routes continue to receive an `actor` dependency even though authorization is
  currently a no-op.

`X-Actor-Id` is dev/MVP attribution only. It is not security. It is spoofable by
any client that can call the API.

When real authentication lands, the backend must:

1. Replace `get_actor()` with identity from a verified bearer token or session
   cookie.
2. Ignore caller-supplied `X-Actor-Id` entirely, except for explicit admin
   impersonation behind policy.
3. Add login/session/token verification endpoints and middleware.
4. Audit every endpoint to enforce permissions from the verified actor.

## Consequences

- M2.1 and M2.2 can attribute sessions, turns, archive events, and registry
  rows to a stable actor id.
- Future RBAC can reuse dependency injection seams without reshaping every route.
- No deployment may treat `X-Actor-Id` as an authentication mechanism.

## Update (2026-07-15): registry endpoint audit (H-11)

Item 4 of the Decision section called for an audit of every endpoint once
authentication landed. `loom/service/routes/registry.py` was the one surface
still missing it: list/get returned every actor's rows, and `mark-deployed`
accepted a workflow id from any authenticated actor regardless of who created
it.

That audit is now done for the registry routes:

- `list` and `get` are scoped to the requesting actor's own rows
  (`WorkflowRegistryStore` filters by `created_by_actor`, indexed).
- `mark-deployed` requires the requesting actor to be the workflow's creator;
  a mismatched or unknown workflow id returns 404 in both cases so existence
  isn't leaked to a non-owning actor.
- `mark-deployed` additionally checks the actor's role against an explicit
  allow-list (`DEPLOY_CAPABLE_ROLES`), so a future non-deploying role (e.g. a
  read-only viewer) is excluded without another code change.

This remains a **single-admin-equivalent** limitation, not full RBAC: every
authenticated actor still carries the same `role="fde"`, so today the role
check above is a no-op and the real boundary is per-actor ownership, exactly
as it already works for sessions, turns, and artifacts. Genuine multi-role
authorization (distinct roles beyond ownership, admin override of another
actor's rows) is still future work and should get its own ADR when real
multi-tenant auth lands.
