// node public/mapmode.test.js
const assert = require('assert');
const fs = require('fs'), path = require('path');
const { chooseMapMode, googleScriptUrl, usableKey } = require('./mapmode.js');
const KEY = 'AIzaSyA-1234567890abcdefghijklmnopqrstu';
// key set -> google, on any host
assert.deepStrictEqual(chooseMapMode({ GOOGLE_MAPS_API_KEY: KEY, TILE_URL: 'x', DEV_OSM_TILES_ON_LOCALHOST: true }, 'example.com'), { mode: 'google', key: KEY });
assert.strictEqual(chooseMapMode({ GOOGLE_MAPS_API_KEY: '  ' + KEY + ' ' }, 'localhost').mode, 'google');
// no key: OSM only on localhost AND only if the dev flag is on
assert.strictEqual(chooseMapMode({ GOOGLE_MAPS_API_KEY: '', TILE_URL: 'x', DEV_OSM_TILES_ON_LOCALHOST: true }, 'localhost').mode, 'osm-dev');
assert.strictEqual(chooseMapMode({ TILE_URL: 'x', DEV_OSM_TILES_ON_LOCALHOST: true }, '127.0.0.1').mode, 'osm-dev');
assert.strictEqual(chooseMapMode({ TILE_URL: 'x', DEV_OSM_TILES_ON_LOCALHOST: true }, 'grain.example.com').mode, 'blank');   // never OSM in public
assert.strictEqual(chooseMapMode({ TILE_URL: 'x', DEV_OSM_TILES_ON_LOCALHOST: false }, 'localhost').mode, 'blank');
assert.strictEqual(chooseMapMode({}, 'localhost').mode, 'blank');
assert.strictEqual(chooseMapMode(undefined, undefined).mode, 'blank');
// placeholders / junk never count as a key
for (const bad of ['', 'YOUR_GOOGLE_MAPS_API_KEY', 'your-key-here-please-replace', 'short', 'AIza has spaces in it and is long', null, undefined])
  assert.strictEqual(usableKey(bad), '', String(bad));
// script URL: Google's own host only, key url-encoded, async loading
const u = new URL(googleScriptUrl(KEY, 'cb'));
assert.strictEqual(u.origin, 'https://maps.googleapis.com'); assert.strictEqual(u.searchParams.get('key'), KEY); assert.strictEqual(u.searchParams.get('callback'), 'cb');
// the committed config never carries a key; the OSM URL is the single tile setting
const cfgSrc = fs.readFileSync(path.join(__dirname, 'config.js'), 'utf8');
assert(/GOOGLE_MAPS_API_KEY:\s*''/.test(cfgSrc), 'config.js must ship with an empty key');
assert(!/AIza[0-9A-Za-z_-]{20,}/.test(cfgSrc), 'no real key in config.js');
// Service worker must never intercept (cache) cross-origin responses such as Google's
const sw = fs.readFileSync(path.join(__dirname, 'sw.js'), 'utf8');
assert(/url\.origin !== location\.origin\) return/.test(sw), 'sw.js must ignore cross-origin requests');
console.log('mapmode ok');
