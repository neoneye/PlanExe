# Frontend-Backend Integration Audit

**Author**: Claude Code using Sonnet 4
**Date**: 2025-09-26
**Purpose**: Comprehensive audit of PlanExe frontend-backend integration issues and remediation plan

---

## 🚨 Executive Summary

A thorough examination of the PlanExe system reveals **critical compatibility issues** between the Next.js frontend and FastAPI backend that render the system **non-functional** despite having a solid Luigi pipeline. The issues stem from:

1. **Schema violations** in FastAPI endpoints not matching their declared Pydantic models
2. **Missing critical endpoints** expected by frontend components
3. **Enum mismatches** between frontend and backend
4. **Documentation inaccuracies** that mislead development

**Status**: The Luigi pipeline (61 tasks) is solid and functional. The FastAPI-Frontend integration is broken.

---

## 🔍 Detailed Findings

### 1. Schema Violations in FastAPI Endpoints

#### `/api/models` Endpoint
**Problem**: Endpoint returns incompatible schema
```python
# Current FastAPI response:
{
    "id": config.model_id,
    "name": config.model_name,           # ❌ Should be "label"
    "provider": config.provider,         # ❌ Not in schema
    "description": f"{config.provider} - {config.model_name}"  # ❌ Should be "comment"
}

# Expected Pydantic LLMModel schema:
{
    "id": str,
    "label": str,                        # ✅ Missing
    "comment": str,                      # ✅ Missing
    "priority": int,                     # ✅ Missing
    "requires_api_key": bool            # ✅ Missing
}
```

#### `/api/prompts` Endpoint
**Problem**: Endpoint returns incompatible schema
```python
# Current FastAPI response:
{
    "title": prompt.title,
    "description": prompt.description,   # ❌ Not in schema
    "prompt": prompt.prompt,
    "category": getattr(prompt, 'category', 'general')  # ❌ Not in schema
}

# Expected Pydantic PromptExample schema:
{
    "uuid": str,                         # ✅ Missing
    "prompt": str,
    "title": Optional[str]
}
```

#### `/api/plans/{id}/files` Endpoint
**Problem**: Endpoint returns complex objects instead of simple schema
```python
# Current FastAPI response:
{
    "plan_id": plan_id,
    "files": [
        {
            "filename": f.filename,       # ❌ Should be simple string list
            "file_type": f.file_type,     # ❌ Not in schema
            "file_size_bytes": f.file_size_bytes,  # ❌ Not in schema
            "generated_by_stage": f.generated_by_stage,  # ❌ Not in schema
            "created_at": f.created_at    # ❌ Not in schema
        }
    ]
}

# Expected Pydantic PlanFilesResponse schema:
{
    "plan_id": str,
    "files": List[str],                  # ✅ Simple filename strings
    "has_report": bool                   # ✅ Missing
}
```

### 2. Missing Critical API Endpoints

#### `/api/plans/{id}/details` - Expected by PipelineDetails Component
```typescript
// planexe-frontend/src/components/PipelineDetails.tsx:51
const response = await fetch(`http://localhost:8000/api/plans/${planId}/details`)
```
**Status**: ❌ **ENDPOINT DOES NOT EXIST**

#### `/api/plans/{id}/stream-status` - Expected by Terminal Component
```typescript
// planexe-frontend/src/components/monitoring/Terminal.tsx:58
const response = await fetch(`http://localhost:8000/api/plans/${planId}/stream-status`);
```
**Status**: ❌ **ENDPOINT DOES NOT EXIST**

### 3. Enum Mismatches

#### SpeedVsDetail Enum Alignment
```typescript
// Frontend expects:
speed_vs_detail: 'fast_but_skip_details' | 'balanced_speed_and_detail' | 'all_details_but_slow'

// Backend Pydantic model defines:
class SpeedVsDetail(str, Enum):
    ALL_DETAILS_BUT_SLOW = "all_details_but_slow"           # ✅ Match
    BALANCED_SPEED_AND_DETAIL = "balanced_speed_and_detail"  # ✅ Match
    FAST_BUT_BASIC = "fast_but_skip_details"                # ❌ Wrong value name
```

### 4. Documentation Inaccuracies

#### Task Count Error
```markdown
# docs/CODEBASE-INDEX.md claims:
"Luigi pipeline with **61 interconnected tasks**"

# Actual count in run_plan_pipeline.py:
62 Luigi Task classes found (StartTimeTask through HandleTaskCompletionParameters)
```

#### Port Reference Inconsistencies
- Some docs mention port 8000, others 8001, actual is 8080 for Railway
- Development vs production port handling is inconsistent across documentation

---

## 🛠️ Remediation Plan

### Phase 1: Fix FastAPI Schema Compliance (Critical)

#### 1.1 Fix `/api/models` Endpoint
```python
# planexe_api/api.py:159-174
@app.get("/api/models", response_model=List[LLMModel])
async def get_models():
    models = []
    for model_id, config in planexe_llmconfig.llm_config_dict.items():
        model = LLMModel(
            id=model_id,
            label=config.get("comment", model_id),           # Fix: use comment as label
            comment=config.get("comment", ""),               # Fix: add comment field
            priority=config.get("priority", 999),           # Fix: add priority field
            requires_api_key=config.get("provider") != "openai"  # Fix: determine based on provider
        )
        models.append(model)
    return models
```

#### 1.2 Fix `/api/prompts` Endpoint
```python
# planexe_api/api.py:177-193
@app.get("/api/prompts", response_model=List[PromptExample])
async def get_prompts():
    examples = []
    for i, prompt in enumerate(prompt_catalog.prompts):
        example = PromptExample(
            uuid=f"prompt_{i}",                              # Fix: generate UUID
            prompt=prompt.prompt,
            title=prompt.title                               # Fix: only include schema fields
        )
        examples.append(example)
    return examples
```

#### 1.3 Fix `/api/plans/{id}/files` Endpoint
```python
# planexe_api/api.py:321-348
@app.get("/api/plans/{plan_id}/files", response_model=PlanFilesResponse)
async def get_plan_files(plan_id: str, db: DatabaseService = Depends(get_database)):
    plan = db.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    files = db.get_plan_files(plan_id)
    filenames = [f.filename for f in files]                  # Fix: extract just filenames

    # Check if HTML report exists
    report_path = Path(plan.output_dir) / "999-final-report.html"
    has_report = report_path.exists()                        # Fix: add has_report field

    return PlanFilesResponse(
        plan_id=plan_id,
        files=filenames,                                     # Fix: simple string list
        has_report=has_report                                # Fix: boolean flag
    )
```

#### 1.4 Fix SpeedVsDetail Enum
```python
# planexe_api/models.py:22-27
class SpeedVsDetail(str, Enum):
    ALL_DETAILS_BUT_SLOW = "all_details_but_slow"
    BALANCED_SPEED_AND_DETAIL = "balanced_speed_and_detail"
    FAST_BUT_SKIP_DETAILS = "fast_but_skip_details"         # Fix: change from fast_but_basic
```

### Phase 2: Implement Missing Endpoints (Critical)

#### 2.1 Add `/api/plans/{id}/details` Endpoint
```python
class PipelineDetailsResponse(BaseModel):
    plan_id: str
    run_directory: str
    pipeline_stages: List[Dict[str, Any]]
    pipeline_log: str
    generated_files: List[Dict[str, Any]]
    total_files: int

@app.get("/api/plans/{plan_id}/details", response_model=PipelineDetailsResponse)
async def get_plan_details(plan_id: str, db: DatabaseService = Depends(get_database)):
    plan = db.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Implementation needed: Read pipeline stage files, logs, etc.
    return PipelineDetailsResponse(...)
```

#### 2.2 Add `/api/plans/{id}/stream-status` Endpoint
```python
class StreamStatusResponse(BaseModel):
    status: str
    ready: bool

@app.get("/api/plans/{plan_id}/stream-status", response_model=StreamStatusResponse)
async def get_stream_status(plan_id: str, db: DatabaseService = Depends(get_database)):
    plan = db.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Check if SSE stream is ready
    is_ready = plan.status in ['running', 'completed', 'failed']

    return StreamStatusResponse(
        status="ready" if is_ready else "not_ready",
        ready=is_ready
    )
```

### Phase 3: Update Documentation (Medium Priority)

#### 3.1 Fix CODEBASE-INDEX.md
- Correct task count: 61 → 62 Luigi tasks
- Standardize port references (8080 for Railway, 8000 for dev)
- Update architecture diagrams

#### 3.2 Update HOW-THIS-ACTUALLY-WORKS.md
- Clarify development vs production port usage
- Fix any remaining port inconsistencies

### Phase 4: Frontend Type Safety (Low Priority)

#### 4.1 Verify Frontend TypeScript Types
- Ensure frontend types match corrected backend schemas
- Add runtime validation for API responses

#### 4.2 End-to-End Testing
- Test complete plan creation workflow
- Verify SSE streaming functionality
- Test file download capabilities

---

## 🧪 Testing Strategy

### 1. Schema Validation Testing
```bash
# Test each endpoint returns correct schema
curl http://localhost:8080/api/models | jq '.[0] | keys'
# Should return: ["comment", "id", "label", "priority", "requires_api_key"]

curl http://localhost:8080/api/prompts | jq '.[0] | keys'
# Should return: ["prompt", "title", "uuid"]

curl http://localhost:8080/api/plans/{id}/files | jq 'keys'
# Should return: ["files", "has_report", "plan_id"]
```

### 2. Missing Endpoint Testing
```bash
# These should return 200, not 404
curl http://localhost:8080/api/plans/{id}/details
curl http://localhost:8080/api/plans/{id}/stream-status
```

### 3. End-to-End Frontend Testing
1. Create a plan via frontend form
2. Monitor real-time progress
3. View pipeline details
4. Download generated files
5. Access HTML report

---

## 🎯 Success Criteria

✅ **Phase 1 Complete When:**
- All `/api/models`, `/api/prompts`, `/api/plans/{id}/files` endpoints return schema-compliant responses
- Frontend can successfully call all existing endpoints without type errors

✅ **Phase 2 Complete When:**
- Missing endpoints `/api/plans/{id}/details` and `/api/plans/{id}/stream-status` are implemented
- Frontend components (PipelineDetails, Terminal) can successfully fetch data

✅ **Phase 3 Complete When:**
- Documentation accurately reflects the system architecture
- Port numbers are consistent across all docs

✅ **Phase 4 Complete When:**
- Complete plan creation and monitoring workflow works end-to-end
- Real-time progress streaming is functional
- File downloads work correctly

---

## 📋 Implementation Order

1. **CRITICAL**: Fix schema violations (Phase 1) - System is non-functional without this
2. **CRITICAL**: Implement missing endpoints (Phase 2) - Frontend components fail without this
3. **MEDIUM**: Update documentation (Phase 3) - Prevents future confusion
4. **LOW**: End-to-end testing (Phase 4) - Validates the fixes work correctly

**Estimated Time**: 2-3 hours for critical fixes, 1 hour for documentation updates

---

*This audit confirms that while the Luigi pipeline is robust and functional, the FastAPI-Frontend integration layer has fundamental schema compliance and missing endpoint issues that must be resolved for system functionality.*