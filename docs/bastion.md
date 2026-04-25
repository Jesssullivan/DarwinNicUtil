# Bastion / OOB Operator Flow

`darwin-nic` supports the generic host-side part of a bastion path:

```text
tailnet -> bastion host -> USB OOB NIC -> managed network device
```

The tool configures the USB management NIC, keeps Wi-Fi or tailnet connectivity
from being displaced, and surfaces host-local diagnostics when ordinary sockets
behave differently from link-layer tools.

## Profile Contract

Use a profile for repeatable operator flows:

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
description = "USB OOB management path"
```

Run:

```bash
darwin-nic status
darwin-nic configure --profile homelab --preserve-wifi
```

The profile schema is intentionally generic. Device-specific hostnames,
credentials, MAC addresses, and switch policy belong in the consuming operator
runbook, not in DarwinNicUtil.

## Sudo Contract

Non-TUI CLI mode uses the normal interactive sudo path. For automation, pre-authenticate first:

```bash
sudo -v
darwin-nic configure --profile homelab --preserve-wifi
```

TUI-guided setup should only use privileged operations after pre-authentication
or through an explicit operator prompt.

## Status Diagnostics

`darwin-nic status` reports the normal network dashboard and, when USB OOB state
is present, bastion diagnostics:

- USB interfaces with assigned management IPs;
- interfaces visible to `scutil --nwi`;
- USB interfaces missing from `scutil --nwi`;
- whether the Tailscale system extension appears active;
- whether recent macOS unified logs include outbound socket drops with `reason: NECP`.

These diagnostics are meant to separate host-local policy issues from device or
cabling issues. If link-layer tools work but TCP sockets fail with `No route to
host`, check the `scutil --nwi` and NECP lines before re-debugging the managed
device.

## Boundaries

DarwinNicUtil owns:

- USB NIC detection and configuration;
- Wi-Fi preservation and route/service-order safety;
- dry-run/status output;
- host-side bastion diagnostics.

Consuming runbooks own:

- target device identity;
- credentials and secret loading;
- device-specific recovery commands;
- topology-specific access tiers.
