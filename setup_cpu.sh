#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# PFFT CPU miner -- one-shot local setup script
#
# Works on Ubuntu/Debian, macOS (with Homebrew Python), and WSL2.
# Creates a venv in ./venv, installs CPU-only deps, and writes a .env from
# .env.example if you do not have one yet.
#
# Usage:
#   bash setup_cpu.sh
#   nano .env                # set PRIVATE_KEY
#   ./run_cpu.sh             # start the miner
# ----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> PFFT CPU miner setup"
echo "    dir: $SCRIPT_DIR"

# Detect python
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "ERROR: python3 not found. Install Python 3.10+ first."
    echo "  Ubuntu/Debian: sudo apt install -y python3 python3-venv python3-pip"
    echo "  macOS:         brew install python"
    exit 1
fi

PY_VER=$($PY -c 'import sys; print("{}.{}".format(sys.version_info[0], sys.version_info[1]))')
echo "    python: $PY ($PY_VER)"

# Create venv
if [ ! -d venv ]; then
    echo "==> Creating venv"
    $PY -m venv venv
else
    echo "==> venv already exists, reusing"
fi

# shellcheck disable=SC1091
source venv/bin/activate

echo "==> Upgrading pip / setuptools / wheel"
python -m pip install --upgrade pip setuptools wheel >/dev/null

echo "==> Installing CPU dependencies (web3 + pycryptodome)"
# We intentionally install ONLY CPU deps here. PyCUDA is optional and lives
# in requirements.txt for GPU users.
python -m pip install "web3>=6.0.0" "pycryptodome>=3.20.0"

# .env handling
if [ ! -f .env ]; then
    echo "==> Creating .env from .env.example"
    cp .env.example .env
    chmod 600 .env
    echo
    echo "    Edit .env now and set PRIVATE_KEY (and optionally ETH_RPC):"
    echo "      nano .env"
else
    echo "==> .env already exists, leaving it alone"
fi

# CPU info
CORES=$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo "?")
SUGGESTED=$((CORES > 1 ? CORES - 1 : 1))
echo
echo "==> Detected $CORES logical CPUs."
echo "    Suggested WORKERS in .env: $SUGGESTED"
echo
echo "Done. Next steps:"
echo "  1) Edit .env  (set PRIVATE_KEY)"
echo "  2) Start it:  ./run_cpu.sh   (or: source venv/bin/activate && python3 pfft_miner.py)"
