#!/usr/bin/env bash
# Build a local PyInstaller binary for smoke testing.

set -euo pipefail

echo "[*] Building Darwin Management NIC Configurator binary..."

# Clean previous builds
echo "[*] Cleaning previous builds..."
rm -rf build/ dist/

# Build binary using PyInstaller
echo "[*] Building binary with PyInstaller..."
uv run --with pyinstaller --with setuptools pyinstaller \
    --onefile \
    --name "darwin-nic" \
    --add-data "src:src" \
    --hidden-import "rich" \
    --hidden-import "typing_extensions" \
    --console \
    darwin-nic

# Check if build succeeded
if [[ -f "dist/darwin-nic" ]]; then
    echo "[OK] Binary built successfully: dist/darwin-nic"

    # Show binary info
    echo "[i] Binary information:"
    ls -lh dist/darwin-nic
    file dist/darwin-nic

    # Test binary
    echo "[*] Testing binary..."
    ./dist/darwin-nic --version

    # Test help
    echo "[*] Testing help..."
    ./dist/darwin-nic --help

    echo "[*] SHA256:"
    shasum -a 256 dist/darwin-nic

    echo ""
    echo "[OK] Build complete!"
    echo "[i] Binary location: dist/darwin-nic"
    echo "[i] This is a local smoke-test artifact, not a supported release binary."

else
    echo "[FAIL] Build failed!"
    exit 1
fi
