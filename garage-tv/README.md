# Garage TV

Long, calm "put it on the shop TV" videos: a cool car in a quiet bay and a
white-noise soundscape that sounds like the shop after hours. Built to be
driven from a phone: tell Claude what you want, Claude renders it and hands
back an MP4.

## Quick start

```bash
pip install numpy Pillow imageio-ffmpeg
cd garage-tv
python3 build.py --minutes 480 --image stills/bay-dusk.webp   # 8-hour loop from a photo
python3 build.py --minutes 60 --theme amber --compressor      # generated neon scene
```

Output lands in `garage-tv/out/garage-<name>-<minutes>m.mp4`
(1920x1080, H.264 + AAC, plays on any smart TV, phone, or YouTube).

## Visual sources

- `--image photo.jpg` : a slow drift and zoom over a still photo, with
  floating dust and a faint light breathe. `stills/bay-dusk.webp` is the
  shop-at-dusk picture. Best results from a landscape photo at least
  1600 px wide.
- `--footage clip.mp4` : your own video, looped as-is. Phone on a tripod, a
  nice car under the lights, 30-60 s of nothing happening.
- neither : the generated coupe-silhouette scene. Themes: `cyan` `amber`
  `red` `purple` `white`.

## Sound

`make_ambience.py` layers brown noise (the shop fan / HVAC rumble people
mean by "white noise"), a breathing pink-noise air hiss, a faint 60 Hz mains
hum, and optionally an air compressor that kicks on for 30-45 s every few
minutes (`--compressor`). Mixed to -6 dBFS so it is not loud on a TV. Every
level is a flag: `--rumble`, `--hiss`, `--hum`.

## How an 8-hour file builds in minutes

`build.py` renders one seamless 60 s visual loop and one seamless 10 min
audio chunk, then has ffmpeg repeat the video with stream copy (no
re-encode) and concatenate the raw audio chunks, encoding the AAC track
once. Every moving element is periodic over its loop, so there is no
visible or audible seam.

Rough sizes at 1080p: about 10 MB per minute, so an 8-hour file is around
5 GB. Too big to send through chat, fine for YouTube or a USB stick.

## Make the long file yourself from the seed files

The seed is two small files: the 60 s video loop (`loop-<name>.mp4`, no
sound) and the seamless raw audio chunk (`ambience-2m-seamless.wav`).
Any computer with ffmpeg turns them into the exact 8-hour file:

```bash
ffmpeg -stream_loop 479 -i loop-bay-dusk.mp4 -stream_loop 239 -i ambience-2m-seamless.wav \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -t 28800 -movflags +faststart garage-bay-dusk-8h.mp4
```

The video is repeated with stream copy (no re-encode). The audio is looped
as raw PCM, which has no gaps, and encoded once, so the sound track is one
continuous 8-hour stream with no click or dropout at any loop point. This
matters for sleep videos. It takes about 10 minutes, almost all of it audio
encoding. On a phone the same command works in iSH (iPhone,
`apk add ffmpeg`) or Termux (Android, `pkg install ffmpeg`).

Do not simply repeat a finished MP4 with `-c copy`: AAC audio carries a
few milliseconds of encoder padding per file, so you get a tiny hiccup at
every join.

YouTube notes: accounts must be verified (phone number) before uploads
over 15 minutes are allowed; the limit is then 12 hours / 256 GB.

Or skip the file entirely and set the TV or player to repeat.

## Weekly machine (Car People Sleep)

`.github/workflows/garage-tv-weekly.yml` runs every Sunday at 14:23 UTC and
calls `weekly.py`, which picks the week's combination from the date:

| Changes | Rotation |
|---|---|
| Sound, every week | rain, shop fan, wind, heater |
| Colour, every 4 weeks | as shot, night, amber work lights, cold winter |
| Photo, every week | cycles through everything in `stills/` |

It builds the 60 s loop, the 2 min seamless sound, a thumbnail in the
Car People Sleep style, and the title / description / tags, then publishes a
GitHub release named `garage-tv-YYYY-Www` holding a zip of the kit. Each zip
has `make-8h.command`: open Terminal, type `bash `, drag the file in, press
Enter, and the 8-hour MP4 appears next to it.

**Add photos any time.** Drop a landscape JPG/PNG/WebP (1600 px wide or
more) into `garage-tv/stills/` on the main branch. More photos means more
variety, and YouTube is less likely to flag the channel as repetitive.

**Full auto-upload (optional).** With these repository secrets set, the job
also builds the 8-hour file and uploads it to YouTube with the thumbnail:
`YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.

1. console.cloud.google.com: create a project, enable **YouTube Data API v3**.
2. OAuth consent screen: External, add yourself as a test user, then set
   publishing status to **In production** (in Testing, tokens die after 7 days).
3. Credentials: create an OAuth client ID of type **Desktop app**.
4. On the Mac: `python3 garage-tv/get_youtube_token.py CLIENT_ID CLIENT_SECRET`,
   sign in, pick the Car People Sleep channel, and copy the three values into
   GitHub > Settings > Secrets and variables > Actions.
5. Apply for the free YouTube API compliance audit. Until it passes, Google
   locks API uploads from new projects to private, so you would still flip
   each one to Public by hand.

Run it by hand any time from the repo's Actions tab: **Garage TV weekly
video**, then **Run workflow**. Locally: `python3 weekly.py --outdir kit`.

## Phone workflow

1. Send Claude a photo of a car in the bay (or just say which one to use).
2. Say the length and whether you want the compressor.
3. Claude builds it here. Short cuts come back in chat; long ones are
   built and you pull them down, or you run the two-line concat above.
4. Cast it to the shop TV, or upload it to YouTube.
