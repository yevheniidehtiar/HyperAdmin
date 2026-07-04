# HyperAdmin Architectural Constitution

This document is the authoritative source of truth for structural decisions in HyperAdmin.
It takes precedence over convention when the two conflict. It complements the coding rules in
`.claude/rules/code-style.md` — those cover syntax and style; this covers structure and boundaries.

---

## 1. Module Structure

The package lives at `src/hyperadmin/` using a `src`-layout. Modules map directly to domain
concepts, not technical layers.

```
src/hyperadmin/
├── core/        # contracts, orchestration, registries — no ORM, no HTTP
├── adapters/    # ORM-specific implementations of core contracts
├── views/       # HTTP handlers and template rendering — no business logic
├── auth/        # (Phase 3) authentication and permission hooks
├── actions/     # (Phase 3) custom model actions
├── uploads/     # (Phase 3) file upload handling
└── __init__.py  # public surface: re-export what library consumers need
```

Root-level package files (`db.py`, `routing.py`, `discover.py`) are acceptable today but should
migrate into `core/` as the package grows — they belong to orchestration, not to the public API.

**Rules:**
- One module = one responsibility. Mixed concerns (e.g. a file that handles both HTTP and DB) are a
  constitution violation.
- Avoid nesting beyond two levels (`hyperadmin/<domain>/<file>.py`). Sub-packages are permitted
  only when a domain has >5 files with distinct concerns.
- Each module exposes its public interface via `__init__.py`. Anything not re-exported there is
  treated as internal.
- Internal helpers are prefixed with `_` (file or function level); they must not be imported by
  other modules.

---

## 2. Dependency Direction

Dependencies flow **inward only**:

```
views/ ──► core/ ──► adapters/
  │          │
  └──────────┴──► auth/ (Phase 3, injects into core via protocol)
```

- `core/` must not import from `views/` or `adapters/`.
- `adapters/` must not import from `views/`.
- `views/` may import from `core/` and `adapters/` (through core-defined interfaces).
- Cross-domain communication goes through protocols or abstract classes defined in `core/`, never
  through direct concrete imports.

Circular imports between top-level modules are a **blocking violation**.

---

## 3. Naming Conventions

| Artifact | Convention | Example |
|---|---|---|
| Directory | `snake_case`, domain noun | `adapters/`, `views/`, `auth/` |
| File | `snake_case`, named after what it implements | `sqlmodel.py`, `dynamic.py` |
| Class | `PascalCase`, matches file concept | `SQLModelAdapter` in `sqlmodel.py` |
| Protocol/ABC | `PascalCase` + no suffix | `BaseAdapter`, not `IAdapter` or `AdapterProtocol` |
| Private helper | `_snake_case` prefix | `_build_filter_clause` |

**Banned names** at any level: `utils.py`, `helpers.py`, `misc.py`, `common.py`, `base.py`
(unless the file *only* contains a single base class, in which case name it after that class).

Generic names hide intent and become dumping grounds. If you can't name a file precisely, it
probably contains mixed concerns — split it instead.

---

## 4. Public Interface Contract

`src/hyperadmin/__init__.py` is the library's public surface. Rules:

- Only symbols intended for end-users are re-exported from `__init__.py`.
- Breaking changes to `__init__.py` exports require a semver major bump.
- New Phase 3 domains (auth, actions, uploads) must be opt-in imports, not auto-loaded on package
  import, to keep the base install lightweight.

The `BaseAdapter` ABC in `core/adapters.py` is the adapter contract. Any new ORM integration must
implement all abstract methods before it can be registered.

---

## 5. Growth Guardrails

These rules prevent premature expansion and future refactoring pain:

- **New feature = new module.** Extend an existing module only when the feature is a direct
  responsibility of that module. When in doubt, create a new one.
- **Size signal:** A module exceeding ~300 LOC is a review trigger. It may still be correct, but
  it must be explicitly justified in the PR.
- **Planned domains** for Phase 3 are reserved: `auth/`, `actions/`, `uploads/`. Do not create
  files or patterns in these domains outside of their dedicated phase work — placeholders block
  clean implementation later.
- **Adapter additions** (e.g. Django ORM, Tortoise) follow the existing pattern:
  implement `BaseAdapter`, add a file under `adapters/`, expose via `adapters/__init__.py`.
  No changes to `core/` are required for a new adapter.
- **Every new public interface** (class or function re-exported from `__init__.py`) requires at
  least one integration test before merge.

---

## 6. Dependency Policy

- Each external dependency must serve a single, clear purpose. Document why it exists in
  `pyproject.toml` if it isn't obvious from context.
- Wrap unstable or version-sensitive third-party APIs behind an adapter or thin wrapper inside the
  relevant domain module (e.g. HTMX conventions belong in `views/`, not spread across core).
- Dev-only dependencies (testing, linting, docs) must never appear in the main `[dependencies]`
  section.

---

## Violations

A constitution violation is any change that:

1. Creates a circular import between top-level modules.
2. Introduces a file named `utils.py`, `helpers.py`, `misc.py`, or `common.py`.
3. Imports from an outer layer into `core/` (e.g. `core/` importing from `views/`).
4. Adds business logic (data transformation, validation rules) directly inside a view handler.
5. Adds a new ORM integration by modifying `core/` rather than adding to `adapters/`.

The Software Architect agent (defined in `AGENTS.md`) is responsible for detecting these on
structural PRs.
