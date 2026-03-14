"""User-oriented CLI handlers extracted from cli.main."""


def handle_preset(args, json_output, output_json, print_fn, json_module, preset_manager_cls):
    """Handle preset subcommand."""
    manager = preset_manager_cls()

    if args.action == "list":
        presets = manager.list_presets()
        if json_output:
            output_json({"presets": presets})
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Available Presets")
            print_fn("═══════════════════════════════════════════")
            if not presets:
                print_fn("\n(no presets found)")
            else:
                for name in presets:
                    print_fn(f"  📋 {name}")
        return 0

    if args.action == "apply":
        if not args.name:
            print_fn("❌ Preset name required")
            return 1
        result = manager.load_preset(args.name)
        if result:
            if json_output:
                output_json({"success": True, "applied": args.name, "settings": result})
            else:
                print_fn(f"✅ Applied preset: {args.name}")
            return 0
        if json_output:
            output_json({"success": False, "error": f"Preset '{args.name}' not found"})
        else:
            print_fn(f"❌ Preset '{args.name}' not found")
        return 1

    if args.action == "export":
        if not args.name or not args.path:
            print_fn("❌ Preset name and path required")
            return 1
        result = manager.load_preset(args.name)
        if not result:
            print_fn(f"❌ Preset '{args.name}' not found")
            return 1
        try:
            with open(args.path, "w", encoding="utf-8") as f:
                json_module.dump(result, f, indent=2)
            if json_output:
                output_json({"success": True, "exported": args.name, "path": args.path})
            else:
                print_fn(f"✅ Exported preset '{args.name}' to {args.path}")
            return 0
        except (OSError, TypeError, ValueError) as e:
            print_fn(f"❌ Export failed: {e}")
            return 1

    return 1


def handle_focus_mode(args, json_output, output_json, print_fn, focus_mode_cls):
    """Handle focus-mode subcommand."""
    if args.action == "on":
        profile = getattr(args, "profile", "default")
        result = focus_mode_cls.enable(profile)
        if json_output:
            output_json(result)
        else:
            icon = "✅" if result["success"] else "❌"
            print_fn(f"{icon} {result['message']}")
            if result.get("hosts_modified"):
                print_fn("   🌐 Domains blocked via /etc/hosts")
            if result.get("dnd_enabled"):
                print_fn("   🔕 Do Not Disturb enabled")
            if result.get("processes_killed"):
                print_fn(f"   💀 Killed processes: {', '.join(result['processes_killed'])}")
        return 0 if result["success"] else 1

    if args.action == "off":
        result = focus_mode_cls.disable()
        if json_output:
            output_json(result)
        else:
            icon = "✅" if result["success"] else "❌"
            print_fn(f"{icon} {result['message']}")
        return 0 if result["success"] else 1

    if args.action == "status":
        is_active = focus_mode_cls.is_active()
        active_profile = focus_mode_cls.get_active_profile()
        profiles = focus_mode_cls.list_profiles()

        if json_output:
            output_json(
                {
                    "active": is_active,
                    "active_profile": active_profile,
                    "profiles": profiles,
                }
            )
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Focus Mode Status")
            print_fn("═══════════════════════════════════════════")
            status_icon = "🟢 Active" if is_active else "⚪ Inactive"
            print_fn(f"\nStatus: {status_icon}")
            if active_profile:
                print_fn(f"Profile: {active_profile}")
            print_fn(f"\nAvailable profiles: {', '.join(profiles)}")
        return 0

    return 1


def handle_profile(args, json_output, output_json, print_fn, profile_manager_cls):
    """Handle profile subcommand."""
    if args.action == "list":
        profiles = profile_manager_cls.list_profiles()
        if json_output:
            output_json({"profiles": profiles})
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   System Profiles")
            print_fn("═══════════════════════════════════════════")
            if not profiles:
                print_fn("\n(no profiles found)")
            else:
                active = profile_manager_cls.get_active_profile()
                for profile in profiles:
                    badge = " [ACTIVE]" if profile["key"] == active else ""
                    ptype = "built-in" if profile["builtin"] else "custom"
                    print_fn(f"\n  {profile['icon']}  {profile['name']}{badge}")
                    print_fn(f"      Key: {profile['key']} ({ptype})")
                    print_fn(f"      {profile['description']}")
        return 0

    if args.action == "apply":
        if not args.name:
            print_fn("❌ Profile name required")
            return 1
        result = profile_manager_cls.apply_profile(
            args.name,
            create_snapshot=not getattr(args, "no_snapshot", False),
        )
        if json_output:
            output_json(
                {
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                }
            )
        else:
            icon = "✅" if result.success else "❌"
            print_fn(f"{icon} {result.message}")
        return 0 if result.success else 1

    if args.action == "create":
        if not args.name:
            print_fn("❌ Profile name required")
            return 1
        result = profile_manager_cls.capture_current_as_profile(args.name)
        if json_output:
            output_json(
                {
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                }
            )
        else:
            icon = "✅" if result.success else "❌"
            print_fn(f"{icon} {result.message}")
        return 0 if result.success else 1

    if args.action == "delete":
        if not args.name:
            print_fn("❌ Profile name required")
            return 1
        result = profile_manager_cls.delete_custom_profile(args.name)
        if json_output:
            output_json(
                {
                    "success": result.success,
                    "message": result.message,
                }
            )
        else:
            icon = "✅" if result.success else "❌"
            print_fn(f"{icon} {result.message}")
        return 0 if result.success else 1

    if args.action == "export":
        if not args.name or not args.path:
            print_fn("❌ Profile name and export path required")
            return 1
        result = profile_manager_cls.export_profile_json(args.name, args.path)
        if json_output:
            output_json(
                {
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                }
            )
        else:
            icon = "✅" if result.success else "❌"
            print_fn(f"{icon} {result.message}")
        return 0 if result.success else 1

    if args.action == "import":
        path = args.path or args.name
        if not path:
            print_fn("❌ Import path required")
            return 1
        result = profile_manager_cls.import_profile_json(path, overwrite=getattr(args, "overwrite", False))
        if json_output:
            output_json(
                {
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                }
            )
        else:
            icon = "✅" if result.success else "❌"
            print_fn(f"{icon} {result.message}")
        return 0 if result.success else 1

    if args.action == "export-all":
        path = args.path or args.name
        if not path:
            print_fn("❌ Export path required")
            return 1
        result = profile_manager_cls.export_bundle_json(
            path,
            include_builtins=getattr(args, "include_builtins", False),
        )
        if json_output:
            output_json(
                {
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                }
            )
        else:
            icon = "✅" if result.success else "❌"
            print_fn(f"{icon} {result.message}")
        return 0 if result.success else 1

    if args.action == "import-all":
        path = args.path or args.name
        if not path:
            print_fn("❌ Import bundle path required")
            return 1
        result = profile_manager_cls.import_bundle_json(path, overwrite=getattr(args, "overwrite", False))
        if json_output:
            output_json(
                {
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                }
            )
        else:
            icon = "✅" if result.success else "❌"
            print_fn(f"{icon} {result.message}")
        return 0 if result.success else 1

    return 1
