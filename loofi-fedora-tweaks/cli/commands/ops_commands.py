"""Operations-oriented CLI handlers extracted from cli.main."""

from typing import Callable


def handle_cleanup(args, run_operation: Callable, cleanup_ops_cls) -> int:
    """Handle cleanup subcommand."""
    if args.action == "all":
        actions = ["dnf", "journal", "trim"]
    else:
        actions = [args.action]

    success = True
    for action in actions:
        if action == "dnf":
            success &= run_operation(cleanup_ops_cls.clean_dnf_cache())
        elif action == "journal":
            success &= run_operation(cleanup_ops_cls.vacuum_journal(args.days))
        elif action == "trim":
            success &= run_operation(cleanup_ops_cls.trim_ssd())
        elif action == "autoremove":
            success &= run_operation(cleanup_ops_cls.autoremove())
        elif action == "rpmdb":
            success &= run_operation(cleanup_ops_cls.rebuild_rpmdb())

    return 0 if success else 1


def handle_tweak(
    args,
    json_output: bool,
    output_json: Callable,
    print_fn: Callable[[str], None],
    run_operation: Callable,
    tweak_ops_cls,
    system_manager_cls,
) -> int:
    """Handle tweak subcommand."""
    if args.action == "power":
        return 0 if run_operation(tweak_ops_cls.set_power_profile(args.profile)) else 1
    if args.action == "audio":
        return 0 if run_operation(tweak_ops_cls.restart_audio()) else 1
    if args.action == "battery":
        result = tweak_ops_cls.set_battery_limit(args.limit)
        print_fn(f"{'✅' if result.success else '❌'} {result.message}")
        return 0 if result.success else 1
    if args.action == "status":
        profile = tweak_ops_cls.get_power_profile()
        if json_output:
            output_json(
                {
                    "power_profile": profile,
                    "system_type": "Atomic" if system_manager_cls.is_atomic() else "Traditional",
                }
            )
        else:
            print_fn(f"⚡ Power Profile: {profile}")
            print_fn(f"💻 System: {'Atomic' if system_manager_cls.is_atomic() else 'Traditional'} Fedora")
        return 0
    return 1


def handle_advanced(args, print_fn: Callable[[str], None], advanced_ops_cls) -> int:
    """Handle advanced subcommand."""
    if args.action == "dnf-tweaks":
        result = advanced_ops_cls.apply_dnf_tweaks()
        print_fn(f"{'✅' if result.success else '❌'} {result.message}")
        return 0 if result.success else 1
    if args.action == "bbr":
        result = advanced_ops_cls.enable_tcp_bbr()
        print_fn(f"{'✅' if result.success else '❌'} {result.message}")
        return 0 if result.success else 1
    if args.action == "gamemode":
        result = advanced_ops_cls.install_gamemode()
        print_fn(f"{'✅' if result.success else '❌'} {result.message}")
        return 0 if result.success else 1
    if args.action == "swappiness":
        result = advanced_ops_cls.set_swappiness(args.value)
        print_fn(f"{'✅' if result.success else '❌'} {result.message}")
        return 0 if result.success else 1
    return 1


def handle_network(args, print_fn: Callable[[str], None], network_ops_cls) -> int:
    """Handle network subcommand."""
    if args.action == "dns":
        result = network_ops_cls.set_dns(args.provider)
        print_fn(f"{'✅' if result.success else '❌'} {result.message}")
        return 0 if result.success else 1
    return 1
