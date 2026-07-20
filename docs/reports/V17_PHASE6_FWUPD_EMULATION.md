# v17 Phase 6 -- fwupd Host Emulation

Date: 2026-07-20
Host: Fedora Linux 44 KDE, fwupd 2.1.6
Result: pass

## Fixture

The test used fwupd's packaged installed-test fixture rather than a project
mock:

```text
/usr/share/installed-tests/fwupd/device-tests/hughski-colorhug2.json
```

The fixture is non-interactive and exercises two signed ColorHug2 firmware
payloads, versions 2.0.6 and 2.0.7, for GUID
`2082b5e0-7a64-478a-b1b2-e3404fab6dad`.

## Command and result

```bash
fwupdmgr device-emulate --assume-yes --only-emulated \
  --no-unreported-check --no-metadata-check \
  /usr/share/installed-tests/fwupd/device-tests/hughski-colorhug2.json
```

fwupd completed both emulated firmware steps and returned:

```text
Hughski ColorHug2: OK!
```

The command exited with status zero. The emulated device is transient: after
the fixture completed, `get-devices` no longer exposed it and `get-results` by
GUID returned `failed to find any device`. This is expected fixture behavior,
not evidence from physical firmware hardware. Assurance therefore retains its
documented hardware-dependent manual matrix while using this host-emulation run
as the automated JSON/device/version/checksum workflow gate.
