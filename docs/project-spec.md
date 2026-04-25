# Project Spec

DarwinNicUtil is a small operator tool for one recurring network-management
problem: a workstation needs a temporary USB Ethernet management link without
losing its normal Wi-Fi, VPN, or tailnet path.

The v2.1 productionization work turns the repo from a useful local script into
a release-ready package with documented boundaries, repeatable artifacts, and
CI-backed safety checks.

## Problem

USB management adapters are convenient for bench and bastion workflows, but
host network policy can make them confusing:

- a USB NIC can outrank Wi-Fi and disrupt the operator's primary path;
- route state can look correct while host-local policy still blocks ordinary
  sockets;
- link-layer tools can work while TCP clients fail;
- one-off shell fixes are hard to repeat safely across machines.

`darwin-nic` makes the host-side setup explicit and inspectable.

## Goals

- Detect and rank safe USB NIC candidates.
- Configure a static management address and route.
- Preserve Wi-Fi and tailnet reachability by default.
- Support profile-driven repeated use.
- Show dry-run and status output before privileged changes.
- Surface macOS bastion diagnostics for route state, `scutil --nwi`,
  Tailscale system-extension state, and recent NECP socket-drop hints.
- Keep downstream device policy out of this generic tool.

## Non-Goals

- Storing credentials.
- Running device-specific recovery commands.
- Encoding switch hostnames, MAC addresses, or topology.
- Replacing downstream operator runbooks.
- Promising standalone binaries before CI, checksums, and signing policy exist.

## Boundary Decisions

DarwinNicUtil can report generic host-side conditions that affect a USB
management NIC, but it should not become a compliance, endpoint-security, or
approval-bypass tool.

ABR-style approval keepalives and scripted approvers are out of scope for this
repo. If a site needs that behavior, it belongs in local operator automation or
a separate tool with its own security review. The generic contract here remains
normal interactive sudo for CLI use, TUI-safe sudo after pre-authentication, and
clear dry-run/status output before privileged changes.

Sophos, ZTNA, CryptoGuard, and similar endpoint-security products are also out
of scope as product-specific integrations. This repo may document generic
symptoms such as host-local socket policy blocking ordinary TCP while link-layer
tools still work. It should not ship adversarial compliance modules, product
workarounds, private policy, or host-specific rules.

## Operator Contract

The stable generic commands are:

```bash
darwin-nic status
darwin-nic configure --profile homelab --preserve-wifi
```

Profiles are TOML and intentionally portable:

```toml
default_profile = "homelab"

[defaults]
preserve_wifi = true

[profiles.homelab]
device_ip = "192.168.88.1"
laptop_ip = "192.168.88.100"
mgmt_network = "192.168.88.0/24"
device_name = "Lab Management Device"
device_type = "network"
```

The example values are documentation values for a generic management subnet.
Consumers own their own device names, secrets, and recovery policy.

## Release Surfaces

Current validated surfaces:

- PyPI distribution for `darwin-mgmt-nic-configurator`.
- GitHub Release with wheel and source distribution artifacts.
- Nix flake package outputs.
- FlakeHub release `v2.1.0` and rolling channel.
- MkDocs site published by GitHub Pages.

Staged or deferred surfaces:
- Standalone binaries are local smoke-test artifacts only until CI builds,
  tests, checksums, and signing/notarization policy exist.
- Homebrew is deferred until PyPI or standalone binary artifacts are proven.
- Bazel/Bzlmod is not a primary install path unless a real downstream consumer
  appears.

## Productionization Results

The post-v2.1 hardening pass added:

- GitHub Actions for Python checks, docs, Nix, release artifacts, and secret
  scanning.
- Gitleaks and TruffleHog CI surfaces.
- MkDocs pages for quickstart, bastion/OOB flow, architecture, artifacts, CLI,
  and development.
- Agent-facing docs in `AGENTS.md` and `docs/llms.txt`.
- FlakeHub publication workflow and documented release reference.
- PyPI trusted publishing and validated `2.1.1` upload.
- Explicit artifact policy for PyPI, binaries, Homebrew, and Bazel/BCR.
- Coverage gate ratcheted to 50 percent, with current coverage above 55
  percent.

## Next Work

- Draft a longer external blog post only if there is a maintained public venue.
- Add guided-setup behavior tests before the next coverage ratchet.
- Keep Sophos and ABR ideas as separate boundary spikes until they have a
  generic, non-secret, non-device-specific shape.
