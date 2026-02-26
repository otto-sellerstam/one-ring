# rusty-ring

## Purpose

Rust-based io_uring bindings for Python via PyO3. Replaces the external `liburing` (Cython) dependency with bindings built on the `io-uring` crate from tokio-rs.

## Layout

```
src/              # Rust source code
python/rusty_ring/  # Python type stubs (maturin mixed layout)
tests/            # Python tests
pyproject.toml    # Package metadata (maturin build backend)
Cargo.toml        # Rust package config
```

## Commands

```bash
just dev           # Build debug extension via maturin develop
just dev-release   # Build release extension
just test          # Run Python tests (builds first)
just test-rust     # Run Rust tests
just check         # Run all checks
```

## Notes

- Uses maturin (not hatchling) as build backend
- Not managed by copier/bonfire template
- `src/` contains Rust code, not Python — Python stubs live in `python/`
