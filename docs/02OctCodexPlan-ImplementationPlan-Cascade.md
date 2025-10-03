# Implementation Plan: Graceful Report Assembly with Database Fallback
**Author**: Cascade (Codex working through Windsurf IDE)  
**Date**: 2025-10-02T22:46:59-04:00  
**Based On**: `02OctCodexPlan.md` by Codex  
**PURPOSE**: Detailed implementation roadmap for enabling graceful degradation in Luigi pipeline report assembly, leveraging the database-first architecture from v0.3.0 to deliver coherent business plans even when some tasks fail.

## Executive Summary

### The Problem
Currently, the Luigi pipeline's `ReportTask` operates in **all-or-nothing mode**: if any of the 61 upstream tasks fails, the entire report generation crashes, leaving users with zero output despite potentially having 50+ successful task results stored in the database.

### The Solution  
Implement a **database-first report assembler** that:
1. Queries the `plan_content` table for all available task outputs
2. Builds a complete report from available sections
3. Documents missing sections in a "Further Research Required" appendix
4. Always produces a deliverable HTML report

### Why This is the Right Approach
- ✅ **Leverages v0.3.0 refactor**: All 61 tasks already write to `plan_content` table
- ✅ **Railway-compatible**: Database survives pod restarts, filesystem doesn't
- ✅ **User-first**: Delivers value from partial results vs. total failure
- ✅ **Minimal risk**: Changes isolated to report assembly, not core pipeline
- ✅ **Incremental**: Can implement in phases with clear rollback points

## Assessment: Is This a Good Plan? 

### ✅ **YES - This is an excellent plan for the following reasons:**

1. **Root Cause Analysis is Correct**
   - Problem: Late-stage failures in tasks like `FindTeamMembers`, `WBS`, or `SWOT` crash the entire pipeline
   - Reality: These failures leave 50+ successful task outputs orphaned in the database
   - Impact: Users get NOTHING despite 90%+ of work being completed

2. **Leverages Existing Architecture**
   - The v0.3.0 refactor (per CHANGELOG.md) already modified all 61 tasks to write to `plan_content`
   - We're not changing the pipeline - just making report assembly resilient
   - Database-first approach matches Railway's ephemeral filesystem reality

3. **Clear Success Criteria**
   - User gets a complete report with available sections
   - Missing sections are clearly documented in appendix
   - Report includes machine-readable `missing_components.json` for downstream tools
   - UI can display partial completion status

4. **Appropriate Scope**
   - NOT modifying 61 Luigi tasks (too risky)
   - NOT changing database schema (already correct)
   - ONLY modifying report assembly logic (contained risk)

## Implementation Phases

### Phase 1: Create ReportAssembler Utility (FOUNDATION)
**Risk**: Low  
**Duration**: 2-3 hours  
**Dependencies**: None

#### Files to Create
1. **`planexe/report/report_assembler.py`** - New utility class

#### What It Does
```python
class ReportAssembler:
    """
    Assembles final report from plan_content table with graceful degradation.
    """
    
    def __init__(self, plan_id: str, db_service: DatabaseService):
        self.plan_id = plan_id
        self.db = db_service
        
    def get_available_sections(self) -> OrderedSectionList:
        """
        Query plan_content for all available task outputs.
        Returns ordered list of (task_name, content, content_type).
        """
        
    def get_missing_sections(self, expected_tasks: List[str]) -> List[MissingSection]:
        """
        Compare expected tasks from FilenameEnum vs actual plan_content records.
        Returns list of missing sections with metadata.
        """
        
    def assemble_report(self) -> AssembledReport:
        """
        Build complete report structure:
        - HTML body from available sections
        - "Further Research Required" appendix for missing sections
        - Metadata: completion %, missing task names, timestamps
        """
```

#### Implementation Details

**Step 1.1**: Define expected task order
- Read task sequence from `FilenameEnum` or Luigi dependency graph
- Create ordered list of all 61 expected outputs

**Step 1.2**: Query database for available content
```python
available = db.get_plan_content_by_plan_id(plan_id)
# Returns: [(filename, content, content_type, created_at), ...]
```

**Step 1.3**: Build section mapping
```python
sections = OrderedDict()
missing = []

for expected_filename in EXPECTED_FILES:
    if expected_filename in available:
        sections[expected_filename] = available[expected_filename]
    else:
        missing.append({
            'filename': expected_filename,
            'task_name': filename_to_task_name(expected_filename),
            'stage': determine_stage(expected_filename)
        })
```

**Step 1.4**: Return structured result
```python
return AssembledReport(
    sections=sections,           # Available content
    missing=missing,             # Missing sections metadata
    completion_pct=len(sections) / 61 * 100,
    generated_at=datetime.now()
)
```

#### Testing Strategy
- Unit test with mock database containing partial results
- Test cases:
  1. All 61 sections present (100% completion)
  2. First 30 sections only (early pipeline failure)
  3. Random gaps (e.g., missing SWOT but have WBS)
  4. Only first 5 sections (very early failure)

---

### Phase 2: Refactor ReportTask for Graceful Degradation (CORE CHANGE)
**Risk**: Medium  
**Duration**: 3-4 hours  
**Dependencies**: Phase 1 complete

#### Files to Modify
1. **`planexe/plan/run_plan_pipeline.py`** - Modify `ReportTask.run_inner()`

#### Current Behavior (BRITTLE)
```python
class ReportTask(PlanTask):
    def run_inner(self):
        # Assumes ALL prerequisite files exist
        generator = ReportGenerator(self.run_id_dir)
        
        # Hard failures if ANY file missing
        premise = self.input()[0].path  # FileNotFoundError if missing
        purpose = self.input()[1].path  # FileNotFoundError if missing
        # ... 59 more required inputs ...
        
        html = generator.generate(premise, purpose, ...)  # Crashes on None
        self.output().path.write_text(html)
```

#### New Behavior (RESILIENT)
```python
class ReportTask(PlanTask):
    def run_inner(self):
        from planexe.report.report_assembler import ReportAssembler
        
        # Phase 1: Query database for available sections
        db = get_database_service()
        assembler = ReportAssembler(self.plan_id, db)
        assembled = assembler.assemble_report()
        
        # Phase 2: Generate report from available sections
        generator = ReportGenerator(self.run_id_dir)
        
        # Pass sections dict - generator handles None values gracefully
        html = generator.generate_from_sections(
            sections=assembled.sections,
            missing=assembled.missing,
            completion_pct=assembled.completion_pct
        )
        
        # Phase 3: Persist report (database + filesystem)
        db.save_plan_content(
            plan_id=self.plan_id,
            task_name='ReportTask',
            content=html,
            content_type='html'
        )
        
        # Persist missing components for API access
        db.save_plan_content(
            plan_id=self.plan_id,
            task_name='MissingComponents',
            content=json.dumps(assembled.missing, indent=2),
            content_type='json'
        )
        
        # Filesystem write for Luigi dependency tracking
        self.output().path.write_text(html)
```

#### Key Changes

**Change 2.1**: Remove hard dependencies on `self.input()` array
- OLD: `premise = self.input()[0].path` → crashes if file missing
- NEW: `premise = assembled.sections.get('003-premise.md')` → None if missing

**Change 2.2**: Modify `ReportGenerator.generate()` signature
```python
# OLD signature (brittle)
def generate(self, premise: str, purpose: str, ...) -> str:
    # Assumes all args are valid strings

# NEW signature (resilient)
def generate_from_sections(
    self, 
    sections: OrderedDict[str, Optional[str]],
    missing: List[MissingSection],
    completion_pct: float
) -> str:
    # Handles None values gracefully
```

**Change 2.3**: Add placeholder rendering for missing sections
```python
def render_section(self, section_name: str, content: Optional[str]) -> str:
    if content is None:
        return f"""
        <div class="missing-section">
            <h3>{section_name}</h3>
            <p><em>This section was not generated. See appendix for details.</em></p>
        </div>
        """
    return content
```

**Change 2.4**: Generate "Further Research Required" appendix
```python
def render_missing_appendix(self, missing: List[MissingSection]) -> str:
    html = "<h2>Further Research Required</h2>\n"
    html += "<p>The following sections could not be generated:</p>\n"
    html += "<table>\n"
    
    for item in missing:
        html += f"""
        <tr>
            <td>{item['task_name']}</td>
            <td>{item['stage']}</td>
            <td>{item['filename']}</td>
        </tr>
        """
    
    html += "</table>\n"
    html += "<p>These sections can be regenerated by re-running the pipeline.</p>\n"
    return html
```

#### Testing Strategy
- Integration test: Manually delete key intermediate files before `ReportTask`
- Scenarios:
  1. Delete `042-team-members.json` → should render with placeholder
  2. Delete `049-wbs-level1.json` → should document in appendix
  3. Delete `047-swot.json` → should continue to final report

---

### Phase 3: Expose Missing-Stage Metadata via API (UI INTEGRATION)
**Risk**: Low  
**Duration**: 1-2 hours  
**Dependencies**: Phase 2 complete

#### Files to Modify
1. **`planexe_api/api.py`** - Add endpoint + modify existing endpoint

#### New Endpoint: Get Plan Details with Completion Info
```python
@app.get("/api/plans/{plan_id}/details")
async def get_plan_details(plan_id: str) -> PlanDetailsResponse:
    """
    Returns plan with completion metadata and missing sections.
    """
    plan = db.get_plan(plan_id)
    
    # Fetch missing components from database
    missing_json = db.get_plan_content(plan_id, 'MissingComponents')
    missing = json.loads(missing_json) if missing_json else []
    
    return PlanDetailsResponse(
        plan=plan,
        completion_pct=calculate_completion(plan_id),
        missing_sections=missing,
        available_sections=get_available_section_names(plan_id)
    )
```

#### Modified Endpoint: Update Plan Summary
```python
@app.get("/api/plans/{plan_id}")
async def get_plan(plan_id: str) -> PlanResponse:
    """
    Existing endpoint - add completion info to response.
    """
    plan = db.get_plan(plan_id)
    
    # NEW: Add completion metadata
    completion = calculate_completion(plan_id)
    missing = get_missing_section_count(plan_id)
    
    return PlanResponse(
        **plan.dict(),
        completion_pct=completion,
        missing_section_count=missing,
        status=determine_status(plan, completion)  # 'complete', 'partial', 'failed'
    )
```

#### Helper Functions
```python
def calculate_completion(plan_id: str) -> float:
    """Count available sections vs. expected 61 tasks."""
    available = db.count_plan_content(plan_id)
    return (available / 61) * 100

def determine_status(plan: Plan, completion: float) -> str:
    """
    - 'complete': 100% completion
    - 'partial': 50-99% completion
    - 'failed': <50% completion
    """
    if completion == 100:
        return 'complete'
    elif completion >= 50:
        return 'partial'
    else:
        return 'failed'
```

#### API Response Schema Updates
```python
class PlanDetailsResponse(BaseModel):
    plan: Plan
    completion_pct: float
    missing_sections: List[MissingSectionInfo]
    available_sections: List[str]

class MissingSectionInfo(BaseModel):
    task_name: str
    stage: str
    filename: str
    expected_after: Optional[str]  # Prerequisite task name
```

---

### Phase 4: Update UI for Partial Completion Display (USER EXPERIENCE)
**Risk**: Low  
**Duration**: 2-3 hours  
**Dependencies**: Phase 3 complete

#### Files to Modify
1. **`planexe-frontend/src/components/PlansQueue.tsx`** - Add completion badge
2. **`planexe-frontend/src/components/PlanDetails.tsx`** - Show missing sections

#### Change 4.1: PlansQueue - Add Completion Badge
```tsx
// Current: Only shows "Completed" or "Running"
<Badge>{plan.status}</Badge>

// New: Show completion percentage for partial results
{plan.status === 'partial' && (
  <Badge variant="warning">
    {plan.completion_pct.toFixed(0)}% Complete
  </Badge>
)}
```

#### Change 4.2: PlanDetails - Show Missing Sections
```tsx
function PlanDetails({ planId }: { planId: string }) {
  const { data: details } = useQuery(
    ['plan-details', planId],
    () => api.getPlanDetails(planId)
  );

  return (
    <div>
      <h2>Plan Details</h2>
      
      {/* Completion Summary */}
      <Card>
        <h3>Completion Status</h3>
        <Progress value={details.completion_pct} />
        <p>{details.completion_pct.toFixed(1)}% complete</p>
      </Card>
      
      {/* Missing Sections (if any) */}
      {details.missing_sections.length > 0 && (
        <Card>
          <h3>Further Research Required</h3>
          <Alert variant="warning">
            <AlertTitle>Incomplete Sections</AlertTitle>
            <AlertDescription>
              {details.missing_sections.length} sections could not be generated.
            </AlertDescription>
          </Alert>
          
          <Accordion>
            {details.missing_sections.map(section => (
              <AccordionItem key={section.filename}>
                <AccordionTrigger>{section.task_name}</AccordionTrigger>
                <AccordionContent>
                  <p><strong>Stage:</strong> {section.stage}</p>
                  <p><strong>File:</strong> {section.filename}</p>
                  <Button onClick={() => retrySection(planId, section.task_name)}>
                    Retry This Section
                  </Button>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </Card>
      )}
      
      {/* Available Sections */}
      <Card>
        <h3>Available Sections ({details.available_sections.length}/61)</h3>
        <ul>
          {details.available_sections.map(name => (
            <li key={name}>✅ {name}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
```

#### Change 4.3: Add "Retry Failed Sections" Button
```tsx
async function retryFailedSections(planId: string) {
  // Call new API endpoint to re-run only missing tasks
  await api.retryPartialPlan(planId);
}
```

---

### Phase 5 (Optional): Agent-Orchestrated Recovery (ADVANCED)
**Risk**: Low (optional feature)  
**Duration**: 4-6 hours  
**Dependencies**: Phases 1-4 complete

This phase is **optional** and can be deferred to future iterations.

#### Concept
Use `.agents/luigi_master_orchestrator.ts` to:
1. Inspect the `missing_components.json` file
2. Propose remediation strategies (e.g., "SWOT task failed due to missing team data")
3. Generate user-friendly guidance in the report appendix

#### Implementation Sketch
```typescript
// .agents/report_recovery_agent.ts
export async function proposeRecovery(missingComponents: MissingSection[]): Promise<string> {
  const guidance: string[] = [];
  
  for (const missing of missingComponents) {
    if (missing.task_name === 'SWOTAnalysisTask') {
      guidance.push(`
        SWOT analysis could not be completed.
        Suggestion: Ensure team member data is available before re-running.
      `);
    }
    // ... more task-specific recovery suggestions
  }
  
  return guidance.join('\n\n');
}
```

---

## Implementation Checklist

### Pre-Implementation
- [ ] Review v0.3.0 database schema to confirm `plan_content` structure
- [ ] Backup current `run_plan_pipeline.py` before modifications
- [ ] Create feature branch: `feature/graceful-report-assembly`

### Phase 1: ReportAssembler
- [ ] Create `planexe/report/report_assembler.py`
- [ ] Implement `get_available_sections()`
- [ ] Implement `get_missing_sections()`
- [ ] Implement `assemble_report()`
- [ ] Write unit tests for all methods
- [ ] Test with mock database (100%, 50%, 10% completion scenarios)

### Phase 2: ReportTask Refactor
- [ ] Modify `ReportTask.run_inner()` to use ReportAssembler
- [ ] Update `ReportGenerator.generate()` to handle None values
- [ ] Implement placeholder rendering for missing sections
- [ ] Implement appendix generation for missing sections
- [ ] Test by deleting intermediate files before ReportTask
- [ ] Verify HTML report includes appendix when sections missing

### Phase 3: API Endpoints
- [ ] Add `/api/plans/{id}/details` endpoint
- [ ] Modify `/api/plans/{id}` to include completion metadata
- [ ] Implement `calculate_completion()` helper
- [ ] Implement `determine_status()` helper
- [ ] Update API response schemas (Pydantic models)
- [ ] Test endpoints with curl/Postman

### Phase 4: UI Updates
- [ ] Update `PlansQueue.tsx` with completion badges
- [ ] Create `PlanDetails.tsx` component for detailed view
- [ ] Add missing sections accordion
- [ ] Add "Retry Failed Sections" button
- [ ] Style partial completion states (colors, badges)
- [ ] Test UI with partial plans

### Phase 5 (Optional): Agent Recovery
- [ ] Create `report_recovery_agent.ts`
- [ ] Implement task-specific recovery suggestions
- [ ] Integrate with ReportGenerator appendix
- [ ] Test with common failure scenarios

### Testing & Validation
- [ ] Run full pipeline with all sections succeeding (100%)
- [ ] Manually delete WBS files, verify report still generates
- [ ] Manually delete team files, verify appendix documents missing sections
- [ ] Verify Railway deployment (database persistence)
- [ ] User acceptance testing with partial results

### Documentation
- [ ] Update `CHANGELOG.md` with this feature
- [ ] Document ReportAssembler API in `docs/`
- [ ] Update `README_API.md` with new endpoints
- [ ] Add troubleshooting section for partial completions

---

## Risk Analysis

### Low Risk ✅
- **Phase 1** (ReportAssembler): New utility, no modifications to existing code
- **Phase 3** (API): Additive changes, no breaking modifications
- **Phase 4** (UI): Only frontend changes, no backend impact

### Medium Risk ⚠️
- **Phase 2** (ReportTask): Modifies core Luigi pipeline task
  - Mitigation: Extensive testing with backup/rollback plan
  - Mitigation: Feature flag to enable/disable new behavior

### High Risk ❌
- **None** - This plan deliberately avoids high-risk changes

### Rollback Strategy
If Phase 2 causes issues:
1. Revert `ReportTask.run_inner()` to original implementation
2. Keep ReportAssembler for future use
3. File detailed bug report with logs
4. Resume with v0.3.0 behavior

---

## Success Metrics

### Technical Success
- ✅ Report generated even when 10+ tasks fail
- ✅ Database `plan_content` queried as primary source
- ✅ HTML report includes "Further Research Required" appendix
- ✅ `missing_components.json` accessible via API

### User Success
- ✅ Users receive deliverable plan from partial results
- ✅ UI clearly communicates completion percentage
- ✅ Users understand which sections are missing and why
- ✅ Users can retry failed sections

### Operational Success
- ✅ Railway deployments survive pod restarts (database-first)
- ✅ No increase in pipeline crashes
- ✅ Error logs contain clear diagnostics for missing sections

---

## Timeline Estimate

| Phase | Duration | Complexity |
|-------|----------|-----------|
| Phase 1: ReportAssembler | 2-3 hours | Low |
| Phase 2: ReportTask Refactor | 3-4 hours | Medium |
| Phase 3: API Endpoints | 1-2 hours | Low |
| Phase 4: UI Updates | 2-3 hours | Low |
| Phase 5: Agent Recovery (Optional) | 4-6 hours | Low |
| **Testing & Documentation** | 3-4 hours | - |
| **TOTAL (without Phase 5)** | **11-16 hours** | - |
| **TOTAL (with Phase 5)** | **15-22 hours** | - |

**Recommended Approach**: Implement Phases 1-4 first, validate with users, then optionally add Phase 5.

---

## Final Recommendation

### ✅ **APPROVE THIS PLAN**

**Rationale:**
1. **Addresses Real User Pain**: Current all-or-nothing behavior wastes successful work
2. **Low Risk Implementation**: Changes isolated to report assembly layer
3. **Leverages Existing Work**: v0.3.0 database-first refactor enables this
4. **Incremental Delivery**: Can ship Phase 1-3 without Phase 4 if needed
5. **Clear Success Criteria**: Easy to verify completion and rollback if needed

**Next Steps:**
1. Get user approval on this implementation plan
2. Create feature branch: `feature/graceful-report-assembly`
3. Start with Phase 1 (ReportAssembler) - lowest risk, highest value
4. Proceed systematically through phases with testing at each step

---

## Questions for User Before Proceeding

1. **Testing Strategy**: Do you want me to use existing old plans in `D:\1Projects\PlanExe\run` for testing, or create new test scenarios?

2. **Feature Flag**: Should we add a feature flag to enable/disable graceful degradation, or go all-in?

3. **Phase 5 (Optional)**: Do you want agent-orchestrated recovery in the initial implementation, or defer it?

4. **UI Priority**: Is the UI update (Phase 4) critical, or can we ship with API-only initially?

5. **Rollback Plan**: Do you want a feature flag for easy rollback, or are you comfortable with git revert?

---

## Approval Required

**Do you approve proceeding with this implementation plan?**

If yes, I will:
1. Create feature branch
2. Start with Phase 1 (ReportAssembler)
3. Provide progress updates at each phase completion
4. Request approval before modifying `ReportTask` (Phase 2 - medium risk)

Please confirm before I begin code changes.
