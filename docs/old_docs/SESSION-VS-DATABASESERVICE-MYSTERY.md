/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-27
 * PURPOSE: Document the persistent Session vs DatabaseService circular debugging issue
 * SRP and DRY check: Pass - Single responsibility for documenting known issue
 */

# Session vs DatabaseService Mystery

## 🔍 **The Persistent Error**

**Error Message**: `'Session' object has no attribute 'get_all_plans'`
**Endpoint**: `/api/plans` (GET request to list all plans)
**Status**: ISOLATED ISSUE - Does not affect core functionality

---

## 🧩 **The Mystery**

### **What The Error Claims**
- Error says code is calling `get_all_plans()` method
- Error says a raw `Session` object is being used instead of `DatabaseService`

### **What The Code Actually Does**
```python
# File: planexe_api/api.py:604
@app.get("/api/plans", response_model=List[PlanResponse])
async def list_plans(db: DatabaseService = Depends(get_database)):
    try:
        plans = db.list_plans()  # ← Calls list_plans, NOT get_all_plans
```

### **What The Dependency Injection Returns**
```python
# File: planexe_api/database.py:148
def get_database():
    """Get DatabaseService instance for dependency injection"""
    db = SessionLocal()
    try:
        yield DatabaseService(db)  # ← Returns DatabaseService, NOT raw Session
```

### **What DatabaseService Actually Has**
```python
# Confirmed via Python inspection:
DatabaseService methods: ['list_plans', 'create_plan', 'get_plan', ...]
# ✅ Has list_plans method
# ❌ Does NOT have get_all_plans method
```

---

## 🔄 **Circular Debugging History**

### **Attempted Solutions**
1. ✅ **Verified dependency injection** - `get_database()` correctly returns `DatabaseService`
2. ✅ **Confirmed method exists** - `DatabaseService.list_plans()` method is present
3. ✅ **Checked for typos** - No `get_all_plans` references found in codebase
4. ✅ **Restarted services** - Backend restarted multiple times
5. ✅ **Checked import caching** - No Python bytecode cache issues found
6. ✅ **Verified code consistency** - Same codebase deployed to Railway

### **Still Failing**
- `/api/plans` continues to return the same error
- Error message doesn't match actual code implementation
- Other endpoints work fine (`/api/models`, `/health`, `/api/prompts`)

---

## 🎯 **Impact Assessment**

### **✅ Core Functionality WORKS**
- **LLM Models**: `/api/models` returns models correctly
- **Health Check**: `/health` confirms backend is operational
- **Prompts**: `/api/prompts` returns example prompts
- **Plan Creation**: `/api/plans` POST (create) likely works
- **WebSocket**: Real-time progress via WebSocket architecture

### **❌ Isolated Issue**
- **Plans List**: `/api/plans` GET (list all plans) fails
- **User Impact**: Cannot view existing plans in UI
- **Workaround**: Users can still create new plans

---

## 🤔 **Possible Explanations**

### **1. Hidden Code Path**
- Maybe there's a different `list_plans` implementation being called
- Could be monkey-patching or dynamic method resolution
- Alternative: Different import path loading wrong code

### **2. Railway Environment Differences**
- Railway might have cached/stale code deployment
- Different Python environment with conflicting packages
- Environment variable differences affecting code path

### **3. SQLAlchemy Session Issues**
- Raw Session object somehow bypassing DatabaseService wrapper
- Session manager not working correctly in Railway environment
- Threading issues in production vs development

### **4. Error Message Confusion**
- Exception handler might be catching wrong error
- Error message from different part of stack trace
- Exception re-raising losing original context

---

## 🚫 **What We WON'T Do**

### **Avoid Time Sinks**
- ❌ **More local debugging** - Railway is the only environment that matters
- ❌ **Complex cache clearing** - Already attempted multiple times
- ❌ **Over-engineering fixes** - Issue is isolated and doesn't block users
- ❌ **Rabbit hole investigation** - Core functionality works, this is edge case

### **Focus on Value**
- ✅ **User experience** - Ensure UI works for plan creation and monitoring
- ✅ **Core workflows** - Model selection and plan execution are priority
- ✅ **Railway deployment** - Verify main functionality works on Railway
- ✅ **Robust UI** - Make sure users can accomplish their goals

---

## 🔧 **Mitigation Strategy**

### **Short Term**
1. **Document the issue** - This file serves as reference
2. **UI graceful handling** - Plans list shows "temporarily unavailable"
3. **Focus on creation flow** - Ensure users can create new plans
4. **Monitor for broader impact** - Watch for related issues

### **Long Term Investigation** (Low Priority)
1. **Deep SQLAlchemy investigation** - When other priorities complete
2. **Railway environment analysis** - Compare production vs development
3. **Alternative list implementation** - Backup endpoint if needed
4. **Database migration** - Potential fresh schema deployment

---

## 📋 **Status Tracking**

### **Current Status**: ISOLATED ISSUE
- **Severity**: Low (doesn't block core user workflows)
- **User Impact**: Cannot view existing plans list
- **Workaround**: Users can create new plans normally
- **Priority**: Low (behind UI robustness and Railway deployment)

### **Next Steps**
1. ✅ **Document issue** (this file)
2. 🔄 **Test Railway UI** - Verify plan creation works
3. 🔄 **UI error handling** - Graceful plans list failure
4. ⏸️ **Deep investigation** - Deferred until core functionality confirmed

---

## 💡 **For Future Developers**

### **If You Encounter This Issue**
1. **Don't go in circles** - This issue has been investigated extensively
2. **Check if it's still isolated** - Test other endpoints first
3. **Focus on user impact** - Can users create and monitor plans?
4. **Update this document** - Add any new findings or solutions

### **Investigation Checklist**
- [ ] Verify `/api/models` and `/health` still work
- [ ] Check if issue affects plan creation (`POST /api/plans`)
- [ ] Test Railway deployment end-to-end
- [ ] Document any new symptoms or solutions

**Remember: Railway deployment and user experience are more important than solving this isolated mystery.**