# Darwin Management NIC Configurator

Configure a USB Ethernet adapter for out-of-band management without letting it
take over normal Wi-Fi or tailnet connectivity.

`darwin-nic` is aimed at bastion and bench workflows where a Mac needs a
temporary management link to network gear while keeping its primary network
path intact.

## Status

- macOS is the primary supported platform.
- Linux support is experimental and currently limited.
- Release artifacts are source distributions, wheels, Nix packages, and
  FlakeHub releases.
- The PyInstaller spec is retained for manual builds, but standalone binaries
  are not the primary release artifact yet.

## Quick Start

```bash
# Run the stable v2.1.0 release from FlakeHub
nix run "https://flakehub.com/f/Jesssullivan/DarwinNicUtil/v2.1.0" -- status

# Or run directly from GitHub
nix run github:Jesssullivan/DarwinNicUtil -- status
nix run github:Jesssullivan/DarwinNicUtil -- configure \
  --device-ip <device-ipv4> \
  --laptop-ip <usb-nic-ipv4> \
  --mgmt-network <cidr> \
  --preserve-wifi

# Run from a source checkout
uv sync --extra dev
uv run darwin-nic status
uv run darwin-nic configure \
  --device-ip <device-ipv4> \
  --laptop-ip <usb-nic-ipv4> \
  --mgmt-network <cidr> \
  --preserve-wifi
```

For repeated use, create a profile:

```bash
darwin-nic init-config
darwin-nic config
darwin-nic configure --profile homelab --preserve-wifi
```

## Install

```bash
# Nix profile from FlakeHub
nix profile install "https://flakehub.com/f/Jesssullivan/DarwinNicUtil/v2.1.0"

# Nix profile from GitHub
nix profile install github:Jesssullivan/DarwinNicUtil

# uv from source
uv tool install .
```

Home Manager and System Manager modules are available under `nix/modules/`.

## Commands

| Command | Description |
|---------|-------------|
| `darwin-nic setup` | Interactive guided setup wizard |
| `darwin-nic configure` | Configure a USB NIC |
| `darwin-nic status` | Show interfaces, routes, and bastion diagnostics |
| `darwin-nic dashboard` | Show network monitoring status |
| `darwin-nic test` | Run basic connectivity checks |
| `darwin-nic restore` | Restore saved network service order |
| `darwin-nic config` | Show resolved settings and profiles |
| `darwin-nic profiles` | List available profiles |
| `darwin-nic init-config` | Create a starter config file |

## Configuration

Settings are loaded in this order, with later sources overriding earlier ones:

| Location | Purpose |
|----------|---------|
| `/etc/darwin-nic/config.toml` | System-wide defaults |
| `~/.config/darwin-nic/config.toml` | User defaults |
| `~/.darwin-nic.toml` | Legacy user config |
| `./.darwin-nic.toml` | Directory-local override |
| `./darwin-nic.toml` | Alternate directory-local override |
| `DARWIN_NIC_*` | Environment overrides |

Example:

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

See `examples/config.toml` for a fuller profile example.

## Bastion Notes

For a generic `tailnet -> bastion host -> USB OOB NIC -> managed network
device` flow:

- keep `mgmt_network` aligned with the real management subnet;
- use `darwin-nic status` before making privileged changes;
- use `--dry-run` to preview interface and route changes;
- pre-authenticate with `sudo -v` for non-interactive wrappers;
- check `status` when raw or link-layer tools work but ordinary sockets fail.

On macOS, `status` includes `scutil --nwi`, Tailscale system-extension state,
and recent NECP socket-drop hints when available.

Device-specific hostnames, credentials, OOB MAC addresses, and switch policy
belong in downstream operator repositories, not in this generic tool.

## Safety

- Protected interfaces such as Wi-Fi, loopback, and system virtual links are
  not modified.
- `--preserve-wifi` keeps the primary network path ahead of the USB NIC.
- Dry-run mode previews intended changes without applying them.
- The emergency restore helper is available at `scripts/emergency-restore.sh`.

## Requirements

- Python 3.14+ for source and uv installs.
- Nix for flake-based package usage.
- A USB-to-Ethernet adapter.
- macOS for the full current feature set.

## Development

```bash
just dev
just check
just test
just docs-build
uv build
```

Run `just` with no arguments to see all recipes.

## Artifacts

Current release artifacts are:

- Python wheel and source distribution from `uv build`;
- Nix flake package outputs, including FlakeHub `v2.1.0`;
- MkDocs site artifacts from the docs workflow.

GitHub release, FlakeHub, and docs workflows are present for tag-based
publication. The PyPI trusted-publishing workflow is staged but not documented
as an install path until the first upload is validated. Standalone binary
distribution remains a tracked release follow-up.
