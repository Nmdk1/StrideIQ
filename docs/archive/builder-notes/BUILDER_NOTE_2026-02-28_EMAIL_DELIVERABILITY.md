# Builder Note — Email Deliverability (Transactional Password Reset)

**Date:** 2026-02-28  
**Assigned to:** Backend Builder  
**Advisor sign-off required:** Yes  
**Urgency:** ~~High~~ — **SHIPPED (Feb 28, 2026)**  
**Status:** Complete. Production verified by Codex advisor. Password reset emails deliver via `smtp.gmail.com:587`, sender `noreply@strideiq.run`.

---

## Before Your First Tool Call

Read in order:
1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. This document

---

## Objective

Make production transactional email reliable for password reset flow.

Confirmed reality:
- Google Workspace is already live for `strideiq.run`
- Multiple working sender addresses already exist
- This task is **application wiring only**, not provider setup

Current issue:
- `EMAIL_ENABLED` is effectively off in practice
- defaults still reference old brand sender (`performancefocused.com`)
- SMTP defaults to localhost path that is not valid for production

---

## Single Technical Decision (No Alternatives)

Use **Google Workspace SMTP via Gmail SMTP** with app password.

- SMTP host: `smtp.gmail.com`
- SMTP port: `587`
- TLS: STARTTLS
- Auth: `SMTP_USERNAME` + `SMTP_PASSWORD` (app password)
- Sender: `StrideIQ <noreply@strideiq.run>` (or `michael@strideiq.run` fallback only if noreply account/alias not ready)

Do **not** evaluate Resend/SendGrid/Mailgun.  
Do **not** branch into Gmail API service account in this task.

---

## Scope

### 1) Backend email service hardening

File: `apps/api/services/email_service.py`

- Keep existing SMTP implementation (`smtplib`).
- Ensure STARTTLS path is used for authenticated SMTP.
- Remove legacy default sender values tied to old brand.
- Keep fail-safe behavior:
  - if `EMAIL_ENABLED=False` => no send attempt
  - SMTP exceptions logged cleanly, function returns `False` without crashing request path.

### 2) Config defaults cleanup

File: `apps/api/core/config.py`

- Update defaults only to current brand-safe values:
  - `FROM_EMAIL` default to `noreply@strideiq.run`
  - `FROM_NAME` default to `StrideIQ`
- Keep env-driven behavior; no hardcoded secrets.

### 3) Production env setup

Set/verify on production:
- `EMAIL_ENABLED=true`
- `SMTP_SERVER=smtp.gmail.com`
- `SMTP_PORT=587`
- `SMTP_USERNAME=<workspace sender>`
- `SMTP_PASSWORD=<google app password>`
- `FROM_EMAIL=<same sender>`
- `FROM_NAME=StrideIQ`

### 4) Password reset E2E verification

- Trigger `/forgot-password` on production.
- Receive reset email.
- Reset password via token link.
- Confirm login succeeds with new password.

---

## Out of Scope

- No provider migration.
- No DNS/SPF/DKIM/DMARC work in this task.
- No marketing/notification campaign work.
- No UI redesign.

---

## What NOT To Do

- Do NOT introduce Resend/SendGrid/Mailgun.
- Do NOT add Gmail API service-account path.
- Do NOT commit app passwords/secrets.
- Do NOT leave any reference to `performancefocused.com` sender identity.

---

## Tests Required

Target file(s): existing email and auth reset tests.

Minimum:
- `test_email_service_sends_with_valid_config` (mock SMTP, verify from/subject/body)
- `test_email_service_disabled_does_not_send`
- `test_email_service_handles_smtp_failure`
- `test_password_reset_flow_end_to_end` (forgot -> token -> reset -> login)

Paste command output in handoff.

---

## Evidence Required in Handoff

1. Scoped changed-file list.
2. Test output (verbatim).
3. Production proof:
   - forgot-password request accepted
   - reset email received (show From + subject)
   - password reset success
   - login success after reset
4. Confirmation that sender domain is `strideiq.run`, not old brand.

---

## Acceptance Criteria

- Password reset emails deliver in production.
- Sender identity is StrideIQ domain.
- No secret leakage.
- Existing auth flows remain stable.
