#!/usr/bin/env bash
# Loofi Fedora Tweaks installer
#
# This helper configures the project's Fedora COPR repository and installs the
# RPM. It intentionally requires an explicit acknowledgement because running a
# remotely fetched shell script is less auditable than installing a published
# RPM directly.

set -euo pipefail

readonly COPR_PROJECT="loofitheboss/loofi-fedora-tweaks"
readonly PACKAGE="loofi-fedora-tweaks"
readonly ACK_FLAG="--i-know-what-i-am-doing"

fail() {
    echo "Error: $*" >&2
    exit 1
}

if [[ "${1:-}" != "${ACK_FLAG}" ]]; then
    cat >&2 <<EOF
This script changes the system package configuration and is intended for
reviewed local copies only.

Preferred installation:
  Enable the '${COPR_PROJECT}' COPR repository with your package manager,
  then install '${PACKAGE}' from the published RPM.

To continue with this script, run:
  bash install.sh ${ACK_FLAG}
EOF
    exit 1
fi

command -v pkexec >/dev/null 2>&1 || fail "pkexec is required; install polkit first."

if [[ -e /run/ostree-booted ]] && command -v rpm-ostree >/dev/null 2>&1; then
    fail "This helper targets mutable Fedora. On an Atomic host, install the published RPM with rpm-ostree and reboot when Fedora requests it."
fi

DNF_BIN=""
if command -v dnf5 >/dev/null 2>&1; then
    DNF_BIN="dnf5"
elif command -v dnf >/dev/null 2>&1; then
    DNF_BIN="dnf"
else
    fail "dnf5 or dnf is required."
fi

echo "Enabling Fedora COPR repository: ${COPR_PROJECT}"
if ! "${DNF_BIN}" copr --help >/dev/null 2>&1; then
    PLUGIN_PACKAGE="dnf-plugins-core"
    [[ "${DNF_BIN}" == "dnf5" ]] && PLUGIN_PACKAGE="dnf5-plugins"
    pkexec "${DNF_BIN}" install -y "${PLUGIN_PACKAGE}"
fi
pkexec "${DNF_BIN}" copr enable -y "${COPR_PROJECT}"

echo "Installing ${PACKAGE}"
pkexec "${DNF_BIN}" install -y --refresh "${PACKAGE}"

echo "Installation complete. Launch with: ${PACKAGE}"
