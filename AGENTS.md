# DarwinNicUtil Agent Guide

This repo owns the generic `darwin-nic` USB management NIC tool.

## Boundaries

- Owns macOS/Linux USB NIC detection, configuration, sudo behavior, routing behavior, and diagnostics.
- Does not own Tinyland switch topology. `crs310-8g-2s-in` owns CRS hostnames, RouterOS policy, OOB MAC addresses, switch credentials, and Tinyland-specific bastion runbooks.
- Do not embed switch secrets, SOPS paths, or Tinyland-specific RouterOS policy in this repo.
- Use the `github` remote for GitHub PR work. Local `origin` may be a non-bare `yoga` checkout.

## Bastion Mode

For `tailnet -> bastion host -> USB OOB NIC -> network gear` workflows, provide:

- profile-driven USB NIC setup with Wi-Fi preservation;
- clear dry-run/status output before privileged changes;
- normal interactive sudo in non-TUI CLI mode;
- TUI-safe sudo only after pre-authentication;
- diagnostics for `scutil --nwi`, active Tailscale system extension state, and recent macOS `reason: NECP` socket drops.

Tinyland CRS309-specific commands belong in `crs310-8g-2s-in`; the generic operator action here is:

```bash
darwin-nic status
darwin-nic configure --profile homelab --preserve-wifi
```

## Agent and MCP Surface

This repo intentionally does not ship a `.mcp.json` today. The maintained
agent-facing surfaces are:

- `AGENTS.md` for repo boundaries, validation, and operator constraints;
- `docs/llms.txt` for compact model-facing documentation context.

Add a repo-local MCP config only when DarwinNicUtil owns a stable, generic MCP
integration. Do not encode sibling-repo control-plane details here.

## Validation

Run the full Python test suite after changing runtime behavior or docs that are covered by tests:

```bash
uv run --extra dev python -m pytest -q
```

For publishable changes, also check formatting/lint/type surfaces when the local toolchain is available:

```bash
just check
```
