{
  description = "Darwin Management NIC Configurator - USB NIC setup with WiFi preservation";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

    flake-utils.url = "github:numtide/flake-utils";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    system-manager = {
      url = "github:numtide/system-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    home-manager,
    system-manager,
  }:
    let
      # Outputs that are system-independent
      systemIndependent = {
        overlays.default = import ./nix/overlay.nix;

        homeModules = {
          darwin-nic = import ./nix/modules/home-manager.nix;
          network-tools = import ./nix/modules/home-manager-network-tools.nix;
          default = self.homeModules.darwin-nic;
        };

        # Alias for home-manager convention
        homeManagerModules = self.homeModules;

        systemManagerModules = {
          darwin-nic = import ./nix/modules/system-manager.nix;
          default = self.systemManagerModules.darwin-nic;
        };
      };

      # Per-system outputs
      perSystem = flake-utils.lib.eachDefaultSystem (system:
        let
          pkgs = import nixpkgs {
            inherit system;
            overlays = [ self.overlays.default ];
          };
        in
        {
          packages = {
            darwin-nic = pkgs.darwin-nic;
            default = pkgs.darwin-nic;

            net-utils = pkgs.callPackage ./nix/net-utils.nix { };

            net-utils-extended = pkgs.callPackage ./nix/net-utils.nix {
              enableExtended = true;
            };
          };

          devShells.default = pkgs.mkShell {
            inputsFrom = [ pkgs.darwin-nic ];

            packages = with pkgs; [
              # Python dev tools
              python3Packages.pytest
              python3Packages.pytest-cov
              python3Packages.pytest-mock
              python3Packages.pytest-html
              python3Packages.black
              ruff
              mypy

              # Nix tools
              nil # Nix LSP
              nixfmt-rfc-style

              # Task runner
              just

              # Docs
              python3Packages.mkdocs
              python3Packages.mkdocs-material
            ];

            shellHook = ''
              echo "darwin-nic dev shell"
              echo "  python: $(python3 --version)"
              echo "  just:   $(just --version)"
              echo ""
              echo "Run 'just' to see available commands."
            '';
          };

          # Flake checks: build the package + run tests
          checks = {
            inherit (pkgs) darwin-nic;
          };
        }
      );
    in
    systemIndependent // perSystem;
}
