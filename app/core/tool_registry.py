"""Tool capability registry and safety validation sandbox.

Requirements:
- A skill's requested tools must not grant permissions automatically.
- Invalid or destructive requested tools must be rejected with explicit, useful errors.
"""
from typing import List, Set, Tuple


# Known safe registered tools for Jarvis AI COO domain (Operations, Construction, Governance)
APPROVED_TOOLS: Set[str] = {
    "calculate_budget",
    "generate_daily_report",
    "lookup_subcontractor",
    "summarize_schedule",
    "track_equipment",
    "check_safety_compliance",
    "estimate_materials",
    "query_inventory",
    "analyze_rfp",
}

# Blocklist of strictly forbidden destructive or dangerous tool primitives
DESTRUCTIVE_TOOLS: Set[str] = {
    "delete_database",
    "execute_shell",
    "format_disk",
    "grant_admin",
    "eval",
    "rm_rf",
    "drop_tables",
    "access_host_filesystem",
    "elevate_privileges",
    "modify_tenant_boundaries",
}


class ToolValidationError(ValueError):
    """Raised when requested tools violate security or validity policies."""
    pass


def validate_requested_tools(requested_tools: List[str]) -> None:
    """
    Validates requested tools against the tool catalog and safety sandbox.

    Rules:
    1. Tool name must be a non-empty string.
    2. Any destructive or dangerous tool is immediately rejected.
    3. Any unapproved/unknown tool is rejected with an explicit error.
    4. Note: Requesting a valid tool merely registers the capability intent;
       it does NOT grant ambient or automatic system permissions.
    """
    if not isinstance(requested_tools, list):
        raise ToolValidationError("requested_tools must be a list of tool names.")

    for tool in requested_tools:
        if not isinstance(tool, str) or not tool.strip():
            raise ToolValidationError("Each requested tool must be a non-empty string.")

        normalized = tool.strip().lower()

        # Check destructive blocklist
        if normalized in DESTRUCTIVE_TOOLS:
            raise ToolValidationError(
                f"Destructive or dangerous tool '{tool}' is strictly forbidden by security policy."
            )

        # Check approval registry
        if normalized not in APPROVED_TOOLS:
            allowed_list = ", ".join(sorted(APPROVED_TOOLS))
            raise ToolValidationError(
                f"Tool '{tool}' is not recognized in the approved tool registry. "
                f"Supported tools are: {allowed_list}"
            )
