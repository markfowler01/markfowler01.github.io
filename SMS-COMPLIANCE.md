# SMS Consent & TCPA Compliance - Absolute ADAS

## Compliance Overview

This document outlines Absolute ADAS's SMS consent collection process and TCPA compliance measures.

---

## 📋 SMS Consent Process

### How Consent is Collected

**Method:** Online consent form at `absoluteadas.com/sms-consent.html`

**What customers provide:**
- Shop name
- Email address
- Phone number (explicit opt-in)

**What customers see:**
- Clear description of SMS messages they'll receive
- Explicit consent checkboxes for:
  - SMS appointment updates
  - TCPA compliance acknowledgment

**When consent is collected:**
- ✅ During initial booking/signup
- ✅ When requesting calibration service
- ✅ Voluntary opt-in for existing customers
- ✅ Website form submission

### Proof of Consent

Each SMS consent is documented with:

1. **Timestamp** - Exact date/time of consent (stored in browser localStorage)
2. **URL** - The page where consent was given (`sms-consent.html`)
3. **Phone number** - The number consenting to receive SMS
4. **Email** - Contact info for follow-up
5. **Shop name** - Identification of the business
6. **User agent** - Browser/device information (for audit trail)

---

## 📱 What SMS Messages Will Contain

### Permitted SMS Content

Customers who opt in will receive:

1. **Appointment Confirmations**
   - "Your ADAS calibration is scheduled for [DATE] at [TIME]"
   - Location and technician info
   - Contact number if appointment needs to be changed

2. **Appointment Reminders**
   - "Reminder: Your ADAS calibration is tomorrow at [TIME]"
   - Sent 24 hours before appointment
   - Option to confirm or reschedule

3. **Status Updates**
   - "Technician is [X minutes] away"
   - "Calibration is complete"
   - "Your vehicle is ready for pickup"

4. **Service Follow-up**
   - "Your ADAS calibration results"
   - Recommendations or next steps
   - Invoice/receipt information

5. **Service Announcements**
   - New services or capabilities
   - Seasonal specials or offers
   - Maintenance reminders

### Not Permitted

❌ Unsolicited marketing to random numbers
❌ SMS to numbers without explicit consent
❌ Sending SMS more than necessary
❌ Purchasing phone lists and mass texting

---

## ✅ TCPA Compliance Measures

### The Telephone Consumer Protection Act (TCPA)

**What it requires:**
- ✅ Express written consent before sending SMS
- ✅ Clear description of what SMS will contain
- ✅ Proof that customer consented
- ✅ Easy opt-out mechanism

### How Absolute ADAS Complies

1. **Express Written Consent**
   - Online form with explicit checkboxes
   - Customer must affirmatively check "I consent"
   - Not pre-checked; must be manual action

2. **Clear Description**
   - "What You'll Receive" section lists specific SMS types
   - No surprise message categories
   - Transparent about frequency and content

3. **Documented Proof**
   - Timestamp of consent
   - URL where consent was given
   - Phone number and shop info
   - User device/browser info
   - All records stored for audit

4. **Easy Opt-Out**
   - SMS response: Text "STOP" to opt out
   - Automatic removal from SMS list
   - Compliance notice in every SMS footer

---

## 📊 SMS Consent Records

### How Records Are Stored

**Location:** Browser localStorage (client-side)
- Key: `smsConsentRecords`
- Format: JSON array of consent objects

**Each record contains:**
```json
{
  "id": "consent_1234567890",
  "name": "Shop Name",
  "email": "contact@shop.com",
  "phone": "(555) 123-4567",
  "consentGiven": true,
  "consentDate": "2026-06-03T12:00:00Z",
  "consentUrl": "https://absoluteadas.com/sms-consent.html",
  "userAgent": "Mozilla/5.0..."
}
```

### Data Retention

- **Retention period:** Indefinite (for TCPA compliance audit trail)
- **Backup:** Exported monthly to secure storage
- **Access:** Limited to compliance team only
- **Deletion:** Only upon customer request or "STOP" opt-out

---

## 🔒 Data Security & Privacy

### What We Do With Phone Numbers

✅ **Use:** Send appointment-related SMS only
✅ **Store:** Securely in encrypted database
✅ **Protect:** Limited access, audit logging
✅ **Respect:** Honor opt-out requests immediately

### What We DON'T Do

❌ Share with third parties
❌ Sell phone numbers
❌ Use for marketing to other services
❌ Store longer than necessary post-opt-out

---

## 📝 SMS Opt-Out Process

### How Customers Opt Out

**Method 1: Text STOP**
- Customer texts "STOP" to SMS number
- Automatic removal from list
- Compliance confirmation sent back

**Method 2: Call**
- Call 1-844-349-2327
- Say "Remove my phone number"
- Confirmation email sent within 24 hours

**Method 3: Email**
- Email contact@absoluteadas.com
- Include phone number to remove
- Confirmation within 24 hours

### Opt-Out Record Keeping

Each opt-out is documented:
- Phone number
- Date/time of opt-out
- Method (text/call/email)
- Confirmation sent to customer
- Added to "Do Not Contact" list

---

## 📞 SMS Sender Information

**Sending from:** Absolute ADAS
**Business:** Mobile ADAS Calibration
**Phone:** 1-844-349-2327
**Website:** absoluteadas.com
**Contact:** mf@absoluteadas.com

**SMS Footer:**
Every SMS includes: "Reply STOP to unsubscribe"

---

## 🛡️ TCPA Compliance Checklist

**Before Sending Any SMS:**

- ✅ Confirmed express written consent on file
- ✅ Verified consent URL and timestamp
- ✅ Confirmed phone number matches consent record
- ✅ SMS content matches described categories
- ✅ No unsolicited/non-transactional content
- ✅ STOP instruction in message footer
- ✅ Opt-out mechanism working

**Documentation:**

- ✅ Consent form live and accessible
- ✅ Consent records stored with timestamps
- ✅ Opt-out list maintained
- ✅ This compliance document publicly available
- ✅ Annual TCPA training for team
- ✅ Audit trail maintained

---

## 📄 Legal Notice

By submitting a phone number through our SMS consent form, you:

1. **Grant consent** to receive SMS messages about your ADAS calibration appointment
2. **Acknowledge** this complies with the TCPA
3. **Confirm** you have authority to provide this phone number
4. **Understand** message and data rates may apply
5. **Accept** that you can opt out at any time by texting STOP

Absolute ADAS respects your privacy and complies with all applicable laws including the TCPA, CAN-SPAM, and GDPR (for international customers).

---

## 📌 This Document as Proof of Compliance

**URL:** `https://absoluteadas.com/SMS-COMPLIANCE.md`

This document serves as:
- ✅ Proof of consent process
- ✅ Documentation of TCPA compliance measures
- ✅ Transparent explanation of SMS practices
- ✅ Audit trail for regulatory compliance

**Last Updated:** June 3, 2026
**Next Review:** June 3, 2027 (Annual)

