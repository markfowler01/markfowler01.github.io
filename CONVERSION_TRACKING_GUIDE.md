# Conversion Tracking & Testing Guide

## 📊 Live Dashboard

**View real-time conversions:** [Analytics Dashboard](./analytics-dashboard.html)

The dashboard tracks:
- Total page views
- Total CTA clicks by button
- Conversion rate (clicks / views)
- Top-performing CTA button
- Event log with timestamps

**Updates every 10 seconds automatically.**

---

## 🎯 CTA Buttons Being Tracked

| Button | ID | Location | Purpose |
|--------|--|----|---------|
| Hero "Claim Your Free ADAS Audit" | `hero_cta` | Top of page | Primary conversion |
| Urgency Band "Book Your Spot Now" | `urgency_cta` | After hero | Scarcity-driven |
| Pain Section "Show Me Where" | `pain_cta` | Problem section | Mid-funnel |
| Proof Section "I Want the Number" | `proof_cta` | After case study | Social proof |
| Offer Section "Claim My Free Snapshot" | `offer_cta` | Free offer details | Value confirmation |
| Final CTA "Get Your Free Audit" | `final_cta` | Bottom section | Last chance |
| Phone Button "📞 Call Now" | `phone_cta` | Final CTA band | Direct call |

---

## 🧪 A/B Testing Plan

### Currently Active: Variant A
**Headline:** "Local Collision Shops Are Quietly Adding $1,400/Month From The Same Number of Cars. Your Shop Isn't."

**Why this works:** Social proof + competitive urgency

---

### Ready to Test: Variant B
**Headline:** "Your Shop Is Losing $153,000 Per Year. Most Don't Even Know It."

**Why to try:** Direct revenue impact focus

**Expected lift:** +10-15%

**How to activate:**
1. Open `index.html`
2. Find line with "Local Collision Shops..."
3. Replace with Variant B headline
4. Push to GitHub
5. Monitor dashboard for 1-2 weeks (need 200+ samples)

---

### Ready to Test: Variant C
**Headline:** "You're Probably Calibrating ADAS On Vehicles You're Not Charging For. That's Costing You $1,400+/Month AND Creating Liability."

**Why to try:** Combines liability + revenue impact

**Expected lift:** +15-20%

**How to activate:**
1. Same as Variant B
2. Use Variant C headline instead
3. Run for 2 weeks alongside A or replace B

---

## 📱 Phone vs. Form Tracking

### Two Entry Points:

**1. Form Button** (`final_cta`)
- "Get Your Free Audit (3 Spots Left)"
- Leads to contact form
- Tracks as: `cta_click` with button ID `final_cta`

**2. Phone Button** (`phone_cta`)
- "📞 Call Now: 1-844-FIX-ADAS"
- Direct phone link
- Tracks as: `cta_click` with button ID `phone_cta`

### To Compare Performance:

1. **Dashboard shows clicks** for each button
2. **Phone clicks** tell you people prefer direct contact
3. **Form clicks** tell you people want to schedule themselves
4. **Ratio** phone:form conversion helps decide where to focus

**Example Analysis:**
- If phone gets 3x more clicks → Phone is preferred → Consider promoting it
- If form gets 2x more clicks → Self-service preferred → Add more self-serve options

---

## 💾 How Data Is Stored

**Location:** Browser's localStorage (survives page refresh)

**Storage keys:**
- `ao_conversions` - Array of all CTA clicks (max 100 most recent)
- `ao_pageviews` - Array of page views (max 100 most recent)

**What's tracked per event:**
```json
{
  "timestamp": "2026-05-26T14:30:00.000Z",
  "eventName": "cta_click",
  "buttonId": "hero_cta",
  "page": "/",
  "userAgent": "Mozilla/5.0..."
}
```

**Access the data:**
```javascript
// In browser console
JSON.parse(localStorage.getItem('ao_conversions'))
JSON.parse(localStorage.getItem('ao_pageviews'))
```

---

## 📈 Interpreting Results

### Weekly Metrics to Monitor:

| Metric | Target | Current |
|--------|--------|---------|
| Page Views | 100+ | — |
| CTA Clicks | 2-3% of views | — |
| Phone Clicks | 40-50% of total | — |
| Hero Button % | 35-45% of clicks | — |
| Final Button % | 25-35% of clicks | — |

### Sample Size for Significance:

- **Need 200+ page views** to declare a winner between variants
- **At 2.5% conversion:** 200 views = 5 conversions
- **With 2 variants:** Takes ~1-2 weeks to get statistical power

---

## 🚀 Testing Workflow

### Week 1: Establish Baseline (Variant A)
- [ ] Deploy current site
- [ ] Let it run for 1 full week
- [ ] Dashboard goal: 100+ page views, 2-3+ clicks
- [ ] Record baseline conversion rate

### Week 2-3: Test Variant B
- [ ] Change headline to Variant B
- [ ] Push to GitHub
- [ ] Run for 1 full week
- [ ] Compare: Variant B clicks vs. Variant A baseline
- [ ] Winner declared if B gets >15% more clicks (statistically)

### Week 4-5: Test Variant C (or iterate on winner)
- [ ] If B won: Test C against B
- [ ] If A won: Keep A, test something else
- [ ] Repeat process

### Ongoing: Monitor Phone vs. Form
- [ ] Track ratio every week
- [ ] If phone winning: Add sticky phone button
- [ ] If form winning: Simplify form fields

---

## 🔧 How to Create New Test

1. **Modify the copy** in `index.html`
2. **Note the change** in a comment: `<!-- TEST: Variant B - Revenue angle -->`
3. **Push to GitHub** (auto-deploys via Pages)
4. **Let run for 1-2 weeks** (minimum 200 visitors)
5. **Export data:** Click "📥 Export CSV" on dashboard
6. **Analyze:** Compare clicks for each variant
7. **Decide:** Keep winner, test next variant

---

## 📊 Expected Conversion Improvements

Based on Sabry Suby methodology:

| Change | Expected Lift |
|--------|---|
| Aggressive headline | +15-20% |
| Urgency/scarcity band | +20-25% |
| Objection removal section | +10-15% |
| Guarantee emphasis | +15-25% |
| **Total combined** | **+70-115%** |

**Current baseline:** 2-3%  
**After all changes:** 3.4-6.5%  
**Your target:** Monitor and adjust to find peak

---

## 🎯 Quick Start

1. **Open dashboard:** Visit `/analytics-dashboard.html` in browser
2. **Click buttons on main site** to generate test data
3. **Watch metrics update** (every 10 seconds)
4. **Export data** (CSV) after 1 week for analysis
5. **Run A/B test** using Variant B headline
6. **Compare results** after 2 weeks

---

## ⚠️ Important Notes

- **No server tracking required** - Everything is localStorage-based
- **Browser-specific** - Each browser stores its own data (use same device for testing)
- **Data persists** until manually cleared or localStorage is cleared
- **Export often** - Keep copies of data in case of cache clearing
- **Sample size matters** - Don't declare winners until you have 200+ visitors

---

## 📞 Support

For questions about:
- **Variants:** See A/B Testing Plan section
- **Tracking:** See How Data Is Stored section
- **Analysis:** See Interpreting Results section
- **New tests:** See How to Create New Test section
