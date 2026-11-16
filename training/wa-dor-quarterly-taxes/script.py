"""Slide text + narration for the WA DOR quarterly excise tax training video.

Each slide: kicker (small label), title, bullets, and narration (list of sentences;
each sentence becomes one caption). Facts checked against dor.wa.gov in Nov 2026.
"""

SLIDES = [
    dict(
        kicker="NEW-HIRE TRAINING",
        title="Filing & paying our quarterly\nWashington excise tax return",
        bullets=["Washington State Department of Revenue (DOR)", "About 6 minutes  ·  follow along with the runbook"],
        narration=[
            "Welcome to Absolute ADAS.",
            "This training walks you through filing and paying our quarterly excise tax return with the Washington State Department of Revenue, also called D O R.",
            "Keep the runbook open while you watch. It has every step as a checklist you can tick off.",
        ],
    ),
    dict(
        kicker="THE BASICS",
        title="What this return is",
        bullets=[
            "Washington has no state income tax",
            "Instead: B&O tax on our gross income",
            "Plus the retail sales tax we collected from customers",
            "One combined return, filed and paid online in My DOR",
        ],
        narration=[
            "Washington doesn't have a state income tax.",
            "Instead, businesses pay B and O tax, which stands for business and occupation, on gross income.",
            "We also send in the retail sales tax we collected from customers.",
            "All of it goes on one combined excise tax return, which we file and pay online in My D O R.",
            "Washington requires businesses to file and pay electronically, so paper returns aren't an option for us.",
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
            "If the due date lands on a weekend or holiday, it moves to the next business day.",
            "For example, the fourth quarter 2026 return is due Monday, February first, 2027, because January thirty-first is a Sunday.",
            "Don't cut it close, though. Our internal target is to have the return filed by the twentieth of the due month.",
        ],
    ),
    dict(
        kicker="BEFORE YOU START",
        title="Gather these first",
        bullets=[
            "Your own SecureAccess Washington (SAW) login, added by the owner",
            "Quarter's sales report from Zoho Books: invoiced totals by month",
            "Sales tax collected, broken out by job location",
            "Wholesale jobs: shop has a reseller permit on file",
            "Any jobs done outside Washington (e.g. Idaho) flagged",
        ],
        narration=[
            "Before you log in, gather what you need.",
            "First, your own SecureAccess Washington login. The owner adds you as a user on our account. Never share a login.",
            "Second, the sales report for the quarter from Zoho Books, with invoiced totals.",
            "Third, the sales tax we collected, broken out by the location where each job was done.",
            "Fourth, a list of shops we sold to at wholesale. They need a reseller permit on file with us.",
            "And finally, flag any jobs done outside Washington, like our Idaho work. Those are handled differently, so ask before entering them.",
        ],
    ),
    dict(
        kicker="STEP 1",
        title="Log in and open the return",
        bullets=[
            "Go to  secure.dor.wa.gov",
            "Sign in with SecureAccess Washington",
            "Select the Absolute ADAS account",
            "Click File return for the correct quarter",
        ],
        narration=[
            "Step one. Go to secure dot D O R dot W A dot gov and sign in with SecureAccess Washington.",
            "Select the Absolute ADAS account.",
            "Find the open return for the quarter you're filing and click File return.",
            "Double-check the period. Filing the wrong quarter is the most common mistake.",
        ],
    ),
    dict(
        kicker="STEP 2",
        title="Confirm the tax lines",
        bullets=[
            "Use the same lines as last quarter",
            "Typical: Retailing B&O + Retail sales tax",
            "Wholesaling B&O for shops with reseller permits",
            "Never add or remove a line without approval",
        ],
        narration=[
            "Step two. The return asks which tax lines apply.",
            "Use the same lines we filed last quarter. You can see them on the prior return in My D O R.",
            "Usually that's Retailing B and O plus retail sales tax, and Wholesaling B and O for sales to shops that gave us a reseller permit.",
            "Never add or remove a line on your own. If something looks different, stop and ask.",
        ],
    ),
    dict(
        kicker="STEP 3",
        title="Enter gross amounts & deductions",
        bullets=[
            "Enter total gross amount for each line",
            "Add deductions with a reason (e.g. interstate)",
            "My DOR calculates the tax automatically",
            "Small business B&O credit applies automatically",
        ],
        narration=[
            "Step three. For each line, enter the total gross amount for the quarter, straight from the Zoho Books report.",
            "If a deduction applies, such as work done out of state, enter it with the reason D O R asks for.",
            "My D O R calculates the tax for you, and applies the small business credit automatically if we qualify.",
        ],
    ),
    dict(
        kicker="STEP 4",
        title="Sales tax by location",
        bullets=[
            "Washington sales tax is destination-based",
            "Report by the location code where the work was done",
            "Find codes with DOR's Tax Rate Lookup tool",
            "Location totals must add up to the retail sales tax line",
        ],
        narration=[
            "Step four. Retail sales tax is reported by location.",
            "Washington is destination-based, so the rate depends on where the work was done, usually the shop's address, not our office.",
            "Each location has a four-digit location code. Look up any you don't recognize with D O R's Tax Rate Lookup tool.",
            "When you're done, the location totals must add up to the retail sales tax line.",
        ],
    ),
    dict(
        kicker="STEP 5",
        title="Review before you submit",
        bullets=[
            "Compare totals to the Zoho Books report",
            "Compare to last quarter: a big swing means stop and ask",
            "Use Save to come back later if needed",
            "Get owner sign-off before paying",
        ],
        narration=[
            "Step five. Review before you submit.",
            "Check that every total matches the Zoho Books report.",
            "Then compare against last quarter. If something swings a lot and you can't explain why, stop and ask.",
            "You can save the return and come back later. Nothing is filed until you submit.",
            "Get the owner's sign-off before you move on to payment.",
        ],
    ),
    dict(
        kicker="STEP 6",
        title="Pay by ACH Debit",
        bullets=[
            "Choose Bank Account (ACH Debit): no fee",
            "Pick a payment date on or before the due date",
            "Submit by 11:59 p.m. Pacific on the due date",
            "Don't pay by card: 2.96% processing fee",
        ],
        narration=[
            "Step six. Pay.",
            "Choose bank account, which is ACH debit. It's free, and it's how we always pay.",
            "Pick a payment date on or before the due date, and make sure the return is submitted by eleven fifty-nine p m Pacific on the due date.",
            "Don't use a credit or debit card. The processor charges a two point nine six percent fee.",
        ],
    ),
    dict(
        kicker="STEP 7",
        title="Save proof & close it out",
        bullets=[
            "Save the confirmation number",
            "Download the return PDF to the shared drive",
            "Folder: Taxes / WA DOR / YYYY-Qn",
            "Check the bank 1–2 business days after the payment date",
        ],
        narration=[
            "Step seven. Save your proof.",
            "Write down the confirmation number and download a PDF of the filed return.",
            "Save both to the shared drive, under Taxes, W A D O R, then the year and quarter.",
            "A day or two after the payment date, check the bank account to confirm the debit went through.",
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
            "No sales? Still file a no-business return",
        ],
        narration=[
            "Here's why the deadline matters.",
            "If the tax isn't paid by the due date, D O R adds a nine percent penalty.",
            "It jumps to nineteen percent after the end of the following month, and twenty-nine percent after the end of the second month, plus interest.",
            "Even in a quarter with no sales, we still have to file a no-business return.",
            "If there's ever a problem paying, file on time anyway and tell the owner right away.",
        ],
    ),
    dict(
        kicker="HEADS UP",
        title="Coming January 1, 2027",
        bullets=[
            "Retailing B&O rate goes from 0.471% to 0.5%",
            "Affects the Q1 2027 return and later",
            "My DOR applies the new rate automatically",
            "Nothing to change by hand",
        ],
        narration=[
            "One heads-up.",
            "Starting January first, 2027, the Retailing B and O rate goes up from point four seven one percent to point five percent.",
            "That affects the first quarter 2027 return and later. My D O R applies the new rate automatically, so you don't change anything by hand.",
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
            "Gather  →  Log in  →  Confirm lines  →  Enter amounts",
            "Locations  →  Review  →  Pay ACH  →  Save proof",
            "Questions: ask the owner first",
            "DOR Taxpayer Services: 360-705-6705",
        ],
        narration=[
            "To recap: gather your numbers, log in, confirm the lines, enter the amounts, report sales tax by location, review, pay by ACH debit, and save your proof.",
            "If anything doesn't look right, ask the owner first.",
            "D O R's taxpayer services line is three six zero, seven zero five, six seven zero five.",
            "Thanks for watching, and welcome to the team.",
        ],
    ),
]
