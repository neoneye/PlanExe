# Railway Deployment Guide for PlanExe

## Overview

This guide will walk you through deploying PlanExe to Railway, which will solve the Windows development environment issues you've been experiencing. Railway's Linux containers will handle Luigi subprocess spawning and environment variable inheritance properly.

## Prerequisites

1. **Railway Account**: Sign up at [railway.app](https://railway.app)
2. **GitHub Repository**: Your PlanExe code should be in a GitHub repository
3. **API Keys**: 
   - OpenRouter API key (recommended) OR OpenAI API key
   - Any other LLM provider keys you want to use

## Step 1: Prepare Your Repository

### 1.1 Commit Your Changes
Make sure all your recent changes are committed and pushed to GitHub:

```bash
git add .
git commit -m "Prepare for Railway deployment"
git push origin main
```

### 1.2 Create Environment Template
Create a `.env.example` file in your project root:

```bash
# Copy this to .env.railway for Railway deployment
# Required API Keys
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Other LLM providers
ANTHROPIC_API_KEY=your_anthropic_key_here

# Railway will automatically provide these:
# DATABASE_URL=postgresql://...
# PORT=...
# RAILWAY_ENVIRONMENT=production
```

## Step 2: Deploy the Database

### 2.1 Create New Railway Project
1. Go to [railway.app](https://railway.app)
2. Click "New Project"
3. Select "Empty Project"
4. Name it something like "planexe-production"

### 2.2 Add PostgreSQL Database
1. In your Railway project dashboard, click "+ New"
2. Select "Database" → "PostgreSQL"
3. Railway will automatically provision and configure the database
4. Note: Railway automatically generates `DATABASE_URL` environment variable

## Step 3: Deploy the Backend (FastAPI + Luigi)

### 3.1 Add Backend Service
1. Click "+ New" → "GitHub Repo"
2. Connect your GitHub account if not already connected
3. Select your PlanExe repository
4. Choose "Deploy from repo"

### 3.2 Configure Backend Service
1. **Service Name**: Change to "planexe-api"
2. **Root Directory**: Leave as `/` (project root)
3. **Build Command**: Railway will auto-detect the Dockerfile

### 3.3 Set Environment Variables
In the Railway dashboard for your API service, go to "Variables" tab and add:

```
OPENROUTER_API_KEY=your_actual_api_key
OPENAI_API_KEY=your_actual_openai_key
PLANEXE_RUN_DIR=/app/run
PYTHONPATH=/app
PYTHONUNBUFFERED=1
```

**Important**: Railway automatically provides:
- `DATABASE_URL` (from PostgreSQL service)
- `PORT` (Railway assigns this)
- `RAILWAY_ENVIRONMENT=production`

### 3.4 Configure Dockerfile Path
1. Go to "Settings" tab in your API service
2. Under "Build", set **Dockerfile Path** to: `docker/Dockerfile.railway.api`
3. Set **Build Context** to: `/` (project root)

### 3.5 Deploy Backend
1. Click "Deploy" or push changes to trigger deployment
2. Monitor the build logs for any errors
3. Once deployed, test the health endpoint: `https://your-api-url.railway.app/health`

## Step 4: Deploy the Frontend (Next.js)

### 4.1 Add Frontend Service
1. Click "+ New" → "GitHub Repo"
2. Select the same repository
3. This creates a second service from the same repo

### 4.2 Configure Frontend Service
1. **Service Name**: Change to "planexe-frontend"
2. **Root Directory**: Set to `/planexe-frontend`
3. **Dockerfile Path**: `docker/Dockerfile.railway.ui`

### 4.3 Set Frontend Environment Variables
In the frontend service "Variables" tab:

```
NEXT_PUBLIC_API_URL=https://your-api-service-url.railway.app
NODE_ENV=production
NEXT_TELEMETRY_DISABLED=1
```

**Note**: Replace `your-api-service-url.railway.app` with the actual URL of your API service.

### 4.4 Deploy Frontend
1. Click "Deploy"
2. Monitor build logs
3. Test the frontend: `https://your-frontend-url.railway.app`

## Step 5: Configure Service Communication

### 5.1 Get Service URLs
1. Go to your API service → "Settings" → "Domains"
2. Copy the public domain (e.g., `planexe-api-production-abc123.railway.app`)
3. Update the frontend's `NEXT_PUBLIC_API_URL` variable with this URL

### 5.2 Test Integration
1. Visit your frontend URL
2. Try creating a test plan
3. Monitor the API service logs for Luigi pipeline execution
4. Verify that the plan generation works end-to-end

## Step 6: Verify Luigi Pipeline

### 6.1 Test Plan Creation
1. Go to your frontend URL
2. Create a simple test plan: "Create a small business plan for a coffee shop"
3. Use model: `gpt-4o-mini` or similar
4. Set speed: `FAST_BUT_SKIP_DETAILS` for quick testing

### 6.2 Monitor Execution
1. In Railway API service dashboard, go to "Logs"
2. You should see Luigi pipeline starting and executing tasks
3. Look for successful environment variable access
4. Verify plan files are generated in `/app/run`

### 6.3 Check for Success Indicators
```
✅ API health check returns 200
✅ Database connection successful
✅ LLM API calls working (check API key access)
✅ Luigi tasks executing successfully
✅ Plan files generated
✅ Frontend displays real-time progress
✅ Plan completion notification
```

## Troubleshooting

### Environment Variable Issues
If Luigi tasks fail with API key errors:

1. **Check Railway Variables**: Ensure all API keys are set correctly
2. **Restart Services**: Railway environment changes require restart
3. **Check Logs**: Look for specific error messages in Railway logs

### Build Failures

**Backend Build Issues**:
- Check Dockerfile path is `docker/Dockerfile.railway.api`
- Ensure all Python dependencies are in `requirements.txt`
- Check build context is set to project root `/`

**Frontend Build Issues**:
- Verify `planexe-frontend` directory structure
- Check Node.js version compatibility
- Ensure all npm dependencies are installed

### Runtime Issues

**Backend Runtime Problems**:
```bash
# Check Railway logs for these errors:
# 1. "ModuleNotFoundError" → PYTHONPATH issue
# 2. "Database connection failed" → DATABASE_URL issue  
# 3. "API key not found" → Environment variable issue
```

**Frontend Runtime Problems**:
```bash
# Common issues:
# 1. "API_URL not defined" → NEXT_PUBLIC_API_URL missing
# 2. "CORS errors" → Backend CORS configuration
# 3. "Connection refused" → Backend service not running
```

## Production Considerations

### 1. Database Backups
- Railway automatically backs up PostgreSQL
- Consider setting up additional backup strategies for critical data

### 2. Monitoring
- Use Railway's built-in monitoring
- Set up alerts for service downtime
- Monitor Luigi pipeline execution times

### 3. Scaling
- Railway auto-scales based on demand
- Monitor resource usage during heavy Luigi pipeline execution
- Consider upgrading Railway plan for higher resource limits

### 4. Security
- Regularly rotate API keys
- Monitor access logs
- Keep dependencies updated

## Cost Optimization

1. **Development vs Production**:
   - Use Railway's free tier for testing
   - Upgrade to paid plan for production usage

2. **Resource Management**:
   - Monitor CPU/Memory usage during Luigi execution
   - Consider Luigi task batching for efficiency

3. **Database Optimization**:
   - Regular database maintenance
   - Monitor connection pool usage

## Migration from Local Development

### What This Solves
✅ **Windows Subprocess Issues**: Linux containers handle process spawning correctly
✅ **Environment Variable Inheritance**: Proper Unix environment handling
✅ **Path Handling**: Unix paths work correctly with Luigi
✅ **Dependency Management**: Consistent Linux environment
✅ **Scalability**: Cloud-based execution vs local resource limits

### Development Workflow
1. **Develop Locally**: Continue using your Windows machine for code editing
2. **Test on Railway**: Push changes to GitHub → auto-deploy to Railway
3. **Debug**: Use Railway logs instead of local terminal output
4. **Iterate**: Much faster than fighting Windows environment issues

## Next Steps

1. **Custom Domain**: Set up custom domain for production
2. **CI/CD**: Set up automated testing before deployment
3. **Monitoring**: Implement application performance monitoring
4. **Backup Strategy**: Set up automated plan data backups
5. **User Management**: Add authentication and user accounts

## Support

- **Railway Docs**: [docs.railway.app](https://docs.railway.app)
- **Railway Discord**: Community support
- **PlanExe Issues**: GitHub repository issues page

---

**You should now have a fully functional PlanExe deployment on Railway that avoids all the Windows development environment issues!**