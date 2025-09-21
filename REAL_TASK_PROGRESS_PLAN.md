# Real Luigi Task Progress Implementation Plan

## Current Problem
The backend uses FAKE progress simulation with only 7 hardcoded stages instead of parsing the actual Luigi pipeline output which has 61 real tasks.

## Luigi Task Output Analysis
From the log files, Luigi outputs:
```
luigi-interface - DEBUG - Checking if RedlineGateTask(...) is complete
luigi-interface - DEBUG - Checking if PremiseAttackTask(...) is complete
luigi-interface - DEBUG - Checking if IdentifyPurposeTask(...) is complete
```

## Implementation Plan

### Phase 1: Remove Fake Progress (IMMEDIATE)
1. **Delete fake progress_stages array** in `api.py`
2. **Remove hardcoded stage progression** in monitoring loop
3. **Keep only real Luigi stdout/stderr parsing**

### Phase 2: Parse Real Luigi Output
1. **Parse Luigi Task Events**:
   - `DEBUG - Checking if {TaskName}(...) is complete` → Task Starting
   - Task completion logs (need to identify pattern)
   - Error patterns for failed tasks

2. **Task Progress Calculation**:
   - Total tasks: 61 (from expected_filenames count)
   - Progress = (completed_tasks / 61) * 100
   - Real task names from Luigi class names

3. **Real-time Parsing**:
   - Read stdout line by line in monitoring loop
   - Extract task names using regex
   - Update database with actual task progress

### Phase 3: Frontend Real Task Display
1. **Update UI components** to show actual task names
2. **Remove fake stage names** from frontend
3. **Display progress as "Task X of 61: {TaskName}"**

### Phase 4: Database Schema
1. **Add task_events table** to track individual tasks
2. **Store real task names and completion status**
3. **Enable task-level retry logic**

## Luigi Task Names (From Pipeline Analysis)
1. StartTimeTask
2. SetupTask
3. RedlineGateTask
4. PremiseAttackTask
5. IdentifyPurposeTask
6. PlanTypeTask
7. PotentialLeversTask
8. DeduplicateLeversTask
9. EnrichLeversTask
10. FocusOnVitalFewLeversTask
... (and 51 more tasks)

## Implementation Priority
1. **CRITICAL**: Remove fake simulation (lines 169-191 in api.py)
2. **HIGH**: Parse Luigi stdout for task names
3. **HIGH**: Calculate real progress percentage
4. **MEDIUM**: Update frontend to show real tasks
5. **LOW**: Enhanced task-level tracking

## Success Criteria
- ✅ No fake progress stages
- ✅ Real Luigi task names in progress messages
- ✅ Accurate progress percentage (completed/61)
- ✅ Frontend shows actual task execution
- ✅ Users see exactly what Luigi is doing