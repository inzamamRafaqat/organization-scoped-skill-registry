# Architecture Decision Note (ADR): Organization-Scoped Skill Registry

## 1. Context & Business Drivers
Jarvis AI COO acts as an autonomous operations copilot for enterprises in construction, engineering, and logistics. Because distinct customer organizations (e.g. **ABC Construction** and **XYZ Builders**) possess proprietary workflows, safety protocols, and commercial terms, the AI COO platform requires strict multi-tenant isolation, immutable version governance, actor authorization, and tamper-evident audit logging.

---

## 2. Decision Summary

| Architectural Area | Decision | Key Justification |
| :--- | :--- | :--- |
| **Backend Framework** | **FastAPI** (Python 3.12/3.14, Async) | High-performance asynchronous execution, native OpenAPI schema generation, Pydantic type safety, and first-class dependency injection for tenant security context. |
| **Database Strategy** | **PostgreSQL** (Primary/Prod) + **SQLite** (Local Zero-Config Evaluation) | Meets the prompt requirement: *"PostgreSQL is preferred. SQLite is allowed only with a written justification."* Fully detailed below. |
| **Multi-Tenant Model** | **Row-Level Tenant Discriminator** via `organization_id` | Canonical ownership key indexed on all entities (`organizations`, `users`, `skills`, `skill_versions`, `audit_logs`). Enforces zero cross-tenant leakage. |
| **Immutability Model** | **Immutable Version History** (`skill_versions`) | Active skills cannot be mutated in place. Prompt or tool changes increment `version_number` ($v_{n+1}$), creating a reproducible, deterministic snapshot. |
| **Authorization Model** | **Role-Based Tenant Guard** (`ActorContext`) | Skill activation is strictly reserved for the `owner` role. Cross-tenant access is unconditionally denied (HTTP 403/404) and logged. |
| **Tool Sandbox** | **Capability Registry & Blocklist** | Skills declare requested capabilities. Destructive operations (`execute_shell`, `delete_database`, etc.) are rejected at validation time. Tool request does not grant ambient authority. |
| **Auditability** | **Append-Only Audit Log** | Every draft creation, version update, activation, and cross-tenant intrusion attempt is logged with organization, actor, event, and version. |

---

## 3. Written Justification: Dual Database Architecture (PostgreSQL & SQLite)

### Primary Production Engine: PostgreSQL
- **Role**: Target production database deployed via `docker-compose.yml` (`postgres:16-alpine`) and configured in `.env.example`.
- **Driver**: `asyncpg` via SQLAlchemy 2.0 async engine.
- **Benefits**: ACID compliance, concurrent connection pooling, native JSONB querying, row-level locking, and transactional schema migrations via Alembic.

### Local-First Evaluation & Testing Engine: SQLite (`aiosqlite`)
- **Role**: Embedded local development and zero-dependency automated test execution (`tests/conftest.py`).
- **Written Justification**:
  1. **Zero-Friction Local Evaluation**: Reviewers and automated CI pipelines can clone the repository and execute `pytest` immediately without provisioning a running Docker daemon or external PostgreSQL instance.
  2. **Deterministic Isolation**: Tests execute in-memory (`sqlite+aiosqlite:///:memory:` with `StaticPool`), ensuring hermetic test runs with instantaneous database setup and teardown.
  3. **Strict Constraint Parity**: SQLite connection pragmas (`PRAGMA foreign_keys=ON;`) are explicitly enforced on every connection to maintain foreign key and cascade delete parity with PostgreSQL.
  4. **Codebase Portability**: The SQLAlchemy 2.0 ORM schema and Alembic migrations are written dialect-agnostically, allowing seamless switching simply by toggling `DATABASE_URL`.

---

## 4. Multi-Tenant Isolation & Security Boundary

### Canonical Ownership Key: `organization_id`
Every resource is tied to an `organization_id`. The application enforces tenant boundaries at three distinct layers:
1. **Dependency Layer (`app/api/deps.py`)**:
   - `get_current_actor` extracts and validates the caller's tenant context (`organization_id`, `actor_id`, `role`).
   - Rejects unauthenticated requests with HTTP 401.
2. **Service Layer (`app/services/skill_service.py`)**:
   - Every read and write query scopes to `actor.organization_id`.
   - If an actor attempts to inspect or mutate another tenant's resource, the service intercepts the mismatch, emits a `CROSS_TENANT_ACCESS_DENIED` audit event, and denies the request (HTTP 403/404).
3. **Database Schema Constraints (`app/models/`)**:
   - Foreign key constraints reference `organizations.id` with `ON DELETE CASCADE`.
   - Redundant `organization_id` columns exist on `skill_versions` and `audit_logs` for direct index scans without cross-table joins.

---

## 5. Domain Lifecycle & Versioning State Machine

```
   [ Create Draft ]
          │
          ▼
     ┌─────────┐
     │  DRAFT  │  <--- Initial creation (v1)
     └────┬────┘       - Excluded from department runtime selection
          │            - Cannot execute (HTTP 400)
          │
   [ Owner Activation ] (Only role='owner')
          │
          ▼
     ┌─────────┐
     │ ACTIVE  │  <--- Runtime selection enabled
     └────┬────┘       - Current version locked & immutable
          │            - In-place mutation forbidden
          │            - Updates create v2, v3...
          │
   [ Owner/Admin Disable ]
          │
          ▼
     ┌──────────┐
     │ DISABLED │ <--- Excluded from runtime selection
     └──────────┘      - Execution attempts rejected (HTTP 400)
```

### Safe and Idempotent Activation
- Calling `POST /skills/{id}/activate` on an already active skill version returns HTTP 200 OK with no-op side effects, ensuring robust retries in distributed networks.

---

## 6. Tool Sandboxing & Capability Governance
- **Principle of Least Privilege**: Declaring a tool in `requested_tools` registers a declarative capability requirement. It does **not** grant ambient execution permissions.
- **Static Rejection of Dangerous Primitives**:
  Tools such as `delete_database`, `execute_shell`, `format_disk`, `grant_admin`, `eval`, `rm_rf`, and `access_host_filesystem` are strictly intercepted during Pydantic schema validation and rejected with HTTP 422.
- **Curated Registry**:
  Only tools registered in `app.core.tool_registry.APPROVED_TOOLS` (e.g. `generate_daily_report`, `calculate_budget`, `check_safety_compliance`) are permitted.

---

## 7. Audit Trail Integrity
- All lifecycle events (`SKILL_DRAFT_CREATED`, `SKILL_VERSION_CREATED`, `SKILL_ACTIVATED`, `SKILL_DISABLED`, `CROSS_TENANT_ACCESS_DENIED`, `UNAUTHORIZED_ACTIVATION_ATTEMPT`) are written to an append-only `audit_logs` table.
- Each audit log captures:
  - `organization_id`
  - `actor_id`
  - `actor_role`
  - `event_type`
  - `resource_type` and `resource_id`
  - `version_number`
  - `created_at` (UTC timestamp)
  - `details` (JSON payload with metadata)
