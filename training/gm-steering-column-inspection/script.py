"""Slide text + narration: GM steering column inspection after a collision.

Original Absolute ADAS training on the procedure demonstrated by Broccolo Automotive in
"2020 GMC Steering column inspection" (YouTube, 5mru7GW8zZ0). Example values are from that
walkthrough of one 2020 GMC Sierra; they are examples only. Always use OEM service info.
"""

FOOTER = "Absolute ADAS  ·  Internal training  ·  Always follow current OEM service information for the VIN"

# Narration is written the way the voice should say it; captions show the normal spelling.
CAPTION_FIXES = [
    ("R P O", "RPO"), ("N thirty-three", "N33"), ("N thirty-seven", "N37"),
    ("O E M", "OEM"), ("ALL DATA", "ALLDATA"), ("G M", "GM"),
    ("five hundred six millimeters", "506 mm"), ("five hundred thirty millimeters", "530 mm"),
    ("fifty-eight millimeters", "58 mm"), ("four millimeters", "4 mm"),
    ("twenty-four millimeters", "24 mm"), ("Control F", "Ctrl+F"),
]

SLIDES = [
    dict(
        kicker="TECHNICIAN TRAINING",
        title="Steering column inspection\nafter a collision",
        bullets=["Worked example: 2020 GMC Sierra", "About 6 minutes  ·  follow along with the runbook"],
        narration=[
            "Welcome to Absolute ADAS technician training.",
            "This one covers the steering column inspection that General Motors requires after a collision, using a 2020 G M C Sierra as the example.",
            "The numbers you'll see are examples from one truck. The method is what matters: look up the procedure for the exact vehicle in front of you.",
        ],
    ),
    dict(
        kicker="WHY IT MATTERS",
        title="The manufacturer decides what gets inspected",
        bullets=[
            "OEMs publish required inspections after a collision",
            "Some are general, some are black and white",
            "A steering column can be damaged with no visible sign",
            "If it's required and skipped, the repair isn't complete",
        ],
        narration=[
            "After a collision, the vehicle has to go back to factory spec. The manufacturer publishes exactly which parts must be inspected or replaced.",
            "Some of that guidance is loosely worded. Some of it is black and white.",
            "A steering column is designed to collapse in a crash. It can be damaged with nothing visible from the driver's seat.",
            "So if the inspection is required and nobody does it, the repair isn't complete, even if the truck drives fine.",
        ],
    ),
    dict(
        kicker="THE BIG PICTURE",
        title="Two things decide what's required",
        bullets=[
            "1.  How severe was the collision?",
            "     Cosmetic only  ·  beyond cosmetic, no airbags  ·  airbags deployed",
            "2.  How was this exact vehicle built?",
            "     VIN and RPO option codes pick the right procedure and specs",
        ],
        narration=[
            "Two things decide what's required.",
            "First, how severe was the collision? Cosmetic damage only, damage beyond cosmetic without airbag deployment, or airbag deployment.",
            "Second, how was this exact vehicle built? The VIN and the R P O option codes tell you which procedure and which specifications apply.",
        ],
    ),
    dict(
        kicker="STEP 1",
        title="Look it up by VIN",
        bullets=[
            "Enter the VIN in ALLDATA (or GM service information)",
            "Body and Frame",
            "→  Repairs and Inspections Required After a Collision",
            "If ALLDATA is missing something, check GM service info",
        ],
        narration=[
            "Step one. Look it up by VIN.",
            "Enter the VIN in ALL DATA, or in G M service information.",
            "Go to Body and Frame, then Repairs and Inspections Required After a Collision.",
            "ALL DATA pulls from G M, but it sometimes has gaps. If something you expect isn't there, check G M service information directly.",
        ],
    ),
    dict(
        kicker="STEP 2",
        title="Match the damage to the chart",
        bullets=[
            "Find the column that matches the collision severity",
            "\"Exceeds minor outer body panel cosmetic distortion\" = more than dents and scratches: bent brackets, rails, supports",
            "The chart lists what to inspect or replace: steering wheel airbag, steering wheel, steering column, impact sensors and more",
            "\"Inspect steering column\" points to the column damage inspection procedure",
        ],
        narration=[
            "Step two. Match the damage to the chart.",
            "The page is laid out like a checklist, with a column for each level of severity.",
            "The middle level is damage that exceeds minor outer body panel cosmetic distortion, without airbag deployment. Think more than dents and scratches: a bent bracket, frame rail, or support.",
            "At that level the list is already long. It includes the steering wheel airbag, the steering wheel, the steering column, and the impact sensors.",
            "Where it says inspect the steering column, it sends you to the steering column accident damage inspection procedure. That's the one we're doing here.",
        ],
    ),
    dict(
        kicker="STEP 3",
        title="Find the RPO codes",
        bullets=[
            "The procedure asks: floor console or not? RPO N33 or N37?",
            "RPO = three-character factory option code",
            "Pull the build sheet by VIN (e.g. repairlinkshop.com)",
            "Ctrl+F for N33, then N37",
            "Example truck: no floor console, N37 (tilt and telescoping column)",
        ],
        narration=[
            "Step three. Find the R P O codes.",
            "The procedure asks two questions: does the truck have a front floor console, and does it have R P O code N thirty-three or N thirty-seven?",
            "R P O codes are three-character factory option codes. They tell you which steering column was installed.",
            "Pull the build sheet by VIN. One free option is repair link shop dot com. Then press Control F and search for each code.",
            "Our example truck has no floor console, and it has N thirty-seven, a tilt and telescoping column.",
        ],
    ),
    dict(
        kicker="WHY THE CODE MATTERS",
        title="Different column, different spec",
        bullets=[
            "Example, same model truck, overall length minimum:",
            "N37 column:  506 mm",
            "N33 column:  530 mm",
            "24 mm apart: pick the wrong code and a damaged column can pass",
        ],
        narration=[
            "Here's why the code matters.",
            "In this example, the minimum overall length for the N thirty-seven column is five hundred six millimeters.",
            "For the N thirty-three column, it's five hundred thirty millimeters.",
            "That's twenty-four millimeters apart. Pick the wrong code, and a damaged column can pass, or a good one can fail.",
        ],
    ),
    dict(
        kicker="STEP 4",
        title="Remove and strip the column",
        bullets=[
            "Follow the OEM removal procedure, including airbag safety steps",
            "Strip it down to the bare column",
            "That's the only way to measure end to end accurately",
            "Set it fully telescoped in (collapsed) before measuring",
        ],
        narration=[
            "Step four. Remove the column.",
            "Follow the manufacturer's removal procedure, including the airbag safety steps.",
            "The column has to come out and be stripped down to the bare column. That's the only way to get an accurate end to end measurement.",
            "Before you measure, set the column fully telescoped in, which means fully collapsed.",
        ],
    ),
    dict(
        kicker="STEP 5",
        title="Measure it",
        image="column_measurements.png",
        narration=[
            "Step five. Measure.",
            "There are three checks. Use the manufacturer's illustration for the exact points.",
            "One: the upper shaft end, where the steering wheel bolts on. In our example it must not be less than fifty-eight millimeters.",
            "Two: the overall length, end to end. For our example truck it must not be less than five hundred six millimeters.",
            "Three: with the tilt lever unlocked, move the column in the radial and axial directions. In our example, the movement must not be more than four millimeters.",
            "Measure in millimeters, with a tram gauge or a digital tape, and write each number down.",
        ],
    ),
    dict(
        kicker="STEP 6",
        title="Pass or fail",
        bullets=[
            "Any measurement out of spec = the column is damaged",
            "Discard it and install a new column. No repairs, no reuse",
            "All in spec = reinstall per the OEM procedure",
            "Unsure where to measure or how to read the spec? Stop and ask",
        ],
        narration=[
            "Step six. Pass or fail.",
            "If any measurement is out of spec, the column is damaged. Discard it and install a new one. It doesn't get repaired or reused.",
            "If everything is in spec, reinstall the column following the manufacturer's procedure.",
            "If you're not sure where to measure or how to read the spec, stop and ask before you decide.",
        ],
    ),
    dict(
        kicker="STEP 7",
        title="Document it",
        bullets=[
            "Save the OEM procedure pages for this VIN",
            "Save the build sheet showing the RPO code",
            "Photo of each measurement with the tape visible",
            "Record the numbers and pass/fail in the job file",
            "Keep with the pre-scan and post-scan reports",
        ],
        narration=[
            "Step seven. Document it.",
            "Save the procedure pages for this VIN, and the build sheet showing the R P O code.",
            "Take a photo of each measurement with the tape visible, and record the numbers and the result in the job file.",
            "Keep it with the pre-scan and post-scan reports. That's the proof the inspection was required and was done.",
        ],
    ),
    dict(
        kicker="RECAP",
        title="The method works on any vehicle",
        bullets=[
            "VIN  →  Repairs and Inspections Required After a Collision",
            "Match the severity  →  find the RPO code",
            "Remove, strip, collapse  →  measure three ways",
            "Out of spec: replace.  In spec: reinstall.  Document either way",
            "Never reuse numbers from another vehicle or from this video",
        ],
        narration=[
            "To recap. Look up the VIN and open Repairs and Inspections Required After a Collision.",
            "Match the severity, then find the R P O code so you're on the right procedure.",
            "Remove, strip, and collapse the column. Take the three measurements.",
            "Out of spec, replace it. In spec, reinstall it. Document it either way.",
            "And never reuse numbers from another vehicle, or from this video. Always pull the spec for the VIN you're working on.",
        ],
    ),
]
