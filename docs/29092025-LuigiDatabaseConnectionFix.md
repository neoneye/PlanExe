# Luigi Pipeline Database Connection Fix Plan

**Date**: 2025-09-29
**Author**: Claude Code using Sonnet 4
**Status**: Ready for Implementation

## Executive Summary

The PlanExe system has a critical architectural gap: the Luigi pipeline runs as an isolated subprocess with no database connection, preventing real-time progress updates. While the FastAPI backend correctly creates database records and the frontend can display them, the Luigi pipeline never updates the database during execution - only writes files.

## Problem Analysis

### Current Broken Flow
1. Frontend submits plan creation request to FastAPI
2. FastAPI creates Plan record in database with `status="pending"`
3. FastAPI starts Luigi pipeline as subprocess in background thread
4. Luigi pipeline executes 61 tasks, writing files but **never touching database**
5. FastAPI only updates database when subprocess completes (success/failure)
6. Frontend never receives real-time progress updates

### Root Cause Discovery
After extensive code analysis, the issue is clear:

**Luigi Pipeline Architecture**: The `planexe/plan/run_plan_pipeline.py` module is completely isolated from the FastAPI database layer. It has a `_handle_task_completion()` callback method that currently only logs completion but never writes to any database.

**Missing Database Bridge**: The Luigi subprocess inherits environment variables from FastAPI but the `DATABASE_URL` is never passed through, and even if it were, the Luigi code has no database imports or connection logic.

**File-Only Operation**: Luigi was designed to be purely file-based, reading inputs from files and writing outputs to files. The database integration was bolted on later for the FastAPI wrapper but never properly connected to the pipeline core.

## Technical Architecture Insights

### FastAPI Side (Working Correctly)
- `pipeline_execution_service.py` properly starts subprocess with environment variables
- Database connection and models are fully functional
- WebSocket broadcasting system is implemented but receives no data from Luigi
- Progress monitoring only tracks subprocess completion, not task-by-task progress

### Luigi Side (Missing Database Layer)
- `ExecutePipeline` class has infrastructure for progress callbacks
- `_handle_task_completion()` method exists but only logs, never persists data
- Pipeline operates entirely through file I/O with numbered outputs (001-start_time.json, etc.)
- No awareness of the FastAPI database schema or connection

### The Missing Bridge
The system needs Luigi to:
1. Receive database configuration from FastAPI environment
2. Import and initialize DatabaseService within the subprocess
3. Update Plan progress/status after each task completion
4. Write LLM interactions to database during execution
5. Create PlanFile records as outputs are generated

## Implementation Plan

### Phase 1: Environment Configuration Bridge
**Objective**: Get DATABASE_URL to Luigi subprocess and verify it's received

**Tasks**:
- Modify `pipeline_execution_service.py._setup_environment()` to include `DATABASE_URL` in environment dict
- Add debug logging to verify Luigi subprocess receives database configuration
- Test subprocess can see database environment variable

### Phase 2: Database Import Integration
**Objective**: Add database connectivity to Luigi pipeline

**Tasks**:
- Add database imports to `planexe/plan/run_plan_pipeline.py`
- Import `DatabaseService`, `Plan`, `LLMInteraction`, `PlanFile` from `planexe_api.database`
- Handle import path issues (may need to adjust Python path or move database models to shared location)
- Initialize DatabaseService within `ExecutePipeline.__init__()` method

### Phase 3: Progress Database Updates
**Objective**: Real-time Plan status updates during Luigi execution

**Tasks**:
- Modify `ExecutePipeline._handle_task_completion()` to update Plan table
- Update `progress_percentage` based on task completion (task_number/61 * 100)
- Set `progress_message` to current task description
- Update `status` to "running" when first task starts
- Ensure database commits are properly handled

### Phase 4: LLM Interaction Logging
**Objective**: Capture all LLM calls during pipeline execution

**Tasks**:
- Identify where LLM calls happen in Luigi tasks (via `LLMExecutor`)
- Intercept LLM prompts and responses
- Write LLMInteraction records with stage, model, prompt, response, timing
- Include token counts and cost tracking if available

### Phase 5: File Generation Tracking
**Objective**: Create PlanFile records as Luigi generates outputs

**Tasks**:
- Monitor Luigi output directory for new files
- Create PlanFile database records when outputs are written
- Include file metadata (size, type, generation stage)
- Map Luigi task names to database stage identifiers

### Phase 6: Error Handling & Status Sync
**Objective**: Ensure database accurately reflects pipeline state

**Tasks**:
- Capture Luigi task failures and write error messages to Plan table
- Handle database connection failures gracefully (fallback to file-only mode)
- Ensure Plan status is set to "failed" if pipeline crashes
- Test recovery scenarios and partial completion states

### Phase 7: Integration Testing
**Objective**: Verify end-to-end real-time progress tracking

**Tasks**:
- Test complete plan generation with database updates
- Verify frontend receives real-time progress via existing SSE implementation
- Test error conditions and recovery
- Validate all generated data is properly persisted
- Performance testing with database writes enabled

## Implementation Considerations

### Database Connection Management
- Luigi subprocess will need its own database session management
- Consider connection pooling and timeout handling
- Ensure database transactions don't interfere with Luigi's task dependency graph

### Error Recovery
- Database write failures should not crash the Luigi pipeline
- Implement fallback to file-only mode if database is unavailable
- Log database connection issues for debugging

### Performance Impact
- Database writes during pipeline execution may slow overall completion
- Consider batch updates or async database writes
- Monitor memory usage with additional database connections

### Testing Strategy
- Use existing failed runs in `D:\1Projects\PlanExe\run\` for testing
- Test with both SQLite (development) and PostgreSQL (production)
- Verify WebSocket broadcasting works with real Luigi data

## Success Criteria

1. **Real-time Progress**: Frontend shows task-by-task progress during Luigi execution
2. **Database Persistence**: All Plan status, LLM interactions, and file records are properly saved
3. **Error Handling**: Failed runs properly update database with error information
4. **Performance**: Database integration doesn't significantly slow pipeline execution
5. **Backward Compatibility**: Existing file-based outputs still work correctly

## Todo List

- [ ] **Environment Bridge**: Pass DATABASE_URL to Luigi subprocess environment
- [ ] **Database Imports**: Add database connectivity to run_plan_pipeline.py
- [ ] **Progress Updates**: Implement real-time Plan status updates in _handle_task_completion()
- [ ] **LLM Logging**: Capture and persist all LLM interactions during pipeline
- [ ] **File Tracking**: Create PlanFile records as Luigi generates outputs
- [ ] **Error Handling**: Ensure database reflects pipeline failures correctly
- [ ] **Integration Testing**: Test end-to-end progress tracking with existing frontend
- [ ] **Performance Testing**: Verify database writes don't significantly slow pipeline
- [ ] **Documentation**: Update CLAUDE.md with new database integration details

## Next Developer Notes

This is a significant architectural change that bridges two previously isolated systems. The key insight is that Luigi was designed to be purely file-based, but the product requirements demand real-time database updates. The solution requires carefully introducing database connectivity to the Luigi subprocess without breaking its existing file-based operation.

Start with Phase 1 to establish the basic connection, then gradually add database writes. Test incrementally to avoid breaking the complex 61-task dependency graph that powers the core planning intelligence.