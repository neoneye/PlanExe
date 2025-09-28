/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-27
 * PURPOSE: Railway-first development workflow - no local testing, Railway staging is the only environment that matters
 * SRP and DRY check: Pass - Single responsibility for development workflow documentation
 */

# Railway-First Development Workflow

## 🚨 **CRITICAL: NO LOCAL TESTING**

**The development machine does NOT run any local testing. Railway staging is the ONLY environment that matters.**

### **Core Principle**
- **Push → Deploy → Test** on Railway staging
- **UI debugging** via error states and visual feedback
- **No console debugging** - UI shows everything users need to know
- **Railway logs** for backend debugging when UI isn't enough

---

## 🔄 **Development Cycle**

### **1. Code Changes**
```bash
# Make changes to frontend/backend
git add -A
git commit -m "descriptive commit message"
git push origin main  # Auto-deploys to Railway
```

### **2. Railway Deployment**
- **Automatic**: Railway deploys on every push to main branch
- **Build time**: ~3-5 minutes for complete build
- **Single service**: FastAPI serves both API and static frontend

### **3. Testing on Railway**
- **URL**: Check Railway dashboard for deployment URL
- **UI testing**: Use the actual UI to test functionality
- **Error states**: UI shows loading, error, success states clearly
- **Debug endpoints**: Use `/api/models/debug` and `/ping` for diagnostics

---

## 🛠️ **Debugging Tools**

### **1. UI-Based Debugging (Primary)**
- **LLM dropdown states**: Loading spinner, error messages, fallback options
- **Error panels**: Railway-specific error details with retry buttons
- **Loading indicators**: Real-time feedback on API calls
- **Interactive debugging**: Retry buttons, manual fallbacks

### **2. Railway Diagnostic Endpoints**
```bash
# Check deployment status
curl https://your-railway-app.railway.app/ping

# Debug LLM models configuration
curl https://your-railway-app.railway.app/api/models/debug

# Test models endpoint
curl https://your-railway-app.railway.app/api/models

# Health check
curl https://your-railway-app.railway.app/health
```

### **3. Railway Logs (When UI Isn't Enough)**
- **Access**: Railway dashboard → Deployments → View Logs
- **Focus**: Backend errors, startup issues, API failures
- **Don't rely on**: Console logs from development machine

---

## ✅ **Testing Checklist**

### **After Each Railway Deployment**
- [ ] **UI loads**: Frontend displays without errors
- [ ] **Models dropdown**: Shows loading → success/error states
- [ ] **Error handling**: Retry buttons work when APIs fail
- [ ] **Plan creation**: Can submit forms (even if backend has issues)
- [ ] **Diagnostic endpoints**: `/ping` and `/api/models/debug` respond

### **UI State Verification**
- [ ] **Loading state**: Spinner shows during model fetch
- [ ] **Success state**: Models populate dropdown correctly
- [ ] **Error state**: Clear error message with Railway context
- [ ] **Empty state**: Fallback options when no models returned
- [ ] **Retry functionality**: Retry buttons reconnect successfully

---

## 🚨 **Common Railway Issues & Solutions**

### **Issue: Models Dropdown Empty**
**UI Shows**: "No models from Railway API"
**Debug Steps**:
1. Check `/api/models/debug` endpoint
2. Verify Railway environment variables (API keys)
3. Use retry button in UI
4. Check Railway deployment logs

### **Issue: API Connection Errors**
**UI Shows**: "Railway API error: HTTP 500"
**Debug Steps**:
1. Check `/health` endpoint status
2. Verify Railway service is running
3. Check for startup errors in Railway logs
4. Wait 30 seconds for Railway startup (auto-retry is built-in)

### **Issue: Old Code Running**
**UI Shows**: Unexpected behavior
**Debug Steps**:
1. Check `/ping` endpoint for deployment timestamp
2. Verify git commit hash matches Railway deployment
3. Clear browser cache
4. Force new Railway deployment

---

## 📚 **Documentation Hierarchy**

### **For Developers**
1. **This file**: Railway workflow and debugging
2. **CHANGELOG.md**: What changed and why
3. **CLAUDE.md**: Architecture overview and guidelines

### **For Troubleshooting**
1. **SESSION-VS-DATABASESERVICE-MYSTERY.md**: Known isolated backend issue
2. **Railway logs**: Detailed backend error investigation
3. **UI error states**: User-facing problem diagnosis

---

## ⚠️ **Critical Warnings**

### **DO NOT**
- **Test locally**: Local environment doesn't match Railway
- **Debug via console**: UI error states are more reliable
- **Assume local works = Railway works**: Completely different environments
- **Skip UI testing**: UI states are the primary debugging tool

### **DO**
- **Test every change on Railway**: Only environment that matters
- **Use UI debugging first**: Error states, retry buttons, loading indicators
- **Check diagnostic endpoints**: `/ping`, `/api/models/debug` for technical details
- **Read Railway logs**: When UI debugging isn't sufficient
- **Update this doc**: When workflow changes or new patterns emerge

---

## 🎯 **Success Criteria**

**A change is considered successful when**:
- ✅ Railway deployment completes without errors
- ✅ UI loads and shows appropriate states (loading/success/error)
- ✅ Users can interact with the interface meaningfully
- ✅ Error states provide clear guidance for next steps
- ✅ Diagnostic endpoints confirm backend functionality

**Performance is secondary to clarity** - users should always know what's happening, even if it's slow or broken.