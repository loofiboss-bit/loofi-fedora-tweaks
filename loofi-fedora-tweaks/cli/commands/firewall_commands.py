"""
Firewall command handler.
"""


def handle_firewall(args, json_output, output_json, print_fn, run_operation, firewall_manager_cls):
    """Handle firewall subcommand."""
    if not firewall_manager_cls.is_available():
        print_fn("❌ FirewallD is not available on this system")
        return 1

    if args.action == "status":
        status = firewall_manager_cls.get_status()
        if json_output:
            output_json(
                {
                    "running": status.running,
                    "default_zone": status.default_zone,
                    "active_zones": status.active_zones,
                    "ports": status.ports,
                    "services": status.services,
                }
            )
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Firewall Status")
            print_fn("═══════════════════════════════════════════")
            print_fn(f"\n  Running: {status.running}")
            print_fn(f"  Default Zone: {status.default_zone}")
            if status.active_zones:
                print_fn("\n  Active Zones:")
                if hasattr(status.active_zones, "items"):
                    for zone_name, interfaces in status.active_zones.items():
                        print_fn(f"    {zone_name}: {', '.join(interfaces) if interfaces else 'no interfaces'}")
                else:
                    print_fn(f"    {status.active_zones}")
            if status.services:
                print_fn(f"\n  Services: {', '.join(status.services)}")
            if status.ports:
                print_fn(f"  Ports: {', '.join(status.ports)}")
        return 0

    elif args.action == "ports":
        ports = firewall_manager_cls.list_ports()
        if json_output:
            output_json({"ports": ports})
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Open Firewall Ports")
            print_fn("═══════════════════════════════════════════")
            if not ports:
                print_fn("  No open ports")
            for port in ports:
                print_fn(f"  {port}")
        return 0

    elif args.action == "services":
        services = firewall_manager_cls.list_services()
        if json_output:
            output_json({"services": services})
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Allowed Firewall Services")
            print_fn("═══════════════════════════════════════════")
            if not services:
                print_fn("  No services configured")
            for service in services:
                print_fn(f"  {service}")
        return 0

    elif args.action == "zones":
        zones = firewall_manager_cls.get_zones()
        active = firewall_manager_cls.get_active_zones()
        if json_output:
            output_json({"zones": zones, "active": active})
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Firewall Zones")
            print_fn("═══════════════════════════════════════════")
            for zone in zones:
                marker = "*" if zone in active else " "
                if zone in active:
                    interfaces = active.get(zone) or []
                    iface_str = f" ({', '.join(interfaces)})" if interfaces else ""
                else:
                    iface_str = ""
                print_fn(f" {marker} {zone}{iface_str}")
        return 0

    elif args.action == "list-zones":
        zones = firewall_manager_cls.list_zones()
        if json_output:
            output_json([{"name": z.name, "active": z.active} for z in zones])
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Firewall Zones")
            print_fn("═══════════════════════════════════════════")
            for z in zones:
                marker = "✅" if z.active else "❌"
                print_fn(f"  {marker} {z.name}")
        return 0

    elif args.action == "add-service":
        if not hasattr(args, "service") or not args.service:
            print_fn("❌ Service name required")
            return 1
        zone = getattr(args, "zone", None)
        return 0 if run_operation(firewall_manager_cls.add_service(args.service, zone=zone)) else 1

    elif args.action == "remove-service":
        if not hasattr(args, "service") or not args.service:
            print_fn("❌ Service name required")
            return 1
        zone = getattr(args, "zone", None)
        return 0 if run_operation(firewall_manager_cls.remove_service(args.service, zone=zone)) else 1

    elif args.action == "add-port":
        if not hasattr(args, "port") or not args.port:
            print_fn("❌ Port required (e.g., 8080/tcp)")
            return 1
        zone = getattr(args, "zone", None)
        return 0 if run_operation(firewall_manager_cls.add_port(args.port, zone=zone)) else 1

    elif args.action == "remove-port":
        if not hasattr(args, "port") or not args.port:
            print_fn("❌ Port required (e.g., 8080/tcp)")
            return 1
        zone = getattr(args, "zone", None)
        return 0 if run_operation(firewall_manager_cls.remove_port(args.port, zone=zone)) else 1

    elif args.action == "set-default-zone":
        if not hasattr(args, "zone") or not args.zone:
            print_fn("❌ Zone name required")
            return 1
        return 0 if run_operation(firewall_manager_cls.set_default_zone(args.zone)) else 1

    elif args.action == "reload":
        return 0 if run_operation(firewall_manager_cls.reload()) else 1

    elif args.action == "open-port":
        if not hasattr(args, "spec") or not args.spec:
            print_fn("❌ Port spec required (e.g., 8080 or 8080/tcp)")
            return 1
        spec = args.spec
        if "/" in spec:
            port, proto = spec.split("/", 1)
        else:
            port, proto = spec, "tcp"
        result = firewall_manager_cls.open_port(port, proto)
        if json_output:
            output_json({"success": result.success, "message": result.message})
        else:
            if result.success:
                print_fn(f"✅ {result.message}")
            else:
                print_fn(f"❌ {result.message}")
        return 0 if result.success else 1

    elif args.action == "close-port":
        if not hasattr(args, "spec") or not args.spec:
            print_fn("❌ Port spec required (e.g., 8080 or 8080/tcp)")
            return 1
        spec = args.spec
        if "/" in spec:
            port, proto = spec.split("/", 1)
        else:
            port, proto = spec, "tcp"
        result = firewall_manager_cls.close_port(port, proto)
        if json_output:
            output_json({"success": result.success, "message": result.message})
        else:
            if result.success:
                print_fn(f"✅ {result.message}")
            else:
                print_fn(f"❌ {result.message}")
        return 0 if result.success else 1

    return 1
