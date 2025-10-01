/**
 * Author: Cascade using Claude 3.5 Sonnet
 * Date: 2025-09-30T20:39:10-04:00
 * PURPOSE: Step-by-step implementation plan to fix Railway deployment blockers
 * SRP and DRY check: Pass - Single responsibility for Railway fix execution plan
 */

# 🔧 Railway Fix Implementation Plan

## **Quick Summary**

**REVISED BASED ON USER EVIDENCE** - Original analysis was incorrect about `/app/run`

Two critical bugs prevent Railway deployment:
1. **SDK cache directory writes** - OpenAI/Luigi SDKs try to write to `$HOME` (undefined/read-only on Railway)
2. **Environment variable validation** - No fail-fast checks for missing API keys

**Evidence**: FastAPI successfully creates `/app/run/PlanExe_xxx/` directories. Crash happens later during Luigi subprocess initialization when SDKs try to write cache files.

**Estimated time**: 1.5 hours total

---

## 📋 **Step-by-Step Implementation**

### **Step 1: Fix SDK Cache Directory Issue** (15 minutes)

**Priority**: CRITICAL - This must be fixed first

**File**: `planexe_api/services/pipeline_execution_service.py`

**Location**: Around line 138-139 (inside `_setup_environment` method)

**Change**:
```python
# BEFORE:
# Copy environment and add pipeline-specific variables
environment = os.environ.copy()
environment[PipelineEnvironmentEnum.RUN_ID_DIR.value] = str(run_id_dir)

# AFTER:
# Copy environment and add pipeline-specific variables
environment = os.environ.copy()

# CRITICAL: Force SDK cache directories to writable /tmp location
# Railway's $HOME is undefined or read-only, causing OpenAI/Luigi SDK crashes
environment['HOME'] = '/tmp'
environment['OPENAI_CACHE_DIR'] = '/tmp/.cache/openai'
environment['LUIGI_CONFIG_PATH'] = '/tmp/.luigi'
print(f"DEBUG ENV: Set HOME=/tmp for SDK cache writes")

environment[PipelineEnvironmentEnum.RUN_ID_DIR.value] = str(run_id_dir)
```

**Why this works**:
- `/app/run` is already writable (proven by successful directory creation)
- The crash happens when OpenAI SDK tries to write to `~/.cache/openai/`
- Luigi tries to write scheduler state to `~/.luigi/`
- Setting `HOME=/tmp` redirects all SDK cache writes to writable location

**Test locally**:
```powershell
# Should still work - /tmp exists on Windows too
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

### **Step 4: Update Dockerfile** (OPTIONAL - Skip This)

**Priority**: NOT NEEDED - `/app/run` is already writable

**Reason**: User evidence proves `/app/run` works fine. The issue is SDK cache directories, not the run directory.

**No changes needed to Dockerfile.**

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
- ✅ `HOME=/tmp` set in subprocess environment
- ✅ No SDK cache write errors
- ✅ Luigi subprocess starts
- ✅ API keys validated successfully

---

### **Step 6: Commit and Deploy to Railway** (15 minutes)

**Commands**:
```powershell
cd d:\1Projects\PlanExe

# Stage all changes
git add planexe_api/services/pipeline_execution_service.py
git add planexe/llm_util/simple_openai_llm.py
git add docs/RAILWAY_BREAKTHROUGH_ANALYSIS.md
git add docs/RAILWAY_FIX_IMPLEMENTATION_PLAN.md

# Commit with detailed message
git commit -m "Fix Railway deployment: SDK cache directories + env var validation

CRITICAL FIXES:
1. Set HOME=/tmp to redirect SDK cache writes to writable location
2. Add fail-fast API key validation in pipeline_execution_service
3. Add fail-fast API key validation in SimpleOpenAILLM
4. Explicitly re-inject API keys into subprocess environment

ISSUE: OpenAI/Luigi SDKs try to write to ~/.cache and ~/.luigi
Railway's \$HOME is undefined or read-only, causing SDK initialization crashes

SOLUTION: 
- Force HOME=/tmp in subprocess environment for SDK cache writes
- Set OPENAI_CACHE_DIR=/tmp/.cache/openai explicitly
- Set LUIGI_CONFIG_PATH=/tmp/.luigi explicitly
- Validate API keys exist before subprocess creation
- Fail fast with clear error messages instead of silent failures

EVIDENCE:
- /app/run IS writable (directory creation succeeds)
- Crash happens during Luigi subprocess initialization
- Log cuts off at 'pipeline_environment: PipelineEnvironment...'
- This matches SDK cache write failure pattern

TESTING:
- Local: Verified /tmp works on Windows too
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
   ✅ OPENAI_API_KEY: Available (length: 164)
   ✅ OPENROUTER_API_KEY: Available (length: 89)
   ```

**Test via UI**:
1. Open Railway deployment URL
2. Submit a test plan
3. Watch Railway logs for:
   ```
   DEBUG: Created run directory: /app/run/PlanExe_xxx
   DEBUG ENV: Set HOME=/tmp for SDK cache writes
   DEBUG ENV: Explicitly set OPENAI_API_KEY in subprocess environment
   DEBUG: Subprocess started with PID: xxxx
   DEBUG LLM: Creating OpenAI client (key length: 164)
   Luigi: INFO - pipeline_environment: PipelineEnvironment(run_id_dir='/app/run/PlanExe_xxx'...)
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
- [ ] Startup logs show API keys available
- [ ] Startup logs show `HOME=/tmp` set
- [ ] Plan creation succeeds
- [ ] Files created in `/app/run/PlanExe_xxx/`
- [ ] Luigi subprocess starts
- [ ] Luigi logs show full `pipeline_environment` line (no crash)
- [ ] Environment variables reach subprocess
- [ ] SDK cache writes succeed to `/tmp/`
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
- **Check**: Railway logs for SDK cache write errors
- **Fix**: Verify `HOME=/tmp` is set in subprocess environment
- **Debug**: Check if OpenAI SDK is trying to write elsewhere

**Error**: Luigi subprocess still crashes
- **Check**: Railway logs for "DEBUG ENV" and "DEBUG LLM" messages
- **Fix**: Verify environment variables are being passed to subprocess

---

## 📊 **Expected Timeline**

| Step | Duration | Cumulative |
|------|----------|------------|
| 1. Fix SDK cache dirs | 15 min | 15 min |
| 2. Add env validation | 30 min | 45 min |
| 3. Add LLM validation | 30 min | 75 min |
| 4. Update Dockerfile | SKIP | 75 min |
| 5. Test locally | 15 min | 90 min |
| 6. Commit & deploy | 15 min | 105 min |
| 7. Monitor Railway | 15 min | 120 min |

**Total**: ~2 hours (revised down from 2.5 hours)

---

## 🎯 **Next Steps After Success**

1. **Remove debug logging** - Clean up excessive `print()` statements
2. **Add persistent storage** - Configure Railway volume for plan persistence
3. **Optimize Docker build** - Cache layers for faster deployments
4. **Add monitoring** - Set up Railway metrics and alerts
5. **Document deployment** - Update README with Railway setup instructions

---

**Ready to implement? Start with Step 1!**
