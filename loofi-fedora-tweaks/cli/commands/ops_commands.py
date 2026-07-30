"""Operations-oriented CLI handlers extracted from cli.main."""

from typing import Callable


def handle_cleanup(args, run_operation: Callable, cleanup_ops_cls) -> int:
    """Retain the legacy import surface without direct execution authority."""
    del args, run_operation, cleanup_ops_cls
    return 1


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
    if args.action in {"power", "audio", "battery"}:
        print_fn("Use the command's Action Center plan path.")
        return 1
    return 1


def handle_advanced(args, print_fn: Callable[[str], None], advanced_ops_cls) -> int:
    """Retain the legacy import surface without direct execution authority."""
    del advanced_ops_cls
    if args.action in {"dnf-tweaks", "bbr", "gamemode", "swappiness"}:
        print_fn("Use the command's Action Center plan path.")
        return 1
    return 1


def handle_network(args, print_fn: Callable[[str], None], network_ops_cls) -> int:
    """Retain the legacy import surface without direct execution authority."""
    del network_ops_cls
    if args.action == "dns":
        print_fn("Use the command's Action Center plan path.")
    return 1
