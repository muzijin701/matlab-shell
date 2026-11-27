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
  RELEASE_JSON="$TMP_DIR/release.json"
  echo "Fetching latest release metadata from $REPO..."
  curl -fsSL "$API_URL" -o "$RELEASE_JSON"

  ASSET_URL="$(grep -Eo "https://[^\"]+-${OS}-${ARCH}\.tar\.gz" "$RELEASE_JSON" | head -n 1 || true)"
  SUMS_URL="$(grep -Eo 'https://[^"]+/SHA256SUMS\.txt' "$RELEASE_JSON" | head -n 1 || true)"
  if [ -z "$ASSET_URL" ]; then
    echo "Error: Could not find a release asset for ${OS}-${ARCH} in $REPO." >&2
    exit 1
  fi
  if [ -z "$SUMS_URL" ]; then
    echo "Error: Could not find SHA256SUMS.txt in latest release of $REPO." >&2
    exit 1
  fi

  ARCHIVE_PATH="$TMP_DIR/matlab-shell.tar.gz"
  SUMS_PATH="$TMP_DIR/SHA256SUMS.txt"
  echo "Downloading $ASSET_URL..."
  curl -fsSL "$ASSET_URL" -o "$ARCHIVE_PATH"
  curl -fsSL "$SUMS_URL" -o "$SUMS_PATH"

  ASSET_NAME="${ASSET_URL##*/}"
  EXPECTED_HASH="$(awk -v target="$ASSET_NAME" '$2 == target || $2 == "*" target { print $1; exit }' "$SUMS_PATH" | tr '[:upper:]' '[:lower:]')"
  if [ -z "$EXPECTED_HASH" ]; then
    echo "Error: Checksum entry for '$ASSET_NAME' not found in SHA256SUMS.txt." >&2
    exit 1
  fi

  if command -v sha256sum >/dev/null 2>&1; then
    ACTUAL_HASH="$(sha256sum "$ARCHIVE_PATH" | awk '{print $1}' | tr '[:upper:]' '[:lower:]')"
  elif command -v shasum >/dev/null 2>&1; then
    ACTUAL_HASH="$(shasum -a 256 "$ARCHIVE_PATH" | awk '{print $1}' | tr '[:upper:]' '[:lower:]')"
  else
    echo "Error: Neither sha256sum nor shasum is available to verify archive checksum." >&2
    exit 1
  fi

  if [ "$ACTUAL_HASH" != "$EXPECTED_HASH" ]; then
    echo "Error: SHA256 verification failed for $ASSET_NAME (expected $EXPECTED_HASH, got $ACTUAL_HASH)." >&2
    exit 1
  fi
  echo "Verified SHA256 checksum."
fi

UNPACK_DIR="$TMP_DIR/unpacked"
mkdir -p "$UNPACK_DIR"
tar -xzf "$ARCHIVE_PATH" -C "$UNPACK_DIR"
if [ ! -f "$UNPACK_DIR/msh" ]; then
  echo "Error: Archive verification failed: msh executable not found." >&2
  exit 1
fi

if [ -e "$INSTALL_DIR" ]; then
  if [ ! -d "$INSTALL_DIR" ]; then
    echo "Error: Install path '$INSTALL_DIR' exists and is not a directory." >&2
    exit 1
  fi
  for entry in "$INSTALL_DIR"/* "$INSTALL_DIR"/.*; do
    [ -e "$entry" ] || [ -L "$entry" ] || continue
    base="$(basename "$entry")"
    case "$base" in
      .|..|msh|matlab-shell|_internal|.matlab-shell-install) ;;
      *)
        echo "Error: Refusing to overwrite non-empty directory '$INSTALL_DIR' containing unrelated entry '$base'. Use a dedicated subdirectory." >&2
        exit 1
        ;;
    esac
  done
  rm -rf "$INSTALL_DIR"
fi

mkdir -p "$INSTALL_DIR" "$BIN_DIR"
cp -R "$UNPACK_DIR"/. "$INSTALL_DIR"/
[ -f "$INSTALL_DIR/.matlab-shell-install" ] || printf '%s\n' "matlab-shell" > "$INSTALL_DIR/.matlab-shell-install"
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
