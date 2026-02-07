# Darwin Management NIC Configurator

Configure USB network interfaces for out-of-band management access with controller WiFi preservation.

*do you regularly find yourself brazenly plugging random networky shit into random computers in the basement?  If the victim device is a mac, I am usually soon thereafter up a creek with borgled network configuration due to* ***various annoyances like abr (admin by request) sophos (so many, bleugh), paloalto (oof!), tailscale, nebula, random CNIs and other silly network things*** *running on the macs in my life.  if this sounds familiar, here we are*

## Usage

```bash
# Using just (dev)
just run setup
just run configure --device-ip <ipv4> --laptop-ip <ipv4> --preserve-wifi
just run status

# Using uv directly
uv run darwin-nic setup
uv run darwin-nic configure --device-ip <ipv4> --laptop-ip <ipv4> --preserve-wifi

# Using Nix (no clone needed)
nix run github:Jesssullivan/DarwinNicUtil -- setup
nix run github:Jesssullivan/DarwinNicUtil -- configure --device-ip <ipv4> --laptop-ip <ipv4>
```

## Install

```bash
# Nix (profile install)
nix profile install github:Jesssullivan/DarwinNicUtil

# Nix (flake reference in your config)
# inputs.darwin-nic.url = "github:Jesssullivan/DarwinNicUtil";

# uv from source
uv tool install .
```

**Home Manager** and **System Manager** modules are also available -- see `nix/modules/` or use `just hm-apply` / `just sm-apply`.


## Commands

| Command | Description |
|---------|-------------|
| `darwin-nic setup` | Interactive guided setup wizard |
| `darwin-nic configure` | Configure USB NIC via CLI |
| `darwin-nic status` | Show current network status |
| `darwin-nic dashboard` | Real-time monitoring dashboard |
| `darwin-nic test` | Test connectivity |
| `darwin-nic restore` | Restore backup configuration |
| `darwin-nic config` | Show current configuration and profiles |
| `darwin-nic profiles` | List available profiles |
| `darwin-nic init-config` | Initialize user config file |

### Configure Options

```bash
darwin-nic configure \
  --device-ip <ipv4> \      # Management device IP (required)
  --laptop-ip <ipv4> \      # Your USB NIC IP (required)
  --profile homelab \       # Use saved profile (optional)
  --preserve-wifi \         # Preserve WiFi connectivity
  --dry-run                 # Preview without changes
```

## Configuration

Save your network settings in a TOML config file to avoid typing IPs every time.

```bash
# Initialize config file
darwin-nic init-config

# View current settings and profiles
darwin-nic config

# List available profiles
darwin-nic profiles

# Use a saved profile
darwin-nic configure --profile homelab
```

### Config File Locations (in order of precedence)

| Location | Purpose |
|----------|---------|
| `/etc/darwin-nic/config.toml` | System-wide defaults |
| `~/.config/darwin-nic/config.toml` | User global settings |
| `./.darwin-nic.toml` | Project/directory local override |

### Example Config

```toml
# ~/.config/darwin-nic/config.toml
default_profile = "homelab"

[defaults]
preserve_wifi = true

[profiles.homelab]
device_ip = "192.168.88.1"
laptop_ip = "192.168.88.100"
mgmt_network = "192.168.10.0/24"
device_name = "Bastion Switch"

[profiles.datacenter]
device_ip = "10.200.0.1"
laptop_ip = "10.200.0.100"
mgmt_network = "10.200.0.0/24"
device_name = "DC Core Switch"
```

See `examples/config.toml` for a full example with all options.

## Requirements
- Python 3.13+ (3.14+ for native install, 3.13 via Nix)
- USB-to-Ethernet adapter
- macOS or Linux (yucky fruit OS or otherwise)

### Supported USB Adapters

Realtek, ASIX, Belkin, Apple USB Ethernet, StarTech, Cable Matters, TP-Link, and most generic USB LAN adapters.

## Safety Features
- **Protected Interfaces**: Never modifies en0 (WiFi), en1, or other critical interfaces
- **WiFi Preservation**: Automatically maintains internet connectivity when configuring USB NICs
- **USB Priority Prevention**: Prevents macOS from routing traffic through USB NIC
- **Dry-Run Mode**: Preview all changes before applying
- Emergency Recovery, os noes!
```bash
./scripts/emergency-restore.sh
```

## Helpful stuff

```bash
# Check if adapter is recognized
networksetup -listallhardwareports  # macOS
ip link show                        # Linux

# Run with verbose logging
darwin-nic configure --device-ip <ipv4> --laptop-ip <ipv4> --dry-run
```

## Development

All dev tasks are managed via [`just`](https://github.com/casey/just):

| Recipe | Description |
|--------|-------------|
| `just dev` | Sync development dependencies |
| `just run <args>` | Run darwin-nic in dev mode |
| `just test` | Run tests with coverage |
| `just lint` | Lint with ruff |
| `just format` | Format with black |
| `just type-check` | Type-check with mypy |
| `just ci` | Run all checks (format + lint + type-check + test) |
| `just build-nix` | Build with Nix |
| `just build-wheel` | Build Python wheel |
| `just nix-check` | Validate Nix flake |
| `just shell` | Enter Nix development shell |
| `just clean` | Remove build artifacts |

Run `just` with no arguments to see all available recipes.


## Future work:
- [ ] Integrate with Outbot Harness
- [ ] add publicly viewable mkdocs route
- [x] ~~add brew packaging and multiarch installers~~ (Nix flake packaging done, brew TBD)
- [ ] add multiarch binary installers
- [ ] add IPC friendly installer patterns
- [ ] add docs site, add IDE & llms.txt
- [ ] Add to tinyland darwin pkg artifactory 
- [ ] add desktop assets 
- [ ] integrate upx compression 
- [ ] Develop bridge module for multiple management connections and tunnels, ie. WAS-110 forwarding 
- [ ] Revise rich logging flow for better log state TUI management 
