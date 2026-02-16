# one-ring

A toy project, building a truly async file IO using io_uring. Used for building a custom event loop using classic coroutines, as well as integration into asyncio's native event loop.

## Packages

- **one-ring-core** — `one-ring-core/`
- **one-ring-loop** — `one-ring-loop/`
- **one-ring-asyncio** — `one-ring-asyncio/`


## Setup

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install just (task runner)
# macOS:
brew install just
# Linux:
cargo install just # (or see https://github.com/casey/just#installation)

# First-time setup (install deps + pre-commit hooks)
just setup
```

## Development

```bash
just check             # Run all checks across all packages
just test-pkg <name>   # Test a single package
just lint-fix          # Auto-fix linting issues
just format            # Auto-format code
just test-cov          # Run tests with coverage (all packages)
```

Run `just` to see all available commands.

## Tools

| Tool | Purpose |
|------|---------|
| [uv](https://docs.astral.sh/uv/) | Package & environment management (workspaces) |
| [Ruff](https://docs.astral.sh/ruff/) | Linting & formatting |
| [Pyrefly](https://pyrefly.org/) | Type checking |
| [Pytest](https://docs.pytest.org/) | Testing |
| [Just](https://github.com/casey/just) | Task runner |
| [Pre-commit](https://pre-commit.com/) | Git hooks |
