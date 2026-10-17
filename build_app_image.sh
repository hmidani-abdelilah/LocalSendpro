#!/usr/bin/env bash
# Build a self-contained AppImage from the current Flet application.
set -euo pipefail

APP_ID=localsend-pro
APP_NAME="LocalSend Pro"
VERSION="${1:-$(sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml | head -n 1)}"
BUILD_ROOT=build/linux
APPDIR=AppDir
OUTPUT_DIR=dist/packages

command -v flet >/dev/null || {
    echo "flet is required. Install the project dependencies first: pip install -r requirements.txt" >&2
    exit 1
}
command -v wget >/dev/null || {
    echo "wget is required to download linuxdeploy." >&2
    exit 1
}

echo "Building $APP_NAME $VERSION for Linux..."
rm -rf "$BUILD_ROOT" "$APPDIR"
flet build linux --build-version="$VERSION"

APP_BIN="$(find "$BUILD_ROOT" -type f -perm -111 ! -path '*/lib/*' -print -quit)"
if [ -z "$APP_BIN" ]; then
    echo "Could not locate the executable produced by Flet in $BUILD_ROOT" >&2
    exit 1
fi
APP_ROOT="$(dirname "$APP_BIN")"
APP_BIN_NAME="$(basename "$APP_BIN")"

if [ ! -x linuxdeploy-x86_64.AppImage ]; then
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
Categories=Network;FileTransfer;Utility;
StartupNotify=true
EOF

export APPIMAGE_EXTRACT_AND_RUN=1
./linuxdeploy-x86_64.AppImage --appdir "$APPDIR" \
    --desktop-file "$DESKTOP_FILE" --output appimage

APPIMAGE_FILE="$(find . -maxdepth 1 -type f -name '*.AppImage' ! -name 'linuxdeploy-*.AppImage' -print -quit)"
if [ -z "$APPIMAGE_FILE" ]; then
    echo "linuxdeploy finished without producing an AppImage." >&2
    exit 1
fi
install -d "$OUTPUT_DIR"
cp "$APPIMAGE_FILE" "$OUTPUT_DIR/"
echo "AppImage build completed: $OUTPUT_DIR/$(basename "$APPIMAGE_FILE")"
