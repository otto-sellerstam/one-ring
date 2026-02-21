# List available recipes (default when running `just`)
default:
    @just --list

### Setup ###############################################################

# Install dependencies (dev included)
install:
    uv sync --all-packages

# Install pre-commit hooks and sync dependencies
setup: install
    uv run pre-commit install

### Code Quality (runs across all packages) #############################

# Run Ruff linter across all packages
lint:
    uv run ruff check .

# Run Ruff linter with auto-fix
lint-fix:
    uv run ruff check --fix .

# Format code with Ruff
format:
    uv run ruff format .

# Check formatting without changes
format-check:
    uv run ruff format --check .

# Run Pyrefly type checker
typecheck:
    uv run pyrefly check

### Testing #############################################################

# Run all tests across all packages
test *args:
    uv run pytest {{args}}

# Run tests for a specific package
test-pkg pkg *args:
    uv run pytest {{pkg}}/tests {{args}}

# Run tests with coverage (all packages)
test-cov:
    uv run pytest --cov=one-ring-core/src/one_ring_core --cov=one-ring-loop/src/one_ring_loop --cov=one-ring-asyncio/src/one_ring_asyncio --cov-report=term-missing --cov-report=html

# Run tests with verbose output
test-verbose *args:
    uv run pytest -v {{args}}

### Combined ############################################################

# Run all checks (lint + format-check + typecheck + test)
check: lint format-check typecheck test

### Docs ###############################################################

# Build documentation
docs:
    uv run --group docs mkdocs build

# Serve documentation with live reload
docs-serve:
    uv run --group docs mkdocs serve -a localhost:8001

### Maintenance ########################################################

# Update project from template (keeps current settings)
update:
    copier update --defaults

### Cleanup #############################################################

# Remove build artifacts and caches
clean:
    rm -rf .ruff_cache .pytest_cache htmlcov .coverage dist build site
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
