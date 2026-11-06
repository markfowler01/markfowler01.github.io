// Runs inside linkedin.com pages. Reads notifications / catch-up / connections and sends messages
// through LinkedIn's normal UI, exactly as if you clicked the buttons yourself.
(function () {
  if (window.__larLoaded) return;
  window.__larLoaded = true;

  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const txt = el => (el ? (el.innerText || el.textContent || '') : '').replace(/\s+/g, ' ').trim();

  // ---------- warning / captcha / restriction detection ----------
  const WARN_PHRASES = [
    /security verification/i, /quick security check/i, /let's do a quick/i, /captcha/i,
    /unusual activity/i, /temporarily restricted/i, /account has been restricted/i,
    /we['’]ve restricted/i, /verify (that )?you['’]re (a )?human/i, /access to your account has been/i,
    /you['’]ve reached the (weekly|daily) (invitation|message) limit/i
  ];
  function detectWarning() {
    if (/\/checkpoint\/|\/uas\/|\/challenge\//.test(location.pathname)) return 'LinkedIn checkpoint / verification page opened';
    if (document.querySelector('iframe[src*="captcha"], #captcha, [id*="captcha" i], .challenge-dialog')) return 'Captcha shown';
    const body = (document.body && document.body.innerText || '').slice(0, 30000);
    for (const rx of WARN_PHRASES) { const m = body.match(rx); if (m) return `LinkedIn showed: "${m[0]}"`; }
    return null;
  }
  // Tell the background about a warning even if the user just happens to be browsing.
  setTimeout(() => {
    const w = detectWarning();
    if (w) chrome.runtime.sendMessage({ type: 'warning', reason: w }, () => chrome.runtime.lastError);
  }, 4000);

  // ---------- parsing helpers ----------
  function profileLink(card) {
    const links = [...card.querySelectorAll('a[href*="/in/"]')];
    return links.find(a => txt(a) && !/^(view|see|connect|message|follow)/i.test(txt(a))) || links[0] || null;
  }
  function nameFrom(card, link) {
    const strong = card.querySelector('strong, .mn-connection-card__name, [class*="entity-result__title"] span[aria-hidden="true"], span.t-bold');
    let n = txt(strong) || txt(link);
    n = n.split('\n')[0].replace(/\s*(•|·|\|).*$/, '').trim();
    if (!n || /linkedin/i.test(n) || n.length > 60) return '';
    return n;
  }
  function classify(text) {
    if (/birthday/i.test(text)) return 'birthday';
    if (/(started a new (position|role|job)|new (position|role|job)|is now (a |an |the )?[^.]{2,60} at |started working (at|as)|has a new job|job change|work anniversary)/i.test(text)) {
      if (/anniversary/i.test(text)) return null;
      return 'jobChange';
    }
    if (/(accepted your (invitation|connection|request)|is now a connection|you are now connected|connected with you|has connected)/i.test(text)) return 'connection';
    return null;
  }
  function parseRole(text) {
    // "X started a new position as Senior PM at Acme" / "X is now Head of Sales at Acme"
    let m = text.match(/(?:position as|role as|job as|is now(?: an?| the)?|working as|as an?|as)\s+(.+?)\s+at\s+([^.,\n!]+)/i);
    if (m) return { newTitle: clean(m[1]), company: clean(m[2]) };
    m = text.match(/\bat\s+([^.,\n!]{2,60})/i);
    if (m) return { newTitle: '', company: clean(m[1]) };
    return { newTitle: '', company: '' };
  }
  function clean(s) {
    return (s || '').replace(/\b(Inc|LLC|Ltd|Corp)\.?$/i, m => m).replace(/\s*(•|·|\|).*$/, '').replace(/[\s.!]+$/, '').trim().slice(0, 60);
  }
  function parseOccupation(occ) {
    // "Senior Engineer at Acme"  |  "Founder, Acme"  |  "Acme"
    const m = occ.match(/^(.+?)\s+(?:at|@)\s+(.+)$/i);
    if (m) return { newTitle: clean(m[1]), company: clean(m[2]) };
    const c = occ.match(/^(.+?),\s*(.+)$/);
    if (c) return { newTitle: clean(c[1]), company: clean(c[2]) };
    return { newTitle: '', company: '' };
  }
  function recentConnectionText(text) {
    const m = text.match(/connected\s+(.+?)\s+ago|connected\s+(today|yesterday)/i);
    if (!m) return false;
    const t = (m[1] || m[2] || '').toLowerCase();
    if (/today|yesterday|minute|hour|just now/.test(t)) return true;
    const d = t.match(/(\d+)\s*day/);
    return d ? Number(d[1]) <= 7 : false;
  }

  async function scrollToLoad(times = 4) {
    for (let i = 0; i < times; i++) { window.scrollTo(0, document.body.scrollHeight); await sleep(1200); }
    window.scrollTo(0, 0);
    await sleep(500);
  }

  // ---------- scanners ----------
  function cardsFor(kind) {
    let sel;
    if (kind === 'connections') sel = 'li.mn-connection-card, li[class*="connection-card"], .mn-connection-card';
    else sel = 'article, .nt-card, [data-finite-scroll-hotkey-item], .artdeco-card li, section li';
    const cards = [...document.querySelectorAll(sel)].filter(c => c.querySelector('a[href*="/in/"]'));
    // Drop cards that contain other matching cards (keep innermost).
    return cards.filter(c => !cards.some(o => o !== c && c.contains(o)));
  }

  function scanEvents() {
    const out = [];
    for (const card of cardsFor('events')) {
      const text = txt(card);
      const eventType = classify(text);
      if (!eventType) continue;
      const link = profileLink(card);
      if (!link) continue;
      const name = nameFrom(card, link);
      if (!name) continue;
      const role = eventType === 'jobChange' ? parseRole(text) : (eventType === 'connection' ? parseRole(text) : {});
      out.push({ eventType, profileUrl: link.href, name, firstName: LAR.firstNameOf(name), company: role.company || '', newTitle: role.newTitle || '', sourceText: text });
    }
    return out;
  }

  function scanConnections() {
    const out = [];
    for (const card of cardsFor('connections')) {
      const text = txt(card);
      if (!recentConnectionText(text)) continue;
      const link = profileLink(card);
      if (!link) continue;
      const name = nameFrom(card, link);
      if (!name) continue;
      const occ = txt(card.querySelector('.mn-connection-card__occupation, [class*="occupation"], [class*="subtitle"]'));
      const role = parseOccupation(occ);
      out.push({ eventType: 'connection', profileUrl: link.href, name, firstName: LAR.firstNameOf(name), company: role.company, newTitle: role.newTitle, sourceText: text });
    }
    return out;
  }

  // ---------- sending ----------
  function findMessageButton() {
    const scope = document.querySelector('main') || document.body;
    const candidates = [...scope.querySelectorAll('button, a')];
    const ok = el => {
      const label = (el.getAttribute('aria-label') || '').trim();
      const t = txt(el);
      return /^message\b/i.test(label) || /^message$/i.test(t);
    };
    // Prefer the one in the profile's top card, and ignore the sticky header duplicate.
    const top = candidates.filter(ok).filter(el => el.offsetParent !== null);
    return top.find(el => el.closest('.pv-top-card, .ph5, section')) || top[0] || null;
  }
  async function waitFor(selectorFn, timeoutMs) {
    const end = Date.now() + timeoutMs;
    while (Date.now() < end) { const el = selectorFn(); if (el) return el; await sleep(300); }
    return null;
  }

  async function sendMessage(message) {
    const w = detectWarning();
    if (w) return { ok: false, warning: w };

    const btn = findMessageButton();
    if (!btn) return { ok: false, error: 'No "Message" button on this profile (not a 1st-degree connection, or layout changed)' };
    btn.click();

    const box = await waitFor(() => document.querySelector('.msg-form__contenteditable[contenteditable="true"], div[role="textbox"][contenteditable="true"]'), 12000);
    if (!box) return { ok: false, error: 'Message box did not open' };
    await sleep(800);

    box.focus();
    let typed = false;
    try { typed = document.execCommand('insertText', false, message); } catch (e) { typed = false; }
    if (!typed || !box.innerText.includes(message.slice(0, 20))) {
      box.innerHTML = '';
      const p = document.createElement('p');
      p.textContent = message;
      box.appendChild(p);
      box.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: message }));
    }
    await sleep(1000);
    if (!box.innerText.includes(message.slice(0, 20))) return { ok: false, error: 'Could not type into the message box' };

    const form = box.closest('form') || document;
    const sendBtn = await waitFor(() => {
      const b = form.querySelector('button.msg-form__send-button, button[type="submit"]');
      return b && !b.disabled ? b : null;
    }, 8000);
    if (!sendBtn) return { ok: false, error: 'Send button never became enabled' };
    sendBtn.click();
    await sleep(2500);

    const w2 = detectWarning();
    if (w2) return { ok: false, warning: w2 };
    const cleared = !box.isConnected || txt(box) === '';
    if (!cleared) return { ok: false, error: 'Send did not go through (text still in box)' };

    // Tidy up: close the conversation bubble.
    const close = [...document.querySelectorAll('button')].find(b => /^close your conversation/i.test(b.getAttribute('aria-label') || ''));
    if (close) close.click();
    return { ok: true };
  }

  // ---------- message bridge ----------
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    (async () => {
      try {
        if (msg.type === 'ping') return sendResponse({ ok: true, url: location.href });
        if (msg.type === 'scan') {
          const w = detectWarning();
          if (w) return sendResponse({ people: [], warning: w });
          await scrollToLoad(msg.kind === 'connections' ? 2 : 4);
          const people = msg.kind === 'connections' ? scanConnections() : scanEvents();
          return sendResponse({ people, url: location.href });
        }
        if (msg.type === 'send') return sendResponse(await sendMessage(msg.message));
        sendResponse({ ok: false, error: 'unknown' });
      } catch (e) {
        sendResponse({ ok: false, error: String(e && e.message || e) });
      }
    })();
    return true;
  });
})();
