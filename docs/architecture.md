# Architecture

## Overview

Darwin Management NIC Configurator uses a factory pattern for cross-platform USB detection with multiple safety layers.

```mermaid
graph TB
    subgraph Entry["Entry Points"]
        CLI[darwin-nic CLI]
        SETUP[Guided Setup TUI]
    end

    subgraph Core["Core Logic"]
        CONF[Configurator]
        FACTORY[USBNICDetectorFactory]
    end

    subgraph Platform["Platform Detectors"]
        MACOS[MacOSUSBNICDetector]
        LINUX[LinuxUSBNICDetector]
        WIN[WindowsUSBNICDetector]
    end

    subgraph Network["Network Management"]
        SVC[ServiceOrderManager]
        WIFI[WiFiMonitor]
        DASH[NetworkDashboard]
    end

    CLI --> CONF
    SETUP --> CONF
    CONF --> FACTORY
    FACTORY --> MACOS
    FACTORY --> LINUX
    FACTORY --> WIN
    CONF --> SVC
    CONF --> WIFI
    DASH --> SVC
    DASH --> WIFI
```

## Module Structure

```
src/darwin_mgmt_nic/
├── unified_entry.py    # Package entry point
├── cli.py              # CLI argument parsing
├── guided_setup.py     # Rich TUI wizard
├── config.py           # Configuration models
├── configurator.py     # Main orchestration
├── factory.py          # Platform factory
├── detectors.py        # Abstract base class
├── macos.py            # macOS implementation
├── linux.py            # Linux placeholder
└── network_manager.py  # Network utilities
```

## Data Flow

```mermaid
flowchart TD
    A[User Input] --> B[CLI/TUI Parser]
    B --> C[NetworkConfig]
    C --> D[Configurator]

    D --> E{Detect Platform}
    E -->|macOS| F[MacOSUSBNICDetector]
    E -->|Linux| G[LinuxUSBNICDetector]

    F --> H[Scan Interfaces]
    G --> H

    H --> I[Score & Rank]
    I --> J{Protected?}
    J -->|Yes| K[Skip Interface]
    J -->|No| L[Select Best USB NIC]

    L --> M[Configure Interface]
    M --> N[Preserve WiFi Priority]
    N --> O[Test Connectivity]
    O --> P[Success]
```

## Safety Architecture

### Protected Interfaces

Interfaces that are never modified:

```mermaid
graph LR
    subgraph Protected["Protected (Never Modified)"]
        EN0[en0 - WiFi]
        EN1[en1 - Ethernet]
        LO[lo0 - Loopback]
        AWDL[awdl0 - AirDrop]
    end

    subgraph Configurable["Configurable (USB NICs)"]
        EN5[en5+]
        USB[USB Ethernet]
    end

    style Protected fill:#ff6b6b,color:#fff
    style Configurable fill:#4ecdc4,color:#fff
```

### USB Detection Heuristics

```mermaid
flowchart TD
    A[Interface Found] --> B{In Protected Set?}
    B -->|Yes| C[Skip - Protected]
    B -->|No| D{Vendor Keyword Match?}

    D -->|Yes| E[Mark as USB]
    D -->|No| F{Interface Number >= 5?}

    F -->|Yes| G{Has Hardware Port?}
    F -->|No| H[Skip - Not USB]

    G -->|Yes| I[Mark as USB]
    G -->|No| H

    E --> J[Score Interface]
    I --> J

    J --> K{Active Link?}
    K -->|Yes| L[+50 Score]
    K -->|No| M[+0 Score]

    L --> N[Return Ranked List]
    M --> N
```

## Interface Scoring

USB interfaces are scored using 6 factors:

| Factor | Weight | Description |
|--------|--------|-------------|
| Active Link | +50 | Interface has carrier |
| Known Vendor | +30 | Realtek, ASIX, etc. |
| Interface Number | +10 | Higher en# preferred |
| Hardware Port | +10 | Valid port name |
| Not Protected | +100 | Must pass protection check |
| Cable Quality | +5 | USB 3.0 vs 2.0 |

## WiFi Preservation

```mermaid
sequenceDiagram
    participant C as Configurator
    participant S as ServiceOrderManager
    participant N as networksetup

    C->>S: prevent_usb_priority_takeover()
    S->>N: Get service order
    N-->>S: [USB, WiFi, VPN...]
    S->>S: Reorder: WiFi first, USB last
    S->>N: Set new order [WiFi, VPN..., USB]
    N-->>S: Success
    S-->>C: WiFi protected
```

## Configuration Models

```mermaid
classDiagram
    class NetworkConfig {
        +device_ip: str
        +laptop_ip: str
        +netmask: str
        +mgmt_network: str
        +device_name: str
        +validate_ips()
    }

    class NetworkInterface {
        +name: str
        +hardware_port: str
        +ip_address: str
        +mac_address: str
        +is_active: bool
        +is_usb: bool
        +is_protected: bool
    }

    class USBNICDetector {
        <<abstract>>
        +PROTECTED_INTERFACES: frozenset
        +detect_interfaces()*
        +is_protected_interface()
        +validate_interface_for_config()
    }

    class MacOSUSBNICDetector {
        +USB_VENDOR_KEYWORDS: tuple
        +detect_interfaces()
        -_parse_networksetup()
        -_is_usb_adapter()
    }

    USBNICDetector <|-- MacOSUSBNICDetector
    NetworkConfig --> NetworkInterface
```

## Platform Support

| Platform | Status | Detection Method |
|----------|--------|------------------|
| macOS | Complete | `networksetup -listallhardwareports` |
| Linux | Planned | `ip link`, `nmcli` |
| Windows | Planned | `netsh`, PowerShell |
