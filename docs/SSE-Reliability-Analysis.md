/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-26
 * PURPOSE: Detailed analysis of SSE reliability issues in PlanExe real-time communication
 * SRP and DRY check: Pass - Single responsibility for technical analysis documentation
 */

# SSE Reliability Issues Analysis

## 🚨 **Critical Problems Identified**

### **1. Global State Management Issues**
**Location**: `planexe_api/services/pipeline_execution_service.py:24`
```python
progress_streams: Dict[str, queue.Queue] = {}  # PROBLEM: Global mutable state
```

**Issues**:
- Global dictionary shared across all plan executions
- No thread-safe access to the dictionary itself (only queue contents are thread-safe)
- Memory leaks: old plan queues accumulate indefinitely
- Race conditions when multiple plans start/stop simultaneously

### **2. Race Condition in SSE Connection**
**Location**: `planexe_api/api.py:296-298`
```python
progress_queue = pipeline_service.get_progress_stream(plan_id)
if not progress_queue:
    yield {"event": "error", "data": json.dumps({"message": "Stream could not be established."})}
```

**Issue**: Pipeline execution and SSE connection are asynchronous
- Client connects to SSE before queue is created → "Stream could not be established"
- Frontend polls for readiness but timing is still unreliable

### **3. Inefficient Polling Architecture**
**Location**: `planexe_api/api.py:307`
```python
await asyncio.sleep(0.1)  # PROBLEM: Wasteful 100ms polling
```

**Issues**:
- Continuous 100ms polling even when no data available
- High CPU usage with multiple concurrent plans
- Unnecessary latency (up to 100ms delay for each message)

### **4. Poor Error Handling**
**Location**: `planexe_api/api.py:306`
```python
except:  # PROBLEM: Catches ALL exceptions, masks real errors
    await asyncio.sleep(0.1)
    continue
```

**Issues**:
- Catches all exceptions, not just `queue.Empty`
- Real errors (memory issues, corruption) are silently ignored
- No way to debug actual problems

### **5. Memory Leaks and Resource Management**
**Multiple Locations**:
- Queue creation: `pipeline_execution_service.py:46-47`
- Cleanup: `pipeline_execution_service.py:352-359`

**Issues**:
- If SSE client never connects, queue accumulates messages forever
- Cleanup only happens when client disconnects (unreliable)
- No timeout mechanism for abandoned streams
- Global `progress_streams` grows without bounds

### **6. No Connection Management**
**Problem**: System doesn't track active connections

**Missing Features**:
- No way to broadcast to multiple clients watching same plan
- No reconnection handling for dropped connections
- No client lifecycle management
- No graceful degradation when connections fail

### **7. Thread Safety Concerns**
**Location**: Multiple threads writing to queue
- `read_stdout()` thread: `pipeline_execution_service.py:187-218`
- `read_stderr()` thread: `pipeline_execution_service.py:221-241`
- Main execution thread: `pipeline_execution_service.py:334`

**Issues**:
- Multiple threads writing to same queue without coordination
- Global dictionary access isn't properly synchronized
- Potential for data corruption under high load

## 🔍 **Frontend Issues**

### **8. Unreliable Stream Readiness Polling**
**Location**: `Terminal.tsx:58-79`
```typescript
const checkStreamStatus = async () => {
  const response = await fetch(`/api/plans/${planId}/stream-status`);
  // Polls every 500ms but still has race conditions
};
```

**Issues**:
- 500ms polling interval still allows race conditions
- No exponential backoff for failed connections
- Polling continues even after stream is ready

### **9. No Reconnection Logic**
**Location**: `Terminal.tsx:85-128`
```typescript
const eventSource = new EventSource(`/api/plans/${planId}/stream`);
// No automatic reconnection on failure
```

**Issues**:
- When connection drops, no automatic reconnection
- Lost messages during disconnection periods
- User has to manually refresh to reconnect

### **10. Error Recovery Problems**
**Location**: `Terminal.tsx:117-123`
```typescript
eventSource.onerror = (err) => {
  eventSource.close();  // Permanently closes connection
};
```

**Issues**:
- Error permanently closes connection instead of retrying
- No distinction between temporary and permanent failures
- No fallback mechanism when SSE fails

## 📊 **Performance Impact**

### **Current Resource Usage**:
- **CPU**: Constant 100ms polling × number of active SSE connections
- **Memory**: Growing global queue dictionary that never fully cleans up
- **Network**: Unnecessary stream-status polling every 500ms per client
- **Latency**: Up to 100ms + 500ms = 600ms delay for progress updates

### **Scalability Issues**:
- 10 concurrent plans = 10 queues polling 10 times per second = 100 poll operations/sec
- Memory grows linearly with number of plans ever created
- No connection pooling or rate limiting

## 🎯 **Root Cause Analysis**

The fundamental architectural problem is **mixing synchronous subprocess communication with asynchronous web communication** using the wrong abstraction:

1. **Luigi subprocess** writes to stdout/stderr (synchronous, line-based)
2. **Python threads** read lines and put in queue (blocking → non-blocking conversion)
3. **SSE endpoint** polls queue asynchronously (non-blocking → streaming conversion)
4. **Frontend** connects via SSE (streaming consumption)

**The Problem**: Too many conversion layers with unreliable timing and resource cleanup.

## ✅ **Proposed WebSocket Solution**

### **Architecture Benefits**:
1. **Real-time bidirectional communication** instead of polling
2. **Connection lifecycle management** with automatic reconnection
3. **Pub/sub pattern** for multiple clients per plan
4. **Proper resource cleanup** with connection tracking
5. **Fallback mechanisms** when WebSocket fails

### **Implementation Strategy**:
1. Replace global queue dictionary with WebSocket connection manager
2. Use pub/sub pattern to broadcast to multiple clients
3. Add connection heartbeat and automatic reconnection
4. Implement fallback to REST polling if WebSocket unavailable
5. Add proper error categorization and recovery logic

This analysis forms the foundation for the WebSocket architecture design in Phase 1.2.