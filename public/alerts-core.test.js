// node public/alerts-core.test.js
const { evaluate, freshRows, bdaysBetween } = require('./alerts-core.js');
const rows = [{ commodity: 'corn', variant: 'Yellow corn', delivery: 'Current', location_id: 1, location: 'SD Central', bid_high: 3.75, unit: '$/Bu', report_date: '2026-10-26' },
              { commodity: 'corn', variant: 'Yellow corn', delivery: 'Current', location_id: 2, location: 'NE South', bid_high: 4.32, unit: '$/Bu', report_date: '2026-10-26' }];
const a = [{ id: '1', commodity: 'corn', variant: 'Yellow corn', locKey: 'any', dir: 'gte', price: 4.2, active: true },
           { id: '2', commodity: 'corn', variant: 'Yellow corn', locKey: '1', dir: 'gte', price: 4.2, active: true },
           { id: '3', commodity: 'corn', variant: 'Yellow corn', locKey: 'any', dir: 'gte', price: 4.2, active: true, lastFiredDate: '2026-10-26' }];
const f = evaluate(a, rows);
if (f.length !== 1 || f[0].row.location !== 'NE South') { console.error('FAIL', f); process.exit(1); }
console.log('alerts-core ok:', f[0].title, '|', f[0].body);

// Staleness filter shared by page + service worker: rows older than 2 business days are skipped
const mk = (d) => Object.assign({}, rows[1], { report_date: d });
const today = '2026-10-29';   // Thursday
const kept = freshRows([mk('2026-10-29'), mk('2026-10-28'), mk('2026-10-27'), mk('2026-10-26'), mk('2026-10-23')], 2, today).map(r => r.report_date);
if (JSON.stringify(kept) !== JSON.stringify(['2026-10-29', '2026-10-28', '2026-10-27'])) { console.error('FAIL freshRows', kept); process.exit(1); }
if (bdaysBetween('2026-10-23', '2026-10-26') !== 1 || bdaysBetween('2026-10-26', '2026-10-26') !== 0) { console.error('FAIL bdays'); process.exit(1); }
if (!/call your elevator/.test(f[0].body)) { console.error('FAIL body note'); process.exit(1); }
console.log('freshRows ok');
