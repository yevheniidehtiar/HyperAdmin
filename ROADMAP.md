# HyperAdmin Product Roadmap

This document outlines the planned features and development phases for HyperAdmin. Our goal is to build a modern, powerful, and easy-to-use admin interface for FastAPI.

> **For detailed epic-level planning, milestone tracking, and priority matrix, see [`docs/roadmap.md`](docs/roadmap.md).**

---

## Phase 1: Foundation & The "Walking Skeleton" (Completed)

This initial phase established the project's foundation, including the repository setup, a basic "walking skeleton" of the application, and a CI/CD pipeline. This work proved the core concept and allowed for rapid development.

---

## Phase 2: Core Functionality & Admin UI (Completed)

This phase built a complete and visually appealing admin interface with full CRUD functionality and a modern UI.

- **CRUD Implementation**:
    - [x] Add SQLAlchemy and SQLModel as dependencies.
    - [x] Refactor `ModelView` to work with SQLModel classes.
    - [x] Implement **Create View** with dynamic form generation.
    - [x] Implement **Update View** with pre-filled forms.
    - [x] Implement **Delete Action** with HTMX for a seamless UI experience.

- **Admin UI Epics**:
    - [x] **Navigation Sidebar**: Collapsible sidebar for easy navigation between different admin views.
    - [x] **Data Table Component**: Reusable and feature-rich data table with sorting, pagination, and filtering.
    - [x] **Forms & Widgets**: Standardized form elements including select/multiselect widgets (enum, FK, M2M, autocomplete).
    - [x] **Styling & Theming**: Clean and modern design system with theme support.
    - [x] **Custom Actions Framework**: Register and execute custom actions per model.
    - [x] **Fieldsets**: Group fields in admin forms with collapsible sections.
    - [x] **WCAG 2.1 AA Accessibility**: Keyboard navigation, ARIA, color contrast, screen reader support.

- **Documentation & Community Outreach**:
    - [x] Set up a documentation site using MkDocs with the `mkdocs-material` theme.
    - [x] Write a "Getting Started" tutorial and document the core classes.
    - [x] Create a complete, runnable project in the `examples/` directory.

---

## Phase 3: Advanced Features & Polish (In Progress)

With a solid foundation and a polished UI, this phase focuses on advanced features and making HyperAdmin more powerful and flexible.

Closed milestones: **v0.2.1** (Developer Experience & Examples), **v0.3.0** (Zero-Config & Auth).

- **Shipped**:
  - [x] Zero-config admin (auto-discover all SQLModel models in 3 lines of code).
  - [x] Authentication and authorization (login/logout, session management).
  - [x] File upload support with local and S3-compatible storage backends.
  - [x] Responsive design overhaul (mobile-first layout).
  - [x] Internationalization (i18n) with `gettext`, RTL support, locale switcher.
  - [x] Object-level permissions.
  - [x] Multi-factor authentication (MFA / OTP).
  - [x] Support for model relationships (FK, M2M, autocomplete).
  - [x] Custom actions (bulk and single-object).

- **Planned (open milestones)**:
  - [ ] Multi-tenancy filtering (`get_queryset` hook) — v0.5.3
  - [ ] Dashboard builder — v0.5.4
  - [ ] OAuth2 / OpenID Connect SSO — v0.5.2
  - [ ] Real-time updates (SSE / WebSocket) — v0.6.0
  - [ ] Presence tracking — v0.6.1
  - [ ] Scalability: cursor-based pagination, connection pool tuning — v0.7.0
  - [ ] Plugin & extension system — v0.8.0
  - [ ] AI-powered features — v0.8.0
