"""End-to-End Workflow Test.

Verifies Section 3: Required End-to-End Workflow
Authenticated organization
→ manual skill draft create
→ draft review
→ owner activation
→ active skill retrieve
→ exact version audit record
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_required_end_to_end_workflow(
    client: AsyncClient, abc_owner_headers: dict, abc_member_headers: dict
):
    """
    Executes the exact end-to-end lifecycle mandated in evaluation Section 3:
    1. Authenticated organization: ABC Construction (alice_owner, bob_member)
    2. Manual skill draft create: Member/Engineer creates a new draft
    3. Draft review: Owner reviews draft details and version 1 contents
    4. Owner activation: Owner approves and activates version 1
    5. Active skill retrieve: Runtime retrieve confirms active status & department availability
    6. Exact version audit record: Audit trail confirms exact version, actor, org, and timestamp
    """
    # -------------------------------------------------------------
    # Step 1: Authenticated organization member creates draft
    # -------------------------------------------------------------
    draft_payload = {
        "name": "Subcontractor Compliance Auditor",
        "department": "safety",
        "system_prompt": "Audit subcontractor workers on site for safety certifications and PPE compliance.",
        "description": "Automates safety verification checks on all active construction sites.",
        "requested_tools": ["check_safety_compliance", "generate_daily_report"],
    }

    create_res = await client.post("/api/v1/skills", json=draft_payload, headers=abc_member_headers)
    assert create_res.status_code == 201, create_res.text
    draft_skill = create_res.json()
    skill_id = draft_skill["id"]

    assert draft_skill["organization_id"] == "org_abc"
    assert draft_skill["status"] == "draft"
    assert draft_skill["current_version_id"] is None
    assert len(draft_skill["versions"]) == 1
    assert draft_skill["versions"][0]["version_number"] == 1

    # Verify that at this stage, skill is NOT in runtime active selection
    pre_active_dept = await client.get("/api/v1/skills/runtime/department/safety", headers=abc_owner_headers)
    assert pre_active_dept.status_code == 200
    assert all(s["id"] != skill_id for s in pre_active_dept.json())

    # -------------------------------------------------------------
    # Step 2: Draft review by organization owner
    # -------------------------------------------------------------
    review_res = await client.get(f"/api/v1/skills/{skill_id}", headers=abc_owner_headers)
    assert review_res.status_code == 200
    reviewed_skill = review_res.json()

    assert reviewed_skill["id"] == skill_id
    assert reviewed_skill["name"] == draft_payload["name"]
    assert reviewed_skill["status"] == "draft"
    assert len(reviewed_skill["versions"]) == 1
    v1 = reviewed_skill["versions"][0]
    assert v1["system_prompt"] == draft_payload["system_prompt"]
    assert v1["requested_tools"] == draft_payload["requested_tools"]

    # -------------------------------------------------------------
    # Step 3: Owner activation
    # -------------------------------------------------------------
    activate_res = await client.post(
        f"/api/v1/skills/{skill_id}/activate",
        json={"version_number": 1},
        headers=abc_owner_headers,
    )
    assert activate_res.status_code == 200
    activated_skill = activate_res.json()

    assert activated_skill["status"] == "active"
    assert activated_skill["current_version_id"] == v1["id"]
    assert activated_skill["current_version"]["version_number"] == 1

    # -------------------------------------------------------------
    # Step 4: Active skill retrieve (Runtime lookup & execution)
    # -------------------------------------------------------------
    active_dept_res = await client.get("/api/v1/skills/runtime/department/safety", headers=abc_owner_headers)
    assert active_dept_res.status_code == 200
    dept_active_skills = active_dept_res.json()

    retrieved_active = next((s for s in dept_active_skills if s["id"] == skill_id), None)
    assert retrieved_active is not None
    assert retrieved_active["status"] == "active"
    assert retrieved_active["current_version"]["version_number"] == 1

    # Test runtime execution of active skill
    exec_res = await client.post(
        f"/api/v1/skills/{skill_id}/execute",
        json={"input_text": "Inspect Subcontractor Crew #12 on Building B"},
        headers=abc_owner_headers,
    )
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["status"] == "active"
    assert exec_data["version_number"] == 1
    assert "Building B" in exec_data["simulated_result"]

    # -------------------------------------------------------------
    # Step 5: Exact version audit record verification
    # -------------------------------------------------------------
    audit_res = await client.get(f"/api/v1/audit-logs?resource_id={skill_id}", headers=abc_owner_headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()

    # Find activation audit log
    activation_log = next((l for l in logs if l["event_type"] == "SKILL_ACTIVATED"), None)
    assert activation_log is not None
    assert activation_log["organization_id"] == "org_abc"
    assert activation_log["actor_id"] == "alice_owner"
    assert activation_log["actor_role"] == "owner"
    assert activation_log["resource_type"] == "skill"
    assert activation_log["resource_id"] == skill_id
    assert activation_log["version_number"] == 1
    assert activation_log["created_at"] is not None

    # Find draft creation audit log
    draft_log = next((l for l in logs if l["event_type"] == "SKILL_DRAFT_CREATED"), None)
    assert draft_log is not None
    assert draft_log["organization_id"] == "org_abc"
    assert draft_log["actor_id"] == "bob_member"
    assert draft_log["version_number"] == 1
