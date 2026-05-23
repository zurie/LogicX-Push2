#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

echo "╔══════════════════════════════════════╗"
echo "║     LogicX-Push2 Installer           ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Add Homebrew to PATH (Apple Silicon and Intel)
if [[ -f /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -f /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
fi

# Install Homebrew if missing
if ! command -v brew &>/dev/null; then
    echo "► Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "✓ Homebrew: $(brew --version | head -1)"
fi

echo ""
echo "► Installing system dependencies..."
brew install python@3.12 pkg-config cairo pango gdk-pixbuf libusb

echo ""
echo "► Creating Python virtual environment..."
if [[ -f /opt/homebrew/opt/python@3.12/bin/python3.12 ]]; then
    PYTHON="/opt/homebrew/opt/python@3.12/bin/python3.12"
elif command -v python3.12 &>/dev/null; then
    PYTHON="$(command -v python3.12)"
else
    echo "ERROR: python3.12 not found."
    echo "Please run: brew install python@3.12"
    read -rp "Press Enter to close..."
    exit 1
fi

"$PYTHON" -m venv .venv
echo "✓ Virtual environment created"

echo ""
echo "► Installing Python packages..."
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -r requirements.txt

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     Installation complete!           ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "You can now close this Terminal window and launch Push2.app."
echo ""
read -rp "Press Enter to close..."
