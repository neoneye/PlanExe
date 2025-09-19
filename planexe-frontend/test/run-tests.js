/**
 * Author: Cascade
 * Date: 2025-09-19T17:40:43-04:00
 * PURPOSE: Simple test runner for PlanExe NextJS frontend integration tests
 * SRP and DRY check: Pass - Single responsibility for test orchestration, validates complete system
 */

const { spawn } = require('child_process');
const path = require('path');

// Test configuration
const TESTS = [
  {
    name: 'Luigi Pipeline Integration',
    script: './integration/luigi-pipeline-test.js',
    timeout: 600000, // 10 minutes
    critical: true
  }
];

// Colors for console output
const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m'
};

function colorize(text, color) {
  return `${colors[color]}${text}${colors.reset}`;
}

// Check if NextJS server is running
async function checkServer(url = 'http://localhost:3000') {
  try {
    const response = await fetch(`${url}/api/health`);
    return response.ok;
  } catch {
    return false;
  }
}

// Run a single test
function runTest(test) {
  return new Promise((resolve) => {
    console.log(colorize(`\n🧪 Running: ${test.name}`, 'blue'));
    console.log(colorize('-'.repeat(50), 'cyan'));

    const testProcess = spawn('node', [test.script], {
      cwd: __dirname,
      stdio: 'inherit'
    });

    const timer = setTimeout(() => {
      testProcess.kill();
      console.log(colorize(`❌ Test timeout: ${test.name}`, 'red'));
      resolve({ success: false, timeout: true });
    }, test.timeout);

    testProcess.on('close', (code) => {
      clearTimeout(timer);
      const success = code === 0;
      
      if (success) {
        console.log(colorize(`✅ Passed: ${test.name}`, 'green'));
      } else {
        console.log(colorize(`❌ Failed: ${test.name} (exit code: ${code})`, 'red'));
      }

      resolve({ success, exitCode: code });
    });

    testProcess.on('error', (error) => {
      clearTimeout(timer);
      console.log(colorize(`❌ Error running ${test.name}: ${error.message}`, 'red'));
      resolve({ success: false, error: error.message });
    });
  });
}

// Main test runner
async function runAllTests() {
  console.log(colorize('🚀 PlanExe Integration Test Suite', 'cyan'));
  console.log(colorize('=' .repeat(50), 'cyan'));

  // Check if server is running
  console.log('🔍 Checking if NextJS server is running...');
  const serverRunning = await checkServer();
  
  if (!serverRunning) {
    console.log(colorize('❌ NextJS server not running at http://localhost:3000', 'red'));
    console.log(colorize('   Please start the server with: npm run dev', 'yellow'));
    process.exit(1);
  }

  console.log(colorize('✅ NextJS server is running', 'green'));

  const results = {
    total: TESTS.length,
    passed: 0,
    failed: 0,
    skipped: 0
  };

  // Run each test
  for (const test of TESTS) {
    const result = await runTest(test);
    
    if (result.success) {
      results.passed++;
    } else {
      results.failed++;
      
      if (test.critical) {
        console.log(colorize('\n💥 Critical test failed! Stopping test suite.', 'red'));
        break;
      }
    }
  }

  // Print summary
  console.log(colorize('\n' + '=' .repeat(50), 'cyan'));
  console.log(colorize('📊 Test Results Summary', 'cyan'));
  console.log(`   Total Tests: ${results.total}`);
  console.log(colorize(`   Passed: ${results.passed}`, 'green'));
  
  if (results.failed > 0) {
    console.log(colorize(`   Failed: ${results.failed}`, 'red'));
  }

  const allPassed = results.failed === 0 && results.passed === results.total;

  if (allPassed) {
    console.log(colorize('\n🎉 All tests passed! System is ready for deployment.', 'green'));
  } else {
    console.log(colorize('\n❌ Some tests failed. Please review and fix issues.', 'red'));
  }

  console.log(colorize('=' .repeat(50), 'cyan'));
  
  return allPassed;
}

// Export for programmatic use
module.exports = {
  runAllTests,
  checkServer,
  runTest
};

// Run if called directly
if (require.main === module) {
  runAllTests().then(success => {
    process.exit(success ? 0 : 1);
  }).catch(error => {
    console.error(colorize(`💥 Test runner error: ${error.message}`, 'red'));
    process.exit(1);
  });
}
