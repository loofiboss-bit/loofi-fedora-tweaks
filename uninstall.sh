#!/usr/bin/env bash
# Loofi Fedora Tweaks uninstaller

set -euo pipefail

fail() {
    echo "Error: $*" >&2
    exit 1
}

command -v pkexec >/dev/null 2>&1 || fail "pkexec is required; install polkit first."

if [[ -e /run/ostree-booted ]] && command -v rpm-ostree >/dev/null 2>&1; then
    echo "Removing Loofi Fedora Tweaks from the Atomic deployment"
    pkexec rpm-ostree uninstall loofi-fedora-tweaks
else
    DNF_BIN=""
    if command -v dnf5 >/dev/null 2>&1; then
        DNF_BIN="dnf5"
    elif command -v dnf >/dev/null 2>&1; then
        DNF_BIN="dnf"
    else
        fail "dnf5 or dnf is required."
    fi
    echo "Removing Loofi Fedora Tweaks"
    pkexec "${DNF_BIN}" remove -y loofi-fedora-tweaks
fi

read -r -p "Remove the project's COPR repository configuration too? [y/N] " reply
if [[ "${reply}" =~ ^[Yy]$ ]]; then
    # These are the two explicit repository names used by this project over
    # time. No wildcard is used so unrelated package sources are untouched.
    pkexec rm -f \
        /etc/yum.repos.d/loofi-fedora-tweaks.repo \
        /etc/yum.repos.d/_copr:copr.fedorainfracloud.org:loofitheboss:loofi-fedora-tweaks.repo
    echo "Repository configuration removed."
fi

echo "Uninstallation complete. User configuration and history were preserved."
