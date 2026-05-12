#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# Convenience wrapper: activate venv and run the CPU miner.
# If you have tmux installed, pass --tmux to run inside a detachable session:
#     ./run_cpu.sh --tmux
# ----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d venv ]; then
    echo "ERROR: venv not found. Run ./setup_cpu.sh first."
    exit 1
fi

if [ ! -f .env ]; then
    echo "ERROR: .env not found. Copy .env.example -> .env and set PRIVATE_KEY."
    exit 1
fi

# shellcheck disable=SC1091
source venv/bin/activate

if [ "${1:-}" = "--tmux" ]; then
    if ! command -v tmux >/dev/null 2>&1; then
        echo "ERROR: tmux not installed. Install with: sudo apt install -y tmux"
        exit 1
    fi
    SESSION=pfft-cpu
    if tmux has-session -t "$SESSION" 2>/dev/null; then
        echo "tmux session '$SESSION' already exists; attaching."
        exec tmux attach -t "$SESSION"
    fi
    echo "Starting miner in tmux session '$SESSION' (detach with Ctrl-b then d)"
    exec tmux new -s "$SESSION" "source venv/bin/activate && python3 pfft_miner.py"
fi

exec python3 pfft_miner.py
