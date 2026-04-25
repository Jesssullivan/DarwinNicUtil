# Darwin Management NIC Configurator

Configure a USB Ethernet adapter for out-of-band management without letting it
take over normal Wi-Fi or tailnet connectivity.

`darwin-nic` is aimed at bastion and bench workflows where a Mac needs a
temporary management link to network gear while keeping its primary network
path intact.

## Status

- macOS is the primary supported platform.
- Linux support is experimental and currently limited.
- Release artifacts are PyPI distributions, GitHub Release wheel/source
  files, Nix packages, and FlakeHub releases.
- The PyInstaller spec is retained for manual builds, but standalone binaries
  are not the primary release artifact yet.
- Public docs are built with MkDocs and published at
  <https://transscendsurvival.org/DarwinNicUtil/>.

## Quick Start

```bash
# Recommended CLI install
uv tool install darwin-mgmt-nic-configurator
darwin-nic status
darwin-nic init-config
darwin-nic configure --profile homelab --preserve-wifi

# Run without installing, using the stable FlakeHub release
nix run "https://flakehub.com/f/Jesssullivan/DarwinNicUtil/v2.1.1" -- status
```

For a one-off setup without a saved profile:

```bash
darwin-nic configure \
  --device-ip <device-ipv4> \
  --laptop-ip <usb-nic-ipv4> \
  --mgmt-network <cidr> \
  --preserve-wifi
```

## Install

| Path | Use When | Command |
|------|----------|---------|
| PyPI | You want the normal CLI on your PATH | `uv tool install darwin-mgmt-nic-configurator` |
| FlakeHub | You want a stable Nix release | `nix profile install "https://flakehub.com/f/Jesssullivan/DarwinNicUtil/v2.1.1"` |
| GitHub flake | You want the current repository flake | `nix profile install github:Jesssullivan/DarwinNicUtil` |
| Source checkout | You are developing or testing local changes | `uv sync --extra dev && uv run darwin-nic status` |

Wheel and source distribution files are attached to GitHub Releases and
published to PyPI. Standalone binary downloads are not supported yet.

Home Manager and System Manager modules are available under `nix/modules/`.
For the release shape and productionization summary, see
[`docs/project-spec.md`](docs/project-spec.md).

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

- PyPI distribution for `darwin-mgmt-nic-configurator`;
- GitHub Release wheel and source distribution files;
- Nix flake package outputs, including FlakeHub `v2.1.1`;
- MkDocs site artifacts from the docs workflow.

GitHub Release, PyPI, FlakeHub, and docs workflows are present for tag-based
publication. Standalone binary distribution remains a tracked release follow-up.

Public artifact URLs:

- Docs: <https://transscendsurvival.org/DarwinNicUtil/>
- PyPI: <https://pypi.org/project/darwin-mgmt-nic-configurator/>
- Releases: <https://github.com/Jesssullivan/DarwinNicUtil/releases>
- FlakeHub: <https://flakehub.com/f/Jesssullivan/DarwinNicUtil>
