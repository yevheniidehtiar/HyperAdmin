---
type: story
id: FsqJ6esFI3nY
title: "feat(loadtest): auth session mixin for Locust (login + cookie reuse)"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - agent:claude
  - size:S
  - performance
  - area:loadtest
estimate: null
epic_ref:
  id: EtcJSgkScBXc
github:
  issue_number: 259
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:96137533c5b41f260ea40ba1a1892333bdf31a5a7fee3d7fc897fe3769188ceb
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T01:08:14Z
updated_at: 2026-06-03T00:00:00Z
---

## Context
Part of Epic #247 (F: Locust Load Testing Suite).
HyperAdmin uses session-based auth. Locust users need to login and reuse session cookies.

## Acceptance criteria
- [ ] Mixin class `HyperAdminAuthMixin` with `on_start()` that POSTs to `/login`
- [ ] Stores session cookie for reuse across all subsequent requests
- [ ] Handles login failure gracefully (logs error, marks user as failed)
- [ ] Configurable credentials via env vars (`LOADTEST_USER`, `LOADTEST_PASSWORD`)

## Files
- `examples/erp/loadtest/auth_mixin.py` (new)

## Dependencies
- Blocked by: #257 (F1 deps)
- Blocking: F5, F6
