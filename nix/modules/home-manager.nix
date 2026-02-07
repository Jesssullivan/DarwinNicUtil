{ config, lib, pkgs, ... }:

let
  cfg = config.programs.darwin-nic;

  # Profile submodule type
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

  # Convert a Nix profile attrset to TOML-compatible snake_case attrset
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

  # Build the full TOML config structure
  tomlConfig =
    let
      defaults = {
        netmask = cfg.settings.netmask;
        preserve_wifi = cfg.settings.preserveWifi;
        dry_run = cfg.settings.dryRun;
        show_dashboard = cfg.settings.showDashboard;
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

in
{
  options.programs.darwin-nic = {
    enable = lib.mkEnableOption "darwin-nic USB NIC configurator";

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.darwin-nic;
      defaultText = lib.literalExpression "pkgs.darwin-nic";
      description = "The darwin-nic package to install.";
    };

    defaultProfile = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Default profile name to use when none is specified.";
    };

    settings = {
      netmask = lib.mkOption {
        type = lib.types.str;
        default = "255.255.255.0";
        description = "Default network mask.";
      };
      preserveWifi = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Preserve WiFi connectivity during configuration.";
      };
      dryRun = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Show what would be done without making changes.";
      };
      showDashboard = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Show network dashboard after configuration.";
      };
    };

    profiles = lib.mkOption {
      type = lib.types.attrsOf profileType;
      default = { };
      description = "Named network configuration profiles.";
      example = lib.literalExpression ''
        {
          homelab = {
            deviceIp = "192.168.88.1";
            laptopIp = "192.168.88.100";
            mgmtNetwork = "192.168.10.0/24";
            deviceName = "CRS309 Bastion";
            deviceType = "mikrotik";
          };
        }
      '';
    };

    networkTools = {
      enable = lib.mkEnableOption "companion network tools (nmap, tshark, mtr, etc.)";

      extras = lib.mkOption {
        type = lib.types.listOf lib.types.package;
        default = [ ];
        description = "Additional network tool packages to install.";
      };
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [ cfg.package ]
      ++ lib.optionals cfg.networkTools.enable [
        (pkgs.callPackage ../net-utils.nix { })
      ]
      ++ cfg.networkTools.extras;

    xdg.configFile."darwin-nic/config.toml" = lib.mkIf (cfg.profiles != { } || cfg.defaultProfile != null) {
      source = tomlFormat.generate "darwin-nic-config" tomlConfig;
    };
  };
}
