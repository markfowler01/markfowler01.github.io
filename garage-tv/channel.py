"""Which YouTube channel a run is for (the CHANNEL environment variable). Each channel keeps its own
log of videos, its own pictures and its own look; the same engine makes both.

  parkedfm  PARKED FM (the default): the illustrated Night Studio, Kyleighanne and Wyatt at the desk,
            the brief's search titles and clean thumbnails, 3 hours, the three music packages
  ceo       CEO Focus (Mark, Nov 2): the sister channel that keeps the Oct 30 Deep Work look, a
            realistic Night Studio photo, one glowing word on the thumbnail, "Deep Work Music"
            titles, 2 hours, deep focus and lo-fi beats
"""
import os

CHANNELS = {
    "parkedfm": dict(name="PARKED FM", brand="PARKED FM", slug="parked-fm", hashtag="parkedfm",
                     log="published.json", stills="stills", tag="daily", look="illustrated",
                     title_styles=["seo"], thumb_styles=["clean"], music=["grinder", "deep_work", "chill_trader"],
                     minutes=180, characters=True, brief=True),
    "ceo": dict(name="CEO Focus", brand="CEO FOCUS", slug="ceo-focus", hashtag="ceofocus",
                log="published-ceo.json", stills="stills-ceo", tag="ceo", look="photo_polished",
                title_styles=["deep_work"], thumb_styles=["word"], music=["deep_focus", "lofi_beats"],
                minutes=120, characters=False, brief=False),
}
CHANNEL = os.environ.get("CHANNEL") or "parkedfm"
C = CHANNELS[CHANNEL]
