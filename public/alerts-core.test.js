// node public/alerts-core.test.js
const { evaluate } = require('./alerts-core.js');
const rows = [{ commodity: 'corn', variant: 'Yellow corn', delivery: 'Current', location_id: 1, location: 'SD Central', bid_high: 3.75, unit: '$/Bu', report_date: '2026-10-26' },
              { commodity: 'corn', variant: 'Yellow corn', delivery: 'Current', location_id: 2, location: 'NE South', bid_high: 4.32, unit: '$/Bu', report_date: '2026-10-26' }];
const a = [{ id: '1', commodity: 'corn', variant: 'Yellow corn', locKey: 'any', dir: 'gte', price: 4.2, active: true },
           { id: '2', commodity: 'corn', variant: 'Yellow corn', locKey: '1', dir: 'gte', price: 4.2, active: true },
           { id: '3', commodity: 'corn', variant: 'Yellow corn', locKey: 'any', dir: 'gte', price: 4.2, active: true, lastFiredDate: '2026-10-26' }];
const f = evaluate(a, rows);
if (f.length !== 1 || f[0].row.location !== 'NE South') { console.error('FAIL', f); process.exit(1); }
console.log('alerts-core ok:', f[0].title, '|', f[0].body);
