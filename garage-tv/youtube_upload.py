#!/usr/bin/env python3
"""Upload a video + thumbnail to YouTube with the Data API v3 (standard library only).

Needs three environment variables (stored as GitHub Actions secrets):
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN   (get the token once with get_youtube_token.py)
Optional:
  YT_PRIVACY   public | unlisted | private   (default public)

  python3 youtube_upload.py kit/car-people-sleep-8h.mp4 kit/thumbnail.jpg kit/details.json

Note: Google keeps API uploads from a brand-new, unaudited Google Cloud project
locked to private until the project passes YouTube's free API compliance audit.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CHUNK = 64 * 1024 * 1024


def access_token():
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data) as r:
        return json.load(r)["access_token"]


def request(url, token, method="POST", body=None, headers=None):
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    return urllib.request.urlopen(req, timeout=600)


def upload(video, thumb, details):
    token = access_token()
    size = os.path.getsize(video)
    meta = {
        "snippet": {
            "title": details["title"],
            "description": details["description"],
            "tags": details["tags"],
            "categoryId": details.get("categoryId", "2"),
        },
        "status": {
            "privacyStatus": os.environ.get("YT_PRIVACY", "public"),
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": bool(details.get("alteredContent", True)),
        },
    }
    with request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        token, body=json.dumps(meta).encode(),
        headers={"Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"},
    ) as r:
        session = r.headers["Location"]

    sent, video_id = 0, None
    with open(video, "rb") as f:
        while video_id is None:
            f.seek(sent)
            chunk = f.read(CHUNK)
            end = sent + len(chunk) - 1
            for attempt in range(6):
                try:
                    with request(session, token, method="PUT", body=chunk, headers={
                        "Content-Length": str(len(chunk)),
                        "Content-Range": f"bytes {sent}-{end}/{size}"}) as r:
                        video_id = json.load(r)["id"]
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 308:  # "resume incomplete": this chunk landed, send the next
                        rng = e.headers.get("Range")
                        sent = int(rng.split("-")[1]) + 1 if rng else sent
                        break
                    if e.code in (500, 502, 503, 504) and attempt < 5:
                        time.sleep(2 ** attempt)
                        continue
                    if e.code == 401 and attempt < 5:
                        token = access_token()
                        continue
                    raise
                except (urllib.error.URLError, TimeoutError):
                    if attempt < 5:
                        time.sleep(2 ** attempt)
                        continue
                    raise
            print(f"  uploaded {min(sent, size) / 1e9:.2f} / {size / 1e9:.2f} GB", flush=True)

    print("video id:", video_id)
    with open(thumb, "rb") as f:
        with request(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}",
                     token, body=f.read(), headers={"Content-Type": "image/jpeg"}):
            pass
    print("thumbnail set")
    print(f"https://youtu.be/{video_id}")
    return video_id


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    with open(sys.argv[3]) as f:
        upload(sys.argv[1], sys.argv[2], json.load(f))
