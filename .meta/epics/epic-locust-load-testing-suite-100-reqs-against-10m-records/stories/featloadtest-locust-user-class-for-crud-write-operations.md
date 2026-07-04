---
type: story
id: lDFpzNYxpor-
title: "feat(loadtest): Locust user class for CRUD write operations"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - agent:claude
  - size:M
  - performance
  - area:loadtest
estimate: null
epic_ref:
  id: EtcJSgkScBXc
github:
  issue_number: 262
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:7e4f9c17f6f8a39416126d7470a224efe663ce8c2113f9e30dd271489597f7fe
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-27T01:08:40Z
updated_at: 2026-06-03T00:00:00Z
---

## Context
Part of Epic #247 (F: Locust Load Testing Suite).

## Acceptance criteria
- [ ] `WriteUser` class with weighted tasks: create (5%), update (3%), delete (2%)
- [ ] Realistic payloads generated via Faker (names, emails, amounts, dates)
- [ ] Create: POST to `/{model}` with form data; verify 201/302 response
- [ ] Update: PUT to `/{model}/{id}` with modified fields; verify 200/302
- [ ] Delete: DELETE to `/{model}/{id}`; verify 200/302
- [ ] Uses auth session mixin for authentication

## Files
- `examples/erp/loadtest/locustfile.py` (extend)

## Dependencies
- Blocked by: #259 (F3 auth), #261 (F5 read users)
- Blocking: F7
