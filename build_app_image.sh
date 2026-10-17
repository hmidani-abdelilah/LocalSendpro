#!/usr/bin/env bash
# Build a self-contained AppImage on Debian/Ubuntu or Fedora.
set -euo pipefail

APP_ID=localsend-pro
APP_NAME="LocalSend Pro"
BUILD_ROOT=build/linux
APPDIR=AppDir
OUTPUT_DIR=dist/packages

# pip --user installs command-line tools here on both Debian-based systems and
# Fedora. Keep it available when --install-deps installs flet-cli.
export PATH="$HOME/.local/bin:$PATH"

usage() {
    cat <<'EOF'
Usage: ./build_app_image.sh [--install-deps] [VERSION]

  --install-deps  Install the required Linux build packages with apt or dnf.
  VERSION         Optional version; defaults to pyproject.toml.
EOF
}

require_sudo() {
    command -v sudo >/dev/null || {
        echo "sudo is required when using --install-deps." >&2
        exit 1
    }
}

install_dependencies() {
    # shellcheck disable=SC1091
    . /etc/os-release
    case "${ID:-}" in
        debian|ubuntu|linuxmint|pop)
            require_sudo
            sudo apt-get update
            sudo apt-get install --yes \
                libgtk-3-dev ninja-build wget pkg-config python3-pip \
                libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
                gstreamer1.0-plugins-good
            ;;
        fedora)
            require_sudo
            sudo dnf install --assumeyes \
                gtk3-devel ninja-build wget pkgconf-pkg-config python3-pip \
                gstreamer1-devel gstreamer1-plugins-base-devel \
                gstreamer1-plugins-good
            ;;
        *)
            echo "Unsupported distribution: ${PRETTY_NAME:-unknown}. Install the build dependencies manually." >&2
            exit 1
            ;;
    esac

    python3 -m pip install --user --upgrade flet-cli
}

INSTALL_DEPS=false
if [[ "${1:-}" == "--install-deps" ]]; then
    INSTALL_DEPS=true
    shift
fi
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi
if [[ $# -gt 1 ]]; then
    usage >&2
    exit 2
fi

VERSION="${1:-$(sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml | head -n 1)}"
if [[ -z "$VERSION" ]]; then
    echo "Could not determine the application version from pyproject.toml." >&2
    exit 1
fi

if "$INSTALL_DEPS"; then
    install_dependencies
fi

command -v flet >/dev/null || {
    echo "flet is required. Run: $0 --install-deps" >&2
    exit 1
}
command -v wget >/dev/null || {
    echo "wget is required. Run: $0 --install-deps" >&2
    exit 1
}
command -v pkg-config >/dev/null || {
    echo "pkg-config is required. Run: $0 --install-deps" >&2
    exit 1
}
pkg-config --exists gstreamer-1.0 || {
    echo "GStreamer development files are required. Run: $0 --install-deps" >&2
    exit 1
}

echo "Building $APP_NAME $VERSION for Linux..."
rm -rf "$BUILD_ROOT" "$APPDIR"
install -d "$OUTPUT_DIR"
find "$OUTPUT_DIR" -maxdepth 1 -type f -name '*.AppImage' -delete
find . -maxdepth 1 -type f -name '*.AppImage' ! -name 'linuxdeploy-*.AppImage' -delete
flet build linux --yes --no-rich-output --build-version="$VERSION"

APP_BIN="$(find "$BUILD_ROOT" -type f -perm -111 ! -path '*/lib/*' -print -quit)"
if [[ -z "$APP_BIN" ]]; then
    echo "Could not locate the executable produced by Flet in $BUILD_ROOT." >&2
    exit 1
fi
APP_ROOT="$(dirname "$APP_BIN")"
APP_BIN_NAME="$(basename "$APP_BIN")"

if [[ ! -x linuxdeploy-x86_64.AppImage ]]; then
    wget -O linuxdeploy-x86_64.AppImage \
        https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
    chmod 755 linuxdeploy-x86_64.AppImage
fi

install -d "$APPDIR/usr/bin" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$APP_ROOT"/. "$APPDIR/usr/bin/"
ln -sf "$APP_BIN_NAME" "$APPDIR/usr/bin/$APP_ID"
install -m 644 assets/icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_ID.png"
install -m 644 assets/icon.png "$APPDIR/$APP_ID.png"
ln -sf "$APP_ID.png" "$APPDIR/.DirIcon"

DESKTOP_FILE="$APPDIR/com.localsend.pro.desktop"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$APP_NAME
Comment=Securely share files and messages on your local network
Exec=$APP_ID
Icon=$APP_ID
Terminal=false
Categories=Network;FileTransfer;
StartupNotify=true
EOF

export APPIMAGE_EXTRACT_AND_RUN=1
./linuxdeploy-x86_64.AppImage --appdir "$APPDIR" \
    --desktop-file "$DESKTOP_FILE" --output appimage

APPIMAGE_FILE="$(find . -maxdepth 1 -type f -name '*.AppImage' ! -name 'linuxdeploy-*.AppImage' -print -quit)"
if [[ -z "$APPIMAGE_FILE" ]]; then
    echo "linuxdeploy finished without producing an AppImage." >&2
    exit 1
fi
cp "$APPIMAGE_FILE" "$OUTPUT_DIR/"
echo "AppImage build completed: $OUTPUT_DIR/$(basename "$APPIMAGE_FILE")"
