# ADR-009: Pace Calculator Overhaul and In-App Access

## Status
Accepted

## Date
2026-01-11

## Context

The Training Pace Calculator has multiple issues:

1. **Accuracy issues**: The fallback formulas in `vdot_calculator.py` were producing wildly incorrect values (26:16/mi for easy pace instead of ~8:00/mi). This was fixed with regression-based formulas, but needs comprehensive verification.

2. **Accessibility**: The pace calculator should be available to ALL users (free and paid) as a value-add tool that builds trust and demonstrates our expertise.

3. **User experience**: Currently, accessing certain tools redirects authenticated users back to the landing page. This is unprofessional and breaks the in-app experience. Subscribed athletes should access all tools without leaving the authenticated experience.

## Decision

### 1. Calculator Accuracy

Implement comprehensive verification against Daniels' Running Formula tables:
- Test VDOT values 30-70 (covers recreational to elite runners)
- Verify all pace types: Easy, Marathon, Threshold, Interval, Repetition
- Maximum acceptable variance: ±5 seconds per mile from published tables
- Create automated test suite that validates against known values

### 2. Free Tier Access

The pace calculator becomes available to ALL users:
- No authentication required to use the calculator
- Located at `/tools/pace-calculator` (or similar)
- Full functionality: race time input, VDOT calculation, all training paces
- Serves as a lead generation tool and demonstrates product quality

### 3. In-App Tool Access

Authenticated users access tools within the app:
- Tools menu/page accessible from main navigation
- No redirect to marketing/landing pages
- Consistent authenticated experience
- Same calculator, different context (in-app vs public)

## Implementation

### Calculator Component
```
/apps/web/app/tools/pace-calculator/page.tsx  (public)
/apps/web/components/tools/PaceCalculator.tsx (shared component)
```

### Navigation Updates
- Add "Tools" to main navigation for authenticated users
- Tools page includes: Pace Calculator, (future: Race Predictor, etc.)

### Routing
- `/tools/*` routes are public (no auth required)
- Authenticated users see same content but with app navigation
- No redirect logic that pushes users out of authenticated context

## Verification Requirements

### Daniels' Table Reference Values (sample)

| VDOT | Easy (slow) | Marathon | Threshold | Interval | Rep |
|------|-------------|----------|-----------|----------|-----|
| 35 | 11:00 | 10:26 | 9:36 | 8:42 | 8:03 |
| 40 | 10:32 | 8:53 | 8:12 | 7:27 | 6:54 |
| 45 | 9:18 | 7:48 | 7:12 | 6:33 | 6:03 |
| 50 | 8:48 | 7:13 | 6:40 | 6:02 | 5:36 |
| 55 | 8:02 | 6:35 | 6:04 | 5:30 | 5:06 |
| 60 | 7:34 | 6:04 | 5:35 | 5:05 | 4:43 |
| 65 | 7:06 | 5:42 | 5:14 | 4:44 | 4:23 |
| 70 | 6:40 | 5:22 | 4:55 | 4:27 | 4:07 |

### Test Cases for Race Times

| Race | Time | Expected VDOT |
|------|------|---------------|
| 5K | 20:00 | ~50 |
| 5K | 25:00 | ~40 |
| 10K | 42:00 | ~50 |
| Half | 1:27:14 | ~53 |
| Half | 1:45:00 | ~45 |
| Marathon | 3:00:00 | ~53 |
| Marathon | 4:00:00 | ~42 |

## Security Considerations

1. **Rate limiting**: Public calculator endpoint should be rate-limited
2. **Input validation**: Race time bounds (reasonable min/max values)
3. **No PII**: Calculator doesn't require or store personal data

## Testing Requirements

1. **Unit tests**: VDOT calculation accuracy across full range
2. **Unit tests**: Training pace accuracy for each pace type
3. **Integration tests**: End-to-end calculator flow
4. **Accessibility**: Calculator works for unauthenticated and authenticated users

## Consequences

### Positive
- Accurate, verified pace calculations build user trust
- Free calculator serves as lead generation tool
- Professional in-app experience for subscribers
- Demonstrates product quality before purchase

### Negative
- Additional public endpoints to maintain
- Potential for abuse (rate limiting mitigates)

### Mitigation
- Comprehensive test suite catches regressions
- Rate limiting prevents abuse
- Shared component reduces maintenance burden
