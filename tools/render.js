#!/usr/bin/env node
/**
 * Rasterise SVG artwork with sharp (librsvg) at a controlled output size.
 *   node tools/render.js jobs.json
 * jobs.json: [{ svg, png, width?, height?, bg?, scale? }]
 * Density is derived from the SVG's intrinsic size so `width` is honoured
 * without ever asking librsvg for a gigantic intermediate bitmap.
 */
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

const MAX_PIXELS = 64 * 1024 * 1024;   // generous but safe

async function renderOne(job) {
  const svg = fs.readFileSync(job.svg);
  const meta = await sharp(svg).metadata();
  const svgW = meta.width || 1000;
  const svgH = meta.height || 1000;
  const targetW = job.width || svgW;
  let density = Math.max(72, Math.min(2400, (72 * targetW) / svgW));
  if ((svgW * density / 72) * (svgH * density / 72) > MAX_PIXELS) {
    density = Math.floor(72 * Math.sqrt(MAX_PIXELS / (svgW * svgH)));
  }
  let img = sharp(svg, { density });
  if (job.width || job.height) {
    img = img.resize({ width: job.width || null, height: job.height || null, fit: job.fit || 'inside' });
  }
  if (job.bg) img = img.flatten({ background: job.bg });
  fs.mkdirSync(path.dirname(job.png), { recursive: true });
  const info = await img.png({ compressionLevel: 9 }).toFile(job.png);
  return `${path.basename(job.png)} ${info.width}x${info.height}`;
}

async function run() {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  for (const j of jobs) process.stdout.write((await renderOne(j)) + '\n');
}
run().catch((e) => { console.error(e.message); process.exit(1); });
