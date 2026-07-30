"""
Firewall command handler.
"""

from cli.action_plans import create_public_plans


def _port_parameters(spec, zone=None):
    value = str(spec or "")
    if "/" in value:
        port_text, protocol = value.split("/", 1)
    else:
        port_text, protocol = value, "tcp"
    if not port_text.isdigit():
        raise ValueError("Port must be numeric.")
    parameters = {"port": int(port_text), "protocol": protocol}
    if zone:
        parameters["zone"] = zone
    return parameters


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
        parameters = {"action": "add", "service": args.service}
        if zone:
            parameters["zone"] = zone
        return create_public_plans(
            [("cli:firewall add-service", parameters)],
            json_output=json_output,
            output_json=output_json,
            print_fn=print_fn,
        )

    elif args.action == "remove-service":
        if not hasattr(args, "service") or not args.service:
            print_fn("❌ Service name required")
            return 1
        zone = getattr(args, "zone", None)
        parameters = {"action": "remove", "service": args.service}
        if zone:
            parameters["zone"] = zone
        return create_public_plans(
            [("cli:firewall remove-service", parameters)],
            json_output=json_output,
            output_json=output_json,
            print_fn=print_fn,
        )

    elif args.action == "add-port":
        if not hasattr(args, "port") or not args.port:
            print_fn("❌ Port required (e.g., 8080/tcp)")
            return 1
        zone = getattr(args, "zone", None)
        try:
            parameters = _port_parameters(args.port, zone)
        except ValueError as exc:
            print_fn(f"❌ {exc}")
            return 1
        return create_public_plans(
            [("cli:firewall open-port", parameters)],
            json_output=json_output,
            output_json=output_json,
            print_fn=print_fn,
        )

    elif args.action == "remove-port":
        if not hasattr(args, "port") or not args.port:
            print_fn("❌ Port required (e.g., 8080/tcp)")
            return 1
        zone = getattr(args, "zone", None)
        try:
            parameters = _port_parameters(args.port, zone)
        except ValueError as exc:
            print_fn(f"❌ {exc}")
            return 1
        return create_public_plans(
            [("cli:firewall close-port", parameters)],
            json_output=json_output,
            output_json=output_json,
            print_fn=print_fn,
        )

    elif args.action == "set-default-zone":
        if not hasattr(args, "zone") or not args.zone:
            print_fn("❌ Zone name required")
            return 1
        return create_public_plans(
            [("cli:firewall set-default-zone", {"zone": args.zone})],
            json_output=json_output,
            output_json=output_json,
            print_fn=print_fn,
        )

    elif args.action == "reload":
        return create_public_plans(
            [("cli:firewall reload", {})],
            json_output=json_output,
            output_json=output_json,
            print_fn=print_fn,
        )

    elif args.action == "open-port":
        if not hasattr(args, "spec") or not args.spec:
            print_fn("❌ Port spec required (e.g., 8080 or 8080/tcp)")
            return 1
        try:
            parameters = _port_parameters(args.spec, getattr(args, "zone", None))
        except ValueError as exc:
            print_fn(f"❌ {exc}")
            return 1
        return create_public_plans(
            [("cli:firewall open-port", parameters)],
            json_output=json_output,
            output_json=output_json,
            print_fn=print_fn,
        )

    elif args.action == "close-port":
        if not hasattr(args, "spec") or not args.spec:
            print_fn("❌ Port spec required (e.g., 8080 or 8080/tcp)")
            return 1
        try:
            parameters = _port_parameters(args.spec, getattr(args, "zone", None))
        except ValueError as exc:
            print_fn(f"❌ {exc}")
            return 1
        return create_public_plans(
            [("cli:firewall close-port", parameters)],
            json_output=json_output,
            output_json=output_json,
            print_fn=print_fn,
        )

    return 1
