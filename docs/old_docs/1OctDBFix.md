/**
 * Author: Cascade using Claude 3.5 Sonnet
 * Date: 2025-09-30T21:29:26-04:00
 * PURPOSE: Complete task list for Option 1 - Database-first architecture refactor
 * SRP and DRY check: Pass - Single responsibility for documenting the proper database integration
 */

# Option 1: Database-First Architecture Refactor

## **Executive Summary**

**Problem**: Luigi pipeline writes all outputs to ephemeral filesystem. Files lost on Railway restart.

**Current State**: Files synced to database AFTER pipeline completion (band-aid fix).

**Target State**: Every Luigi task writes to database DURING execution (proper fix).

**Estimated Effort**: 40-60 hours (8-12 days at 5 hours/day)

**Risk Level**: HIGH - Touches 61 Luigi tasks, core pipeline architecture

---

## **🎯 Goals**

### **Primary Goals**
1. ✅ All plan content persisted to database during generation
2. ✅ LLM interactions tracked in `llm_interactions` table
3. ✅ Files still written to filesystem for Luigi dependency tracking
4. ✅ Zero data loss on Railway restarts
5. ✅ Historical plan retrieval from database

### **Secondary Goals**
1. ✅ Cost tracking (token usage per task)
2. ✅ Performance metrics (duration per task)
3. ✅ Content versioning (track iterations)
4. ✅ Audit trail (who generated what, when)

---

## **📊 Current Architecture**

### **How Luigi Tasks Work Now**

```python
class WBSLevel1Task(PlanTask):
    def requires(self):
        return [PreviousTask(...)]  # Luigi dependency
    
    def output(self):
        return self.local_target(FilenameEnum.WBS_LEVEL1)  # File path
    
    def run_inner(self):
        # 1. Generate content using LLM
        content = self.generate_wbs()
        
        # 2. Write to file (ONLY storage)
        with self.output().open("w") as f:
            f.write(json.dumps(content))
        
        # 3. NO DATABASE INTERACTION
```

### **Problems**
- ❌ Content only in filesystem (ephemeral)
- ❌ No LLM interaction tracking
- ❌ No cost tracking
- ❌ No audit trail
- ❌ Luigi dependency system relies on file existence

---

## **🏗️ Target Architecture**

### **How Luigi Tasks Should Work**

```python
class WBSLevel1Task(PlanTask):
    def requires(self):
        return [PreviousTask(...)]
    
    def output(self):
        return self.local_target(FilenameEnum.WBS_LEVEL1)  # Still needed for Luigi
    
    def run_inner(self):
        # 1. Get database service
        db_service = self.get_database_service()
        
        # 2. Generate content using LLM (with tracking)
        llm_executor = self.create_llm_executor()
        
        # Track LLM interaction start
        interaction_id = db_service.create_llm_interaction({
            "plan_id": self.get_plan_id(),
            "llm_model": self.llm_models[0],
            "stage": "wbs_level1",
            "prompt_text": prompt,
            "status": "pending"
        }).id
        
        try:
            # 3. Execute LLM call
            content = llm_executor.run(prompt, response_model=WBSLevel1)
            
            # 4. Update LLM interaction with response
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(content.to_dict()),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration,
                "input_tokens": token_counts.input,
                "output_tokens": token_counts.output
            })
            
        except Exception as e:
            # Track failure
            db_service.update_llm_interaction(interaction_id, {
                "status": "failed",
                "error_message": str(e)
            })
            raise
        
        # 5. Persist content to database (PRIMARY storage)
        db_service.create_plan_content({
            "plan_id": self.get_plan_id(),
            "filename": FilenameEnum.WBS_LEVEL1.value,
            "stage": "wbs_level1",
            "content_type": "json",
            "content": json.dumps(content.to_dict()),
            "content_size_bytes": len(json.dumps(content.to_dict()))
        })
        
        # 6. ALSO write to file for Luigi dependency tracking
        with self.output().open("w") as f:
            f.write(json.dumps(content.to_dict()))
```

### **Benefits**
- ✅ Content in database (persistent)
- ✅ LLM interactions tracked
- ✅ Cost tracking automatic
- ✅ Audit trail complete
- ✅ Luigi dependency system still works

---

## **📋 Implementation Task List**

### **Phase 1: Infrastructure Setup** (8 hours)

#### **Task 1.1: Extend Database Schema** (2 hours)
- [x] Add `plan_content` table (DONE in Option 3)
- [ ] Add indexes for performance:
  - `CREATE INDEX idx_plan_content_plan_id ON plan_content(plan_id)`
  - `CREATE INDEX idx_plan_content_filename ON plan_content(plan_id, filename)`
  - `CREATE INDEX idx_llm_interactions_plan_id ON llm_interactions(plan_id)`
- [ ] Add migration script for existing Railway database
- [ ] Test schema changes on local SQLite

#### **Task 1.2: Add Database Service to PlanTask** (3 hours)
- [ ] Add `get_database_service()` method to `PlanTask` base class
- [ ] Add `get_plan_id()` method to extract plan ID from `run_id_dir`
- [ ] Add database session management (open/close)
- [ ] Add error handling for database connection failures
- [ ] Test database access from Luigi tasks

#### **Task 1.3: Extend LLMExecutor for Tracking** (3 hours)
- [ ] Add token counting to `LLMExecutor.run()`
- [ ] Add duration tracking
- [ ] Add callback for database interaction logging
- [ ] Return metadata (tokens, duration) with response
- [ ] Test token counting with OpenAI/OpenRouter

---

### **Phase 2: Refactor Core Tasks** (16 hours)

**Pattern**: Start with simple tasks, move to complex ones

#### **Task 2.1: Refactor File I/O Tasks** (4 hours)
Simple tasks that just write files:
- [ ] `StartTimeTask` - Write timestamp to DB
- [ ] `InitialPlanTask` - Write prompt to DB
- [ ] Test both tasks end-to-end

#### **Task 2.2: Refactor Analysis Tasks** (6 hours)
Tasks with LLM calls:
- [ ] `RedlineGateTask` - Track LLM interaction
- [ ] `PremiseAttackTask` - Track LLM interaction
- [ ] `IdentifyPurposeTask` - Track LLM interaction
- [ ] Test LLM interaction tracking
- [ ] Verify token counts are accurate

#### **Task 2.3: Refactor Strategic Tasks** (6 hours)
Complex tasks with multiple LLM calls:
- [ ] `IdentifyPotentialLeversTask`
- [ ] `EnrichPotentialLeversTask`
- [ ] `FocusOnVitalFewLeversTask`
- [ ] `CandidateScenariosTask`
- [ ] `SelectScenarioTask`
- [ ] Test multi-call tracking

---

### **Phase 3: Refactor Planning Tasks** (12 hours)

#### **Task 3.1: Assumptions Tasks** (4 hours)
- [ ] `MakeAssumptionsTask`
- [ ] `DistillAssumptionsTask`
- [ ] `ReviewAssumptionsTask`
- [ ] `ConsolidateAssumptionsTask`

#### **Task 3.2: Context Tasks** (4 hours)
- [ ] `PhysicalLocationsTask`
- [ ] `CurrencyStrategyTask`
- [ ] `IdentifyRisksTask`
- [ ] `IdentifyPlanTypeTask`

#### **Task 3.3: Planning Tasks** (4 hours)
- [ ] `PreProjectAssessmentTask`
- [ ] `ProjectPlanTask`
- [ ] `GovernancePhase1AuditTask`
- [ ] `GovernancePhase2BodiesTask`
- [ ] `GovernancePhase3ImplPlanTask`
- [ ] `GovernancePhase4DecisionEscalationMatrixTask`
- [ ] `GovernancePhase5MonitoringProgressTask`
- [ ] `GovernancePhase6ExtraTask`

---

### **Phase 4: Refactor Execution Tasks** (12 hours)

#### **Task 4.1: Team Tasks** (4 hours)
- [ ] `FindTeamMembersTask`
- [ ] `EnrichTeamMembersWithContractTypeTask`
- [ ] `EnrichTeamMembersWithBackgroundStoryTask`
- [ ] `EnrichTeamMembersWithEnvironmentInfoTask`
- [ ] `ReviewTeamTask`

#### **Task 4.2: SWOT & Expert Tasks** (4 hours)
- [ ] `SWOTAnalysisTask`
- [ ] `ExpertFinderTask`
- [ ] `ExpertCriticismTask`
- [ ] `ExpertOrchestratorTask`

#### **Task 4.3: WBS Tasks** (4 hours)
- [ ] `CreateWBSLevel1Task`
- [ ] `CreateWBSLevel2Task`
- [ ] `CreateWBSLevel3Task`
- [ ] `IdentifyWBSTaskDependenciesTask`
- [ ] `EstimateWBSTaskDurationsTask`

---

### **Phase 5: Refactor Output Tasks** (8 hours)

#### **Task 5.1: Schedule Tasks** (4 hours)
- [ ] `ProjectSchedulePopulatorTask`
- [ ] `ExportGanttDHTMLXTask`
- [ ] `ExportGanttCSVTask`
- [ ] `ExportGanttMermaidTask`

#### **Task 5.2: Report Tasks** (4 hours)
- [ ] `DataCollectionTask`
- [ ] `ReviewPlanTask`
- [ ] `ExecutiveSummaryTask`
- [ ] `ReportGeneratorTask`
- [ ] `FullPlanPipelineTask`

---

### **Phase 6: Testing & Validation** (8 hours)

#### **Task 6.1: Unit Testing** (3 hours)
- [ ] Test database writes for each task type
- [ ] Test LLM interaction tracking
- [ ] Test token counting accuracy
- [ ] Test error handling (DB connection failures)
- [ ] Test rollback on task failure

#### **Task 6.2: Integration Testing** (3 hours)
- [ ] Run full pipeline end-to-end locally
- [ ] Verify all 61 tasks write to database
- [ ] Verify files still written to filesystem
- [ ] Verify Luigi dependency system still works
- [ ] Check database size (expect ~5-10MB per plan)

#### **Task 6.3: Railway Testing** (2 hours)
- [ ] Deploy to Railway
- [ ] Run test plan
- [ ] Verify database persistence after restart
- [ ] Test file retrieval from database
- [ ] Monitor PostgreSQL performance

---

### **Phase 7: Cleanup & Documentation** (4 hours)

#### **Task 7.1: Remove Option 3 Code** (1 hour)
- [ ] Remove post-completion file sync
- [ ] Update comments
- [ ] Clean up temporary code

#### **Task 7.2: Update Documentation** (2 hours)
- [ ] Update `RAILWAY_BREAKTHROUGH_ANALYSIS.md`
- [ ] Update `run_plan_pipeline_documentation.md`
- [ ] Document new database schema
- [ ] Add migration guide

#### **Task 7.3: Update CHANGELOG** (1 hour)
- [ ] Document Option 1 implementation
- [ ] List all refactored tasks
- [ ] Note breaking changes (if any)

---

## **🚨 Risk Management**

### **High-Risk Areas**

#### **Risk 1: Luigi Dependency System**
**Problem**: Luigi tracks task completion via file existence. If we mess this up, pipeline breaks.

**Mitigation**:
- Always write to filesystem AFTER database write
- Keep `output()` method returning file path
- Test Luigi dependency resolution after each task refactor

#### **Risk 2: Database Performance**
**Problem**: 61 database writes per plan could slow down pipeline.

**Mitigation**:
- Use connection pooling
- Batch writes where possible
- Add database indexes
- Monitor query performance

#### **Risk 3: Database Size Growth**
**Problem**: Storing full plan content could bloat database.

**Mitigation**:
- Compress large text fields
- Archive old plans to cold storage
- Set retention policy (e.g., 90 days)
- Monitor database size on Railway

#### **Risk 4: Backward Compatibility**
**Problem**: Old plans don't have database content.

**Mitigation**:
- Keep filesystem fallback in API endpoints
- Add migration script to backfill old plans
- Document migration process

---

## **📈 Success Metrics**

### **Technical Metrics**
- ✅ 100% of Luigi tasks write to database
- ✅ 100% of LLM interactions tracked
- ✅ 0% data loss on Railway restart
- ✅ <5% pipeline performance degradation
- ✅ Database size <10MB per plan

### **User-Facing Metrics**
- ✅ Historical plans retrievable after restart
- ✅ Cost tracking visible in UI
- ✅ LLM interaction audit trail available
- ✅ No user-facing breaking changes

---

## **🔧 Implementation Guidelines**

### **Code Standards**

#### **Every Refactored Task Must**:
1. Get database service in `run_inner()`
2. Track LLM interactions (if applicable)
3. Write content to database BEFORE filesystem
4. Handle database errors gracefully
5. Include debug logging
6. Update unit tests

#### **Template for Refactored Task**:

```python
def run_inner(self):
    # 1. Get database service
    db_service = self.get_database_service()
    plan_id = self.get_plan_id()
    
    try:
        # 2. Track LLM interaction (if applicable)
        interaction_id = None
        if self.uses_llm:
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": self.llm_models[0],
                "stage": self.stage_name,
                "prompt_text": prompt,
                "status": "pending"
            }).id
        
        # 3. Generate content
        content = self.generate_content()
        
        # 4. Update LLM interaction (if applicable)
        if interaction_id:
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(content),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration,
                "input_tokens": tokens.input,
                "output_tokens": tokens.output
            })
        
        # 5. Persist to database (PRIMARY storage)
        db_service.create_plan_content({
            "plan_id": plan_id,
            "filename": self.output_filename,
            "stage": self.stage_name,
            "content_type": self.content_type,
            "content": content,
            "content_size_bytes": len(content.encode('utf-8'))
        })
        
        # 6. Write to filesystem (for Luigi)
        with self.output().open("w") as f:
            f.write(content)
        
        print(f"DEBUG: {self.stage_name} - Content persisted to database")
        
    except Exception as e:
        # Track failure
        if interaction_id:
            db_service.update_llm_interaction(interaction_id, {
                "status": "failed",
                "error_message": str(e)
            })
        print(f"ERROR: {self.stage_name} - Database write failed: {e}")
        raise
    finally:
        db_service.close()
```

---

## **📅 Recommended Schedule**

### **Week 1: Infrastructure** (40 hours)
- Days 1-2: Phase 1 (Infrastructure Setup)
- Days 3-4: Phase 2 (Core Tasks)
- Day 5: Testing & validation

### **Week 2: Planning & Execution** (40 hours)
- Days 1-2: Phase 3 (Planning Tasks)
- Days 3-4: Phase 4 (Execution Tasks)
- Day 5: Testing & validation

### **Week 3: Output & Polish** (20 hours)
- Days 1-2: Phase 5 (Output Tasks)
- Day 3: Phase 6 (Testing & Validation)
- Day 4: Phase 7 (Cleanup & Documentation)
- Day 5: Railway deployment & monitoring

**Total**: ~100 hours (2.5 weeks full-time)

---

## **🎯 Quick Wins (Do These First)**

If you want to see immediate value before full refactor:

### **Quick Win 1: Track LLM Interactions** (4 hours)
- Modify `LLMExecutor` to log all interactions
- Don't refactor tasks yet
- Immediate cost tracking visibility

### **Quick Win 2: Persist Final Report** (2 hours)
- Only persist `999-final-report.html` to database
- Users can always download final report
- Minimal code changes

### **Quick Win 3: Add Railway Volume** (1 hour)
- Mount persistent storage for `/app/run/`
- No code changes needed
- Buys time for proper refactor

---

## **💰 Cost Analysis**

### **Development Cost**
- **Option 3 (Current)**: 4 hours (DONE)
- **Option 1 (This Plan)**: 100 hours
- **Cost Difference**: 96 hours (~$10,000 at $100/hour)

### **Operational Cost**
- **Database Storage**: ~10MB per plan × 100 plans = 1GB (~$0.10/month)
- **Railway Volume**: 10GB = ~$2.50/month
- **PostgreSQL**: Included in Railway plan

### **ROI**
- **Value**: Zero data loss, full audit trail, cost tracking
- **Break-even**: After ~10 lost plans (user frustration avoided)

---

## **🚀 Deployment Strategy**

### **Staged Rollout**

#### **Stage 1: Canary (10% of tasks)**
- Refactor 6 simple tasks
- Deploy to Railway
- Monitor for 1 week
- Rollback if issues

#### **Stage 2: Beta (50% of tasks)**
- Refactor 30 more tasks
- Deploy to Railway
- Monitor for 1 week
- Rollback if issues

#### **Stage 3: Full (100% of tasks)**
- Refactor remaining 25 tasks
- Deploy to Railway
- Monitor for 2 weeks
- Declare success

---

## **📞 Support & Escalation**

### **If Things Go Wrong**

#### **Database Connection Failures**
1. Check Railway PostgreSQL status
2. Verify `DATABASE_URL` environment variable
3. Check connection pool exhaustion
4. Rollback to Option 3 if critical

#### **Pipeline Performance Degradation**
1. Check database query performance
2. Add missing indexes
3. Batch database writes
4. Consider async writes

#### **Data Inconsistency**
1. Compare database vs filesystem
2. Check for partial writes
3. Add transaction rollback
4. Re-sync from filesystem

---

## **✅ Definition of Done**

### **This refactor is complete when**:
1. ✅ All 61 Luigi tasks write to database
2. ✅ All LLM interactions tracked
3. ✅ Full pipeline runs successfully
4. ✅ Railway restart doesn't lose data
5. ✅ Historical plans retrievable
6. ✅ Unit tests pass
7. ✅ Integration tests pass
8. ✅ Railway deployment successful
9. ✅ Documentation updated
10. ✅ CHANGELOG updated

---

**Ready to start? Begin with Phase 1, Task 1.1!**
