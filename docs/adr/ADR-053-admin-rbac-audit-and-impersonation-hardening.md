# ADR-053: Admin RBAC Seam, Audit Log, and Impersonation Hardening

## Status
**Accepted (Implemented)**

## Date
2026-01-24

## Context
StrideIQ needs a business-critical admin console that is safe to operate:
- Admin routes must never be reachable by normal subscribers in production.
- Privileged actions must be traceable (support, security, compliance).
- Certain actions (impersonation) have high blast radius and must be tightly controlled.

We also need to avoid an early rewrite when future roles emerge (support, ops, finance).

## Decision
Implement:
1) **Role-based gate** for admin access (`admin` / `owner`).
2) A **permissions seam** (`admin_permissions`) for fine-grained authorization without redesign.
3) An append-only **AdminAuditEvent** log for privileged actions.
4) **Owner-only impersonation**, time-boxed, auditable, and visible in the UI.

### Permissions seam behavior
- `owner`: always allowed.
- `admin`: allowed when permission is present.
- **Bootstrap mode**: legacy admins with no explicit permissions may be allowed for non-system actions, but **system-level controls (`system.*`) require explicit permission**.

### Impersonation hardening requirements
- Owner only.
- Short-lived token (bounded TTL).
- Audit event on start (`auth.impersonate.start`) with TTL and expiry.
- Global UI banner while impersonating + one-click stop that restores original token.

## Consequences
### Positive
- Operational actions are traceable and reviewable.
- High-risk actions are constrained and visible.
- Permission seam supports future role expansion without rewriting endpoints.

### Negative
- Requires ongoing hygiene: ensure new admin endpoints declare permissions and are audited.
- Requires careful test isolation when global state is involved.

## Audit Logging Requirements
Minimum for each action:
- actor id, target id (optional), action, timestamp
- request metadata (ip/ua where available)
- reason (when supplied)
- minimal payload (before/after for mutations)

## Test Strategy
- Backend:
  - verify role/permission guards (403s)
  - verify impersonation is owner-only + TTL-bounded + audited
  - verify sensitive system controls are explicitly permissioned
- Web:
  - verify impersonation banner renders and stop clears state safely (no JSDOM reload crashes)

## Security / Privacy Considerations
- Treat audit logs as sensitive telemetry (access control, retention).
- Prevent silent privilege escalation: banner + TTL reduce blast radius.
- Avoid storing long-lived impersonation tokens.

## Related
- Ops controls: `docs/adr/ADR-054-viral-safe-ingestion-resilience-and-emergency-brake.md`

