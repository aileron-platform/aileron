/**
 * Generate Aileron logo icons for Chrome extension
 *
 * Run with: node scripts/generate-icons.js
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// SVG logo template - A modern "Aileron" icon
function generateSvgLogo(size) {
  const padding = size * 0.1;
  const innerSize = size - padding * 2;
  const centerX = size / 2;
  const centerY = size / 2;
  const radius = innerSize / 2;

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#6366f1;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#8b5cf6;stop-opacity:1" />
    </linearGradient>
    <linearGradient id="accentGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#22d3ee;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#06b6d4;stop-opacity:1" />
    </linearGradient>
  </defs>

  <!-- Background circle -->
  <circle cx="${centerX}" cy="${centerY}" r="${radius}" fill="url(#bgGradient)"/>

  <!-- AI symbol - stylized circuit/brain pattern -->
  <g fill="white" transform="translate(${padding}, ${padding})">
    <!-- Center node -->
    <circle cx="${innerSize/2}" cy="${innerSize/2}" r="${innerSize*0.08}" fill="url(#accentGradient)"/>

    <!-- Connection lines -->
    <line x1="${innerSize*0.25}" y1="${innerSize*0.25}" x2="${innerSize*0.5}" y2="${innerSize*0.5}" stroke="white" stroke-width="${size*0.02}" stroke-linecap="round" opacity="0.9"/>
    <line x1="${innerSize*0.75}" y1="${innerSize*0.25}" x2="${innerSize*0.5}" y2="${innerSize*0.5}" stroke="white" stroke-width="${size*0.02}" stroke-linecap="round" opacity="0.9"/>
    <line x1="${innerSize*0.25}" y1="${innerSize*0.75}" x2="${innerSize*0.5}" y2="${innerSize*0.5}" stroke="white" stroke-width="${size*0.02}" stroke-linecap="round" opacity="0.9"/>
    <line x1="${innerSize*0.75}" y1="${innerSize*0.75}" x2="${innerSize*0.5}" y2="${innerSize*0.5}" stroke="white" stroke-width="${size*0.02}" stroke-linecap="round" opacity="0.9"/>

    <!-- Corner nodes -->
    <circle cx="${innerSize*0.25}" cy="${innerSize*0.25}" r="${innerSize*0.06}" fill="white"/>
    <circle cx="${innerSize*0.75}" cy="${innerSize*0.25}" r="${innerSize*0.06}" fill="white"/>
    <circle cx="${innerSize*0.25}" cy="${innerSize*0.75}" r="${innerSize*0.06}" fill="white"/>
    <circle cx="${innerSize*0.75}" cy="${innerSize*0.75}" r="${innerSize*0.06}" fill="white"/>

    <!-- Side nodes -->
    <circle cx="${innerSize*0.5}" cy="${innerSize*0.15}" r="${innerSize*0.045}" fill="url(#accentGradient)"/>
    <circle cx="${innerSize*0.5}" cy="${innerSize*0.85}" r="${innerSize*0.045}" fill="url(#accentGradient)"/>
    <circle cx="${innerSize*0.15}" cy="${innerSize*0.5}" r="${innerSize*0.045}" fill="url(#accentGradient)"/>
    <circle cx="${innerSize*0.85}" cy="${innerSize*0.5}" r="${innerSize*0.045}" fill="url(#accentGradient)"/>

    <!-- Additional connection lines to side nodes -->
    <line x1="${innerSize*0.5}" y1="${innerSize*0.15}" x2="${innerSize*0.5}" y2="${innerSize*0.42}" stroke="white" stroke-width="${size*0.015}" stroke-linecap="round" opacity="0.7"/>
    <line x1="${innerSize*0.5}" y1="${innerSize*0.85}" x2="${innerSize*0.5}" y2="${innerSize*0.58}" stroke="white" stroke-width="${size*0.015}" stroke-linecap="round" opacity="0.7"/>
    <line x1="${innerSize*0.15}" y1="${innerSize*0.5}" x2="${innerSize*0.42}" y2="${innerSize*0.5}" stroke="white" stroke-width="${size*0.015}" stroke-linecap="round" opacity="0.7"/>
    <line x1="${innerSize*0.85}" y1="${innerSize*0.5}" x2="${innerSize*0.58}" y2="${innerSize*0.5}" stroke="white" stroke-width="${size*0.015}" stroke-linecap="round" opacity="0.7"/>
  </g>
</svg>`;
}

// Output directory
const iconsDir = path.join(__dirname, '..', 'public', 'icons');

// Ensure directory exists
if (!fs.existsSync(iconsDir)) {
  fs.mkdirSync(iconsDir, { recursive: true });
}

// Generate SVG files for each required size
const sizes = [16, 32, 48, 128];

console.log('Generating SVG icon files...');

sizes.forEach(size => {
  const svg = generateSvgLogo(size);
  const filename = path.join(iconsDir, `icon-${size}.svg`);
  fs.writeFileSync(filename, svg);
  console.log(`Generated: icon-${size}.svg`);
});

// Also generate a master SVG at 512px for high-res needs
const masterSvg = generateSvgLogo(512);
fs.writeFileSync(path.join(iconsDir, 'icon-master.svg'), masterSvg);
console.log('Generated: icon-master.svg');

console.log('\nSVG icons generated successfully!');
console.log('\nTo convert to PNG, you can use:');
console.log('- Online converter: https://convertio.co/svg-png/');
console.log('- Or install sharp: npm install sharp');
console.log('  Then run: node scripts/svg-to-png.js');
