"""Mandatory Tests for Tenant Isolation and Authorization.

Requirements:
- Canonical ownership key: organization_id.
- Organization A must not be able to access, modify or activate Organization B's data.
- Same-organization create/read succeeds.
- Cross-organization read is denied.
- Cross-organization update is denied.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_same_organization_create_read_succeeds(
    client: AsyncClient, abc_owner_headers: dict
):
    """
    Verifies that creating a skill draft within the same organization succeeds,
    and subsequent reading returns the exact skill data and version.
    """
    payload = {
        "name": "Daily Jobsite Log Assistant",
        "department": "operations",
        "system_prompt": "You are an AI assistant logging daily construction site progress.",
        "description": "Logs subcontractor headcounts and material deliveries.",
        "requested_tools": ["generate_daily_report", "track_equipment"],
    }

    # 1. Create draft
    create_res = await client.post("/api/v1/skills", json=payload, headers=abc_owner_headers)
    assert create_res.status_code == 201, create_res.text
    data = create_res.json()

    assert data["name"] == payload["name"]
    assert data["organization_id"] == "org_abc"
    assert data["status"] == "draft"
    assert data["created_by"] == "alice_owner"
    assert len(data["versions"]) == 1
    assert data["versions"][0]["version_number"] == 1
    assert data["versions"][0]["requested_tools"] == payload["requested_tools"]

    skill_id = data["id"]

    # 2. Read created skill using same organization actor
    read_res = await client.get(f"/api/v1/skills/{skill_id}", headers=abc_owner_headers)
    assert read_res.status_code == 200
    read_data = read_res.json()

    assert read_data["id"] == skill_id
    assert read_data["organization_id"] == "org_abc"
    assert read_data["name"] == payload["name"]


@pytest.mark.asyncio
async def test_cross_organization_read_is_denied(
    client: AsyncClient, abc_owner_headers: dict, xyz_owner_headers: dict
):
    """
    Verifies that Organization B (XYZ Builders) cannot read skills owned by Organization A (ABC Construction).
    """
    # 1. ABC Construction creates a skill
    payload = {
        "name": "ABC Proprietary Estimator",
        "department": "finance",
        "system_prompt": "Confidential cost estimation prompt for ABC projects.",
        "requested_tools": ["calculate_budget"],
    }
    create_res = await client.post("/api/v1/skills", json=payload, headers=abc_owner_headers)
    assert create_res.status_code == 201
    skill_id = create_res.json()["id"]

    # 2. XYZ Builders attempts to read ABC's skill -> MUST BE DENIED (403 or 404)
    cross_read_res = await client.get(f"/api/v1/skills/{skill_id}", headers=xyz_owner_headers)
    assert cross_read_res.status_code in (403, 404), (
        f"Expected cross-organization read to be denied (403/404), got {cross_read_res.status_code}"
    )


@pytest.mark.asyncio
async def test_cross_organization_update_is_denied(
    client: AsyncClient, abc_owner_headers: dict, xyz_owner_headers: dict
):
    """
    Verifies that Organization B (XYZ Builders) cannot update or create versions for Organization A's skill.
    """
    # 1. ABC Construction creates a skill
    payload = {
        "name": "Safety Inspection Assistant",
        "department": "safety",
        "system_prompt": "Safety protocols for ABC Construction.",
        "requested_tools": ["check_safety_compliance"],
    }
    create_res = await client.post("/api/v1/skills", json=payload, headers=abc_owner_headers)
    assert create_res.status_code == 201
    skill_id = create_res.json()["id"]

    # 2. XYZ Builders attempts to create a new version for ABC's skill -> MUST BE DENIED
    version_payload = {
        "system_prompt": "Malicious override attempt from XYZ Builders.",
        "description": "Attempting cross-tenant mutation.",
        "requested_tools": ["calculate_budget"],
    }
    cross_update_res = await client.post(
        f"/api/v1/skills/{skill_id}/versions",
        json=version_payload,
        headers=xyz_owner_headers,
    )
    assert cross_update_res.status_code in (403, 404), (
        f"Expected cross-organization update to be denied (403/404), got {cross_update_res.status_code}"
    )

    # 3. XYZ Builders attempts to activate ABC's skill -> MUST BE DENIED
    cross_activate_res = await client.post(
        f"/api/v1/skills/{skill_id}/activate",
        json={"version_number": 1},
        headers=xyz_owner_headers,
    )
    assert cross_activate_res.status_code in (403, 404)


@pytest.mark.asyncio
async def test_organization_skill_listing_strictly_isolated(
    client: AsyncClient, abc_owner_headers: dict, xyz_owner_headers: dict
):
    """
    Verifies that listing skills only returns skills belonging to the calling organization.
    """
    # ABC creates 2 skills
    for name in ["ABC Operations Assistant", "ABC Logistics Tool"]:
        await client.post(
            "/api/v1/skills",
            json={
                "name": name,
                "department": "operations",
                "system_prompt": "ABC prompt content.",
                "requested_tools": ["generate_daily_report"],
            },
            headers=abc_owner_headers,
        )

    # XYZ creates 1 skill
    await client.post(
        "/api/v1/skills",
        json={
            "name": "XYZ Procurement Tool",
            "department": "operations",
            "system_prompt": "XYZ prompt content.",
            "requested_tools": ["query_inventory"],
        },
        headers=xyz_owner_headers,
    )

    # Query list as ABC
    abc_list_res = await client.get("/api/v1/skills", headers=abc_owner_headers)
    assert abc_list_res.status_code == 200
    abc_skills = abc_list_res.json()
    assert len(abc_skills) == 2
    for s in abc_skills:
        assert s["organization_id"] == "org_abc"
        assert not s["name"].startswith("XYZ")

    # Query list as XYZ
    xyz_list_res = await client.get("/api/v1/skills", headers=xyz_owner_headers)
    assert xyz_list_res.status_code == 200
    xyz_skills = xyz_list_res.json()
    assert len(xyz_skills) == 1
    assert xyz_skills[0]["organization_id"] == "org_xyz"
    assert xyz_skills[0]["name"] == "XYZ Procurement Tool"
