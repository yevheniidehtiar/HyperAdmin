---
type: story
id: GEbmrSdOnvTF
title: "chore(deps): add locust and rich to dev dependencies"
status: done
priority: medium
assignee: null
labels:
  - dependencies
  - agent-task
  - ready
  - size:S
  - performance
  - area:loadtest
estimate: null
epic_ref:
  id: EtcJSgkScBXc
github:
  issue_number: 257
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:37c968efcc5c75a6882580302e9099c4872abd7ccb6ad702c77782bb1ce76999
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T01:08:08Z
updated_at: 2026-06-03T00:00:00Z
---

## Context
Part of Epic #247 (F: Locust Load Testing Suite).

## Acceptance criteria
- [ ] Add `[project.optional-dependencies].loadtest` section with `locust>=2.29`, `rich>=14.0`
- [ ] `uv sync --extra loadtest` installs both packages
- [ ] Existing dev deps unaffected

## Files
- `pyproject.toml`

## Dependencies
- Blocked by: none
- Blocking: F2, F3, F4
