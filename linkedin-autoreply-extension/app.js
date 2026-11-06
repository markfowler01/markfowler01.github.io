// Dashboard: review queue, sent log, settings.
const $ = id => document.getElementById(id);
const esc = s => String(s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const send = msg => new Promise(res => chrome.runtime.sendMessage(msg, r => res(r || { ok: false, error: chrome.runtime.lastError && chrome.runtime.lastError.message })));
const fmtTime = ts => ts ? new Date(ts).toLocaleString('en-US', { timeZone: LAR.TZ, month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '—';

// ---------- tabs ----------
document.querySelectorAll('nav button').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('nav button').forEach(x => x.classList.toggle('active', x === b));
  document.querySelectorAll('main section').forEach(s => s.classList.toggle('active', s.id === 'tab-' + b.dataset.tab));
  location.hash = b.dataset.tab;
}));
if (location.hash === '#settings') document.querySelector('[data-tab="settings"]').click();

// ---------- render ----------
async function render() {
  const settings = await LAR.getSettings();
  const { queue = [], log = [], state = {} } = await LAR.storageGet(['queue', 'log', 'state']);
  const today = LAR.pacificParts().dateKey;
  const sentToday = log.filter(l => LAR.pacificParts(new Date(l.sentAt)).dateKey === today).length;
  const pending = queue.filter(q => q.status === 'pending');
  const approved = queue.filter(q => q.status === 'approved' || q.status === 'sending');

  $('modeAuto').checked = settings.mode === 'auto';
  $('stMode').textContent = settings.mode === 'auto' ? 'Full auto' : 'Approval';
  $('stToday').textContent = `${sentToday} / ${settings.dailyCap}`;
  $('stApproved').textContent = approved.length;
  $('stNext').textContent = state.nextSendAt ? fmtTime(state.nextSendAt) : (approved.length ? 'waiting' : '—');
  $('stScan').textContent = fmtTime(state.lastScan);
  $('stNote').textContent = (state.note || '') + (LAR.isBusinessHours(settings) ? '' : '  (outside business hours — sending paused)');
  $('pendingCount').textContent = pending.length ? `(${pending.length})` : '';
  $('haltBanner').classList.toggle('halt', !!state.halted);
  $('haltReason').textContent = state.haltReason || '';

  // queue
  const show = queue.filter(q => q.status !== 'sent').sort((a, b) => b.foundAt - a.foundAt);
  $('queue').innerHTML = show.length ? show.map(q => `
    <div class="card" data-id="${q.id}">
      <div class="top">
        <a href="${esc(q.profileUrl)}" target="_blank" rel="noopener">${esc(q.name)}</a>
        <span class="badge ${q.eventType}">${esc(LAR.EVENT_LABELS[q.eventType])}</span>
        ${q.company ? `<span class="subtle">${esc(q.company)}</span>` : ''}
        <span class="spacer"></span>
        <span class="subtle status-${q.status}">${esc(statusLabel(q))}</span>
      </div>
      ${q.sourceText ? `<div class="src">${esc(q.sourceText.slice(0, 160))}</div>` : ''}
      <textarea data-field="message" ${q.status === 'pending' || q.status === 'failed' ? '' : 'readonly'}>${esc(q.message)}</textarea>
      <div class="actions">
        ${q.status === 'pending' || q.status === 'failed' ? `<button class="primary" data-act="approve">Send</button>` : ''}
        ${q.status === 'approved' ? `<button class="secondary" data-act="unapprove">Hold</button>` : ''}
        ${q.status !== 'sending' ? `<button class="secondary" data-act="skip">Skip</button>` : ''}
      </div>
    </div>`).join('') : `<div class="empty">No drafts waiting. Click <b>Scan LinkedIn now</b> to look for new connections, birthdays and job changes.</div>`;

  // log
  $('logBody').innerHTML = log.slice().reverse().slice(0, 300).map(l => `
    <tr><td>${fmtTime(l.sentAt)}</td><td><a href="${esc(l.profileUrl)}" target="_blank" rel="noopener">${esc(l.name)}</a></td>
    <td>${esc(LAR.EVENT_LABELS[l.eventType])}</td><td>${esc(l.message)}</td></tr>`).join('') ||
    `<tr><td colspan="4" class="empty">Nothing sent yet.</td></tr>`;
}
function statusLabel(q) {
  return { pending: 'Draft', approved: 'Queued to send', sending: 'Sending…', failed: 'Failed: ' + (q.error || ''), skipped: 'Skipped' }[q.status] || q.status;
}

// ---------- queue actions ----------
$('queue').addEventListener('click', async e => {
  const btn = e.target.closest('button[data-act]');
  if (!btn) return;
  const card = btn.closest('.card');
  const id = card.dataset.id;
  const { queue = [], dismissed = [] } = await LAR.storageGet(['queue', 'dismissed']);
  const item = queue.find(q => q.id === id);
  if (!item) return;
  const act = btn.dataset.act;
  if (act === 'approve') {
    item.message = card.querySelector('textarea').value.trim() || item.message;
    item.status = 'approved'; item.approvedAt = Date.now(); item.error = '';
    await LAR.storageSet({ queue });
    await send({ type: 'processQueue' });
  } else if (act === 'unapprove') {
    item.status = 'pending';
    await LAR.storageSet({ queue });
  } else if (act === 'skip') {
    dismissed.push(item.key);
    await LAR.storageSet({ queue: queue.filter(q => q.id !== id), dismissed });
  }
  render();
});

$('approveAll').addEventListener('click', async () => {
  const { queue = [] } = await LAR.storageGet('queue');
  const n = queue.filter(q => q.status === 'pending').length;
  if (!n || !confirm(`Queue all ${n} drafts to send (with the usual delays and daily cap)?`)) return;
  for (const q of queue) if (q.status === 'pending') { q.status = 'approved'; q.approvedAt = Date.now(); }
  await LAR.storageSet({ queue });
  await send({ type: 'processQueue' });
  render();
});
$('processNow').addEventListener('click', async () => { await send({ type: 'processQueue' }); render(); });
$('stopBtn').addEventListener('click', async () => { await send({ type: 'halt', reason: 'Stopped by you from the dashboard' }); render(); });
$('resumeBtn').addEventListener('click', async () => { await send({ type: 'resume' }); render(); });
$('scanBtn').addEventListener('click', async () => {
  $('scanBtn').disabled = true; $('scanBtn').textContent = 'Scanning… (a LinkedIn tab opens in the background)';
  const r = await send({ type: 'scanNow' });
  $('scanBtn').disabled = false; $('scanBtn').textContent = 'Scan LinkedIn now';
  if (r && !r.ok) alert(r.error || 'Scan failed');
  render();
});
$('modeAuto').addEventListener('change', async e => {
  if (e.target.checked && !confirm('Full auto mode sends every draft without you reviewing it. Turn it on?')) { e.target.checked = false; return; }
  const settings = await LAR.getSettings();
  settings.mode = e.target.checked ? 'auto' : 'approval';
  await LAR.storageSet({ settings });
  if (settings.mode === 'auto') {
    const { queue = [] } = await LAR.storageGet('queue');
    for (const q of queue) if (q.status === 'pending') { q.status = 'approved'; q.approvedAt = Date.now(); }
    await LAR.storageSet({ queue });
    await send({ type: 'processQueue' });
  }
  loadSettings(); render();
});

// ---------- log actions ----------
$('exportCsv').addEventListener('click', async () => {
  const { log = [] } = await LAR.storageGet('log');
  const rows = [['date', 'name', 'profile', 'event', 'message'], ...log.map(l => [new Date(l.sentAt).toISOString(), l.name, l.profileUrl, LAR.EVENT_LABELS[l.eventType], l.message])];
  const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  a.download = 'linkedin-autoreply-log.csv'; a.click();
});
$('clearFailed').addEventListener('click', async () => {
  const { queue = [] } = await LAR.storageGet('queue');
  await LAR.storageSet({ queue: queue.filter(q => q.status !== 'failed' && q.status !== 'skipped') });
  render();
});

// ---------- settings ----------
const FIELDS = ['dailyCap', 'recontactDays', 'delayMinSec', 'delayMaxSec', 'hoursStart', 'hoursEnd'];
const TPL = ['connection', 'connectionNoCompany', 'birthday', 'jobChange', 'jobChangeNoCompany'];
async function loadSettings() {
  const s = await LAR.getSettings();
  $('enabled').checked = s.enabled;
  $('mode').value = s.mode;
  for (const f of FIELDS) $(f).value = s[f];
  for (const t of TPL) $('t_' + t).value = s.templates[t];
}
$('saveSettings').addEventListener('click', async () => {
  const s = await LAR.getSettings();
  s.enabled = $('enabled').checked;
  s.mode = $('mode').value;
  for (const f of FIELDS) s[f] = Number($(f).value);
  s.dailyCap = Math.max(1, s.dailyCap || 25);
  s.delayMinSec = Math.max(30, s.delayMinSec || 45);
  s.delayMaxSec = Math.max(s.delayMinSec, s.delayMaxSec || 180);
  s.hoursStart = Math.min(23, Math.max(0, s.hoursStart));
  s.hoursEnd = Math.min(24, Math.max(s.hoursStart + 1, s.hoursEnd));
  for (const t of TPL) s.templates[t] = $('t_' + t).value.trim() || LAR.DEFAULT_SETTINGS.templates[t];
  await LAR.storageSet({ settings: s });
  $('savedMsg').textContent = 'Saved'; setTimeout(() => $('savedMsg').textContent = '', 2000);
  loadSettings(); render();
});

chrome.storage.onChanged.addListener(() => render());
loadSettings(); render();
