# Garage TV

Long, calm "put it on the shop TV" videos: cool cars, low light, and a
white-noise soundscape that sounds like a quiet garage. Built to be driven
from a phone: tell Claude what you want, Claude renders it here and hands
back an MP4.

## Quick start

```bash
pip install numpy Pillow imageio-ffmpeg
cd garage-tv
python3 build.py --minutes 60 --theme amber        # one-hour video
python3 build.py --minutes 10 --theme cyan --compressor
```

Output lands in `garage-tv/out/garage-<theme>-<minutes>m.mp4`
(1280x720, H.264 + AAC, plays on any smart TV, phone, or YouTube).

Themes: `cyan` `amber` `red` `purple` `white`

## What it makes

**Sound** (`make_ambience.py`): layered brown noise (the shop fan / HVAC
rumble that people mean by "white noise"), a breathing pink-noise air hiss,
a faint 60 Hz mains hum, and optionally an air compressor that kicks on for
30-45 s every few minutes (`--compressor`). Mixed to -6 dBFS so it is not
loud on a TV. Every level is a flag: `--rumble`, `--hiss`, `--hum`.

**Picture** (`make_visuals.py`): a seamless loop of a coupe silhouette in a
dark bay under a neon strip. A soft light sweeps the body, the neon
breathes, dust drifts, and the camera does a very slow zoom. Everything is
periodic over the loop length so it repeats with no visible seam.

**Assembly** (`build.py`): renders the audio for the full length, renders one
visual loop, then loops the picture to fit the audio and muxes the two.

## Using real footage instead

The generated scene is a placeholder for testing the pipeline. For the real
thing, the best visuals are your own: prop the phone on a tripod in the bay
with a nice car under the lights, film 30-60 s of nothing happening (a slow
pan is even better), then:

```bash
python3 build.py --minutes 60 --footage my-clip.mp4
```

The clip is looped to the audio length. Keep the clip static or slow so the
loop point is not jarring, and film in landscape.

## Phone workflow

1. Open Claude on the phone and describe the video ("one hour, amber, with
   the compressor").
2. Claude runs `build.py` with those flags and sends the MP4 back.
3. Save it to the phone, AirPlay / Cast it to the shop TV, or upload it to
   YouTube for the long-form "ambience" audience.

## Ideas for later

- More silhouettes (truck, classic, EV) chosen with `--car`.
- Rain-on-the-roof or night-street layers for the soundscape.
- Text-to-video (Veo / Runway / Sora) shots for the visuals, written from
  Claude prompts, dropped in via `--footage`.
- A YouTube channel: 1-hour and 8-hour cuts, one per theme.
