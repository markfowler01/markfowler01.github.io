# 📅 Monthly Scarcity Messaging Update Guide

## Current Month: JUNE 2026

Update these 4 locations in `index.html` at the start of each month:

---

## 🔧 Update Template

**Copy and replace these sections in index.html:**

### 1️⃣ Urgency Band - Month Label (Line 917)
**Current:**
```html
🔴 April Audit Spots
```

**June (Replace with):**
```html
🔴 June Audit Spots
```

---

### 2️⃣ Urgency Band - Spots Count (Line ~919)
**Current:**
```html
3
```

**June (Replace with):**
```html
[NUMBER OF SPOTS AVAILABLE]
```

**Options:**
- `3` = All 3 spots available (month just started)
- `2` = 2 of 3 remaining
- `1` = 1 of 3 remaining  
- `0` = No spots available

---

### 3️⃣ Offer Section - Spots Message (Line 1178)
**Current:**
```html
We open <strong style="color:var(--orange);">8 new shop audit slots</strong> each month. <strong style="color:var(--orange);">April slots: 3 remaining.</strong>
```

**June (Replace with):**
```html
We open <strong style="color:var(--orange);">3 new shop audit slots</strong> each month. <strong style="color:var(--orange);">June slots: [X] remaining.</strong>
```

---

### 4️⃣ Final CTA Band - Deadline Message (Lines 1407-1408)
**Current:**
```html
🔴 <strong>April Audit Deadline: This Week</strong>

3 spots available before slots close and reset May 1st. Book now or wait 8 days.
```

**June (Replace with):**
```html
🔴 <strong>June Audit Deadline: End of Month</strong>

[X] spots available before slots close and reset July 1st. Book now or wait.
```

---

## 📊 Monthly Messaging Scenarios

### **Scenario A: Month Starts (3 Spots Available)**
```
🔴 June Audit Spots
3
"June slots: 3 remaining"
"3 spots available before slots close and reset July 1st"
```

### **Scenario B: Mid-Month (1 Spot Left)**
```
🔴 June Audit Spots
1
"June slots: 1 remaining"
"Only 1 spot left! Book before it's gone and reset July 1st"
```

### **Scenario C: Month Ending (No Spots)**
```
🔴 June Audit Spots (FULL)
0
"June slots: FULL - Wait for July 1st"
"All June spots booked! Next availability opens July 1st"
```

---

## ⏰ Timing

**Update on:**
- 1st of each month (at 9am LA time)
- Update all 4 locations
- Push to GitHub
- Goes live immediately (GitHub Pages auto-deploys)

---

## 🎯 Monthly Schedule Template

Copy this and update each month:

```
JUNE 2026
- Date Updated: June 1, 2026
- Spots Total: 3
- Spots Booked: 0
- Spots Available: 3
- Status: OPEN - All 3 available

JULY 2026
- Date Updated: July 1, 2026
- Spots Total: 3
- Spots Booked: [NUMBER]
- Spots Available: [3 - BOOKED]
- Status: [OPEN / LIMITED / FULL]
```

---

## 💡 Zoho Cliq Strategy

### **Option 1: Automated Cliq Posts** (RECOMMENDED)
Add this to your weekly routine prompt:

```
If any spots became available/unavailable this week:
- Post to #business-updates: "June audit spots: [X]/3 available"
- Update urgency level based on availability
```

### **Option 2: Manual Cliq Announcements**
When updating the website:
1. Update HTML (4 locations)
2. Post to Zoho Cliq:
   - "📅 New month! June audit spots are [STATUS]"
   - Link to absoluteadas.com

### **Option 3: Real-Time Cliq Updates** (ADVANCED)
Store spot count in a shared file that:
- Gets updated when someone books
- Triggers Cliq notification when spots change
- Updates website dynamically

---

## 🚀 Quick Update Checklist

Each month (1st):
- [ ] Check how many spots are booked
- [ ] Calculate remaining (3 - booked)
- [ ] Update 4 HTML locations
- [ ] Push to GitHub
- [ ] Post to Zoho Cliq (optional)
- [ ] Note in analytics report

---

## 📝 Example Commits

```bash
# June 1
git commit -m "Update scarcity messaging: June 2026, 3 spots available"

# Mid-June (if spots change)
git commit -m "Update scarcity messaging: June 2026, 1 spot remaining"

# Late June (if full)
git commit -m "Update scarcity messaging: June audit FULL, July 1 opening"
```

---

## 🎯 Current Status (June 1, 2026)

**What needs updating NOW:**
- [ ] Change "April" → "June" (4 locations)
- [ ] Update spot count based on actual bookings
- [ ] Push to GitHub
- [ ] Done!

---

## Questions?

**For exact line numbers**, search `index.html` for:
- `April Audit Spots`
- `April slots:`
- `April Audit Deadline`

Then replace the month name and numbers accordingly.
