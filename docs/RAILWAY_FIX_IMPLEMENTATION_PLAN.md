/**
 * Author: Cascade using Claude 3.5 Sonnet
 * Date: 2025-09-30T20:39:10-04:00
 * PURPOSE: Step-by-step implementation plan to fix Railway deployment blockers
 * SRP and DRY check: Pass - Single responsibility for Railway fix execution plan
 */

# 🔧 Railway Fix Implementation Plan

## **Quick Summary**

Two critical bugs prevent Railway deployment:
1. **Read-only filesystem** - FastAPI tries to create directories in `/app/run` (read-only)
2. **Environment variable validation** - No fail-fast checks for missing API keys

**Estimated time**: 2 hours total

---

## 📋 **Step-by-Step Implementation**

### **Step 1: Fix Read-Only Filesystem Issue** (30 minutes)

**Priority**: CRITICAL - This must be fixed first

**File**: `planexe_api/api.py`

**Location**: Around line 73

**Change**:
```python
# BEFORE:
RUN_DIR = "run"

# AFTER:
# Use writable path on Railway, local path for development
if IS_DEVELOPMENT:
    RUN_DIR = Path("run")
else:
    # Railway: Use /tmp for writable storage
    RUN_DIR = Path("/tmp/planexe/run")
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Railway mode: Using writable run directory: {RUN_DIR}")
```

**Location**: Around line 270-272

**Change**:
```python
# BEFORE:
run_id_dir = run_dir / plan_id
run_id_dir.mkdir(parents=True, exist_ok=True)

# AFTER:
run_id_dir = RUN_DIR / plan_id
try:
    run_id_dir.mkdir(parents=True, exist_ok=True)
    print(f"DEBUG: Created run directory: {run_id_dir}")
except PermissionError as e:
    print(f"ERROR: Cannot create run directory: {e}")
    raise HTTPException(
        status_code=500,
        detail=f"Cannot create plan directory - filesystem is read-only. Path: {run_id_dir}"
    )
```

**Test locally**:
```powershell
# Should still work with local run/ directory
cd planexe-frontend
npm run go
# Submit a test plan
```

---

### **Step 2: Add Environment Variable Validation** (30 minutes)

**Priority**: CRITICAL - Prevents silent failures

**File**: `planexe_api/services/pipeline_execution_service.py`

**Location**: Around line 123-156 (inside `_setup_environment` method)

**Add at the beginning of the method**:
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
    
    # Check API keys in current environment (existing code continues...)
    api_keys_to_check = ["OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]
    # ... rest of existing code ...
```

**Add before returning environment** (around line 153):
```python
    environment[PipelineEnvironmentEnum.LLM_MODEL.value] = request.llm_model
    
    # EXPLICIT: Re-add API keys to ensure they're in subprocess env
    for key in required_keys.keys():
        value = os.environ.get(key)
        if value:
            environment[key] = value
            print(f"DEBUG ENV: Explicitly set {key} in subprocess environment")
    
    print(f"DEBUG ENV: Pipeline environment configured with {len(environment)} variables")
    return environment
```

---

### **Step 3: Add Fail-Fast LLM Validation** (30 minutes)

**Priority**: CRITICAL - Clear error messages

**File**: `planexe/llm_util/simple_openai_llm.py`

**Location**: Around line 36-44 (inside `__init__` method)

**Change**:
```python
# BEFORE:
if provider == "openai":
    self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
elif provider == "openrouter":
    self._client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY")
    )

# AFTER:
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

---

### **Step 4: Update Dockerfile** (15 minutes)

**Priority**: OPTIONAL - For documentation clarity

**File**: `docker/Dockerfile.railway.single`

**Location**: Line 72

**Change**:
```dockerfile
# BEFORE:
ENV PLANEXE_RUN_DIR=/app/run

# AFTER:
ENV PLANEXE_RUN_DIR=/tmp/planexe/run
```

**Location**: Lines 61-62

**Add comment**:
```dockerfile
# NOTE: /app is read-only at runtime on Railway
# The application uses /tmp/planexe/run for writable storage (see api.py)
RUN mkdir -p /app/run && chmod 755 /app/run
```

---

### **Step 5: Test Locally** (15 minutes)

**Commands**:
```powershell
# Start development environment
cd d:\1Projects\PlanExe\planexe-frontend
npm run go

# In another terminal, test plan creation
curl -X POST http://localhost:8080/api/plans \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Test plan", "llm_model": "gpt-4.1-nano-2025-04-14", "speed_vs_detail": "fast_but_skip_details"}'
```

**Expected output**:
- ✅ Plan directory created in `run/PlanExe_xxx`
- ✅ No permission errors
- ✅ Luigi subprocess starts
- ✅ API keys validated successfully

---

### **Step 6: Commit and Deploy to Railway** (15 minutes)

**Commands**:
```powershell
cd d:\1Projects\PlanExe

# Stage all changes
git add planexe_api/api.py
git add planexe_api/services/pipeline_execution_service.py
git add planexe/llm_util/simple_openai_llm.py
git add docker/Dockerfile.railway.single
git add docs/RAILWAY_BREAKTHROUGH_ANALYSIS.md
git add docs/RAILWAY_FIX_IMPLEMENTATION_PLAN.md

# Commit with detailed message
git commit -m "Fix Railway deployment: writable filesystem + env var validation

CRITICAL FIXES:
1. Use /tmp/planexe/run for writable storage on Railway (fixes read-only /app)
2. Add fail-fast API key validation in pipeline_execution_service
3. Add fail-fast API key validation in SimpleOpenAILLM
4. Explicitly re-inject API keys into subprocess environment

ISSUE: Railway mounts /app as read-only, causing mkdir() to fail.
Luigi subprocess also wasn't getting environment variables reliably.

SOLUTION: 
- Detect Railway environment and use /tmp for runtime file creation
- Validate API keys exist before subprocess creation
- Explicitly pass API keys to subprocess environment
- Fail fast with clear error messages instead of silent failures

TESTING:
- Local: Verified run/ directory still works
- Railway: Will test after deployment

See docs/RAILWAY_BREAKTHROUGH_ANALYSIS.md for full analysis."

# Push to GitHub (triggers Railway deployment)
git push origin main
```

---

### **Step 7: Monitor Railway Deployment** (15 minutes)

**Railway Dashboard**:
1. Go to Railway project
2. Click on "Deployments" tab
3. Watch build logs for:
   - ✅ Docker build succeeds
   - ✅ Container starts
   - ✅ Health check passes

**Railway Logs** (after deployment):
1. Click on "Logs" tab
2. Look for startup messages:
   ```
   Railway mode: Using writable run directory: /tmp/planexe/run
   ✅ OPENAI_API_KEY: Available (length: 164)
   ✅ OPENROUTER_API_KEY: Available (length: 89)
   ```

**Test via UI**:
1. Open Railway deployment URL
2. Submit a test plan
3. Watch Railway logs for:
   ```
   DEBUG: Created run directory: /tmp/planexe/run/PlanExe_xxx
   DEBUG ENV: Explicitly set OPENAI_API_KEY in subprocess environment
   DEBUG: Subprocess started with PID: xxxx
   DEBUG LLM: Creating OpenAI client (key length: 164)
   Luigi: INFO - Using the specified LLM model: 'gpt-4.1-nano-2025-04-14'
   ```

---

## ✅ **Success Criteria**

### **Local Development**
- [x] No TypeScript errors
- [x] FastAPI starts successfully
- [x] Plan creation works
- [x] Files created in `run/` directory
- [x] Luigi subprocess starts
- [x] API calls reach OpenAI

### **Railway Deployment**
- [ ] Docker build succeeds
- [ ] Container starts without errors
- [ ] Health check passes
- [ ] Startup logs show writable directory path
- [ ] Startup logs show API keys available
- [ ] Plan creation succeeds
- [ ] Files created in `/tmp/planexe/run/`
- [ ] Luigi subprocess starts
- [ ] Environment variables reach subprocess
- [ ] API calls reach OpenAI
- [ ] First task completes successfully
- [ ] WebSocket shows progress updates
- [ ] Plan generation completes

---

## 🚨 **Troubleshooting**

### **If Local Testing Fails**

**Error**: `NameError: name 'RUN_DIR' is not defined`
- **Fix**: Make sure you changed `run_dir` to `RUN_DIR` (uppercase)

**Error**: `TypeError: unsupported operand type(s) for /: 'str' and 'str'`
- **Fix**: Make sure `RUN_DIR` is a `Path` object, not a string

**Error**: Plan creation still fails
- **Fix**: Check that `.env` file has valid API keys

### **If Railway Deployment Fails**

**Error**: Container won't start
- **Check**: Railway logs for Python import errors
- **Fix**: Make sure all syntax is correct

**Error**: "Missing required API keys"
- **Check**: Railway dashboard → Variables tab
- **Fix**: Add `OPENAI_API_KEY` and `OPENROUTER_API_KEY`

**Error**: Still getting permission denied
- **Check**: Railway logs for actual path being used
- **Fix**: Verify `/tmp/planexe/run` is being created

**Error**: Luigi subprocess still crashes
- **Check**: Railway logs for "DEBUG ENV" and "DEBUG LLM" messages
- **Fix**: Verify environment variables are being passed to subprocess

---

## 📊 **Expected Timeline**

| Step | Duration | Cumulative |
|------|----------|------------|
| 1. Fix filesystem | 30 min | 30 min |
| 2. Add env validation | 30 min | 60 min |
| 3. Add LLM validation | 30 min | 90 min |
| 4. Update Dockerfile | 15 min | 105 min |
| 5. Test locally | 15 min | 120 min |
| 6. Commit & deploy | 15 min | 135 min |
| 7. Monitor Railway | 15 min | 150 min |

**Total**: ~2.5 hours

---

## 🎯 **Next Steps After Success**

1. **Remove debug logging** - Clean up excessive `print()` statements
2. **Add persistent storage** - Configure Railway volume for plan persistence
3. **Optimize Docker build** - Cache layers for faster deployments
4. **Add monitoring** - Set up Railway metrics and alerts
5. **Document deployment** - Update README with Railway setup instructions

---

**Ready to implement? Start with Step 1!**
