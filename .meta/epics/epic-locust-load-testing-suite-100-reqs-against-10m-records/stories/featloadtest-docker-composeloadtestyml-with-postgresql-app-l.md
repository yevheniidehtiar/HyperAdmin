---
type: story
id: xPDyOCDzSTYV
title: "feat(loadtest): docker-compose.loadtest.yml with PostgreSQL + app + Locust"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - agent:claude
  - size:M
  - performance
  - area:infra
  - area:loadtest
estimate: null
epic_ref:
  id: EtcJSgkScBXc
github:
  issue_number: 258
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:efdab36e6db4a5e539dd11c20df301ebdf2f166050f4151d493ace49a7e6a7ca
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T01:08:11Z
updated_at: 2026-06-03T00:00:00Z
---

## Context
Part of Epic #247 (F: Locust Load Testing Suite).

## Acceptance criteria
- [ ] PostgreSQL 16 service with tuned `shared_buffers`, `work_mem`; persistent volume
- [ ] App service: ERP example on uvicorn with `--workers 3`; depends on postgres; runs seed on startup
- [ ] Locust master service: exposes web UI on port 8089
- [ ] Locust worker service: scalable via `docker compose up --scale locust-worker=3`
- [ ] `docker compose -f docker-compose.loadtest.yml up` starts full stack
- [ ] Health checks on postgres and app before Locust starts

## Files
- `docker-compose.loadtest.yml` (new)

## Dependencies
- Blocked by: #257 (F1 deps)
- Blocking: F8, F9
