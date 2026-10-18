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

## Daily machine (PARKED FM)

PARKED FM: *Dream Cars. Easy Listening.* `.github/workflows/car-people-sleep-daily.yml`
runs every day around 13:23 UTC:

1. **Car engine** (`car_engine.py`, with a `GEMINI_API_KEY` (Nano Banana Pro at 2K,
   falling back to Nano Banana) or
   `OPENAI_API_KEY` secret): picks a random **exotic** car (Ferrari, Lamborghini,
   McLaren, Porsche GT, Aston Martin, Bugatti, Pagani, Koenigsegg, ...), a colour
   and a scene from one of three series, never repeating a car from the last 20
   videos or a scene from the last 3, and paints it. Black letterbox bars are
   trimmed. Without a key, or if the call fails, the day uses the photo queue.

   | Series | Scenes | Length |
   |---|---|---|
   | Midnight Garage | garages above a rainy city, the shop after hours, rooftop deck | 3 h |
   | Rainy Drives | rainy mountain road, neon city, forest road, late-night gas station | 8 h |
   | Parked & Peaceful | snowy cabin, desert dusk, foggy coast, mountain overlook, lakeside cafe | 4 h |

2. **Photo queue** fallback: the next never-used picture in `stills/`, or the
   one used longest ago with a new colour grade.
3. **Sound, alternating days:**
   - **Music day:** 30 minutes of continuous original lo-fi (`make_lofi.py`), new
     every time, at the series length. **Music only: never any rain, hiss, crackle or
     other noise mixed in.** Music and white noise always stay in separate videos.
   - **Soundscape day:** 8 hours, no music. The scene's own rain, wind, fan or heater
     sound, or plain brown or white noise (`make_ambience.py`). `--style jazz` and `--style piano` exist but are not used.
4. **Kit:** smooth 60 s video loop (falling rain on rainy scenes), PARKED FM
   thumbnail (navy, cream, amber), title, description, tags, and a 30 s vertical
   **trailer** for Shorts. Published as release `daily-YYYY-MM-DD`; kits older
   than 21 days are deleted. `published.json` logs every video.

On a Mac: unzip the kit, `cd` into it, `bash make-video.command`, upload the
finished file, then upload `trailer.mp4` as a Short from the YouTube app.

**Picture test (Nano Banana vs ChatGPT vs Sora).** With both `GEMINI_API_KEY` and
`OPENAI_API_KEY` set, the car engine rotates three makers: a Nano Banana Pro photo, a ChatGPT
(`gpt-image-1`) photo, and Sora (a ChatGPT photo animated into a 12 s clip, looped seamlessly by
`make_motion_loop.py`). Each maker gets the same number of music days and soundscape days.
`published.json` records the maker and YouTube ids. With a `YT_API_KEY` secret (a plain Google
Cloud API key for YouTube Data API v3), `scoreboard.py` refreshes view counts daily into
absoluteadas.com/parked-fm/scoreboard. Sora costs about $1.20 a video (`sora-2`, 720p); set the
repository variable or env `SORA_MODEL=sora-2-pro` for 1792x1024 at about $6.

**Turning on Nano Banana photos (preferred, about 4 cents an image):**
aistudio.google.com > Get API key > Create API key (set up billing on that
project if asked), then add it as repository secret `GEMINI_API_KEY`.

**Or ChatGPT photos:** platform.openai.com > API keys > Create new
secret key (billing must be set up; one high-quality image is roughly a
quarter, so about $5-8 a month daily). Then github.com > this repo > Settings >
Secrets and variables > Actions > New repository secret, name
`OPENAI_API_KEY`, paste the key.

**Adding your own photos:** github.com > this repo > `garage-tv/stills` >
Add file > Upload files > Commit to `main`. Optional `<same-name>.json` beside
a photo sets its title, description, tags, `bed`, `text_side`, `text_scale`
and `rain` (see `rain-road-gt500.json`).

**Full auto-upload (optional).** With these repository secrets set, the job
also builds the 8-hour file and uploads it to YouTube with the thumbnail:
`YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.

1. console.cloud.google.com: create a project, enable **YouTube Data API v3**.
2. OAuth consent screen: External, add yourself as a test user, then set
   publishing status to **In production** (in Testing, tokens die after 7 days).
3. Credentials: create an OAuth client ID of type **Desktop app**.
4. Click **Download JSON** on the client, then on the Mac: `cd ~/Downloads && python3 get_youtube_token.py`
   (it finds the key file itself),
   sign in, pick the PARKED FM channel, and copy the three values into
   GitHub > Settings > Secrets and variables > Actions.
5. Apply for the free YouTube API compliance audit. Until it passes, Google
   locks API uploads from new projects to private, so you would still flip
   each one to Public by hand.

Run it by hand any time from the repo's Actions tab: **PARKED FM daily
video**, then **Run workflow**. Locally: `python3 weekly.py --outdir kit`.

## Phone workflow

1. Send Claude a photo of a car in the bay (or just say which one to use).
2. Say the length and whether you want the compressor.
3. Claude builds it here. Short cuts come back in chat; long ones are
   built and you pull them down, or you run the two-line concat above.
4. Cast it to the shop TV, or upload it to YouTube.
