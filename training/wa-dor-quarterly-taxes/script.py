"""Slide text + narration for the WA DOR quarterly excise tax training video.

Each slide: kicker, title, and either bullets (text slide) or image (screenshot slide,
from screens/), plus narration (list of sentences; each becomes one caption).
Narration is written the way the voice should say it; build_video.py fixes captions.
Process follows Absolute ADAS's real Q3 2026 filing screenshots; DOR facts checked Nov 2026.
"""

SLIDES = [
    dict(
        kicker="NEW-HIRE TRAINING",
        title="Filing & paying our quarterly\nWashington excise tax return",
        bullets=["Washington State Department of Revenue (DOR)", "About 7 minutes  ·  follow along with the runbook"],
        narration=[
            "Welcome to Absolute ADAS.",
            "This training walks you through filing and paying our quarterly excise tax return with the Washington State Department of Revenue, also called D O R.",
            "You'll see the real screens from Zoho Books and My D O R. Keep the runbook open while you watch. It has every step as a checklist.",
        ],
    ),
    dict(
        kicker="THE BASICS",
        title="What this return is",
        bullets=[
            "Washington has no state income tax",
            "Instead: B&O tax on our gross receipts",
            "We report it under Service and Other Activities",
            "Filed and paid online in My DOR, every quarter",
        ],
        narration=[
            "Washington doesn't have a state income tax.",
            "Instead, businesses pay B and O tax, which stands for business and occupation, on gross receipts.",
            "We report ours under one line, Service and Other Activities.",
            "The return is filed and paid online in My D O R, once every quarter.",
        ],
    ),
    dict(
        kicker="DEADLINES",
        title="When it's due",
        bullets=[
            "Q1  Jan–Mar   →   April 30",
            "Q2  Apr–Jun   →   July 31",
            "Q3  Jul–Sep   →   October 31",
            "Q4  Oct–Dec   →   January 31",
            "Weekend or holiday? Due the next business day",
            "Our target: filed by the 20th of the due month",
        ],
        narration=[
            "Quarterly returns are due on the last day of the month after the quarter ends.",
            "That's April thirtieth, July thirty-first, October thirty-first, and January thirty-first.",
            "If the due date lands on a weekend or holiday, it moves to the next business day. My D O R shows the exact due date at the top of the return.",
            "For example, the fourth quarter 2026 return is due Monday, February first, 2027.",
            "Our target is to have it filed by the twentieth of the due month, well before the deadline.",
        ],
    ),
    dict(
        kicker="PART 1 · ZOHO BOOKS",
        title="Open Reports → Payments Received",
        image="01_zoho_reports_center.png",
        narration=[
            "Part one. Get the number from Zoho Books.",
            "In Zoho Books, click Reports in the left menu.",
            "Under Report Category, click Payments Received.",
        ],
    ),
    dict(
        kicker="PART 1 · ZOHO BOOKS",
        title="Open the Payments Received report",
        image="02_zoho_payments_received_category.png",
        narration=[
            "In the Payments Received category, open the report also called Payments Received.",
        ],
    ),
    dict(
        kicker="PART 1 · ZOHO BOOKS",
        title="Previous Quarter → check dates → Export PDF",
        image="03_zoho_payments_received_report.png",
        narration=[
            "Set the date range to Previous Quarter and run the report.",
            "Check the dates under the company name. For the third quarter, it should say July first through September thirtieth.",
            "Then click Export and choose P D F. Save the P D F. It's our backup for the return.",
            "Scroll to the bottom of the report. The TOTAL line is the number you'll enter in My D O R.",
        ],
    ),
    dict(
        kicker="PART 2 · MY DOR",
        title="Log in and open the return",
        bullets=[
            "Go to  secure.dor.wa.gov",
            "Sign in with your own SecureAccess Washington login",
            "Select ABSOLUTE ADAS LLC",
            "Click File return for the quarter you're filing",
            "Check the period and the due date at the top",
        ],
        narration=[
            "Part two. File in My D O R.",
            "Go to secure dot D O R dot W A dot gov and sign in with your own SecureAccess Washington login. Mark adds you as a user. Never share a login.",
            "Select Absolute ADAS L L C, find the open return for the quarter, and click File return.",
            "Double-check the period. Filing the wrong quarter is the most common mistake.",
        ],
    ),
    dict(
        kicker="SELECT TAXES",
        title="Keep the same classifications → Next",
        image="04_dor_select_taxes.png",
        narration=[
            "The first screen lists our tax classifications.",
            "Keep the same classifications as last period, and click Next.",
            "Never click Add or Delete Tax Classifications without asking Mark first.",
        ],
    ),
    dict(
        kicker="BUSINESS & OCCUPATION",
        title="Zoho TOTAL goes in Service and Other",
        image="05_dor_business_and_occupation.png",
        narration=[
            "On the Business and Occupation screen, type the Zoho TOTAL into Gross Amount on the Service and Other Activities line.",
            "In this example, that's seventy-four thousand, seven hundred twenty-five dollars and sixty-one cents.",
            "Leave Retailing at zero.",
            "My D O R calculates the tax automatically at one and a half percent. You don't add deductions or credits.",
            "Then click Next.",
        ],
    ),
    dict(
        kicker="STATE SALES AND USE",
        title="Retail Sales stays 0.00",
        image="06_dor_state_sales_and_use.png",
        narration=[
            "On State Sales and Use, Retail Sales stays at zero. We don't collect retail sales tax.",
            "If you ever see sales tax on one of our invoices, stop and ask Mark.",
            "Click Next.",
        ],
    ),
    dict(
        kicker="LOCAL SALES",
        title="Lake Stevens (3109) stays 0.00",
        image="07_dor_local_sales.png",
        narration=[
            "On Local Sales, the Lake Stevens line, location code three one zero nine, also stays at zero.",
            "The Difference box at the bottom should read zero.",
            "Click Next.",
        ],
    ),
    dict(
        kicker="SUMMARY",
        title="Your name, phone, ar@absoluteadas.com, No",
        image="08_dor_summary_submitter.png",
        narration=[
            "The Summary screen shows the line you filed. Check that the period and gross amount are right.",
            "Fill in Prepared By with your name, and your phone number.",
            "For email, use A R at absolute A D A S dot com.",
            "For the Buyers Sales and Use Preference Addendum question, choose No. Then click Next.",
        ],
    ),
    dict(
        kicker="RETURN TOTALS",
        title="Penalty & interest only show up when late",
        image="09_dor_return_totals.png",
        narration=[
            "Return Totals shows what we owe.",
            "Estimated Penalty and Estimated Interest should be zero. They only show up when a return is late, like in this example.",
            "Don't check Request Penalty Waiver on your own. Ask Mark.",
            "Click Next.",
        ],
    ),
    dict(
        kicker="PAYMENT METHOD",
        title="Choose Bank Account (ACH Debit)",
        image="10_dor_payment_method.png",
        narration=[
            "For Payment Method, choose Bank Account, A C H Debit. It's free, and it's how we always pay.",
            "Don't use a card. The processor charges a two point nine six percent fee. And never choose No Payment.",
            "On the next screen, confirm our bank account and set the payment date on or before the due date.",
        ],
    ),
    dict(
        kicker="REVIEW & SUBMIT",
        title="Check every line, then Submit",
        image="11_dor_review_submit.png",
        narration=[
            "On Review and Submit, check four things: total amount due, payment method, payment effective date, and payment amount.",
            "The payment amount must match the total amount due, and the date must be on or before the due date.",
            "Click Submit once. Submitting authorizes D O R to debit our bank account, so never pay the same return a second way.",
        ],
    ),
    dict(
        kicker="CLOSE IT OUT",
        title="Save proof",
        bullets=[
            "Save the confirmation number",
            "Download the filed return as a PDF",
            "Save it with the Zoho Payments Received PDF",
            "Check the bank 1–2 business days after the payment date",
            "Tell Mark it's done",
        ],
        narration=[
            "Last step. Save your proof.",
            "Write down the confirmation number and download a P D F of the filed return.",
            "Save it alongside the Zoho Payments Received P D F for that quarter.",
            "A day or two after the payment date, check the bank account to confirm the debit went through, and let Mark know it's done.",
        ],
    ),
    dict(
        kicker="DON'T BE LATE",
        title="Penalties add up fast",
        bullets=[
            "9%  if not paid by the due date",
            "19%  after the end of the following month",
            "29%  after the end of the second month",
            "Plus interest  ·  minimum penalty $5",
            "No receipts? Still file a no-business return",
        ],
        narration=[
            "Here's why the deadline matters.",
            "If the tax isn't paid by the due date, D O R adds a nine percent penalty.",
            "It jumps to nineteen percent after the end of the following month, and twenty-nine percent after the end of the second month, plus interest.",
            "Even in a quarter with no receipts, we still have to file.",
            "If there's ever a problem paying, file on time anyway and tell Mark right away.",
        ],
    ),
    dict(
        kicker="NOT ON THIS RETURN",
        title="Other quarterly filings",
        bullets=[
            "ESD: unemployment, Paid Family & Medical Leave, WA Cares",
            "L&I: workers' comp quarterly report",
            "IRS: federal estimated tax payments",
            "Each has its own system and deadlines",
        ],
        narration=[
            "Some other quarterly filings are not part of this return.",
            "Employment Security, or E S D, handles unemployment insurance, Paid Family and Medical Leave, and WA Cares.",
            "Labor and Industries handles the workers' comp quarterly report, and federal estimated taxes go to the I R S.",
            "Each one has its own system and deadlines. Those are covered separately.",
        ],
    ),
    dict(
        kicker="RECAP",
        title="You've got this",
        bullets=[
            "Zoho: Payments Received  →  Previous Quarter  →  TOTAL",
            "My DOR: TOTAL in Service and Other; everything else 0.00",
            "Summary  →  ACH Debit  →  Review  →  Submit  →  Save proof",
            "Questions: ask Mark first",
            "DOR Telephone Information Center: 360-705-6705",
        ],
        narration=[
            "To recap: in Zoho, run Payments Received for the previous quarter and grab the total.",
            "In My D O R, put that total on the Service and Other Activities line, and leave everything else at zero.",
            "Fill in the summary, pay by A C H debit, check the review screen, submit, and save your proof.",
            "If anything doesn't look right, ask Mark first. D O R's information line is three six zero, seven zero five, six seven zero five.",
            "Thanks for watching, and welcome to the team.",
        ],
    ),
]
