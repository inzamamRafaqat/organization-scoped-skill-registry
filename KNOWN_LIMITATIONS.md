# Known Limitations & Production Roadmap

This document outlines intentional trade-offs of this vertical slice prototype, along with production-grade mitigations for subsequent enterprise iterations.

---

## 1. Authentication & Identity Provider (IdP) Integration
- **Current Vertical Slice**:
  Authentication context is established via deterministic headers (`X-Organization-Id`, `X-User-Id`, `X-User-Role`) or simulated Bearer tokens (`Bearer <org_id>:<user_id>:<role>`).
- **Production Roadmap**:
  In a full enterprise deployment, integrate an OpenID Connect (OIDC) / SAML 2.0 provider (such as Auth0, Okta, or Keycloak) where tenant claims (`org_id`, `roles`, `permissions`) are cryptographically verified via RS256 JWT tokens.

---

## 2. Tool Execution Sandbox
- **Current Vertical Slice**:
  Validates tool requests against an approved registry and blocks destructive tools (`execute_shell`, `delete_database`, etc.), returning a simulated execution payload.
- **Production Roadmap**:
  Execute AI COO tools inside ephemeral, network-isolated WebAssembly (Wasm) runtimes or Firecracker micro-VMs with strictly scoped, short-lived IAM credentials and mutual TLS (mTLS).

---

## 3. Database Multi-Tenancy Strategy
- **Current Vertical Slice**:
  Employs a **shared-database, row-level tenant discriminator** model (`organization_id` indexed on all tables).
- **Production Roadmap**:
  - For standard enterprise tiers: Implement PostgreSQL Row Level Security (RLS) policies enforcing `current_setting('app.current_org_id')`.
  - For high-compliance enterprise tiers (e.g. defense, critical infrastructure): Implement schema-per-tenant or database-per-tenant physical isolation.

---

## 4. Concurrent Version Drafting
- **Current Vertical Slice**:
  Version numbers increment sequentially by evaluating existing version count for the skill (`max(version_number) + 1`).
- **Production Roadmap**:
  Introduce database-level advisory locks or optimistic concurrency controls (`SELECT FOR UPDATE`) on the parent `skills` row when minting new versions to prevent race conditions during simultaneous draft submissions.

---

## 5. Audit Trail Immutability & Archival
- **Current Vertical Slice**:
  Audit records are stored in an append-only relational table with foreign keys and indexes.
- **Production Roadmap**:
  Stream audit records to a Write-Once-Read-Many (WORM) compliant storage engine (such as AWS S3 with Object Lock or an append-only ledger database like QLDB) with cryptographic hash chains to prove non-repudiation.
