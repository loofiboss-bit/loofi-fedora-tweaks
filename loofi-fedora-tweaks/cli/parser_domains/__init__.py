"""Domain-owned registration functions for the public CLI grammar."""

from cli.parser_domains.host import (
    register_basic_host_commands,
    register_post_agent_commands,
    register_system_management_commands,
)
from cli.parser_domains.observability import register_observability_commands
from cli.parser_domains.execution import register_execution_commands
from cli.parser_domains.specialist import register_agent_command, register_specialist_commands
from cli.parser_domains.support import register_support_commands

__all__ = [
    "register_agent_command",
    "register_basic_host_commands",
    "register_observability_commands",
    "register_execution_commands",
    "register_post_agent_commands",
    "register_specialist_commands",
    "register_support_commands",
    "register_system_management_commands",
]
