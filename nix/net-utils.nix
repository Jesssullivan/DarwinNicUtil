{
  lib,
  stdenv,
  symlinkJoin,
  # Core tools
  wireshark-cli,
  nmap,
  tcpdump,
  mtr,
  iperf3,
  socat,
  netcat-openbsd,
  # Extended tools
  bandwhich,
  trippy,
  termshark,
  doggo,
  aria2,
  ldns,
  # Linux-only
  wireshark ? null,
  ethtool ? null,
  # Options
  enableExtended ? false,
  enableLinuxGui ? stdenv.hostPlatform.isLinux,
}:

let
  coreTools = [
    wireshark-cli # tshark
    nmap
    tcpdump
    mtr
    iperf3
    socat
    netcat-openbsd
  ];

  extendedTools = lib.optionals enableExtended [
    bandwhich
    trippy
    termshark
    doggo
    aria2
    ldns # drill
  ];

  linuxGuiTools = lib.optionals (enableLinuxGui && stdenv.hostPlatform.isLinux) (
    lib.filter (p: p != null) [
      wireshark
      ethtool
    ]
  );

in
symlinkJoin {
  name = "darwin-nic-net-utils";
  paths = coreTools ++ extendedTools ++ linuxGuiTools;

  meta = {
    description = "Network utilities bundle for darwin-nic management workflows";
    license = lib.licenses.free;
    platforms = lib.platforms.unix;
  };
}
