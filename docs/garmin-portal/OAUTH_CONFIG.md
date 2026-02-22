# Garmin OAuth 2.0 PKCE Flow — Official Portal Documentation

**Source:** Garmin Connect Developer Program > OAuth2 Tools
**Captured:** February 22, 2026

---

## Flow Type: OAuth 2.0 with PKCE

Confirmed via portal OAuth2 Tools wizard. NOT OAuth 1.0a (token-exchange endpoint
in Partner API is a legacy migration path only).

### 4-Step Flow

1. Create a secret code verifier and code challenge
2. Build the authorization URL and redirect the user to the authorization server
3. After the user is redirected back to the client, verify the state
4. Exchange the authorization code and code verifier for an access token

---

## Step 1: Code Verifier and Challenge

**Code Verifier:**
- Cryptographically random string
- Characters: A-Z, a-z, 0-9, and punctuation `-.~_`
- Length: between 43 and 128 characters
- Must be stored server-side for later exchange

**Code Challenge:**
- `base64url(sha256(code_verifier))` when device supports SHA256
- Otherwise, the verifier string itself is used as the challenge (plain method)
- We will always use S256

---

## Step 2: Authorization URL

**Base URL:** `https://connect.garmin.com/oauth2Confirm`

**Query Parameters:**

| Parameter | Value | Notes |
|-----------|-------|-------|
| `client_id` | `{GARMIN_CLIENT_ID}` | From env var, e.g. `b9e5cbc5-c156-4735-b6e3-a5930e3c79b9` |
| `response_type` | `code` | Fixed |
| `state` | `{random_string}` | Optional but recommended. Used to look up code_verifier and user. |
| `redirect_uri` | `{GARMIN_REDIRECT_URI}` | Production: `https://strideiq.run/v1/garmin/callback` |
| `code_challenge` | `{base64url_sha256_of_verifier}` | From Step 1 |
| `code_challenge_method` | `S256` | Fixed |

**Example curl:**
```
curl --request GET --url "https://connect.garmin.com/oauth2Confirm?client_id=b9e5cbc5-c156-4735-b6e3-a5930e3c79b9&response_type=code&state={state}&redirect_uri=https://strideiq.run/v1/garmin/callback&code_challenge={challenge}&code_challenge_method=S256"
```

---

## User Consent Screen

After redirecting, the user sees the Garmin consent screen showing the StrideIQ
logo and brand name. URL changes to:
`connect.garmin.com/partner/oauth2Confirm?client_id=...&response_type=...`

**User-facing permission toggles:**

| Permission | Default | Maps to API Permission |
|------------|---------|----------------------|
| Activities | ON | `ACTIVITY_EXPORT` |
| Women's Health | ON | `MCT_EXPORT` |
| Daily Health Stats | ON | `HEALTH_EXPORT` |
| Historical Data | OFF | Controls backfill access |

**Key behaviors:**
- User can toggle each permission independently
- Historical Data is OFF by default (impacts D7 backfill)
- "StrideIQ Privacy Policy" link is shown — must point to real policy before launch
- User can change selections at any time in app settings
- Save = grant, Cancel = deny

---

## Step 3: Callback (not yet captured — requires user authorization)

**Expected callback parameters (standard OAuth 2.0 PKCE):**
- `code` — authorization code
- `state` — must match the state sent in Step 2

**Callback URL:** `{GARMIN_REDIRECT_URI}?code={auth_code}&state={state}`

---

## Step 4: Token Exchange (not yet captured — requires user authorization)

**Expected behavior (standard OAuth 2.0 PKCE + confirmed by Partner API schema):**

**Token response fields (from `OAuthTokenExchangeResp` schema):**
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

**Key facts:**
- Access tokens expire (`expires_in` field)
- Refresh tokens also expire (`refresh_token_expires_in` field)
- D2.2 must handle refresh token expiry → re-auth flow

---

## Portal Sidebar Sections (for reference)

- Endpoint Configuration
- Data Viewer
- Backfill
- Summary Resender
- Data Generator
- Partner Verification
- Connect Status
- API Configuration
- API Documentation
- API Pull Token
- OAuth2 Tools (this page)
- User Authorization
- Refresh Token
