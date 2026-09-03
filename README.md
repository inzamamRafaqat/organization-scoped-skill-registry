# Organization-Scoped Skill Registry Vertical Slice

A privacy-first, local-first, multi-tenant backend vertical slice for **Jarvis AI COO**, engineered to enforce strict tenant isolation, immutable versioning, owner-only activation, tool permission sandboxing, and tamper-evident auditability.

---

## 1. Overview & Core Guarantees

This service provides an organization-scoped registry where enterprise customers (such as **ABC Construction** and **XYZ Builders**) can draft, review, version, and activate AI COO operational skills without risk of cross-tenant data leakage or silent in-place prompt mutation.

### Core Architectural Guarantees:
- **Canonical Ownership Boundary**: All entities are strictly keyed by `organization_id`. Cross-tenant queries are blocked and audited.
- **Skill Lifecycle**: State transitions strictly follow `draft` &rarr; `active` &rarr; `disabled`.
- **Immutable Versioning**: An active skill cannot be mutated in place. Any update produces an incremented immutable snapshot ($v_1, v_2, \dots, v_n$).
- **Role-Based Activation**: Only organization `owner` roles can activate skills. Duplicate activation requests are safe and idempotent.
- **Tool Sandboxing**: Requested tools are validated against an approved registry. Destructive primitives (`delete_database`, `execute_shell`, `format_disk`, etc.) are rejected with explicit HTTP 422 errors. Tool declaration does not grant ambient permissions.
- **Auditability**: An append-only audit trail records every draft creation, version addition, activation, disablement, and cross-tenant access violation.
- **Dual Database Architecture**: Target production environment runs on **PostgreSQL** (configured in Docker Compose and Alembic); zero-dependency local evaluation and fast CI testing runs on **SQLite** with enforced foreign key pragmas (see [ARCHITECTURE_DECISION_NOTE.md](ARCHITECTURE_DECISION_NOTE.md)).

---

## 2. Pre-Seeded Fixture Organizations

The database automatically seeds the following fixture tenants on startup:

| Organization | ID | Fixture Users | Roles |
| :--- | :--- | :--- | :--- |
| **ABC Construction** | `org_abc` | `alice_owner`<br>`bob_member` | `owner`<br>`member` (Field Engineer) |
| **XYZ Builders** | `org_xyz` | `carol_owner`<br>`dan_member` | `owner`<br>`member` (Project Manager) |

---

## 3. Quickstart & Deployment

### Option A: Docker Compose (Production PostgreSQL Stack)

1. Ensure Docker is running.
2. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
3. Build and launch the stack:
   ```bash
   docker-compose up --build -d
   ```
4. Verify health status:
   ```bash
   curl http://localhost:8000/health
   ```
   Interactive OpenAPI docs are available at: `http://localhost:8000/docs`.

### Option B: Local Python Environment (Zero-Config SQLite)

1. Create and activate a Python 3.11+ virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

---

## 4. Running Automated Tests

Run the complete suite of mandatory automated tests covering tenant isolation, immutability, role authorization, tool sandboxing, and audit logging:

```bash
pytest -v tests/
```

Test output is captured and maintained in [TEST_OUTPUT.txt](TEST_OUTPUT.txt).

---

## 5. End-to-End Workflow API Examples (cURL)

Every API request requires tenant identity headers:
- `X-Organization-Id`: Tenant ID (`org_abc`, `org_xyz`)
- `X-User-Id`: Actor ID (`alice_owner`, `bob_member`, etc.)
- `X-User-Role`: Actor role (`owner`, `member`, `developer`)

*(Alternatively, standard Bearer tokens formatted as `Bearer <org_id>:<user_id>:<role>` are supported).*

### Step 1: Create a Skill Draft (Member or Owner)

```bash
curl -X POST http://localhost:8000/api/v1/skills \
  -H "Content-Type: application/json" \
  -H "X-Organization-Id: org_abc" \
  -H "X-User-Id: bob_member" \
  -H "X-User-Role: member" \
  -d '{
    "name": "Subcontractor Compliance Auditor",
    "department": "safety",
    "system_prompt": "Audit subcontractor personnel on site for OSHA compliance and valid PPE certifications.",
    "description": "Automated site safety checking skill.",
    "requested_tools": ["check_safety_compliance", "generate_daily_report"]
  }'
```

*Response (HTTP 201): Returns skill in `status: "draft"` with initial immutable version 1.*

---

### Step 2: Read Skill and Full Version History

```bash
curl -X GET http://localhost:8000/api/v1/skills/{skill_id} \
  -H "X-Organization-Id: org_abc" \
  -H "X-User-Id: alice_owner" \
  -H "X-User-Role: owner"
```

---

### Step 3: Owner Activation (Owner Only, Idempotent)

```bash
curl -X POST http://localhost:8000/api/v1/skills/{skill_id}/activate \
  -H "Content-Type: application/json" \
  -H "X-Organization-Id: org_abc" \
  -H "X-User-Id: alice_owner" \
  -H "X-User-Role: owner" \
  -d '{
    "version_number": 1
  }'
```

*Note: Non-owner activation attempts return `403 Forbidden`.*

---

### Step 4: Department Runtime Retrieval

```bash
curl -X GET http://localhost:8000/api/v1/skills/runtime/department/safety \
  -H "X-Organization-Id: org_abc" \
  -H "X-User-Id: alice_owner" \
  -H "X-User-Role: owner"
```

*Returns only active skills belonging to ABC Construction. Draft and disabled skills are strictly excluded.*

---

### Step 5: Create a New Immutable Version ($v_2$)

```bash
curl -X POST http://localhost:8000/api/v1/skills/{skill_id}/versions \
  -H "Content-Type: application/json" \
  -H "X-Organization-Id: org_abc" \
  -H "X-User-Id: alice_owner" \
  -H "X-User-Role: owner" \
  -d '{
    "system_prompt": "Updated prompt: Include biometric helmet verification and hazardous gas sensor monitoring.",
    "description": "Version 2 with sensor telemetry.",
    "requested_tools": ["check_safety_compliance", "track_equipment"]
  }'
```

---

### Step 6: Verify Tamper-Evident Audit Trail

```bash
curl -X GET "http://localhost:8000/api/v1/audit-logs?resource_id={skill_id}" \
  -H "X-Organization-Id: org_abc" \
  -H "X-User-Id: alice_owner" \
  -H "X-User-Role: owner"
```

*Returns audit events capturing `organization_id`, `actor_id`, `actor_role`, `event_type`, and exact `version_number`.*

---

### Step 7: Disable Skill

```bash
curl -X POST http://localhost:8000/api/v1/skills/{skill_id}/disable \
  -H "X-Organization-Id: org_abc" \
  -H "X-User-Id: alice_owner" \
  -H "X-User-Role: owner"
```

---

## 6. Architecture & Security Invariants

1. **Zero Cross-Tenant Leakage**: Queries for resources owned by another tenant return `403 Forbidden` or `404 Not Found`, and log a `CROSS_TENANT_ACCESS_DENIED` security audit event.
2. **Immutability Enforcement**: An active skill's prompt or tools can never be edited in place. Any update requires creating an explicit new version.
3. **Destructive Tool Interception**: Attempts to register tools containing destructive shell commands or disk operations return `422 Unprocessable Content`.
4. **Zero Hardcoded Secrets**: Secrets and database credentials reside exclusively in environment variables.

For detailed architecture rationale, see [ARCHITECTURE_DECISION_NOTE.md](ARCHITECTURE_DECISION_NOTE.md).
For known trade-offs and future roadmap, see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).
