"""
Service/package command handlers: service, package, extension, flatpak_manage.
"""


def handle_service(args, json_output, output_json, print_fn, run_operation, service_explorer_cls):
    """Handle service subcommand."""
    if args.action == "list":
        scope_arg = getattr(args, "user", False)
        from utils.service_explorer import ServiceScope
        scope = ServiceScope.USER if scope_arg else ServiceScope.SYSTEM
        filter_arg = getattr(args, "filter", None)
        search_arg = getattr(args, "search", "")
        services = service_explorer_cls.list_services(
            scope=scope,
            filter_state=filter_arg,
            search=search_arg
        )
        if json_output:
            output_json(
                [
                    {
                        "name": s.name,
                        "state": s.state.value,
                        "enabled": s.enabled,
                        "description": s.description,
                    }
                    for s in services
                ]
            )
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   System Services")
            print_fn("═══════════════════════════════════════════")
            for s in services[:50]:
                marker = "●" if s.state.value == "active" else "○"
                enable_str = "(enabled)" if s.enabled else "(disabled)"
                print_fn(f"  {marker} {s.name} — {s.state.value} {enable_str}")
        return 0

    elif args.action == "status":
        if not hasattr(args, "name") or not args.name:
            print_fn("❌ Service name required")
            return 1
        scope_arg = getattr(args, "user", False)
        from utils.service_explorer import ServiceScope
        scope = ServiceScope.USER if scope_arg else ServiceScope.SYSTEM
        details = service_explorer_cls.get_service_details(args.name, scope=scope)
        if json_output:
            memory_value = getattr(details, "memory_usage", getattr(details, "memory_human", "N/A"))
            pid_value = getattr(details, "pid", getattr(details, "main_pid", None))
            output_json(
                {
                    "name": details.name,
                    "state": details.state.value,
                    "enabled": details.enabled,
                    "description": details.description,
                    "memory": memory_value,
                    "pid": pid_value,
                }
            )
        else:
            memory_value = getattr(details, "memory_usage", getattr(details, "memory_human", "N/A"))
            pid_value = getattr(details, "pid", getattr(details, "main_pid", None))
            print_fn(f"\n  Name: {details.name}")
            print_fn(f"  State: {details.state.value}")
            print_fn(f"  Enabled: {details.enabled}")
            print_fn(f"  Memory: {memory_value}")
            print_fn(f"  PID: {pid_value if pid_value else 'N/A'}")
        return 0

    elif args.action in ("start", "stop", "restart", "enable", "disable", "mask", "unmask"):
        if not hasattr(args, "name") or not args.name:
            print_fn("❌ Service name required")
            return 1
        scope_arg = getattr(args, "user", False)
        from utils.service_explorer import ServiceScope
        scope = ServiceScope.USER if scope_arg else ServiceScope.SYSTEM
        method_map = {
            "start": "start_service",
            "stop": "stop_service",
            "restart": "restart_service",
            "enable": "enable_service",
            "disable": "disable_service",
            "mask": "mask_service",
            "unmask": "unmask_service",
        }
        method_name = method_map[args.action]
        method = getattr(service_explorer_cls, method_name)
        result = method(args.name, scope=scope)
        if json_output:
            output_json({"success": result.success, "message": result.message})
        else:
            if result.success:
                print_fn(f"✅ {result.message}")
            else:
                print_fn(f"❌ {result.message}")
        return 0 if result.success else 1

    elif args.action == "logs":
        if not hasattr(args, "name") or not args.name:
            print_fn("❌ Service name required")
            return 1
        scope_arg = getattr(args, "user", False)
        from utils.service_explorer import ServiceScope
        scope = ServiceScope.USER if scope_arg else ServiceScope.SYSTEM
        lines = getattr(args, "lines", 50)
        logs = service_explorer_cls.get_service_logs(args.name, scope=scope, lines=lines)
        if json_output:
            output_json({"logs": logs})
        else:
            for line in logs:
                print_fn(line)
        return 0

    return 1


def handle_package(args, json_output, output_json, print_fn, run_operation, package_explorer_cls):
    """Handle package subcommand."""
    if args.action == "info":
        if not hasattr(args, "package_name") or not args.package_name:
            print_fn("❌ Package name required")
            return 1
        info = package_explorer_cls.get_package_info(args.package_name)
        if json_output:
            output_json(vars(info))
        else:
            print_fn(f"\n  Name: {info.name}")
            print_fn(f"  Version: {info.version}")
            print_fn(f"  Repo: {info.repo}")
            print_fn(f"  Size: {info.size}")
            print_fn(f"  Summary: {info.summary}")
        return 0

    elif args.action == "list-installed":
        pkgs = package_explorer_cls.list_installed()
        if json_output:
            output_json([{"name": p.name, "version": p.version} for p in pkgs])
        else:
            for p in pkgs[:100]:
                print_fn(f"  {p.name}-{p.version}")
        return 0

    elif args.action == "search":
        if not hasattr(args, "query") or not args.query:
            print_fn("❌ Search query required")
            return 1
        search_fn = getattr(package_explorer_cls, "search", None)
        if search_fn is None:
            search_fn = getattr(package_explorer_cls, "search_packages")
        results = search_fn(args.query)
        if json_output:
            output_json([{"name": r.name, "summary": r.summary} for r in results])
        else:
            if not results:
                print_fn("  No results found.")
            for r in results[:20]:
                print_fn(f"  {r.name}: {r.summary}")
        return 0

    elif args.action == "deps":
        if not hasattr(args, "package_name") or not args.package_name:
            print_fn("❌ Package name required")
            return 1
        deps = package_explorer_cls.get_dependencies(args.package_name)
        if json_output:
            output_json(deps)
        else:
            for d in deps:
                print_fn(f"  {d}")
        return 0

    elif args.action == "install":
        if not hasattr(args, "name") or not args.name:
            print_fn("❌ Package name required")
            return 1
        source = getattr(args, "source", "auto")
        result = package_explorer_cls.install(args.name, source=source)
        if json_output:
            output_json({"success": result.success, "message": result.message})
        else:
            if result.success:
                print_fn(f"✅ {result.message}")
            else:
                print_fn(f"❌ {result.message}")
        return 0 if result.success else 1

    elif args.action == "remove":
        if not hasattr(args, "name") or not args.name:
            print_fn("❌ Package name required")
            return 1
        source = getattr(args, "source", "auto")
        result = package_explorer_cls.remove(args.name, source=source)
        if json_output:
            output_json({"success": result.success, "message": result.message})
        else:
            if result.success:
                print_fn(f"✅ {result.message}")
            else:
                print_fn(f"❌ {result.message}")
        return 0 if result.success else 1

    elif args.action == "list":
        source = getattr(args, "source", "all")
        pkgs = package_explorer_cls.list_installed(source=source)
        if json_output:
            output_json([{"name": p.name, "version": p.version, "source": p.source} for p in pkgs])
        else:
            for p in pkgs[:100]:
                print_fn(f"  {p.name}-{p.version} ({p.source})")
        return 0

    elif args.action == "recent":
        days = getattr(args, "days", 7)
        pkgs = package_explorer_cls.recently_installed(days=days)
        if json_output:
            output_json([{"name": p.name, "version": p.version, "installed": p.installed} for p in pkgs])
        else:
            for p in pkgs[:50]:
                print_fn(f"  {p.name}-{p.version}")
        return 0

    return 1


def handle_extension(args, json_output, output_json, print_fn, run_operation, extension_manager_cls):
    """Handle extension subcommand."""
    if args.action == "list":
        extensions = extension_manager_cls.list_installed()
        if json_output:
            output_json([{"uuid": e.uuid, "name": e.name, "enabled": e.enabled, "version": e.version} for e in extensions])
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   GNOME Shell Extensions")
            print_fn("═══════════════════════════════════════════")
            for e in extensions:
                marker = "✅" if e.enabled else "❌"
                print_fn(f"  {marker} {e.name} (v{e.version}) — {e.uuid}")
        return 0

    elif args.action == "info":
        if not hasattr(args, "uuid") or not args.uuid:
            print_fn("❌ Extension UUID required")
            return 1
        info = extension_manager_cls.get_extension_info(args.uuid)
        if json_output:
            output_json(vars(info))
        else:
            print_fn(f"\n  Name: {info.name}")
            print_fn(f"  UUID: {info.uuid}")
            print_fn(f"  Version: {info.version}")
            print_fn(f"  Enabled: {info.enabled}")
            print_fn(f"  Description: {info.description}")
        return 0

    elif args.action == "enable":
        if not hasattr(args, "uuid") or not args.uuid:
            print_fn("❌ Extension UUID required")
            return 1
        return 0 if run_operation(extension_manager_cls.enable(args.uuid)) else 1

    elif args.action == "disable":
        if not hasattr(args, "uuid") or not args.uuid:
            print_fn("❌ Extension UUID required")
            return 1
        return 0 if run_operation(extension_manager_cls.disable(args.uuid)) else 1

    elif args.action == "install":
        if not hasattr(args, "uuid") or not args.uuid:
            print_fn("❌ Extension UUID required")
            return 1
        return 0 if run_operation(extension_manager_cls.install(args.uuid)) else 1

    elif args.action == "remove":
        if not hasattr(args, "uuid") or not args.uuid:
            print_fn("❌ Extension UUID required")
            return 1
        return 0 if run_operation(extension_manager_cls.remove(args.uuid)) else 1

    elif args.action == "prefs":
        if not hasattr(args, "uuid") or not args.uuid:
            print_fn("❌ Extension UUID required")
            return 1
        return 0 if run_operation(extension_manager_cls.open_preferences(args.uuid)) else 1

    return 1


def handle_flatpak_manage(args, json_output, output_json, print_fn, run_operation, flatpak_manager_cls):
    """Handle flatpak subcommand."""
    if args.action == "list":
        apps = flatpak_manager_cls.list_installed()
        if json_output:
            output_json([{"app_id": a.app_id, "name": a.name, "version": a.version, "branch": a.branch} for a in apps])
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Installed Flatpaks")
            print_fn("═══════════════════════════════════════════")
            for a in apps:
                print_fn(f"  {a.name} ({a.app_id}) — {a.version}/{a.branch}")
        return 0

    elif args.action == "info":
        if not hasattr(args, "app_id") or not args.app_id:
            print_fn("❌ App ID required")
            return 1
        info = flatpak_manager_cls.get_app_info(args.app_id)
        if json_output:
            output_json(vars(info))
        else:
            print_fn(f"\n  Name: {info.name}")
            print_fn(f"  App ID: {info.app_id}")
            print_fn(f"  Version: {info.version}")
            print_fn(f"  Size: {info.size}")
            print_fn(f"  Origin: {info.origin}")
        return 0

    elif args.action == "install":
        if not hasattr(args, "app_id") or not args.app_id:
            print_fn("❌ App ID required")
            return 1
        return 0 if run_operation(flatpak_manager_cls.install_app(args.app_id)) else 1

    elif args.action == "uninstall":
        if not hasattr(args, "app_id") or not args.app_id:
            print_fn("❌ App ID required")
            return 1
        return 0 if run_operation(flatpak_manager_cls.uninstall_app(args.app_id)) else 1

    elif args.action == "update":
        app_id = getattr(args, "app_id", None)
        return 0 if run_operation(flatpak_manager_cls.update_app(app_id)) else 1

    elif args.action == "remotes":
        remotes = flatpak_manager_cls.list_remotes()
        if json_output:
            output_json([{"name": r.name, "url": r.url, "enabled": r.enabled} for r in remotes])
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Flatpak Remotes")
            print_fn("═══════════════════════════════════════════")
            for r in remotes:
                marker = "✅" if r.enabled else "❌"
                print_fn(f"  {marker} {r.name} — {r.url}")
        return 0

    elif args.action == "sizes":
        sizes = flatpak_manager_cls.get_flatpak_sizes()
        total = flatpak_manager_cls.get_total_size()
        if json_output:
            output_json({
                "apps": [{"app_id": s.app_id, "name": s.name, "size": s.size_str} for s in sizes],
                "total": total
            })
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Flatpak Disk Usage")
            print_fn("═══════════════════════════════════════════")
            for s in sizes:
                print_fn(f"  {s.name} ({s.app_id}): {s.size_str}")
            print_fn(f"\n  Total: {total}")
        return 0

    elif args.action == "permissions":
        perms = flatpak_manager_cls.get_all_permissions()
        if json_output:
            output_json([{"app_id": p.app_id, "permissions": p.permissions} for p in perms])
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Flatpak Permissions")
            print_fn("═══════════════════════════════════════════")
            for p in perms:
                print_fn(f"\n  {p.app_id}:")
                for perm in p.permissions:
                    print_fn(f"    - {perm}")
        return 0

    elif args.action == "orphans":
        orphans = flatpak_manager_cls.find_orphan_runtimes()
        if json_output:
            output_json({"orphans": orphans})
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Orphaned Flatpak Runtimes")
            print_fn("═══════════════════════════════════════════")
            if orphans:
                for o in orphans:
                    print_fn(f"  {o}")
            else:
                print_fn("  No orphans found.")
        return 0

    elif args.action == "cleanup":
        return 0 if run_operation(flatpak_manager_cls.cleanup_unused()) else 1

    return 1
