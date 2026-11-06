# LinkedIn Auto-Reply (personal Chrome extension)

Finds three kinds of events in your own logged-in LinkedIn session and drafts a short message for each:

1. **New connections** – people who recently connected with you
2. **Birthdays** – from the Notifications and Catch Up pages
3. **Job changes** – from the Notifications and Catch Up pages

By default it runs in **approval mode**: it drafts the messages and you click **Send** or **Skip** on each one. A **Full auto mode** toggle is on the dashboard for later.

## Built-in safety rules

| Rule | Default | Where to change |
|---|---|---|
| Daily cap | 25 messages/day | Settings |
| Random delay between messages | 45–180 seconds | Settings |
| Only sends during business hours | 8am–6pm Pacific | Settings |
| Never the same person twice for the same event | always on | — |
| Skip anyone messaged in the last N days | 30 days | Settings |
| Local log (person, event, message, date) | always on | "Sent log" tab, CSV export |
| Stop on warning / captcha / restriction notice | always on | Dashboard shows a red banner; click Resume after you've checked LinkedIn |

Everything is stored only in your browser (`chrome.storage.local`). Nothing is sent anywhere except to LinkedIn, through LinkedIn's own Message button.

## Install in Chrome (about 2 minutes)

1. **Get the folder onto your computer.** Download `linkedin-autoreply-extension.zip` and double-click it to unzip. You should end up with a folder called `linkedin-autoreply-extension` that contains `manifest.json`. Put that folder somewhere you won't delete it (e.g. Documents) — Chrome loads it from that spot every time.
2. Open Chrome and type **`chrome://extensions`** in the address bar, then press Enter.
3. In the top-right corner, turn on the **Developer mode** switch.
4. Click the **Load unpacked** button (top-left).
5. Pick the `linkedin-autoreply-extension` folder and click **Select** / **Open**.
6. You'll see "LinkedIn Auto-Reply (Personal)" appear in the list. Click the puzzle-piece icon to the right of the address bar and **pin** it so its blue icon shows on the toolbar.
7. Make sure you're logged in to LinkedIn in this same Chrome profile.

That's it. Chrome may show a yellow "Disable developer mode extensions" bar once in a while — click the X; that's normal for extensions not from the Chrome Web Store.

## Using it

- Click the blue toolbar icon → the dashboard opens.
- Click **Scan LinkedIn now**. A LinkedIn tab opens in the background, visits Notifications, Catch Up and your Connections list, then closes. Drafts show up under **Review**. (It also scans on its own once an hour during business hours.)
- For each draft: edit the text if you like, then click **Send** or **Skip**. Sends go out one at a time with the random delay, and only during business hours and under the daily cap. The "Next send" box tells you when the next one will go.
- **Send all drafts** queues everything on the page. **Stop everything** halts sends immediately.
- **Settings** tab: edit the templates, daily cap, delay range, business hours and the re-contact window. The "no company known" templates are used when LinkedIn didn't show a company.
- **Sent log** tab: every message sent, with a CSV download.

The badge on the icon shows how many drafts are waiting for your review. A red **!** means it halted because LinkedIn showed a warning.

## Good to know

- The first scan looks at connections made in the last 7 days, so you won't get a flood of drafts for old connections.
- It can only message 1st-degree connections (people with a **Message** button on their profile). Anyone else gets a "Failed" note in the queue — just Skip them.
- LinkedIn changes its page layout now and then. If a scan starts finding nothing or sends start failing, the selectors in `content.js` are the place to update.
- Automating LinkedIn is against LinkedIn's User Agreement. The caps, delays and approval mode are there to keep this behaving like a person, but use it at your own risk and keep the daily cap modest.
