"""Mandatory Tests for Audit Logging.

Requirements:
- Skill version creation and activation must be audit logged.
- Audit record contains organization, actor, event and version.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_audit_record_contains_organization_actor_event_and_version(
    client: AsyncClient, abc_owner_headers: dict
):
    """
    Verifies that creating a skill draft, adding an immutable version, and activating it
    all produce audit log records containing:
    1. organization_id
    2. actor_id and actor_role
    3. event_type
    4. version_number
    """
    # 1. Create skill draft
    create_payload = {
        "name": "Audit Tracked Skill",
        "department": "operations",
        "system_prompt": "Audit testing prompt v1.",
        "requested_tools": ["track_equipment"],
    }
    create_res = await client.post("/api/v1/skills", json=create_payload, headers=abc_owner_headers)
    assert create_res.status_code == 201
    skill_id = create_res.json()["id"]

    # 2. Add version 2
    v2_payload = {
        "system_prompt": "Audit testing prompt v2 with extra analytics.",
        "description": "Version 2 description.",
        "requested_tools": ["track_equipment", "generate_daily_report"],
    }
    v2_res = await client.post(
        f"/api/v1/skills/{skill_id}/versions",
        json=v2_payload,
        headers=abc_owner_headers,
    )
    assert v2_res.status_code == 201

    # 3. Activate version 2
    act_res = await client.post(
        f"/api/v1/skills/{skill_id}/activate",
        json={"version_number": 2},
        headers=abc_owner_headers,
    )
    assert act_res.status_code == 200

    # 4. Fetch audit logs for the organization
    logs_res = await client.get("/api/v1/audit-logs", headers=abc_owner_headers)
    assert logs_res.status_code == 200
    audit_logs = logs_res.json()

    assert len(audit_logs) >= 3

    # Check activation log record
    activation_log = next(
        (log for log in audit_logs if log["event_type"] == "SKILL_ACTIVATED" and log["resource_id"] == skill_id),
        None,
    )
    assert activation_log is not None
    assert activation_log["organization_id"] == "org_abc"
    assert activation_log["actor_id"] == "alice_owner"
    assert activation_log["actor_role"] == "owner"
    assert activation_log["version_number"] == 2
    assert activation_log["created_at"] is not None

    # Check version creation log record
    version_log = next(
        (log for log in audit_logs if log["event_type"] == "SKILL_VERSION_CREATED" and log["version_number"] == 2),
        None,
    )
    assert version_log is not None
    assert version_log["organization_id"] == "org_abc"
    assert version_log["actor_id"] == "alice_owner"
    assert version_log["version_number"] == 2

    # Check draft creation log record
    draft_log = next(
        (log for log in audit_logs if log["event_type"] == "SKILL_DRAFT_CREATED" and log["resource_id"] == skill_id),
        None,
    )
    assert draft_log is not None
    assert draft_log["organization_id"] == "org_abc"
    assert draft_log["actor_id"] == "alice_owner"
    assert draft_log["version_number"] == 1


@pytest.mark.asyncio
async def test_cross_tenant_access_attempt_is_audit_logged(
    client: AsyncClient, abc_owner_headers: dict, xyz_owner_headers: dict
):
    """
    Verifies that attempting cross-organization access generates an audit security event.
    """
    # Org A creates a skill
    create_res = await client.post(
        "/api/v1/skills",
        json={
            "name": "Classified ABC Operations",
            "department": "operations",
            "system_prompt": "Top secret ABC construction scheduling.",
            "requested_tools": ["summarize_schedule"],
        },
        headers=abc_owner_headers,
    )
    skill_id = create_res.json()["id"]

    # Org B attempts to read Org A's skill
    await client.get(f"/api/v1/skills/{skill_id}", headers=xyz_owner_headers)

    # Check Org B's audit log to verify the intrusion attempt was recorded
    logs_res = await client.get("/api/v1/audit-logs", headers=xyz_owner_headers)
    assert logs_res.status_code == 200
    xyz_logs = logs_res.json()
    assert any(log["event_type"] == "CROSS_TENANT_ACCESS_DENIED" for log in xyz_logs)
