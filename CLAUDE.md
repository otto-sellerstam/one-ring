# CLAUDE.md

This file provides guidance for Claude (or any AI assistant) working on this monorepo.

## Overview

**one-ring** — A toy project, building a truly async file IO using io_uring, and on it building a custom event loop, as well as integration into asyncio's native event loop

This is a **uv workspace** containing multiple Python packages.
Each package has its own `CLAUDE.md` with package-specific context.

## Packages

- **one-ring-core** — `one-ring-core/` (see `one-ring-core/CLAUDE.md`)
- **one-ring-loop** — `one-ring-loop/` (see `one-ring-loop/CLAUDE.md`)
- **one-ring-asyncio** — `one-ring-asyncio/` (see `one-ring-asyncio/CLAUDE.md`)
- **one-ring-http** — `one-ring-http/` (see `one-ring-http/CLAUDE.md`)
- **rusty-ring** — `rusty-ring/` (see `rusty-ring/CLAUDE.md`) — Rust/PyO3 bindings, uses maturin (not copier-managed)


## Tech Stack

- **Python 3.14+** with **uv workspaces** (single lockfile)
- **Rust** with **PyO3 + maturin** for native io_uring bindings
- **Ruff** for linting and formatting (ALL rules enabled, configured at root)
- **Pyrefly** for static type checking (strict mode)
- **Pytest** for testing (with coverage via pytest-cov)
- **Just** as task runner
- **Pre-commit** for git hooks

## Key Commands

```bash
just setup             # First-time: install deps + pre-commit hooks
just check             # Run ALL checks across all packages
just test-pkg <name>   # Test a single package
just lint-fix          # Fix lint issues across all packages
just format            # Format all code
```

## Architecture & Conventions

- **Shared config at root**: Ruff rules, Pyrefly settings, pytest options, and dev dependencies
  all live in the root `pyproject.toml`. Sub-packages inherit automatically.
- **Per-package**: Each package has its own `pyproject.toml` for package metadata,
  build system, and coverage source. No tool config duplication.
- **Coverage threshold: 80%** (enforced at root).
- Always run `just check` before committing. Pre-commit hooks enforce formatting.

## Monorepo Layout

```
one-ring/
├── pyproject.toml              # Workspace definition, shared tool config, dev deps
├── justfile                    # Root commands (orchestrates all packages)
├── CLAUDE.md                   # This file (repo-wide context)
├── one-ring-core/
│   ├── pyproject.toml          # Package metadata + build system
│   ├── CLAUDE.md               # Package-specific context
│   ├── justfile                # Package-specific commands
│   ├── src/one_ring_core/
│   └── tests/
├── one-ring-loop/
│   ├── pyproject.toml          # Package metadata + build system
│   ├── CLAUDE.md               # Package-specific context
│   ├── justfile                # Package-specific commands
│   ├── src/one_ring_loop/
│   └── tests/
├── one-ring-asyncio/
│   ├── pyproject.toml          # Package metadata + build system
│   ├── CLAUDE.md               # Package-specific context
│   ├── justfile                # Package-specific commands
│   ├── src/one_ring_asyncio/
│   └── tests/
├── one-ring-http/
│   ├── pyproject.toml          # Package metadata + build system
│   ├── CLAUDE.md               # Package-specific context
│   ├── justfile                # Package-specific commands
│   ├── src/one_ring_http/
│   └── tests/
├── rusty-ring/                 # Rust/PyO3 native extension (maturin, NOT copier-managed)
│   ├── Cargo.toml              # Rust dependencies
│   ├── pyproject.toml          # maturin build backend
│   ├── CLAUDE.md               # Package-specific context
│   ├── justfile                # Package-specific commands
│   ├── src/                    # Rust source (lib.rs)
│   ├── python/rusty_ring/      # Python type stubs (maturin mixed layout)
│   └── tests/
├── .pre-commit-config.yaml
├── .github/workflows/ci.yml
└── .copier-answers.yml
```

## Adding a New Package

- **Python packages**: Run `copier update` and add the new package name to the `packages` list.
- **Native extensions** (like `rusty-ring`): Manually create the package directory with maturin
  build backend, and add it to the workspace in root `pyproject.toml`. These are not managed
  by the copier template.
