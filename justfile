# Darwin Management NIC Configurator - Unified Task Runner
# Run 'just' to see available commands

# Default recipe: list all commands
default:
    @just --list

# ─────────────────────────────────────────────────────────────────────
# Development
# ─────────────────────────────────────────────────────────────────────

# Run darwin-nic in development mode
run *ARGS:
    uv run darwin-nic {{ ARGS }}

# Sync development dependencies
dev:
    uv sync --all-extras

# Enter Nix development shell
shell:
    nix develop

# ─────────────────────────────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────────────────────────────

# Run tests with coverage
test *ARGS:
    uv run pytest --verbose --cov=darwin_mgmt_nic --cov-report=term-missing --tb=short {{ ARGS }}

# Run tests with HTML report
test-report:
    uv run pytest --verbose --cov=darwin_mgmt_nic --cov-report=term-missing --cov-report=html --html=test-report.html --self-contained-html --tb=short

# ─────────────────────────────────────────────────────────────────────
# Code Quality
# ─────────────────────────────────────────────────────────────────────

# Run all checks (format + lint + type-check + test)
ci: format-check lint type-check test

# Run all checks without tests
check: format-check lint type-check

# Lint with ruff
lint:
    uv run ruff check src/ tests/

# Lint and auto-fix
lint-fix:
    uv run ruff check --fix src/ tests/

# Format with black
format:
    uv run black src/ tests/

# Check formatting without modifying
format-check:
    uv run black --check src/ tests/

# Type-check with mypy
type-check:
    uv run mypy src/darwin_mgmt_nic

# ─────────────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────────────

# Build Python wheel
build-wheel:
    uv build

# Build with Nix
build-nix:
    nix build .#darwin-nic -L

# Build PyInstaller binary (legacy)
build-binary:
    bash scripts/build.sh

# ─────────────────────────────────────────────────────────────────────
# Nix
# ─────────────────────────────────────────────────────────────────────

# Validate Nix flake
nix-check:
    nix flake check

# Show flake outputs
nix-show:
    nix flake show

# Update flake inputs
nix-update:
    nix flake update

# Build network utilities bundle
build-net-utils:
    nix build .#net-utils -L

# ─────────────────────────────────────────────────────────────────────
# Home Manager
# ─────────────────────────────────────────────────────────────────────

# Apply home-manager configuration
hm-apply:
    home-manager switch --flake .

# Dry-run home-manager build
hm-dry-run:
    home-manager build --flake .

# ─────────────────────────────────────────────────────────────────────
# System Manager (Linux only)
# ─────────────────────────────────────────────────────────────────────

# Apply system-manager configuration
[linux]
sm-apply:
    sudo system-manager switch --flake .

# Dry-run system-manager build
[linux]
sm-dry-run:
    system-manager build --flake .

# ─────────────────────────────────────────────────────────────────────
# Documentation
# ─────────────────────────────────────────────────────────────────────

# Build documentation
docs-build:
    uv run mkdocs build

# Serve documentation locally
docs-serve:
    uv run mkdocs serve

# ─────────────────────────────────────────────────────────────────────
# Housekeeping
# ─────────────────────────────────────────────────────────────────────

# Remove build artifacts
clean:
    rm -rf build/ dist/ result result-* htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
    @echo "Cleaned build artifacts."

# Show project and environment info
info:
    @echo "Project: darwin-mgmt-nic-configurator"
    @echo "Version: 2.0.0"
    @echo "Python:  $(python3 --version 2>/dev/null || echo 'not found')"
    @echo "uv:      $(uv --version 2>/dev/null || echo 'not found')"
    @echo "nix:     $(nix --version 2>/dev/null || echo 'not found')"
    @echo "just:    $(just --version 2>/dev/null || echo 'not found')"
    @echo "OS:      {{ os() }}"
    @echo "Arch:    {{ arch() }}"
