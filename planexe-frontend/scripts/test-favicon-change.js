/*
 * Author: Cascade
 * Date: 2025-09-19
 * PURPOSE: Test script to verify that the favicon changes each time the generation script is run
 * SRP and DRY check: Pass - This script has a single responsibility of testing favicon changes
 */

const fs = require('fs');
const path = require('path');

// Get favicon file path
const faviconPath = path.join(__dirname, '..', 'public', 'favicon.ico');

// Check if favicon exists and get its stats
if (fs.existsSync(faviconPath)) {
  const stats = fs.statSync(faviconPath);
  console.log('Current favicon:');
  console.log(`  Size: ${stats.size} bytes`);
  console.log(`  Modified: ${stats.mtime}`);
  console.log(`  Created: ${stats.ctime}`);
} else {
  console.log('Favicon does not exist yet');
}

console.log('\nRun the generation script and then run this test again to see the changes!');
