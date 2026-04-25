# Darwin Management NIC Configurator

`darwin-nic` configures a USB Ethernet adapter for out-of-band management while
preserving the host's normal Wi-Fi and tailnet path.

## What It Owns

- USB NIC detection and ranking.
- Static USB management addressing.
- Wi-Fi/service-order preservation.
- Dry-run and status output before privileged changes.
- Bastion diagnostics for route state, `scutil --nwi`, Tailscale extension
  state, and recent macOS NECP socket drops.

Device-specific topology, credentials, switch commands, and recovery policy
belong in downstream operator repositories.

For the public release shape and productionization summary, see the
[project spec](project-spec.md).

Public artifact URLs:

- Docs: <https://transscendsurvival.org/DarwinNicUtil/>
- PyPI: <https://pypi.org/project/darwin-mgmt-nic-configurator/>
- GitHub Releases: <https://github.com/Jesssullivan/DarwinNicUtil/releases>
- FlakeHub: <https://flakehub.com/f/Jesssullivan/DarwinNicUtil>

## Quick Start

```bash
# Recommended CLI install
uv tool install darwin-mgmt-nic-configurator
darwin-nic status

# Stable release from FlakeHub
nix run "https://flakehub.com/f/Jesssullivan/DarwinNicUtil/v2.1.2" -- status
```

## Install Path Matrix

| Path | Best For | Command |
|------|----------|---------|
| PyPI | Normal CLI install | `uv tool install darwin-mgmt-nic-configurator` |
| FlakeHub | Stable Nix install or one-shot run | `nix run "https://flakehub.com/f/Jesssullivan/DarwinNicUtil/v2.1.2" -- status` |
| GitHub flake | Current repository state | `nix run github:Jesssullivan/DarwinNicUtil -- status` |
| Source checkout | Development and local validation | `uv sync --extra dev && uv run darwin-nic status` |

From a checkout:

```bash
uv sync --extra dev
uv run darwin-nic setup
uv run darwin-nic status
```

## Workflow

```mermaid
flowchart LR
    A[USB NIC plugged in] --> B[Detect safe candidate]
    B --> C[Apply profile or CLI IPs]
    C --> D[Preserve Wi-Fi priority]
    D --> E[Add management route]
    E --> F[Report status and diagnostics]
```

## Main Commands

| Scenario | Command |
|----------|---------|
| Guided setup | `darwin-nic setup` |
| Profile-based setup | `darwin-nic configure --profile homelab --preserve-wifi` |
| One-off setup | `darwin-nic configure --device-ip 192.168.88.1 --laptop-ip 192.168.88.100 --mgmt-network 192.168.88.0/24` |
| Inspect state | `darwin-nic status` |
| List profiles | `darwin-nic profiles` |

## Platform Status

| Platform | Status |
|----------|--------|
| macOS | Primary supported platform |
| Linux | Experimental placeholder support |

## Artifacts

The release path supports PyPI distributions, GitHub Release wheel/source
files, Nix packages, FlakeHub releases, and MkDocs site artifacts. Standalone
binary publication remains a tracked follow-up.
