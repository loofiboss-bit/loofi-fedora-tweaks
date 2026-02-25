"""
Agent automation command handler.
"""


def _resolve_instance(target):
    """Return instance for singleton-style classes or return object as-is."""
    instance_fn = getattr(target, "instance", None)
    if callable(instance_fn):
        return instance_fn()
    if isinstance(target, type):
        return target()
    return target


def handle_agent(
    args,
    json_output,
    output_json,
    print_fn,
    run_operation,
    agent_registry_cls,
    agent_scheduler_cls,
    agent_planner_cls,
    agent_notifier_cls,
):
    """Handle agent subcommand."""
    if args.action == "list":
        registry = _resolve_instance(agent_registry_cls)
        agents = registry.list_agents()
        if json_output:
            output_json(
                [
                    {
                        "id": getattr(a, "id", getattr(a, "agent_id", "")),
                        "name": a.name,
                        "enabled": a.enabled,
                        "description": getattr(a, "description", ""),
                    }
                    for a in agents
                ]
            )
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Automation Agents")
            print_fn("═══════════════════════════════════════════")
            if not agents:
                print_fn("\n  (no agents registered)")
            for a in agents:
                marker = "✅" if a.enabled else "❌"
                agent_id = getattr(a, "id", getattr(a, "agent_id", ""))
                print_fn(f"  {marker} {a.name} ({agent_id})")
                description = getattr(a, "description", "")
                if description:
                    print_fn(f"      Description: {description}")
        return 0

    elif args.action == "status":
        registry = _resolve_instance(agent_registry_cls)
        if not hasattr(args, "agent_id") or not args.agent_id:
            summary = registry.get_agent_summary()
            if json_output:
                output_json(summary)
            else:
                print_fn(f"\n  Total Agents: {summary.get('total_agents', 0)}")
                print_fn(f"  Enabled: {summary.get('enabled', 0)}")
                print_fn(f"  Disabled: {summary.get('disabled', 0)}")
            return 0
        state = registry.get_state(args.agent_id)
        if json_output:
            output_json(vars(state))
        else:
            print_fn(f"\n  Agent ID: {args.agent_id}")
            print_fn(f"  Enabled: {state.enabled}")
            print_fn(f"  Last Run: {state.last_run if getattr(state, 'last_run', None) else 'Never'}")
            action_count = getattr(state, "action_count", getattr(state, "run_count", 0))
            print_fn(f"  Actions: {action_count}")
        return 0

    elif args.action in ("enable", "disable"):
        if not hasattr(args, "agent_id") or not args.agent_id:
            print_fn("❌ Agent ID required")
            return 1
        registry = _resolve_instance(agent_registry_cls)
        if args.action == "enable":
            success = registry.enable_agent(args.agent_id)
        else:
            success = registry.disable_agent(args.agent_id)
        if success:
            print_fn(f"✅ Agent {args.agent_id} {args.action}d")
        else:
            print_fn(f"❌ Failed to {args.action} agent {args.agent_id}")
        return 0 if success else 1

    elif args.action == "run":
        if not hasattr(args, "agent_id") or not args.agent_id:
            print_fn("❌ Agent ID required")
            return 1
        print_fn(f"🚀 Running agent: {args.agent_id}")
        scheduler = _resolve_instance(agent_scheduler_cls)
        run_now = getattr(scheduler, "run_agent_now", None)
        if run_now is not None:
            result = run_now(args.agent_id)
        else:
            planner = _resolve_instance(agent_planner_cls)
            execute_fn = getattr(planner, "execute_agent", None)
            if execute_fn is None:
                print_fn("❌ Agent runner unavailable")
                return 1
            result = execute_fn(args.agent_id)
        if isinstance(result, list):
            success = all(getattr(item, "success", False) for item in result) if result else True
            if json_output:
                output_json([vars(item) for item in result])
            else:
                print_fn(f"  Results: {len(result)} actions")
                print_fn(f"  Status: {'success' if success else 'failed'}")
            return 0 if success else 1

        status = getattr(result, "status", "failed")
        if json_output:
            output_json(vars(result))
        else:
            print_fn(f"  Status: {status}")
            if hasattr(result, 'duration'):
                print_fn(f"  Duration: {result.duration}s")
            if hasattr(result, 'errors') and result.errors:
                print_fn(f"  Errors: {', '.join(result.errors)}")
        return 0 if status == "success" else 1

    elif args.action == "schedule":
        scheduler = _resolve_instance(agent_scheduler_cls)
        schedules = scheduler.get_schedules()
        if json_output:
            output_json([{"agent_id": s.agent_id, "cron": s.cron_expression, "enabled": s.enabled} for s in schedules])
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Agent Schedules")
            print_fn("═══════════════════════════════════════════")
            if not schedules:
                print_fn("\n  (no schedules configured)")
            for s in schedules:
                marker = "✅" if s.enabled else "❌"
                print_fn(f"  {marker} {s.agent_id}: {s.cron_expression}")
        return 0

    elif args.action == "notifications":
        notifier = _resolve_instance(agent_notifier_cls)
        notifs = notifier.get_recent_notifications(limit=20)
        if json_output:
            output_json(
                [
                    {
                        "timestamp": n.timestamp,
                        "agent_id": n.agent_id,
                        "message": n.message,
                        "severity": n.severity,
                    }
                    for n in notifs
                ]
            )
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Agent Notifications")
            print_fn("═══════════════════════════════════════════")
            if not notifs:
                print_fn("\n  (no recent notifications)")
            for n in notifs:
                import time

                ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(n.timestamp))
                print_fn(f"  [{n.severity}] {ts} — {n.agent_id}: {n.message}")
        return 0

    elif args.action == "create":
        if not hasattr(args, "goal") or not args.goal:
            print_fn("❌ Agent goal required (use --goal)")
            return 1
        from utils.agents import AgentConfig, AgentType, AgentTrigger, TriggerType
        import uuid

        agent_id = str(uuid.uuid4())[:8]
        config = AgentConfig(
            agent_id=agent_id,
            name=f"cli-agent-{agent_id}",
            agent_type=AgentType.CUSTOM,
            description=f"CLI-created agent for goal: {args.goal}",
            triggers=[AgentTrigger(trigger_type=TriggerType.MANUAL)],
            actions=[],
            enabled=True,
            settings={"goal": args.goal},
        )
        registry = _resolve_instance(agent_registry_cls)
        registered = registry.register_agent(config)
        created_id = getattr(registered, "id", getattr(registered, "agent_id", agent_id))
        print_fn(f"✅ Created agent: {created_id} ({registered.name})")
        return 0

    elif args.action == "remove":
        if not hasattr(args, "agent_id") or not args.agent_id:
            print_fn("❌ Agent ID required")
            return 1
        registry = _resolve_instance(agent_registry_cls)
        success = registry.remove_agent(args.agent_id)
        if success:
            print_fn(f"✅ Removed agent {args.agent_id}")
        else:
            print_fn(f"❌ Failed to remove agent {args.agent_id}")
        return 0 if success else 1

    elif args.action == "logs":
        registry = _resolve_instance(agent_registry_cls)
        activity = registry.get_recent_activity(limit=20)
        target_agent_id = getattr(args, "agent_id", None)
        if target_agent_id:
            filtered = [a for a in activity if a.get("agent_id") == target_agent_id]
        else:
            filtered = activity
        if json_output:
            output_json(filtered)
        else:
            if not filtered:
                print_fn("  No recent activity")
            for act in filtered:
                import time
                ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(act.get("timestamp", 0)))
                status = act.get("status", "unknown")
                print_fn(f"  [{ts}] {status}")
        return 0

    elif args.action == "templates":
        from core.agents import GOAL_TEMPLATES
        if json_output:
            output_json([{"name": k, "description": v} for k, v in GOAL_TEMPLATES.items()])
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Agent Templates")
            print_fn("═══════════════════════════════════════════")
            for name, desc in GOAL_TEMPLATES.items():
                print_fn(f"  {name}: {desc}")
        return 0

    elif args.action == "notify":
        if not hasattr(args, "agent_id") or not args.agent_id:
            print_fn("❌ Agent ID required")
            return 1
        webhook = getattr(args, "webhook", None)
        min_severity = getattr(args, "min_severity", "low")
        if not webhook:
            print_fn("❌ --webhook URL required")
            return 1

        registry = _resolve_instance(agent_registry_cls)
        agent = registry.get_agent(args.agent_id)
        if not agent:
            print_fn(f"❌ Agent not found: {args.agent_id}")
            return 1

        from core.agents.agent_notifications import AgentNotifier

        if not AgentNotifier.validate_webhook_url(webhook):
            print_fn("❌ Invalid webhook URL")
            return 1

        from core.agents import AgentNotificationConfig
        config = AgentNotificationConfig(
            webhook_url=webhook,
            min_severity=min_severity,
        )

        if not isinstance(agent.notification_config, dict):
            agent.notification_config = {}
        agent.notification_config.update(config.to_dict())
        save_fn = getattr(registry, "save", None)
        if callable(save_fn):
            save_fn()

        print_fn(f"✅ Configured notifications for {args.agent_id}")
        return 0

    return 1
