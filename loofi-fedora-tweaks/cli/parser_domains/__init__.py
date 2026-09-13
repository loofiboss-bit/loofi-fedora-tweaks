from cli.parser_domains.host import (
    register_basic_host_commands,
    register_host_commands,
    register_post_agent_commands,
    register_system_management_commands,
)
from cli.parser_domains.observability import (
    register_activity_command,
    register_health_commands,
    register_observability_commands,
    register_troubleshooting_command,
)
from cli.parser_domains.execution import register_execution_commands
from cli.parser_domains.support import register_support_commands

__all__ = [
    "register_activity_command",
    "register_basic_host_commands",
    "register_execution_commands",
    "register_health_commands",
    "register_host_commands",
    "register_observability_commands",
    "register_post_agent_commands",
    "register_support_commands",
    "register_system_management_commands",
    "register_troubleshooting_command",
]
