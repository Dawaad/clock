#!/bin/sh
# clock installer — downloads the standalone binary for your platform.
#
#   curl -fsSL https://raw.githubusercontent.com/Dawaad/clock/main/install.sh | sh
#
# Environment overrides:
#   CLOCK_VERSION       release tag to install (default: latest)
#   CLOCK_INSTALL_DIR   target directory (default: $HOME/.local/bin)
set -eu

REPO="Dawaad/clock"
INSTALL_DIR="${CLOCK_INSTALL_DIR:-$HOME/.local/bin}"

err() {
	echo "clock-install: $*" >&2
	exit 1
}

os="$(uname -s)"
case "$os" in
	Linux) os="linux" ;;
	Darwin) os="darwin" ;;
	*) err "unsupported OS: $os (only Linux and macOS have prebuilt binaries)" ;;
esac

arch="$(uname -m)"
case "$arch" in
	x86_64 | amd64) arch="x86_64" ;;
	arm64 | aarch64) arch="arm64" ;;
	*) err "unsupported architecture: $arch" ;;
esac

asset="clock-${os}-${arch}"

if [ -n "${CLOCK_VERSION:-}" ]; then
	url="https://github.com/${REPO}/releases/download/${CLOCK_VERSION}/${asset}"
else
	url="https://github.com/${REPO}/releases/latest/download/${asset}"
fi

command -v curl >/dev/null 2>&1 || err "curl is required"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

echo "Downloading ${asset}..."
if ! curl -fSL --progress-bar "$url" -o "$tmp"; then
	err "download failed: $url (no release asset for this platform?)"
fi

mkdir -p "$INSTALL_DIR"
target="${INSTALL_DIR}/clock"
mv "$tmp" "$target"
chmod +x "$target"
trap - EXIT

echo "Installed clock to ${target}"

case ":${PATH}:" in
	*":${INSTALL_DIR}:"*) ;;
	*)
		echo
		echo "NOTE: ${INSTALL_DIR} is not on your PATH. Add this to your shell profile:"
		echo "    export PATH=\"${INSTALL_DIR}:\$PATH\""
		;;
esac

echo "Run 'clock 5m' to start a 5-minute timer, or 'clock' to pick interactively."
