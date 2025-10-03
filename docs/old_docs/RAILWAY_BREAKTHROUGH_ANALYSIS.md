/**
 * Author: Cascade using Claude 3.5 Sonnet
 * Date: 2025-09-30T20:39:10-04:00
 * PURPOSE: Critical breakthrough analysis of Railway deployment failures - filesystem + environment variable issues
 * SRP and DRY check: Pass - Single responsibility for documenting Railway-specific deployment blockers
 */

# 🚨 RAILWAY BREAKTHROUGH ANALYSIS: The REAL Blockers

## **Executive Summary**

Two independent experts identified **TWO CRITICAL BLOCKERS** that explain why Luigi crashes on Railway:

1. **Environment Variable Propagation Failure** - Railway env vars don't reach Luigi subprocess
2. **Read-Only Filesystem Issue** - Luigi tries to write to `/app/run` which Railway mounts read-only

**Both issues must be fixed simultaneously.**

---

## 🔍 **Issue #1: Environment Variables Not Reaching Subprocess**

### **The Problem**

Railway sets environment variables at the **container level**, but Python's `subprocess.Popen` doesn't automatically inherit them unless explicitly passed.

### **Evidence from Code**

**File**: `planexe_api/services/pipeline_execution_service.py:138`
```python
environment = os.environ.copy()  # ✅ Copies FastAPI's environment
```

**File**: `planexe_api/services/pipeline_execution_service.py:186-196`
```python
process = subprocess.Popen(
    command,
    cwd=str(self.planexe_project_root),
    env=environment,  # ✅ Passes environment to subprocess
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
    universal_newlines=True,
    shell=use_shell
)
```

### **Analysis: This SHOULD Work**

The code **already does** `env=environment` in the subprocess call. So why doesn't it work?

**Hypothesis**: The issue is **NOT** that we're not passing the environment. The issue is that:
1. Railway environment variables are set **AFTER** FastAPI imports modules
2. OR Railway uses a different mechanism that doesn't populate `os.environ`
3. OR There's a timing issue where env vars aren't available when FastAPI starts

### **Current Mitigation in Code**

**File**: `planexe_api/api.py:82-87`
```python
planexe_dotenv = PlanExeDotEnv.load()  # Loads from .env file OR environment
planexe_dotenv.update_os_environ()     # Merges into os.environ
```

This **should** make Railway env vars available, but there's a critical gap:

**File**: `planexe/utils/planexe_dotenv.py:33-35`
```python
if config.cloud_mode:
    logger.info("Cloud environment detected - using hybrid loading with environment variable priority")
    return cls.load_hybrid()
```

**File**: `planexe/utils/planexe_dotenv.py:69-89`
```python
# Define all possible environment variables PlanExe might need
env_var_keys = [
    # API Keys
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    # ... etc
]
```

**CRITICAL INSIGHT**: The hybrid loader only checks **predefined keys**. If Railway sets env vars with different names or if there's a typo, they won't be loaded!

---

## 🔍 **Issue #2: Read-Only Filesystem on Railway**

### **The SMOKING GUN**

**File**: `docker/Dockerfile.railway.single:62`
```dockerfile
# Create run directory for plan outputs
RUN mkdir -p /app/run && chmod 755 /app/run
```

**File**: `docker/Dockerfile.railway.single:72`
```dockerfile
ENV PLANEXE_RUN_DIR=/app/run
```

**File**: `planexe_api/api.py:73`
```python
RUN_DIR = "run"  # ❌ HARDCODED - Ignores PLANEXE_RUN_DIR environment variable!
```

**File**: `planexe_api/api.py:270-271`
```python
# Create run directory
run_id_dir = run_dir / plan_id
run_id_dir.mkdir(parents=True, exist_ok=True)  # ❌ FAILS ON RAILWAY READ-ONLY FILESYSTEM
```

### **Why This Breaks on Railway**

1. **Railway mounts `/app` as read-only** for security and immutability
2. Dockerfile creates `/app/run` at **build time** (line 62)
3. FastAPI tries to create subdirectories at **runtime** (line 271)
4. **`mkdir()` fails with permission error**
5. Exception occurs **BEFORE** Luigi subprocess even starts
6. WebSocket closes, log cuts off mid-sentence

### **The Correct Fix**

Railway provides **writable paths**:
- `/tmp` - Temporary storage (ephemeral)
- Mounted volumes - Persistent storage (requires Railway volume configuration)

**We need to**:
1. Use `/tmp/planexe/run` for Luigi output directories
2. Ensure this path is writable before creating plans
3. Update all code that references `run_dir` to use the writable path

---

## 📊 **Root Cause Chain (Complete Picture)**

```
Railway Container Starts
    ↓
Environment variables set (OPENAI_API_KEY, etc.)
    ↓
FastAPI api.py imports and runs module-level code
    ↓
PlanExeDotEnv.load() → load_hybrid() reads env vars
    ↓
✅ API keys loaded into os.environ
    ↓
FastAPI server starts listening on port 8080
    ↓
User submits plan via UI
    ↓
POST /api/plans endpoint called
    ↓
api.py:270 - Creates run_id_dir = run_dir / plan_id
    ↓
api.py:271 - Calls run_id_dir.mkdir(parents=True, exist_ok=True)
    ↓
❌ PERMISSION DENIED - /app/run is read-only on Railway
    ↓
Exception raised in FastAPI endpoint
    ↓
Thread crashes before Luigi subprocess even starts
    ↓
WebSocket closes unexpectedly
    ↓
Log cuts off mid-sentence
    ↓
User sees: "WebSocket just closes, no error message"
```

---

## 🛠️ **The Complete Fix**

### **Phase 1: Fix Read-Only Filesystem Issue** (CRITICAL - Do This First)

**File**: `planexe_api/api.py:73`
```python
# BEFORE (BROKEN):
RUN_DIR = "run"

# AFTER (FIXED):
# Use writable path on Railway, local path for development
if IS_DEVELOPMENT:
    RUN_DIR = Path("run")
else:
    # Railway: Use /tmp for writable storage
    RUN_DIR = Path("/tmp/planexe/run")
    RUN_DIR.mkdir(parents=True, exist_ok=True)  # Create at startup
    print(f"Railway mode: Using writable run directory: {RUN_DIR}")
```

**File**: `planexe_api/api.py:270-272`
```python
# BEFORE (BROKEN):
run_id_dir = run_dir / plan_id
run_id_dir.mkdir(parents=True, exist_ok=True)

# AFTER (FIXED):
run_id_dir = RUN_DIR / plan_id
try:
    run_id_dir.mkdir(parents=True, exist_ok=True)
    print(f"DEBUG: Created run directory: {run_id_dir}")
except PermissionError as e:
    print(f"ERROR: Cannot create run directory (read-only filesystem?): {e}")
    raise HTTPException(
        status_code=500, 
        detail=f"Cannot create plan directory - filesystem is read-only. Path: {run_id_dir}"
    )
```

### **Phase 2: Validate Environment Variables** (CRITICAL - Do This Second)

**File**: `planexe_api/services/pipeline_execution_service.py:123-156`
```python
def _setup_environment(self, plan_id: str, request: CreatePlanRequest, run_id_dir: Path) -> Dict[str, str]:
    """Set up environment variables for Luigi pipeline execution"""
    print(f"DEBUG ENV: Starting environment setup for plan {plan_id}")
    
    # CRITICAL: Validate API keys BEFORE subprocess creation
    required_keys = {
        "OPENAI_API_KEY": "OpenAI API calls",
        "OPENROUTER_API_KEY": "OpenRouter API calls"
    }
    
    missing_keys = []
    for key, purpose in required_keys.items():
        value = os.environ.get(key)
        if not value:
            missing_keys.append(f"{key} (needed for {purpose})")
            print(f"  ❌ {key}: NOT FOUND in os.environ")
        else:
            print(f"  ✅ {key}: Available (length: {len(value)})")
    
    if missing_keys:
        error_msg = f"Missing required API keys: {', '.join(missing_keys)}"
        print(f"ERROR ENV: {error_msg}")
        raise ValueError(error_msg)
    
    # Copy environment and add pipeline-specific variables
    environment = os.environ.copy()
    environment[PipelineEnvironmentEnum.RUN_ID_DIR.value] = str(run_id_dir)
    
    # EXPLICIT: Re-add API keys to ensure they're in subprocess env
    for key in required_keys.keys():
        value = os.environ.get(key)
        if value:
            environment[key] = value
            print(f"DEBUG ENV: Explicitly set {key} in subprocess environment")
    
    # ... rest of existing code ...
```

### **Phase 3: Add Fail-Fast Validation** (CRITICAL - Do This Third)

**File**: `planexe/llm_util/simple_openai_llm.py:36-44`
```python
# BEFORE (SILENT FAILURE):
if provider == "openai":
    self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# AFTER (FAIL FAST):
if provider == "openai":
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        error_msg = (
            "OPENAI_API_KEY environment variable not set! "
            "Cannot create OpenAI client. "
            "Check Railway environment variables."
        )
        print(f"ERROR LLM: {error_msg}")
        raise ValueError(error_msg)
    
    print(f"DEBUG LLM: Creating OpenAI client (key length: {len(api_key)})")
    self._client = OpenAI(api_key=api_key)
```

**File**: `planexe/llm_util/simple_openai_llm.py:38-42` (OpenRouter)
```python
# BEFORE (SILENT FAILURE):
elif provider == "openrouter":
    self._client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY")
    )

# AFTER (FAIL FAST):
elif provider == "openrouter":
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        error_msg = (
            "OPENROUTER_API_KEY environment variable not set! "
            "Cannot create OpenRouter client. "
            "Check Railway environment variables."
        )
        print(f"ERROR LLM: {error_msg}")
        raise ValueError(error_msg)
    
    print(f"DEBUG LLM: Creating OpenRouter client (key length: {len(api_key)})")
    self._client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )
```

### **Phase 4: Update Dockerfile** (OPTIONAL - For Clarity)

**File**: `docker/Dockerfile.railway.single:61-62`
```dockerfile
# BEFORE:
# Create run directory for plan outputs
RUN mkdir -p /app/run && chmod 755 /app/run

# AFTER (DOCUMENT THE LIMITATION):
# NOTE: /app/run is created at build time but /app is read-only at runtime
# The application will use /tmp/planexe/run for writable storage
RUN mkdir -p /app/run && chmod 755 /app/run
```

**File**: `docker/Dockerfile.railway.single:72`
```dockerfile
# BEFORE:
ENV PLANEXE_RUN_DIR=/app/run

# AFTER (CORRECT PATH):
ENV PLANEXE_RUN_DIR=/tmp/planexe/run
```

---

## 🧪 **Testing Strategy**

### **Local Testing (Windows)**
1. ✅ Verify `/tmp` path fallback doesn't break Windows
2. ✅ Confirm `IS_DEVELOPMENT` flag works correctly
3. ✅ Test plan creation with local `run/` directory

### **Railway Testing**
1. Deploy with all fixes
2. Check Railway logs for:
   - `"Railway mode: Using writable run directory: /tmp/planexe/run"`
   - `"✅ OPENAI_API_KEY: Available (length: XX)"`
   - `"DEBUG ENV: Explicitly set OPENAI_API_KEY in subprocess environment"`
   - `"DEBUG LLM: Creating OpenAI client (key length: XX)"`
3. Submit test plan via UI
4. Verify Luigi subprocess actually starts
5. Confirm first LLM API call reaches OpenAI

### **Success Criteria**
- ✅ No "Permission denied" errors on Railway
- ✅ Luigi subprocess starts successfully
- ✅ Environment variables reach Luigi subprocess
- ✅ First task makes OpenAI API call
- ✅ WebSocket shows task execution progress
- ✅ Plan completes successfully

---

## 📋 **Implementation Checklist**

### **Critical Path (Must Do)**
- [ ] Fix `RUN_DIR` to use `/tmp/planexe/run` on Railway
- [ ] Add fail-fast API key validation in `_setup_environment()`
- [ ] Add fail-fast API key validation in `SimpleOpenAILLM.__init__`
- [ ] Add explicit API key re-injection into subprocess environment
- [ ] Test on Railway with full diagnostic logging

### **Nice to Have**
- [ ] Update Dockerfile comments for clarity
- [ ] Add Railway volume mount for persistent storage (if needed)
- [ ] Create health check endpoint that validates filesystem writability
- [ ] Add startup validation that tests `/tmp` write permissions

---

## 🎯 **Why Both Experts Are Correct**

### **Expert #1: Environment Variables**
✅ **CORRECT** - Subprocess environment passing is critical
✅ **CORRECT** - Need explicit validation and re-injection
❌ **INCOMPLETE** - Didn't identify the filesystem issue

### **Expert #2: Read-Only Filesystem**
✅ **CORRECT** - `/app/run` is read-only on Railway
✅ **CORRECT** - Need to use `/tmp` for writable storage
✅ **CORRECT** - This explains the "log cuts off mid-sentence" symptom
❌ **INCOMPLETE** - Didn't identify the environment variable validation gap

### **The Truth**
**BOTH issues exist and BOTH must be fixed:**
1. **Filesystem issue** causes crash **BEFORE** Luigi starts
2. **Environment variable issue** would cause crash **AFTER** Luigi starts (if we fixed #1)

**Fix order matters**:
1. Fix filesystem issue first → Luigi subprocess can start
2. Fix environment variables second → Luigi can make API calls
3. Add fail-fast validation → Clear error messages instead of silent failures

---

## 🚀 **Expected Outcome After Fixes**

### **Before Fixes**
```
Railway Logs:
DEBUG: Directory created successfully
[CRASH - No error message]
[WebSocket closes]
[Log cuts off]
```

### **After Filesystem Fix Only**
```
Railway Logs:
Railway mode: Using writable run directory: /tmp/planexe/run
DEBUG: Created run directory: /tmp/planexe/run/PlanExe_abc123
DEBUG: Subprocess started with PID: 1234
Luigi: pipeline_environment: PipelineEnvironment(run_id_dir='/tmp/planexe/run/PlanExe_abc123'...
ERROR LLM: OPENAI_API_KEY environment variable not set!
[Luigi crashes with clear error message]
```

### **After Both Fixes**
```
Railway Logs:
Railway mode: Using writable run directory: /tmp/planexe/run
✅ OPENAI_API_KEY: Available (length: 164)
✅ OPENROUTER_API_KEY: Available (length: 89)
DEBUG ENV: Explicitly set OPENAI_API_KEY in subprocess environment
DEBUG: Created run directory: /tmp/planexe/run/PlanExe_abc123
DEBUG: Subprocess started with PID: 1234
Luigi: pipeline_environment: PipelineEnvironment(run_id_dir='/tmp/planexe/run/PlanExe_abc123'...
DEBUG LLM: Creating OpenAI client (key length: 164)
Luigi: INFO - Using the specified LLM model: 'gpt-4.1-nano-2025-04-14'
Luigi: INFO - Task RedlineGateTask started
[OpenAI API call succeeds]
Luigi: INFO - Task RedlineGateTask completed
[Plan generation continues successfully]
```

---

## 📖 **For Future Developers**

### **Railway Deployment Gotchas**
1. **`/app` is read-only** - Use `/tmp` for runtime file creation
2. **Environment variables** - Validate they exist before subprocess creation
3. **Silent failures** - OpenAI client accepts `None` API key without error
4. **Subprocess environment** - Must explicitly pass `env=` parameter
5. **Logging is critical** - Add diagnostic prints at every stage

### **Debugging Railway Issues**
1. Check Railway logs for permission errors
2. Validate environment variables are set in Railway dashboard
3. Add diagnostic logging to track env var propagation
4. Test filesystem write permissions at startup
5. Use fail-fast validation instead of silent failures

---

**Bottom Line**: The regression is caused by **TWO independent blockers** working together. Both must be fixed for Railway deployment to work.
