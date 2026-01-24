## Ops Playbook (Owner)

### Emergency Checklist (10 lines)
1. If **Queue looks unhealthy**: open `/admin` → **Ops**.
2. If **Queue > 1000** or rising fast: (Owner or explicitly-permitted admin) toggle **Pause global ingestion** = ON.
3. Confirm Home banner appears (“Import delayed”) so users aren’t confused.
4. Check **Deferred ingestion**: if growing, you’re likely Strava rate-limited (expected under spikes).
5. Check **Stuck ingestion**: if non-zero, spot-check one user and hit **Retry ingestion** (only after pause is OFF).
6. Check **Recent ingestion errors**: if token/auth errors spike, pause ingestion and investigate before retrying.
7. If you need to protect Strava quotas: keep pause ON until traffic stabilizes.
8. When stable: toggle **Pause global ingestion** = OFF and watch queue + deferred count for 5–10 minutes.
9. If backlog remains: selectively retry ingestion for the most important users (support priority).
10. After incident: write down what happened + timestamps and add one regression test if a gap was discovered.

**Note:** If an admin can’t pause ingestion, the owner can grant `system.ingestion.pause` via `POST /v1/admin/users/{id}/permissions`.

