/**
 * Convert SVG icons to PNG using sharp
 *
 * Run with: node scripts/svg-to-png.js
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import sharp from 'sharp';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function convertSvgToPng() {

  const iconsDir = path.join(__dirname, '..', 'public', 'icons');
  const sizes = [16, 32, 48, 128];

  console.log('Converting SVG to PNG...');

  for (const size of sizes) {
    const svgPath = path.join(iconsDir, `icon-${size}.svg`);
    const pngPath = path.join(iconsDir, `icon-${size}.png`);

    if (!fs.existsSync(svgPath)) {
      console.log(`Skipping icon-${size}.svg (not found)`);
      continue;
    }

    try {
      await sharp(svgPath)
        .resize(size, size)
        .png()
        .toFile(pngPath);
      console.log(`Converted: icon-${size}.png`);
    } catch (err) {
      console.error(`Error converting icon-${size}.svg:`, err.message);
    }
  }

  console.log('\nPNG icons generated successfully!');
}

convertSvgToPng().catch(console.error);
