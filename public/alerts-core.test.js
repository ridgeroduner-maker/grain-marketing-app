// node public/alerts-core.test.js
const fs = require('fs');
const G = require('./alerts-core.js');
const { evaluate, freshRows, bdaysBetween } = G;
const rows = [{ commodity: 'corn', variant: 'Yellow corn', delivery: 'Current', location_id: 1, location: 'SD Central', bid_high: 3.75, unit: '$/Bu', report_date: '2026-10-26' },
              { commodity: 'corn', variant: 'Yellow corn', delivery: 'Current', location_id: 2, location: 'NE South', bid_high: 4.32, unit: '$/Bu', report_date: '2026-10-26' }];
const a = [{ id: '1', commodity: 'corn', variant: 'Yellow corn', locKey: 'any', dir: 'gte', price: 4.2, active: true },
           { id: '2', commodity: 'corn', variant: 'Yellow corn', locKey: '1', dir: 'gte', price: 4.2, active: true },
           { id: '3', commodity: 'corn', variant: 'Yellow corn', locKey: 'any', dir: 'gte', price: 4.2, active: true, lastFiredDate: '2026-10-26' }];
const f = evaluate(a, rows);
if (f.length !== 1 || f[0].row.location !== 'NE South') { console.error('FAIL', f); process.exit(1); }
console.log('alerts-core ok:', f[0].title, '|', f[0].body);

// Staleness filter shared by page + service worker: ONE rule. A bid is reliable at 0-1 business days old; at 2 the banner says "do not rely".
const mk = (d) => Object.assign({}, rows[1], { report_date: d });
const today = '2026-10-29';   // Thursday
if (G.MAX_RELIABLE_BDAYS !== 1 || G.DO_NOT_RELY_BDAYS !== 2 || G.MAX_ALERT_AGE_BDAYS !== G.MAX_RELIABLE_BDAYS) { console.error('FAIL constants'); process.exit(1); }
const kept = freshRows([mk('2026-10-29'), mk('2026-10-28'), mk('2026-10-27'), mk('2026-10-26'), mk('2026-10-23')], G.MAX_ALERT_AGE_BDAYS, today).map(r => r.report_date);
if (JSON.stringify(kept) !== JSON.stringify(['2026-10-29', '2026-10-28'])) { console.error('FAIL freshRows', kept); process.exit(1); }   // the 2-business-day-old 10/27 bid is NOT kept

// A matching bid that is 2 business days old (banner: "Do not rely") must not fire; the same bid 1 day old does.
const alertOn = [{ id: 'x', commodity: 'corn', variant: 'Yellow corn', locKey: 'any', dir: 'gte', price: 4.2, active: true }];
const fire = (reportDate) => evaluate(alertOn, freshRows([mk(reportDate)], G.MAX_ALERT_AGE_BDAYS, today)).length;
if (fire('2026-10-27') !== 0 || fire('2026-10-26') !== 0) { console.error('FAIL alert fired on a bid the banner says not to rely on'); process.exit(1); }
if (fire('2026-10-28') !== 1 || fire('2026-10-29') !== 1) { console.error('FAIL alert did not fire on a reliable bid'); process.exit(1); }
// Weekend: Friday's bid on Monday is 1 business day old -> still reliable; Thursday's is 2 -> not.
if (freshRows([mk('2026-10-23')], 1, '2026-10-26').length !== 1 || freshRows([mk('2026-10-22')], 1, '2026-10-26').length !== 0) { console.error('FAIL weekend rule'); process.exit(1); }

// The page and the service worker must read the shared constants, never their own literal numbers.
const app = fs.readFileSync(__dirname + '/app.js', 'utf8'), sw = fs.readFileSync(__dirname + '/sw.js', 'utf8');
for (const [name, src] of [['app.js', app], ['sw.js', sw]]) {
  if (!/GrainAlerts\.MAX_ALERT_AGE_BDAYS|GrainAlerts\.MAX_RELIABLE_BDAYS/.test(src)) { console.error('FAIL ' + name + ' does not use the shared age constant'); process.exit(1); }
}
if (/freshRows\([^)]*,\s*\d+\s*[,)]/.test(app + sw)) { console.error('FAIL a hard-coded age in freshRows()'); process.exit(1); }
if (/r\.bage\s*(<=|>)\s*\d/.test(app) || /\.filter\(x => x\.b >= \d/.test(app) || /ageB >= \d/.test(app)) { console.error('FAIL app.js hard-codes the stale threshold'); process.exit(1); }
if (!/GrainAlerts\.freshRows\(latest, GrainAlerts\.MAX_ALERT_AGE_BDAYS\)/.test(sw)) { console.error('FAIL sw.js alert filter'); process.exit(1); }
if (!/r\.bage <= GrainAlerts\.MAX_RELIABLE_BDAYS/.test(app) || !/GrainAlerts\.DO_NOT_RELY_BDAYS/.test(app)) { console.error('FAIL app.js ranking/banner rule'); process.exit(1); }
if (bdaysBetween('2026-10-23', '2026-10-26') !== 1 || bdaysBetween('2026-10-26', '2026-10-26') !== 0) { console.error('FAIL bdays'); process.exit(1); }
if (!/call your elevator/.test(f[0].body)) { console.error('FAIL body note'); process.exit(1); }
console.log('freshRows ok');

// Hard 7-day limit in the browser (audit F-02): report date more than STALE_EXPIRE_DAYS CALENDAR days before today (Central) is hidden.
if (G.STALE_EXPIRE_DAYS !== 7) { console.error('FAIL STALE_EXPIRE_DAYS must match ingest/config.py (7)'); process.exit(1); }
const cfgPy = fs.readFileSync(__dirname + '/../ingest/config.py', 'utf8');
if (!new RegExp('STALE_EXPIRE_DAYS = ' + G.STALE_EXPIRE_DAYS + '\\b').test(cfgPy)) { console.error('FAIL browser and export stale limits differ'); process.exit(1); }
if (G.calendarDaysBetween('2026-10-30', '2026-11-10') !== 11 || G.calendarDaysBetween('2026-11-01', '2026-11-02') !== 1   // across the Nov 1 DST change
    || G.calendarDaysBetween('2026-11-10', '2026-11-09') !== -1) { console.error('FAIL calendarDaysBetween'); process.exit(1); }
{
  const sp = G.splitExpired([mk('2026-11-17'), mk('2026-11-16'), mk('2026-11-24'), mk('2026-10-30'), Object.assign({}, rows[0], { report_date: null })], 7, '2026-11-24');
  const k = sp.kept.map(r => r.report_date), h = sp.hidden.map(r => r.report_date);
  if (JSON.stringify(k) !== JSON.stringify(['2026-11-17', '2026-11-24']) || JSON.stringify(h) !== JSON.stringify(['2026-11-16', '2026-10-30', null])) {
    console.error('FAIL splitExpired: exactly 7 days old is kept, 8+ or no date is hidden', k, h); process.exit(1);
  }
  if (G.splitExpired([mk('2026-11-16')], undefined, '2026-11-24').hidden.length !== 1) { console.error('FAIL splitExpired default limit'); process.exit(1); }
  if (G.splitExpired([], 7, '2026-11-24').kept.length !== 0) { console.error('FAIL splitExpired empty'); process.exit(1); }
}
// app.js must route every load of latest.json through the filter, use Central "today", and show the stale notice.
if ((app.match(/loadJSON\('latest\.json'\)/g) || []).length !== (app.match(/setLatest\(/g) || []).length - 1) { console.error('FAIL every latest.json load must go through setLatest()'); process.exit(1); }
if (!/GrainAlerts\.splitExpired\(rows, expireDays\(\), today\)/.test(app) || !/const today = chicagoToday\(\)/.test(app)) { console.error('FAIL app.js hide rule'); process.exit(1); }
if (!/Data is stale\./.test(app) || !/state\.meta\.stale_expire_days/.test(app)) { console.error('FAIL app.js stale notice'); process.exit(1); }
console.log('splitExpired ok');
