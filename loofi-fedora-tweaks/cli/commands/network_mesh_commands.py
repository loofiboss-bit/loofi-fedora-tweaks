"""
Network/mesh command handlers: mesh, teleport.
"""

import os


def handle_mesh(args, json_output, output_json, print_fn, mesh_discovery_cls):
    """Handle mesh networking subcommand."""
    if args.action == "discover":
        peers = mesh_discovery_cls.discover_peers()
        if json_output:
            from dataclasses import asdict

            output_json({"peers": [asdict(p) for p in peers]})
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Loofi Link - Nearby Devices")
            print_fn("═══════════════════════════════════════════")
            if not peers:
                print_fn("\n(no devices found on local network)")
            else:
                for peer in peers:
                    print_fn(f"  🔗 {peer.hostname} ({peer.ip_address})")
        return 0

    elif args.action == "status":
        device_id = mesh_discovery_cls.get_device_id()
        local_ips = mesh_discovery_cls.get_local_ips()
        if json_output:
            output_json({"device_id": device_id, "local_ips": local_ips})
        else:
            print_fn(f"Device ID: {device_id}")
            print_fn(f"Local IPs: {', '.join(local_ips)}")
        return 0

    return 1


def handle_teleport(args, json_output, output_json, print_fn, state_teleport_manager_cls):
    """Handle state teleport subcommand."""
    if args.action == "capture":
        workspace_path = getattr(args, "path", None) or os.getcwd()
        state = state_teleport_manager_cls.capture_full_state(workspace_path)
        package = state_teleport_manager_cls.create_teleport_package(state, target_device=getattr(args, "target", "unknown"))
        pkg_dir = state_teleport_manager_cls.get_package_dir()
        filepath = os.path.join(pkg_dir, f"{package.package_id}.json")
        result = state_teleport_manager_cls.save_package_to_file(package, filepath)

        if json_output:
            output_json(
                {
                    "success": result.success,
                    "package_id": package.package_id,
                    "file": filepath,
                }
            )
        else:
            print_fn(f"{'✅' if result.success else '❌'} {result.message}")
            if result.success:
                print_fn(f"   Package ID: {package.package_id}")
                print_fn(f"   Size: {package.size_bytes} bytes")
        return 0 if result.success else 1

    elif args.action == "list":
        packages = state_teleport_manager_cls.list_saved_packages()
        if json_output:
            output_json({"packages": packages})
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Saved Teleport Packages")
            print_fn("═══════════════════════════════════════════")
            if not packages:
                print_fn("\n(no packages found)")
            else:
                for pkg in packages:
                    print_fn(f"  📦 {pkg['package_id'][:8]}... from {pkg['source_device']}")
                    print_fn(f"     Size: {pkg['size_bytes']} bytes")
        return 0

    elif args.action == "restore":
        if not args.package_id:
            print_fn("❌ Package ID required for restore")
            return 1
        pkg_dir = state_teleport_manager_cls.get_package_dir()
        # Find matching package file
        for filename in os.listdir(pkg_dir):
            if args.package_id in filename:
                filepath = os.path.join(pkg_dir, filename)
                package = state_teleport_manager_cls.load_package_from_file(filepath)
                result = state_teleport_manager_cls.apply_teleport(package)
                print_fn(f"{'✅' if result.success else '❌'} {result.message}")
                return 0 if result.success else 1
        print_fn(f"❌ Package '{args.package_id}' not found")
        return 1

    return 1
