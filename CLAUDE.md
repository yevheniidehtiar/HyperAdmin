# Project Constitution

For architectural principles, naming conventions, module boundaries, and dependency rules,
see [`CONSTITUTION.md`](CONSTITUTION.md). All planning and code generation must comply with it.

The Software Architect agent role and its review checklist are defined in [`AGENTS.md`](AGENTS.md).

---

## Development Methodologies

All planning, issue creation, and implementation in this project follows three joint methodologies:

### BDD — Behavior-Driven Development (`.claude/rules/bdd-conventions.md`)
- Every `feat` or `test(e2e)` issue **must** contain a `## Scenarios` section with Given/When/Then scenarios before any tasks are created.
- E2E tests (Playwright) map 1:1 to scenarios. Each test function is named after its scenario.
- Inline `# Given / # When / # Then` comments are mandatory in E2E tests.
- Size estimate derived from scenario count: 1–2 → S, 3–5 → M, 6+ → L.

### SDD — Specification-Driven Development (`.claude/rules/sdd-conventions.md`)
- Any `size:L` issue or epic touching ≥ 2 top-level modules **must** have a Design Doc at `docs/specs/{slug}.md` before implementation starts.
- SDD template: `docs/specs/TEMPLATE.md`.
- First sub-task of any SDD-required epic is `review(spec): approve SDD` — a **human gate**.
- All implementation sub-tasks are `blocked_by` the spec review task.

### Bottom-Up Architecture (`.claude/rules/planning-playbook.md`)
- Domain models → Business logic → API/Views → UI (never reversed).

---

# Commands

```bash
poe lint              # Run all linters (pre-commit hooks: ruff, mypy, commitizen)
poe test              # Run all tests (unit + e2e)
poe test:unit         # Unit tests only (pytest with coverage)
poe test:e2e          # E2E tests with Playwright
poe deps:bump         # Bump deps and verify across compatibility matrix
poe docs:serve        # Serve docs locally on port 8080
poe docs:build        # Build documentation
uv sync --all-extras  # Install all dependencies
uv run <cmd>          # Run commands in the virtual environment
```

## Dependency Management

HyperAdmin is a library consumed by other projects, so dependency bounds matter:

- **Runtime deps** (`[project.dependencies]`): Keep conservative lower bounds (e.g., `pydantic>=2.7`). Only bump when code requires a newer API or a security fix exists.
- **Dev deps** (`[project.optional-dependencies].dev`): Bump freely to latest — they only affect contributors.
- **Dependabot**: Configured for monthly automated dev dep bumps via PR.

### Bumping Dependencies

```bash
poe deps:bump         # Bump lock file and verify across compatibility matrix
```

This command:
1. Runs `uv lock --upgrade` to resolve latest compatible versions
2. Verifies lint + unit tests + security checks across 3 combos:
   - Python 3.10 + lowest-direct
   - Python 3.13 + lowest-direct
   - Python 3.13 + highest
3. Restores the default environment when done (even on failure)

## Branch and Commit Conventions

See [`.claude/rules/git-workflow.md`](.claude/rules/git-workflow.md) for commit message format,
commit authorship, and PR creation conventions.

---

# Hook-First Planning Instructions

## Hook-First Rule

Before answering any request that may lead to planning, code generation,
refactoring, architecture, or tests, you MUST first use the hook-injected
context tagged `[Coding Rules from Rippletide]` when it is present.

This requirement applies especially to plan mode requests such as:

- `/plan ...`
- requests that ask for a step-by-step implementation plan
- requests that ask what should be built before writing code

## Required Behavior Before Plan Mode

When the user enters a plan-style request, the assistant must treat the
hook result as input that is processed before producing the plan.

If hook rules are present:

1. Begin the response by explicitly naming the rules being applied.
2. Make the plan consistent with those rules.
3. Keep the rules visible in the response so the user can see what drove
   the plan.

Use a direct format such as:

`Applying rules: Rule A, Rule B, Rule C`

If the hook returns no rules, say so explicitly before continuing:

`Applying rules: none returned by hook`

## Required Behavior Before Code Generation

Before generating code, examples, patches, refactors, or tests:

1. Read the hook-injected rules first.
2. State which rules are being applied.
3. Ensure the implementation follows those rules.
4. If relevant, explain which rule changed the implementation or plan.

## Query Source

The hook query should use the user's current request text, not a fixed
prompt. For example, if the user submits:

`/plan write a hello world`

then the hook query should contain that exact text as the request being
evaluated.

## Enforcement

Do not produce planning or code output silently.

Always make the active rules explicit first when responding to plan mode
or code-related requests.

---

# E2E Testing Conventions

## E2E Selector Convention

E2E tests use Playwright's accessibility-first locators. Query priority (highest to lowest):

1. `page.get_by_role()` — buttons, links, headings, rows
2. `page.get_by_label()` — form inputs (matched via `<label for>`)
3. `page.get_by_text()` — static content assertions
4. `page.get_by_test_id()` — elements without a natural accessible role

**Do NOT** use `page.locator('.ha-*')` or positional DOM selectors in E2E tests. `ha-*` classes are for styling only and must not appear in test selectors.

### `data-testid` reference

| Template element | `data-testid` |
|-----------------|---------------|
| Sidebar `<aside>` | `sidebar` |
| List table | `list-table` |
| Each table row | `list-row` |
| View action link | `row-view-link` |
| Edit action link | `row-edit-link` |
| Delete action button | `row-delete-btn` |
| Search input | `search-input` |
| Pagination info | `pagination-info` |
| Pagination previous | `pagination-prev` |
| Pagination next | `pagination-next` |
| Pagination current page | `pagination-page` |
| Sort link (per field) | `sort-{field_name}` |
| Create New link | `create-link` |
| Form (create/update) | `model-form` |
| Field error list | `{field_name}-errors` |
| Detail fields container | `detail-fields` |

When adding new interactive or assertable elements to templates, add a `data-testid` following the `<view>-<element>` naming pattern.

---

## Agentic Workflow

This project follows a 5-agent Claude Code workflow. See `docs/agentic-workflow/`:

1. **Conductor** → orchestrates autonomous team cycles (Opus)
2. **Delivery Manager** → PR monitoring, E2E orchestration, merge execution (Haiku)
3. **Project Manager** → strategic planning, sprint cadence, priority triage (Sonnet)
4. **Code Reviewer** → architectural review against CONSTITUTION.md (Sonnet)
5. **OSS Triage Auditor** → detect AI-slop, enforce labels (Sonnet, optional)

## MCP Servers in Use

See `.mcp.json` for active MCP servers. Default model: `claude-sonnet-4-6`.

## Project Management: GitPM

All issue, epic, and milestone state is managed via **GitPM** (`.meta/` files).
Agents read/write `.meta/` directly instead of using `gh issue` or GitHub Projects API.
PRs are still managed via `gh pr`. See `.claude/project-config.md` for full reference.

```bash
./scripts/gitpm.sh validate                        # Validate .meta/ tree
./scripts/gitpm.sh pull --token "$GITHUB_TOKEN"    # Pull from GitHub
./scripts/gitpm.sh push --token "$GITHUB_TOKEN"    # Push to GitHub
```

## Key Files

| Path | Purpose |
|------|---------|
| `.meta/` | Git-native project state (stories, epics, milestones) |
| `scripts/gitpm.sh` | GitPM CLI wrapper |
| `justfile` | All dev targets |
| `scripts/` | Automation helpers |
| `.claude/commands/` | Claude slash commands |
| `docs/` | MkDocs source |
| `docs/agentic-workflow/` | OSS agentic workflow specs |
