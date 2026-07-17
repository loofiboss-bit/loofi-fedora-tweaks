#!/bin/bash
# Build an SRPM suitable for Fedora COPR submission.
# Usage: bash scripts/build_srpm.sh
#
# The SRPM is written to rpmbuild/SRPMS/ and can be uploaded to COPR.
# Source bytes always come from the verified checkout commit, never from a
# mutable release-tag archive or from uncommitted working-tree content.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$ROOT_DIR"

# Container jobs can mount the checkout with a host UID that differs from the
# container user. Scope Git's ownership exception to this resolved repository
# only, rather than mutating global Git configuration in the runner.
git_repo() {
  command git -c "safe.directory=${ROOT_DIR}" "$@"
}

# A Git commit is the source-of-truth.  In GitHub Actions, GITHUB_SHA binds the
# archive to the exact commit which passed the preceding release gates.
if ! command -v git >/dev/null 2>&1; then
  echo "Error: git is required to build a commit-bound SRPM" >&2
  exit 1
fi
if ! git_repo rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: SRPM source must be built from a Git checkout" >&2
  exit 1
fi

HEAD_SHA="$(git_repo rev-parse --verify 'HEAD^{commit}')"
EXPECTED_SHA="${EXPECTED_SOURCE_SHA:-${GITHUB_SHA:-}}"
if [[ -n "$EXPECTED_SHA" ]]; then
  EXPECTED_SHA_INPUT="$EXPECTED_SHA"
  if ! EXPECTED_SHA="$(git_repo rev-parse --verify "${EXPECTED_SHA}^{commit}" 2>/dev/null)"; then
    echo "Error: expected source commit is not available: ${EXPECTED_SHA_INPUT}" >&2
    exit 1
  fi
  if [[ "$HEAD_SHA" != "$EXPECTED_SHA" ]]; then
    echo "Error: checkout HEAD ${HEAD_SHA} does not match expected source commit ${EXPECTED_SHA}" >&2
    exit 1
  fi
fi
echo "Verified source commit: ${HEAD_SHA}"

VERSION="$(
  git_repo show "${HEAD_SHA}:loofi-fedora-tweaks/version.py" |
    python3 -c "import sys; values = {}; exec(sys.stdin.read(), values); print(values['__version__'])"
)"
if [[ -z "$VERSION" ]]; then
  echo "Error: failed to parse version from commit ${HEAD_SHA}" >&2
  exit 1
fi
echo "Building SRPM for loofi-fedora-tweaks v${VERSION}"

# Setup an isolated rpmbuild tree.  A caller-provided directory is supported
# for deterministic tests; normal builds use a unique temporary directory.
if [[ -n "${SRPM_BUILD_DIR:-}" ]]; then
  BUILD_DIR="$SRPM_BUILD_DIR"
  mkdir -p "$BUILD_DIR"
  CLEAN_BUILD_DIR=0
else
  BUILD_DIR="$(mktemp -d -t loofi-fedora-tweaks-srpm.XXXXXXXX)"
  CLEAN_BUILD_DIR=1
fi
cleanup() {
  if [[ "$CLEAN_BUILD_DIR" -eq 1 ]]; then
    rm -rf -- "$BUILD_DIR"
  fi
}
trap cleanup EXIT
mkdir -p "$BUILD_DIR"/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

SOURCE_TARBALL="$BUILD_DIR/rpmbuild/SOURCES/loofi-fedora-tweaks-${VERSION}.tar.gz"
echo "Archiving verified checkout commit ${HEAD_SHA}"
git_repo archive \
  --format=tar.gz \
  --prefix="loofi-fedora-tweaks-${VERSION}/" \
  --output="$SOURCE_TARBALL" \
  "$HEAD_SHA"

# Extract the spec from the same verified commit as the source archive.
git_repo show "${HEAD_SHA}:loofi-fedora-tweaks.spec" > "$BUILD_DIR/rpmbuild/SPECS/loofi-fedora-tweaks.spec"

# Build SRPM only (-bs = build source)
rpmbuild --define "_topdir $BUILD_DIR/rpmbuild" \
         -bs "$BUILD_DIR/rpmbuild/SPECS/loofi-fedora-tweaks.spec"

# Copy SRPM back to repo tree
mkdir -p rpmbuild/SRPMS
mapfile -t BUILT_SRPMS < <(find "$BUILD_DIR/rpmbuild/SRPMS" -maxdepth 1 -type f -name '*.src.rpm' -print)
if [[ "${#BUILT_SRPMS[@]}" -ne 1 ]]; then
  echo "Error: expected exactly one SRPM, found ${#BUILT_SRPMS[@]}" >&2
  exit 1
fi
cp "${BUILT_SRPMS[0]}" rpmbuild/SRPMS/

SRPM_FILE="rpmbuild/SRPMS/$(basename "${BUILT_SRPMS[0]}")"
echo ""
echo "SRPM built successfully: ${SRPM_FILE}"
echo ""
echo "To submit to COPR manually:"
echo "  copr-cli build loofi-fedora-tweaks ${SRPM_FILE}"
