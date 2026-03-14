"""Insight-oriented CLI handlers extracted from cli.main."""


def handle_ai_models(args, json_output, output_json, print_fn, ai_model_manager_cls, recommended_models) -> int:
    """Handle AI models subcommand."""
    if args.action == "list":
        installed = ai_model_manager_cls.get_installed_models()
        if json_output:
            output_json({"installed": installed, "recommended": list(recommended_models.keys())})
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   AI Models")
            print_fn("═══════════════════════════════════════════")
            print_fn("\nInstalled:")
            if not installed:
                print_fn("  (none - install Ollama first)")
            else:
                for model in installed:
                    print_fn(f"  ✅ {model}")
            print_fn("\nRecommended:")
            for name, info in recommended_models.items():
                status = "✅" if name in installed else "⚪"
                print_fn(f"  {status} {name} - {info.get('description', '')}")
        return 0

    if args.action == "recommend":
        model = ai_model_manager_cls.get_recommended_model(ai_model_manager_cls.get_system_ram())
        if json_output:
            output_json({"recommended": model})
        else:
            if model:
                print_fn(f"Recommended model for this system: {model}")
            else:
                print_fn("Unable to determine recommended model")
        return 0

    return 1


def handle_security_audit(json_output, output_json, print_fn, port_auditor_cls) -> int:
    """Handle security-audit subcommand."""
    score_data = port_auditor_cls.get_security_score()

    if json_output:
        output_json(score_data)
    else:
        score = score_data["score"]
        rating = score_data["rating"]

        if score >= 90:
            icon = "🟢"
        elif score >= 70:
            icon = "🟡"
        elif score >= 50:
            icon = "🟠"
        else:
            icon = "🔴"

        print_fn("═══════════════════════════════════════════")
        print_fn("   Security Audit")
        print_fn("═══════════════════════════════════════════")
        print_fn(f"\n{icon} Security Score: {score}/100 ({rating})")
        print_fn(f"\n📊 Open Ports: {score_data['open_ports']}")
        print_fn(f"⚠️  Risky Ports: {score_data['risky_ports']}")

        fw_status = "Running" if port_auditor_cls.is_firewalld_running() else "Not Running"
        fw_icon = "✅" if port_auditor_cls.is_firewalld_running() else "❌"
        print_fn(f"{fw_icon} Firewall: {fw_status}")

        if score_data["recommendations"]:
            print_fn("\n📋 Recommendations:")
            for rec in score_data["recommendations"]:
                print_fn(f"   • {rec}")

    return 0
