#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./install.sh [--install-root DIR] [--bin-dir DIR]

Defaults:
  install root: ~/.local/share/yunji-cli-vendor
  command dir:  ~/.local/bin
EOF
}

INSTALL_ROOT="$HOME/.local/share/yunji-cli-vendor"
BIN_DIR="$HOME/.local/bin"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --install-root) INSTALL_ROOT="${2:?missing value for --install-root}"; shift 2 ;;
    --bin-dir) BIN_DIR="${2:?missing value for --bin-dir}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
mkdir -p "$INSTALL_ROOT/scripts" "$BIN_DIR"
cp "$SCRIPT_DIR/README.md" "$INSTALL_ROOT/README.md"
cp "$SCRIPT_DIR/scripts/yunji" "$INSTALL_ROOT/scripts/yunji"
cp "$SCRIPT_DIR/scripts/yunji_vendor.py" "$INSTALL_ROOT/scripts/yunji_vendor.py"
chmod +x "$INSTALL_ROOT/scripts/yunji" "$INSTALL_ROOT/scripts/yunji_vendor.py"

TARGET="$BIN_DIR/yunji"
if [ -e "$TARGET" ] && [ ! -L "$TARGET" ]; then
  echo "refusing to overwrite non-symlink: $TARGET" >&2
  exit 1
fi
ln -sfn "$INSTALL_ROOT/scripts/yunji" "$TARGET"
"$TARGET" --help >/dev/null

cat <<EOF
yunji vendor CLI installed
  command: $TARGET
  root:    $INSTALL_ROOT

If "$BIN_DIR" is not in PATH, add it to your shell PATH.
EOF

