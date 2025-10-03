/**
 * Author: Codex using GPT-5 (refreshing original doc by Claude Code using Sonnet 4)
 * Date: 2025-10-03T00:00:00Z
 * PURPOSE: Keep the thread-safety analysis current and highlight open risks impacting SSE/WebSocket reliability.
 * SRP and DRY check: Pass - Focused on concurrency concerns; defers implementation specifics to code comments.
 */

## Status Update (2025-10-03)
- No locking changes merged yet; treat pipeline execution dictionaries as unsafe and avoid new concurrent writes.
- WebSocket manager remains the recommended pattern for guarded access; use it when adding new transports.
- Coordinate with the SSE test plan to validate that reconnect behaviour does not trigger cleanup races.


# Thread Safety Analysis - PlanExe Pipeline Execution

## 🧵 **Threading Architecture Overview**

The current system uses 4 types of threads per plan execution:

1. **Main HTTP Thread**: Creates plan, starts pipeline thread
2. **Pipeline Execution Thread**: Manages subprocess and monitoring threads
3. **Stdout Reader Thread**: Reads Luigi stdout, writes to queue
4. **Stderr Reader Thread**: Reads Luigi stderr, writes to queue

Plus: **SSE HTTP Threads** that read from queues (one per connected client)

## 🚨 **Critical Thread Safety Issues**

### **1. UNSAFE Global Dictionary Access**
**Location**: `pipeline_execution_service.py:24`
```python
running_processes: Dict[str, subprocess.Popen] = {}  # UNSAFE!
progress_streams: Dict[str, queue.Queue] = {}        # UNSAFE!
```

**The Problem**: Python dictionaries are NOT thread-safe for concurrent modifications.

**Unsafe Operations**:
```python
# Thread A (pipeline execution):
progress_streams[plan_id] = progress_queue          # Write

# Thread B (SSE endpoint):
return progress_streams.get(plan_id)                # Read

# Thread C (cleanup):
del progress_streams[plan_id]                       # Delete
```

**Race Condition Example**:
```python
# Thread A checks existence
if plan_id in progress_streams:                     # True
    # Thread B deletes entry here!
    del progress_streams[other_plan_id]             # Resizes dict
    # Thread A accesses - possible KeyError or corruption!
    queue = progress_streams[plan_id]               # CRASH!
```

### **2. Queue Cleanup Race Condition**
**Location**: `pipeline_execution_service.py:352-359`
```python
def cleanup_progress_stream(self, plan_id: str) -> None:
    if plan_id in progress_streams:                 # Check
        # Another thread could delete here!
        while not progress_streams[plan_id].empty(): # KeyError!
            try:
                progress_streams[plan_id].get_nowait()
            except queue.Empty:
                break
        del progress_streams[plan_id]               # Delete
```

**The Problem**: Time-of-check vs time-of-use (TOCTOU) bug
- Thread A checks `plan_id in progress_streams` → True
- Thread B deletes the entry
- Thread A tries to access `progress_streams[plan_id]` → KeyError!

### **3. Process Cleanup Race Condition**
**Location**: `pipeline_execution_service.py:341-342`
```python
def _cleanup_execution(self, plan_id: str) -> None:
    if plan_id in running_processes:               # Check
        # Another thread could delete here!
        del running_processes[plan_id]             # KeyError!
```

**Same TOCTOU problem** as queue cleanup.

### **4. Thread Resource Leaks**
**Location**: `pipeline_execution_service.py:254-255`
```python
stdout_thread.join(timeout=5.0)
stderr_thread.join(timeout=5.0)
```

**The Problem**: Timeout handling
- If threads don't complete in 5 seconds, they continue running as daemon threads
- Main thread proceeds to cleanup, but monitoring threads still have references
- Leads to resource leaks and potential corruption

### **5. Multiple Queue Writers (Actually OK)**
**Location**: Multiple threads write to same queue
```python
# stdout_thread:
progress_queue.put_nowait(log_data)               # Thread-safe ✅

# stderr_thread:
progress_queue.put_nowait(error_data)             # Thread-safe ✅

# main_thread:
progress_queue.put_nowait(None)                   # Thread-safe ✅
```

**Status**: This is actually SAFE because `queue.Queue.put_nowait()` is thread-safe.

### **6. Database Access Thread Safety**
**Location**: Multiple threads access same `DatabaseService`
```python
# Pipeline thread:
db_service.update_plan(plan_id, status_data)

# HTTP threads:
plan = db_service.get_plan(plan_id)
```

**Potential Issue**: SQLAlchemy session usage across threads
- If same session object shared across threads → corruption
- Each thread should have its own database session

## 🔧 **Concurrency Bugs in Practice**

### **Scenario 1: Rapid Plan Creation/Deletion**
```
Time 0: User creates Plan A
Time 1: HTTP Thread A starts pipeline execution
Time 2: User creates Plan B
Time 3: HTTP Thread B starts pipeline execution
Time 4: Plan A completes, cleanup starts
Time 5: SSE client connects for Plan B
Time 6: CRASH - Plan B queue deleted during Plan A cleanup
```

### **Scenario 2: Multiple SSE Clients**
```
Time 0: Plan starts, queue created
Time 1: Client 1 connects to SSE
Time 2: Client 2 connects to SSE
Time 3: Plan completes
Time 4: Client 1 disconnects, triggers cleanup
Time 5: Client 2 still active but queue deleted
Time 6: CRASH - Client 2 tries to read from deleted queue
```

### **Scenario 3: Slow Thread Cleanup**
```
Time 0: Plan starts, monitoring threads created
Time 1: Luigi subprocess completes
Time 2: Main thread waits 5 seconds for thread cleanup
Time 3: stdout_thread still processing large output buffer
Time 4: Main thread times out, deletes queue
Time 5: stdout_thread continues, tries to write to deleted queue
Time 6: CRASH or silent failure
```

## 📊 **Impact Analysis**

### **High Impact Issues**:
1. **Dictionary race conditions** → Data corruption, KeyError crashes
2. **Cleanup race conditions** → Resource leaks, double-cleanup crashes
3. **Thread timeout leaks** → Memory leaks, zombie threads

### **Medium Impact Issues**:
1. **Database session sharing** → Potential SQLAlchemy issues
2. **Process reference leaks** → File handle exhaustion

### **Performance Impact**:
- **CPU**: Zombie threads continue consuming cycles
- **Memory**: Leaked queues accumulate indefinitely
- **File Handles**: Unclosed subprocess pipes
- **Database**: Connection pool exhaustion from leaked sessions

## ✅ **Thread-Safe WebSocket Solution**

### **Architecture Changes**:

1. **Connection Manager with Locks**:
```python
class WebSocketManager:
    def __init__(self):
        self._connections: Dict[str, List[WebSocket]] = {}
        self._lock = threading.RLock()  # Reentrant lock

    def add_connection(self, plan_id: str, websocket: WebSocket):
        with self._lock:
            if plan_id not in self._connections:
                self._connections[plan_id] = []
            self._connections[plan_id].append(websocket)
```

2. **Atomic Operations**:
```python
def cleanup_plan(self, plan_id: str):
    with self._lock:
        connections = self._connections.pop(plan_id, [])
        for ws in connections:
            asyncio.create_task(ws.close())
```

3. **Publisher-Subscriber Pattern**:
```python
async def broadcast_message(self, plan_id: str, message: dict):
    with self._lock:
        connections = self._connections.get(plan_id, []).copy()

    # Send outside lock to prevent deadlock
    for ws in connections:
        try:
            await ws.send_json(message)
        except:
            # Handle disconnected clients
            self._remove_connection(plan_id, ws)
```

4. **Graceful Thread Shutdown**:
```python
def stop_monitoring_threads(self):
    # Signal threads to stop
    self._stop_event.set()

    # Wait for graceful shutdown
    for thread in self._monitoring_threads:
        thread.join(timeout=10.0)
        if thread.is_alive():
            # Force termination if needed
            thread._stop()
```

This thread-safe design eliminates all race conditions while maintaining high performance.




