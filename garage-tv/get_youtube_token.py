#!/usr/bin/env python3
"""One-time helper: sign in to YouTube and hand the three upload secrets to GitHub.

Run this on your own Mac (not in the cloud). Easiest: in Google Cloud > Clients, click
Download JSON on your Desktop client, then in Terminal:
  cd ~/Downloads && python3 get_youtube_token.py

It finds the client_secret_....json file in Downloads by itself (or pass
CLIENT_ID CLIENT_SECRET). A browser opens: sign in, pick the channel, allow access.
Then it opens GitHub's "New secret" page and puts each name and value on the clipboard,
one at a time, so you only paste (Cmd+V).

  python3 get_youtube_token.py --renew   replaces only YT_REFRESH_TOKEN (if uploads stop with
                                         invalid_grant, or after publishing the consent screen)
"""
import glob
import http.server
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import webbrowser

SCOPE = "https://www.googleapis.com/auth/youtube.upload"
PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}/"
NEW_SECRET = "https://github.com/markfowler01/markfowler01.github.io/settings/secrets/actions/new"
EDIT_TOKEN = "https://github.com/markfowler01/markfowler01.github.io/settings/secrets/actions/YT_REFRESH_TOKEN"


def find_client():
    """Client ID and secret from the newest client_secret*.json in Downloads or here."""
    files = glob.glob(os.path.expanduser("~/Downloads/client_secret*.json")) + glob.glob("client_secret*.json")
    if not files:
        sys.exit("Couldn't find the Google key file.\nIn Google Cloud > Clients, click your PARKED FM client, "
                 "then Download JSON, and run this again.")
    newest = max(files, key=os.path.getmtime)
    with open(newest) as f:
        c = json.load(f)
    c = c.get("installed") or c.get("web") or c
    print("Using", os.path.basename(newest))
    return c["client_id"], c["client_secret"]


def copy(text):
    try:
        subprocess.run(["pbcopy"], input=text.encode(), check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def main():
    renew = "--renew" in sys.argv  # only replace YT_REFRESH_TOKEN (the other two never change)
    if renew:
        sys.argv.remove("--renew")
    if len(sys.argv) == 3:
        client_id, client_secret = sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 1:
        client_id, client_secret = find_client()
    else:
        sys.exit(__doc__)
    auth = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": REDIRECT, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent select_account",
    })
    got = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"All set. You can close this tab and go back to Terminal.")

        def log_message(self, *a):
            pass

    print("Opening your browser to sign in...\nIf it doesn't open, paste this link into it:\n\n" + auth + "\n")
    webbrowser.open(auth)
    srv = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    while "code" not in got and "error" not in got:
        srv.handle_request()
    if "error" in got:
        sys.exit("Google said: " + got["error"])

    data = urllib.parse.urlencode({
        "code": got["code"], "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": REDIRECT, "grant_type": "authorization_code",
    }).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data) as r:
        tok = json.load(r)
    if "refresh_token" not in tok:
        sys.exit("No refresh token came back. Remove the app's access at myaccount.google.com/permissions and run again.")

    secrets = [("YT_CLIENT_ID", client_id), ("YT_CLIENT_SECRET", client_secret),
               ("YT_REFRESH_TOKEN", tok["refresh_token"])]
    if renew and copy(tok["refresh_token"]):
        webbrowser.open(EDIT_TOKEN)
        input("\nNew token copied. On the GitHub page, click in the Value box, press Cmd+V, click "
              "Update secret, then press Enter here...")
        copy("")
        print("\nDone. YouTube uploads stay connected for good now.")
        return
    if not copy("test"):
        print("Copy these three into GitHub > Settings > Secrets and variables > Actions > New repository secret:\n")
        for name, value in secrets:
            print(f"{name:18}= {value}")
        return
    print("\nSigned in. Now 3 GitHub secrets. Each one: paste the name, paste the value, click Add secret.\n")
    for i, (name, value) in enumerate(secrets, 1):
        webbrowser.open(NEW_SECRET)
        copy(name)
        input(f"[{i}/3] Name copied ({name}). Click the Name box, press Cmd+V, then press Enter here...")
        copy(value)
        input(f"[{i}/3] Value copied. Click the Secret box, press Cmd+V, click Add secret, then press Enter here...")
    copy("")
    print("\nDone. All three secrets are in GitHub, and tomorrow's video uploads itself.")


if __name__ == "__main__":
    main()
