#!/usr/bin/env node
/**
 * Bundle everything a client/printer needs into theapostrophe-logo-files.zip
 *   node tools/package.js
 */
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'theapostrophe-logo-files.zip');

// sharp has no zip support; use the system zip when present, else fall back to
// archiving with `tar` is not equivalent — so we build a STORE-only zip by hand.
function zipStore(files, out) {
  // Minimal ZIP writer (no compression) — good enough for SVG/PNG/PDF bundles
  const chunks = [];
  const central = [];
  let offset = 0;
  const crcTable = (() => {
    const t = new Int32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c;
    }
    return t;
  })();
  const crc32 = (buf) => {
    let c = -1;
    for (let i = 0; i < buf.length; i++) c = crcTable[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
    return (c ^ -1) >>> 0;
  };
  const dosTime = () => {
    const d = new Date();
    const time = ((d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1)) & 0xffff;
    const date = (((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate()) & 0xffff;
    return { time, date };
  };
  const { time, date } = dosTime();
  for (const entry of files) {
    const [f, name] = Array.isArray(entry) ? entry : [entry, entry];
    const data = fs.readFileSync(path.join(ROOT, f));
    const nameBuf = Buffer.from(name, 'utf8');
    const crc = crc32(data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0, 6);
    local.writeUInt16LE(0, 8);
    local.writeUInt16LE(time, 10);
    local.writeUInt16LE(date, 12);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(data.length, 18);
    local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    local.writeUInt16LE(0, 28);
    chunks.push(local, nameBuf, data);
    central.push({ nameBuf, crc, size: data.length, offset });
    offset += local.length + nameBuf.length + data.length;
  }
  const cdStart = offset;
  for (const e of central) {
    const h = Buffer.alloc(46);
    h.writeUInt32LE(0x02014b50, 0);
    h.writeUInt16LE(20, 4);
    h.writeUInt16LE(20, 6);
    h.writeUInt16LE(0, 8);
    h.writeUInt16LE(0, 10);
    h.writeUInt16LE(time, 12);
    h.writeUInt16LE(date, 14);
    h.writeUInt32LE(e.crc, 16);
    h.writeUInt32LE(e.size, 20);
    h.writeUInt32LE(e.size, 24);
    h.writeUInt16LE(e.nameBuf.length, 28);
    h.writeUInt32LE(0, 30);
    h.writeUInt16LE(0, 34);
    h.writeUInt16LE(0, 36);
    h.writeUInt32LE(0, 38);
    h.writeUInt32LE(e.offset, 42);
    chunks.push(h, e.nameBuf);
    offset += h.length + e.nameBuf.length;
  }
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(central.length, 8);
  end.writeUInt16LE(central.length, 10);
  end.writeUInt32LE(offset - cdStart, 12);
  end.writeUInt32LE(cdStart, 16);
  chunks.push(end);
  fs.writeFileSync(out, Buffer.concat(chunks));
  return files.length;
}

function walk(dir, base = dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(p, base));
    else out.push(path.relative(ROOT, p).split(path.sep).join('/'));
  }
  return out;
}

(async () => {
  const wanted = [];
  const add = (dir) => {
    if (fs.existsSync(path.join(ROOT, dir))) wanted.push(...walk(path.join(ROOT, dir)));
  };
  add('build/master'); add('build/print'); add('build/eps'); add('build/png');
  add('build/jpg'); add('build/icons'); add('build/social'); add('build/brand');
  wanted.push('README.md', 'LICENSE', 'src/fonts/OFL.txt');

  // drop the watermark scratch SVG and any job manifests
  // deliver a flat, client-friendly tree: strip the leading "build/"
  const files = wanted
    .filter((f) => !f.endsWith('jobs.json') && !f.includes('_watermark-white.svg'))
    .map((f) => [f, f.startsWith('build/') ? f.slice('build/'.length) : f]);
  const n = zipStore(files, OUT);
  const kb = (fs.statSync(OUT).size / 1024).toFixed(0);
  console.log(`packaged ${n} files → ${path.basename(OUT)} (${kb} KB)`);
})();
