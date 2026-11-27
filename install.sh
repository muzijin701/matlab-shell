#!/usr/bin/env sh
set -eu

REPO="${MATLAB_SHELL_REPO:-muzijin701/matlab-shell}"
INSTALL_DIR="${MATLAB_SHELL_INSTALL_DIR:-$HOME/.local/share/matlab-shell/bin}"
BIN_DIR="${MATLAB_SHELL_BIN_DIR:-$HOME/.local/bin}"
LOCAL_ARCHIVE="${MATLAB_SHELL_ARCHIVE:-}"
NO_MODIFY_PATH="${MATLAB_SHELL_NO_MODIFY_PATH:-0}"

OS_RAW="$(uname -s)"
case "$OS_RAW" in
  Linux) OS="linux" ;;
  Darwin) OS="macos" ;;
  *)
    echo "Error: Unsupported OS '$OS_RAW'." >&2
    exit 1
    ;;
esac

ARCH_RAW="$(uname -m)"
case "$ARCH_RAW" in
  x86_64|amd64) ARCH="x86_64" ;;
  arm64|aarch64) ARCH="arm64" ;;
  *)
    echo "Error: Unsupported architecture '$ARCH_RAW'." >&2
    exit 1
    ;;
esac

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

if [ -n "$LOCAL_ARCHIVE" ]; then
  ARCHIVE_PATH="$LOCAL_ARCHIVE"
else
  API_URL="https://api.github.com/repos/$REPO/releases/latest"
  echo "Fetching latest release metadata from $REPO..."
  ASSET_URL="$(curl -fsSL "$API_URL" | grep -Eo "https://[^\"]+-${OS}-${ARCH}\.tar\.gz" | head -n 1 || true)"
  if [ -z "$ASSET_URL" ]; then
    echo "Error: Could not find a release asset for ${OS}-${ARCH} in $REPO." >&2
    exit 1
  fi
  ARCHIVE_PATH="$TMP_DIR/matlab-shell.tar.gz"
  echo "Downloading $ASSET_URL..."
  curl -fsSL "$ASSET_URL" -o "$ARCHIVE_PATH"
fi

rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR" "$BIN_DIR"
tar -xzf "$ARCHIVE_PATH" -C "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/msh" "$INSTALL_DIR/matlab-shell"

ln -sf "$INSTALL_DIR/msh" "$BIN_DIR/msh"
ln -sf "$INSTALL_DIR/matlab-shell" "$BIN_DIR/matlab-shell"

if [ "$NO_MODIFY_PATH" != "1" ]; then
  case ":${PATH}:" in
    *":${BIN_DIR}:"*) ;;
    *)
      echo "Note: Add '$BIN_DIR' to your PATH (e.g., export PATH=\"$BIN_DIR:\$PATH\")."
      ;;
  esac
fi

echo "Installed matlab-shell successfully! Run: $BIN_DIR/msh --version"
