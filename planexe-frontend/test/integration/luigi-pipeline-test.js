/**
 * Author: Cascade
 * Date: 2025-09-19T17:40:43-04:00
 * PURPOSE: Integration test for Luigi pipeline through NextJS API to verify end-to-end functionality
 * SRP and DRY check: Pass - Single responsibility for integration testing, validates API -> Luigi workflow
 */

const fs = require('fs').promises;
const path = require('path');

// Test configuration
const TEST_CONFIG = {
  baseUrl: 'http://localhost:3000',
  testPlan: {
    prompt: 'Create a simple mobile app development plan for a todo list application with user authentication and cloud sync.',
    llmModel: 'ollama-llama3.2:3b', // Use local model for testing
    speedVsDetail: 'FAST_BUT_SKIP_DETAILS',
    title: 'Integration Test Plan'
  },
  timeout: 300000, // 5 minutes timeout
  pollInterval: 3000 // 3 seconds
};

// Helper function to make API requests
async function apiRequest(endpoint, options = {}) {
  const url = `${TEST_CONFIG.baseUrl}${endpoint}`;
  
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      ...options
    });

    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(`API Error: ${data.error?.message || 'Unknown error'}`);
    }

    return data;
  } catch (error) {
    console.error(`Request to ${endpoint} failed:`, error.message);
    throw error;
  }
}

// Test session creation
async function testSessionCreation() {
  console.log('🔄 Testing session creation...');
  
  try {
    const session = await apiRequest('/api/session', {
      method: 'POST',
      body: JSON.stringify({
        preferences: { testMode: true }
      })
    });

    if (session.success && session.sessionId) {
      console.log('✅ Session created successfully:', session.sessionId);
      return session.sessionId;
    } else {
      throw new Error('Session creation failed');
    }
  } catch (error) {
    console.error('❌ Session creation failed:', error.message);
    throw error;
  }
}

// Test configuration loading
async function testConfigurationLoading() {
  console.log('🔄 Testing configuration loading...');
  
  try {
    // Test LLM models
    const llmConfig = await apiRequest('/api/config/llms');
    if (llmConfig.success && llmConfig.models.length > 0) {
      console.log(`✅ LLM models loaded: ${llmConfig.models.length} models available`);
    } else {
      throw new Error('No LLM models available');
    }

    // Test prompt examples  
    const prompts = await apiRequest('/api/config/prompts');
    if (prompts.success && prompts.examples.length > 0) {
      console.log(`✅ Prompt examples loaded: ${prompts.examples.length} examples available`);
    } else {
      console.log('⚠️ No prompt examples available (non-critical)');
    }

    return { llmModels: llmConfig.models, promptExamples: prompts.examples };
  } catch (error) {
    console.error('❌ Configuration loading failed:', error.message);
    throw error;
  }
}

// Test plan creation and Luigi pipeline startup
async function testPlanCreation() {
  console.log('🔄 Testing plan creation and Luigi pipeline startup...');
  
  try {
    const plan = await apiRequest('/api/plans', {
      method: 'POST',
      body: JSON.stringify(TEST_CONFIG.testPlan)
    });

    if (plan.success && plan.planId) {
      console.log(`✅ Plan created successfully: ${plan.planId}`);
      console.log(`   Run ID: ${plan.runId}`);
      console.log(`   Run Directory: ${plan.runDir}`);
      console.log(`   Status: ${plan.status}`);
      console.log(`   Estimated Duration: ${plan.estimatedDuration} minutes`);
      
      return plan;
    } else {
      throw new Error('Plan creation failed');
    }
  } catch (error) {
    console.error('❌ Plan creation failed:', error.message);
    throw error;
  }
}

// Test progress monitoring
async function testProgressMonitoring(planId, timeoutMs = TEST_CONFIG.timeout) {
  console.log('🔄 Testing progress monitoring...');
  
  const startTime = Date.now();
  let lastProgress = -1;
  
  while (Date.now() - startTime < timeoutMs) {
    try {
      const progress = await apiRequest(`/api/plans/${planId}/progress`);
      
      if (progress.success) {
        const current = progress.progress.progressPercentage;
        
        if (current !== lastProgress) {
          console.log(`📊 Progress: ${current}% (${progress.progress.progressMessage})`);
          console.log(`   Phase: ${progress.progress.currentPhase}`);
          console.log(`   Files: ${progress.progress.filesCompleted}/${progress.progress.totalExpectedFiles}`);
          console.log(`   Status: ${progress.progress.status}`);
          lastProgress = current;
        }

        // Check if completed
        if (['completed', 'failed', 'stopped'].includes(progress.progress.status)) {
          const duration = Math.round(progress.progress.duration / 60);
          
          if (progress.progress.status === 'completed') {
            console.log(`✅ Pipeline completed successfully in ${duration} minutes`);
            return progress.progress;
          } else {
            console.log(`❌ Pipeline ended with status: ${progress.progress.status}`);
            console.log(`   Errors:`, progress.progress.errors);
            throw new Error(`Pipeline failed with status: ${progress.progress.status}`);
          }
        }
      }

      // Wait before next poll
      await new Promise(resolve => setTimeout(resolve, TEST_CONFIG.pollInterval));
      
    } catch (error) {
      console.error('❌ Progress monitoring error:', error.message);
      throw error;
    }
  }
  
  throw new Error('Pipeline timeout - did not complete within expected time');
}

// Test file operations
async function testFileOperations(planId) {
  console.log('🔄 Testing file operations...');
  
  try {
    // Test file listing
    const files = await apiRequest(`/api/plans/${planId}/files`);
    
    if (files.success && files.files) {
      const fileCount = files.files.files.length;
      console.log(`✅ Files listed successfully: ${fileCount} files found`);
      
      // Group by phase
      const phaseCount = Object.keys(files.files.phases).length;
      console.log(`   Phases with files: ${phaseCount}`);
      
      // Test individual file download (if files exist)
      if (fileCount > 0) {
        const firstFile = files.files.files[0];
        console.log(`🔄 Testing individual file download: ${firstFile.filename}`);
        
        const response = await fetch(`${TEST_CONFIG.baseUrl}/api/plans/${planId}/files/${firstFile.filename}`);
        
        if (response.ok) {
          const content = await response.text();
          console.log(`✅ File downloaded successfully: ${content.length} bytes`);
        } else {
          throw new Error(`File download failed: ${response.statusText}`);
        }
      }

      // Test ZIP download
      console.log('🔄 Testing ZIP archive download...');
      const zipResponse = await fetch(`${TEST_CONFIG.baseUrl}/api/plans/${planId}/download`);
      
      if (zipResponse.ok) {
        const zipBuffer = await zipResponse.arrayBuffer();
        console.log(`✅ ZIP download successful: ${zipBuffer.byteLength} bytes`);
      } else {
        throw new Error(`ZIP download failed: ${zipResponse.statusText}`);
      }
      
      return { fileCount, phaseCount };
    } else {
      throw new Error('File listing failed');
    }
  } catch (error) {
    console.error('❌ File operations failed:', error.message);
    throw error;
  }
}

// Main test runner
async function runIntegrationTest() {
  console.log('🚀 Starting Luigi Pipeline Integration Test');
  console.log('=' .repeat(50));
  
  const testResults = {
    sessionCreation: false,
    configurationLoading: false,
    planCreation: false,
    progressMonitoring: false,
    fileOperations: false,
    overallSuccess: false
  };

  try {
    // Test 1: Session Management
    const sessionId = await testSessionCreation();
    testResults.sessionCreation = true;
    
    // Test 2: Configuration Loading
    const config = await testConfigurationLoading();
    testResults.configurationLoading = true;
    
    // Test 3: Plan Creation & Luigi Pipeline
    const plan = await testPlanCreation();
    testResults.planCreation = true;
    
    // Test 4: Progress Monitoring
    console.log('⏱️ Monitoring pipeline execution...');
    const finalProgress = await testProgressMonitoring(plan.planId);
    testResults.progressMonitoring = true;
    
    // Test 5: File Operations
    const fileStats = await testFileOperations(plan.planId);
    testResults.fileOperations = true;
    
    // Success!
    testResults.overallSuccess = true;
    
    console.log('\n' + '=' .repeat(50));
    console.log('🎉 INTEGRATION TEST PASSED!');
    console.log('✅ All systems working correctly');
    console.log(`✅ Generated ${fileStats.fileCount} files across ${fileStats.phaseCount} phases`);
    console.log('✅ Luigi pipeline integration successful');
    
  } catch (error) {
    console.log('\n' + '=' .repeat(50));
    console.log('❌ INTEGRATION TEST FAILED');
    console.error('Error:', error.message);
    
    // Print test results summary
    console.log('\nTest Results:');
    Object.entries(testResults).forEach(([test, passed]) => {
      console.log(`  ${passed ? '✅' : '❌'} ${test}`);
    });
  }
  
  return testResults;
}

// Export for use in other test files
module.exports = {
  runIntegrationTest,
  apiRequest,
  TEST_CONFIG
};

// Run if called directly
if (require.main === module) {
  runIntegrationTest().then(results => {
    process.exit(results.overallSuccess ? 0 : 1);
  });
}
