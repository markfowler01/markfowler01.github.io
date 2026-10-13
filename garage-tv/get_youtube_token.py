#!/usr/bin/env python3
"""One-time helper: sign in to YouTube and print a refresh token for the weekly uploader.

Run this on your own Mac (not in the cloud):
  python3 get_youtube_token.py CLIENT_ID CLIENT_SECRET

A browser opens. Sign in, pick the channel you want the videos on, and allow access.
The script prints YT_REFRESH_TOKEN. Paste it, with the client ID and secret, into the
repository's Settings > Secrets and variables > Actions.
"""
import http.server
import json
import sys
import urllib.parse
import urllib.request
import webbrowser

SCOPE = "https://www.googleapis.com/auth/youtube.upload"
PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}/"


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    client_id, client_secret = sys.argv[1], sys.argv[2]
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
    print("Copy these three into GitHub > Settings > Secrets and variables > Actions > New repository secret:\n")
    print("YT_CLIENT_ID      =", client_id)
    print("YT_CLIENT_SECRET  =", client_secret)
    print("YT_REFRESH_TOKEN  =", tok["refresh_token"])


if __name__ == "__main__":
    main()
