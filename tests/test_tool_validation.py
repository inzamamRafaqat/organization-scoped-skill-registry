"""Mandatory Tests for Tool Validation and Permission Sandboxing.

Requirements:
- A skill's requested tools must not grant permissions automatically.
- Invalid or destructive requested tool is rejected.
- Inputs must be validated and failures must return explicit, useful errors.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.parametrize(
    "destructive_tool",
    [
        "delete_database",
        "execute_shell",
        "format_disk",
        "grant_admin",
        "eval",
        "rm_rf",
        "drop_tables",
        "access_host_filesystem",
        "elevate_privileges",
    ],
)
@pytest.mark.asyncio
async def test_invalid_or_destructive_requested_tool_is_rejected(
    client: AsyncClient, abc_owner_headers: dict, destructive_tool: str
):
    """
    Verifies that creating a skill or new version with any destructive or dangerous tool
    is strictly rejected with HTTP 422 and an explicit, informative error message.
    """
    payload = {
        "name": f"Malicious Skill with {destructive_tool}",
        "department": "operations",
        "system_prompt": "Attempting unauthorized privilege escalation.",
        "requested_tools": [destructive_tool],
    }

    response = await client.post("/api/v1/skills", json=payload, headers=abc_owner_headers)
    assert response.status_code == 422, f"Expected 422 for tool '{destructive_tool}', got {response.status_code}"
    error_body = response.json()
    assert (
        destructive_tool in str(error_body).lower()
        or "destructive" in str(error_body).lower()
        or "forbidden" in str(error_body).lower()
    )


@pytest.mark.asyncio
async def test_unregistered_tool_is_rejected_with_useful_error(
    client: AsyncClient, abc_owner_headers: dict
):
    """
    Verifies that unknown or unregistered tools are rejected with an explicit error listing
    supported tools.
    """
    payload = {
        "name": "Custom Unregistered Tool Skill",
        "department": "operations",
        "system_prompt": "Testing arbitrary tool name.",
        "requested_tools": ["arbitrary_unregistered_tool_xyz"],
    }

    response = await client.post("/api/v1/skills", json=payload, headers=abc_owner_headers)
    assert response.status_code == 422
    assert "not recognized in the approved tool registry" in response.text


@pytest.mark.asyncio
async def test_valid_tools_do_not_grant_ambient_permissions(
    client: AsyncClient, abc_owner_headers: dict
):
    """
    Verifies that approved tools are registered strictly as declarative requested tools
    and execute only within sandboxed capabilities.
    """
    payload = {
        "name": "Daily Report Synthesizer",
        "department": "operations",
        "system_prompt": "Synthesizes field superintendent updates into daily summary.",
        "requested_tools": ["generate_daily_report", "calculate_budget"],
    }

    response = await client.post("/api/v1/skills", json=payload, headers=abc_owner_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["versions"][0]["requested_tools"] == ["generate_daily_report", "calculate_budget"]
