# Release Readiness Plan

Date: 2026-04-25
Target release: v2.1.0
Status: Active branch plan

## Goal

Make DarwinNicUtil release-ready as a generic USB management NIC tool: tested,
documented, packaged, scanned for secrets, and safe for bastion workflows.

The supported generic operator path is:

```text
tailnet -> bastion host -> USB OOB NIC -> managed network device
```

Switch hostnames, credentials, OOB MAC addresses, RouterOS commands, and
site-specific recovery policy remain outside this repository.

## Current Branch State

| Surface | Status |
|---------|--------|
| Tests | Unit suite is green with coverage above the configured 40 percent gate |
| CI | GitHub Actions now cover CI, docs, secret scans, and tag releases |
| Docs | MkDocs includes quickstart, architecture, CLI, bastion, artifacts, and this plan |
| Packaging | Wheel/source distribution and Nix package paths are present |
| Security | Repo-local gitleaks config and scan workflow are present |
| Changelog | `CHANGELOG.md` records work since `v2.0.0` |

## Release Contract

Keep these public interfaces stable for v2.1.0:

- `darwin-nic = "darwin_mgmt_nic.app:main"`
- `darwin-nic configure --device-ip <ip> --laptop-ip <ip> --preserve-wifi`
- `darwin-nic configure --profile <name> --preserve-wifi`
- `darwin-nic status`
- `~/.config/darwin-nic/config.toml`
- `packages.${system}.darwin-nic`
- `packages.${system}.net-utils` as an optional Nix output

The TOML profile schema remains:

```toml
default_profile = "homelab"

[defaults]
preserve_wifi = true
dry_run = false
show_dashboard = false

[profiles.homelab]
device_ip = "192.168.88.1"
laptop_ip = "192.168.88.100"
mgmt_network = "192.168.88.0/24"
device_name = "Lab Management Device"
device_type = "network"
```

Profile names and values are examples only. Downstream repos own their own
device names, policies, and secrets.

## Remaining Work

| Priority | Task | Done When |
|----------|------|-----------|
| P0 | Final docs/readme accuracy pass | README and MkDocs no longer overpromise binaries, PyPI, Homebrew, or Linux parity |
| P0 | Release artifact smoke test | Wheel installs in a clean venv and `darwin-nic --help` works |
| P0 | Nix validation | `nix flake check` passes with new docs and tests included |
| P0 | Hardware dry-run | `darwin-nic status` and `configure --dry-run` are checked on a bastion Mac |
| P1 | Close or split issue #4 | Shipped NECP diagnostics are documented; remaining hardware evidence is tracked |
| P1 | Ratchet tests | Next target is 50 percent coverage after macOS/network-manager follow-ups |
| P2 | PyPI trusted publishing | Trusted publisher is configured and release workflow publishes packages |
| P2 | Binary installer decision | Either validate PyInstaller releases or document them as unsupported |
| P3 | Sophos and ABR spikes | Issues #2 and #3 are scoped separately from v2.1.0 release readiness |

## Validation Checklist

Run before tagging:

```bash
just check
uv run --extra dev python -m pytest -q
uv run --extra dev mkdocs build --strict
uv build
nix flake check --print-build-logs
```

Optional but recommended:

```bash
nix run nixpkgs#actionlint -- -color
nix run nixpkgs#gitleaks -- detect --source . --config .gitleaks.toml --verbose --exit-code 1
```

Hardware validation:

```bash
darwin-nic status
darwin-nic configure --profile homelab --preserve-wifi --dry-run
```

Record skipped hardware checks as release risks rather than silently treating
them as complete.

## Artifacts

The v2.1.0 release should publish:

- wheel and source distribution from `uv build`;
- GitHub Release notes and attached `dist/*` artifacts;
- MkDocs site through GitHub Pages;
- Nix package availability through the flake.

PyPI publication is desirable but can follow the GitHub Release if trusted
publisher setup is not ready.

## Risks

| Risk | Mitigation |
|------|------------|
| CLI sudo behavior differs over SSH or wrappers | Document `sudo -v` pre-authentication and manually validate on hardware |
| Docs leak downstream topology or credentials | Keep examples generic and enforce docs boundary tests |
| TOML schema drift breaks Home Manager consumers | Treat profile schema as release contract and cover it with settings tests |
| Nix output drift breaks downstream flakes | Keep `packages.${system}.darwin-nic` stable |
| Host policy blocks normal sockets despite healthy L2 | Keep NECP/Tailscale diagnostics visible in `status` |
| CI and local commands diverge | Keep workflows aligned with `just`/`uv` validation commands |
