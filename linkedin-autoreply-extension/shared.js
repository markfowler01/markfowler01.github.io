// Shared helpers used by background.js, content.js and app.js.
// Loaded via importScripts (background), content_scripts list, and <script> (app).

const LAR = (() => {
  const TZ = 'America/Los_Angeles';

  const DEFAULT_SETTINGS = {
    mode: 'approval',            // 'approval' | 'auto'
    enabled: true,
    dailyCap: 25,
    delayMinSec: 45,
    delayMaxSec: 180,
    hoursStart: 8,               // 8am Pacific
    hoursEnd: 18,                // 6pm Pacific
    recontactDays: 30,
    templates: {
      connection: 'Appreciate the connect, {first_name}! What does your role at {company} look like day to day?',
      connectionNoCompany: 'Appreciate the connect, {first_name}! What does your day to day look like at work?',
      birthday: 'Happy birthday {first_name}! Hope you get some time away from work to enjoy it.',
      jobChange: 'Saw the news about {company}, congrats {first_name}! What are you most excited about in the new role?',
      jobChangeNoCompany: 'Saw the news, congrats {first_name}! What are you most excited about in the new role?'
    }
  };

  const EVENT_LABELS = { connection: 'New connection', birthday: 'Birthday', jobChange: 'Job change' };

  function storageGet(keys) {
    return new Promise(res => chrome.storage.local.get(keys, res));
  }
  function storageSet(obj) {
    return new Promise(res => chrome.storage.local.set(obj, res));
  }

  async function getSettings() {
    const { settings } = await storageGet('settings');
    const merged = Object.assign({}, DEFAULT_SETTINGS, settings || {});
    merged.templates = Object.assign({}, DEFAULT_SETTINGS.templates, (settings && settings.templates) || {});
    return merged;
  }

  // Parts of "now" in Pacific time.
  function pacificParts(date = new Date()) {
    const fmt = new Intl.DateTimeFormat('en-US', {
      timeZone: TZ, hourCycle: 'h23',
      year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
    });
    const p = {};
    for (const part of fmt.formatToParts(date)) p[part.type] = part.value;
    return {
      dateKey: `${p.year}-${p.month}-${p.day}`,
      hour: Number(p.hour),
      minute: Number(p.minute),
      year: Number(p.year)
    };
  }

  function isBusinessHours(settings, date = new Date()) {
    const { hour, minute } = pacificParts(date);
    const now = hour + minute / 60;
    return now >= settings.hoursStart && now < settings.hoursEnd;
  }

  function fillTemplate(tpl, vars) {
    return tpl
      .replace(/\{first_name\}/g, vars.firstName || 'there')
      .replace(/\{company\}/g, vars.company || '')
      .replace(/\{new_title\}/g, vars.newTitle || 'your new role')
      .replace(/\s{2,}/g, ' ')
      .trim();
  }

  function buildMessage(settings, person) {
    const t = settings.templates;
    const hasCompany = !!(person.company && person.company.trim());
    let tpl;
    if (person.eventType === 'connection') tpl = hasCompany ? t.connection : t.connectionNoCompany;
    else if (person.eventType === 'birthday') tpl = t.birthday;
    else tpl = hasCompany ? t.jobChange : t.jobChangeNoCompany;
    return fillTemplate(tpl, person);
  }

  // One key per person per event. Birthdays repeat yearly, so the year is part of the key.
  function eventKey(person, year) {
    const y = person.eventType === 'birthday' ? `:${year || pacificParts().year}` : '';
    return `${person.eventType}:${person.profileUrl}${y}`;
  }

  function normalizeProfileUrl(href) {
    try {
      const u = new URL(href, 'https://www.linkedin.com');
      const m = u.pathname.match(/^\/in\/([^/]+)\/?/);
      if (!m) return null;
      return `https://www.linkedin.com/in/${m[1]}/`;
    } catch (e) { return null; }
  }

  function firstNameOf(fullName) {
    if (!fullName) return '';
    const cleaned = fullName.replace(/\(.*?\)/g, '').replace(/[,|•].*$/, '').trim();
    const first = cleaned.split(/\s+/)[0] || '';
    return first.replace(/[^A-Za-zÀ-ÿ'\-]/g, '');
  }

  function randomDelayMs(settings) {
    const min = Math.max(30, Number(settings.delayMinSec) || 45);
    const max = Math.max(min, Number(settings.delayMaxSec) || 180);
    return Math.floor((min + Math.random() * (max - min)) * 1000);
  }

  return {
    TZ, DEFAULT_SETTINGS, EVENT_LABELS,
    storageGet, storageSet, getSettings, pacificParts, isBusinessHours,
    fillTemplate, buildMessage, eventKey, normalizeProfileUrl, firstNameOf, randomDelayMs
  };
})();

if (typeof self !== 'undefined') self.LAR = LAR;
