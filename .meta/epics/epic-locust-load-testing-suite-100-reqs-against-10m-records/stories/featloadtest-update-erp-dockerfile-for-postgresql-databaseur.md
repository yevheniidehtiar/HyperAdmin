---
type: story
id: YSdgUJFtZdSe
title: "feat(loadtest): update ERP Dockerfile for PostgreSQL + DATABASE_URL"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:examples
  - size:S
  - performance
  - area:infra
estimate: null
epic_ref:
  id: EtcJSgkScBXc
github:
  issue_number: 264
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d70434c4ce126569854cb32c50a94872b8a644f3fd2f417184517829f7837711
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-27T01:08:47Z
updated_at: 2026-06-03T00:00:00Z
---

## Context
Part of Epic #247 (F: Locust Load Testing Suite).

## Acceptance criteria
- [ ] Add `psycopg2-binary` (or `asyncpg`) to ERP Dockerfile
- [ ] Accept `DATABASE_URL` env var in `examples/erp/db.py`
- [ ] Fallback to SQLite (`sqlite+aiosqlite:///erp.db`) when `DATABASE_URL` not set
- [ ] Docker build succeeds; app starts with both SQLite and PostgreSQL URLs

## Files
- `examples/erp/Dockerfile` (modify)
- `examples/erp/db.py` (modify)

## Dependencies
- Blocked by: #258 (F2 docker-compose)
- Blocking: F9
