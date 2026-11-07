---
name: chrome-extension-agent-setup
description: How to build, test and publish Chrome extensions with a coding agent — installing Chrome's Modern Web Guidance skills (chrome-extensions, modern-web-guidance), adding the Chrome DevTools MCP server with extension tools, and keeping a CHROMEWEBSTORE.md file with permission justifications for the Chrome Web Store. Use when creating or changing a Chrome extension, setting up extension tooling, or preparing an extension for store submission.
---

# Building Chrome extensions with a coding agent

Source: Chrome for Developers, "Build extensions with coding agents" (last updated 2026-05-19).
Related docs: https://developer.chrome.com/docs/modern-web-guidance and https://developer.chrome.com/docs/devtools/agents

## 1. Install Chrome's skills (Modern Web Guidance)

Run on the user's own machine (interactive wizard; keeps skills up to date):

```bash
npx modern-web-guidance@latest install --choose
```

Pick the coding agent(s), and select both `chrome-extensions` and `modern-web-guidance`.
If those skills are installed, load `chrome-extensions` before writing extension code — it has
current APIs (newer than model training), best practices, and the CHROMEWEBSTORE.md format.

## 2. Add Chrome DevTools for agents (MCP)

Claude Code (project scope, writes `.mcp.json`):

```bash
claude mcp add chrome-devtools --scope project -- npx chrome-devtools-mcp@latest --categoryExtensions --autoConnect
```

- `--categoryExtensions` is required for the extension tools.
- `--autoConnect` attaches to the user's real Chrome profile (needed for sign-in flows such as
  Google Sign-in, and for Chrome's built-in AI APIs).
- In Chrome, open `chrome://inspect/#remote-debugging` and enable
  "Allow remote debugging for this browser instance". This must be re-allowed every new browser
  session; Chrome then asks for approval and shows "Chrome is currently controlled by automated
  test software".
- Other agents: https://github.com/ChromeDevTools/chrome-devtools-mcp/#mcp-client-configuration

Generic MCP config:

```json
{
  "mcpServers": {
    "chrome-devtools-mcp": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest", "--categoryExtensions", "--autoConnect"]
    }
  }
}
```

What the extension tools can do: install/uninstall extensions, list and reload them, trigger
extension actions, and inspect every surface (popup, side panel, service worker).

**Cloud sessions:** `--autoConnect` cannot reach the user's local Chrome from a cloud container.
There, test with the pre-installed Chromium/Playwright instead (load the unpacked extension with
`chromium.launchPersistentContext` and `--disable-extensions-except=<dir> --load-extension=<dir>`),
and tell the user to use the MCP server locally.

## 3. Always maintain CHROMEWEBSTORE.md

Whenever creating or changing a Chrome extension, create and keep up to date a `CHROMEWEBSTORE.md`
next to `manifest.json`. It holds what the Chrome Web Store Developer Dashboard asks for, so the
user can copy it straight in:

- Single purpose statement (the store enforces the single-purpose policy)
- Store listing: name, short and detailed description, category
- A justification for **every** permission and host permission in `manifest.json`
  (e.g. `storage` — persists the user's notes locally; `sidePanel` — shows the UI in the side panel)
- Remote code use (normally "No")
- Data usage / privacy disclosures and the privacy policy text, including how data is handled locally
- Notes on review history (rejection reasons and what changed)

Update it in the same change whenever permissions are added or removed.
(If the `chrome-extensions` skill is installed, follow its exact format.)

## 4. Build defaults

- Manifest V3 only; service worker background, no remotely hosted code.
- Request the fewest permissions possible; prefer `activeTab` and optional permissions.
- Example: a "Quick notes" popup extension needs only the `storage` permission.
- After building, install it, exercise each surface, check the service worker console for errors,
  then report what was verified.

## Useful prompts

- First publish: "Prepare the extension for publication on the Chrome Web Store."
- New permissions: "We just added the 'declarativeNetRequest' and 'storage' permissions to our
  manifest. Let's update our store listing."
- Rejection: paste the reason, e.g. "Our submission was rejected because our privacy policy doesn't
  explicitly mention how we handle user data locally. Update the privacy policy section in
  CHROMEWEBSTORE.md."
