# Qt scroll-area accessibility dependency regression

The downstream patch targets Qt Base 6.11.2. It bounds-checks against the same
local child list used for lookup. It preserves accessible children and returns
null for negative, out-of-range, and stale indices, as required by the accessible
interface. Source: https://github.com/qt/qtbase/blob/v6.11.2/src/widgets/accessible/complexwidgets.cpp

This is a downstream source fix. Never patch live shared libraries.
`patch --dry-run -p1` validates applicability from a Qt Base checkout.

Run `python3 scripts/qualify_qt_scroll_accessibility.py` against the rebuilt Qt
(`pkg-config`, compiler and runtime library paths must refer to that same build).
The probe checks a formerly valid index after hiding a scroll area, negative
and upper-bound indices, and the surviving viewport child. It disables core
creation, uses isolated XDG state and does not disable accessibility.

## Reproducible isolated runtime

On Fedora with exact Qt 6.11.2 Core/Gui development packages, private headers,
WidgetsTools, and BuildInternals installed, run:

```bash
python3 scripts/build_qualified_qt_widgets.py
```

The recipe downloads the official Qt Base 6.11.2 source archive and verifies its
pinned, published SHA256, applies the checked-in patch, and builds the complete
QtWidgets shared library against the matching installed Core and Gui. It uses
Qt's own Widgets CMake definition and BuildInternals; compilation and automatic
MOC generation are both limited to two jobs. It does not install any files.

Outputs are isolated under `test-results/v35/qt-runtime/`. The recipe records
source, patch, runtime and dependency library hashes, installed Qt package
identities, full probe `ldd` output, and the native probe result in
`qualification.json`. `configure.log` and `build.log` preserve diagnostics.
Only the probe child uses `LD_LIBRARY_PATH` to load the complete rebuilt
library. No preload interposer or accessibility disabling is used.

The installed Qt 6.11.2 baseline still reproduced SIGSEGV (exit -11) on
2026-10-19; the result is `installed-baseline.json` in the same output folder.
The complete rebuilt library passed the native regression on the same date:
exit 0, stale/negative/upper-bound indices returned null, and the surviving
viewport remained accessible. `ldd` resolved Widgets to the isolated build and
Core/Gui to Fedora's `6.11.2-3.fc44` libraries. All 72 public Widgets feature
flags matched the installed package. A separate isolated PyQt6 Widgets
show/hide smoke process also passed (`pyqt-smoke.json`).

The built `libQt6Widgets.so.6.11.2` SHA256 is
`68aa0b68a29a62b6f89ccd753ff52726ef661f37b04405ff42e61ccb9d93131f`.
This establishes a source-corrected runtime for this native regression; the
host's installed Qt remains unchanged. The preserved Ninja compilation records
are `ninja-compilation.log`. Only an actual `passed: true` result in a fresh
`qualification.json` establishes a successful rerun on another environment.

## Disposable guest staging

Stage the actual library and its `.so.6` symlink from `runtime_library_dir`
into a dedicated directory inside an owned disposable Fedora KDE guest.
Verify that the guest's Core/Gui version, package identities and library hashes
match the manifest first. A Qt 6.11.2 Widgets library must not be loaded into the
earlier Qt 6.10.2 guest. Alternatively, run the recipe inside a disposable
guest with matching development packages. Do not overwrite system libraries or
copy the build's generated CMake/header files into `/usr`.

Set `LD_LIBRARY_PATH` to that guest directory for the native probe and candidate
application process only, and retain `ldd`/loaded-library evidence. Run the full
exact-RPM Wayland/X11 AT-SPI matrix with accessibility enabled, preserving the
original package/runtime identities alongside the patched library hash.
The isolated source-built artifact is not a replacement Fedora RPM, an
upstream release, or full candidate qualification. A native offscreen pass
alone does not establish full desktop qualification or qualify deployment on
user systems. Full native matrices are complementary, risk-based evidence under
the maintainer's October 21, 2026 release policy.
