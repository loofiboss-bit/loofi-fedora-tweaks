#!/bin/bash
set -euo pipefail

VERSION=$(python3 -c "exec(open('loofi-fedora-tweaks/version.py').read()); print(__version__)")

echo "Building RPM for loofi-fedora-tweaks v${VERSION}"

# Use a unique temporary build root so parallel builds and stale paths cannot
# cause this script to remove data owned by another run.
BUILD_DIR=$(mktemp -d "${TMPDIR:-/tmp}/loofi-fedora-tweaks-build.XXXXXX")
trap 'rm -rf -- "$BUILD_DIR"' EXIT
mkdir -p "$BUILD_DIR"/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

# Prepare source tarball (mirrors the GitHub archive layout)
STAGE="$BUILD_DIR/temp_build/loofi-fedora-tweaks-$VERSION"
mkdir -p "$STAGE/loofi-fedora-tweaks"
cp -r loofi-fedora-tweaks/* "$STAGE/loofi-fedora-tweaks/"
cp loofi-fedora-tweaks.desktop "$STAGE/"
cp loofi-fedora-tweaks.metainfo.xml "$STAGE/"
cp LICENSE "$STAGE/"
cp README.md "$STAGE/"
cp loofi-fedora-tweaks.1 "$STAGE/"
mkdir -p "$STAGE/scripts"
cp scripts/loofi-flatpak-maintenance "$STAGE/scripts/"
cp scripts/loofi-rpm-transaction scripts/loofi-setup-sources "$STAGE/scripts/"

# Ensure Python cache artifacts are never packaged
find "$STAGE" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$STAGE" -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete

tar -czf "$BUILD_DIR"/rpmbuild/SOURCES/loofi-fedora-tweaks-$VERSION.tar.gz -C "$BUILD_DIR"/temp_build loofi-fedora-tweaks-$VERSION

# Copy spec file
cp loofi-fedora-tweaks.spec "$BUILD_DIR"/rpmbuild/SPECS/

# Normalize spec line endings to avoid %prep failures on Linux when working tree files
# were checked out with CRLF on Windows.
sed -i 's/\r$//' "$BUILD_DIR"/rpmbuild/SPECS/loofi-fedora-tweaks.spec

# Build RPM
rpmbuild --define "_topdir $BUILD_DIR/rpmbuild" -ba "$BUILD_DIR"/rpmbuild/SPECS/loofi-fedora-tweaks.spec

# Copy only the RPM produced by this invocation back to the repository.
shopt -s nullglob
BUILT_RPMS=("$BUILD_DIR"/rpmbuild/RPMS/noarch/loofi-fedora-tweaks-*.rpm)
if [[ ${#BUILT_RPMS[@]} -ne 1 ]]; then
    echo "Expected one noarch RPM, found ${#BUILT_RPMS[@]}" >&2
    exit 1
fi
mkdir -p rpmbuild/RPMS/noarch
RPM_PATH="$(pwd)/rpmbuild/RPMS/noarch/${BUILT_RPMS[0]##*/}"
cp "${BUILT_RPMS[0]}" "$RPM_PATH"

echo "RPM built successfully at $RPM_PATH"
echo "RPM_PATH=$RPM_PATH"
