# Darwin Management NIC Configurator

Configure USB network interfaces for out-of-band management access with automatic WiFi preservation.

## Features

- **Single Binary** - No Python environment required
- **WiFi Preservation** - Maintains internet connectivity during USB NIC setup
- **Hardware-Aware** - MacBook model detection and optimal port recommendations
- **Safety First** - Protected interfaces prevent accidental misconfiguration

## Quick Start

```bash
# Interactive setup (recommended)
./darwin-nic setup

# CLI configuration
./darwin-nic configure --device-ip 192.0.2.1 --laptop-ip 192.0.2.100 --preserve-wifi
```

## How It Works

```mermaid
flowchart LR
    A[USB NIC Plugged In] --> B{Detect Interface}
    B --> C[Score & Rank NICs]
    C --> D[Configure Selected NIC]
    D --> E[Preserve WiFi Priority]
    E --> F[Test Connectivity]
```

## Use Cases

| Scenario | Command |
|----------|---------|
| First-time setup | `darwin-nic setup` |
| Use saved profile | `darwin-nic configure --profile homelab` |
| Quick configure | `darwin-nic configure --device-ip 192.0.2.1 --laptop-ip 192.0.2.100` |
| View config | `darwin-nic config` |
| Check status | `darwin-nic status` |
| Monitor network | `darwin-nic dashboard` |

## Requirements

- macOS (Darwin) - Linux support planned
- Python 3.14+
- USB-to-Ethernet adapter

## Supported Adapters

Realtek, ASIX, Belkin, Apple USB Ethernet, StarTech, Cable Matters, TP-Link, and generic USB LAN adapters.

## License

zlib License - Copyright (c) 2024-2025 Contributors
