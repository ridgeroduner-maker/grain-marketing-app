// node public/mapmode.test.js
const assert = require('assert');
const fs = require('fs'), path = require('path');
const { chooseMapMode, safeUrl } = require('./mapmode.js');
const P = { MAP_TILES_URL: 'tiles/plains.pmtiles', MAP_TILES_ATTRIBUTION: 'attr', MAP_TILES_MAX_ZOOM: 10, PMTILES_DATA_MAX_ZOOM: 9 };
// pmtiles (default): any host, no key involved
let m = chooseMapMode(P, 'grain.example.com');
assert.deepStrictEqual(m, { mode: 'pmtiles', url: 'tiles/plains.pmtiles', attribution: 'attr', maxZoom: 10, dataMaxZoom: 9 });
assert.strictEqual(chooseMapMode({ ...P, MAP_TILES_URL: 'https://cdn.example.com/t/x.pmtiles?v=2' }, 'localhost').mode, 'pmtiles');
// raster XYZ with and without {key}
m = chooseMapMode({ MAP_TILES_URL: 'https://t.example.com/{z}/{x}/{y}.png?key={key}', MAP_TILES_KEY: ' ab c/d ' }, 'x.com');
assert.strictEqual(m.mode, 'xyz'); assert.strictEqual(m.url, 'https://t.example.com/{z}/{x}/{y}.png?key=ab%20c%2Fd');
assert.strictEqual(chooseMapMode({ MAP_TILES_URL: 'https://t.example.com/{z}/{x}/{y}.png?key={key}' }, 'x.com').why, 'nokey');
assert.strictEqual(chooseMapMode({ MAP_TILES_URL: 'https://t.example.com/{z}/{x}/{y}.png?key={key}', MAP_TILES_KEY: 'YOUR_KEY_HERE' }, 'x.com').mode, 'blank');
assert.strictEqual(chooseMapMode({ MAP_TILES_URL: 'https://t.example.com/{z}/{x}/{y}.png' }, 'x.com').mode, 'xyz');
// empty URL: OSM only on localhost AND only with the dev flag
assert.strictEqual(chooseMapMode({ MAP_TILES_URL: '', DEV_OSM_TILES_ON_LOCALHOST: true }, 'localhost').mode, 'osm-dev');
assert.strictEqual(chooseMapMode({ DEV_OSM_TILES_ON_LOCALHOST: true }, '127.0.0.1').mode, 'osm-dev');
assert.strictEqual(chooseMapMode({ DEV_OSM_TILES_ON_LOCALHOST: true }, 'grain.example.com').mode, 'blank');   // never OSM in public
assert.strictEqual(chooseMapMode({ DEV_OSM_TILES_ON_LOCALHOST: false }, 'localhost').mode, 'blank');
assert.strictEqual(chooseMapMode({}, 'localhost').mode, 'blank');
assert.strictEqual(chooseMapMode(undefined, undefined).mode, 'blank');
// unsafe / malformed URLs never become a tile source
for (const bad of ['javascript:alert(1)', 'data:text/plain,x', 'http://t.example.com/{z}/{x}/{y}.png', '//evil.example/x.pmtiles', 'ftp://x/y.pmtiles'])
  assert.strictEqual(safeUrl(bad), '', bad);
assert.strictEqual(chooseMapMode({ MAP_TILES_URL: 'https://t.example.com/tiles.png' }, 'x.com').mode, 'blank');      // https but no {z}/{x}/{y}
assert.strictEqual(chooseMapMode({ MAP_TILES_URL: 'javascript:1' }, 'localhost').mode, 'blank');
// the committed config: pmtiles default, no key, no Google, no http tile URL
const cfgSrc = fs.readFileSync(path.join(__dirname, 'config.js'), 'utf8');
assert(/MAP_TILES_URL:\s*'tiles\/plains\.pmtiles'/.test(cfgSrc), 'default tile source is the self-hosted pmtiles file');
assert(/MAP_TILES_KEY:\s*''/.test(cfgSrc), 'config.js must ship with an empty key');
assert(!/google/i.test(cfgSrc), 'no Google settings');
assert(/OpenStreetMap/.test(cfgSrc) && /Protomaps/.test(cfgSrc), 'default attribution names OSM contributors and Protomaps');
// Service worker must never intercept (cache) cross-origin responses nor the range-read tile archive
const sw = fs.readFileSync(path.join(__dirname, 'sw.js'), 'utf8');
assert(/url\.origin !== location\.origin\) return/.test(sw), 'sw.js must ignore cross-origin requests');
assert(/\.pmtiles/.test(sw) && /return;/.test(sw.split('.pmtiles')[1].slice(0, 120)), 'sw.js must not handle .pmtiles range reads');
assert(!/plains\.pmtiles/.test(sw.split('const SHELL')[1].split(']')[0]), 'the tile archive is not in the install-time shell cache');
console.log('mapmode ok');
