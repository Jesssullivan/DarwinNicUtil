#!/bin/bash
# Emergency Network Restore Script
# Use this if the USB NIC configurator breaks your network

echo "[!!!] Emergency Network Restore - Fixing broken network configuration..."

# Restore Automatic location
echo "[*] Restoring Automatic location..."
networksetup -switchtolocation "Automatic"

# Ensure WiFi is enabled
echo "[*] Enabling WiFi..."
networksetup -setairportpower en0 on

# Set proper service order (WiFi first)
echo "[*] Restoring service order with WiFi priority..."
networksetup -ordernetworkservices "Wi-Fi" "USB Management" "Sophos ZTNA" "Sophos ZTNA 1"

# Clean up any USB interface configurations
echo "[*] Cleaning up USB interfaces..."
for iface in en7 en11 en5 en9; do
    if ifconfig $iface 2>/dev/null | grep -q "inet "; then
        echo "  Removing IP from $iface"
        sudo ifconfig $iface down 2>/dev/null || true
    fi
done

echo ""
echo "[OK] Network restore complete!"
echo ""
echo "[i] WiFi Status: $(networksetup -getairportpower en0)"
echo "[i] Service Order:"
networksetup -listnetworkserviceorder | head -10
echo ""
echo "[i] If WiFi still doesn't work, try restarting your Mac or running:"
echo "   sudo dscacheutil -flushcache"
echo "   sudo killall -HUP mDNSResponder"