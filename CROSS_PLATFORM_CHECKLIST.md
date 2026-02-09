# Cross-Platform Testing Checklist

**Generated:** January 7, 2026  
**Status:** Pre-beta verification

---

## Platform Coverage

| Platform | Device Type | Priority | Notes |
|----------|-------------|----------|-------|
| **iOS Safari** | iPhone | HIGH | Most mobile users |
| **Android Chrome** | Phone | HIGH | Most mobile users |
| **Chrome Desktop** | Windows/Mac | HIGH | Coach/founder primary |
| **Safari Desktop** | Mac | MEDIUM | Mac users |
| **Firefox** | Desktop | LOW | Power users |
| **Edge** | Windows | LOW | Windows default |
| **Tablet** | iPad/Android | MEDIUM | Coaches |

---

## Changes Applied for Cross-Platform Support

### ✅ Viewport & PWA
- [x] `viewport-fit: cover` for iPhone notch
- [x] `maximum-scale: 1` to prevent double-tap zoom
- [x] `theme-color: #ea580c` for address bar theming
- [x] `manifest.json` for add-to-homescreen
- [x] `apple-web-app` metadata for iOS standalone
- [x] `format-detection: telephone: false` to prevent auto-linking

### ✅ Safe Areas (iPhone Notch/Home Indicator)
- [x] `env(safe-area-inset-*)` padding on body
- [x] `.safe-area-bottom` utility class
- [x] `.safe-area-top` utility class

### ✅ Touch Targets (44px minimum)
- [x] Global minimum height on buttons/inputs
- [x] Range slider thumb: 28px (larger for fingers)
- [x] `.touch-target` utility class
- [x] Mobile nav links: `py-3` for taller targets

### ✅ Range Sliders (Check-in page)
- [x] `-webkit-slider-thumb` styling
- [x] `-moz-range-thumb` styling
- [x] Track styling for both browsers
- [x] Focus states for accessibility

### ✅ Form Inputs
- [x] `font-size: 16px` minimum (prevents iOS zoom)
- [x] Consistent styling across platforms
- [x] Proper input types for mobile keyboards

### ✅ Mobile Navigation
- [x] Scrollable menu with `max-h-[calc(100vh-8rem)]`
- [x] `.scrollbar-hide` for cleaner look
- [x] Larger touch targets (`py-3`)

### ✅ Dashboard Responsiveness
- [x] Controls stack on mobile (`flex-col sm:flex-row`)
- [x] Smaller heading on mobile (`text-2xl md:text-3xl`)
- [x] Full-width selects on mobile (`flex-1`)

---

## Manual Testing Checklist

### Mobile (iPhone/Android)

#### Check-in Page `/checkin`
- [ ] Sliders respond smoothly to touch
- [ ] Thumb is easy to grab (not too small)
- [ ] Number inputs don't zoom the page
- [ ] "Done" button is easy to tap
- [ ] Page fits without horizontal scroll

#### Dashboard `/dashboard`
- [ ] Charts render and scale correctly
- [ ] Dropdowns are tap-friendly
- [ ] Data loads without errors
- [ ] No horizontal overflow

#### Landing Page `/`
- [ ] Hero section readable
- [ ] Free tools calculators work
- [ ] Navigation hamburger works
- [ ] All CTAs are tappable
- [ ] Pricing section scrolls smoothly

#### Navigation
- [ ] Hamburger menu opens/closes
- [ ] Links are easy to tap
- [ ] Menu scrolls if many items
- [ ] Active state visible

#### Forms
- [ ] Login form keyboard appears correctly
- [ ] Register form keyboard types correct
- [ ] Form validation shows errors
- [ ] Submission works

### Tablet (iPad/Android Tablet)

- [ ] Layout adapts (not just stretched mobile)
- [ ] Charts are readable
- [ ] Split views work (if any)
- [ ] Landscape orientation handled

### Desktop (Windows/Mac)

- [ ] All mouse interactions work
- [ ] Hover states visible
- [ ] Keyboard navigation works
- [ ] Screen reader basics work
- [ ] Charts are readable

---

## Known Issues / TODO

### HIGH Priority (Pre-Beta)
1. **PWA Icons Missing** - Need 192x192 and 512x512 PNG icons
   - Can use favicon generator: https://realfavicongenerator.net
   - Or create simple orange "PFC" text on dark background

2. **Offline Support** - No service worker yet
   - Consider adding later for check-in offline use

### MEDIUM Priority (Post-Beta)
3. **Chart Touch** - Recharts touch interaction could be smoother
   - Consider tooltip on tap instead of hover

4. **Pull-to-Refresh** - Disabled globally, may want per-page control

### LOW Priority
5. **Haptic Feedback** - Could add for slider interactions on iOS
6. **3D Touch / Long Press** - Future enhancement

---

## Testing Tools

### Browser DevTools
- Chrome: Device Toolbar (Ctrl+Shift+M)
- Safari: Responsive Design Mode (Cmd+Option+R)
- Firefox: Responsive Design Mode (Ctrl+Shift+M)

### Real Device Testing
- **iOS:** Use Safari on iPhone, or Mac Safari + iPhone simulator
- **Android:** Use Chrome on Android, or Chrome DevTools remote debugging

### Useful Simulators
- iOS: Xcode Simulator (free, Mac only)
- Android: Android Studio Emulator (free, any OS)
- BrowserStack (paid, but free trial)

---

## Quick Test Procedure

1. **Mobile Quick Test (5 min)**
   ```
   Open localhost:3000 on phone (same WiFi)
   - Tap hamburger menu
   - Navigate to /checkin
   - Drag all 3 sliders
   - Enter HRV number
   - Tap "Done"
   - Check dashboard loads
   ```

2. **Desktop Quick Test (3 min)**
   ```
   Open localhost:3000
   - Click through navigation
   - Try RPI calculator
   - Login/register flow
   - View dashboard
   - Check responsive breakpoints (resize window)
   ```

---

## Accessing From Phone

To test on your phone while running locally:

1. Find your computer's local IP:
   - Windows: `ipconfig` → look for IPv4 Address
   - Mac: `ifconfig` → look for inet under en0

2. Ensure phone is on same WiFi

3. Open browser on phone: `http://YOUR_IP:3000`
   - Example: `http://192.168.1.100:3000`

4. Note: API calls may need CORS adjustment for non-localhost

---

**Document Version:** 1.0  
**Last Updated:** January 7, 2026


