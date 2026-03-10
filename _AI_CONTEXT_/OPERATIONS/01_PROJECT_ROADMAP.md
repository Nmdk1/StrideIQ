# StrideIQ Project Roadmap

> **Last Updated**: 2026-01-09
> **Status**: Pre-Beta Development

---

## Current Phase: Foundation Hardening

Before adding new features, we are ensuring the foundation is rock-solid.

---

## Phase 0: Infrastructure & Stability (CURRENT)

**Goal**: Production-ready infrastructure with zero technical debt.

### 0.1 Code Quality & Stability
| Task | Status | Priority |
|------|--------|----------|
| Fix all console errors in authenticated flow | ✅ Done | P0 |
| Fix auth race conditions | ✅ Done | P0 |
| Fix unit preferences (km/miles) | ✅ Done | P0 |
| Fix race filter on activities page | ✅ Done | P0 |
| Fix activity names from Strava | ✅ Done | P0 |
| Verify all API endpoints have proper auth | 🔲 Pending | P0 |
| Comprehensive error handling in frontend | 🔲 Pending | P1 |
| Loading states for all async operations | 🔲 Pending | P1 |

### 0.2 Version Control & Deployment
| Task | Status | Priority |
|------|--------|----------|
| Push to GitHub (private repo) | 🔲 Pending | P0 |
| Set up branch protection rules | 🔲 Pending | P0 |
| Create staging environment (Vercel) | 🔲 Pending | P0 |
| Create staging environment (Railway) | 🔲 Pending | P0 |
| Create production environment (Vercel) | 🔲 Pending | P0 |
| Create production environment (Railway) | 🔲 Pending | P0 |
| Configure CI/CD pipeline | 🔲 Pending | P1 |
| Set up staging database | 🔲 Pending | P1 |

### 0.3 Security Hardening
| Task | Status | Priority |
|------|--------|----------|
| Email verification flow | 🔲 Pending | P0 |
| Password reset flow | 🔲 Pending | P0 |
| Account lockout after failed attempts | 🔲 Pending | P1 |
| Rate limiting on auth endpoints | 🔲 Pending | P1 |
| Security headers configuration | 🔲 Pending | P1 |
| Dependency audit (npm, pip) | 🔲 Pending | P1 |
| GDPR compliance review | 🔲 Pending | P2 |

---

## Phase 1: Core Product Features

**Goal**: Deliver the minimum viable product that provides real value.

### 1.1 Activity Management
| Task | Status | Priority |
|------|--------|----------|
| Activities list with filtering | ✅ Done | P0 |
| Activity detail page | ✅ Done | P0 |
| Workout type classification | ✅ Done | P0 |
| Manual workout type override | ✅ Done | P1 |
| RPE capture with expected range | ✅ Done | P1 |
| Comparison engine (like-to-like) | ✅ Scaffolded | P1 |
| Activity-first calendar view | 🔲 Pending | P1 |
| Environmental context (weather) | 🔲 Pending | P2 |

### 1.2 Training Intelligence
| Task | Status | Priority |
|------|--------|----------|
| RPI Calculator | ✅ Done | P0 |
| Age-graded performance | ✅ Done | P0 |
| Personal best tracking | ✅ Done | P0 |
| Workout classification system | ✅ Done | P0 |
| Expected RPE model | ✅ Done | P1 |
| RPE gap analysis | ✅ Done | P1 |
| Training load calculation | 🔲 Pending | P1 |
| Fatigue/fitness model (CTL/ATL) | 🔲 Pending | P2 |
| Periodization detection | 🔲 Pending | P2 |

### 1.3 AI Coach
| Task | Status | Priority |
|------|--------|----------|
| Basic chat interface | ✅ Scaffolded | P1 |
| OpenAI Assistants API integration | 🔲 Pending | P1 |
| Persistent conversation threads | 🔲 Pending | P1 |
| Athlete profile injection | 🔲 Pending | P1 |
| Context tiering (7/30/120 days) | 🔲 Pending | P2 |
| Training plan generation | 🔲 Pending | P2 |

---

## Phase 2: Differentiation Features

**Goal**: Features that set StrideIQ apart from competitors.

### 2.1 Deep Analysis
| Task | Status | Priority |
|------|--------|----------|
| Statistical correlation engine | 🔲 Pending | P1 |
| Plain-language diagnostic reports | 🔲 Pending | P1 |
| Confidence scoring (sample size, p-value) | 🔲 Pending | P1 |
| Missing data identification | 🔲 Pending | P2 |
| Training experiment suggestions | 🔲 Pending | P2 |

### 2.2 Wellness Integration
| Task | Status | Priority |
|------|--------|----------|
| HRV tracking (manual entry) | 🔲 Pending | P2 |
| Sleep duration tracking | 🔲 Pending | P2 |
| Resting HR tracking | 🔲 Pending | P2 |
| Garmin wellness data import | 🔲 Pending | P2 |
| Wellness ↔ performance correlation | 🔲 Pending | P2 |

### 2.3 Nutrition (Optional)
| Task | Status | Priority |
|------|--------|----------|
| NLP nutrition input | 🔲 Roadmap | P3 |
| Pre/during/post run nutrition | 🔲 Roadmap | P3 |
| Nutrition ↔ performance correlation | 🔲 Roadmap | P3 |

---

## Phase 3: Scale & Polish

**Goal**: Handle growth and refine the user experience.

### 3.1 Performance
| Task | Status | Priority |
|------|--------|----------|
| Database query optimization | 🔲 Pending | P2 |
| Redis caching strategy | 🔲 Pending | P2 |
| Frontend bundle optimization | 🔲 Pending | P2 |
| Image optimization | 🔲 Pending | P3 |

### 3.2 User Experience
| Task | Status | Priority |
|------|--------|----------|
| Onboarding flow | 🔲 Pending | P1 |
| Help/documentation | 🔲 Pending | P2 |
| Mobile responsiveness audit | 🔲 Pending | P2 |
| Accessibility (WCAG 2.1) | 🔲 Pending | P3 |

### 3.3 Business
| Task | Status | Priority |
|------|--------|----------|
| Stripe payment integration | 🔲 Pending | P1 |
| Subscription management | 🔲 Pending | P1 |
| Usage metering (for AI calls) | 🔲 Pending | P2 |
| Analytics dashboard (founder) | 🔲 Pending | P2 |

---

## Immediate Next Steps (This Week)

1. **Push to GitHub** - Get code into version control
2. **Set up staging environment** - Safe place to test
3. **Verify Strava sync** - Test with full 250+ activities
4. **Complete the calendar view** - Activity-first with plan overlay
5. **Email verification** - Required before beta users

---

## Success Metrics for Beta Launch

| Metric | Target |
|--------|--------|
| Page load time | < 2 seconds |
| API response time (p95) | < 500ms |
| Uptime | > 99.5% |
| Critical bugs | 0 |
| Console errors | 0 |
| Strava sync reliability | > 99% |

---

## Document History

| Date | Change | Author |
|------|--------|--------|
| 2026-01-09 | Initial roadmap | AI Assistant |

