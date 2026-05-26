# ⚡ Quick Start - Conversion Monitoring

## 📊 Access Your Dashboard
**URL:** `https://absoluteadas.com/analytics-dashboard.html`

---

## 🎯 Daily Checklist

### Monday (Start of Week)
- [ ] Open dashboard
- [ ] Record: page views, CTA clicks, conversion rate
- [ ] Check: which CTA button is winning
- [ ] Note: phone vs. form ratio

### Wednesday (Mid-Week)
- [ ] Dashboard check - any significant changes?
- [ ] Are CTAs performing as expected?
- [ ] Any technical issues?

### Friday (End of Week)
- [ ] Click "📥 Export CSV"
- [ ] Save with date: `conversions-2026-05-31.csv`
- [ ] Calculate: weekly conversion rate
- [ ] Plan: next week's test (if ready)

---

## 📈 What to Look For

### Healthy Metrics:
- ✅ 20-30 page views per day
- ✅ 1-2 CTA clicks per day (5-10% conversion)
- ✅ Consistent performance day-to-day

### Red Flags:
- ❌ Zero page views for 24+ hours (site down?)
- ❌ Zero clicks for 3+ days (CTA broken?)
- ❌ Drop >30% from previous week (what changed?)

---

## 🧪 Running an A/B Test

### Step 1: Change the Headline
Edit `index.html`, find this line:
```html
<h1 class="ao-h1">Local Collision Shops Are Quietly Adding...
```

Replace with Variant B:
```html
<h1 class="ao-h1">Your Shop Is Losing $153,000 Per Year...
```

### Step 2: Push to GitHub
```bash
git add index.html
git commit -m "A/B Test: Activate Variant B headline"
git push origin main
```

### Step 3: Monitor for 1 Week
- Dashboard auto-updates
- Track clicks on new headline
- Don't change anything else

### Step 4: Compare Results
- Export CSV
- Compare Variant B clicks vs. baseline
- Winner = higher click count
- Declare winner if >15% difference

---

## 📱 Phone vs. Form Monitoring

### Weekly Ratio Check:
1. Open dashboard
2. Look at event log
3. Count: `phone_cta` vs `final_cta` clicks
4. Calculate: % phone = (phone clicks / total clicks) × 100

### Expected:
- Phone: 40-50% (people like direct contact)
- Form: 50-60% (people like self-service)

### If Phone Winning (>60%):
- [ ] Add sticky "Call Now" button
- [ ] Promote phone number in copy
- [ ] Reduce form fields

### If Form Winning (>70%):
- [ ] Simplify contact form (fewer fields)
- [ ] Add more form entry points
- [ ] Reduce phone CTA prominence

---

## 🎯 CTA Button Performance

### Dashboard shows which button gets most clicks:

| Rank | Button | Best | Strategy |
|------|--------|------|----------|
| 🥇 | Hero CTA | 35-45% | Keep prominent |
| 🥈 | Final CTA | 25-35% | Optimize copy |
| 🥉 | Phone CTA | 10-20% | Test placement |
| 4️⃣ | Others | 5-15% | Monitor |

**Action:** If a button drops >20%, investigate why (broken link? moved?)

---

## 🚨 Troubleshooting

### "Dashboard shows no data"
1. Refresh page (Cmd+R)
2. Check browser console (Cmd+Option+J)
3. Look for errors
4. Try a different browser
5. Verify localStorage: `localStorage.getItem('ao_conversions')`

### "CTA isn't tracking"
1. Check button has `onclick="trackEvent(...)"`
2. Verify button ID is unique (hero_cta, etc.)
3. Open browser console, click button
4. Should see: "📊 Conversion tracked: {...}"

### "Numbers seem low"
- Normal! You need time to get data
- First 1-2 weeks: expect 20-50 visitors
- After 1 month: ~100+ visitors
- After 3 months: 300+ visitors for real patterns

---

## 📊 Expected Weekly Numbers

| Week | Page Views | CTA Clicks | Conv Rate |
|------|-----------|-----------|-----------|
| 1 (Baseline) | 20-30 | 1-3 | 2-5% |
| 2 (Test B) | 20-30 | 2-5 | 5-10%? |
| 3 (Compare) | 20-30 | 2-5 | See trend |
| 4+ (Winner) | 20-30 | 3-6 | Improved |

**Goal:** Track improvement week-over-week

---

## 💡 When to Make Changes

### Good reasons to change headline:
- ✅ Variant B got >15% more clicks than A
- ✅ Analysis shows clear winner
- ✅ You've collected 200+ visitors (1+ month)

### Bad reasons:
- ❌ Only 2 days of data
- ❌ "Feels" better
- ❌ One person's opinion
- ❌ <50 total visitors

**Rule:** Minimum 1 week + 100 visitors before deciding

---

## 📞 Button IDs for Reference

Copy these for data analysis:

```
hero_cta = Hero button (top of page)
urgency_cta = Urgency band (after hero)
pain_cta = Pain section button
proof_cta = Proof section button  
offer_cta = Offer section button
final_cta = Final CTA button (bottom)
phone_cta = Phone button
```

---

## 🔄 Weekly Meeting Notes Template

```markdown
## Week of May 26, 2026

**Baseline Metrics:**
- Page Views: __
- Total Clicks: __
- Conversion Rate: __%
- Top Button: __

**Phone vs Form:**
- Phone Clicks: __ (_%
- Form Clicks: __ (_%

**Changes Made:**
- [ ] None (baseline week)
- [ ] Other: __

**Next Week Plan:**
- [ ] Continue monitoring
- [ ] Prepare Variant B
- [ ] Other: __

**Notes:**
- 

```

---

## ✅ You're All Set!

**What's running:**
- ✅ Tracking code (live)
- ✅ Dashboard (updating)
- ✅ A/B tests (ready)

**What to do:**
- 🔍 Monitor the dashboard
- 📊 Export data weekly
- 🧪 Run tests when ready
- 📈 Track improvements

**That's it.** The system is automated. You just observe and decide.

---

## 🎯 Success Looks Like:

**In 1 week:** Baseline established  
**In 2 weeks:** First test results visible  
**In 4 weeks:** Clear winning headline  
**In 12 weeks:** Conversion rate +70-115%

**Your job:** Just check the dashboard weekly and make one small change at a time.

Ready? Go check your dashboard! 🚀
