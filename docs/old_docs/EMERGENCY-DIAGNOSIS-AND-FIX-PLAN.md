# Emergency PlanExe System Diagnosis & Fix Plan

**CRITICAL STATUS**: System completely broken - Luigi pipeline not executing at all

## Phase 1: Immediate System Diagnosis (30 minutes)

### 1.1 Verify Basic Services
- Test if backend starts on port 8080
- Test if frontend starts on port 3000
- Check health endpoint responses
- Verify model loading from llm_config.json

### 1.2 Test Plan Creation API
- Submit snow plow business plan via API
- Monitor what actually happens vs what should happen
- Check if Luigi pipeline starts at all
- Examine error logs and stack traces

### 1.3 Environment Variable Analysis
- Verify API keys are loaded from .env
- Check if environment variables reach Luigi process
- Test LLM factory initialization
- Validate model selection works

## Phase 2: Fix Core Luigi Pipeline Execution (2 hours)

### 2.1 Revert In-Process Execution
**Problem**: Recent commit broke subprocess execution with "in-process" Luigi
**Solution**: Revert to working subprocess approach with proper environment passing

### 2.2 Fix Windows Subprocess Issues
- Use `shell=True` for Windows compatibility
- Fix environment variable inheritance
- Ensure Python module path resolution
- Test subprocess spawning with real plan

### 2.3 LLM Integration Fixes
- Fix SimpleOpenAILLM missing methods (identified in handover docs)
- Fix RedlineGateTask and IdentifyPurposeTask errors
- Test model fallback sequence works
- Ensure API keys reach all tasks

## Phase 3: Fix Progress Monitoring (1 hour)

### 3.1 Fix False Progress Reporting
- Debug regex parsing of Luigi subprocess output
- Fix "95% complete" lie when at 1.8% actual progress
- Only report completion when `999-pipeline_complete.txt` exists
- Stream real Luigi task output to frontend

### 3.2 Fix File Access API
- Debug Internal Server Error in `/api/plans/{id}/files`
- Fix filesystem scanning crash
- Ensure users can browse generated files
- Test file downloads work end-to-end

## Phase 4: End-to-End Validation (1 hour)

### 4.1 Snow Plow Business Test
- Create plan: "snow plow business in eastern CT. already own a truck. just need a plow right? how much are those?"
- Monitor through complete pipeline execution
- Verify all 61 Luigi tasks complete
- Confirm HTML report generation
- Test file download access

### 4.2 User Journey Validation
- Start both services correctly
- Submit plan via frontend form
- See accurate real-time progress
- Access generated files when complete
- Download final HTML report

## Implementation Strategy

### Step 1: Emergency Revert (30 minutes)
```bash
# Revert the broken in-process execution
git revert e206124 --no-edit
# Test if subprocess execution works again
```

### Step 2: Fix Environment Issues (1 hour)
- Fix Windows subprocess spawning
- Ensure .env variables reach Luigi subprocess
- Test with real API keys and model selection

### Step 3: Fix Luigi Task Errors (1 hour)
- Add missing LlamaIndex compatibility methods
- Fix RedlineGateTask and IdentifyPurposeTask
- Test pipeline completes all 61 tasks

### Step 4: Fix UX Issues (1 hour)
- Fix progress monitoring lies
- Fix file access crashes
- Test complete user experience

## Success Criteria

### Minimum Viable Success
- Backend starts without errors
- Frontend connects to backend
- Plan creation triggers Luigi pipeline
- Luigi pipeline executes beyond 3 tasks
- Users can see real progress updates
- File access API doesn't crash

### Complete Success
- Snow plow plan completes all 61 Luigi tasks
- Progress monitoring shows accurate percentage
- Users can browse and download all generated files
- HTML report is generated and accessible
- System is demonstrably usable end-to-end

## Risk Mitigation

### Backup Plan
If fixing current system proves too complex:
1. Document exactly what's broken
2. Create minimal working subprocess version
3. Strip out complex progress monitoring
4. Focus only on basic plan generation

### Testing Protocol
- Test each change immediately
- Use existing failed run data
- Don't create fake test data
- Commit working changes incrementally

### Time Management
- 30 min diagnosis maximum
- 2 hours core fixes maximum
- 1 hour validation maximum
- Document failures clearly if time runs out

## Files to Modify

### Priority 1 (Core Execution)
- `planexe_api/api.py` - Fix subprocess execution
- `planexe/llm_util/simple_openai_llm.py` - Add missing methods
- `planexe/diagnostics/redline_gate.py` - Fix task errors
- `planexe/assume/identify_purpose.py` - Fix task errors

### Priority 2 (UX Fixes)
- `planexe_api/api.py` - Fix progress monitoring and file access
- Frontend components - Real-time progress display

### Priority 3 (Validation)
- Test scripts for end-to-end validation
- Documentation updates

This plan prioritizes getting the core Luigi pipeline working first, then fixing the user experience, then validating with the specific snow plow business test case.