# COROS API Application - Form Responses

**Application URL:** https://docs.google.com/forms/d/e/1FAIpQLSe2i_nIRV62yCeld8J9UR41I_vC34Z2_S82CodxurHHjFEo9Q/viewform

Copy/paste these responses into the form.

---

## Contact Information

**Email:** 
```
michael@strideiq.run
```

**Second email address for continuity of business:**
```
support@strideiq.run
```

**Product Owner / Applicant Name and Title:**
```
Michael Shaffer, Founder
```

**Company Name:**
```
StrideIQ
```

**Company URL:**
```
https://strideiq.run
```

---

## Application Details

**Application Name:**
```
StrideIQ
```

**Application Description (100 Character Limit):**
```
AI running coach with personalized analytics. Sync workouts to unlock insights.
```
*(79 characters)*

**Number of Total Active Users:**
```
0-150
```

**Primary Region of Users:**
```
United States
```

---

## API Functions Needed

Select:
- [x] **Activity/Workout Data Sync**

Leave unchecked:
- [ ] Structured Workouts and Training Plans Sync
- [ ] GPX Route Import / Export
- [ ] Bluetooth Connectivity
- [ ] ANT+ Connectivity

---

## Technical Configuration

**Authorized Callback Domain (redirect_url):**
```
https://strideiq.run
```

**Workout data receiving Endpoint URL:**
```
https://api.strideiq.run/v1/webhooks/coros
```

**Service Status Check URL:**
```
https://api.strideiq.run/health
```

---

## Additional Questions

**If your application/product has a Bluetooth or ANT+ element to it, please provide the link to the protocol/profile, or write N/A:**
```
N/A
```

**Will your application/concept be for personal or public use?**
```
Public use - available to all StrideIQ users who have COROS devices.
```

**Will your application/concept be for commercial or non-commercial use?**
```
Commercial use - StrideIQ is a subscription-based running analytics platform.
```

**Intended use of data? Please describe how mutual user data will be used and processed by your application:**
```
We sync running activities (distance, duration, pace, heart rate, cadence) and daily health metrics (sleep, HRV, resting heart rate) to provide personalized training insights. Our N=1 analysis engine calculates efficiency trends, age-graded performance, and personal records for each individual athlete. No population modeling or data aggregation occurs. User data is never sold, shared, or used for AI model training. Users can delete or export their data at any time per GDPR requirements.
```

---

## App Images

**Have you sent the images?**
- [ ] I've sent these

**AFTER submitting the form, email your logo images to:**
- **To:** api@coros.com
- **Subject:** StrideIQ - API Images
- **Attachments:**
  - Logo 144×144 PNG
  - Logo 102×102 PNG

---

## Logo Image Instructions

Your logo file is at:
```
C:\Users\mbsha\.cursor\projects\c-Dev-StrideIQ\assets\stride_logo.png
```

You need to create two versions:
1. **144×144 pixels** - PNG format
2. **102×102 pixels** - PNG format

Use any image editor (Paint, Photoshop, Canva, or online tool like https://www.iloveimg.com/resize-image) to resize.

---

## After Submission

1. COROS will review and issue clientId and clientSecret
2. Store credentials in production `.env`
3. Implement OAuth flow
4. Implement webhook endpoint
5. Notify COROS 1 week before going live

---

**Created:** 2026-01-31
