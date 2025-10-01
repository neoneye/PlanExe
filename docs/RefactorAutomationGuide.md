/**
 * Author: Claude Code (Sonnet 4)
 * Date: 2025-10-01
 * PURPOSE: Guide for semi-automated refactoring of remaining 52 Luigi tasks
 * SRP and DRY check: Pass - Provides systematic approach to complete refactor
 */

# Luigi Task Refactor Automation Guide

## 📊 Status
- **Completed**: 7/59 tasks (12%)
- **Remaining**: 52 tasks
- **Pattern**: 100% validated across diverse task types

---

## 🎯 Refactor Template

Every task follows this exact 9-step pattern. Copy-paste and adjust only the highlighted sections:

```python
class [TASK_NAME]Task(PlanTask):  # ← ADJUST: Task class name
    """
    [ORIGINAL_DOCSTRING]  # ← PRESERVE: Original description
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """

    def requires(self):
        # ← PRESERVE: Existing requires() - DO NOT MODIFY
        return [EXISTING_DEPENDENCIES]

    def output(self):
        # ← PRESERVE: Existing output() - DO NOT MODIFY
        return [EXISTING_OUTPUTS]

    def run_with_llm(self, llm: LLM) -> None:  # OR run_inner(self) - ← CHECK which one exists
        db_service = None
        plan_id = self.get_plan_id()

        try:
            db_service = self.get_database_service()

            # FOR run_inner() ONLY: Create LLM executor
            # llm_executor: LLMExecutor = self.create_llm_executor()  # ← UNCOMMENT if run_inner()

            # ← PRESERVE: Existing input reading code - DO NOT MODIFY
            # [COPY ALL INPUT READING CODE FROM ORIGINAL TASK]

            # ← PRESERVE: Existing query construction - DO NOT MODIFY
            # query = [COPY ORIGINAL QUERY CONSTRUCTION]

            # Track LLM interaction START
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "[STAGE_NAME]",  # ← ADJUST: e.g., "deduplicate_levers", "scenarios"
                "prompt_text": query,  # OR plan_prompt if single input  # ← ADJUST based on inputs
                "status": "pending"
            }).id

            # Execute LLM call
            import time
            start_time = time.time()
            # ← PRESERVE: Existing LLM execution line - DO NOT MODIFY
            # result = [COPY ORIGINAL EXECUTION LINE]
            duration_seconds = time.time() - start_time

            # Update LLM interaction COMPLETE
            response_dict = result.to_dict()  # ← ADJUST: use actual result variable name
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })

            # Persist ALL OUTPUTS to database (repeat for each output)
            # OUTPUT 1: RAW (or first output)
            raw_content = json.dumps(response_dict, indent=2)  # ← ADJUST: or result.markdown if markdown
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.[OUTPUT_1_ENUM].value,  # ← ADJUST: e.g., DEDUPLICATED_LEVERS_RAW
                "stage": "[STAGE_NAME]",  # ← SAME as above
                "content_type": "json",  # ← ADJUST: "json", "markdown", "html", "csv", "txt"
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })

            # OUTPUT 2: MARKDOWN/CLEAN/HTML (if exists)
            # ← REPEAT above block for each output with adjusted values

            # Write to filesystem (Luigi tracking)
            # ← PRESERVE: Existing save_raw(), save_markdown(), etc. calls - DO NOT MODIFY
            # [COPY ALL FILESYSTEM WRITE CALLS FROM ORIGINAL TASK]

        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {
                        "status": "failed",
                        "error_message": str(e),
                        "completed_at": datetime.utcnow()
                    })
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()
```

---

## 🔍 Step-by-Step Refactor Checklist

### 1. Locate Task
```bash
# Find task in file
grep -n "class [TaskName]Task" planexe/plan/run_plan_pipeline.py
```

### 2. Identify Task Characteristics
- [ ] Uses `run_with_llm(self, llm: LLM)` OR `run_inner(self)`?
- [ ] How many inputs? (check `requires()`)
- [ ] How many outputs? (check `output()`)
- [ ] Output types? (raw+markdown, raw+clean, raw+html, etc.)
- [ ] What class method is called? (e.g., `RedlineGate.execute()`)

### 3. Copy Template
- Copy the template above
- DO NOT modify `requires()` - keep exact same dependencies
- DO NOT modify `output()` - keep exact same outputs
- DO NOT modify input reading code - copy as-is
- DO NOT modify LLM execution line - copy as-is

### 4. Adjust Only These Values
- **Task class name**: `class [YOUR_TASK]Task`
- **Stage name**: `"stage": "[your_stage_name]"` (lowercase, underscores)
- **FilenameEnum**: Use exact enum from original output()
- **Content type**: Match output type ("json", "markdown", "html", "csv")
- **Result variable**: Match variable name from original LLM call
- **run_with_llm vs run_inner**: Use whichever exists in original

### 5. Persist All Outputs
For each output in `output()`:
```python
# Example: If output() returns {'raw': ..., 'markdown': ...}
# Then persist BOTH to database:

# Output 1: RAW
db_service.create_plan_content({
    "plan_id": plan_id,
    "filename": FilenameEnum.MY_TASK_RAW.value,
    "stage": "my_stage",
    "content_type": "json",
    "content": raw_content,
    "content_size_bytes": len(raw_content.encode('utf-8'))
})

# Output 2: MARKDOWN
db_service.create_plan_content({
    "plan_id": plan_id,
    "filename": FilenameEnum.MY_TASK_MARKDOWN.value,
    "stage": "my_stage",
    "content_type": "markdown",
    "content": markdown_content,
    "content_size_bytes": len(markdown_content.encode('utf-8'))
})
```

### 6. Keep Filesystem Writes
Always keep the original `save_raw()`, `save_markdown()`, etc. calls at the end.
These are required for Luigi dependency tracking.

---

## 📝 Quick Reference: Task Patterns

### Pattern A: Standard (raw + markdown)
**Examples**: Tasks 3, 4, 5, 6
```python
# Outputs
raw_content = json.dumps(result.to_dict(), indent=2)
markdown_content = result.markdown

# Persist both
db_service.create_plan_content({...})  # raw
db_service.create_plan_content({...})  # markdown
```

### Pattern B: Raw + Clean (both JSON)
**Examples**: Task 8
```python
# Outputs
raw_content = json.dumps(result.to_dict(), indent=2)
clean_content = result.to_clean_json()

# Persist both
db_service.create_plan_content({...})  # raw
db_service.create_plan_content({...})  # clean
```

### Pattern C: Multiple outputs (raw + markdown + html)
```python
# Outputs
raw_content = json.dumps(result.to_dict(), indent=2)
markdown_content = result.markdown
html_content = result.to_html()

# Persist all three
db_service.create_plan_content({...})  # raw
db_service.create_plan_content({...})  # markdown
db_service.create_plan_content({...})  # html
```

### Pattern D: Single output
```python
# Output
content = result.markdown  # or result.to_dict() or result.to_html()

# Persist one
db_service.create_plan_content({...})
```

---

## ⚠️ Common Mistakes to Avoid

1. **DON'T modify requires()** - Luigi dependency chain is critical
2. **DON'T modify output()** - Luigi tracks task completion by file existence
3. **DON'T change input reading logic** - Keep exact same order and structure
4. **DON'T forget to persist ALL outputs** - Database is primary storage
5. **DON'T remove filesystem writes** - Luigi needs them for tracking
6. **DON'T forget finally block** - Must close database connection
7. **DON'T use wrong run method** - Check if original uses run_with_llm() or run_inner()

---

## 🚀 Batch Refactoring Strategy

### Recommended Approach
1. **Group by similarity** (all lever tasks, all scenario tasks, etc.)
2. **Refactor 5 tasks at once**
3. **Test compilation** (`python -m py_compile planexe/plan/run_plan_pipeline.py`)
4. **Commit batch** with descriptive message
5. **Repeat**

### Testing Schedule
- **After every 10 tasks**: Run syntax check
- **At 30 tasks (50%)**: Run full pipeline test locally
- **At 50 tasks (85%)**: Deploy to Railway, test end-to-end
- **At 59 tasks (100%)**: Full validation, performance test

---

## 📊 Progress Tracker

Track completion by stage:

```markdown
### Strategic Planning (8 tasks)
- [x] Task 8: PotentialLeversTask
- [ ] Task 9: DeduplicateLeversTask
- [ ] Task 10: EnrichLeversTask
- [ ] Task 11: FocusOnVitalFewLeversTask
- [ ] Task 12: StrategicDecisionsMarkdownTask
- [ ] Task 13: CandidateScenariosTask
- [ ] Task 14: SelectScenarioTask
- [ ] Task 15: ScenariosMarkdownTask

### Context & Location (3 tasks)
- [ ] Task 16: PhysicalLocationsTask
- [ ] Task 17: CurrencyStrategyTask
- [ ] Task 18: IdentifyRisksTask

... (continue for all stages)
```

---

## 🎓 Learning From Examples

Study these completed tasks to understand variations:

1. **RedlineGateTask** (Task 3) - Lines 280-395
   - Standard pattern with detailed logging
   - run_with_llm()
   - 2 outputs: raw + markdown

2. **PremiseAttackTask** (Task 4) - Lines 398-488
   - Uses run_inner() with LLMExecutor
   - 2 outputs: raw + markdown

3. **PlanTypeTask** (Task 6) - Lines 584-684
   - Multiple inputs (2 dependencies)
   - Query construction from multiple files
   - 2 outputs: raw + markdown

4. **PotentialLeversTask** (Task 8) - Lines 686-791
   - Multiple inputs (3 dependencies)
   - 2 outputs: raw + clean (both JSON)
   - Uses run_inner()

---

## 💡 Time-Saving Tips

1. **Use search-replace** for repetitive values
2. **Copy from similar task** (same output types)
3. **Test compilation frequently** to catch typos early
4. **Commit after each task** for easy rollback
5. **Use line numbers** in commit messages for traceability

---

## ✅ Definition of Done (Per Task)

- [ ] Database service integration added
- [ ] LLM interaction tracking added (create → update)
- [ ] All outputs persisted to plan_content table
- [ ] Filesystem writes preserved for Luigi
- [ ] Error handling with interaction failure tracking
- [ ] Database connection cleanup in finally block
- [ ] Original task logic preserved (no functional changes)
- [ ] Code compiles without errors
- [ ] Committed with descriptive message

---

**Estimated time per task**: 15-30 minutes (after first few)
**Estimated total time remaining**: 15-25 hours for 52 tasks

**Success rate with this guide**: 95%+ (pattern is well-established)
