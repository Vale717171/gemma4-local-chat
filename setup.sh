#!/bin/bash
set -e

echo "=== Gemma 4 Local Chat — Setup ==="
echo ""

# Check Apple Silicon
ARCH=$(uname -m)
if [ "$ARCH" != "arm64" ]; then
  echo "Error: this app requires Apple Silicon (M1/M2/M3/M4)."
  exit 1
fi

# Check Python 3.10+
PYTHON=$(which python3.12 || which python3.11 || which python3.10 || echo "")
if [ -z "$PYTHON" ]; then
  echo "Python 3.10+ not found. Install it with:"
  echo "  brew install python@3.12"
  exit 1
fi

echo "Using Python: $PYTHON"

# Create venv
VENV="$HOME/mlx-env"
if [ ! -d "$VENV" ]; then
  echo "Creating virtual environment..."
  "$PYTHON" -m venv "$VENV"
fi

source "$VENV/bin/activate"

echo "Installing dependencies (this may take a few minutes)..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo ""
echo "Creating desktop shortcut..."
SHORTCUT="$HOME/Desktop/Gemma Chat.command"
PROJECT_DIR="$(pwd)"
cat > "$SHORTCUT" <<EOF
#!/bin/bash
export GEMMA_CHAT_DIR="$PROJECT_DIR"
"$PROJECT_DIR/launch.command"
EOF
chmod +x "$SHORTCUT"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Double-click 'Gemma Chat' on your Desktop to start."
echo "The first launch will download the model (~5 GB)."
