// Service worker: scheduling, the review queue, daily caps, delays and the send loop.
importScripts('shared.js');

const SCAN_ALARM = 'lar-scan';
const SEND_ALARM = 'lar-send';
const LOCK_MS = 6 * 60 * 1000;

const SCAN_PAGES = [
  { kind: 'notifications', url: 'https://www.linkedin.com/notifications/?filter=all' },
  { kind: 'catchup', url: 'https://www.linkedin.com/mynetwork/catch-up/all/' },
  { kind: 'connections', url: 'https://www.linkedin.com/mynetwork/invite-connect/connections/' }
];

// ---------- lifecycle ----------
chrome.runtime.onInstalled.addListener(async () => {
  const { settings } = await LAR.storageGet('settings');
  if (!settings) await LAR.storageSet({ settings: LAR.DEFAULT_SETTINGS });
  const cur = await LAR.storageGet(['queue', 'log', 'state']);
  await LAR.storageSet({
    queue: cur.queue || [],
    log: cur.log || [],
    state: Object.assign({ halted: false, haltReason: '', lastScan: 0, note: '', nextSendAt: 0 }, cur.state || {})
  });
  chrome.alarms.create(SCAN_ALARM, { periodInMinutes: 60 });
  await updateBadge();
});
chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create(SCAN_ALARM, { periodInMinutes: 60 });
  updateBadge();
});

chrome.action.onClicked.addListener(() => openDashboard());

function openDashboard() {
  const url = chrome.runtime.getURL('app.html');
  chrome.tabs.query({ url }, tabs => {
    if (tabs.length) chrome.tabs.update(tabs[0].id, { active: true });
    else chrome.tabs.create({ url });
  });
}

chrome.alarms.onAlarm.addListener(async alarm => {
  if (alarm.name === SCAN_ALARM) {
    const settings = await LAR.getSettings();
    if (settings.enabled && LAR.isBusinessHours(settings)) await runScan({ auto: true });
  } else if (alarm.name === SEND_ALARM) {
    await processQueue();
  }
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      switch (msg.type) {
        case 'scanNow': sendResponse(await runScan({ auto: false })); break;
        case 'processQueue': sendResponse(await processQueue()); break;
        case 'halt': await halt(msg.reason || 'Stopped by user'); sendResponse({ ok: true }); break;
        case 'resume': await resume(); sendResponse({ ok: true }); break;
        case 'warning': await halt(msg.reason); sendResponse({ ok: true }); break; // from content script, any page
        case 'openDashboard': openDashboard(); sendResponse({ ok: true }); break;
        default: sendResponse({ ok: false, error: 'unknown message' });
      }
    } catch (e) {
      sendResponse({ ok: false, error: String(e && e.message || e) });
    }
  })();
  return true;
});

// ---------- state helpers ----------
async function getState() {
  const { state } = await LAR.storageGet('state');
  return Object.assign({ halted: false, haltReason: '', lastScan: 0, note: '', nextSendAt: 0 }, state || {});
}
async function setState(patch) {
  const s = await getState();
  const next = Object.assign(s, patch);
  await LAR.storageSet({ state: next });
  await updateBadge();
  return next;
}
async function halt(reason) {
  await chrome.alarms.clear(SEND_ALARM);
  await setState({ halted: true, haltReason: reason, nextSendAt: 0, note: 'Halted: ' + reason });
  // Put anything mid-send back to approved so nothing is lost.
  const { queue = [] } = await LAR.storageGet('queue');
  for (const q of queue) if (q.status === 'sending') q.status = 'approved';
  await LAR.storageSet({ queue });
  await releaseLock();
}
async function resume() {
  await setState({ halted: false, haltReason: '', note: 'Resumed' });
  await scheduleNextSend(5000);
}

async function updateBadge() {
  const [{ queue = [] }, state] = [await LAR.storageGet('queue'), await getState()];
  if (state.halted) {
    chrome.action.setBadgeBackgroundColor({ color: '#c0392b' });
    chrome.action.setBadgeText({ text: '!' });
    return;
  }
  const pending = queue.filter(q => q.status === 'pending').length;
  chrome.action.setBadgeBackgroundColor({ color: '#0a66c2' });
  chrome.action.setBadgeText({ text: pending ? String(pending) : '' });
}

async function sentTodayCount() {
  const { log = [] } = await LAR.storageGet('log');
  const today = LAR.pacificParts().dateKey;
  return log.filter(l => LAR.pacificParts(new Date(l.sentAt)).dateKey === today).length;
}

// Simple lock so scan and send never overlap (survives worker restarts).
async function acquireLock(name) {
  const { lock } = await LAR.storageGet('lock');
  if (lock && lock.until > Date.now()) return false;
  await LAR.storageSet({ lock: { name, until: Date.now() + LOCK_MS } });
  return true;
}
async function releaseLock() { await LAR.storageSet({ lock: null }); }

// ---------- worker tab ----------
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function getWorkerTab() {
  const { workerTabId } = await LAR.storageGet('workerTabId');
  if (workerTabId) {
    try { const t = await chrome.tabs.get(workerTabId); if (t) return t; } catch (e) { /* gone */ }
  }
  const tab = await chrome.tabs.create({ url: 'https://www.linkedin.com/feed/', active: false });
  await LAR.storageSet({ workerTabId: tab.id });
  await waitForLoad(tab.id);
  return tab;
}
async function closeWorkerTab() {
  const { workerTabId } = await LAR.storageGet('workerTabId');
  if (workerTabId) { try { await chrome.tabs.remove(workerTabId); } catch (e) { /* ignore */ } }
  await LAR.storageSet({ workerTabId: null });
}
function waitForLoad(tabId, timeoutMs = 30000) {
  return new Promise(resolve => {
    let done = false;
    const finish = () => { if (!done) { done = true; chrome.tabs.onUpdated.removeListener(listener); resolve(); } };
    const listener = (id, info) => { if (id === tabId && info.status === 'complete') finish(); };
    chrome.tabs.onUpdated.addListener(listener);
    chrome.tabs.get(tabId).then(t => { if (t.status === 'complete') finish(); }).catch(finish);
    setTimeout(finish, timeoutMs);
  });
}
async function navigate(tabId, url) {
  await chrome.tabs.update(tabId, { url });
  await sleep(500);
  await waitForLoad(tabId);
  await sleep(3000); // let LinkedIn's client-side rendering settle
  // make sure the content script is alive
  for (let i = 0; i < 10; i++) {
    try {
      const r = await chrome.tabs.sendMessage(tabId, { type: 'ping' });
      if (r && r.ok) return true;
    } catch (e) { /* not ready */ }
    await sleep(1000);
  }
  return false;
}

// ---------- scanning ----------
async function runScan({ auto }) {
  const settings = await LAR.getSettings();
  const state = await getState();
  if (state.halted) return { ok: false, error: 'Halted: ' + state.haltReason };
  if (!(await acquireLock('scan'))) return { ok: false, error: 'Busy — a scan or send is already running' };

  let added = 0, found = 0;
  try {
    await setState({ note: 'Scanning LinkedIn…' });
    const tab = await getWorkerTab();
    const { queue = [], log = [], dismissed = [] } = await LAR.storageGet(['queue', 'log', 'dismissed']);
    const year = LAR.pacificParts().year;
    const known = new Set([
      ...queue.map(q => q.key),
      ...log.map(l => l.key),
      ...dismissed
    ]);
    const cutoff = Date.now() - settings.recontactDays * 86400000;
    const recentlyMessaged = new Set(log.filter(l => l.sentAt > cutoff).map(l => l.profileUrl));

    for (const page of SCAN_PAGES) {
      const alive = await navigate(tab.id, page.url);
      if (!alive) continue;
      let res;
      try { res = await chrome.tabs.sendMessage(tab.id, { type: 'scan', kind: page.kind }); }
      catch (e) { continue; }
      if (!res) continue;
      if (res.warning) { await halt(res.warning); return { ok: false, error: 'Halted: ' + res.warning }; }
      for (const p of res.people || []) {
        found++;
        p.profileUrl = LAR.normalizeProfileUrl(p.profileUrl);
        if (!p.profileUrl || !p.firstName) continue;
        const key = LAR.eventKey(p, year);
        if (known.has(key)) continue;
        if (recentlyMessaged.has(p.profileUrl)) { known.add(key); continue; }
        known.add(key);
        queue.push({
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          key,
          profileUrl: p.profileUrl,
          name: p.name,
          firstName: p.firstName,
          company: p.company || '',
          newTitle: p.newTitle || '',
          eventType: p.eventType,
          sourceText: (p.sourceText || '').slice(0, 300),
          message: LAR.buildMessage(settings, p),
          status: settings.mode === 'auto' ? 'approved' : 'pending',
          foundAt: Date.now(),
          approvedAt: settings.mode === 'auto' ? Date.now() : 0
        });
        added++;
      }
    }
    await LAR.storageSet({ queue });
    await setState({ lastScan: Date.now(), note: `Scan done: ${added} new draft${added === 1 ? '' : 's'} (${found} events seen)` });
  } finally {
    await releaseLock();
    await closeWorkerTab();
  }
  await scheduleNextSend(3000);
  return { ok: true, added, found };
}

// ---------- sending ----------
async function scheduleNextSend(delayMs) {
  const { queue = [] } = await LAR.storageGet('queue');
  if (!queue.some(q => q.status === 'approved')) { await setState({ nextSendAt: 0 }); return; }
  const when = Date.now() + Math.max(delayMs, 1000);
  await chrome.alarms.create(SEND_ALARM, { when });
  await setState({ nextSendAt: when });
}

async function processQueue() {
  const settings = await LAR.getSettings();
  const state = await getState();
  if (state.halted) return { ok: false, error: 'Halted: ' + state.haltReason };
  if (!settings.enabled) { await setState({ note: 'Sending is paused in settings', nextSendAt: 0 }); return { ok: false, error: 'paused' }; }

  const { queue = [] } = await LAR.storageGet('queue');
  const next = queue.filter(q => q.status === 'approved').sort((a, b) => a.approvedAt - b.approvedAt)[0];
  if (!next) { await setState({ nextSendAt: 0 }); return { ok: true, sent: 0 }; }

  if (!LAR.isBusinessHours(settings)) {
    await setState({ note: `Outside business hours (${settings.hoursStart}:00–${settings.hoursEnd}:00 Pacific). Will send when the window opens.`, nextSendAt: 0 });
    await chrome.alarms.create(SEND_ALARM, { delayInMinutes: 15 });
    return { ok: false, error: 'outside hours' };
  }
  const sentToday = await sentTodayCount();
  if (sentToday >= settings.dailyCap) {
    await setState({ note: `Daily cap reached (${sentToday}/${settings.dailyCap}). Resumes tomorrow.`, nextSendAt: 0 });
    await chrome.alarms.create(SEND_ALARM, { delayInMinutes: 60 });
    return { ok: false, error: 'cap' };
  }
  if (!(await acquireLock('send'))) { await scheduleNextSend(20000); return { ok: false, error: 'busy' }; }

  let outcome = { ok: false, error: 'unknown' };
  try {
    next.status = 'sending';
    await LAR.storageSet({ queue });
    await setState({ note: `Sending to ${next.name}…` });

    const tab = await getWorkerTab();
    const alive = await navigate(tab.id, next.profileUrl);
    if (!alive) throw new Error('Could not load profile page');
    outcome = await chrome.tabs.sendMessage(tab.id, { type: 'send', message: next.message });

    if (outcome && outcome.warning) {
      next.status = 'approved';
      await LAR.storageSet({ queue });
      await halt(outcome.warning);
      return { ok: false, error: 'Halted: ' + outcome.warning };
    }
    if (outcome && outcome.ok) {
      next.status = 'sent';
      next.sentAt = Date.now();
      const { log = [] } = await LAR.storageGet('log');
      log.push({ key: next.key, profileUrl: next.profileUrl, name: next.name, eventType: next.eventType, message: next.message, sentAt: next.sentAt });
      await LAR.storageSet({ queue, log });
      await setState({ note: `Sent to ${next.name}` });
    } else {
      next.status = 'failed';
      next.error = (outcome && outcome.error) || 'Unknown error';
      await LAR.storageSet({ queue });
      await setState({ note: `Failed for ${next.name}: ${next.error}` });
    }
  } catch (e) {
    next.status = 'failed';
    next.error = String(e && e.message || e);
    await LAR.storageSet({ queue });
    await setState({ note: `Failed for ${next.name}: ${next.error}` });
  } finally {
    await releaseLock();
    await closeWorkerTab();
  }
  await scheduleNextSend(LAR.randomDelayMs(settings));
  return outcome;
}
