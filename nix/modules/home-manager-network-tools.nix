{ config, lib, pkgs, ... }:

let
  cfg = config.programs.network-tools;
in
{
  options.programs.network-tools = {
    enable = lib.mkEnableOption "core network diagnostic tools (nmap, tshark, mtr, etc.)";

    enableExtended = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Also install extended tools (bandwhich, trippy, termshark, doggo, aria2, drill).";
    };

    extras = lib.mkOption {
      type = lib.types.listOf lib.types.package;
      default = [ ];
      description = "Additional packages to include in the network tools bundle.";
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [
      (pkgs.callPackage ../net-utils.nix {
        enableExtended = cfg.enableExtended;
      })
    ] ++ cfg.extras;
  };
}
