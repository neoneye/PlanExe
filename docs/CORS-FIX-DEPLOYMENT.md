# CORS Fix Deployment Guide

## Issue
Production endpoint at `https://planexe-production.up.railway.app/api/plans` was rejecting POST requests with HTTP 403 errors due to missing CORS headers.

## Root Cause
CORS was completely disabled in production mode (lines 66-77 in `planexe_api/api.py`). The code assumed all production requests would come from the same origin (served static UI), blocking external API access.

## Fix Applied
**File Modified:** `planexe_api/api.py`

**Changes:**
- ✅ Enabled CORS middleware in production mode
- ✅ Added Railway domain whitelist (`*.railway.app`)
- ✅ Added regex pattern matching for all Railway subdomains
- ✅ Specified explicit HTTP methods including OPTIONS for preflight requests

**New Production CORS Configuration:**
```python
# Production mode: Enable CORS for Railway production domain and allow API access
production_origins = [
    "https://planexe-production.up.railway.app",
    "https://*.railway.app",  # Allow all Railway subdomains
]
print(f"Production mode: CORS enabled for {production_origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=production_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    allow_origin_regex=r"https://.*\.railway\.app",  # Regex pattern for Railway domains
)
```

## Deployment Steps

### Option 1: Git Push (Automatic Railway Deployment)
```bash
# From PlanExe root directory
git add planexe_api/api.py
git commit -m "fix: Enable CORS in production for Railway API access"
git push origin main
```

Railway will automatically detect the push and redeploy. Monitor deployment at:
https://railway.app/project/[your-project-id]

### Option 2: Railway CLI
```bash
# Install Railway CLI if not already installed
npm i -g @railway/cli

# Login to Railway
railway login

# Link to your project
railway link

# Deploy
railway up
```

### Option 3: Manual Railway Dashboard
1. Go to Railway dashboard
2. Select PlanExe project
3. Click "Deploy" → "Redeploy" from latest commit
4. Wait for build to complete (~3-5 minutes)

## Verification

### 1. Check CORS Headers
```bash
curl -X OPTIONS https://planexe-production.up.railway.app/api/plans \
  -H "Origin: https://planexe-production.up.railway.app" \
  -H "Access-Control-Request-Method: POST" \
  -v
```

**Expected Response Headers:**
- `Access-Control-Allow-Origin: https://planexe-production.up.railway.app`
- `Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS, PATCH`
- `Access-Control-Allow-Credentials: true`

### 2. Test POST Request
```bash
curl -X POST https://planexe-production.up.railway.app/api/plans \
  -H "Content-Type: application/json" \
  -H "Origin: https://planexe-production.up.railway.app" \
  -d '{
    "prompt": "Test Yorkshire plan",
    "llm_model": "openrouter/anthropic/claude-3.5-sonnet",
    "speed_vs_detail": "full"
  }' \
  -v
```

**Expected:** HTTP 200 or 201 with plan creation response (not 403)

### 3. Check Railway Logs
```bash
# Using Railway CLI
railway logs

# Or via dashboard at:
# https://railway.app/project/[your-project-id]/service/[service-id]
```

**Look for this log line:**
```
Production mode: CORS enabled for ['https://planexe-production.up.railway.app', 'https://*.railway.app']
```

## Additional Configuration (If Needed)

### Allow More Origins
If you need to allow additional domains (e.g., custom domain or testing tools), modify `production_origins` list:

```python
production_origins = [
    "https://planexe-production.up.railway.app",
    "https://*.railway.app",
    "https://your-custom-domain.com",  # Add custom domains here
]
```

### Open CORS for Development Testing
**⚠️ NOT RECOMMENDED FOR PRODUCTION ⚠️**

For temporary testing, you can allow all origins:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows ANY origin
    allow_credentials=False,  # Must be False with allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Rollback Plan
If the fix causes issues, revert to previous version:

```bash
git revert HEAD
git push origin main
```

Or manually restore the old CORS configuration:
```python
# Old configuration (CORS disabled in production)
if IS_DEVELOPMENT:
    app.add_middleware(CORSMiddleware, ...)
else:
    print("Production mode: CORS disabled, serving static UI")
```

## Expected Behavior After Fix

### ✅ Working Scenarios
- ✅ POST to `/api/plans` from Railway frontend
- ✅ POST to `/api/plans` from external tools (Postman, curl)
- ✅ WebSocket connections to `/ws/plans/{id}/progress`
- ✅ GET requests to all API endpoints
- ✅ OPTIONS preflight requests

### ❌ Still Blocked (By Design)
- ❌ Requests from non-Railway domains (unless explicitly added)
- ❌ Requests without proper Origin headers (might work depending on browser)

## Troubleshooting

### Still Getting 403 After Deployment?
1. **Check Railway logs** for CORS configuration message
2. **Verify PLANEXE_CLOUD_MODE=true** in Railway environment variables
3. **Clear browser cache** and test in incognito mode
4. **Check request Origin header** matches Railway domain

### CORS Preflight Failing?
- Ensure OPTIONS method is included in `allow_methods`
- Check `Access-Control-Request-Headers` in preflight request
- Verify `allow_headers=["*"]` allows your custom headers

### Production vs Development Confusion?
Check environment variable in Railway dashboard:
```
PLANEXE_CLOUD_MODE = true
```

If missing or set to "false", add it manually in Railway → Settings → Variables.

## Related Files
- `planexe_api/api.py` - Main API file with CORS configuration
- `docker/Dockerfile.railway.single` - Sets PLANEXE_CLOUD_MODE=true
- `railway.toml` - Railway deployment configuration

## References
- FastAPI CORS Documentation: https://fastapi.tiangolo.com/tutorial/cors/
- Railway Deployment Docs: https://docs.railway.app/deploy/deployments
- MDN CORS Guide: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
