#!/bin/bash
# Build script for creating UPX-packable binary

set -e

echo "[*] Building Darwin Management NIC Configurator binary..."

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "[!] Warning: Not in a virtual environment"
    echo "[i] Consider creating a venv: python -m venv build-env && source build-env/bin/activate"
fi

# Install build requirements
echo "[*] Installing build requirements..."
pip install -r build-requirements.txt

# Clean previous builds
echo "[*] Cleaning previous builds..."
rm -rf build/ dist/

# Build binary using PyInstaller
echo "[*] Building binary with PyInstaller..."
pyinstaller \
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

    echo ""
    echo "[OK] Build complete!"
    echo "[i] Binary location: dist/darwin-nic"
    echo "[i] To install system-wide: sudo cp dist/darwin-nic /usr/local/bin/"
    echo "[i] To compress with UPX: upx --best dist/darwin-nic"

else
    echo "[FAIL] Build failed!"
    exit 1
fi