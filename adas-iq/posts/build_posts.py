"""Builds posts.json for the 12-week ADAS IQ social series.

Edit the WEEKS list below, then run: python3 adas-iq/posts/build_posts.py
"""
import json
import os

URL = "https://adas-iq.com"
IG_CTA = "Book a 15-minute demo. Link in bio, or type adas-iq.com"
FB_CTA = f"Book a 15-minute demo: {URL}"
LI_CTA = f"Book a 15-minute demo: {URL}"
SIGN = "Built by Mark Fowler, owner of Absolute ADAS, where this stuff actually gets tested."

TAGS_LI = "#ADAS #ADAScalibration #CollisionRepair #AutoBody #ShopManagement"
TAGS_FB = "#ADAS #CollisionRepair #BodyShop"
TAGS_IG = ("#ADAS #ADAScalibration #collisionrepair #autobody #bodyshop "
           "#bodyshoplife #estimator #calibration #autoglass #shopowner")

WEEKS = [
    {
        "kicker": "WEEK 1 · WHY WE BUILT IT",
        "headline": "We built the software we couldn't buy.",
        "core": (
            "We built the software we couldn't buy.\n\n"
            "Absolute ADAS has done 50,000+ calibrations since 2018. Somewhere along the way, "
            "spreadsheets and sticky notes stopped working. Missed lines. Post-scans nobody billed. "
            "Supplements that died in an inbox.\n\n"
            "So we built ADAS IQ to run our own shop. Now we license it to other shops doing "
            "serious calibration volume."
        ),
        "li_extra": (
            "It wasn't built in a lab. Every feature exists because a real job on a real floor "
            "went sideways without it."
        ),
    },
    {
        "kicker": "WEEK 2 · THE MISSED LINE",
        "headline": "The calibration you don't write is the one you don't get paid for.",
        "core": (
            "The calibration you don't write is the one you don't get paid for.\n\n"
            "Windshield. Bumper cover. Mirror. Alignment. Each one can trigger a calibration, and "
            "every make has its own rules.\n\n"
            "ADAS IQ shows you which vehicles need which calibrations, before the estimate goes out."
        ),
        "li_extra": (
            "Estimators shouldn't have to memorize every OEM position statement. The software "
            "should catch it."
        ),
    },
    {
        "kicker": "WEEK 3 · POST-SCANS",
        "headline": "You did the post-scan. Did you bill it?",
        "core": (
            "You did the post-scan. Did you bill it?\n\n"
            "In a lot of shops, the scan happens and the line never makes it onto the invoice. "
            "Same scan. No pay.\n\n"
            "ADAS IQ tags your post-scans automatically, so the work you did shows up as work "
            "you get paid for."
        ),
        "li_extra": "Ask your team: how many post-scans last month never made it onto an invoice?",
    },
    {
        "kicker": "WEEK 4 · SUPPLEMENTS",
        "headline": "A supplement isn't money until it's paid.",
        "core": (
            "A supplement isn't money until it's paid.\n\n"
            "Sent isn't paid. Approved isn't paid. Paid is paid.\n\n"
            "ADAS IQ tracks every supplement until the money lands, so nothing quietly dies "
            "in somebody's inbox."
        ),
        "li_extra": (
            "Supplements often get lost after they're sent, not before. That's where the "
            "tracking matters."
        ),
    },
    {
        "kicker": "WEEK 5 · DENIALS",
        "headline": "\"Included in standard labor.\" No, it isn't.",
        "core": (
            "\"Included in standard labor.\" No, it isn't.\n\n"
            "When a carrier denies a calibration, scan or R&R line, your answer is the OEM "
            "procedure and your documentation. Nothing else holds up.\n\n"
            "ADAS IQ builds documentation that holds up, and it powers our free rebuttal tool."
        ),
        "li_extra": (
            "Try the free OEM-cited rebuttal generator first: https://absoluteadas.com/audit "
            "It runs on ADAS IQ."
        ),
    },
    {
        "kicker": "WEEK 6 · OEM REQUIREMENTS",
        "headline": "Position statements change. Your binder doesn't.",
        "core": (
            "Position statements change. Your binder doesn't.\n\n"
            "OEMs update their calibration requirements all the time. A printout from last year "
            "is a liability this year.\n\n"
            "ADAS IQ keeps your team on current OEM calibration specs."
        ),
        "li_extra": "If your team is working from a printout, ask when it was last updated.",
    },
    {
        "kicker": "WEEK 7 · PRICING",
        "headline": "Guessing at calibration pricing costs you both ways.",
        "core": (
            "Guessing at calibration pricing costs you both ways.\n\n"
            "Price too low and you eat the bay time. Price too high and the line gets cut.\n\n"
            "ADAS IQ shows you what each vehicle needs and how to price it, so every line is "
            "one you can defend."
        ),
        "li_extra": (
            "Want to see what your shop is leaving on the table? Try the free calculator: "
            "https://absoluteadas.com/calculator It runs on ADAS IQ."
        ),
    },
    {
        "kicker": "WEEK 8 · BEFORE THE CAR ARRIVES",
        "headline": "Know the job before the customer walks in.",
        "core": (
            "Know the job before the customer walks in.\n\n"
            "Which systems. Which procedure. What usually goes wrong.\n\n"
            "ADAS IQ gives your techs real-time calibration specs and failure logic, so the "
            "first attempt is the one that passes."
        ),
        "li_extra": "Fewer comebacks start with the tech knowing the job before it's on the lift.",
    },
    {
        "kicker": "WEEK 9 · ALTERNATIVE PARTS",
        "headline": "The part fits. Will the sensor?",
        "core": (
            "The part fits. Will the sensor?\n\n"
            "Alternative bumper covers, brackets and glass can throw off ADAS sensors even when "
            "everything bolts up fine.\n\n"
            "ADAS IQ flags alternative-parts compatibility, so you find out at estimate, not at "
            "the post-scan."
        ),
        "li_extra": "With margins tight, the cheapest part isn't cheap if the calibration fails.",
    },
    {
        "kicker": "WEEK 10 · LIABILITY",
        "headline": "If it isn't documented, it didn't happen.",
        "core": (
            "If it isn't documented, it didn't happen.\n\n"
            "When an uncalibrated sensor fails after a repair, liability usually lands on the "
            "shop that did the work.\n\n"
            "ADAS IQ keeps the scans, the procedure and the proof together on every job."
        ),
        "li_extra": "You're not just passing a diagnostic. You're proving the car is safe to drive.",
    },
    {
        "kicker": "WEEK 11 · VOLUME",
        "headline": "What works at 10 cars a month breaks at 50.",
        "core": (
            "What works at 10 cars a month breaks at 50.\n\n"
            "More techs, more vans, more estimators. The whiteboard can't keep up.\n\n"
            "ADAS IQ was built for shops doing serious calibration volume, because ours is one."
        ),
        "li_extra": "If you're growing your calibration volume, your process has to grow with it.",
    },
    {
        "kicker": "WEEK 12 · SEE IT",
        "headline": "15 minutes. Your jobs. Our software.",
        "core": (
            "15 minutes. Your jobs. Our software.\n\n"
            "Missed calibrations. Unbilled post-scans. Supplements that never got paid. "
            "Documentation that doesn't hold up.\n\n"
            "That's what ADAS IQ fixes. Bring a few of your recent ROs to the demo and we'll "
            "walk through them."
        ),
        "li_extra": "Built on 50,000+ calibrations. Licensed to shops that take ADAS seriously.",
    },
]


def build():
    posts = []
    for i, w in enumerate(WEEKS, 1):
        posts.append({
            "week": i,
            "kicker": w["kicker"],
            "headline": w["headline"],
            "linkedin": f"{w['core']}\n\n{w['li_extra']}\n\n{LI_CTA}\n\n{SIGN}\n\n{TAGS_LI}",
            "facebook": f"{w['core']}\n\n{FB_CTA}\n\n{TAGS_FB}",
            "ig": f"{w['core']}\n\n{IG_CTA}\n.\n.\n{TAGS_IG}",
            "cta_url": URL,
            "image_url": "",
        })
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "posts.json")
    with open(out, "w") as f:
        json.dump(posts, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {len(posts)} posts to {out}")

    md = ["# ADAS IQ weekly posts\n",
          "Generated from build_posts.py. Edit that file, not this one.\n"]
    for p in posts:
        md.append(f"\n## Week {p['week']}: {p['headline']}\n")
        for label, key in (("LinkedIn", "linkedin"), ("Facebook", "facebook"), ("Instagram", "ig")):
            md.append(f"\n**{label}**\n\n```\n{p[key]}\n```\n")
    md_out = os.path.join(os.path.dirname(out), "POSTS.md")
    with open(md_out, "w") as f:
        f.write("".join(md))
    print(f"wrote {md_out}")


if __name__ == "__main__":
    build()
