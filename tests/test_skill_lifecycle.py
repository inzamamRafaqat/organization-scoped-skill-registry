"""Mandatory Tests for Skill Lifecycle and Activation Authorization.

Requirements:
- Skill lifecycle: draft → active → disabled.
- Only an organization owner can activate a skill.
- Non-owner activation is denied.
- Draft skill cannot execute or load as active.
- Disabled skill is excluded from runtime selection.
- Duplicate activation request is safe and idempotent.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_non_owner_activation_denied(
    client: AsyncClient, abc_owner_headers: dict, abc_member_headers: dict
):
    """
    Verifies that a non-owner actor (e.g. member/engineer) within the same organization
    is forbidden from activating a skill.
    """
    # 1. Create a draft skill
    payload = {
        "name": "Subcontractor Invoice Parser",
        "department": "finance",
        "system_prompt": "Parses subcontractor billing invoices against contract terms.",
        "requested_tools": ["calculate_budget"],
    }
    create_res = await client.post("/api/v1/skills", json=payload, headers=abc_owner_headers)
    assert create_res.status_code == 201
    skill_id = create_res.json()["id"]

    # 2. Member tries to activate skill -> MUST BE FORBIDDEN (403)
    activate_res = await client.post(
        f"/api/v1/skills/{skill_id}/activate",
        json={"version_number": 1},
        headers=abc_member_headers,
    )
    assert activate_res.status_code == 403, (
        f"Expected 403 Forbidden for non-owner activation, got {activate_res.status_code}"
    )
    assert "owner" in activate_res.text.lower()


@pytest.mark.asyncio
async def test_draft_skill_cannot_execute_or_load_as_active(
    client: AsyncClient, abc_owner_headers: dict
):
    """
    Verifies that a skill in 'draft' status:
    1. Is excluded from active department runtime selection.
    2. Fails runtime execution attempts.
    """
    payload = {
        "name": "Heavy Machinery Tracker",
        "department": "operations",
        "system_prompt": "Monitors excavators and cranes utilization.",
        "requested_tools": ["track_equipment"],
    }
    create_res = await client.post("/api/v1/skills", json=payload, headers=abc_owner_headers)
    assert create_res.status_code == 201
    skill_id = create_res.json()["id"]

    # 1. Department active runtime lookup should NOT include draft skill
    dept_res = await client.get("/api/v1/skills/runtime/department/operations", headers=abc_owner_headers)
    assert dept_res.status_code == 200
    active_skills = dept_res.json()
    assert all(s["id"] != skill_id for s in active_skills)

    # 2. Attempting to execute draft skill runtime must fail
    exec_res = await client.post(
        f"/api/v1/skills/{skill_id}/execute",
        json={"input_text": "Check status of Crane #4"},
        headers=abc_owner_headers,
    )
    assert exec_res.status_code == 400
    assert "draft" in exec_res.text.lower()


@pytest.mark.asyncio
async def test_disabled_skill_excluded_from_runtime_selection(
    client: AsyncClient, abc_owner_headers: dict
):
    """
    Verifies that disabling an active skill immediately removes it from department runtime selection
    and disables its runtime execution.
    """
    # 1. Create draft and activate it
    payload = {
        "name": "OSHA Safety Checklist",
        "department": "safety",
        "system_prompt": "Daily OSHA safety compliance auditing.",
        "requested_tools": ["check_safety_compliance"],
    }
    create_res = await client.post("/api/v1/skills", json=payload, headers=abc_owner_headers)
    assert create_res.status_code == 201
    skill_id = create_res.json()["id"]

    activate_res = await client.post(
        f"/api/v1/skills/{skill_id}/activate",
        headers=abc_owner_headers,
    )
    assert activate_res.status_code == 200
    assert activate_res.json()["status"] == "active"

    # Verify present in department runtime selection
    dept_res = await client.get("/api/v1/skills/runtime/department/safety", headers=abc_owner_headers)
    assert any(s["id"] == skill_id for s in dept_res.json())

    # 2. Disable the skill
    disable_res = await client.post(f"/api/v1/skills/{skill_id}/disable", headers=abc_owner_headers)
    assert disable_res.status_code == 200
    assert disable_res.json()["status"] == "disabled"

    # 3. Verify excluded from department runtime selection
    dept_after_res = await client.get("/api/v1/skills/runtime/department/safety", headers=abc_owner_headers)
    assert all(s["id"] != skill_id for s in dept_after_res.json())

    # 4. Verify execution fails for disabled skill
    exec_res = await client.post(
        f"/api/v1/skills/{skill_id}/execute",
        json={"input_text": "Verify hard hat zone"},
        headers=abc_owner_headers,
    )
    assert exec_res.status_code == 400
    assert "disabled" in exec_res.text.lower()


@pytest.mark.asyncio
async def test_duplicate_activation_request_is_safe_and_idempotent(
    client: AsyncClient, abc_owner_headers: dict
):
    """
    Verifies that activating an already active skill version repeatedly is safe, idempotent,
    and returns successfully with 200 OK.
    """
    # 1. Create draft
    payload = {
        "name": "Concrete Pour Schedule Coordinator",
        "department": "operations",
        "system_prompt": "Coordinates concrete mixer arrival schedules.",
        "requested_tools": ["summarize_schedule"],
    }
    create_res = await client.post("/api/v1/skills", json=payload, headers=abc_owner_headers)
    skill_id = create_res.json()["id"]

    # 2. First activation
    act1_res = await client.post(
        f"/api/v1/skills/{skill_id}/activate",
        json={"version_number": 1},
        headers=abc_owner_headers,
    )
    assert act1_res.status_code == 200
    act1_data = act1_res.json()
    assert act1_data["status"] == "active"
    first_updated_at = act1_data["updated_at"]

    # 3. Second (duplicate) activation
    act2_res = await client.post(
        f"/api/v1/skills/{skill_id}/activate",
        json={"version_number": 1},
        headers=abc_owner_headers,
    )
    assert act2_res.status_code == 200
    act2_data = act2_res.json()
    assert act2_data["status"] == "active"
    assert act2_data["current_version_id"] == act1_data["current_version_id"]
