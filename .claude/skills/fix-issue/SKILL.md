---
name: fix-issue
description: Implement a GitHub issue end-to-end following TDD — branch, code, tests, PR
argument-hint: "<issue-number>"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash(git *), Bash(gh *), Bash(just *), Bash(uv run *)
---

Fix story for GitHub issue #$ARGUMENTS in HyperAdmin.

## Steps

### 1. Read the story from .meta/
```bash
STORY_FILE=$(grep -rl "issue_number: $ARGUMENTS" .meta/stories/ .meta/epics/*/stories/ 2>/dev/null | head -1)
cat "$STORY_FILE"
```
Check `ROADMAP.md` to confirm priority and scope. Do not expand scope.

### 2. Start worktree

Run `/wt fix/issue-$ARGUMENTS` to create an isolated worktree branched from `develop`.

Then sync the environment:
```bash
uv sync --all-extras
```

### 3. Explore before changing
- Read relevant source files in `src/hyperadmin/`
- Read existing tests to understand patterns

### 4. TDD loop — for each component
1. Write a failing unit test in `tests/unit/`
2. Implement minimal code to make it pass
3. Refactor — strict type hints, no commented-out code

### 5. E2E test (if UI is involved)
- Write/update Playwright test in `tests/e2e/`
- Use accessibility-first locators: `get_by_role` > `get_by_label` > `get_by_text` > `get_by_test_id`
- `ha-*` CSS classes are for styling only — never use them in test selectors (see `.claude/rules/testing.md`)
- `just test-e2e` to verify

### 6. Pre-submission checks
```bash
just lint
just test
```
All must pass. Fix any failures before continuing.

### 7. Commit and PR
```bash
git -c user.name="Claude Code" -c user.email="noreply+claude-code@anthropic.com" \
  commit -m "fix: <description> (#$ARGUMENTS)"
git push origin HEAD
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr create --fill
```

**Important**: if `CLAUDE_GH_TOKEN` is not set, stop and ask the user to add it — do not create the PR under their identity.
