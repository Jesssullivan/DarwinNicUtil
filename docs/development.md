# Development

## Setup

```bash
git clone https://github.com/Jesssullivan/DarwinNicUtil.git
cd DarwinNicUtil

uv sync --extra dev
```

Python 3.14+ is required for source-based development. The Nix package provides
its own interpreter.

## Project Structure

```text
DarwinNicUtil/
├── darwin-nic              # Legacy bootstrap runner
├── src/darwin_mgmt_nic/    # Runtime package
├── tests/                  # Unit and docs tests
├── docs/                   # MkDocs site
├── nix/                    # Nix package, overlay, and modules
├── .github/workflows/      # GitHub CI, docs, release, and secret scans
├── pyproject.toml          # Python package and tooling config
└── mkdocs.yml              # Docs config
```

## Common Commands

| Command | Purpose |
|---------|---------|
| `just dev` | Sync development dependencies |
| `just run <args>` | Run `darwin-nic` from the checkout |
| `just check` | Run format check, Ruff, and mypy |
| `just test` | Run pytest with coverage |
| `just docs-build` | Build MkDocs locally |
| `just build-wheel` | Build wheel and source distribution |
| `just nix-check` | Run `nix flake check` |

Direct equivalents:

```bash
uv run black --check src/ tests/
uv run ruff check src/ tests/
uv run mypy src/darwin_mgmt_nic
uv run pytest --cov=darwin_mgmt_nic --cov-report=term-missing
uv run mkdocs build --strict
uv build
```

## Test Policy

Runtime changes should include focused tests near the touched surface. The
current coverage gate starts at 40 percent and should ratchet upward as the
large TUI and network-manager surfaces become better covered.

Useful focused runs:

```bash
uv run --extra dev python -m pytest -q
uv run --extra dev python -m pytest tests/test_settings.py -q
uv run --extra dev python -m pytest tests/test_app.py -q
```

Tests mock system commands. Do not require live USB adapters, privileged network
mutation, Tailscale, or downstream switch access in the unit suite.

## Code Style

| Rule | Value |
|------|-------|
| Line length | 120 characters |
| Runtime target | Python 3.14+ |
| Formatter | Black |
| Linter | Ruff |
| Type checker | mypy strict mode |

Use typed functions for new runtime code. Keep comments short and reserve them
for command parsing, privilege boundaries, or platform-specific behavior that is
not obvious from the code.

## CI

GitHub Actions now own the public validation path:

| Workflow | Purpose |
|----------|---------|
| `ci.yml` | Format, lint, type-check, tests, docs build, package build |
| `secret-detection.yml` | Gitleaks and TruffleHog scanning |
| `docs.yml` | MkDocs build and GitHub Pages artifact upload |
| `release.yml` | Tag-triggered wheel/source distribution and GitHub Release |

GitLab CI remains in the repository for compatibility, but GitHub is the
release-facing surface.

## Releasing

Before tagging:

```bash
just check
uv run --extra dev python -m pytest -q
uv run --extra dev mkdocs build --strict
uv build
nix flake check
```

Then tag from a clean, reviewed branch:

```bash
git tag -a v2.1.0 -m "Release v2.1.0"
git push origin v2.1.0
```

The release workflow attaches `dist/*` to the GitHub Release. PyPI trusted
publishing and standalone binary distribution are follow-up release tasks unless
they are explicitly enabled before the tag.
