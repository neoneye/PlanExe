/*
 * Author: Cascade
 * Date: 2025-09-19
 * PURPOSE: Generate a dynamic favicon with a 3x3 grid of random colors in a circular shape
 * This script creates a new favicon.ico file with random colors in a circular mask each time it runs
 * SRP and DRY check: Pass - This script has a single responsibility of generating a favicon
 */

const fs = require('fs');
const path = require('path');

// Try to use canvas for generating favicon
let useCanvas = true;
let createCanvas;

try {
  ({ createCanvas } = require('canvas'));
  console.log('Using canvas for favicon generation');
} catch (error) {
  console.log('Canvas not available, using SVG fallback');
  useCanvas = false;
}

/**
 * Generate a random hex color
 * @returns A random hex color string
 */
function getRandomColor() {
  // Generate a random number between 0 and 16777215 (0xFFFFFF)
  // Convert to hexadecimal and pad with zeros to ensure 6 digits
  return '#' + Math.floor(Math.random() * 16777215).toString(16).padStart(6, '0');
}

/**
 * Generate a favicon using canvas
 * @returns A buffer containing the favicon PNG data
 */
function generateFaviconWithCanvas() {
  // Create a canvas
  const canvas = createCanvas(32, 32);
  const ctx = canvas.getContext('2d');

  // Configuration constants
  const GRID_SIZE = 3;
  const squareSize = Math.floor(canvas.width / GRID_SIZE);
  const centerX = canvas.width / 2;
  const centerY = canvas.height / 2;
  const radius = Math.min(canvas.width, canvas.height) / 2 - 2; // Leave 2px margin

  // Draw white background
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Draw 3x3 grid of colored squares
  for (let row = 0; row < GRID_SIZE; row++) {
    for (let col = 0; col < GRID_SIZE; col++) {
      // Generate random color for each square
      const color = getRandomColor();
      ctx.fillStyle = color;

      // Draw square at calculated position
      ctx.fillRect(col * squareSize, row * squareSize, squareSize, squareSize);
    }
  }

  // Create circular mask by using composite operation
  ctx.globalCompositeOperation = 'destination-in';
  ctx.beginPath();
  ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
  ctx.fill();

  // Convert to PNG buffer
  return canvas.toBuffer('image/png');
}

/**
 * Generate a favicon as an SVG string (fallback)
 * @returns An SVG string representing the favicon
 */
function generateFaviconSVG() {
  // Configuration constants
  const GRID_SIZE = 3;
  const squareSize = 32 / GRID_SIZE;
  const centerX = 16;
  const centerY = 16;
  const radius = 14; // Leave 2px margin

  // Start SVG with clipping path definition
  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
    <defs>
      <clipPath id="circleClip">
        <circle cx="${centerX}" cy="${centerY}" r="${radius}"/>
      </clipPath>
    </defs>
    <rect width="32" height="32" fill="#FFFFFF"/>
    <g clip-path="url(#circleClip)">`;

  // Draw 3x3 grid of colored squares
  for (let row = 0; row < GRID_SIZE; row++) {
    for (let col = 0; col < GRID_SIZE; col++) {
      // Generate random color for each square
      const color = getRandomColor();

      // Draw square at calculated position
      svg += `<rect x="${col * squareSize}" y="${row * squareSize}" width="${squareSize}" height="${squareSize}" fill="${color}" />`;
    }
  }

  // End clipped group and SVG
  svg += `</g></svg>`;

  return svg;
}

// Generate favicon
let faviconData;
let isSVG = false;

if (useCanvas) {
  try {
    faviconData = generateFaviconWithCanvas();
    console.log('Favicon generated using canvas');
  } catch (error) {
    console.log('Canvas failed, falling back to SVG');
    faviconData = generateFaviconSVG();
    isSVG = true;
  }
} else {
  faviconData = generateFaviconSVG();
  isSVG = true;
}

// Save to public directory
const outputPath = path.join(__dirname, '..', 'public', isSVG ? 'favicon.svg' : 'favicon.ico');
fs.writeFileSync(outputPath, faviconData);

// Also create the other format for compatibility
if (isSVG) {
  // Create ICO as well for broader compatibility
  const icoPath = path.join(__dirname, '..', 'public', 'favicon.ico');
  fs.writeFileSync(icoPath, faviconData);
} else {
  // Create SVG as well for browsers that prefer it
  const svgPath = path.join(__dirname, '..', 'public', 'favicon.svg');
  const svgData = generateFaviconSVG();
  fs.writeFileSync(svgPath, svgData);
}

console.log('Dynamic favicon generated successfully!');
console.log(`Saved to: ${outputPath}`);
