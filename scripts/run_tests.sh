#!/bin/bash
# Test runner for Darwin Management NIC Configurator
# Runs pytest with coverage

set -e

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║     Darwin Management NIC Configurator - Test Suite          ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Activate venv if it exists
if [ -d ".venv" ]; then
    echo "[*] Activating virtual environment..."
    source .venv/bin/activate
fi

# Install test dependencies
echo "[*] Installing test dependencies..."
uv pip install pytest pytest-cov pytest-mock pytest-html --quiet

# Install package in editable mode
echo "[*] Installing darwin-mgmt-nic in editable mode..."
uv pip install -e . --quiet

# Add src directory to PYTHONPATH as backup
export PYTHONPATH="$PWD/src:$PYTHONPATH"

# Run tests
echo ""
echo "[*] Running test suite..."
echo ""

pytest tests/ \
    --verbose \
    --cov=darwin_mgmt_nic \
    --cov-report=term-missing \
    --cov-report=html \
    --html=test-report.html \
    --self-contained-html \
    --tb=short

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║          Test Results                                         ║"
echo "╠═══════════════════════════════════════════════════════════════╣"
echo "║  Coverage Report: htmlcov/index.html                          ║"
echo "║  Test Report:     test-report.html                            ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
