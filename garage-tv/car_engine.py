#!/usr/bin/env python3
"""Car engine: pick a random exotic car and a moody scene, have
Google's Nano Banana (GEMINI_API_KEY) or OpenAI's image model (OPENAI_API_KEY) paint it, and write the photo's settings
(title, description, tags, white-noise bed, rain, thumbnail text side) next to it.

  python3 car_engine.py --date 2026-10-12 --dry-run      # show the pick and the prompt
  GEMINI_API_KEY=... python3 car_engine.py --date 2026-10-12     # Nano Banana
  OPENAI_API_KEY=... python3 car_engine.py --date 2026-10-12     # ChatGPT images

Picks avoid repeating a car used in the last 20 videos or a scene used in the last 3
(read from published.json). Output: stills/<date>-<car>.webp + .json, marked rotate:false
so the old weekly rotation never reuses it; the daily queue picks it up as a fresh photo.
"""
import argparse
import base64
import datetime as dt
import io
import json
import os
import random
import re
import sys
import urllib.error
import urllib.request

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import learn  # noqa: E402  (make more of what viewers like)

HERE = os.path.dirname(os.path.abspath(__file__))

# Exotic cars only: supercars and hypercars, a different one every video.
CARS = [
    ("Ferrari 296 GTB", "Ferrari 296 GTB"), ("Ferrari SF90 Stradale", "Ferrari SF90"), ("Ferrari Roma", "Ferrari Roma"),
    ("Ferrari F8 Tributo", "Ferrari F8"), ("Ferrari 812 Superfast", "Ferrari 812"), ("Ferrari 12Cilindri", "Ferrari 12Cilindri"),
    ("Lamborghini Huracan STO", "Huracan STO"), ("Lamborghini Revuelto", "Lamborghini Revuelto"),
    ("Lamborghini Aventador SVJ", "Aventador SVJ"), ("Lamborghini Countach LPI 800-4", "Countach"),
    ("McLaren 750S", "McLaren 750S"), ("McLaren 720S", "McLaren 720S"), ("McLaren Artura", "McLaren Artura"),
    ("McLaren P1", "McLaren P1"), ("McLaren Senna", "McLaren Senna"),
    ("Porsche 911 GT3 RS", "911 GT3 RS"), ("Porsche 911 Turbo S", "911 Turbo S"), ("Porsche 918 Spyder", "918 Spyder"),
    ("Porsche Carrera GT", "Carrera GT"), ("Aston Martin Vantage", "Aston Martin Vantage"),
    ("Aston Martin DBS", "Aston Martin DBS"), ("Aston Martin Valkyrie", "Aston Martin Valkyrie"),
    ("Bugatti Chiron", "Bugatti Chiron"), ("Pagani Huayra", "Pagani Huayra"), ("Koenigsegg Jesko", "Koenigsegg Jesko"),
    ("Ford GT", "Ford GT"), ("Lexus LFA", "Lexus LFA"), ("Audi R8 V10", "Audi R8"),
    ("Mercedes-AMG GT Black Series", "AMG GT Black Series"), ("Mercedes-AMG One", "AMG One"),
    ("Maserati MC20", "Maserati MC20"), ("Rimac Nevera", "Rimac Nevera"), ("Nissan GT-R Nismo", "GT-R Nismo"),
    ("Acura NSX Type S", "NSX Type S"), ("Chevrolet Corvette ZR1", "Corvette ZR1"), ("Lotus Evija", "Lotus Evija"),
]
COLORS = ["rosso red", "gloss black", "chalk grey", "pearl white", "midnight blue", "british racing green",
          "papaya orange", "liquid silver", "satin black", "giallo yellow", "gunmetal grey", "deep burgundy"]

# The three PARKED FM series: how long the video runs, the title words.
SERIES = {
    "midnight_garage": dict(name="Midnight Garage", minutes=180, tail="Late-Night Lo-Fi for Work & Focus"),
    "rainy_drives": dict(name="Rainy Nights", minutes=480, tail="Rainy Night Lo-Fi for Sleep, Work & Focus"),
    "parked_peaceful": dict(name="Parked & Peaceful", minutes=240, tail="Calm Lo-Fi for Relaxing & Focus"),
}

# Music days pick one of the three styles of our own music creator (make_lofi_real.py), new
# songs every video: name for titles and thumbnails, title words, description words.
MUSIC_STYLES = {
    "lofi": dict(name="Chill Lo-Fi", words="slow, warm lo-fi hip hop on Rhodes, soft drums and round bass"),
    "garage": dict(name="Future Garage", tail="Chill Future Garage for Work & Focus",
                   words="mellow future garage and chillstep: airy pads, deep bass, a soft half-time beat"),
    "house": dict(name="Lo-Fi House", tail="Lo-Fi House for Work & Focus",
                  words="gentle lo-fi house: warm Rhodes chords over a soft four-on-the-floor"),
    # made with Google's Lyria (make_lyria_album.py); the two most popular focus sounds, Mark's pick
    "deep_focus": dict(name="Deep Focus", tail="Deep Focus Music for Work", lyria=True,
                       words="calm ambient electronic: warm synth pads, a soft deep bass and a gentle beat"),
    "lofi_beats": dict(name="Lo-Fi Beats", tail="Lo-Fi Beats for Work & Focus", lyria=True,
                       words="mellow lo-fi hip hop: jazzy keys and a soft head-nod beat"),
}
MUSIC_ORDER = ["deep_focus", "lofi_beats"]  # music styles in use (lofi, garage, house: our own creator)
# dials the learning tunes for Lyria albums: the main instrument and the tempo
MUSIC_LEADS = ["felt piano", "electric piano", "soft guitar", "warm synth pluck"]
MUSIC_TEMPOS = ["slow", "upbeat"]
# Deep Work: one word sets the mood of each video (thumbnail and title); not repeated within 10 videos,
# and learned (Mark's picks, Oct 30)
DEEP_WORDS = [
    # car + focus
    "Launch Mode", "Overdrive", "Cruise Control", "Full Throttle", "Redline", "Apex", "Night Run", "Track Mode",
    "Green Light", "Pole Position", "Torque", "Top Gear",
    # grind and ambition
    "CEO Mode", "Boss Mode", "Discipline", "No Days Off", "Built Different", "Silent Grind", "Grind Season",
    "Empire", "Legacy", "Execute", "Unstoppable", "Mindset",
    # calm focus
    "Locked In", "Deep Work", "Hyperfocus", "Flow State", "Laser Focus", "Dark Mode", "In The Zone", "Clarity",
    "Calm Mind", "Night Shift", "2AM Drive", "One More Hour",
    # discipline (Mark kept "Stay Hard"; never put a real person's name in titles or descriptions)
    "No Excuses", "Own It", "Earn It", "Do The Work", "Stay Ready", "Win The Morning", "No Shortcuts",
    "Embrace The Grind", "Wake Up Early", "Zero Excuses", "Prove It", "Stay Hard",
]
# The opening statement, big on screen for the first seconds of the video and its Shorts (statement.py).
# PARKED FM's own lines in a no-excuses voice, plus three old sayings Mark asked for ("Discipline equals
# freedom", "Stay hungry", "Embrace the suck"); never a real person's name. Learned like the word.
STATEMENTS = [
    "Nobody is coming to do it for you.",
    "The work doesn't care how you feel. Start anyway.",
    "Comfort is the enemy of progress.",
    "Your future is built in the hours nobody sees.",
    "Stay quiet. Work hard. Let the results talk.",
    "Motivation fades. Habits drive.",
    "Lock in. The world can wait.",
    "Two hours. One task. No excuses.",
    "Do the hard thing first.",
    "Show up. Do the work. Repeat.",
    "Earn the car. Earn the view.",
    "The grind is quiet. The results are loud.",
    "Discipline equals freedom.",
    "Stay hungry.",
    "Embrace the suck.",
    "Show up tonight. That's the whole plan.",
    "One focused hour beats a perfect plan.",
    "Small work, done daily, gets loud over time.",
    "Don't wait for motivation. Build the routine.",
    "Make starting easy. The rest follows.",
    "Today counts, even if it's small.",
    "Same desk. Same time. Better results.",
    "The streak is the reward.",
    "Goals are wishes. Routines are results.",
    "Every session is a vote for who you're becoming.",
    "The hardest part is sitting down. You're here.",
    "Start before you feel ready.",
    "Open the laptop. That's step one.",
    "Ten minutes in, you'll forget you didn't want to.",
    "Don't plan the whole night. Plan the next hour.",
    "Motivation shows up after you start.",
    "Begin badly. Fix it later.",
    "The first five minutes are the toll. Pay it.",
    "Nobody sees this part. That's why it counts.",
    "Quiet work. Loud results.",
    "Same time tomorrow.",
    "Show up tired. Show up anyway.",
    "Consistency beats intensity.",
    "One more session. Then another.",
    "Don't break the chain tonight.",
    "Average effort, every day, beats genius once a month.",
    "You don't need a good day. You need a done day.",
    "Small steps. Every night.",
    "One page. One rep. One task.",
    "Little by little becomes a lot.",
    "Stack small wins.",
    "Progress you can't see is still progress.",
    "A small thing done beats a big thing planned.",
    "Inch by inch, it adds up.",
    "Phone down. Mind on.",
    "One tab. One task. One hour.",
    "Close everything but this.",
    "Deep work is a quiet flex.",
    "Distraction is easy. Focus is rare. Be rare.",
    "The world can wait two hours.",
    "Locked in. Lights low. Let's work.",
    "Silence the noise. Do the work.",
    "Become the person who finishes.",
    "Every session builds who you are.",
    "You're not behind. You're building.",
    "Prove it to yourself first.",
    "Earn your own respect tonight.",
    "Your future self is watching this hour.",
    "Be someone your goals can count on.",
    "Discipline is a promise you keep to yourself.",
    "Do it when no one is checking.",
    "Feelings are optional. Effort isn't.",
    "Comfort can wait. The work can't.",
    "Hard now. Easy later.",
    "Do the boring part. That's the secret.",
    "Excuses don't build anything.",
    "The city sleeps. You build.",
    "2AM. Engine off. Mind on.",
    "Park the distractions.",
    "Built in the quiet hours.",
    "Late nights. Clear goals.",
    "Keep your foot on the gas.",
    "No shortcuts. Just miles.",
    "Slow is smooth. Smooth is fast.",
    "Warm up the engine. Then go.",
    "Every great machine was built one bolt at a time.",
    "Night shift for your future.",
    "Lights off outside. Lights on inside.",
    "Drive the work. Don't let it drive you.",
    "The garage is quiet. Your goals aren't.",
]
# How the title is put together (weekly.title_for); never the same style two days running
TITLE_STYLES = ["scene_first", "hours_first", "use_first", "deep_work"]
# Rooms, title styles and thumbnails in use: the Deep Work look since Oct 30 (the Night Studio, a
# "Deep Work Music – Locked In" title, one glowing word on the thumbnail). Add names back to bring
# the other rooms and styles back into the rotation.
ACTIVE_ROOMS = ["studio"]
ACTIVE_TITLE_STYLES = ["deep_work"]
ACTIVE_THUMB_STYLES = ["word"]
# Thumbnail layouts (weekly.make_thumbnail): the brand big, or what you'll hear big; learned like the rest
THUMB_STYLES = ["brand_first", "sound_first", "word"]

# Videos alternate: one day music only, the next day a soundscape only (no music), 8 hours
# for sleep. A soundscape day plays the scene's own sound or, now and then, plain brown or white noise.
SOUND_MINUTES = 480
SOUND_NAMES = {"rain_road": "Rain Sounds", "rain": "Rain Sounds", "wind": "Wind Sounds", "fan": "Fan Noise",
               "heater": "Heater Hum", "brown": "Brown Noise", "white": "White Noise"}
SOUND_WORDS = {"rain_road": "steady rain", "rain": "soft rain on the roof", "wind": "soft wind",
               "fan": "a steady fan", "heater": "a low heater hum", "brown": "deep brown noise",
               "white": "smooth white noise"}

# The PARKED FM rooms: a few signature places the channel keeps coming back to, so it feels like
# somewhere you know rather than random pictures. The car changes every video; so do the weather
# and the time of day outside each room's big window.
ROOMS = {
    "loft": dict(name="the Loft", floor="polished concrete floor", desc=(
        "a cozy, warm loft garage with exposed red-brick walls, a black steel-framed floor-to-ceiling window wall, "
        "warm amber Edison-bulb pendant lights, a wooden workbench with a steaming mug of coffee and a small glowing "
        "vintage radio, a worn brown leather armchair with a knit blanket, potted plants, and a polished concrete floor")),
    "cabin": dict(name="the Mountain Cabin Garage", floor="wide wooden plank floor", desc=(
        "a cozy timber mountain-cabin garage with honey-colored log walls, exposed wooden beams, a stone fireplace "
        "with a low fire, a huge picture window looking out over pine forest and mountains, a wooden workbench with a "
        "steaming mug of coffee and a small glowing vintage radio, a plaid wool blanket on a leather armchair, "
        "and a wide wooden plank floor")),
    "penthouse": dict(name="the Penthouse Garage", floor="dark polished stone floor", desc=(
        "a quiet luxury penthouse garage high above the city, floor-to-ceiling glass wall with the skyline far below, "
        "warm walnut wood panels, soft indirect lighting and a few brass floor lamps, a low leather lounge chair, a "
        "side table with a coffee cup and a small glowing vintage radio, a tall plant, and a dark polished stone floor")),
    # the Deep Work look (from Oct 30): a dark luxury private garage at night where the car is the
    # star, with a desk and glowing screens beside it; 2-hour videos people leave running while they work
    "studio": dict(name="the Night Studio", minutes=120, prompt="studio"),
    # out on the road: the car parked at a beautiful spot, no garage
    "outdoors": dict(name="Scenic Overlooks", outdoor=True),
    "seaside": dict(name="the Seaside Garage", floor="weathered wooden floor", desc=(
        "a calm seaside garage on the coast, whitewashed wooden walls, a wide glass wall looking out over the ocean "
        "and rocky shore, a surfboard leaning on the wall, warm lantern lights, a wooden workbench with a steaming mug "
        "of coffee and a small glowing vintage radio, a canvas armchair with a blanket, and a weathered wooden floor")),
}

SCENES = [
    dict(room="loft", id="loft_rain_night", series="midnight_garage", bed="rain", rain=0,
         title="in the Loft on a Rainy Night",
         view="outside the big window it is night and raining over the city skyline, rain streaks and droplets on the glass, city lights glowing softly through the wet window",
         words="rain running down the big window, coffee steaming on the bench and the city glowing below",
         motion="raindrops running down the window glass, steam curling up from the coffee mug, city lights twinkling softly"),
    dict(room="loft", id="loft_late_night", series="midnight_garage", bed="brown", rain=0,
         title="in the Loft Late at Night",
         view="outside the big window it is 2 am, a quiet city with scattered lit windows under a light drizzle, the room lit only by warm lamps and the radio's glow",
         words="the city asleep outside, a light drizzle on the glass and the radio glowing low",
         motion="a light drizzle on the window, the radio dial glowing gently, steam rising from the coffee"),
    dict(room="loft", id="loft_heavy_rain", series="rainy_drives", bed="rain", rain=0,
         title="in the Loft in Heavy Rain",
         view="outside the big window heavy rain pours over the city at night, sheets of water running down the glass, blurred lights beyond",
         words="water pouring down the windows while it stays warm and dry inside",
         motion="heavy rain streaming down the window glass, blurred city lights shimmering through the water, steam from the coffee"),
    dict(room="loft", id="loft_rain_dusk", series="rainy_drives", bed="rain", rain=0,
         title="in the Loft on a Rainy Evening",
         view="outside the big window it is blue-hour dusk in steady rain, the city lights just coming on, raindrops beading on the glass",
         words="the city lights coming on and raindrops beading on the glass",
         motion="raindrops sliding down the window, city lights flickering on one by one, steam from the coffee"),
    dict(room="loft", id="loft_autumn_rain", series="parked_peaceful", bed="rain", rain=0,
         title="in the Loft on a Rainy Autumn Afternoon",
         view="outside the big window it is a grey autumn afternoon with soft rain, orange and red trees along the street below, a few wet leaves stuck to the glass",
         words="red and orange trees outside and a warm lamp on",
         motion="soft rain running down the window, a leaf drifting past outside, steam from the coffee"),
    dict(room="loft", id="loft_snow", series="parked_peaceful", bed="heater", rain=0,
         title="in the Loft on a Snowy Evening",
         view="outside the big window snow is falling gently over the city rooftops at dusk, frost in the corners of the glass, a small wood stove glowing in the corner",
         words="snow on the rooftops, a wood stove glowing and the lamps on low",
         motion="snow drifting down outside the window, the wood stove's fire flickering, steam from the coffee"),
    dict(room="loft", id="loft_fog_morning", series="parked_peaceful", bed="white", rain=0,
         title="in the Loft on a Foggy Morning",
         view="outside the big window soft morning fog hides the city, only the nearest rooftops visible, pale cool light mixing with the warm lamps",
         words="the city hidden in mist and the first coffee of the day",
         motion="fog slowly drifting past the window, steam curling from the coffee, the lamps glowing softly"),
    dict(room="loft", id="loft_golden_rain", series="parked_peaceful", bed="rain", rain=0,
         title="in the Loft as the Rain Clears at Sunset",
         view="outside the big window the rain is clearing at sunset, golden light breaking through the clouds over the wet city, the last raindrops on the glass catching the light",
         words="golden light on the wet city and the last drops on the glass",
         motion="the last raindrops sliding down the glowing window, clouds drifting, steam from the coffee"),
    dict(room="cabin", id="cabin_snow_night", series="parked_peaceful", bed="heater", rain=0,
         title="in a Mountain Cabin Garage on a Snowy Night",
         view="outside the big window snow is falling softly over dark pine trees at night, the fireplace glowing warm inside",
         words="snow falling on the pines, the fire crackling low and the coffee still hot",
         motion="snow drifting down past the window, the fireplace flickering, steam rising from the coffee"),
    dict(room="cabin", id="cabin_forest_rain", series="rainy_drives", bed="rain", rain=0,
         title="in a Mountain Cabin Garage in the Rain",
         view="outside the big window steady rain falls on a deep green pine forest, mist between the trees, droplets on the glass",
         words="rain on the pines, mist in the trees and the fire keeping it warm",
         motion="rain running down the window, mist drifting between the pines, the fire flickering"),
    dict(room="cabin", id="cabin_misty_morning", series="parked_peaceful", bed="wind", rain=0,
         title="in a Mountain Cabin Garage on a Misty Morning",
         view="outside the big window morning mist rolls over the mountains and pine forest, soft pale light, the fire still glowing from the night",
         words="mist rolling over the mountains and the first light of the morning",
         motion="mist slowly rolling over the mountains, pine tops swaying gently, steam from the coffee"),
    dict(room="penthouse", id="penthouse_city_night", series="midnight_garage", bed="brown", rain=0,
         title="in a Penthouse Garage Above the City at Night",
         view="outside the glass wall the city glitters far below at night, streets of light and quiet towers, the room lit by warm lamps",
         words="the whole city glittering far below and the lamps turned low",
         motion="city lights twinkling far below, a plane's lights crossing slowly, steam from the coffee"),
    dict(room="penthouse", id="penthouse_rain", series="rainy_drives", bed="rain", rain=0,
         title="in a Penthouse Garage on a Rainy Night",
         view="outside the glass wall rain streaks across the glass high above a wet, glowing city at night, low clouds around the towers",
         words="rain streaking the glass high above a glowing city",
         motion="rain streaking across the glass, clouds drifting past the towers, city lights shimmering"),
    dict(room="penthouse", id="penthouse_sunrise", series="parked_peaceful", bed="white", rain=0,
         title="in a Penthouse Garage at Sunrise",
         view="outside the glass wall the sun is rising over the city, soft gold and pink light across the towers and the haze below",
         words="the sun coming up over the city and the first coffee of the day",
         motion="soft sunrise light slowly brightening, haze drifting over the city, steam from the coffee"),
    dict(room="studio", id="studio_city_night", series="midnight_garage", bed="brown", rain=0,
         title="in the Night Studio Above the City",
         view="outside the glass wall a city skyline glitters at night far below",
         words="the city glittering far below and the screens glowing low",
         motion="city lights twinkling beyond the glass, the screens' glow shifting softly, steam from the coffee"),
    dict(room="studio", id="studio_rain_night", series="midnight_garage", bed="rain", rain=0,
         title="in the Night Studio on a Rainy Night",
         view="rain streaks down the glass wall, the city lights beyond blurred into soft colour",
         words="rain streaking down the glass and the city lights blurred beyond",
         motion="raindrops running down the glass wall, blurred lights shimmering, the screens glowing"),
    dict(room="studio", id="studio_forest_night", series="midnight_garage", bed="wind", rain=0,
         title="in the Night Studio in the Forest",
         view="outside the glass wall a dark pine forest under moonlight, thin mist drifting between the trees",
         words="a moonlit pine forest outside and mist between the trees",
         motion="mist drifting between the pines, branches swaying slightly, the screens glowing"),
    dict(room="studio", id="studio_snow_night", series="midnight_garage", bed="heater", rain=0,
         title="in the Night Studio on a Snowy Night",
         view="outside the glass wall snow is falling softly over a quiet courtyard lit by low lamps",
         words="snow falling softly outside and the room warm and quiet",
         motion="snow drifting down beyond the glass, the lamps glowing, steam from the coffee"),
    dict(room="studio", id="studio_2am", series="midnight_garage", bed="brown", rain=0,
         title="in the Night Studio at 2 AM",
         view="outside the glass wall a quiet city at 2 am, only a few lit windows, a light drizzle on the glass",
         words="the city asleep at 2 am and only your screens still on",
         motion="a light drizzle on the glass, a few distant windows going dark, the screens glowing"),
    dict(room="studio", id="studio_before_dawn", series="midnight_garage", bed="white", rain=0,
         title="in the Night Studio Before Dawn",
         view="outside the glass wall the first deep-blue light of dawn rises over dark hills",
         words="the first blue light of dawn and a long night of work behind you",
         motion="the dawn light slowly brightening over the hills, the screens glowing, steam from the coffee"),
    dict(room="outdoors", id="out_cherry_blossom", series="parked_peaceful", bed="wind", rain=0,
         title="at a Cherry Blossom Overlook in Spring",
         view="parked on a gravel overlook under a blooming cherry tree, pink petals drifting in the air, rolling green hills and forest valleys stretching to the horizon under a soft blue sky with a few clouds",
         words="pink petals drifting down and green valleys rolling out to the horizon",
         motion="cherry blossom petals drifting down, branches swaying gently, clouds moving slowly over the valley"),
    dict(room="outdoors", id="out_autumn_valley", series="parked_peaceful", bed="wind", rain=0,
         title="at an Autumn Valley Overlook",
         view="parked on a quiet mountain overlook in autumn, a valley of orange, red and gold trees below, soft late-afternoon light and a winding road in the distance",
         words="a valley of red and gold trees and the late sun on the hills",
         motion="autumn leaves drifting past, trees swaying gently in the valley, soft light shifting over the hills"),
    dict(room="outdoors", id="out_alpine_lake", series="parked_peaceful", bed="wind", rain=0,
         title="by an Alpine Lake at Sunrise",
         view="parked on the shore of a calm alpine lake at sunrise, snow-capped mountains reflected in the still water, pine trees and a thin morning mist over the lake",
         words="snowy peaks reflected in a still lake and morning mist on the water",
         motion="mist drifting slowly over the lake, gentle ripples on the water, the sunrise light growing"),
    dict(room="outdoors", id="out_coast_sunset", series="parked_peaceful", bed="wind", rain=0,
         title="on a Coastal Cliff Road at Sunset",
         view="parked at a pull-out on a winding coastal cliff road at sunset, the ocean far below glowing orange, waves on the rocks and the road curving away along the coast",
         words="the ocean glowing below and the coast road curving away into the sunset",
         motion="waves rolling onto the rocks far below, the sun sinking slowly, clouds drifting"),
    dict(room="outdoors", id="out_forest_rain", series="rainy_drives", bed="rain_road", rain=700,
         title="on a Forest Road in the Rain",
         view="parked on the side of a wet two-lane road through a tall green forest in steady rain, the asphalt shining, mist between the trees and puddles reflecting the car",
         words="steady rain on the forest road and mist between the tall trees",
         motion="rain falling steadily, droplets splashing in the puddles, mist drifting between the trees"),
    dict(room="outdoors", id="out_city_night", series="midnight_garage", bed="brown", rain=0,
         title="at a City Overlook at Night",
         view="parked at a hilltop overlook at night, the whole city spread out below in glittering lights, a clear dark sky with a few stars",
         words="the city lights spread out below and a clear night sky",
         motion="city lights twinkling far below, a few cars' lights moving on the roads, stars shimmering"),
    dict(room="seaside", id="seaside_rain_evening", series="rainy_drives", bed="rain", rain=0,
         title="in a Seaside Garage on a Rainy Evening",
         view="outside the glass wall a grey ocean meets the rocky shore in soft evening rain, waves rolling in slowly, raindrops on the glass",
         words="rain on the glass and slow grey waves rolling in",
         motion="raindrops sliding down the glass, waves rolling slowly onto the rocks, the lanterns glowing"),
    dict(room="seaside", id="seaside_sunset", series="parked_peaceful", bed="wind", rain=0,
         title="in a Seaside Garage at Sunset",
         view="outside the glass wall the sun is setting over a calm ocean, warm orange light across the water and the rocks",
         words="the sun going down over the ocean and a soft sea breeze",
         motion="gentle waves catching the sunset light, clouds drifting slowly, steam from the coffee"),
    dict(room="seaside", id="seaside_night", series="midnight_garage", bed="wind", rain=0,
         title="in a Seaside Garage Late at Night",
         view="outside the glass wall the ocean is dark under a moonlit sky, a distant lighthouse beam and moonlight on the waves",
         words="moonlight on the water and a lighthouse turning in the distance",
         motion="moonlight shimmering on the waves, the lighthouse beam turning slowly, the lanterns glowing"),
]

ROOM_OF = {s["id"]: s["room"] for s in SCENES}

STUDIO_PROMPT = (
    "Photorealistic, dark and moody cinematic photograph, 16:9 framing, inside a luxury private garage studio at "
    "night: polished dark concrete floor, black walls with soft LED strip lights, a floor-to-ceiling glass wall; "
    "{view}. A {color} {car} is the star of the image, parked in the middle of the frame, three-quarter front view, "
    "large, sharp and beautifully lit by the soft strip lights and the glow of the screens, with crisp reflections on "
    "its paint and on the floor. Beside the car, a minimalist black desk with two glowing monitors showing calm "
    "abstract charts, a small desk lamp and a coffee cup: part of the scene, smaller than the car. Deep shadows, cool "
    "blue and teal tones with warm accent lights, rich detail, soft depth of field. The upper third of the image is "
    "dark and calm so a word can be written there. One single continuous photograph, not a collage, diptych or split "
    "frame. Full-bleed image filling the entire frame edge to edge: no black bars, no letterboxing, no borders. "
    "No people, no text, no readable writing on the screens, no logos, no watermarks, no license plate numbers."
)

OUTDOOR_PROMPT = (
    "Photorealistic, cinematic landscape photograph, 16:9 framing. A {color} {car} {view}. "
    "The whole car is in view, seen from a little distance, three-quarter view, filling about a third of the frame "
    "width in the left two-thirds, beautifully lit with gentle reflections on its paint; nothing of the car is cut off. The right third of the image is open sky and landscape, calm and uncluttered so text can go there. "
    "The feeling is peaceful and breathtaking, a place you would want to stop and stay a while. "
    "Rich detail, natural light, soft depth of field. "
    "One single continuous photograph, not a collage, diptych or split frame. "
    "Full-bleed image filling the entire frame edge to edge: no black bars, no letterboxing, no borders. "
    "No people, no text, no logos, no watermarks, no license plate numbers."
)

PROMPT = (
    "Photorealistic, warm and inviting cinematic interior photograph, 16:9 framing, inside {room}. "
    "A {color} {car} is parked inside on the {floor}, in the left two-thirds of the frame, "
    "three-quarter front view, softly lit by the warm lamps with gentle reflections on its paint. "
    "{view}. The big window takes up the right third of the image and stays calm and uncluttered so text can go there. "
    "The feeling is cozy and peaceful, a place you would want to sit with a coffee and listen to music, not dark or gloomy. "
    "Rich detail, soft depth of field, natural light falloff. "
    "One single continuous photograph, not a collage, diptych or split frame. "
    "Full-bleed image filling the entire frame edge to edge: no black bars, no letterboxing, no borders. "
    "No people, no text, no logos on the radio, no watermarks, no license plate numbers."
)


def prompt_for(scene, color, car):
    """The picture prompt: inside one of the rooms, or out at a scenic spot."""
    room, view = ROOMS[scene["room"]], scene["view"]
    if room.get("prompt") == "studio":
        return STUDIO_PROMPT.format(color=color, car=car, view=view)
    if room.get("outdoor"):
        return OUTDOOR_PROMPT.format(color=color, car=car, view=view)
    return PROMPT.format(room=room["desc"], floor=room["floor"], color=color, car=car,
                         view=view[0].upper() + view[1:])


def looks_split(path):
    """True if the picture came out as two photos side by side: some vertical line where, row after
    row, the colour jumps sharply from one side to the other. Only meaningful outdoors; indoors the
    window frames and wall edges look just like that."""
    import numpy as np
    g = np.asarray(Image.open(path).convert("RGB").resize((480, 270)), float)
    jumps = [np.median(np.abs(g[:, x - 10:x - 2].mean(axis=1) - g[:, x + 2:x + 10].mean(axis=1)).sum(axis=1))
             for x in range(96, 384)]
    return max(jumps) > 150  # good outdoor pictures score about 40-60, a split one about 280


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def pick(day, published):
    rng = random.Random(day.toordinal() * 7 + len(published))
    recent_cars = {e.get("car") for e in published[-20:]}
    recent_scenes = [e.get("scene") for e in published[-3:]]
    cars = [c for c in CARS if c[0] not in recent_cars] or CARS
    active = [s for s in SCENES if s["room"] in ACTIVE_ROOMS]
    scenes = [s for s in active if s["id"] not in recent_scenes] or active
    # each part of the video is picked with odds that follow how past videos did (learn.py);
    # music and soundscape days still alternate, and the picture makers stay a fair test
    history = learn.scored(published)
    make = learn.choose(rng, [learn.brand(c[0]) for c in cars], lambda e: learn.brand(e.get("car")), history)
    car, short = rng.choice([c for c in cars if learn.brand(c[0]) == make])
    # never the same room two days running, so the channel keeps moving around its places
    last_room = ROOM_OF.get(published[-1].get("scene")) if published else None
    rooms = [s["room"] for s in scenes if s["room"] != last_room] or [s["room"] for s in scenes]
    room = learn.choose(rng, rooms, lambda e: ROOM_OF.get(e.get("scene")), history)
    scene_id = learn.choose(rng, [s["id"] for s in scenes if s["room"] == room], lambda e: e.get("scene"), history)
    scene = next(s for s in scenes if s["id"] == scene_id)
    last = published[-1].get("recipe") if published else None
    soundscape = learn.choose(rng, [scene["bed"], "brown", "white"], lambda e: e.get("recipe"), history)
    sound = "lofi" if last != "lofi" else soundscape
    style = learn.choose(rng, MUSIC_ORDER, lambda e: e.get("music_style"), history)
    lead = learn.choose(rng, MUSIC_LEADS, lambda e: e.get("music_lead"), history)
    tempo = learn.choose(rng, MUSIC_TEMPOS, lambda e: e.get("music_tempo"), history)
    last_title = published[-1].get("title_style") if published else None
    title_style = learn.choose(rng, [t for t in ACTIVE_TITLE_STYLES if t != last_title] or ACTIVE_TITLE_STYLES,
                               lambda e: e.get("title_style"), history)
    thumb_style = learn.choose(rng, ACTIVE_THUMB_STYLES, lambda e: e.get("thumb_style"), history)
    recent_words = {e.get("word") for e in published[-10:]}
    # the word is learned like the rest: words that earn clicks come back more often
    word = learn.choose(rng, [w for w in DEEP_WORDS if w not in recent_words] or DEEP_WORDS,
                        lambda e: e.get("word"), history)
    recent_lines = {e.get("statement") for e in published[-6:]}
    line = learn.choose(rng, [x for x in STATEMENTS if x not in recent_lines] or STATEMENTS,
                        lambda e: e.get("statement"), history)
    return dict(car=car, short=short, color=rng.choice(COLORS), scene=scene, sound=sound, music_style=style,
                title_style=title_style, thumb_style=thumb_style, word=word, music_lead=lead, music_tempo=tempo,
                statement=line if ROOMS[scene["room"]].get("prompt") == "studio" else None)


def sidecar(choice):
    sc, short, sound = choice["scene"], choice["short"], choice.get("sound", "lofi")
    series = SERIES[sc["series"]]
    title = f"{short} {sc['title']}"
    where = sc["title"].lower()
    tag = slug(short).replace("-", "")
    meta = {
        "rotate": False,
        "recipes": [sound],
        "daily_sound": sound,
        "bed": sc["bed"],
        "rain": sc["rain"],
        "dust": 0 if sc["rain"] else 40,
        "grades": ["none"],
        "series": series["name"],
        "text_side": "right",
        "text_scale": 0.66,
        "title": title,
        "label": series["name"].upper(),
        "slug": slug(short),
        "car": choice["car"],
        "scene": sc["id"],
        "room": sc["room"],
        "title_style": choice.get("title_style", "scene_first"),
        "thumb_style": choice.get("thumb_style", "brand_first"),
        "word": choice.get("word"),
        "statement": choice.get("statement"),
    }
    room = ROOMS[sc["room"]]
    deep = room.get("prompt") == "studio"
    deep_tags = ["deep work music", "focus music", "music for work", "concentration music", "study music",
                 (choice.get("word") or "").lower()] if deep else []
    if sound == "lofi":
        minutes = room.get("minutes") or series["minutes"]
        hours = minutes // 60
        style = choice.get("music_style", "lofi")
        ms = MUSIC_STYLES[style]
        meta.update(
            minutes=minutes,
            music_style=style,
            music_lead=choice.get("music_lead"),
            music_tempo=choice.get("music_tempo"),
            sound_name=ms["name"],
            title_tail=ms.get("tail", series["tail"]),
            tags=deep_tags + [choice["car"].lower(), short.lower(), series["name"].lower(), ms["name"].lower(),
                              "exotic cars", "supercar", "lofi for work", "focus music"],
            description=(
                f"{series['name']}: a {choice['color']} {choice['car']} {where}, {sc['words']}. "
                f"{hours} hours of {ms['words']}, music only, for working, studying, "
                "relaxing or drifting off to sleep.\n\n"
                "No talking. No lyrics. No sudden sounds. "
                + ("Every track is original, made for PARKED FM.\n\n" if ms.get("lyria") else
                   "Every song is original, written and played for PARKED FM on real recorded instruments.\n\n")
                + "PARKED FM | Dream Cars. Easy Listening.\n\n"
                f"#parkedfm #{ms['name'].lower().replace(' ', '').replace('-', '')} #musicforwork #focusmusic #{tag}"
            ),
        )
    else:
        name = SOUND_NAMES[sound]
        hashtag = name.lower().replace(" ", "")
        minutes = room.get("minutes") or SOUND_MINUTES
        meta.update(
            minutes=minutes,
            title_tail=f"{name} for Sleep & Focus",
            sound_name=name,
            tags=deep_tags + [name.lower(), f"{name.lower()} for sleeping", "white noise", "sleep sounds", "no music",
                              choice["car"].lower(), short.lower(), "exotic cars", "supercar"],
            description=(
                f"{series['name']}: a {choice['color']} {choice['car']} {where}, {sc['words']}. "
                f"{minutes // 60} hours of {SOUND_WORDS[sound]}, no music, for sleeping, studying, "
                "or blocking out the world while you work.\n\n"
                "No music. No talking. No sudden sounds. Seamless from start to finish, so nothing wakes you up.\n\n"
                "PARKED FM | Dream Cars. Easy Listening.\n\n"
                + " ".join(dict.fromkeys(f"#{h}" for h in ("parkedfm", hashtag, "sleepsounds", "whitenoise", tag)))
            ),
        )
    return meta


def trim_bars(img, dark=14, spread=8):
    """Cut off black letterbox / pillarbox bars that image models sometimes add."""
    import numpy as np
    a = np.asarray(img.convert("L"), float)
    def flat_dark(lines):
        return (lines.mean(axis=1) < dark) & (lines.std(axis=1) < spread)
    rows, cols = flat_dark(a), flat_dark(a.T)
    top = int(np.argmin(rows)) if rows.any() else 0
    bottom = len(rows) - int(np.argmin(rows[::-1])) if rows.any() else len(rows)
    left = int(np.argmin(cols)) if cols.any() else 0
    right = len(cols) - int(np.argmin(cols[::-1])) if cols.any() else len(cols)
    if bottom - top < a.shape[0] * 0.5 or right - left < a.shape[1] * 0.5:
        return img  # a genuinely dark picture, not bars: leave it alone
    return img.crop((left, top, right, bottom))


# The three-way test: Nano Banana photo, ChatGPT photo, and Sora (a ChatGPT photo brought to life
# as a moving clip). Each needs its key; Sora uses the OpenAI key.
MAKERS = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY", "sora": "OPENAI_API_KEY"}
CLIPS = os.path.join(HERE, "out", "clips")


def pick_maker(published, sound):
    """Each maker gets the same number of music days and of soundscape days (so the sound can't
    skew the views); a tie goes to the next maker after the one that did the last video of that kind."""
    makers = [m for m, k in MAKERS.items() if os.environ.get(k)]
    if len(makers) < 2:
        return makers[0] if makers else "gemini"
    group = [e["maker"] for e in published if e.get("maker") in MAKERS and (e.get("recipe") == "lofi") == (sound == "lofi")]
    counts = {m: group.count(m) for m in makers}
    low = min(counts.values())
    tied = [m for m in makers if counts[m] == low]
    if group and group[-1] in makers:
        after = makers[makers.index(group[-1]) + 1:] + makers[:makers.index(group[-1]) + 1]
        return next(m for m in after if m in tied)
    return tied[0]


def generate(prompt, out_path, maker="gemini"):
    """Paint the picture with the chosen maker (Google's Nano Banana, GEMINI_API_KEY, or OpenAI's
    image model behind ChatGPT, OPENAI_API_KEY), falling back to the other one if it fails.
    Returns the maker that actually painted it."""
    painters = ["gemini", "openai"]
    order = [maker] + [m for m in painters if m != maker]
    order = [m for m in order if os.environ.get(MAKERS[m])] or ["openai"]
    for i, m in enumerate(order):
        try:
            (generate_gemini if m == "gemini" else generate_openai)(prompt, out_path)
            return m
        except RuntimeError as e:
            if i == len(order) - 1:
                raise
            print(f"{m} failed, trying {order[i + 1]}:", e, file=sys.stderr)


def generate_gemini(prompt, out_path):
    """Nano Banana Pro at 2K (about 2752x1536, sharp at 1080p after the zoom), falling back to the
    original Nano Banana (about 1344x768) if Pro is unavailable."""
    models = [os.environ["GEMINI_IMAGE_MODEL"]] if os.environ.get("GEMINI_IMAGE_MODEL") else \
        ["gemini-3-pro-image-preview", "gemini-2.5-flash-image"]
    for i, model in enumerate(models):
        try:
            return gemini_image(model, prompt, out_path)
        except RuntimeError as e:
            if i == len(models) - 1:
                raise
            print(f"{model} failed, trying {models[i + 1]}:", e, file=sys.stderr)


def gemini_image(model, prompt, out_path):
    key = os.environ["GEMINI_API_KEY"]
    image_config = {"aspectRatio": "16:9"}
    if "pro" in model:
        image_config["imageSize"] = "2K"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": image_config},
    }).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("x-goog-api-key", key)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gemini said {e.code}: {e.read()[:400]!r}")
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                img = trim_bars(Image.open(io.BytesIO(base64.b64decode(inline["data"]))).convert("RGB"))
                img.save(out_path, quality=92)
                return out_path
    raise RuntimeError(f"Gemini returned no image: {json.dumps(data)[:400]}")


def generate_openai(prompt, out_path):
    """OpenAI's image model (the one behind ChatGPT); save it as a 1536x1024 WebP."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    body = json.dumps({
        "model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        "prompt": prompt,
        "size": "1536x1024",
        "quality": os.environ.get("OPENAI_IMAGE_QUALITY", "high"),
        "n": 1,
    }).encode()
    req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenAI said {e.code}: {e.read()[:400]!r}")
    img = trim_bars(Image.open(io.BytesIO(base64.b64decode(data["data"][0]["b64_json"]))).convert("RGB"))
    img.save(out_path, quality=92)
    return out_path


WRITER_PROMPT = (
    "Write the opening paragraph of a YouTube description for a relaxing video. One paragraph, 3 or 4 sentences, "
    "50 to 90 words. Warm, simple and calm, like a person describing a place they love; talk to the viewer as 'you'. "
    "Paint this scene in a fresh way: the car, the room, what's outside the window, then what you hear and what the "
    "video is good for. No hashtags, no emojis, no links, no lists, no quotation marks, no made-up car facts or "
    "numbers, and don't mention AI.\n\nThe video: {facts}"
)


def write_intro(choice, meta):
    """A fresh opening paragraph for this video's description (Gemini text, then OpenAI), so no two
    descriptions read like a template. None if neither answers; the template one is used then."""
    sc, room = choice["scene"], ROOMS[choice["scene"]["room"]]
    hear = (MUSIC_STYLES[meta["music_style"]]["words"] + ", music only" if choice["sound"] == "lofi"
            else SOUND_WORDS[choice["sound"]] + ", no music")
    facts = (f"a {choice['color']} {choice['car']} parked {sc['title']} ({room['name']}). Outside: {sc['words']}. "
             f"You hear {hear}, for {meta['minutes'] // 60} hours. "
             f"Good for {'working, studying and relaxing' if choice['sound'] == 'lofi' else 'sleeping and focus'}.")
    prompt = WRITER_PROMPT.format(facts=facts)
    for name, fn in (("gemini", gemini_text), ("openai", openai_text)):
        if not os.environ.get(MAKERS[name]):
            continue
        try:
            text = " ".join(fn(prompt).replace("#", "").split())
        except (RuntimeError, OSError, KeyError, ValueError) as e:
            print(f"{name} couldn't write the description:", e, file=sys.stderr)
            continue
        if 120 <= len(text) <= 900 and "http" not in text:
            return text
    return None


def with_written_intro(choice, meta):
    """Swap the template's first paragraph for a freshly written one, when the writer answers."""
    text = write_intro(choice, meta)
    if text:
        meta["description"] = text + meta["description"][meta["description"].index("\n\n"):]
    return meta


def gemini_text(prompt):
    model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-latest")  # Google retires dated models
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                 data=body, method="POST")
    req.add_header("x-goog-api-key", os.environ["GEMINI_API_KEY"])
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gemini said {e.code}: {e.read()[:300]!r}")
    return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip()


def openai_text(prompt):
    body = json.dumps({"model": os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o-mini"),
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {os.environ['OPENAI_API_KEY']}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenAI said {e.code}: {e.read()[:300]!r}")
    return data["choices"][0]["message"]["content"].strip()


SORA_PROMPT = (
    "Bring this photo to life as a calm, cinematic ambient shot. Locked-off tripod camera: the camera does not "
    "move, pan, zoom or cut at all. The {color} {car} stays perfectly still, parked. "
    "Only gentle natural motion in the scene: {motion}. Slow, peaceful, relaxing. No people, no text, no new objects."
)


def scene_motion(scene):
    return scene.get("motion") or "soft light glowing, steam curling from the coffee, gentle movement outside the window"


def multipart(fields, files):
    """Encode a multipart/form-data body by hand (standard library only)."""
    boundary = "----parkedfm" + base64.b16encode(os.urandom(8)).decode()
    out = io.BytesIO()
    for k, v in fields.items():
        out.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, (name, data, ctype) in files.items():
        out.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\n'
                  f"Content-Type: {ctype}\r\n\r\n".encode())
        out.write(data)
        out.write(b"\r\n")
    out.write(f"--{boundary}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={boundary}"


def openai_call(url, data=None, ctype=None, method=None, raw=False, timeout=120):
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"))
    req.add_header("Authorization", f"Bearer {os.environ['OPENAI_API_KEY']}")
    if ctype:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read() if raw else json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenAI said {e.code}: {e.read()[:400]!r}")


def generate_sora(still_path, prompt, out_clip):
    """Animate the still with Sora (OpenAI Videos API): the photo is the first frame, 12 seconds."""
    import time
    model = os.environ.get("SORA_MODEL") or "sora-2"
    size = os.environ.get("SORA_SIZE") or ("1792x1024" if model == "sora-2-pro" else "1280x720")
    w, h = map(int, size.split("x"))
    img = Image.open(still_path).convert("RGB")
    s = max(w / img.width, h / img.height)  # cover the video frame, centre crop
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    img = img.crop(((img.width - w) // 2, (img.height - h) // 2, (img.width - w) // 2 + w, (img.height - h) // 2 + h))
    ref = io.BytesIO()
    img.save(ref, "JPEG", quality=95)
    body, ctype = multipart(dict(model=model, prompt=prompt, seconds=os.environ.get("SORA_SECONDS") or "12", size=size),
                            {"input_reference": ("first-frame.jpg", ref.getvalue(), "image/jpeg")})
    job = openai_call("https://api.openai.com/v1/videos", body, ctype)
    print("Sora job", job.get("id"), job.get("status"), file=sys.stderr)
    deadline = time.time() + 30 * 60
    while job.get("status") in ("queued", "in_progress"):
        if time.time() > deadline:
            raise RuntimeError("Sora took longer than 30 minutes")
        time.sleep(15)
        job = openai_call(f"https://api.openai.com/v1/videos/{job['id']}")
    if job.get("status") != "completed":
        raise RuntimeError(f"Sora job {job.get('status')}: {json.dumps(job.get('error'))[:300]}")
    os.makedirs(os.path.dirname(out_clip), exist_ok=True)
    with open(out_clip, "wb") as f:
        f.write(openai_call(f"https://api.openai.com/v1/videos/{job['id']}/content", raw=True, timeout=600))
    return out_clip


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (default today); the same date always gives the same pick")
    ap.add_argument("--dry-run", action="store_true", help="print the pick and prompt, call nothing")
    args = ap.parse_args()
    day = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    pub_path = os.path.join(HERE, "published.json")
    published = json.load(open(pub_path)) if os.path.exists(pub_path) else []

    choice = pick(day, published)
    if os.environ.get("FORCE_SOUND") == "music":  # a hand-started run can ask for a music day
        choice["sound"] = "lofi"
    elif os.environ.get("FORCE_SOUND") == "soundscape" and choice["sound"] == "lofi":
        choice["sound"] = random.Random(day.toordinal()).choice([choice["scene"]["bed"], "brown", "white"])
    prompt = prompt_for(choice["scene"], choice["color"], choice["car"])
    meta = sidecar(choice)
    if not args.dry_run:
        with_written_intro(choice, meta)
    maker = os.environ.get("MAKER") if os.environ.get("MAKER") in MAKERS else pick_maker(published, choice["sound"])
    print(json.dumps(dict(car=choice["car"], color=choice["color"], scene=choice["scene"]["id"],
                          sound=choice["sound"], maker=maker, title=meta["title"], prompt=prompt), indent=2))
    if args.dry_run:
        return
    base = os.path.join(HERE, "stills", f"{day.isoformat()}-{slug(choice['short'])}")
    meta["maker"] = generate(prompt, base + ".webp", "openai" if maker == "sora" else maker)
    for _ in range(2):  # an outdoor picture that came out as two side-by-side photos gets painted again
        if not (ROOMS[choice["scene"]["room"]].get("outdoor") and looks_split(base + ".webp")):
            break
        print("the picture came out split in two; painting it again", file=sys.stderr)
        meta["maker"] = generate(prompt, base + ".webp", meta["maker"])
    if maker == "sora" and meta["maker"] == "openai":
        clip = os.path.join(CLIPS, os.path.basename(base) + ".mp4")
        try:
            generate_sora(base + ".webp", SORA_PROMPT.format(color=choice["color"], car=choice["car"],
                                                             motion=scene_motion(choice["scene"])), clip)
            meta["maker"], meta["motion_clip"] = "sora", os.path.relpath(clip, HERE)
        except RuntimeError as e:
            print("Sora failed; using the still photo today:", e, file=sys.stderr)
    with open(base + ".json", "w") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    print("wrote", base + ".webp", "painted by", meta["maker"])


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print("car engine:", e, file=sys.stderr)
        sys.exit(2)
