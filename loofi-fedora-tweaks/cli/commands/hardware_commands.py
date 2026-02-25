"""
Hardware command handlers: hardware, vm, vfio, bluetooth, storage, display.
"""


def handle_hardware(json_output, output_json, print_fn, detect_hardware_profile_fn):
    """Show detected hardware profile."""
    key, profile = detect_hardware_profile_fn()

    if json_output:
        output_json({"profile_key": key, "profile": profile})
    else:
        print_fn("═══════════════════════════════════════════")
        print_fn("   Hardware Profile")
        print_fn("═══════════════════════════════════════════")
        print_fn(f"\n🖥️  Detected: {profile['label']}")
        print_fn(f"   Battery Limit:    {'✅' if profile.get('battery_limit') else '❌'}")
        print_fn(f"   Fan Control:      {'✅' if profile.get('nbfc') else '❌'}")
        print_fn(f"   Fingerprint:      {'✅' if profile.get('fingerprint') else '❌'}")
        print_fn(f"   Power Profiles:   {'✅' if profile.get('power_profiles') else '❌'}")
        thermal = profile.get("thermal_management", "None")
        print_fn(f"   Thermal Driver:   {thermal or 'Generic'}")

    return 0


def handle_vm(args, json_output, output_json, print_fn, vm_manager_cls):
    """Handle VM subcommand."""
    if args.action == "list":
        vms = vm_manager_cls.list_vms()
        if json_output:
            from dataclasses import asdict

            output_json({"vms": [asdict(v) for v in vms]})
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Virtual Machines")
            print_fn("═══════════════════════════════════════════")
            if not vms:
                print_fn("\n(no VMs found)")
            else:
                for vm in vms:
                    icon = "🟢" if vm.state == "running" else "⚪"
                    print_fn(f"  {icon} {vm.name} [{vm.state}]  RAM: {vm.memory_mb}MB  vCPUs: {vm.vcpus}")
        return 0

    elif args.action == "status":
        status = vm_manager_cls.get_vm_info(args.name)
        if json_output:
            if status:
                from dataclasses import asdict

                output_json(asdict(status))
            else:
                output_json({"error": "VM not found"})
        else:
            if status:
                print_fn(f"VM: {status.name} [{status.state}]")
            else:
                print_fn(f"❌ VM '{args.name}' not found")
        return 0

    elif args.action == "start":
        result = vm_manager_cls.start_vm(args.name)
        print_fn(f"{'✅' if result.success else '❌'} {result.message}")
        return 0 if result.success else 1

    elif args.action == "stop":
        result = vm_manager_cls.stop_vm(args.name)
        print_fn(f"{'✅' if result.success else '❌'} {result.message}")
        return 0 if result.success else 1

    return 1


def handle_vfio(args, json_output, output_json, print_fn, vfio_assistant_cls):
    """Handle VFIO GPU passthrough subcommand."""
    if args.action == "check":
        prereqs = vfio_assistant_cls.check_prerequisites()
        if json_output:
            output_json(prereqs)
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   VFIO Prerequisites Check")
            print_fn("═══════════════════════════════════════════")
            for key, val in prereqs.items():
                icon = "✅" if val else "❌"
                print_fn(f"  {icon} {key}")
        return 0

    elif args.action == "gpus":
        candidates = vfio_assistant_cls.get_passthrough_candidates()
        if json_output:
            output_json({"candidates": candidates})
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   GPU Passthrough Candidates")
            print_fn("═══════════════════════════════════════════")
            if not candidates:
                print_fn("\n(no candidates found)")
            else:
                for gpu in candidates:
                    print_fn(f"\n  {gpu.get('name', 'Unknown GPU')}")
                    print_fn(f"    IOMMU Group: {gpu.get('iommu_group', '?')}")
                    print_fn(f"    IDs: {gpu.get('vendor_id', '?')}:{gpu.get('device_id', '?')}")
        return 0

    elif args.action == "plan":
        candidates = vfio_assistant_cls.get_passthrough_candidates()
        if not candidates:
            if json_output:
                output_json({"steps": [], "error": "No passthrough GPU candidates found"})
            else:
                print_fn("❌ No passthrough GPU candidates found")
            return 1

        plan = vfio_assistant_cls.get_step_by_step_plan(candidates[0])
        if json_output:
            output_json({"steps": plan})
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   VFIO Setup Plan")
            print_fn("═══════════════════════════════════════════")
            for i, step in enumerate(plan, 1):
                print_fn(f"\n  Step {i}: {step}")
        return 0

    return 1


def handle_bluetooth(args, json_output, output_json, print_fn, bluetooth_manager_cls):
    """Handle bluetooth subcommand."""
    if args.action == "status":
        status = bluetooth_manager_cls.get_adapter_status()
        if json_output:
            output_json(
                {
                    "available": bool(status.adapter_name),
                    "powered": status.powered,
                    "discoverable": status.discoverable,
                    "adapter_name": status.adapter_name,
                    "adapter_address": status.adapter_address,
                }
            )
        else:
            if not status.adapter_name:
                print_fn("❌ No Bluetooth adapter found")
                return 1
            power = "🟢 On" if status.powered else "🔴 Off"
            print_fn(f"Bluetooth: {power}")
            print_fn(f"Adapter: {status.adapter_name} ({status.adapter_address})")
            print_fn(f"Discoverable: {'yes' if status.discoverable else 'no'}")
        return 0

    elif args.action == "devices":
        paired_only = getattr(args, "paired", False)
        devices = bluetooth_manager_cls.list_devices(paired_only=paired_only)
        if json_output:
            output_json(
                {
                    "devices": [
                        {
                            "address": d.address,
                            "name": d.name,
                            "paired": d.paired,
                            "connected": d.connected,
                            "trusted": d.trusted,
                            "device_type": d.device_type.value,
                        }
                        for d in devices
                    ]
                }
            )
        else:
            if not devices:
                print_fn("No devices found.")
                return 0
            for d in devices:
                status_icons = []
                if d.connected:
                    status_icons.append("connected")
                if d.paired:
                    status_icons.append("paired")
                if d.trusted:
                    status_icons.append("trusted")
                status_str = ", ".join(status_icons) if status_icons else "available"
                print_fn(f"  {d.name} ({d.address}) [{status_str}]")
        return 0

    elif args.action == "scan":
        timeout = getattr(args, "timeout", 10)
        print_fn(f"Scanning for {timeout} seconds...")
        devices = bluetooth_manager_cls.scan(timeout=timeout)
        if json_output:
            output_json(
                {
                    "devices": [
                        {
                            "address": d.address,
                            "name": d.name,
                            "device_type": d.device_type.value,
                        }
                        for d in devices
                    ]
                }
            )
        else:
            print_fn(f"Found {len(devices)} devices:")
            for d in devices:
                print_fn(f"  {d.name} ({d.address}) [{d.device_type.value}]")
        return 0

    elif args.action in ("power-on", "power-off"):
        result = bluetooth_manager_cls.power_on() if args.action == "power-on" else bluetooth_manager_cls.power_off()
        icon = "✅" if result.success else "❌"
        print_fn(f"{icon} {result.message}")
        return 0 if result.success else 1

    elif args.action in ("connect", "disconnect", "pair", "unpair", "trust"):
        address = getattr(args, "address", None)
        if not address:
            print_fn("❌ Device address required")
            return 1
        action_map = {
            "connect": bluetooth_manager_cls.connect,
            "disconnect": bluetooth_manager_cls.disconnect,
            "pair": bluetooth_manager_cls.pair,
            "unpair": bluetooth_manager_cls.unpair,
            "trust": bluetooth_manager_cls.trust,
        }
        result = action_map[args.action](address)
        icon = "✅" if result.success else "❌"
        print_fn(f"{icon} {result.message}")
        return 0 if result.success else 1

    return 1


def handle_storage(args, json_output, output_json, print_fn, storage_manager_cls):
    """Handle storage subcommand."""
    if args.action == "disks":
        disks = storage_manager_cls.list_disks()
        if json_output:
            output_json(
                {
                    "disks": [
                        {
                            "name": d.name,
                            "size": d.size,
                            "type": d.device_type,
                            "model": d.model,
                            "mountpoint": d.mountpoint,
                            "removable": d.rm,
                        }
                        for d in disks
                    ]
                }
            )
        else:
            if not disks:
                print_fn("No disks found.")
                return 0
            print_fn("Physical Disks:")
            for d in disks:
                rm = " [removable]" if d.rm else ""
                print_fn(f"  {d.name}: {d.model or 'Unknown'} ({d.size}){rm}")
        return 0

    elif args.action == "mounts":
        mounts = storage_manager_cls.list_mounts()
        if json_output:
            output_json(
                {
                    "mounts": [
                        {
                            "device": m.source,
                            "mountpoint": m.target,
                            "fstype": m.fstype,
                            "size": m.size,
                            "used": m.used,
                            "available": m.avail,
                            "use_percent": m.use_percent,
                        }
                        for m in mounts
                    ]
                }
            )
        else:
            print_fn("Mount Points:")
            for m in mounts:
                print_fn(f"  {m.source} -> {m.target} ({m.fstype}) [{m.used}/{m.size} = {m.use_percent}]")
        return 0

    elif args.action == "smart":
        device = getattr(args, "device", None)
        if not device:
            print_fn("❌ Device path required (e.g. /dev/sda)")
            return 1
        health = storage_manager_cls.get_smart_health(device)
        if json_output:
            output_json(
                {
                    "device": device,
                    "model": health.model,
                    "serial": health.serial,
                    "health": "PASSED" if health.health_passed else "FAILED",
                    "temperature_c": health.temperature_c,
                    "power_on_hours": health.power_on_hours,
                    "reallocated_sectors": health.reallocated_sectors,
                    "raw_output": health.raw_output,
                }
            )
        else:
            print_fn(f"SMART Health for {device}:")
            print_fn(f"  Model: {health.model}")
            print_fn(f"  Serial: {health.serial}")
            print_fn(f"  Health: {'PASSED' if health.health_passed else 'FAILED'}")
            print_fn(f"  Temperature: {health.temperature_c}°C")
            print_fn(f"  Power-on hours: {health.power_on_hours}")
            print_fn(f"  Reallocated sectors: {health.reallocated_sectors}")
        return 0

    elif args.action == "usage":
        summary = storage_manager_cls.get_usage_summary()
        if json_output:
            output_json(summary)
        else:
            print_fn(f"Total: {summary.get('total_size', 'N/A')}")
            print_fn(f"Used:  {summary.get('total_used', 'N/A')}")
            print_fn(f"Free:  {summary.get('total_available', 'N/A')}")
            print_fn(f"Disks: {summary.get('disk_count', 0)}")
            print_fn(f"Mounts: {summary.get('mount_count', 0)}")
        return 0

    elif args.action == "trim":
        result = storage_manager_cls.trim_ssd()
        icon = "✅" if result.success else "❌"
        print_fn(f"{icon} {result.message}")
        return 0 if result.success else 1

    return 1


def handle_display(args, json_output, output_json, print_fn, run_operation, wayland_display_manager_cls):
    """Handle display configuration subcommand."""
    if args.action == "list":
        displays = wayland_display_manager_cls.get_displays()
        if json_output:
            output_json(
                [
                    {
                        "name": d.name,
                        "resolution": d.resolution,
                        "scale": d.scale,
                        "refresh": d.refresh_rate,
                        "primary": d.primary,
                    }
                    for d in displays
                ]
            )
        else:
            for d in displays:
                primary = " ★" if d.primary else ""
                print_fn(f"  {d.name}: {d.resolution} @{d.scale}x {d.refresh_rate}Hz{primary}")
        return 0

    elif args.action == "session":
        info = wayland_display_manager_cls.get_session_info()
        if json_output:
            output_json(info)
        else:
            for k, v in info.items():
                print_fn(f"  {k}: {v}")
        return 0

    elif args.action == "fractional-on":
        return 0 if run_operation(wayland_display_manager_cls.enable_fractional_scaling()) else 1

    elif args.action == "fractional-off":
        return 0 if run_operation(wayland_display_manager_cls.disable_fractional_scaling()) else 1

    return 1
