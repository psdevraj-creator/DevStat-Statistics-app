// DevStat offline licence gate — Option A: occasional phone-home with offline grace.
//
// The analysis engine runs 100% locally. This module only handles the £25/yr
// licence: it talks to the hosted backend for licence status and caches a signed
// token locally so the app keeps working offline between checks. It cannot be
// perfectly enforced (a fully offline program can always be run) — this makes
// paying the only sensible path and lets a lapsed subscription be re-locked.
const fs = require('fs');
const path = require('path');
const os = require('os');

const LICENCE_FILE = path.join(os.homedir(), '.devstat', 'licence.json');
const FREE_TRIAL = 3; // local free analyses before a licence is required
const CHECK_EVERY_MS = 30 * 24 * 60 * 60 * 1000; // 30 days (roughly monthly phone-home)
const BACKEND = process.env.DEVSTAT_API_URL ||
  'https://devstat-statistics-app-991466352708.europe-west1.run.app';

function load() {
  try { return JSON.parse(fs.readFileSync(LICENCE_FILE, 'utf8')); } catch { return null; }
}

function save(data) {
  try {
    fs.mkdirSync(path.dirname(LICENCE_FILE), { recursive: true });
    fs.writeFileSync(LICENCE_FILE, JSON.stringify(data));
  } catch {}
}

// Is the cached licence trusted right now? (not past licensed_until)
function cachedValid(c) {
  if (!c || !c.licensed || !c.licensed_until) return false;
  return new Date(c.licensed_until).getTime() > Date.now();
}

// Online check: refresh licence status from the hosted backend (uses the cached
// session token). Falls back to the cache when offline.
async function checkOnline() {
  const c = load() || {};
  try {
    const token = c.sessionToken || '';
    const res = await fetch(BACKEND + '/api/license/status', {
      headers: token ? { Authorization: 'Bearer ' + token } : {},
    });
    if (res.ok) {
      const j = await res.json();
      c.licensed = !!j.licensed;
      c.plan = j.plan || 'free';
      if (j.licensed_until) c.licensed_until = j.licensed_until;
      c.lastCheck = Date.now();
      save(c);
    }
  } catch {
    // offline: keep using cache
  }
  return c;
}

// Decide what the app can do right now.
function gate(c) {
  const licensed = cachedValid(c);
  const used = (c.usageCount || 0);
  const trialLeft = Math.max(0, FREE_TRIAL - used);
  return {
    licensed,
    plan: licensed ? 'pro' : 'free',
    licensed_until: c.licensed_until || null,
    trialLeft,
    requiresSubscription: !licensed && trialLeft === 0,
    needsCheckIn: !c.licensed_until || (Date.now() - (c.lastCheck || 0) > CHECK_EVERY_MS),
  };
}

module.exports = { load, save, cachedValid, checkOnline, gate, FREE_TRIAL, BACKEND, LICENCE_FILE };
