# Jarvis AI COO — Organization-Scoped Skill Registry Vertical Slice

[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Tests-23%2F23%20Passing-brightgreen.svg)](tests/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A privacy-first, multi-tenant backend vertical slice for **Jarvis AI COO**, engineered to enforce strict organization-level isolation, immutable skill versioning, owner-only authorization, tool capability sandboxing, and tamper-evident auditability.

---

## Table of Contents
1. [Architectural Overview](#1-architectural-overview)
2. [Core Guarantees & Invariants](#2-core-guarantees--invariants)
3. [Fixture Organizations](#3-fixture-organizations)
4. [End-to-End Workflow & cURL Examples](#4-end-to-end-workflow--curl-examples)
5. [API Capabilities Reference](#5-api-capabilities-reference)
6. [Quickstart: Local & Docker Deployment](#6-quickstart-local--docker-deployment)
7. [Automated Verification & Test Suite](#7-automated-verification--test-suite)
8. [Architecture Decision Record (ADR) Summary](#8-architecture-decision-record-adr-summary)
9. [Known Limitations & Production Roadmap](#9-known-limitations--production-roadmap)
10. [Submission Final Report (Section 8)](#10-submission-final-report-section-8)

---

## 1. Architectural Overview

Jarvis AI COO serves enterprise clients in construction, operations, and logistics. Because clients possess confidential workflows and commercial terms, this vertical slice enforces **zero cross-tenant data leakage** and **pure immutable versioning**.

```
                           Incoming Client Request
                                      │
               ┌──────────────────────▼──────────────────────┐
               │    FastAPI Tenant Guard (deps.py)          │
               │   - Extracts X-Organization-Id & Actor      │
               │   - Enforces Authentication & Tenant Scope  │
               └──────────────────────┬──────────────────────┘
                                      │
                     ┌────────────────┴────────────────┐
                     ▼                                 ▼
         [ Tenant Matches Context ]        [ Tenant Mismatch / Intrusion ]
                     │                                 │
                     ▼                                 ▼
         ┌──────────────────────┐          ┌──────────────────────┐
         │ Skill Service Layer  │          │ Audit Intrusion Log  │
         │ - Validate Tools     │          │ Returns 403 / 404    │
         │ - Enforce Lifecycle  │          └──────────────────────┘
         │ - Verify Owner Role  │
         └───────────┬──────────┘
                     │
         ┌───────────▼─────────────────────────────────┐
         │     Database Layer (SQLAlchemy 2.0)         │
         │  PostgreSQL (Prod) / SQLite (Local Test)    │
         │  - organizations (Tenants)                  │
         │  - skills (Lifecycle state machine)         │
         │  - skill_versions (Immutable snapshots)    │
         │  - audit_logs (Tamper-evident trail)        │
         └─────────────────────────────────────────────┘
```

---

## 2. Core Guarantees & Invariants

- **Canonical Ownership Key**: Every domain entity explicitly indexes `organization_id`. Database queries strictly filter by the caller's tenant boundary. Cross-tenant access is unconditionally blocked and logged as `CROSS_TENANT_ACCESS_DENIED`.
- **Domain State Machine**: Strict lifecycle progression:
  $$\text{Draft} \xrightarrow{\text{Owner Activation}} \text{Active} \xrightarrow{\text{Disable}} \text{Disabled}$$
- **Immutable Version Governance**: Active skills can **never** be edited in place. Any change to system prompts, descriptions, or toolsets increments the version counter ($v_1 \rightarrow v_2 \rightarrow \dots \rightarrow v_n$) and creates an immutable snapshot.
- **Owner-Only Activation**: Only organization actors with the `owner` role are authorized to activate a skill version. Non-owner activation requests return `403 Forbidden`.
- **Safe & Idempotent Activation**: Re-activating an already active version succeeds with `200 OK` without duplicate side effects.
- **Tool Capability Sandboxing**:
  - Requesting a tool registers declarative intent only; it does **not** grant ambient system permissions.
  - Destructive primitives (`delete_database`, `execute_shell`, `format_disk`, `grant_admin`, `eval`, `rm_rf`, `access_host_filesystem`) are intercepted at validation time and rejected with `HTTP 422`.
- **Tamper-Evident Audit Logging**: An append-only audit trail logs tenant ID, actor ID, actor role, event type, exact version number, and UTC timestamp for all lifecycle and security events.

---

## 3. Fixture Organizations

The database automatically seeds the following fixture organizations and users on startup:

| Organization | Tenant ID | User ID | Role | Name / Title |
| :--- | :--- | :--- | :--- | :--- |
| **ABC Construction** | `org_abc` | `alice_owner` | `owner` | Alice Cooper (Owner / Executive) |
| **ABC Construction** | `org_abc` | `bob_member` | `member` | Bob Martinez (Field Operations Engineer) |
| **XYZ Builders** | `org_xyz` | `carol_owner` | `owner` | Carol Danvers (Owner / Executive) |
| **XYZ Builders** | `org_xyz` | `dan_member` | `member` | Dan Vance (Project Manager) |

---

## 4. End-to-End Workflow & cURL Examples

All endpoints require tenant identification headers:
- `X-Organization-Id`: Tenant identifier (`org_abc`, `org_xyz`)
- `X-User-Id`: Actor identifier (`alice_owner`, `bob_member`, etc.)
- `X-User-Role`: Actor role (`owner`, `member`, `developer`)

*(Alternatively, standard Bearer tokens formatted as `Bearer <org_id>:<user_id>:<role>` are supported).*

### Step 1: Create a Skill Draft (Field Member or Owner)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/skills \
  -H "Content-Type: application/json" \
  -H "X-Organization-Id: org_abc" \
  -H "X-User-Id: bob_member" \
  -H "X-User-Role: member" \
  -d '{
    "name": "Subcontractor Safety Compliance Auditor",
    "department": "safety",
    "system_prompt": "Audit daily subcontractor work permits and personal protective equipment certifications.",
    "description": "Daily automated site safety inspection assistant.",
    "requested_tools": ["check_safety_compliance", "generate_daily_report"]
  }'
```

**Response (HTTP 201 Created):**
```json
{
  "id": "e98df8b1-1cb3-4882-a392-1209b552fa10",
  "organization_id": "org_abc",
  "name": "Subcontractor Safety Compliance Auditor",
  "slug": "subcontractor-safety-compliance-auditor",
  "department": "safety",
  "status": "draft",
  "current_version_id": null,
  "created_by": "bob_member",
  "versions": [
    {
      "id": "1d8b7ea3-2a3b-41fa-bb55-a2df6a059d01",
      "skill_id": "e98df8b1-1cb3-4882-a392-1209b552fa10",
      "organization_id": "org_abc",
      "version_number": 1,
      "system_prompt": "Audit daily subcontractor work permits and personal protective equipment certifications.",
      "description": "Daily automated site safety inspection assistant.",
      "requested_tools": ["check_safety_compliance", "generate_daily_report"],
      "created_by": "bob_member",
      "is_immutable": true
    }
  ]
}
```

---

### Step 2: Read Skill & Versions (Draft Review)

```bash
curl -X GET http://127.0.0.1:8000/api/v1/skills/e98df8b1-1cb3-4882-a392-1209b552fa10 \
  -H "X-Organization-Id: org_abc" \
  -H "X-User-Id: alice_owner" \
  -H "X-User-Role: owner"
```

---

### Step 3: Owner Activation (Owner-Only, Idempotent)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/skills/e98df8b1-1cb3-4882-a392-1209b552fa10/activate \
  -H "Content-Type: application/json" \
  -H "X-Organization-Id: org_abc" \
  -H "X-User-Id: alice_owner" \
  -H "X-User-Role: owner" \
  -d '{"version_number": 1}'
```

*Note: Non-owner activation attempts return `403 Forbidden`.*

---

### Step 4: Department Runtime Retrieval

```bash
curl -X GET http://127.0.0.1:8000/api/v1/skills/runtime/department/safety \
  -H "X-Organization-Id: org_abc" \
  -H "X-User-Id: alice_owner" \
  -H "X-User-Role: owner"
```

*Returns only active skills for ABC Construction. Draft and disabled skills are strictly excluded.*

---

### Step 5: Create a New Immutable Version ($v_2$)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/skills/e98df8b1-1cb3-4882-a392-1209b552fa10/versions \
  -H "Content-Type: application/json" \
  -H "X-Organization-Id: org_abc" \
  -H "X-User-Id: alice_owner" \
  -H "X-User-Role: owner" \
  -d '{
    "system_prompt": "Version 2: Added hazardous atmospheric sensor verification.",
    "description": "Upgraded version with atmospheric telemetry.",
    "requested_tools": ["check_safety_compliance", "track_equipment"]
  }'
```

---

### Step 6: Verify Tamper-Evident Audit Trail

```bash
curl -X GET "http://127.0.0.1:8000/api/v1/audit-logs?resource_id=e98df8b1-1cb3-4882-a392-1209b552fa10" \
  -H "X-Organization-Id: org_abc" \
  -H "X-User-Id: alice_owner" \
  -H "X-User-Role: owner"
```

**Response:**
```json
[
  {
    "id": "7a35368a-cf8e-4a6c-b3a5-bc75836a0f7e",
    "organization_id": "org_abc",
    "actor_id": "alice_owner",
    "actor_role": "owner",
    "event_type": "SKILL_ACTIVATED",
    "resource_type": "skill",
    "resource_id": "e98df8b1-1cb3-4882-a392-1209b552fa10",
    "version_number": 1,
    "details": {
      "previous_status": "draft",
      "tools": ["check_safety_compliance", "generate_daily_report"]
    }
  },
  {
    "id": "2d8f9104-58a1-432d-9659-19812bc6572e",
    "organization_id": "org_abc",
    "actor_id": "bob_member",
    "actor_role": "member",
    "event_type": "SKILL_DRAFT_CREATED",
    "resource_type": "skill",
    "resource_id": "e98df8b1-1cb3-4882-a392-1209b552fa10",
    "version_number": 1
  }
]
```

---

### Step 7: Disable Skill

```bash
curl -X POST http://127.0.0.1:8000/api/v1/skills/e98df8b1-1cb3-4882-a392-1209b552fa10/disable \
  -H "X-Organization-Id: org_abc" \
  -H "X-User-Id: alice_owner" \
  -H "X-User-Role: owner"
```

---

## 5. API Capabilities Reference

| HTTP Method | Route | Description | Authorization |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/skills` | Create a skill draft (with $v_1$ snapshot) | Owner, Member, Developer |
| `GET` | `/api/v1/skills` | List organization's skills (supports filters) | Any tenant member |
| `GET` | `/api/v1/skills/{id}` | Read skill together with all immutable versions | Any tenant member |
| `POST` | `/api/v1/skills/{id}/versions` | Create a new immutable version ($v_{n+1}$) | Owner, Member, Developer |
| `POST` | `/api/v1/skills/{id}/activate` | Activate an approved version (idempotent) | **Owner Only** |
| `POST` | `/api/v1/skills/{id}/disable` | Disable a skill (removes from runtime) | Owner, Member |
| `GET` | `/api/v1/skills/runtime/department/{dept}` | Runtime query for active department skills | Any tenant member |
| `POST` | `/api/v1/skills/{id}/execute` | Runtime skill execution probe | Active skills only |
| `GET` | `/api/v1/audit-logs` | Retrieve organization-scoped audit trail | Any tenant member |
| `GET` | `/health` | Service health probe | Public |

Interactive OpenAPI documentation is available live at `http://127.0.0.1:8000/docs` (visiting `http://127.0.0.1:8000/` automatically redirects to `/docs`).

---

## 6. Quickstart: Local & Docker Deployment

### Prerequisites
- Python 3.11+ (tested on Python 3.12 and 3.14)
- Git
- Docker & Docker Compose (optional, for containerized PostgreSQL)

### Option A: Local Zero-Config Setup (Recommended for Evaluation)

1. **Clone repository and create virtual environment**:
   ```bash
   git clone https://github.com/inzamamRafaqat/organization-scoped-skill-registry.git
   cd organization-scoped-skill-registry
   python -m venv .venv
   
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux / macOS:
   source .venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the FastAPI server**:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

4. Open `http://127.0.0.1:8000/docs` in your browser.

---

### Option B: Docker Compose (PostgreSQL Production Stack)

1. **Launch containers**:
   ```bash
   docker-compose up --build -d
   ```

2. **Inspect running services**:
   ```bash
   docker-compose ps
   ```

3. **Verify health endpoint**:
   ```bash
   curl http://localhost:8000/health
   ```

---

## 7. Automated Verification & Test Suite

The test suite covers all 10 mandatory evaluation criteria plus end-to-end integration workflows.

### Running Pytest:
```bash
pytest -v tests/
```

### Verified Output (`TEST_OUTPUT.txt`):
```text
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\Inzamam Rafaqat\Desktop\Gobined Traders
configfile: pyproject.toml
plugins: anyio-4.15.0, asyncio-1.4.0
collected 23 items

tests/test_audit_logging.py::test_audit_record_contains_organization_actor_event_and_version PASSED [  4%]
tests/test_audit_logging.py::test_cross_tenant_access_attempt_is_audit_logged PASSED [  8%]
tests/test_e2e_workflow.py::test_full_required_end_to_end_workflow PASSED [ 13%]
tests/test_immutable_versioning.py::test_active_version_is_immutable PASSED [ 17%]
tests/test_skill_lifecycle.py::test_non_owner_activation_denied PASSED   [ 21%]
tests/test_skill_lifecycle.py::test_draft_skill_cannot_execute_or_load_as_active PASSED [ 26%]
tests/test_skill_lifecycle.py::test_disabled_skill_excluded_from_runtime_selection PASSED [ 30%]
tests/test_skill_lifecycle.py::test_duplicate_activation_request_is_safe_and_idempotent PASSED [ 34%]
tests/test_tenant_isolation.py::test_same_organization_create_read_succeeds PASSED [ 39%]
tests/test_tenant_isolation.py::test_cross_organization_read_is_denied PASSED [ 43%]
tests/test_tenant_isolation.py::test_cross_organization_update_is_denied PASSED [ 47%]
tests/test_tenant_isolation.py::test_organization_skill_listing_strictly_isolated PASSED [ 52%]
tests/test_tool_validation.py::test_invalid_or_destructive_requested_tool_is_rejected[delete_database] PASSED [ 56%]
tests/test_tool_validation.py::test_invalid_or_destructive_requested_tool_is_rejected[execute_shell] PASSED [ 60%]
tests/test_tool_validation.py::test_invalid_or_destructive_requested_tool_is_rejected[format_disk] PASSED [ 65%]
tests/test_tool_validation.py::test_invalid_or_destructive_requested_tool_is_rejected[grant_admin] PASSED [ 69%]
tests/test_tool_validation.py::test_invalid_or_destructive_requested_tool_is_rejected[eval] PASSED [ 73%]
tests/test_tool_validation.py::test_invalid_or_destructive_requested_tool_is_rejected[rm_rf] PASSED [ 78%]
tests/test_tool_validation.py::test_invalid_or_destructive_requested_tool_is_rejected[drop_tables] PASSED [ 82%]
tests/test_tool_validation.py::test_invalid_or_destructive_requested_tool_is_rejected[access_host_filesystem] PASSED [ 86%]
tests/test_tool_validation.py::test_invalid_or_destructive_requested_tool_is_rejected[elevate_privileges] PASSED [ 91%]
tests/test_tool_validation.py::test_unregistered_tool_is_rejected_with_useful_error PASSED [ 95%]
tests/test_tool_validation.py::test_valid_tools_do_not_grant_ambient_permissions PASSED [100%]

============================= 23 passed in 4.97s ==============================
```

---

## 8. Architecture Decision Record (ADR) Summary

For the full ADR, see [`ARCHITECTURE_DECISION_NOTE.doc`](ARCHITECTURE_DECISION_NOTE.doc).

### Written Justification: Dual Database Architecture (PostgreSQL & SQLite)
- **Target Production**: **PostgreSQL 16** via `asyncpg` driver in `docker-compose.yml` with Alembic transactional schema migrations.
- **Local Evaluation & Testing**: **SQLite** via `aiosqlite` with `PRAGMA foreign_keys=ON;`.
- **Written Justification**:
  1. **Zero-Dependency Evaluation**: Reviewers can execute `pytest` immediately without provisioning a running Docker daemon or external PostgreSQL instance.
  2. **Hermetic Test Isolation**: Tests execute in-memory with `StaticPool`, ensuring isolated state and sub-5-second test runs.
  3. **Strict Constraint Parity**: SQLite connection pragmas (`PRAGMA foreign_keys=ON`) enforce foreign key cascade deletes matching PostgreSQL.
  4. **Dialect Portability**: SQLAlchemy 2.0 ORM models and Alembic migrations are dialect-agnostic, switching transparently via `DATABASE_URL`.

---

## 9. Known Limitations & Production Roadmap

For complete details, see [`KNOWN_LIMITATIONS.doc`](KNOWN_LIMITATIONS.doc).

1. **Authentication Token Mechanism**:
   - *Current*: Multi-tenant test headers (`X-Organization-Id`) and simulated Bearer tokens.
   - *Production Roadmap*: RS256 JWT validation integrated with OIDC / SAML 2.0 provider (Auth0, Okta, Keycloak).
2. **Tool Execution Sandbox**:
   - *Current*: Validates tool requests against approved catalog and rejects destructive primitives.
   - *Production Roadmap*: WebAssembly (Wasm) or Firecracker micro-VM isolated runtimes.
3. **Database Multi-Tenancy Strategy**:
   - *Current*: Row-level tenant discriminator `organization_id` in a shared schema.
   - *Production Roadmap*: PostgreSQL Row-Level Security (RLS) policies and schema-per-tenant physical isolation.
4. **Concurrent Version Drafting**:
   - *Current*: Sequential `max(version) + 1` calculation.
   - *Production Roadmap*: PostgreSQL advisory locks or optimistic concurrency controls (`SELECT FOR UPDATE`).

---

## 10. Submission Final Report (Section 8)

```text
Repository URL: https://github.com/inzamamRafaqat/organization-scoped-skill-registry
Submission Branch: submission/skill-registry-vertical-slice
Start time: 2026-09-03 14:05 PKT
Finish time: 2026-09-03 14:42 PKT
Approximate hours: 0.6 hours
Final commit SHA: 29d61bd419d2b27a3c33306d15bba1b42ceca431

Goal achieved:
Built a fully isolated, multi-tenant Organization-Scoped Skill Registry backend in FastAPI for Jarvis AI COO. Strict row-level tenant boundaries prevent Organization B from accessing Organization A's data. Implemented immutable skill versioning where active skills cannot be modified in place, owner-only activation, tool permission sandboxing with destructive primitive rejection, and an append-only audit trail capturing organization, actor, event, and exact version.

Architecture decisions:
FastAPI with async SQLAlchemy 2.0. Dual database design: PostgreSQL 16 (production container via docker-compose with asyncpg and Alembic migrations) alongside SQLite (aiosqlite) with PRAGMA foreign_keys=ON for zero-dependency local evaluation. Canonical ownership key organization_id indexed across all entities. Redundant tenant keys on child version/audit tables for direct index scans. Declarative capability sandboxing preventing ambient tool privileges.

Tests passed:
23 passed out of 23 tests in 4.97 seconds (0 warnings). All 10 mandatory evaluation scenarios passed:
- Same-organization create/read succeeds
- Cross-organization read is denied (403/404)
- Cross-organization update is denied (403/404)
- Non-owner activation is denied (403)
- Draft skill cannot execute or load as active (400)
- Disabled skill is excluded from runtime selection (400)
- Active version is immutable (previous version contents preserved)
- Duplicate activation request is safe and idempotent (200 OK)
- Invalid or destructive requested tool is rejected (422) [9 parametrized destructive tools tested]
- Audit record contains organization, actor, event and version
- Full end-to-end lifecycle workflow verified

Security/isolation evidence:
Cross-tenant access attempts by XYZ Builders on ABC Construction skills return HTTP 403 and write CROSS_TENANT_ACCESS_DENIED audit events. Non-owner activation attempts fail with HTTP 403 and log UNAUTHORIZED_ACTIVATION_ATTEMPT. Active skill version updates create incremented version rows (v2) leaving v1 untouched. Destructive tools (delete_database, execute_shell, format_disk, etc.) are blocked at the schema boundary.

Known limitations:
Header/simulated Bearer token authentication rather than full enterprise OIDC/SAML IdP; simulated tool runtime rather than isolated Wasm/Firecracker micro-VMs; row-level multi-tenancy rather than schema-per-tenant physical database isolation; sequential version increments rather than advisory database write locks.

What I would implement next:
1. RS256 JWT validation with an external identity provider (Auth0/Keycloak).
2. PostgreSQL Row-Level Security (RLS) policies beneath the ORM.
3. WebAssembly / Firecracker micro-VM isolated runtime for executing approved AI COO tools.
4. Cryptographic WORM / ledger audit log streaming (AWS QLDB / S3 Object Lock).

AI tools used, if any:
Antigravity AI Coding Assistant (Gemini 3.8 Flash)
```
