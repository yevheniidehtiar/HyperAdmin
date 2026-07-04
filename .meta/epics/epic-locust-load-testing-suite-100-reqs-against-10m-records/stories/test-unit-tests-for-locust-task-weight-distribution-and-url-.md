---
type: story
id: JvgiA6TzVyQF
title: "test: unit tests for Locust task weight distribution and URL generation"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:S
  - performance
  - area:loadtest
estimate: null
epic_ref:
  id: EtcJSgkScBXc
github:
  issue_number: 260
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:9a6f19a219de20cbb71449a89f17acd510650bb86ae22ca5c7955ba35e66b71c
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-27T01:08:22Z
updated_at: 2026-06-03T00:00:00Z
---

## Context
Part of Epic #247 (F: Locust Load Testing Suite).

## Acceptance criteria
- [ ] Test endpoint weight distribution matches spec (list=40%, search=15%, sort=10%, detail=15%, choices=10%, CRUD=10%)
- [ ] Test URL parameter generation: random page numbers, search terms, sort fields, valid IDs
- [ ] Test model selection covers Contact, Invoice, JournalLine

## Files
- `tests/unit/loadtest/test_locust_tasks.py` (new)

## Dependencies
- Blocked by: #257 (F1 deps)
- Blocking: F5
