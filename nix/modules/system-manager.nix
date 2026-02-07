{ config, lib, pkgs, ... }:

let
  cfg = config.services.darwin-nic;

  profileType = lib.types.submodule {
    options = {
      deviceIp = lib.mkOption {
        type = lib.types.str;
        description = "Management device IP address.";
      };
      laptopIp = lib.mkOption {
        type = lib.types.str;
        description = "Laptop USB NIC IP address.";
      };
      netmask = lib.mkOption {
        type = lib.types.str;
        default = "255.255.255.0";
        description = "Network mask.";
      };
      mgmtNetwork = lib.mkOption {
        type = lib.types.str;
        default = "198.51.100.0/24";
        description = "Management network CIDR.";
      };
      deviceName = lib.mkOption {
        type = lib.types.str;
        default = "Network Device";
        description = "Human-readable device name.";
      };
      description = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = "Profile description.";
      };
      deviceType = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = "Device type (e.g. mikrotik, cisco, juniper).";
      };
    };
  };

  profileToToml = name: profile:
    let
      base = {
        device_ip = profile.deviceIp;
        laptop_ip = profile.laptopIp;
        netmask = profile.netmask;
        mgmt_network = profile.mgmtNetwork;
        device_name = profile.deviceName;
      };
      withDesc = lib.optionalAttrs (profile.description != "") {
        description = profile.description;
      };
      withType = lib.optionalAttrs (profile.deviceType != "") {
        device_type = profile.deviceType;
      };
    in
    base // withDesc // withType;

  tomlConfig =
    let
      defaults = {
        preserve_wifi = true;
        dry_run = false;
      };
      profiles = lib.mapAttrs profileToToml cfg.profiles;
      base = {
        inherit defaults;
      } // lib.optionalAttrs (profiles != { }) {
        inherit profiles;
      };
      withDefault = lib.optionalAttrs (cfg.defaultProfile != null) {
        default_profile = cfg.defaultProfile;
      };
    in
    withDefault // base;

  tomlFormat = pkgs.formats.toml { };

  # udev rules for USB NIC hotplug auto-configuration
  # Matches common USB Ethernet chipsets: Realtek r8152, ASIX ax88179, CDC-ECM/NCM
  udevRules = pkgs.writeTextFile {
    name = "90-darwin-nic.rules";
    text = ''
      # Darwin Management NIC Configurator - USB NIC hotplug rules
      # Realtek RTL8152/RTL8153
      ACTION=="add", SUBSYSTEM=="net", DRIVERS=="r8152", TAG+="systemd", ENV{SYSTEMD_WANTS}="darwin-nic-autoconfig@%k.service"
      # ASIX AX88179
      ACTION=="add", SUBSYSTEM=="net", DRIVERS=="ax88179_178a", TAG+="systemd", ENV{SYSTEMD_WANTS}="darwin-nic-autoconfig@%k.service"
      # CDC Ethernet (generic USB Ethernet)
      ACTION=="add", SUBSYSTEM=="net", DRIVERS=="cdc_ether", TAG+="systemd", ENV{SYSTEMD_WANTS}="darwin-nic-autoconfig@%k.service"
      # CDC NCM
      ACTION=="add", SUBSYSTEM=="net", DRIVERS=="cdc_ncm", TAG+="systemd", ENV{SYSTEMD_WANTS}="darwin-nic-autoconfig@%k.service"
    '';
    destination = "/etc/udev/rules.d/90-darwin-nic.rules";
  };

in
{
  options.services.darwin-nic = {
    enable = lib.mkEnableOption "darwin-nic USB NIC configurator (system-wide)";

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.darwin-nic;
      defaultText = lib.literalExpression "pkgs.darwin-nic";
      description = "The darwin-nic package to install.";
    };

    autoDetect = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Enable USB NIC hotplug auto-configuration via udev rules.";
    };

    defaultProfile = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Profile to use for auto-configuration.";
    };

    allowedUsers = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = "Users allowed to run darwin-nic with elevated privileges via sudoers.";
      example = [ "jsullivan2" ];
    };

    profiles = lib.mkOption {
      type = lib.types.attrsOf profileType;
      default = { };
      description = "System-wide network configuration profiles.";
    };

    netUtils = {
      enable = lib.mkEnableOption "network diagnostic utilities (system-wide)";
    };

    monitor = {
      enable = lib.mkEnableOption "periodic NIC status monitoring service";

      interval = lib.mkOption {
        type = lib.types.str;
        default = "300";
        description = "Monitoring interval in seconds.";
      };
    };
  };

  config = lib.mkIf cfg.enable {
    # Install the package system-wide
    environment.systemPackages = [ cfg.package ]
      ++ lib.optionals cfg.netUtils.enable [
        (pkgs.callPackage ../net-utils.nix {
          enableExtended = true;
          enableLinuxGui = true;
        })
      ];

    # System-wide config file
    environment.etc."darwin-nic/config.toml" = lib.mkIf (cfg.profiles != { } || cfg.defaultProfile != null) {
      source = tomlFormat.generate "darwin-nic-system-config" tomlConfig;
    };

    # udev rules for USB NIC hotplug
    services.udev.packages = lib.mkIf cfg.autoDetect [ udevRules ];

    # Autoconfig service template (triggered by udev)
    systemd.services."darwin-nic-autoconfig@" = lib.mkIf cfg.autoDetect {
      description = "Darwin NIC auto-configure %i";
      after = [ "network-pre.target" ];

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${cfg.package}/bin/darwin-nic configure --profile ${
          if cfg.defaultProfile != null then cfg.defaultProfile else "default"
        }";
        ProtectSystem = "strict";
        ProtectHome = true;
        CapabilityBoundingSet = [ "CAP_NET_ADMIN" "CAP_NET_RAW" ];
        AmbientCapabilities = [ "CAP_NET_ADMIN" "CAP_NET_RAW" ];
        NoNewPrivileges = true;
        PrivateTmp = true;
      };
    };

    # Optional monitoring service
    systemd.services.darwin-nic-monitor = lib.mkIf cfg.monitor.enable {
      description = "Darwin NIC status monitor";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "simple";
        ExecStart = pkgs.writeShellScript "darwin-nic-monitor" ''
          while true; do
            ${cfg.package}/bin/darwin-nic status || true
            sleep ${cfg.monitor.interval}
          done
        '';
        Restart = "on-failure";
        RestartSec = 30;
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        CapabilityBoundingSet = [ "CAP_NET_ADMIN" "CAP_NET_RAW" ];
        AmbientCapabilities = [ "CAP_NET_ADMIN" "CAP_NET_RAW" ];
        NoNewPrivileges = true;
      };
    };

    # Sudoers fragment for allowed users
    security.sudo.extraRules = lib.mkIf (cfg.allowedUsers != [ ]) (
      map (user: {
        users = [ user ];
        commands = [
          {
            command = "${cfg.package}/bin/darwin-nic";
            options = [ "NOPASSWD" ];
          }
        ];
      }) cfg.allowedUsers
    );
  };
}
