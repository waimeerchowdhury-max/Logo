#!/usr/bin/env node
/**
 * Zero-dependency static server for the brand page (and the build folder).
 *   node tools/serve.js [port]
 * Binds 0.0.0.0 so the sandbox preview can reach it.
 */
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const PORT = Number(process.argv[2] || process.env.PORT || 4173);
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.json': 'application/json',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg', '.pdf': 'application/pdf', '.eps': 'application/postscript',
  '.zip': 'application/zip', '.woff2': 'font/woff2', '.ttf': 'font/ttf',
  '.txt': 'text/plain; charset=utf-8', '.md': 'text/markdown; charset=utf-8',
};

http.createServer((req, res) => {
  let p = decodeURIComponent((req.url || '/').split('?')[0]);
  if (p.endsWith('/')) p += 'index.html';
  const file = path.normalize(path.join(ROOT, p));
  if (!file.startsWith(ROOT)) { res.writeHead(403).end('forbidden'); return; }
  fs.stat(file, (err, st) => {
    if (err || !st.isFile()) { res.writeHead(404, { 'Content-Type': 'text/plain' }).end('not found'); return; }
    const type = TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream';
    const dl = /[?&]download/.test(req.url || '');
    res.writeHead(200, {
      'Content-Type': type,
      'Content-Length': st.size,
      'Cache-Control': 'no-cache',
      ...(dl ? { 'Content-Disposition': `attachment; filename="${path.basename(file)}"` } : {}),
    });
    fs.createReadStream(file).pipe(res);
  });
}).listen(PORT, '0.0.0.0', () => {
  console.log(`theapostrophe identity site → http://0.0.0.0:${PORT}/`);
});
