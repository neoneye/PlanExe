# Railway Deployment Plan for PlanExe

## Current Problem Analysis
Windows development environment issues with Luigi subprocess spawning, environment variable inheritance, and path handling are blocking local development. Railway deployment on Linux containers should resolve these issues.

## Deployment Strategy

### Architecture Decision
- **Backend (FastAPI + Luigi Pipeline)**: Deploy to Railway with PostgreSQL
- **Frontend (Next.js)**: Deploy to Railway as separate service
- **Database**: Railway PostgreSQL service

### Phase 1: Railway Backend Setup
1. Create `railway.toml` configuration
2. Update `Dockerfile.api` for Railway compatibility (PORT variable)
3. Configure PostgreSQL database connection
4. Set up environment variables (API keys, database URL)
5. Test Luigi pipeline execution in Railway environment

### Phase 2: Railway Frontend Setup
1. Create separate `Dockerfile` for Next.js optimized for Railway
2. Configure backend API URL environment variable
3. Set up build and deployment process
4. Test frontend-backend connectivity

### Phase 3: Environment Configuration
1. Document all required environment variables
2. Create Railway environment variable setup guide
3. Test API key inheritance in Luigi subprocess
4. Verify plan generation end-to-end

### Phase 4: Documentation and Testing
1. Create deployment documentation
2. Test Windows → Railway development workflow
3. Document troubleshooting for common issues
4. Create backup/migration strategy

## Key Files to Create/Modify
- `railway.toml` - Railway configuration
- `docker/Dockerfile.railway.api` - Railway-optimized API Docker
- `docker/Dockerfile.railway.ui` - Railway-optimized frontend Docker  
- `docs/RAILWAY-SETUP-GUIDE.md` - Step-by-step deployment
- Environment variable documentation

## Expected Benefits
- Resolve Windows subprocess issues
- Proper environment variable inheritance
- Linux-based Luigi pipeline execution
- Scalable cloud deployment
- Easy CI/CD integration