/**
 * Author: Cascade using Claude 3.5 Sonnet
 * Date: 2025-10-01T13:43:00-04:00
 * PURPOSE: Railway database migration checklist for v0.3.0 database-first architecture
 * SRP and DRY check: Pass - Single responsibility for Railway deployment migration
 */

# Railway Database Migration Checklist

## **Status: Ready to Deploy ✅**

After completing the Luigi database integration refactor (v0.3.0), you need to apply database migrations to Railway and verify the deployment configuration.

---

## **1. Database Migrations**

### **✅ Migration Files Exist**

The required migration already exists:
- **File**: `planexe_api/migrations/versions/002_add_plan_content_and_indexes.py`
- **Creates**: `plan_content` table with indexes
- **Status**: Ready to apply

### **📋 What the Migration Does**

```sql
-- Creates plan_content table
CREATE TABLE plan_content (
    id INTEGER PRIMARY KEY,
    plan_id VARCHAR(255) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    stage VARCHAR(100),
    content_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    content_size_bytes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance indexes
CREATE INDEX idx_plan_content_plan_id ON plan_content(plan_id);
CREATE INDEX idx_plan_content_plan_id_filename ON plan_content(plan_id, filename);
CREATE INDEX idx_plan_content_stage ON plan_content(stage);
```

### **🚀 Apply Migration to Railway**

#### **Option A: Via Railway CLI**
```bash
# Connect to Railway project
railway link

# Run migration
railway run alembic upgrade head

# Verify migration applied
railway run alembic current
```

#### **Option B: Via Railway Shell**
```bash
# Open Railway shell
railway shell

# Inside shell
cd planexe_api
alembic upgrade head
alembic current
exit
```

#### **Option C: Via API Container**
```bash
# SSH into running container
railway ssh

# Run migration
cd /app/planexe_api
python -m alembic upgrade head
```

### **✅ Verify Migration Success**

Check that the table exists:
```bash
railway run python -c "
from planexe_api.database import engine
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print('Tables:', tables)
print('plan_content exists:', 'plan_content' in tables)
"
```

---

## **2. Dockerfile Changes - `/tmp` for Run Directory**

### **❌ Issue Identified**

You mentioned `/add` folder - this doesn't exist in the codebase. However, the run directory configuration needed updating.

### **✅ Fix Applied**

Changed from `/app/run` to `/tmp/planexe_run`:

**Before**:
```dockerfile
RUN mkdir -p /app/run && chmod 755 /app/run
ENV PLANEXE_RUN_DIR=/app/run
```

**After**:
```dockerfile
RUN mkdir -p /tmp/planexe_run && chmod 755 /tmp/planexe_run
ENV PLANEXE_RUN_DIR=/tmp/planexe_run
```

### **Why `/tmp`?**

1. **Ephemeral by Design**: Railway filesystem is temporary anyway
2. **Database-First**: All content persists to PostgreSQL (v0.3.0)
3. **Luigi Dependency**: Files only needed during pipeline execution
4. **Clear Intent**: `/tmp` signals temporary storage

---

## **3. Railway Environment Variables**

### **Required Variables**

Ensure these are set in Railway:

```bash
# Database (should already be set)
DATABASE_URL=postgresql://user:pass@host:port/db

# LLM Configuration
OPENROUTER_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here  # If using OpenAI models

# PlanExe Configuration
PLANEXE_CLOUD_MODE=true
PLANEXE_RUN_DIR=/tmp/planexe_run  # Should match Dockerfile

# FastAPI
PORT=8080  # Railway sets this automatically
```

### **Verify Environment Variables**

```bash
railway variables
```

---

## **4. Deployment Checklist**

### **Pre-Deployment**

- [x] Migration file exists (`002_add_plan_content_and_indexes.py`)
- [x] Dockerfile updated to use `/tmp/planexe_run`
- [ ] Railway DATABASE_URL points to correct PostgreSQL instance
- [ ] Railway environment variables verified
- [ ] Local testing completed

### **Deployment Steps**

1. **Commit Dockerfile changes**:
   ```bash
   git add docker/Dockerfile.railway.single
   git commit -m "fix: Use /tmp for Railway run directory"
   git push origin ui
   ```

2. **Deploy to Railway**:
   ```bash
   railway up
   ```

3. **Apply database migration**:
   ```bash
   railway run alembic upgrade head
   ```

4. **Verify deployment**:
   ```bash
   # Check health endpoint
   curl https://your-railway-app.railway.app/health
   
   # Check database tables
   railway run python -c "from planexe_api.database import engine; from sqlalchemy import inspect; print(inspect(engine).get_table_names())"
   ```

5. **Test plan creation**:
   - Create a test plan via UI
   - Verify content written to database
   - Check that plan persists after Railway restart

### **Post-Deployment Verification**

- [ ] Health endpoint returns 200 OK
- [ ] `plan_content` table exists in database
- [ ] Test plan creates successfully
- [ ] Database contains plan content records
- [ ] Luigi pipeline completes without errors
- [ ] Plan accessible after Railway restart

---

## **5. Troubleshooting**

### **Migration Fails**

**Error**: `Table 'plan_content' already exists`

**Solution**: 
```bash
# Mark migration as applied without running it
railway run alembic stamp 002
```

### **Database Connection Error**

**Error**: `could not connect to server`

**Check**:
1. Railway DATABASE_URL is correct
2. PostgreSQL service is running
3. Database credentials are valid

**Fix**:
```bash
# Verify DATABASE_URL
railway variables | grep DATABASE_URL

# Test connection
railway run python -c "from planexe_api.database import engine; engine.connect()"
```

### **Luigi Can't Write Files**

**Error**: `Permission denied: /tmp/planexe_run`

**Fix**: Directory should be created automatically, but verify:
```bash
railway run ls -la /tmp/planexe_run
```

### **Content Not Persisting**

**Check**:
1. Migration applied successfully
2. Luigi tasks using `get_database_service()`
3. Database writes happening before filesystem writes

**Verify**:
```bash
# Check plan_content records
railway run python -c "
from planexe_api.database import get_database_service
db = get_database_service()
content = db.get_plan_content('test-plan-id')
print(f'Found {len(content)} content records')
db.close()
"
```

---

## **6. Rollback Plan**

If deployment fails:

### **Rollback Migration**
```bash
railway run alembic downgrade 001
```

### **Rollback Code**
```bash
git revert HEAD
git push origin ui
railway up
```

### **Emergency Fix**
If database is corrupted:
1. Create new PostgreSQL instance in Railway
2. Update DATABASE_URL
3. Run all migrations from scratch
4. Redeploy application

---

## **7. Success Criteria**

Deployment is successful when:

1. ✅ Migration 002 applied to Railway database
2. ✅ `plan_content` table exists with indexes
3. ✅ Application deploys without errors
4. ✅ Health endpoint returns 200 OK
5. ✅ Test plan creates successfully
6. ✅ Plan content persists to database
7. ✅ Luigi pipeline completes all 61 tasks
8. ✅ Plan accessible after Railway restart
9. ✅ No filesystem errors in logs
10. ✅ Database queries performant (<100ms)

---

## **8. Next Steps After Deployment**

1. **Monitor Performance**:
   - Watch database query times
   - Check for slow queries
   - Monitor database size growth

2. **Test Thoroughly**:
   - Create multiple plans
   - Verify all 61 tasks write to database
   - Test plan retrieval and downloads

3. **Update Documentation**:
   - Mark v0.3.0 as deployed
   - Document any deployment issues
   - Update CHANGELOG with deployment date

4. **Clean Up**:
   - Remove old plan files from filesystem (if any)
   - Archive old Railway logs
   - Update monitoring dashboards

---

## **Quick Reference Commands**

```bash
# Link to Railway project
railway link

# Check current migration
railway run alembic current

# Apply migrations
railway run alembic upgrade head

# Verify tables
railway run python -c "from planexe_api.database import engine; from sqlalchemy import inspect; print(inspect(engine).get_table_names())"

# Check environment variables
railway variables

# View logs
railway logs

# Deploy
railway up

# Open Railway dashboard
railway open
```

---

**Ready to deploy? Follow the checklist above step-by-step!**
