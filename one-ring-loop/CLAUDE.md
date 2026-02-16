# one-ring-loop — Package Context

Part of the **one-ring** monorepo. See the root `CLAUDE.md` for shared conventions.

## Purpose

<!-- Describe what this package does -->

## Package Commands

```bash
# From this directory:
just test          # Run tests for this package
just test-cov      # Tests with coverage
just typecheck     # Type check this package

# From monorepo root:
just test-pkg one-ring-loop   # Test this package
just check                # Run all checks (all packages)
```

## Layout

```
src/one_ring_loop/    # Source code
tests/                                # Tests
pyproject.toml                        # Package metadata (tool config inherited from root)
```
