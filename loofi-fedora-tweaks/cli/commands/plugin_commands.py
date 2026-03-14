"""
Plugin command handlers: plugins, plugin-marketplace.
"""

import sys


def handle_plugins(args, json_output, output_json, print_fn, plugin_loader_cls):
    """Manage plugins."""
    loader = plugin_loader_cls()

    if args.action == "list":
        plugins = loader.list_plugins()
        if json_output:
            output_json({"plugins": plugins})
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Plugins")
            print_fn("═══════════════════════════════════════════")
            if not plugins:
                print_fn("\n(no plugins found)")
                return 0
            for plugin in plugins:
                name = plugin["name"]
                enabled = plugin["enabled"]
                manifest = plugin.get("manifest") or {}
                status = "✅" if enabled else "❌"
                version = manifest.get("version", "unknown")
                desc = manifest.get("description", "")
                print_fn(f"{status} {name} v{version}")
                if desc:
                    print_fn(f"   {desc}")
        return 0

    if args.action in ("enable", "disable"):
        if not args.name:
            print_fn("❌ Plugin name required")
            return 1
        enabled = args.action == "enable"
        loader.set_enabled(args.name, enabled)
        if json_output:
            output_json({"plugin": args.name, "enabled": enabled})
        else:
            print_fn(f"{'✅' if enabled else '❌'} {args.name} {'enabled' if enabled else 'disabled'}")
        return 0

    return 1


def handle_plugin_marketplace(
    args,
    json_output,
    output_json,
    print_fn,
    json_module,
    plugin_marketplace_cls,
    plugin_installer_cls,
):
    """Plugin marketplace operations."""
    marketplace = plugin_marketplace_cls()
    installer = plugin_installer_cls()
    use_json = getattr(args, "json", False) or json_output

    def _resolve_plugin_id():
        """Accept both modern `plugin_id` and legacy `plugin` argparse names."""
        plugin_id = getattr(args, "plugin_id", None)
        if isinstance(plugin_id, str) and plugin_id:
            return plugin_id
        legacy = getattr(args, "plugin", None)
        if isinstance(legacy, str) and legacy:
            return legacy
        return None

    if args.action == "search":
        query = getattr(args, "query", None) or ""
        category = getattr(args, "category", None)
        result = marketplace.search(query=query, category=category)

        if not result.success:
            print(f"Error: {result.error}", file=sys.stderr)
            return 1

        plugins = result.data or []
        if use_json:
            data = [
                {
                    "id": p.id,
                    "name": p.name,
                    "version": p.version,
                    "author": p.author,
                    "category": p.category,
                    "description": p.description,
                    "verified_publisher": bool(getattr(p, "verified_publisher", False)),
                    "publisher_id": getattr(p, "publisher_id", None),
                    "publisher_badge": getattr(p, "publisher_badge", None),
                }
                for p in plugins
            ]
            print(json_module.dumps({"plugins": data, "count": len(data)}, indent=2, default=str))
        else:
            if not plugins:
                print("No plugins found")
                return 0
            for p in plugins:
                print(f"📦 {p.name} v{p.version} by {p.author}")
                print(f"   Category: {p.category}")
                if getattr(p, "verified_publisher", False):
                    badge = getattr(p, "publisher_badge", None) or "verified"
                    publisher_id = getattr(p, "publisher_id", None)
                    publisher_suffix = f" ({publisher_id})" if publisher_id else ""
                    print(f"   Publisher: {badge}{publisher_suffix}")
                print(f"   {p.description}")
                print()
        return 0

    if args.action == "info":
        plugin_id = _resolve_plugin_id()
        if not plugin_id:
            print("Error: Plugin ID required", file=sys.stderr)
            return 1

        result = marketplace.get_plugin(plugin_id)

        if not result.success:
            print(f"Error: {result.error}", file=sys.stderr)
            return 1

        plugin = result.data[0] if isinstance(result.data, list) else result.data

        if use_json:
            data = {
                "id": plugin.id,
                "name": plugin.name,
                "version": plugin.version,
                "author": plugin.author,
                "category": plugin.category,
                "description": plugin.description,
                "homepage": getattr(plugin, "homepage", None),
                "license": getattr(plugin, "license", None),
                "verified_publisher": bool(getattr(plugin, "verified_publisher", False)),
                "publisher_id": getattr(plugin, "publisher_id", None),
                "publisher_badge": getattr(plugin, "publisher_badge", None),
            }
            print(json_module.dumps(data, indent=2, default=str))
        else:
            print(f"{plugin.name} v{plugin.version}")
            print(f"Author:      {plugin.author}")
            print(f"Category:    {plugin.category}")
            print(f"Description: {plugin.description}")
            if getattr(plugin, "verified_publisher", False):
                badge = getattr(plugin, "publisher_badge", None) or "verified"
                publisher_id = getattr(plugin, "publisher_id", None)
                if publisher_id:
                    print(f"Publisher:   {badge} ({publisher_id})")
                else:
                    print(f"Publisher:   {badge}")
            if getattr(plugin, "homepage", None):
                print(f"Homepage:    {plugin.homepage}")
        return 0

    if args.action == "install":
        plugin_id = _resolve_plugin_id()
        if not plugin_id:
            print("Error: Plugin ID required", file=sys.stderr)
            return 1

        # Fetch plugin info
        info_result = marketplace.get_plugin(plugin_id)
        if not info_result.success:
            print(f"Error: {info_result.error}", file=sys.stderr)
            return 1

        plugin = info_result.data[0] if isinstance(info_result.data, list) else info_result.data

        # Check permissions consent
        permissions = getattr(plugin, "requires", None) or []
        accept = getattr(args, "accept_permissions", False)
        if permissions and not accept:
            print(f"Plugin '{plugin.name}' requires permissions: {', '.join(permissions)}")
            print("Re-run with --accept-permissions to install")
            return 1

        result = installer.install(plugin_id)

        if result.success:
            if use_json:
                print(
                    json_module.dumps(
                        {"status": "success", "plugin": plugin_id},
                        indent=2,
                        default=str,
                    )
                )
            else:
                print(f"Successfully installed '{plugin.name}'")
            return 0
        else:
            print(f"Error: Installation failed: {result.error}", file=sys.stderr)
            return 1

    if args.action == "reviews":
        plugin_id = _resolve_plugin_id()
        if not plugin_id:
            print("Error: Plugin ID required", file=sys.stderr)
            return 1

        limit = getattr(args, "limit", 20)
        offset = getattr(args, "offset", 0)
        result = marketplace.fetch_reviews(plugin_id=plugin_id, limit=limit, offset=offset)

        if not result.success:
            print(f"Error: {result.error}", file=sys.stderr)
            return 1

        reviews = result.data or []
        if use_json:
            data = [
                {
                    "plugin_id": r.plugin_id,
                    "reviewer": r.reviewer,
                    "rating": r.rating,
                    "title": r.title,
                    "comment": r.comment,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
                for r in reviews
            ]
            print(
                json_module.dumps(
                    {"plugin_id": plugin_id, "reviews": data, "count": len(data)},
                    indent=2,
                    default=str,
                )
            )
        else:
            if not reviews:
                print("No reviews found")
                return 0
            for review in reviews:
                print(f"★ {review.rating}/5 by {review.reviewer}")
                if review.title:
                    print(f"  {review.title}")
                if review.comment:
                    print(f"  {review.comment}")
                if review.created_at:
                    print(f"  Date: {review.created_at}")
                print()
        return 0

    if args.action == "review-submit":
        plugin_id = _resolve_plugin_id()
        if not plugin_id:
            print("Error: Plugin ID required", file=sys.stderr)
            return 1

        reviewer = getattr(args, "reviewer", "")
        rating = getattr(args, "rating", None)
        title = getattr(args, "title", "") or ""
        comment = getattr(args, "comment", "") or ""

        result = marketplace.submit_review(
            plugin_id=plugin_id,
            reviewer=reviewer,
            rating=rating,
            title=title,
            comment=comment,
        )

        if not result.success:
            print(f"Error: {result.error}", file=sys.stderr)
            return 1

        if use_json:
            print(
                json_module.dumps(
                    {
                        "status": "success",
                        "plugin_id": plugin_id,
                        "review": result.data,
                    },
                    indent=2,
                    default=str,
                )
            )
        else:
            print(f"Review submitted for '{plugin_id}'")
        return 0

    if args.action == "rating":
        plugin_id = _resolve_plugin_id()
        if not plugin_id:
            print("Error: Plugin ID required", file=sys.stderr)
            return 1

        result = marketplace.get_rating_aggregate(plugin_id=plugin_id)
        if not result.success:
            print(f"Error: {result.error}", file=sys.stderr)
            return 1

        aggregate = result.data
        if use_json:
            print(
                json_module.dumps(
                    {
                        "plugin_id": aggregate.plugin_id,
                        "average_rating": aggregate.average_rating,
                        "rating_count": aggregate.rating_count,
                        "review_count": aggregate.review_count,
                        "breakdown": aggregate.breakdown,
                    },
                    indent=2,
                    default=str,
                )
            )
        else:
            print(f"Rating for {aggregate.plugin_id}: {aggregate.average_rating:.2f}/5")
            print(f"Ratings: {aggregate.rating_count}")
            print(f"Reviews: {aggregate.review_count}")
            if aggregate.breakdown:
                print("Breakdown:")
                for stars in sorted(aggregate.breakdown.keys(), reverse=True):
                    print(f"  {stars}★: {aggregate.breakdown[stars]}")
        return 0

    if args.action == "uninstall":
        plugin_id = _resolve_plugin_id()
        if not plugin_id:
            print("Error: Plugin ID required", file=sys.stderr)
            return 1

        result = installer.uninstall(plugin_id)

        if result.success:
            if use_json:
                print(
                    json_module.dumps(
                        {"status": "success", "plugin": plugin_id},
                        indent=2,
                        default=str,
                    )
                )
            else:
                print(f"Successfully uninstalled '{plugin_id}'")
            return 0
        else:
            print(f"Error: {result.error}", file=sys.stderr)
            return 1

    if args.action == "update":
        plugin_id = _resolve_plugin_id()
        if not plugin_id:
            print("Error: Plugin ID required", file=sys.stderr)
            return 1

        # Check if update is available first
        check = installer.check_update(plugin_id)
        if check.success and check.data and not check.data.get("update_available", True):
            print(f"Plugin '{plugin_id}' is already up to date")
            return 0

        result = installer.update(plugin_id)

        if result.success:
            if use_json:
                print(
                    json_module.dumps(
                        {"status": "success", "plugin": plugin_id},
                        indent=2,
                        default=str,
                    )
                )
            else:
                print(f"Successfully updated '{plugin_id}'")
            return 0
        else:
            print(f"Error: {result.error}", file=sys.stderr)
            return 1

    if args.action == "list-installed":
        result = installer.list_installed()

        plugins = result.data or []
        if use_json:
            print(json_module.dumps(plugins, indent=2, default=str))
        else:
            if not plugins:
                print("No plugins installed")
                return 0
            for p in plugins:
                name = p.get("name", p.get("id", "unknown"))
                version = p.get("version", "unknown")
                print(f"📦 {name} v{version}")
        return 0

    return 1
