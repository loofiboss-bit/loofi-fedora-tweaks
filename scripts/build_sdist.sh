#!/bin/bash
# Source distribution build script for Loofi Fedora Tweaks

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSION_FILE="${ROOT_DIR}/loofi-fedora-tweaks/version.py"
DIST_DIR="${ROOT_DIR}/dist"

require_python_build() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required" >&2
    exit 1
  fi

  if ! python3 -c "import build" >/dev/null 2>&1; then
    echo "Error: Python module 'build' is required (pip install build)" >&2
    exit 1
  fi
}

extract_version() {
  local version
  version="$(sed -nE 's/^__version__ = "([^"]+)"/\1/p' "${VERSION_FILE}" | head -n 1)"
  version="$(printf '%s' "${version}" | tr -d '\r\n')"
  if [[ -z "${version}" ]]; then
    echo "Error: Failed to parse version from ${VERSION_FILE}" >&2
    exit 1
  fi
  printf '%s' "${version}"
}

main() {
  require_python_build

  local version
  version="$(extract_version)"

  # setuptools may reuse an ignored, stale SOURCES.txt from an earlier
  # checkout and then fail while archiving files that no longer exist.
  # This directory is generated metadata, never a source-of-truth input.
  local egg_info_dir="${ROOT_DIR}/loofi-fedora-tweaks/loofi_fedora_tweaks.egg-info"
  if [[ -d "${egg_info_dir}" ]]; then
    rm -rf -- "${egg_info_dir}"
  fi

  mkdir -p "${DIST_DIR}"
  rm -f "${DIST_DIR}/loofi_fedora_tweaks-${version}.tar.gz"

  cd "${ROOT_DIR}"
  python3 -m build --sdist --outdir dist

  local tarball="${DIST_DIR}/loofi_fedora_tweaks-${version}.tar.gz"
  if [[ ! -f "${tarball}" ]]; then
    echo "Error: Expected sdist not found: ${tarball}" >&2
    exit 1
  fi

  echo "Source distribution created: ${tarball}"
}

main "$@"
