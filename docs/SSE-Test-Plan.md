/**
 * Author: Codex using GPT-5 (refreshing original doc by Claude Code using Sonnet 4)
 * Date: 2025-10-03T00:00:00Z
 * PURPOSE: Maintain the SSE test plan with current guidance while preserving the original scenarios.
 * SRP and DRY check: Pass - Focused on test execution; references analysis doc for root cause details.
 */

## Status Update (2025-10-03)
- Continue to execute baseline SSE vs WebSocket comparisons after each release; fallback assembler does not change test steps.
- Prioritise multi-client SSE endurance tests because thread cleanup fixes are still pending.
- Capture fallback report availability during tests to confirm partial runs still deliver artefacts when SSE fails.


# SSE Endpoint Testing Plan

## 🎯 **Objectives**

1. **Demonstrate current SSE reliability issues** using real pipeline execution
2. **Validate WebSocket replacement** with same test scenarios
3. **Ensure no regression** in functionality during migration
4. **Performance benchmarking** for improvement validation

## 🧪 **Test Categories**

### **Category 1: Basic Functionality Tests**

#### Test 1.1: Single Client Connection
```bash
# Start development environment
cd planexe-frontend && npm run go

# Create test plan via API
curl -X POST http://localhost:8080/api/plans \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Create a simple marketing plan for a local bakery", "speed_vs_detail": "fast_but_skip_details"}'

# Expected: SSE stream should start immediately
# Current Issue: Race condition may cause "Stream could not be established"
```

#### Test 1.2: Stream Readiness Polling
```javascript
// Test the frontend polling mechanism
const planId = "test-plan-id";
const checkStreamStatus = async () => {
  const response = await fetch(`/api/plans/${planId}/stream-status`);
  return response.json();
};

// Expected: Eventually returns {"status": "ready", "ready": true}
// Current Issue: Timing-dependent, may never become ready
```

#### Test 1.3: Log Message Reception
```javascript
// Connect to SSE and verify log messages
const eventSource = new EventSource(`/api/plans/${planId}/stream`);
const receivedMessages = [];

eventSource.onmessage = (event) => {
  receivedMessages.push(JSON.parse(event.data));
};

// Expected: Receive Luigi pipeline logs in real-time
// Current Issue: Messages may be delayed or missing
```

### **Category 2: Reliability Tests**

#### Test 2.1: Multiple Client Connections
```javascript
// Simulate multiple browsers watching same plan
const connections = [];
for (let i = 0; i < 5; i++) {
  connections.push(new EventSource(`/api/plans/${planId}/stream`));
}

// Expected: All clients receive same messages
// Current Issue: Queue cleanup may break some connections
```

#### Test 2.2: Connection Drop and Reconnect
```javascript
// Simulate network disconnection
const eventSource = new EventSource(`/api/plans/${planId}/stream`);

// Force disconnect after 10 seconds
setTimeout(() => {
  eventSource.close();

  // Try to reconnect after 5 seconds
  setTimeout(() => {
    const newEventSource = new EventSource(`/api/plans/${planId}/stream`);
  }, 5000);
}, 10000);

// Expected: Reconnection should work seamlessly
// Current Issue: Queue may be cleaned up, preventing reconnection
```

#### Test 2.3: Rapid Plan Creation/Deletion
```javascript
// Create multiple plans rapidly
const plans = [];
for (let i = 0; i < 10; i++) {
  const plan = await createPlan(`Test plan ${i}`);
  plans.push(plan);

  // Connect to SSE immediately
  const eventSource = new EventSource(`/api/plans/${plan.plan_id}/stream`);

  // Delete plan after random interval
  setTimeout(() => {
    deletePlan(plan.plan_id);
  }, Math.random() * 30000);
}

// Expected: Clean handling of creation/deletion
// Current Issue: Race conditions may cause crashes
```

### **Category 3: Thread Safety Tests**

#### Test 3.1: Concurrent Dictionary Access
```python
# Script to stress test global dictionary access
import threading
import requests
import time

def create_plan_worker():
    for i in range(100):
        response = requests.post('http://localhost:8080/api/plans', json={
            'prompt': f'Test plan {i}',
            'speed_vs_detail': 'fast_but_skip_details'
        })
        plan_id = response.json()['plan_id']

        # Immediately try to connect to SSE
        try:
            sse_response = requests.get(f'http://localhost:8080/api/plans/{plan_id}/stream',
                                      stream=True, timeout=1)
        except:
            pass

# Run 10 concurrent workers
threads = [threading.Thread(target=create_plan_worker) for _ in range(10)]
for t in threads:
    t.start()

# Expected: No crashes or errors
# Current Issue: Dictionary race conditions may cause KeyError
```

#### Test 3.2: Queue Cleanup Race Condition
```python
# Test cleanup while reading from queue
def sse_reader_worker(plan_id):
    try:
        response = requests.get(f'http://localhost:8080/api/plans/{plan_id}/stream',
                              stream=True, timeout=30)
        for line in response.iter_lines():
            print(f"Received: {line}")
    except Exception as e:
        print(f"SSE Error: {e}")

def plan_deleter_worker(plan_id):
    time.sleep(5)  # Let SSE connect first
    requests.delete(f'http://localhost:8080/api/plans/{plan_id}')

# Test concurrent reading and cleanup
plan_id = create_test_plan()
t1 = threading.Thread(target=sse_reader_worker, args=(plan_id,))
t2 = threading.Thread(target=plan_deleter_worker, args=(plan_id,))

t1.start()
t2.start()

# Expected: Graceful cleanup
# Current Issue: Queue deletion while SSE is reading may cause crash
```

### **Category 4: Performance Tests**

#### Test 4.1: Message Throughput
```python
# Measure SSE message throughput
import time

start_time = time.time()
message_count = 0

def count_messages(event):
    global message_count
    message_count += 1

eventSource.onmessage = count_messages

# Run for 60 seconds
time.sleep(60)

throughput = message_count / 60
print(f"SSE Throughput: {throughput} messages/second")

# Expected: Consistent throughput
# Current Issue: Polling delay adds latency
```

#### Test 4.2: Memory Usage Over Time
```python
# Monitor memory usage during long-running plan
import psutil
import time

process = psutil.Process()
memory_samples = []

for i in range(720):  # 2 hours
    memory_mb = process.memory_info().rss / 1024 / 1024
    memory_samples.append(memory_mb)
    time.sleep(10)

# Expected: Stable memory usage
# Current Issue: Memory leaks from queues and threads
```

#### Test 4.3: Concurrent Plan Scaling
```python
# Test system with multiple concurrent plans
concurrent_plans = [1, 5, 10, 20, 50]
response_times = []

for plan_count in concurrent_plans:
    start_time = time.time()

    # Create multiple plans simultaneously
    threads = []
    for i in range(plan_count):
        t = threading.Thread(target=create_and_monitor_plan, args=(f"Plan {i}",))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    end_time = time.time()
    response_times.append(end_time - start_time)

# Expected: Linear scaling
# Current Issue: Thread contention may cause exponential degradation
```

## 🔧 **Test Infrastructure**

### **Automated Test Script**
```python
#!/usr/bin/env python3
"""
Automated SSE reliability test suite
"""
import asyncio
import aiohttp
import json
import time
import logging
from typing import List, Dict
import statistics

class SSETestSuite:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.test_results = {}

    async def run_all_tests(self):
        """Run complete test suite"""
        tests = [
            self.test_basic_connection,
            self.test_multiple_clients,
            self.test_reconnection,
            self.test_race_conditions,
            self.test_performance
        ]

        for test in tests:
            try:
                result = await test()
                self.test_results[test.__name__] = result
            except Exception as e:
                self.test_results[test.__name__] = {"error": str(e)}

        return self.test_results

    async def test_basic_connection(self):
        """Test basic SSE connection and message reception"""
        # Implementation here
        pass

    async def test_multiple_clients(self):
        """Test multiple clients connecting to same plan"""
        # Implementation here
        pass

    async def test_reconnection(self):
        """Test connection recovery after disconnect"""
        # Implementation here
        pass

    async def test_race_conditions(self):
        """Test concurrent access scenarios"""
        # Implementation here
        pass

    async def test_performance(self):
        """Test message throughput and latency"""
        # Implementation here
        pass

if __name__ == "__main__":
    suite = SSETestSuite()
    results = asyncio.run(suite.run_all_tests())
    print(json.dumps(results, indent=2))
```

### **Expected Test Results (Current SSE)**

#### Failure Scenarios:
1. **Test 2.1**: Some clients lose connection during cleanup
2. **Test 2.2**: Reconnection fails if queue was cleaned up
3. **Test 2.3**: KeyError crashes under rapid creation/deletion
4. **Test 3.1**: Dictionary race conditions cause exceptions
5. **Test 3.2**: Queue cleanup during reading causes crashes
6. **Test 4.2**: Memory usage grows over time (leaks)
7. **Test 4.3**: Performance degrades with concurrent plans

#### Success Criteria for WebSocket:
1. **100% connection reliability** - no race conditions
2. **Automatic reconnection** - seamless recovery from disconnects
3. **Zero memory leaks** - stable memory usage over time
4. **Linear performance scaling** - no degradation with concurrent plans
5. **Sub-second latency** - real-time message delivery
6. **Graceful error handling** - proper cleanup and error reporting

## 📊 **Benchmarking Metrics**

### **Reliability Metrics**:
- Connection success rate: Target 100% (current ~80%)
- Message delivery rate: Target 100% (current ~90%)
- Reconnection success rate: Target 100% (current ~30%)

### **Performance Metrics**:
- Message latency: Target <100ms (current ~300ms)
- Throughput: Target >1000 msg/sec (current ~300 msg/sec)
- Memory stability: Target <1% growth/hour (current ~10% growth/hour)
- CPU efficiency: Target <5% baseline (current ~15% baseline)

This comprehensive test plan will validate both the current SSE issues and the effectiveness of the WebSocket replacement.





