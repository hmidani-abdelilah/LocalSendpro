#!/usr/bin/env bash
# Build the Debian package from debian/ and optionally convert it to RPM.
set -euo pipefail

PACKAGE=localsend-pro
OUTPUT_DIR="$PWD/dist/packages"

command -v dpkg-buildpackage >/dev/null || {
    echo "dpkg-buildpackage is required (install the dpkg-dev package)." >&2
    exit 1
}

echo "Building the Debian package for LocalSend Pro..."
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
dpkg-buildpackage -us -uc -b

DEB_FILE="$(find .. -maxdepth 1 -type f -name "${PACKAGE}_*.deb" -printf '%f\n' | sort | tail -n 1)"
if [ -z "$DEB_FILE" ]; then
    echo "The Debian build finished without producing a .deb file." >&2
    exit 1
fi
DEB_FILE="../$DEB_FILE"
cp "$DEB_FILE" "$OUTPUT_DIR/"
echo "Debian package: $OUTPUT_DIR/$(basename "$DEB_FILE")"

if command -v alien >/dev/null; then
    echo "Converting the Debian package to RPM..."
    alien --to-rpm "$DEB_FILE"
    RPM_FILE="$(find . -maxdepth 1 -type f -name "${PACKAGE}-*.rpm" -print -quit)"
    if [ -z "$RPM_FILE" ]; then
        echo "Alien completed without producing an RPM file." >&2
        exit 1
    fi
    cp "$RPM_FILE" "$OUTPUT_DIR/"
    echo "RPM package: $OUTPUT_DIR/$(basename "$RPM_FILE")"
    echo "RPM conversion completed."
else
    echo "RPM not created: install alien and run this script again to convert the .deb."
fi
