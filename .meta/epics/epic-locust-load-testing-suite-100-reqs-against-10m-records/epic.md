---
type: epic
id: EtcJSgkScBXc
title: "epic: Locust Load Testing Suite (100 req/s against 10M+ records)"
status: done
priority: medium
owner: null
labels:
  - performance
  - area:infra
  - area:loadtest
milestone_ref:
  id: c-zG_jh0ymKJ
github:
  issue_number: 247
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:fd437c291b6dc38f0752580c4c34891411fd618a7301707e010a704394e7c6f3
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T01:05:12Z
updated_at: 2026-06-03T00:00:00Z
---

## Overview
Locust-based load testing suite with docker-compose (PostgreSQL + app + workers), baseline recording, regression detection, and CI integration.

## Sub-issues
- #257 chore(deps): add locust and rich to dev dependencies
- #258 feat(loadtest): docker-compose.loadtest.yml
- #259 feat(loadtest): auth session mixin for Locust
- #260 test: unit tests for task weights and URL generation
- #261 feat(loadtest): Locust read endpoint user classes
- #262 feat(loadtest): Locust CRUD write user class
- #263 feat(loadtest): baseline recording and regression comparison
- #264 feat(loadtest): update ERP Dockerfile for PostgreSQL
- #265 ci: GitHub Actions workflow (smoke + nightly)

## Endpoint coverage
| Endpoint | Weight |
|----------|--------|
| List view + pagination | 40% |
| Search | 15% |
| Sort | 10% |
| Detail view | 15% |
| FK choices | 10% |
| Create | 5% |
| Update | 3% |
| Delete | 2% |

## Regression thresholds
- p95 > 2× baseline = failure
- Error rate > 1% = failure
