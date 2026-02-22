# Garmin Partner API — Official Portal Documentation

**Source:** `https://apis.garmin.com/tools/apiDocs/user-api`
**Captured:** February 22, 2026
**Server:** `https://apis.garmin.com/partner-gateway` (Prod)

---

## User API

### POST /rest/user/token-exchange

Exchange existing OAuth 1.0a tokens for OAuth 2.0 tokens. 1-to-1 mapping per user.

**Parameters:** None (uses existing OAuth 1.0a auth)

**Response schema (`OAuthTokenExchangeResp`):**

```json
{
  "access_token": "string",
  "token_type": "string",
  "refresh_token": "string",
  "expires_in": 0,
  "scope": "string",
  "refresh_token_expires_in": 0
}
```

**Fields:**
- `access_token` (string) — OAuth 2.0 access token
- `token_type` (string) — token type
- `refresh_token` (string) — OAuth 2.0 refresh token
- `expires_in` (int32) — access token TTL in seconds
- `scope` (string) — granted scope
- `refresh_token_expires_in` (int32) — refresh token TTL in seconds

**Key implications:**
- Garmin's primary OAuth flow is OAuth 1.0a, with this endpoint as a migration path to OAuth 2.0
- Refresh tokens DO expire (`refresh_token_expires_in` is present)
- D2.2 must handle refresh token expiry (re-auth flow)

---

### GET /rest/user/permissions

Get permissions granted to the partner by the user.

**Parameters:** None (uses OAuth token)

**Response schema (`ClientConsumerPermissions`):**

```json
{
  "userId": "4aacafe82427c251df9c9592d0c06768",
  "summaryId": "x153a9f3-5a9478d4-6",
  "permissions": "[ACTIVITY_EXPORT, WORKOUT_IMPORT, HEALTH_EXPORT, COURSE_IMPORT, MCT_EXPORT]",
  "changeTimeInSeconds": 1613065860
}
```

**Official permission enum values:**
- `ACTIVITY_EXPORT` — activities, activity details, activity files
- `HEALTH_EXPORT` — dailies, epochs, sleeps, HRV, stress, body comp, respiration, pulse ox, etc.
- `MCT_EXPORT` — menstrual cycle tracking
- `WORKOUT_IMPORT` — push workouts to device (not used in Phase 2)
- `COURSE_IMPORT` — push courses to device (not used in Phase 2)

**StrideIQ needs:** `ACTIVITY_EXPORT`, `HEALTH_EXPORT`, `MCT_EXPORT`

---

### GET /rest/user/id

Get the Connect Developer User ID. Persists across multiple User Access Tokens from the same user.

**Response:**

```json
{
  "userId": "4aacafe82427c251df9c9592d0c06768"
}
```

**Important:** This is the stable user identifier. Use this for the `garmin_user_id` field on the Athlete model. It survives token refresh/re-auth.

---

### DELETE /rest/user/registration

Delete the user access token, removing the association between the user and the app.

**Response:** `204 No Content` (empty body)

**This is the deregistration endpoint for D2.3 disconnect flow.**

---

## Schemas

```
OAuthTokenExchangeResp {
  access_token:              string
  token_type:                string
  refresh_token:             string
  expires_in:                int32
  scope:                     string
  refresh_token_expires_in:  int32
}

ClientConsumerPermissions {
  userId:              string    (e.g. "4aacafe82427c251df9c9592d0c06768")
  summaryId:           string    (e.g. "x153a9f3-5a9478d4-6")
  permissions:         string[]  (enum values)
  changeTimeInSeconds: int32     (Unix epoch)
}

ClientUserId {
  userId: string
}

ServiceFailure {
  errorType:    string
  message:      string
  errorMessage: string
  errorId:      string
}

ApiServiceFailure {
  errorMessage: string
}
```
