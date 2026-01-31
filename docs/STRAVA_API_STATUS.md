# Strava API Status

**Status:** APPROVED ✅  
**Approved:** 2026-01-31  
**Application Submitted:** 2026-01-30

---

## Rate Limits (Approved)

| Limit Type | Per 15 Minutes | Per Day |
|------------|----------------|---------|
| **Overall Rate Limit** | 600 requests | 6,000 requests |
| **Read Rate Limit** | 300 requests | 3,000 requests |

**Athlete Capacity:** 999 users

---

## What This Means

1. **Can sync up to 999 athletes** - Sufficient for beta and early growth
2. **300 reads per 15 min** - ~20 reads/minute sustained
3. **6,000 requests/day** - Enough for active user base

---

## Rate Limit Math

At 999 athletes with average 1 activity/day:
- Daily activity syncs: ~1,000 requests
- Webhook confirmations: ~1,000 requests
- User-initiated refreshes: ~500 requests
- **Total:** ~2,500/day (well under 6,000 limit)

---

## Next Steps

1. ✅ Application approved
2. [ ] Verify webhook is receiving events
3. [ ] Test OAuth flow in production
4. [ ] Monitor rate limit usage
5. [ ] Request capacity increase when approaching 999 athletes

---

## Support Resources

- **Developer Community:** https://developers.strava.com/
- **Developer Hub:** https://developers.strava.com/

---

## Credentials Location

Strava credentials are stored in:
- **Local:** `.env` file
- **Production:** Droplet `.env` at `/opt/strideiq/repo/.env`

Environment variables:
```
STRAVA_CLIENT_ID=xxxxx
STRAVA_CLIENT_SECRET=xxxxx
STRAVA_REDIRECT_URI=https://strideiq.run/auth/strava/callback
```

---

**Last Updated:** 2026-01-31
