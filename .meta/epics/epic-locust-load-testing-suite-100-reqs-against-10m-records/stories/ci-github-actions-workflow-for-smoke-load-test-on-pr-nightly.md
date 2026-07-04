---
type: story
id: 8W8i05r1Ib_j
title: "ci: GitHub Actions workflow for smoke load test on PR + nightly full run"
status: done
priority: medium
assignee: null
labels:
  - github_actions
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
  issue_number: 265
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:0df23bb60c662894f8798c783e04a9da16b6371bdd125feff05e4fca0038f657
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-27T01:08:54Z
updated_at: 2026-06-03T00:00:00Z
---

## Context
Part of Epic #247 (F: Locust Load Testing Suite).

## Acceptance criteria
- [ ] **PR smoke test**: triggers on PRs touching `adapters/`, `views/`, `core/`; seeds 1K records; 10 Locust users; 30s duration; SQLite
- [ ] **Nightly full test**: scheduled cron; seeds 100K records; 100 users; 5min; PostgreSQL via docker-compose
- [ ] Both compare against baseline; fail on regression (p95 > 2× or error rate > 1%)
- [ ] Uploads Locust HTML report as artifact
- [ ] Completes smoke test in <2min

## Files
- `.github/workflows/loadtest.yml` (new)

## Dependencies
- Blocked by: #258 (F2 docker-compose), #261 (F5 Locust users), #263 (F7 baselines), #254 (E7 CLI seed)
- Blocking: none (terminal task)
