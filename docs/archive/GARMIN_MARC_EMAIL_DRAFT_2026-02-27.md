# Draft Email — Marc Lussi (DO NOT COPY THIS LINE)

Everything below the dashed line is clean copy-paste text for your email client.
Fill in the three [BRACKETED] placeholders before sending.
Attach screenshots in the order listed at the bottom.

---

Hi Marc,

Thank you for the detailed review. I've addressed all three sections below.


SECTION 1: TECHNICAL REVIEW

APIs in use (read-only):
  - Activity API — activity summaries
  - Activity Details API — GPS, heart rate, cadence, velocity samples
  - Health API — sleep, HRV, stress, daily metrics, user metrics
  - Women's Health API — requested for production access, currently feature-gated. We plan to use it only with explicit user consent to surface women-specific training and racing insights (cycle-aware context for planning, readiness, and race execution). It is not yet exposed broadly in-product.
  - Training/Courses API — not used. StrideIQ does not write data to Garmin Connect.

Authorization: Two Garmin Connect users are authorized in our evaluation environment (founder + one additional user).

User Deregistration: Endpoint active at /v1/garmin/webhook/deregistrations. Returns HTTP 200 immediately; processing is asynchronous.

User Permissions: Endpoint active at /v1/garmin/webhook/permissions. Returns HTTP 200 immediately; processing is asynchronous.

PING/PUSH: All webhook endpoints receive Garmin push notifications and return HTTP 200 within seconds. Processing is asynchronous via task queue. No scheduled polling pipeline is used.

Payload handling: Endpoints accept payloads up to 100 MB. HTTP 200 is returned immediately on receipt; downstream processing is asynchronous.

Partner Verification Tool: [INSERT VERIFICATION TOOL RESULTS HERE]

Training/Courses API: Not applicable — StrideIQ does not transfer workouts or courses to Garmin Connect.


SECTION 2: TEAM MEMBERS AND ACCOUNT SETUP

API Blog: Subscribed. [INSERT DATE YOU SUBSCRIBED]

Account operator: michael@strideiq.run (company domain, sole operator). No freemail or generic addresses.

Third-party integrators: None. No NDA required.


SECTION 3: UX AND BRAND COMPLIANCE

We have updated all Garmin attribution in StrideIQ to comply with the Garmin API Brand Guidelines v2 (effective 6/30/2025). Changes made:

Activity detail page: Official GARMIN wordmark displayed above the fold, directly beneath the activity title. Device model shown adjacent (e.g., "Forerunner 165"). Former "via Garmin Connect" text removed.

Splits table footer: Official GARMIN wordmark + device model replaces former "Sourced from Garmin Connect" text.

Home page last run: Official GARMIN wordmark + device model replaces former "via Garmin Connect" attribution text.

Settings connected state: Official Garmin Connect app icon displayed with full "Garmin Connect" heading.

Settings disconnected CTA: Official Garmin Connect badge used as the primary connect button. Custom-styled button removed.

AI-derived data attribution: "Insights derived in part from Garmin device-sourced data" displayed on activity surfaces where Garmin data was an input.

Screenshots are attached in order above (Activity detail, Splits, Home, Settings connected, Settings disconnected, Derived-data attribution).

PDF export attribution is out of scope for this UI compliance review and will be addressed as a follow-up once production access is confirmed.


Best regards,
Michael
michael@strideiq.run
StrideIQ


---

BEFORE SENDING (do not include anything below this line in the email):

Fill in these placeholders:
1. Partner Verification Tool results — run the tool, paste results
2. API Blog subscription date — subscribe and note the date

Attach screenshots in this order:
1. Activity detail — Garmin tag logo + device model above the fold
2. Splits table — updated footer
3. Home page — last run with Garmin badge
4. Settings connected — official app icon + heading
5. Settings disconnected — official Garmin Connect badge as CTA
6. Derived-data attribution — "Insights derived in part from Garmin device-sourced data"
