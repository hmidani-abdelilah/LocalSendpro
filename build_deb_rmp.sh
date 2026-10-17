#!/usr/bin/env bash
# Build DEB and RPM packages on Debian/Ubuntu or Fedora.
set -euo pipefail

PACKAGE=localsend-pro
OUTPUT_DIR="$PWD/dist/packages"
BUILD_WITHOUT_DEB_CHECKS=false

usage() {
    cat <<'EOF'
Usage: ./build_deb_rmp.sh [--install-deps]

  --install-deps  Install the required Linux build packages with apt or dnf.
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
                alien build-essential debhelper dh-python dpkg-dev fakeroot \
                python3-all python3-pip python3-venv rpm rsync
            ;;
        fedora)
            require_sudo
            sudo dnf install --assumeyes \
                '@development-tools' alien debhelper dh-python dpkg dpkg-dev \
                fakeroot python3-devel python3-pip python3-virtualenv \
                rpm-build rsync
            ;;
        *)
            echo "Unsupported distribution: ${PRETTY_NAME:-unknown}. Install the build dependencies manually." >&2
            exit 1
            ;;
    esac
}

if [[ "${1:-}" == "--install-deps" ]]; then
    install_dependencies
    shift
fi
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi
if [[ $# -ne 0 ]]; then
    usage >&2
    exit 2
fi

# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}" in
    fedora)
        # Fedora packages are not registered in dpkg's package database.
        # The required commands are installed above, so only skip that check.
        BUILD_WITHOUT_DEB_CHECKS=true
        ;;
    debian|ubuntu|linuxmint|pop) ;;
    *)
        echo "Unsupported distribution: ${PRETTY_NAME:-unknown}." >&2
        exit 1
        ;;
esac

command -v dpkg-buildpackage >/dev/null || {
    echo "dpkg-buildpackage is required. Run: $0 --install-deps" >&2
    exit 1
}
command -v alien >/dev/null || {
    echo "alien is required. Run: $0 --install-deps" >&2
    exit 1
}

echo "Building the Debian package for LocalSend Pro..."
mkdir -p "$OUTPUT_DIR"
find "$OUTPUT_DIR" -maxdepth 1 -type f \( -name '*.deb' -o -name '*.rpm' \) -delete

BUILD_ARGS=(-us -uc -b)
if "$BUILD_WITHOUT_DEB_CHECKS"; then
    BUILD_ARGS+=(-d)
fi
dpkg-buildpackage "${BUILD_ARGS[@]}"

DEB_FILE="$(find .. -maxdepth 1 -type f -name "${PACKAGE}_*.deb" -printf '%f\n' | sort | tail -n 1)"
if [[ -z "$DEB_FILE" ]]; then
    echo "The Debian build finished without producing a .deb file." >&2
    exit 1
fi
DEB_FILE="$(realpath "../$DEB_FILE")"
cp "$DEB_FILE" "$OUTPUT_DIR/"
echo "Debian package: $OUTPUT_DIR/$(basename "$DEB_FILE")"

echo "Converting the Debian package to RPM..."
(
    cd "$OUTPUT_DIR"
    alien --to-rpm "$DEB_FILE"
)
RPM_FILE="$(find "$OUTPUT_DIR" -maxdepth 1 -type f -name "${PACKAGE}-*.rpm" -print -quit)"
if [[ -z "$RPM_FILE" ]]; then
    echo "Alien completed without producing an RPM file." >&2
    exit 1
fi
echo "RPM package: $RPM_FILE"
echo "RPM conversion completed."
