"""Mandatory Tests for Immutable Versioning.

Requirements:
- An active skill must never be modified in place; changes create a new immutable version.
- Active version is immutable.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_active_version_is_immutable(
    client: AsyncClient, abc_owner_headers: dict
):
    """
    Verifies that once a skill is created and activated, its version cannot be mutated in place.
    Any updates must be registered as a new version, preserving the integrity of previous versions.
    """
    # 1. Create draft skill with initial version (v1)
    payload = {
        "name": "Steel Rebar Quality Checker",
        "department": "operations",
        "system_prompt": "Version 1 prompt: Verify steel rebar tensile certifications.",
        "description": "Initial version 1 description.",
        "requested_tools": ["track_equipment"],
    }
    create_res = await client.post("/api/v1/skills", json=payload, headers=abc_owner_headers)
    assert create_res.status_code == 201
    skill_data = create_res.json()
    skill_id = skill_data["id"]
    v1_id = skill_data["versions"][0]["id"]

    # 2. Activate v1
    act_res = await client.post(f"/api/v1/skills/{skill_id}/activate", headers=abc_owner_headers)
    assert act_res.status_code == 200
    assert act_res.json()["status"] == "active"

    # 3. Create a new version (v2) with updated prompts and tools
    v2_payload = {
        "system_prompt": "Version 2 prompt: Advanced ultrasound rebar tensile analysis.",
        "description": "Updated v2 description.",
        "requested_tools": ["track_equipment", "generate_daily_report"],
    }
    v2_res = await client.post(
        f"/api/v1/skills/{skill_id}/versions",
        json=v2_payload,
        headers=abc_owner_headers,
    )
    assert v2_res.status_code == 201
    v2_data = v2_res.json()
    assert v2_data["version_number"] == 2
    assert v2_data["is_immutable"] is True

    # 4. Fetch the skill and verify that v1 remains completely unchanged and unmutated
    get_res = await client.get(f"/api/v1/skills/{skill_id}", headers=abc_owner_headers)
    assert get_res.status_code == 200
    fetched_skill = get_res.json()

    assert len(fetched_skill["versions"]) == 2
    fetched_v1 = next(v for v in fetched_skill["versions"] if v["version_number"] == 1)
    fetched_v2 = next(v for v in fetched_skill["versions"] if v["version_number"] == 2)

    # Immutability assertions: v1 retains original system prompt and tools exactly
    assert fetched_v1["id"] == v1_id
    assert fetched_v1["system_prompt"] == payload["system_prompt"]
    assert fetched_v1["description"] == payload["description"]
    assert fetched_v1["requested_tools"] == payload["requested_tools"]
    assert fetched_v1["is_immutable"] is True

    # v2 has its separate contents
    assert fetched_v2["system_prompt"] == v2_payload["system_prompt"]
    assert fetched_v2["requested_tools"] == v2_payload["requested_tools"]

    # The currently active version is still v1 until explicitly activated
    assert fetched_skill["current_version_id"] == v1_id

    # 5. Activate v2
    act_v2_res = await client.post(
        f"/api/v1/skills/{skill_id}/activate",
        json={"version_number": 2},
        headers=abc_owner_headers,
    )
    assert act_v2_res.status_code == 200
    assert act_v2_res.json()["current_version_id"] == fetched_v2["id"]
