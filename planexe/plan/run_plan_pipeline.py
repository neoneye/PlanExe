"""
PROMPT> python -m planexe.plan.run_plan_pipeline

In order to resume an unfinished run.
Insert the run_id_dir of the thing you want to resume.
If it's an already finished run, then remove the "999-pipeline_complete.txt" file.
PROMPT> RUN_ID_DIR=/absolute/path/to/PlanExe_20250216_150332 python -m planexe.plan.run_plan_pipeline
"""
from dataclasses import dataclass, field
from datetime import date, datetime
import logging
import json
from typing import Any, Optional
import luigi
from pathlib import Path
from llama_index.core.llms.llm import LLM
from planexe.diagnostics.redline_gate import RedlineGate
from planexe.diagnostics.premise_attack import PremiseAttack
from planexe.diagnostics.premortem import Premortem
from planexe.plan.pipeline_config import PIPELINE_CONFIG
from planexe.lever.deduplicate_levers import DeduplicateLevers
from planexe.lever.scenarios_markdown import ScenariosMarkdown
from planexe.lever.strategic_decisions_markdown import StrategicDecisionsMarkdown
from planexe.plan.filenames import FilenameEnum, ExtraFilenameEnum
from planexe.plan.speedvsdetail import SpeedVsDetailEnum
from planexe.assume.identify_purpose import IdentifyPurpose
from planexe.assume.identify_plan_type import IdentifyPlanType
from planexe.assume.physical_locations import PhysicalLocations
from planexe.assume.currency_strategy import CurrencyStrategy
from planexe.assume.identify_risks import IdentifyRisks
from planexe.assume.make_assumptions import MakeAssumptions
from planexe.assume.distill_assumptions import DistillAssumptions
from planexe.assume.review_assumptions import ReviewAssumptions
from planexe.assume.shorten_markdown import ShortenMarkdown
from planexe.expert.pre_project_assessment import PreProjectAssessment
from planexe.plan.project_plan import ProjectPlan
from planexe.document.identify_documents import IdentifyDocuments
from planexe.document.filter_documents_to_find import FilterDocumentsToFind
from planexe.document.filter_documents_to_create import FilterDocumentsToCreate
from planexe.document.draft_document_to_find import DraftDocumentToFind
from planexe.document.draft_document_to_create import DraftDocumentToCreate
from planexe.document.markdown_with_document import markdown_rows_with_document_to_create, markdown_rows_with_document_to_find
from planexe.governance.governance_phase1_audit import GovernancePhase1Audit
from planexe.governance.governance_phase2_bodies import GovernancePhase2Bodies
from planexe.governance.governance_phase3_impl_plan import GovernancePhase3ImplPlan
from planexe.governance.governance_phase4_decision_escalation_matrix import GovernancePhase4DecisionEscalationMatrix
from planexe.governance.governance_phase5_monitoring_progress import GovernancePhase5MonitoringProgress
from planexe.governance.governance_phase6_extra import GovernancePhase6Extra
from planexe.plan.related_resources import RelatedResources
from planexe.questions_answers.questions_answers import QuestionsAnswers
from planexe.lever.identify_potential_levers import IdentifyPotentialLevers
from planexe.lever.enrich_potential_levers import EnrichPotentialLevers
from planexe.lever.focus_on_vital_few_levers import FocusOnVitalFewLevers
from planexe.lever.candidate_scenarios import CandidateScenarios
from planexe.lever.select_scenario import SelectScenario
from planexe.swot.swot_analysis import SWOTAnalysis
from planexe.expert.expert_finder import ExpertFinder
from planexe.expert.expert_criticism import ExpertCriticism
from planexe.expert.expert_orchestrator import ExpertOrchestrator
from planexe.plan.create_wbs_level1 import CreateWBSLevel1
from planexe.plan.create_wbs_level2 import CreateWBSLevel2
from planexe.plan.create_wbs_level3 import CreateWBSLevel3
from planexe.pitch.create_pitch import CreatePitch
from planexe.pitch.convert_pitch_to_markdown import ConvertPitchToMarkdown
from planexe.plan.identify_wbs_task_dependencies import IdentifyWBSTaskDependencies
from planexe.plan.estimate_wbs_task_durations import EstimateWBSTaskDurations
from planexe.plan.data_collection import DataCollection
from planexe.plan.review_plan import ReviewPlan
from planexe.plan.executive_summary import ExecutiveSummary
from planexe.team.find_team_members import FindTeamMembers
from planexe.team.enrich_team_members_with_contract_type import EnrichTeamMembersWithContractType
from planexe.team.enrich_team_members_with_background_story import EnrichTeamMembersWithBackgroundStory
from planexe.team.enrich_team_members_with_environment_info import EnrichTeamMembersWithEnvironmentInfo
from planexe.team.team_markdown_document import TeamMarkdownDocumentBuilder
from planexe.team.review_team import ReviewTeam
from planexe.wbs.wbs_task import WBSTask, WBSProject
from planexe.wbs.wbs_populate import WBSPopulate
from planexe.wbs.wbs_task_tooltip import WBSTaskTooltip
from planexe.schedule.project_schedule_populator import ProjectSchedulePopulator
from planexe.schedule.schedule import ProjectSchedule
from planexe.schedule.export_gantt_dhtmlx import ExportGanttDHTMLX
from planexe.schedule.export_gantt_csv import ExportGanttCSV
from planexe.schedule.export_gantt_mermaid import ExportGanttMermaid
from planexe.llm_util.llm_executor import LLMExecutor, LLMModelFromName, ShouldStopCallbackParameters, PipelineStopRequested
from planexe.llm_factory import get_llm_names_by_priority, SPECIAL_AUTO_ID, is_valid_llm_name
from planexe.format_json_for_use_in_query import format_json_for_use_in_query
from planexe.report.report_generator import ReportGenerator
from planexe.luigi_util.obtain_output_files import ObtainOutputFiles
from planexe.plan.pipeline_environment import PipelineEnvironment
# Import database service for Option 1 database-first architecture
import sys
import os
# Add parent directory to path to import planexe_api
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from planexe_api.database import DatabaseService, get_database_service

logger = logging.getLogger(__name__)
DEFAULT_LLM_MODEL = "gpt-5-mini-2025-08-07"  # Updated from ollama-llama3.1 (no longer in config)

REPORT_EXECUTE_PLAN_SECTION_HIDDEN = True
# REPORT_EXECUTE_PLAN_SECTION_HIDDEN = False

class PlanTask(luigi.Task):
    # Default it to the current timestamp, eg. 19841231_235959
    # Path to the 'run/{run_id}' directory
    run_id_dir = luigi.Parameter(default=Path('run') / datetime.now().strftime("%Y%m%d_%H%M%S"))

    # By default, run everything but it's slow.
    # This can be overridden in developer mode, where a quick turnaround is needed, and the details are not important.
    speedvsdetail = luigi.EnumParameter(enum=SpeedVsDetailEnum, default=SpeedVsDetailEnum.ALL_DETAILS_BUT_SLOW)

    # List of LLM models to try, in order of priority.
    llm_models = luigi.ListParameter(default=[DEFAULT_LLM_MODEL])

    # Optional callback for updating progress bar and aborting the pipeline.
    # If the callback raises PipelineStopRequested, the pipeline will be aborted. This is the only exception that is allowed to be raised.
    # If the callback raises exceptions different than PipelineStopRequested, the pipeline will be aborted. This means that something went wrong, and we should not continue.
    # If the callback doesn't raise an exception, the pipeline will continue.
    # If the callback is not provided, the pipeline will run until completion.
    _pipeline_executor_callback = luigi.Parameter(default=None, significant=False, visibility=luigi.parameter.ParameterVisibility.PRIVATE)

    def file_path(self, filename: FilenameEnum) -> Path:
        return self.run_id_dir / filename.value
    
    def local_target(self, filename: FilenameEnum) -> luigi.LocalTarget:
        return luigi.LocalTarget(self.file_path(filename))

    def get_plan_id(self) -> str:
        """
        Extract plan_id from run_id_dir.
        Example: run/PlanExe_20250216_150332 -> PlanExe_20250216_150332

        Returns:
            str: The plan ID (directory name)
        """
        # run_id_dir is a Path object like: Path('run/PlanExe_20250216_150332')
        # We want just the directory name: 'PlanExe_20250216_150332'
        return self.run_id_dir.name

    def get_database_service(self) -> DatabaseService:
        """
        Get DatabaseService instance for persisting content to database.

        This method creates a new database session for the current task.
        The caller is responsible for calling db_service.close() when done.

        Returns:
            DatabaseService: Database service instance with active session

        Raises:
            Exception: If database connection fails

        Example usage in task:
            db_service = self.get_database_service()
            try:
                db_service.create_plan_content({...})
            except Exception as e:
                logger.error(f"Database write failed: {e}")
            finally:
                db_service.close()
        """
        try:
            return get_database_service()
        except Exception as e:
            logger.error(f"Failed to get database service: {e}")
            raise Exception(f"Database connection failed for plan_id: {self.get_plan_id()}") from e

    def create_llm_executor(self) -> LLMExecutor:
        """
        Create an LLMExecutor instance.
        - Responsible for stopping the pipeline when the user presses Ctrl-C or closes the browser tab.
        - Fallback mechanism to try the next LLM if the current one fails.
        """
        # Redirect the callback to the pipeline_executor_callback.
        def should_stop_callback(parameters: ShouldStopCallbackParameters) -> None:
            if self._pipeline_executor_callback is None:
                return
            # The pipeline_executor_callback expects (task, duration) but we have ShouldStopCallbackParameters
            total_duration = parameters.total_duration
            self._pipeline_executor_callback(self, total_duration)

        llm_model_instances = LLMModelFromName.from_names(self.llm_models)

        return LLMExecutor(
            llm_models=llm_model_instances,
            should_stop_callback=should_stop_callback
        )

    def run(self):
        """
        Don't override this method. Instead either override the run_inner() method, or override the run_with_llm() method.
        """
        # DIAGNOSTIC: Log when ANY task run() is called
        logger.error(f"🔥 {self.__class__.__name__}.run() CALLED - Luigi worker IS running!")
        print(f"🔥 {self.__class__.__name__}.run() CALLED - Luigi worker IS running!")

        try:
            self.run_inner()
        except PipelineStopRequested as e:
            logger.debug(f"{self.__class__.__name__} -> PipelineStopRequested raised: {e}")
            # This exception is raised by the should_stop_callback
            # If we get here, it means that the pipeline was aborted by the callback, such as by the user pressing Ctrl-C or closing the browser tab.
            # Create a flag file to signal that the stop was intentional.
            flag_path = self.run_id_dir / ExtraFilenameEnum.PIPELINE_STOP_REQUESTED_FLAG.value
            logger.info(f"Creating stop flag file: {flag_path!r}")
            flag_path.touch()
            raise
        except Exception as e:
            # Re-raise the exception with a more descriptive message
            logger.error(f"🔥 {self.__class__.__name__}.run() FAILED: {e}")
            print(f"🔥 {self.__class__.__name__}.run() FAILED: {e}")
            raise Exception(f"Failed to run {self.__class__.__name__} with any of the LLMs in the list: {self.llm_models!r} for run_id_dir: {self.run_id_dir!r}") from e

    def run_inner(self):
        """
        Override this method or the run_with_llm() method.
        """
        llm_executor: LLMExecutor = self.create_llm_executor()
        
        # Attempt executing this code with the first LLM, if that fails, try the next one, and so on.
        def execute_function(llm: LLM) -> None:
            self.run_with_llm(llm)

        # Make multiple attempts at running the run_with_llm() function.
        # No try/except needed here. Let PlanTask.run() handle it.
        llm_executor.run(execute_function)

    def run_with_llm(self, llm: LLM) -> None:
        """
        Override this method or the run_inner() method.
        """
        raise NotImplementedError("Subclasses must implement this method.")


class StartTimeTask(PlanTask):
    """
    The timestamp when the pipeline was started.

    DATABASE INTEGRATION EXEMPTION (Option 1 Refactor):
    This task does NOT need database integration because it is pre-created by
    the FastAPI server before the Luigi pipeline starts. The file is written
    in pipeline_execution_service.py:_write_pipeline_inputs() (line 195-198).

    The FastAPI server already writes this file to the filesystem, and it's
    a simple timestamp - no LLM interaction, no complex content generation.
    Adding database persistence here would be redundant.

    Luigi uses this file's existence to track task completion, so the file
    must exist on the filesystem regardless of database integration.
    """
    def output(self):
        return self.local_target(FilenameEnum.START_TIME)

    def run(self):
        # The Gradio/Flask app that starts the luigi pipeline, must first create the `START_TIME` file inside the `run_id_dir`.
        # This code will ONLY run if the Gradio/Flask app *failed* to create the file.
        raise AssertionError(f"This code is not supposed to be run. Before starting the pipeline the '{FilenameEnum.START_TIME.value}' file must be present in the `run_id_dir`: {self.run_id_dir!r}")


class SetupTask(PlanTask):
    """
    The plan prompt text provided by the user.

    DATABASE INTEGRATION EXEMPTION (Option 1 Refactor):
    This task does NOT need database integration because it is pre-created by
    the FastAPI server before the Luigi pipeline starts. The file is written
    in pipeline_execution_service.py:_write_pipeline_inputs() (line 200-203).

    The FastAPI server already writes the user's prompt to the filesystem, and
    it's stored in the database via the Plans table (plans.prompt column).
    The prompt is simple text - no LLM interaction, no processing required.
    Adding database persistence here would duplicate the Plans table.

    Luigi uses this file's existence to track task completion, so the file
    must exist on the filesystem regardless of database integration.
    """
    def output(self):
        return self.local_target(FilenameEnum.INITIAL_PLAN)

    def run(self):
        # The Gradio/Flask app that starts the luigi pipeline, must first create the `INITIAL_PLAN` file inside the `run_id_dir`.
        # This code will ONLY run if the Gradio/Flask app *failed* to create the file.
        raise AssertionError(f"This code is not supposed to be run. Before starting the pipeline the '{FilenameEnum.INITIAL_PLAN.value}' file must be present in the `run_id_dir`: {self.run_id_dir!r}")


class RedlineGateTask(PlanTask):
    """
    First real LLM task in the pipeline - moral compass safety check.

    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    This task persists content to database DURING execution, not after completion.
    Files are still written to filesystem for Luigi dependency tracking.
    """
    def requires(self):
        return self.clone(SetupTask)

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.REDLINE_GATE_RAW),
            'markdown': self.local_target(FilenameEnum.REDLINE_GATE_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        # DIAGNOSTIC: Log that this method is actually being called
        logger.error(f"🔥 RedlineGateTask.run_with_llm() CALLED - Luigi IS executing tasks!")
        print(f"🔥 RedlineGateTask.run_with_llm() CALLED - Luigi IS executing tasks!")

        # Get database service and plan ID (Phase 1.1)
        db_service = None
        plan_id = self.get_plan_id()
        logger.error(f"🔥 RedlineGateTask: plan_id = {plan_id}")
        print(f"🔥 RedlineGateTask: plan_id = {plan_id}")

        try:
            logger.error(f"🔥 RedlineGateTask: About to get database service...")
            print(f"🔥 RedlineGateTask: About to get database service...")
            db_service = self.get_database_service()
            logger.error(f"🔥 RedlineGateTask: Database service obtained successfully")
            print(f"🔥 RedlineGateTask: Database service obtained successfully")

            # Read inputs from required tasks
            with self.input().open("r") as f:
                plan_prompt = f.read()
            logger.error(f"🔥 RedlineGateTask: Read plan prompt ({len(plan_prompt)} chars)")
            print(f"🔥 RedlineGateTask: Read plan prompt ({len(plan_prompt)} chars)")

            # Track LLM interaction START (Phase 1.2)
            logger.error(f"🔥 RedlineGateTask: About to create LLM interaction in database...")
            print(f"🔥 RedlineGateTask: About to create LLM interaction in database...")
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "redline_gate",
                "prompt_text": plan_prompt,
                "status": "pending"
            }).id

            logger.info(f"RedlineGateTask: Created LLM interaction {interaction_id} for plan {plan_id}")
            logger.error(f"🔥 RedlineGateTask: LLM interaction {interaction_id} created successfully")
            print(f"🔥 RedlineGateTask: LLM interaction {interaction_id} created successfully")

            # Execute LLM call
            import time
            logger.error(f"🔥 RedlineGateTask: About to call RedlineGate.execute() with LLM...")
            print(f"🔥 RedlineGateTask: About to call RedlineGate.execute() with LLM: {type(llm).__name__}")
            start_time = time.time()
            redline_gate = RedlineGate.execute(llm, plan_prompt)
            duration_seconds = time.time() - start_time
            logger.error(f"🔥 RedlineGateTask: RedlineGate.execute() completed in {duration_seconds:.2f}s")
            print(f"🔥 RedlineGateTask: RedlineGate.execute() completed in {duration_seconds:.2f}s")

            # Update LLM interaction COMPLETE (Phase 1.2)
            response_dict = redline_gate.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds,
                # Note: Token counts not available from RedlineGate.execute() - would need LLMExecutor integration
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None
            })

            logger.info(f"RedlineGateTask: Updated LLM interaction {interaction_id} to completed ({duration_seconds:.2f}s)")

            # Persist RAW content to database (PRIMARY storage - Phase 1.3)
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.REDLINE_GATE_RAW.value,
                "stage": "redline_gate",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })

            logger.info(f"RedlineGateTask: Persisted RAW to database ({len(raw_content)} bytes)")

            # Persist MARKDOWN content to database (PRIMARY storage - Phase 1.3)
            markdown_content = redline_gate.markdown
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.REDLINE_GATE_MARKDOWN.value,
                "stage": "redline_gate",
                "content_type": "markdown",
                "content": markdown_content,
                "content_size_bytes": len(markdown_content.encode('utf-8'))
            })

            logger.info(f"RedlineGateTask: Persisted MARKDOWN to database ({len(markdown_content)} bytes)")

            # Write to filesystem (SECONDARY storage for Luigi dependency tracking)
            output_raw_path = self.output()['raw'].path
            redline_gate.save_raw(output_raw_path)
            output_markdown_path = self.output()['markdown'].path
            redline_gate.save_markdown(output_markdown_path)

            logger.info(f"RedlineGateTask: Wrote files to filesystem for Luigi tracking")

        except Exception as e:
            # Track LLM interaction FAILURE if it was created
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {
                        "status": "failed",
                        "error_message": str(e),
                        "completed_at": datetime.utcnow()
                    })
                    logger.error(f"RedlineGateTask: Marked LLM interaction {interaction_id} as failed")
                except Exception as db_error:
                    logger.error(f"RedlineGateTask: Failed to update interaction status: {db_error}")

            logger.error(f"RedlineGateTask: Execution failed for plan {plan_id}: {e}")
            raise

        finally:
            # Clean up database connection
            if db_service:
                db_service.close()
                logger.debug(f"RedlineGateTask: Closed database connection")


class PremiseAttackTask(PlanTask):
    """
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return self.clone(SetupTask)

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.PREMISE_ATTACK_RAW),
            'markdown': self.local_target(FilenameEnum.PREMISE_ATTACK_MARKDOWN)
        }

    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()

        try:
            db_service = self.get_database_service()
            llm_executor: LLMExecutor = self.create_llm_executor()

            # Read inputs
            with self.input().open("r") as f:
                plan_prompt = f.read()

            # Track LLM interaction START
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "premise_attack",
                "prompt_text": plan_prompt,
                "status": "pending"
            }).id

            # Execute LLM call
            import time
            start_time = time.time()
            premise_attack = PremiseAttack.execute(llm_executor, plan_prompt)
            duration_seconds = time.time() - start_time

            # Update LLM interaction COMPLETE
            response_dict = premise_attack.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })

            # Persist RAW to database
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.PREMISE_ATTACK_RAW.value,
                "stage": "premise_attack",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })

            # Persist MARKDOWN to database
            markdown_content = premise_attack.markdown
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.PREMISE_ATTACK_MARKDOWN.value,
                "stage": "premise_attack",
                "content_type": "markdown",
                "content": markdown_content,
                "content_size_bytes": len(markdown_content.encode('utf-8'))
            })

            # Write to filesystem (Luigi tracking)
            output_raw_path = self.output()['raw'].path
            premise_attack.save_raw(output_raw_path)
            output_markdown_path = self.output()['markdown'].path
            premise_attack.save_markdown(output_markdown_path)

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


class IdentifyPurposeTask(PlanTask):
    """
    Determine if this is this going to be a business/personal/other plan.
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return self.clone(SetupTask)

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.IDENTIFY_PURPOSE_RAW),
            'markdown': self.local_target(FilenameEnum.IDENTIFY_PURPOSE_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()

        try:
            db_service = self.get_database_service()

            # Read inputs
            with self.input().open("r") as f:
                plan_prompt = f.read()

            # Track LLM interaction START
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "identify_purpose",
                "prompt_text": plan_prompt,
                "status": "pending"
            }).id

            # Execute LLM call
            import time
            start_time = time.time()
            identify_purpose = IdentifyPurpose.execute(llm, plan_prompt)
            duration_seconds = time.time() - start_time

            # Update LLM interaction COMPLETE
            response_dict = identify_purpose.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })

            # Persist RAW to database
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.IDENTIFY_PURPOSE_RAW.value,
                "stage": "identify_purpose",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })

            # Persist MARKDOWN to database
            markdown_content = identify_purpose.markdown
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.IDENTIFY_PURPOSE_MARKDOWN.value,
                "stage": "identify_purpose",
                "content_type": "markdown",
                "content": markdown_content,
                "content_size_bytes": len(markdown_content.encode('utf-8'))
            })

            # Write to filesystem (Luigi tracking)
            output_raw_path = self.output()['raw'].path
            identify_purpose.save_raw(output_raw_path)
            output_markdown_path = self.output()['markdown'].path
            identify_purpose.save_markdown(output_markdown_path)

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


class PlanTypeTask(PlanTask):
    """
    Determine if the plan is purely digital or requires physical locations.
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'identify_purpose': self.clone(IdentifyPurposeTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.PLAN_TYPE_RAW),
            'markdown': self.local_target(FilenameEnum.PLAN_TYPE_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()

        try:
            db_service = self.get_database_service()

            # Read inputs from required tasks
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['identify_purpose']['markdown'].open("r") as f:
                identify_purpose_markdown = f.read()

            query = (
                f"File 'plan.txt':\n{plan_prompt}\n\n"
                f"File 'purpose.md':\n{identify_purpose_markdown}"
            )

            # Track LLM interaction START
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "plan_type",
                "prompt_text": query,
                "status": "pending"
            }).id

            # Execute LLM call
            import time
            start_time = time.time()
            identify_plan_type = IdentifyPlanType.execute(llm, query)
            duration_seconds = time.time() - start_time

            # Update LLM interaction COMPLETE
            response_dict = identify_plan_type.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })

            # Persist RAW to database
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.PLAN_TYPE_RAW.value,
                "stage": "plan_type",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })

            # Persist MARKDOWN to database
            markdown_content = identify_plan_type.markdown
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.PLAN_TYPE_MARKDOWN.value,
                "stage": "plan_type",
                "content_type": "markdown",
                "content": markdown_content,
                "content_size_bytes": len(markdown_content.encode('utf-8'))
            })

            # Write to filesystem (Luigi tracking)
            output_raw_path = self.output()['raw'].path
            identify_plan_type.save_raw(str(output_raw_path))
            output_markdown_path = self.output()['markdown'].path
            identify_plan_type.save_markdown(str(output_markdown_path))

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

class PotentialLeversTask(PlanTask):
    """
    Identify potential levers that can be adjusted.
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'plan_type': self.clone(PlanTypeTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.POTENTIAL_LEVERS_RAW),
            'clean': self.local_target(FilenameEnum.POTENTIAL_LEVERS_CLEAN),
        }

    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()

        try:
            db_service = self.get_database_service()
            llm_executor: LLMExecutor = self.create_llm_executor()

            # Read inputs
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['identify_purpose']['markdown'].open("r") as f:
                identify_purpose_markdown = f.read()
            with self.input()['plan_type']['markdown'].open("r") as f:
                plan_type_markdown = f.read()

            query = (
                f"File 'plan.txt':\n{plan_prompt}\n\n"
                f"File 'purpose.md':\n{identify_purpose_markdown}\n\n"
                f"File 'plan_type.md':\n{plan_type_markdown}"
            )

            # Track LLM interaction START
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "potential_levers",
                "prompt_text": query,
                "status": "pending"
            }).id

            # Execute LLM call
            import time
            start_time = time.time()
            identify_potential_levers = IdentifyPotentialLevers.execute(llm_executor, query)
            duration_seconds = time.time() - start_time

            # Update LLM interaction COMPLETE
            response_dict = identify_potential_levers.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })

            # Persist RAW to database
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.POTENTIAL_LEVERS_RAW.value,
                "stage": "potential_levers",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })

            # Persist CLEAN to database
            clean_content = identify_potential_levers.to_clean_json()
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.POTENTIAL_LEVERS_CLEAN.value,
                "stage": "potential_levers",
                "content_type": "json",
                "content": clean_content,
                "content_size_bytes": len(clean_content.encode('utf-8'))
            })

            # Write to filesystem (Luigi tracking)
            output_raw_path = self.output()['raw'].path
            identify_potential_levers.save_raw(str(output_raw_path))
            output_clean_path = self.output()['clean'].path
            identify_potential_levers.save_clean(str(output_clean_path))

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


class DeduplicateLeversTask(PlanTask):
    """
    The potential levers usually have some redundant levers.
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'plan_type': self.clone(PlanTypeTask),
            'potential_levers': self.clone(PotentialLeversTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.DEDUPLICATED_LEVERS_RAW)
        }

    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()

        try:
            db_service = self.get_database_service()
            llm_executor: LLMExecutor = self.create_llm_executor()

            # Read inputs
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['identify_purpose']['markdown'].open("r") as f:
                identify_purpose_markdown = f.read()
            with self.input()['plan_type']['markdown'].open("r") as f:
                plan_type_markdown = f.read()
            with self.input()['potential_levers']['clean'].open("r") as f:
                lever_item_list = json.load(f)

            query = (
                f"File 'plan.txt':\n{plan_prompt}\n\n"
                f"File 'purpose.md':\n{identify_purpose_markdown}\n\n"
                f"File 'plan_type.md':\n{plan_type_markdown}"
            )

            # Track LLM interaction START
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "deduplicate_levers",
                "prompt_text": query,
                "status": "pending"
            }).id

            # Execute LLM call
            import time
            start_time = time.time()
            deduplicate_levers = DeduplicateLevers.execute(
                llm_executor,
                project_context=query,
                raw_levers_list=lever_item_list
            )
            duration_seconds = time.time() - start_time

            # Update LLM interaction COMPLETE
            response_dict = deduplicate_levers.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })

            # Persist RAW to database
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.DEDUPLICATED_LEVERS_RAW.value,
                "stage": "deduplicate_levers",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })

            # Write to filesystem (Luigi tracking)
            output_raw_path = self.output()['raw'].path
            deduplicate_levers.save_raw(str(output_raw_path))

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

class EnrichLeversTask(PlanTask):
    """
    Enrich potential levers with more information.
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'plan_type': self.clone(PlanTypeTask),
            'deduplicate_levers': self.clone(DeduplicateLeversTask),
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.ENRICHED_LEVERS_RAW)
        }

    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            llm_executor: LLMExecutor = self.create_llm_executor()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['identify_purpose']['markdown'].open("r") as f:
                identify_purpose_markdown = f.read()
            with self.input()['plan_type']['markdown'].open("r") as f:
                plan_type_markdown = f.read()
            with self.input()['deduplicate_levers']['raw'].open("r") as f:
                json_dict = json.load(f)
                lever_item_list = json_dict["deduplicated_levers"]
            query = (
                f"File 'plan.txt':\n{plan_prompt}\n\n"
                f"File 'purpose.md':\n{identify_purpose_markdown}\n\n"
                f"File 'plan_type.md':\n{plan_type_markdown}"
            )
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "enrich_levers",
                "prompt_text": query,
                "status": "pending"
            }).id
            import time
            start_time = time.time()
            enrich_potential_levers = EnrichPotentialLevers.execute(
                llm_executor,
                project_context=query,
                raw_levers_list=lever_item_list
            )
            duration_seconds = time.time() - start_time
            response_dict = enrich_potential_levers.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.ENRICHED_LEVERS_RAW.value,
                "stage": "enrich_levers",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })
            output_raw_path = self.output()['raw'].path
            enrich_potential_levers.save_raw(str(output_raw_path))
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class FocusOnVitalFewLeversTask(PlanTask):
    """
    Apply the 80/20 principle to the levers.
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'plan_type': self.clone(PlanTypeTask),
            'enriched_levers': self.clone(EnrichLeversTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.VITAL_FEW_LEVERS_RAW)
        }

    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            llm_executor: LLMExecutor = self.create_llm_executor()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['identify_purpose']['markdown'].open("r") as f:
                identify_purpose_markdown = f.read()
            with self.input()['plan_type']['markdown'].open("r") as f:
                plan_type_markdown = f.read()
            with self.input()['enriched_levers']['raw'].open("r") as f:
                lever_item_list = json.load(f)["characterized_levers"]
            query = (
                f"File 'plan.txt':\n{plan_prompt}\n\n"
                f"File 'purpose.md':\n{identify_purpose_markdown}\n\n"
                f"File 'plan_type.md':\n{plan_type_markdown}\n\n"
            )
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "vital_few_levers",
                "prompt_text": query,
                "status": "pending"
            }).id
            import time
            start_time = time.time()
            focus_on_vital_few_levers = FocusOnVitalFewLevers.execute(
                llm_executor,
                project_context=query,
                raw_levers_list=lever_item_list
            )
            duration_seconds = time.time() - start_time
            response_dict = focus_on_vital_few_levers.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.VITAL_FEW_LEVERS_RAW.value,
                "stage": "vital_few_levers",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })
            output_raw_path = self.output()['raw'].path
            focus_on_vital_few_levers.save_raw(str(output_raw_path))
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()


class StrategicDecisionsMarkdownTask(PlanTask):
    """
    Human readable markdown with the levers.
    DATABASE INTEGRATION: Option 1 (No LLM - data transformation only)
    """
    def requires(self):
        return {
            'enriched_levers': self.clone(EnrichLeversTask),
            'levers_vital_few': self.clone(FocusOnVitalFewLeversTask)
        }

    def output(self):
        return {
            'markdown': self.local_target(FilenameEnum.STRATEGIC_DECISIONS_MARKDOWN)
        }

    def run(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['enriched_levers']['raw'].open("r") as f:
                enrich_lever_list = json.load(f)["characterized_levers"]
            with self.input()['levers_vital_few']['raw'].open("r") as f:
                vital_data = json.load(f)
                vital_lever_list = vital_data["levers"]
                lever_assessments_list = vital_data.get("response", {}).get("lever_assessments", [])
                vital_levers_summary = vital_data.get("response", {}).get("summary", "")
            result = StrategicDecisionsMarkdown(enrich_lever_list, vital_lever_list, vital_levers_summary, lever_assessments_list)
            markdown_content = result.to_markdown()
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.STRATEGIC_DECISIONS_MARKDOWN.value,
                "stage": "strategic_decisions",
                "content_type": "markdown",
                "content": markdown_content,
                "content_size_bytes": len(markdown_content.encode('utf-8'))
            })
            result.save_markdown(self.output()['markdown'].path)
        except Exception as e:
            raise
        finally:
            if db_service:
                db_service.close()


class CandidateScenariosTask(PlanTask):
    """
    Combinations of the vital few levers.
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'plan_type': self.clone(PlanTypeTask),
            'levers_vital_few': self.clone(FocusOnVitalFewLeversTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.CANDIDATE_SCENARIOS_RAW),
            'clean': self.local_target(FilenameEnum.CANDIDATE_SCENARIOS_CLEAN)
        }

    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            llm_executor: LLMExecutor = self.create_llm_executor()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['identify_purpose']['markdown'].open("r") as f:
                identify_purpose_markdown = f.read()
            with self.input()['plan_type']['markdown'].open("r") as f:
                plan_type_markdown = f.read()
            with self.input()['levers_vital_few']['raw'].open("r") as f:
                lever_item_list = json.load(f)["levers"]
            query = (
                f"File 'plan.txt':\n{plan_prompt}\n\n"
                f"File 'purpose.md':\n{identify_purpose_markdown}\n\n"
                f"File 'plan_type.md':\n{plan_type_markdown}\n\n"
            )
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "candidate_scenarios",
                "prompt_text": query,
                "status": "pending"
            }).id
            import time
            start_time = time.time()
            scenarios = CandidateScenarios.execute(
                llm_executor=llm_executor,
                project_context=query,
                raw_vital_levers=lever_item_list
            )
            duration_seconds = time.time() - start_time
            response_dict = scenarios.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.CANDIDATE_SCENARIOS_RAW.value,
                "stage": "candidate_scenarios",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })
            clean_content = scenarios.to_clean_json()
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.CANDIDATE_SCENARIOS_CLEAN.value,
                "stage": "candidate_scenarios",
                "content_type": "json",
                "content": clean_content,
                "content_size_bytes": len(clean_content.encode('utf-8'))
            })
            output_raw_path = self.output()['raw'].path
            scenarios.save_raw(str(output_raw_path))
            output_clean_path = self.output()['clean'].path
            scenarios.save_clean(str(output_clean_path))
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()


class SelectScenarioTask(PlanTask):
    """
    Pick the best fitting scenario to make a plan for.
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'plan_type': self.clone(PlanTypeTask),
            'levers_vital_few': self.clone(FocusOnVitalFewLeversTask),
            'candidate_scenarios': self.clone(CandidateScenariosTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.SELECTED_SCENARIO_RAW),
            'clean': self.local_target(FilenameEnum.SELECTED_SCENARIO_CLEAN)
        }

    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            llm_executor: LLMExecutor = self.create_llm_executor()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['identify_purpose']['markdown'].open("r") as f:
                identify_purpose_markdown = f.read()
            with self.input()['plan_type']['markdown'].open("r") as f:
                plan_type_markdown = f.read()
            with self.input()['levers_vital_few']['raw'].open("r") as f:
                lever_item_list = json.load(f)["levers"]
            with self.input()['candidate_scenarios']['clean'].open("r") as f:
                scenarios_list = json.load(f).get('scenarios', [])
            query = (
                f"File 'plan.txt':\n{plan_prompt}\n\n"
                f"File 'purpose.md':\n{identify_purpose_markdown}\n\n"
                f"File 'plan_type.md':\n{plan_type_markdown}\n\n"
                f"File 'levers_vital_few.json':\n{format_json_for_use_in_query(lever_item_list)}\n\n"
                f"File 'candidate_scenarios.json':\n{format_json_for_use_in_query(scenarios_list)}"
            )
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "select_scenario",
                "prompt_text": query,
                "status": "pending"
            }).id
            import time
            start_time = time.time()
            select_scenario = SelectScenario.execute(
                llm_executor=llm_executor,
                project_context=query,
                scenarios=scenarios_list
            )
            duration_seconds = time.time() - start_time
            response_dict = select_scenario.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.SELECTED_SCENARIO_RAW.value,
                "stage": "select_scenario",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })
            clean_content = select_scenario.to_clean_json()
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.SELECTED_SCENARIO_CLEAN.value,
                "stage": "select_scenario",
                "content_type": "json",
                "content": clean_content,
                "content_size_bytes": len(clean_content.encode('utf-8'))
            })
            output_raw_path = self.output()['raw'].path
            select_scenario.save_raw(str(output_raw_path))
            output_clean_path = self.output()['clean'].path
            select_scenario.save_clean(str(output_clean_path))
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()


class ScenariosMarkdownTask(PlanTask):
    """
    Present the scenarios in a human readable format.
    DATABASE INTEGRATION: Option 1 (No LLM - data transformation only)
    """
    def requires(self):
        return {
            'candidate_scenarios': self.clone(CandidateScenariosTask),
            'selected_scenario': self.clone(SelectScenarioTask)
        }

    def output(self):
        return {
            'markdown': self.local_target(FilenameEnum.SCENARIOS_MARKDOWN)
        }

    def run(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['candidate_scenarios']['clean'].open("r") as f:
                scenarios_list = json.load(f).get('scenarios', [])
            with self.input()['selected_scenario']['clean'].open("r") as f:
                selected_scenario_dict = json.load(f)
            plan_characteristics = selected_scenario_dict.get('plan_characteristics', {})
            scenario_assessments = selected_scenario_dict.get('scenario_assessments', [])
            final_choice = selected_scenario_dict.get('final_choice', {})
            result = ScenariosMarkdown(scenarios_list, plan_characteristics, scenario_assessments, final_choice)
            markdown_content = result.to_markdown()
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.SCENARIOS_MARKDOWN.value,
                "stage": "scenarios",
                "content_type": "markdown",
                "content": markdown_content,
                "content_size_bytes": len(markdown_content.encode('utf-8'))
            })
            result.save_markdown(self.output()['markdown'].path)
        except Exception as e:
            raise
        finally:
            if db_service:
                db_service.close()


class PhysicalLocationsTask(PlanTask):
    """
    Identify/suggest physical locations for the plan.
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'plan_type': self.clone(PlanTypeTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.PHYSICAL_LOCATIONS_RAW),
            'markdown': self.local_target(FilenameEnum.PHYSICAL_LOCATIONS_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()

        try:
            db_service = self.get_database_service()
            logger.info("Identify/suggest physical locations for the plan...")

            # Read inputs from required tasks.
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['identify_purpose']['markdown'].open("r") as f:
                identify_purpose_markdown = f.read()
            with self.input()['plan_type']['raw'].open("r") as f:
                plan_type_dict = json.load(f)
            with self.input()['plan_type']['markdown'].open("r") as f:
                plan_type_markdown = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()

            output_raw_path = self.output()['raw'].path
            output_markdown_path = self.output()['markdown'].path

            plan_type = plan_type_dict.get("plan_type")
            if plan_type == "physical":
                query = (
                    f"File 'plan.txt':\n{plan_prompt}\n\n"
                    f"File 'purpose.md':\n{identify_purpose_markdown}\n\n"
                    f"File 'plan_type.md':\n{plan_type_markdown}\n\n"
                    f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n"
                    f"File 'scenarios.md':\n{scenarios_markdown}"
                )

                # Track LLM interaction START
                interaction_id = db_service.create_llm_interaction({
                    "plan_id": plan_id,
                    "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                    "stage": "physical_locations",
                    "prompt_text": query,
                    "status": "pending"
                }).id

                # Execute LLM call with timing
                import time
                start_time = time.time()
                physical_locations = PhysicalLocations.execute(llm, query)
                duration_seconds = time.time() - start_time

                # Update LLM interaction COMPLETE
                response_dict = physical_locations.to_dict()
                db_service.update_llm_interaction(interaction_id, {
                    "status": "completed",
                    "response_text": json.dumps(response_dict),
                    "completed_at": datetime.utcnow(),
                    "duration_seconds": duration_seconds
                })

                # Persist RAW to database
                raw_content = json.dumps(response_dict, indent=2)
                db_service.create_plan_content({
                    "plan_id": plan_id,
                    "filename": FilenameEnum.PHYSICAL_LOCATIONS_RAW.value,
                    "stage": "physical_locations",
                    "content_type": "json",
                    "content": raw_content,
                    "content_size_bytes": len(raw_content.encode('utf-8'))
                })

                # Persist MARKDOWN to database
                markdown_content = physical_locations.markdown
                db_service.create_plan_content({
                    "plan_id": plan_id,
                    "filename": FilenameEnum.PHYSICAL_LOCATIONS_MARKDOWN.value,
                    "stage": "physical_locations",
                    "content_type": "markdown",
                    "content": markdown_content,
                    "content_size_bytes": len(markdown_content.encode('utf-8'))
                })

                # Write the physical locations to disk (Luigi tracking)
                physical_locations.save_raw(str(output_raw_path))
                physical_locations.save_markdown(str(output_markdown_path))
            else:
                # Digital plan - no LLM call needed, but still persist to database
                data = {
                    "comment": "The plan is purely digital, without any physical locations."
                }
                digital_message = "The plan is purely digital, without any physical locations."

                # Persist RAW to database
                raw_content = json.dumps(data, indent=2)
                db_service.create_plan_content({
                    "plan_id": plan_id,
                    "filename": FilenameEnum.PHYSICAL_LOCATIONS_RAW.value,
                    "stage": "physical_locations",
                    "content_type": "json",
                    "content": raw_content,
                    "content_size_bytes": len(raw_content.encode('utf-8'))
                })

                # Persist MARKDOWN to database
                db_service.create_plan_content({
                    "plan_id": plan_id,
                    "filename": FilenameEnum.PHYSICAL_LOCATIONS_MARKDOWN.value,
                    "stage": "physical_locations",
                    "content_type": "markdown",
                    "content": digital_message,
                    "content_size_bytes": len(digital_message.encode('utf-8'))
                })

                # Write to filesystem (Luigi tracking)
                with open(output_raw_path, "w") as f:
                    json.dump(data, f, indent=2)

                with open(output_markdown_path, "w", encoding='utf-8') as f:
                    f.write(digital_message)

        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {
                        "status": "failed",
                        "error_message": str(e),
                        "completed_at": datetime.utcnow()
                    })
                except Exception as db_error:
                    logger.error(f"Failed to update interaction status: {db_error}")
            raise
        finally:
            if db_service:
                db_service.close()

class CurrencyStrategyTask(PlanTask):
    """
    Identify/suggest what currency to use for the plan, depending on the physical locations.
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'plan_type': self.clone(PlanTypeTask),
            'physical_locations': self.clone(PhysicalLocationsTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.CURRENCY_STRATEGY_RAW),
            'markdown': self.local_target(FilenameEnum.CURRENCY_STRATEGY_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()

        try:
            db_service = self.get_database_service()

            # Read inputs from required tasks.
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['identify_purpose']['markdown'].open("r") as f:
                identify_purpose_markdown = f.read()
            with self.input()['plan_type']['markdown'].open("r") as f:
                plan_type_markdown = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['physical_locations']['markdown'].open("r") as f:
                physical_locations_markdown = f.read()

            query = (
                f"File 'plan.txt':\n{plan_prompt}\n\n"
                f"File 'purpose.md':\n{identify_purpose_markdown}\n\n"
                f"File 'plan_type.md':\n{plan_type_markdown}\n\n"
                f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n"
                f"File 'scenarios.md':\n{scenarios_markdown}\n\n"
                f"File 'physical_locations.md':\n{physical_locations_markdown}"
            )

            # Track LLM interaction START
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "currency_strategy",
                "prompt_text": query,
                "status": "pending"
            }).id

            # Execute LLM call with timing
            import time
            start_time = time.time()
            currency_strategy = CurrencyStrategy.execute(llm, query)
            duration_seconds = time.time() - start_time

            # Update LLM interaction COMPLETE
            response_dict = currency_strategy.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })

            # Persist RAW to database
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.CURRENCY_STRATEGY_RAW.value,
                "stage": "currency_strategy",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })

            # Persist MARKDOWN to database
            markdown_content = currency_strategy.markdown
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.CURRENCY_STRATEGY_MARKDOWN.value,
                "stage": "currency_strategy",
                "content_type": "markdown",
                "content": markdown_content,
                "content_size_bytes": len(markdown_content.encode('utf-8'))
            })

            # Write to filesystem (Luigi tracking)
            output_raw_path = self.output()['raw'].path
            currency_strategy.save_raw(str(output_raw_path))
            output_markdown_path = self.output()['markdown'].path
            currency_strategy.save_markdown(str(output_markdown_path))

        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {
                        "status": "failed",
                        "error_message": str(e),
                        "completed_at": datetime.utcnow()
                    })
                except Exception as db_error:
                    logger.error(f"Failed to update interaction status: {db_error}")
            raise
        finally:
            if db_service:
                db_service.close()


class IdentifyRisksTask(PlanTask):
    """
    Identify risks for the plan, depending on the physical locations.
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'plan_type': self.clone(PlanTypeTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'physical_locations': self.clone(PhysicalLocationsTask),
            'currency_strategy': self.clone(CurrencyStrategyTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.IDENTIFY_RISKS_RAW),
            'markdown': self.local_target(FilenameEnum.IDENTIFY_RISKS_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()

        try:
            db_service = self.get_database_service()

            # Read inputs from required tasks.
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['identify_purpose']['markdown'].open("r") as f:
                identify_purpose_markdown = f.read()
            with self.input()['plan_type']['markdown'].open("r") as f:
                plan_type_markdown = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['physical_locations']['markdown'].open("r") as f:
                physical_locations_markdown = f.read()
            with self.input()['currency_strategy']['markdown'].open("r") as f:
                currency_strategy_markdown = f.read()

            query = (
                f"File 'plan.txt':\n{plan_prompt}\n\n"
                f"File 'purpose.md':\n{identify_purpose_markdown}\n\n"
                f"File 'plan_type.md':\n{plan_type_markdown}\n\n"
                f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n"
                f"File 'scenarios.md':\n{scenarios_markdown}\n\n"
                f"File 'physical_locations.md':\n{physical_locations_markdown}\n\n"
                f"File 'currency_strategy.md':\n{currency_strategy_markdown}"
            )

            # Track LLM interaction START
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "identify_risks",
                "prompt_text": query,
                "status": "pending"
            }).id

            # Execute LLM call with timing
            import time
            start_time = time.time()
            identify_risks = IdentifyRisks.execute(llm, query)
            duration_seconds = time.time() - start_time

            # Update LLM interaction COMPLETE
            response_dict = identify_risks.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })

            # Persist RAW to database
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.IDENTIFY_RISKS_RAW.value,
                "stage": "identify_risks",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })

            # Persist MARKDOWN to database
            markdown_content = identify_risks.markdown
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.IDENTIFY_RISKS_MARKDOWN.value,
                "stage": "identify_risks",
                "content_type": "markdown",
                "content": markdown_content,
                "content_size_bytes": len(markdown_content.encode('utf-8'))
            })

            # Write to filesystem (Luigi tracking)
            output_raw_path = self.output()['raw'].path
            identify_risks.save_raw(str(output_raw_path))
            output_markdown_path = self.output()['markdown'].path
            identify_risks.save_markdown(str(output_markdown_path))

        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {
                        "status": "failed",
                        "error_message": str(e),
                        "completed_at": datetime.utcnow()
                    })
                except Exception as db_error:
                    logger.error(f"Failed to update interaction status: {db_error}")
            raise
        finally:
            if db_service:
                db_service.close()


class MakeAssumptionsTask(PlanTask):
    """
    Make assumptions about the plan.
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'plan_type': self.clone(PlanTypeTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'physical_locations': self.clone(PhysicalLocationsTask),
            'currency_strategy': self.clone(CurrencyStrategyTask),
            'identify_risks': self.clone(IdentifyRisksTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.MAKE_ASSUMPTIONS_RAW),
            'clean': self.local_target(FilenameEnum.MAKE_ASSUMPTIONS_CLEAN),
            'markdown': self.local_target(FilenameEnum.MAKE_ASSUMPTIONS_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()

        try:
            db_service = self.get_database_service()

            # Read inputs from required tasks.
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['identify_purpose']['markdown'].open("r") as f:
                identify_purpose_markdown = f.read()
            with self.input()['plan_type']['markdown'].open("r") as f:
                plan_type_markdown = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['physical_locations']['markdown'].open("r") as f:
                physical_locations_markdown = f.read()
            with self.input()['currency_strategy']['markdown'].open("r") as f:
                currency_strategy_markdown = f.read()
            with self.input()['identify_risks']['markdown'].open("r") as f:
                identify_risks_markdown = f.read()

            query = (
                f"File 'plan.txt':\n{plan_prompt}\n\n"
                f"File 'purpose.md':\n{identify_purpose_markdown}\n\n"
                f"File 'plan_type.md':\n{plan_type_markdown}\n\n"
                f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n"
                f"File 'scenarios.md':\n{scenarios_markdown}\n\n"
                f"File 'physical_locations.md':\n{physical_locations_markdown}\n\n"
                f"File 'currency_strategy.md':\n{currency_strategy_markdown}\n\n"
                f"File 'identify_risks.md':\n{identify_risks_markdown}"
            )

            # Track LLM interaction START
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "make_assumptions",
                "prompt_text": query,
                "status": "pending"
            }).id

            # Execute LLM call with timing
            import time
            start_time = time.time()
            make_assumptions = MakeAssumptions.execute(llm, query)
            duration_seconds = time.time() - start_time

            # Update LLM interaction COMPLETE
            response_dict = make_assumptions.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })

            # Persist RAW to database
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.MAKE_ASSUMPTIONS_RAW.value,
                "stage": "make_assumptions",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })

            # Persist CLEAN to database
            clean_content = make_assumptions.to_clean_json()
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.MAKE_ASSUMPTIONS_CLEAN.value,
                "stage": "make_assumptions",
                "content_type": "json",
                "content": clean_content,
                "content_size_bytes": len(clean_content.encode('utf-8'))
            })

            # Persist MARKDOWN to database
            markdown_content = make_assumptions.markdown
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.MAKE_ASSUMPTIONS_MARKDOWN.value,
                "stage": "make_assumptions",
                "content_type": "markdown",
                "content": markdown_content,
                "content_size_bytes": len(markdown_content.encode('utf-8'))
            })

            # Write to filesystem (Luigi tracking)
            output_raw_path = self.output()['raw'].path
            make_assumptions.save_raw(str(output_raw_path))
            output_clean_path = self.output()['clean'].path
            make_assumptions.save_assumptions(str(output_clean_path))
            output_markdown_path = self.output()['markdown'].path
            make_assumptions.save_markdown(str(output_markdown_path))

        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {
                        "status": "failed",
                        "error_message": str(e),
                        "completed_at": datetime.utcnow()
                    })
                except Exception as db_error:
                    logger.error(f"Failed to update interaction status: {db_error}")
            raise
        finally:
            if db_service:
                db_service.close()


class DistillAssumptionsTask(PlanTask):
    """
    Distill raw assumption data.
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'make_assumptions': self.clone(MakeAssumptionsTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.DISTILL_ASSUMPTIONS_RAW),
            'markdown': self.local_target(FilenameEnum.DISTILL_ASSUMPTIONS_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()

        try:
            db_service = self.get_database_service()

            # Read inputs from required tasks.
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['identify_purpose']['markdown'].open("r") as f:
                identify_purpose_markdown = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            make_assumptions_target = self.input()['make_assumptions']['clean']
            with make_assumptions_target.open("r") as f:
                assumptions_raw_data = json.load(f)

            query = (
                f"File 'plan.txt':\n{plan_prompt}\n\n"
                f"File 'purpose.md':\n{identify_purpose_markdown}\n\n"
                f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n"
                f"File 'scenarios.md':\n{scenarios_markdown}\n\n"
                f"File 'assumptions.json':\n{format_json_for_use_in_query(assumptions_raw_data)}"
            )

            # Track LLM interaction START
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "distill_assumptions",
                "prompt_text": query,
                "status": "pending"
            }).id

            # Execute LLM call with timing
            import time
            start_time = time.time()
            distill_assumptions = DistillAssumptions.execute(llm, query)
            duration_seconds = time.time() - start_time

            # Update LLM interaction COMPLETE
            response_dict = distill_assumptions.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })

            # Persist RAW to database
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.DISTILL_ASSUMPTIONS_RAW.value,
                "stage": "distill_assumptions",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })

            # Persist MARKDOWN to database
            markdown_content = distill_assumptions.markdown
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.DISTILL_ASSUMPTIONS_MARKDOWN.value,
                "stage": "distill_assumptions",
                "content_type": "markdown",
                "content": markdown_content,
                "content_size_bytes": len(markdown_content.encode('utf-8'))
            })

            # Write to filesystem (Luigi tracking)
            output_raw_path = self.output()['raw'].path
            distill_assumptions.save_raw(str(output_raw_path))
            output_markdown_path = self.output()['markdown'].path
            distill_assumptions.save_markdown(str(output_markdown_path))

        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {
                        "status": "failed",
                        "error_message": str(e),
                        "completed_at": datetime.utcnow()
                    })
                except Exception as db_error:
                    logger.error(f"Failed to update interaction status: {db_error}")
            raise
        finally:
            if db_service:
                db_service.close()


class ReviewAssumptionsTask(PlanTask):
    """
    Find issues with the assumptions.
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'plan_type': self.clone(PlanTypeTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'physical_locations': self.clone(PhysicalLocationsTask),
            'currency_strategy': self.clone(CurrencyStrategyTask),
            'identify_risks': self.clone(IdentifyRisksTask),
            'make_assumptions': self.clone(MakeAssumptionsTask),
            'distill_assumptions': self.clone(DistillAssumptionsTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.REVIEW_ASSUMPTIONS_RAW),
            'markdown': self.local_target(FilenameEnum.REVIEW_ASSUMPTIONS_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()

        try:
            db_service = self.get_database_service()

            # Define the list of (title, path) tuples
            title_path_list = [
                ('Purpose', self.input()['identify_purpose']['markdown'].path),
                ('Plan Type', self.input()['plan_type']['markdown'].path),
                ('Strategic Decisions', self.input()['strategic_decisions_markdown']['markdown'].path),
                ('Scenarios', self.input()['scenarios_markdown']['markdown'].path),
                ('Physical Locations', self.input()['physical_locations']['markdown'].path),
                ('Currency Strategy', self.input()['currency_strategy']['markdown'].path),
                ('Identify Risks', self.input()['identify_risks']['markdown'].path),
                ('Make Assumptions', self.input()['make_assumptions']['markdown'].path),
                ('Distill Assumptions', self.input()['distill_assumptions']['markdown'].path)
            ]

            # Read the files and handle exceptions
            markdown_chunks = []
            for title, path in title_path_list:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        markdown_chunk = f.read()
                    markdown_chunks.append(f"# {title}\n\n{markdown_chunk}")
                except FileNotFoundError:
                    logger.warning(f"Markdown file not found: {path} (from {title})")
                    markdown_chunks.append(f"**Problem with document:** '{title}'\n\nFile not found.")
                except Exception as e:
                    logger.error(f"Error reading markdown file {path} (from {title}): {e}")
                    markdown_chunks.append(f"**Problem with document:** '{title}'\n\nError reading markdown file.")

            # Combine the markdown chunks
            full_markdown = "\n\n".join(markdown_chunks)

            # Track LLM interaction START
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "review_assumptions",
                "prompt_text": full_markdown[:10000],  # Truncate for storage
                "status": "pending"
            }).id

            # Execute LLM call with timing
            import time
            start_time = time.time()
            review_assumptions = ReviewAssumptions.execute(llm, full_markdown)
            duration_seconds = time.time() - start_time

            # Update LLM interaction COMPLETE
            response_dict = review_assumptions.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })

            # Persist RAW to database
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.REVIEW_ASSUMPTIONS_RAW.value,
                "stage": "review_assumptions",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })

            # Persist MARKDOWN to database
            markdown_content = review_assumptions.markdown
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.REVIEW_ASSUMPTIONS_MARKDOWN.value,
                "stage": "review_assumptions",
                "content_type": "markdown",
                "content": markdown_content,
                "content_size_bytes": len(markdown_content.encode('utf-8'))
            })

            # Write to filesystem (Luigi tracking)
            output_raw_path = self.output()['raw'].path
            review_assumptions.save_raw(str(output_raw_path))
            output_markdown_path = self.output()['markdown'].path
            review_assumptions.save_markdown(str(output_markdown_path))

        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {
                        "status": "failed",
                        "error_message": str(e),
                        "completed_at": datetime.utcnow()
                    })
                except Exception as db_error:
                    logger.error(f"Failed to update interaction status: {db_error}")
            raise
        finally:
            if db_service:
                db_service.close()


class ConsolidateAssumptionsMarkdownTask(PlanTask):
    """
    Combines multiple small markdown documents into a single big document.
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'plan_type': self.clone(PlanTypeTask),
            'physical_locations': self.clone(PhysicalLocationsTask),
            'currency_strategy': self.clone(CurrencyStrategyTask),
            'identify_risks': self.clone(IdentifyRisksTask),
            'make_assumptions': self.clone(MakeAssumptionsTask),
            'distill_assumptions': self.clone(DistillAssumptionsTask),
            'review_assumptions': self.clone(ReviewAssumptionsTask)
        }

    def output(self):
        return {
            'full': self.local_target(FilenameEnum.CONSOLIDATE_ASSUMPTIONS_FULL_MARKDOWN),
            'short': self.local_target(FilenameEnum.CONSOLIDATE_ASSUMPTIONS_SHORT_MARKDOWN)
        }

    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()

        try:
            db_service = self.get_database_service()
            llm_executor: LLMExecutor = self.create_llm_executor()

            # Define the list of (title, path) tuples
            title_path_list = [
                ('Purpose', self.input()['identify_purpose']['markdown'].path),
                ('Plan Type', self.input()['plan_type']['markdown'].path),
                ('Physical Locations', self.input()['physical_locations']['markdown'].path),
                ('Currency Strategy', self.input()['currency_strategy']['markdown'].path),
                ('Identify Risks', self.input()['identify_risks']['markdown'].path),
                ('Make Assumptions', self.input()['make_assumptions']['markdown'].path),
                ('Distill Assumptions', self.input()['distill_assumptions']['markdown'].path),
                ('Review Assumptions', self.input()['review_assumptions']['markdown'].path)
            ]

            # Read the files and handle exceptions
            full_markdown_chunks = []
            short_markdown_chunks = []
            for title, path in title_path_list:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        markdown_chunk = f.read()
                    full_markdown_chunks.append(f"# {title}\n\n{markdown_chunk}")
                except FileNotFoundError:
                    logger.warning(f"Markdown file not found: {path} (from {title})")
                    full_markdown_chunks.append(f"**Problem with document:** '{title}'\n\nFile not found.")
                    short_markdown_chunks.append(f"**Problem with document:** '{title}'\n\nFile not found.")
                    continue
                except Exception as e:
                    logger.error(f"Error reading markdown file {path} (from {title}): {e}")
                    full_markdown_chunks.append(f"**Problem with document:** '{title}'\n\nError reading markdown file.")
                    short_markdown_chunks.append(f"**Problem with document:** '{title}'\n\nError reading markdown file.")
                    continue

                # IDEA: If the chunk file already exist, then there is no need to run the LLM again.
                def execute_shorten_markdown(llm: LLM) -> ShortenMarkdown:
                    return ShortenMarkdown.execute(llm, markdown_chunk)

                try:
                    shorten_markdown = llm_executor.run(execute_shorten_markdown)
                    short_markdown_chunks.append(f"# {title}\n{shorten_markdown.markdown}")
                except PipelineStopRequested:
                    # Re-raise PipelineStopRequested without wrapping it
                    raise
                except Exception as e:
                    logger.error(f"Error shortening markdown file {path} (from {title}): {e}")
                    short_markdown_chunks.append(f"**Problem with document:** '{title}'\n\nError shortening markdown file.")
                    continue

            # Combine the markdown chunks
            full_markdown = "\n\n".join(full_markdown_chunks)
            short_markdown = "\n\n".join(short_markdown_chunks)

            # Persist FULL MARKDOWN to database
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.CONSOLIDATE_ASSUMPTIONS_FULL_MARKDOWN.value,
                "stage": "consolidate_assumptions",
                "content_type": "markdown",
                "content": full_markdown,
                "content_size_bytes": len(full_markdown.encode('utf-8'))
            })

            # Persist SHORT MARKDOWN to database
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.CONSOLIDATE_ASSUMPTIONS_SHORT_MARKDOWN.value,
                "stage": "consolidate_assumptions",
                "content_type": "markdown",
                "content": short_markdown,
                "content_size_bytes": len(short_markdown.encode('utf-8'))
            })

            # Write to filesystem (Luigi tracking)
            output_full_markdown_path = self.output()['full'].path
            with open(output_full_markdown_path, "w", encoding="utf-8") as f:
                f.write(full_markdown)

            output_short_markdown_path = self.output()['short'].path
            with open(output_short_markdown_path, "w", encoding="utf-8") as f:
                f.write(short_markdown)

        except Exception as e:
            logger.error(f"Error in ConsolidateAssumptionsMarkdownTask: {e}")
            raise
        finally:
            if db_service:
                db_service.close()


class PreProjectAssessmentTask(PlanTask):
    """
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.PRE_PROJECT_ASSESSMENT_RAW),
            'clean': self.local_target(FilenameEnum.PRE_PROJECT_ASSESSMENT)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()

        try:
            db_service = self.get_database_service()
            logger.info("Conducting pre-project assessment...")

            # Read the plan prompt from the SetupTask's output.
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()

            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()

            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                consolidate_assumptions_markdown = f.read()

            # Build the query.
            query = (
                f"File 'plan.txt':\n{plan_prompt}\n\n"
                f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n"
                f"File 'scenarios.md':\n{scenarios_markdown}\n\n"
                f"File 'assumptions.md':\n{consolidate_assumptions_markdown}"
            )

            # Track LLM interaction START
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "pre_project_assessment",
                "prompt_text": query[:10000],  # Truncate for storage
                "status": "pending"
            }).id

            # Execute LLM call with timing
            import time
            start_time = time.time()
            pre_project_assessment = PreProjectAssessment.execute(llm, query)
            duration_seconds = time.time() - start_time

            # Update LLM interaction COMPLETE
            response_dict = pre_project_assessment.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })

            # Persist RAW to database
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.PRE_PROJECT_ASSESSMENT_RAW.value,
                "stage": "pre_project_assessment",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })

            # Persist CLEAN to database
            clean_content = pre_project_assessment.to_clean_json()
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.PRE_PROJECT_ASSESSMENT.value,
                "stage": "pre_project_assessment",
                "content_type": "json",
                "content": clean_content,
                "content_size_bytes": len(clean_content.encode('utf-8'))
            })

            # Write to filesystem (Luigi tracking)
            raw_path = self.file_path(FilenameEnum.PRE_PROJECT_ASSESSMENT_RAW)
            pre_project_assessment.save_raw(str(raw_path))
            clean_path = self.file_path(FilenameEnum.PRE_PROJECT_ASSESSMENT)
            pre_project_assessment.save_preproject_assessment(str(clean_path))

        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {
                        "status": "failed",
                        "error_message": str(e),
                        "completed_at": datetime.utcnow()
                    })
                except Exception as db_error:
                    logger.error(f"Failed to update interaction status: {db_error}")
            raise
        finally:
            if db_service:
                db_service.close()


class ProjectPlanTask(PlanTask):
    """
    DATABASE INTEGRATION: Option 1 (Database-First Architecture)
    """
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'preproject': self.clone(PreProjectAssessmentTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.PROJECT_PLAN_RAW),
            'markdown': self.local_target(FilenameEnum.PROJECT_PLAN_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()

        try:
            db_service = self.get_database_service()
            logger.info("Creating plan...")

            # Read the plan prompt from SetupTask's output.
            setup_target = self.input()['setup']
            with setup_target.open("r") as f:
                plan_prompt = f.read()

            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()

            # Load the consolidated assumptions.
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                consolidate_assumptions_markdown = f.read()

            # Read the pre-project assessment from its file.
            pre_project_assessment_file = self.input()['preproject']['clean']
            with pre_project_assessment_file.open("r") as f:
                pre_project_assessment_dict = json.load(f)

            # Build the query.
            query = (
                f"File 'plan.txt':\n{plan_prompt}\n\n"
                f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n"
                f"File 'scenarios.md':\n{scenarios_markdown}\n\n"
                f"File 'assumptions.md':\n{consolidate_assumptions_markdown}\n\n"
                f"File 'pre-project-assessment.json':\n{format_json_for_use_in_query(pre_project_assessment_dict)}"
            )

            # Track LLM interaction START
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id,
                "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "project_plan",
                "prompt_text": query[:10000],  # Truncate for storage
                "status": "pending"
            }).id

            # Execute LLM call with timing
            import time
            start_time = time.time()
            project_plan = ProjectPlan.execute(llm, query)
            duration_seconds = time.time() - start_time

            # Update LLM interaction COMPLETE
            response_dict = project_plan.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed",
                "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(),
                "duration_seconds": duration_seconds
            })

            # Persist RAW to database
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.PROJECT_PLAN_RAW.value,
                "stage": "project_plan",
                "content_type": "json",
                "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })

            # Persist MARKDOWN to database
            markdown_content = project_plan.markdown
            db_service.create_plan_content({
                "plan_id": plan_id,
                "filename": FilenameEnum.PROJECT_PLAN_MARKDOWN.value,
                "stage": "project_plan",
                "content_type": "markdown",
                "content": markdown_content,
                "content_size_bytes": len(markdown_content.encode('utf-8'))
            })

            # Write to filesystem (Luigi tracking)
            project_plan.save_raw(self.output()['raw'].path)
            project_plan.save_markdown(self.output()['markdown'].path)

            logger.info("Project plan created and saved")

        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {
                        "status": "failed",
                        "error_message": str(e),
                        "completed_at": datetime.utcnow()
                    })
                except Exception as db_error:
                    logger.error(f"Failed to update interaction status: {db_error}")
            raise
        finally:
            if db_service:
                db_service.close()


class GovernancePhase1AuditTask(PlanTask):
    """DATABASE INTEGRATION: Option 1 (Database-First Architecture)"""
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.GOVERNANCE_PHASE1_AUDIT_RAW),
            'markdown': self.local_target(FilenameEnum.GOVERNANCE_PHASE1_AUDIT_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                consolidate_assumptions_markdown = f.read()
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            query = (
                f"File 'initial-plan.txt':\n{plan_prompt}\n\n"
                f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n"
                f"File 'scenarios.md':\n{scenarios_markdown}\n\n"
                f"File 'assumptions.md':\n{consolidate_assumptions_markdown}\n\n"
                f"File 'project-plan.md':\n{project_plan_markdown}"
            )
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "governance_phase1", "prompt_text": query[:10000], "status": "pending"
            }).id
            import time
            start_time = time.time()
            governance_phase1_audit = GovernancePhase1Audit.execute(llm, query)
            duration_seconds = time.time() - start_time
            response_dict = governance_phase1_audit.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed", "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds
            })
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id, "filename": FilenameEnum.GOVERNANCE_PHASE1_AUDIT_RAW.value,
                "stage": "governance_phase1", "content_type": "json", "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })
            markdown_content = governance_phase1_audit.markdown
            db_service.create_plan_content({
                "plan_id": plan_id, "filename": FilenameEnum.GOVERNANCE_PHASE1_AUDIT_MARKDOWN.value,
                "stage": "governance_phase1", "content_type": "markdown", "content": markdown_content,
                "content_size_bytes": len(markdown_content.encode('utf-8'))
            })
            governance_phase1_audit.save_raw(self.output()['raw'].path)
            governance_phase1_audit.save_markdown(self.output()['markdown'].path)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception as db_error:
                    logger.error(f"Failed to update interaction status: {db_error}")
            raise
        finally:
            if db_service:
                db_service.close()


class GovernancePhase2BodiesTask(PlanTask):
    """DATABASE INTEGRATION: Option 1 (Database-First Architecture)"""
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'governance_phase1_audit': self.clone(GovernancePhase1AuditTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.GOVERNANCE_PHASE2_BODIES_RAW),
            'markdown': self.local_target(FilenameEnum.GOVERNANCE_PHASE2_BODIES_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                consolidate_assumptions_markdown = f.read()
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['governance_phase1_audit']['markdown'].open("r") as f:
                governance_phase1_audit_markdown = f.read()
            query = (
                f"File 'initial-plan.txt':\n{plan_prompt}\n\n"
                f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n"
                f"File 'scenarios.md':\n{scenarios_markdown}\n\n"
                f"File 'assumptions.md':\n{consolidate_assumptions_markdown}\n\n"
                f"File 'project-plan.md':\n{project_plan_markdown}\n\n"
                f"File 'governance-phase1-audit.md':\n{governance_phase1_audit_markdown}"
            )
            interaction_id = db_service.create_llm_interaction({
                "plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown",
                "stage": "governance_phase2", "prompt_text": query[:10000], "status": "pending"
            }).id
            import time
            start_time = time.time()
            governance_phase2_bodies = GovernancePhase2Bodies.execute(llm, query)
            duration_seconds = time.time() - start_time
            response_dict = governance_phase2_bodies.to_dict()
            db_service.update_llm_interaction(interaction_id, {
                "status": "completed", "response_text": json.dumps(response_dict),
                "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds
            })
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({
                "plan_id": plan_id, "filename": FilenameEnum.GOVERNANCE_PHASE2_BODIES_RAW.value,
                "stage": "governance_phase2", "content_type": "json", "content": raw_content,
                "content_size_bytes": len(raw_content.encode('utf-8'))
            })
            markdown_content = governance_phase2_bodies.markdown
            db_service.create_plan_content({
                "plan_id": plan_id, "filename": FilenameEnum.GOVERNANCE_PHASE2_BODIES_MARKDOWN.value,
                "stage": "governance_phase2", "content_type": "markdown", "content": markdown_content,
                "content_size_bytes": len(markdown_content.encode('utf-8'))
            })
            governance_phase2_bodies.save_raw(self.output()['raw'].path)
            governance_phase2_bodies.save_markdown(self.output()['markdown'].path)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception as db_error:
                    logger.error(f"Failed to update interaction status: {db_error}")
            raise
        finally:
            if db_service:
                db_service.close()


class GovernancePhase3ImplPlanTask(PlanTask):
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'governance_phase2_bodies': self.clone(GovernancePhase2BodiesTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.GOVERNANCE_PHASE3_IMPL_PLAN_RAW),
            'markdown': self.local_target(FilenameEnum.GOVERNANCE_PHASE3_IMPL_PLAN_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        """DATABASE INTEGRATION: Option 1 (Database-First Architecture)"""
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                consolidate_assumptions_markdown = f.read()
            with self.input()['project_plan']['raw'].open("r") as f:
                project_plan_dict = json.load(f)
            with self.input()['governance_phase2_bodies']['raw'].open("r") as f:
                governance_phase2_bodies_dict = json.load(f)
            query = (
                f"File 'initial-plan.txt':\n{plan_prompt}\n\n"
                f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n"
                f"File 'scenarios.md':\n{scenarios_markdown}\n\n"
                f"File 'assumptions.md':\n{consolidate_assumptions_markdown}\n\n"
                f"File 'project-plan.json':\n{format_json_for_use_in_query(project_plan_dict)}\n\n"
                f"File 'governance-phase2-bodies.json':\n{format_json_for_use_in_query(governance_phase2_bodies_dict)}"
            )
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "governance_phase3", "prompt_text": query[:10000], "status": "pending"}).id
            import time
            start_time = time.time()
            governance_phase3_impl_plan = GovernancePhase3ImplPlan.execute(llm, query)
            duration_seconds = time.time() - start_time
            response_dict = governance_phase3_impl_plan.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(response_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.GOVERNANCE_PHASE3_IMPL_PLAN_RAW.value, "stage": "governance_phase3", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            markdown_content = governance_phase3_impl_plan.markdown
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.GOVERNANCE_PHASE3_IMPL_PLAN_MARKDOWN.value, "stage": "governance_phase3", "content_type": "markdown", "content": markdown_content, "content_size_bytes": len(markdown_content.encode('utf-8'))})
            governance_phase3_impl_plan.save_raw(self.output()['raw'].path)
            governance_phase3_impl_plan.save_markdown(self.output()['markdown'].path)
        except Exception as e:
            logger.error("GovernancePhase3ImplPlan failed: %s", e)
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception as db_error:
                    logger.error(f"Failed to update interaction status: {db_error}")
            raise
        finally:
            if db_service:
                db_service.close()

class GovernancePhase4DecisionEscalationMatrixTask(PlanTask):
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'governance_phase2_bodies': self.clone(GovernancePhase2BodiesTask),
            'governance_phase3_impl_plan': self.clone(GovernancePhase3ImplPlanTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.GOVERNANCE_PHASE4_DECISION_ESCALATION_MATRIX_RAW),
            'markdown': self.local_target(FilenameEnum.GOVERNANCE_PHASE4_DECISION_ESCALATION_MATRIX_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                consolidate_assumptions_markdown = f.read()
            with self.input()['project_plan']['raw'].open("r") as f:
                project_plan_dict = json.load(f)
            with self.input()['governance_phase2_bodies']['raw'].open("r") as f:
                governance_phase2_bodies_dict = json.load(f)
            with self.input()['governance_phase3_impl_plan']['raw'].open("r") as f:
                governance_phase3_impl_plan_dict = json.load(f)
            query = (
                f"File 'initial-plan.txt':\n{plan_prompt}\n\n"
                f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n"
                f"File 'scenarios.md':\n{scenarios_markdown}\n\n"
                f"File 'assumptions.md':\n{consolidate_assumptions_markdown}\n\n"
                f"File 'project-plan.json':\n{format_json_for_use_in_query(project_plan_dict)}\n\n"
                f"File 'governance-phase2-bodies.json':\n{format_json_for_use_in_query(governance_phase2_bodies_dict)}\n\n"
                f"File 'governance-phase3-impl-plan.json':\n{format_json_for_use_in_query(governance_phase3_impl_plan_dict)}"
            )
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "governance_phase4", "prompt_text": query[:10000], "status": "pending"}).id
            import time
            start_time = time.time()
            governance_phase4_decision_escalation_matrix = GovernancePhase4DecisionEscalationMatrix.execute(llm, query)
            duration_seconds = time.time() - start_time
            response_dict = governance_phase4_decision_escalation_matrix.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(response_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.GOVERNANCE_PHASE4_DECISION_ESCALATION_MATRIX_RAW.value, "stage": "governance_phase4", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            markdown_content = governance_phase4_decision_escalation_matrix.markdown
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.GOVERNANCE_PHASE4_DECISION_ESCALATION_MATRIX_MARKDOWN.value, "stage": "governance_phase4", "content_type": "markdown", "content": markdown_content, "content_size_bytes": len(markdown_content.encode('utf-8'))})
            governance_phase4_decision_escalation_matrix.save_raw(self.output()['raw'].path)
            governance_phase4_decision_escalation_matrix.save_markdown(self.output()['markdown'].path)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception as db_error:
                    logger.error(f"Failed to update interaction status: {db_error}")
            raise
        finally:
            if db_service:
                db_service.close()

class GovernancePhase5MonitoringProgressTask(PlanTask):
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'governance_phase2_bodies': self.clone(GovernancePhase2BodiesTask),
            'governance_phase3_impl_plan': self.clone(GovernancePhase3ImplPlanTask),
            'governance_phase4_decision_escalation_matrix': self.clone(GovernancePhase4DecisionEscalationMatrixTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.GOVERNANCE_PHASE5_MONITORING_PROGRESS_RAW),
            'markdown': self.local_target(FilenameEnum.GOVERNANCE_PHASE5_MONITORING_PROGRESS_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                consolidate_assumptions_markdown = f.read()
            with self.input()['project_plan']['raw'].open("r") as f:
                project_plan_dict = json.load(f)
            with self.input()['governance_phase2_bodies']['raw'].open("r") as f:
                governance_phase2_bodies_dict = json.load(f)
            with self.input()['governance_phase3_impl_plan']['raw'].open("r") as f:
                governance_phase3_impl_plan_dict = json.load(f)
            with self.input()['governance_phase4_decision_escalation_matrix']['raw'].open("r") as f:
                governance_phase4_decision_escalation_matrix_dict = json.load(f)
            query = (
                f"File 'initial-plan.txt':\n{plan_prompt}\n\n"
                f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n"
                f"File 'scenarios.md':\n{scenarios_markdown}\n\n"
                f"File 'assumptions.md':\n{consolidate_assumptions_markdown}\n\n"
                f"File 'project-plan.json':\n{format_json_for_use_in_query(project_plan_dict)}\n\n"
                f"File 'governance-phase2-bodies.json':\n{format_json_for_use_in_query(governance_phase2_bodies_dict)}\n\n"
                f"File 'governance-phase3-impl-plan.json':\n{format_json_for_use_in_query(governance_phase3_impl_plan_dict)}\n\n"
                f"File 'governance-phase4-decision-escalation-matrix.json':\n{format_json_for_use_in_query(governance_phase4_decision_escalation_matrix_dict)}"
            )
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "governance_phase5", "prompt_text": query[:10000], "status": "pending"}).id
            import time
            start_time = time.time()
            governance_phase5_monitoring_progress = GovernancePhase5MonitoringProgress.execute(llm, query)
            duration_seconds = time.time() - start_time
            response_dict = governance_phase5_monitoring_progress.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(response_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.GOVERNANCE_PHASE5_MONITORING_PROGRESS_RAW.value, "stage": "governance_phase5", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            markdown_content = governance_phase5_monitoring_progress.markdown
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.GOVERNANCE_PHASE5_MONITORING_PROGRESS_MARKDOWN.value, "stage": "governance_phase5", "content_type": "markdown", "content": markdown_content, "content_size_bytes": len(markdown_content.encode('utf-8'))})
            governance_phase5_monitoring_progress.save_raw(self.output()['raw'].path)
            governance_phase5_monitoring_progress.save_markdown(self.output()['markdown'].path)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception as db_error:
                    logger.error(f"Failed to update interaction status: {db_error}")
            raise
        finally:
            if db_service:
                db_service.close()

class GovernancePhase6ExtraTask(PlanTask):
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'governance_phase1_audit': self.clone(GovernancePhase1AuditTask),
            'governance_phase2_bodies': self.clone(GovernancePhase2BodiesTask),
            'governance_phase3_impl_plan': self.clone(GovernancePhase3ImplPlanTask),
            'governance_phase4_decision_escalation_matrix': self.clone(GovernancePhase4DecisionEscalationMatrixTask),
            'governance_phase5_monitoring_progress': self.clone(GovernancePhase5MonitoringProgressTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.GOVERNANCE_PHASE6_EXTRA_RAW),
            'markdown': self.local_target(FilenameEnum.GOVERNANCE_PHASE6_EXTRA_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                consolidate_assumptions_markdown = f.read()
            with self.input()['project_plan']['raw'].open("r") as f:
                project_plan_dict = json.load(f)
            with self.input()['governance_phase1_audit']['raw'].open("r") as f:
                governance_phase1_audit_dict = json.load(f)
            with self.input()['governance_phase2_bodies']['raw'].open("r") as f:
                governance_phase2_bodies_dict = json.load(f)
            with self.input()['governance_phase3_impl_plan']['raw'].open("r") as f:
                governance_phase3_impl_plan_dict = json.load(f)
            with self.input()['governance_phase4_decision_escalation_matrix']['raw'].open("r") as f:
                governance_phase4_decision_escalation_matrix_dict = json.load(f)
            with self.input()['governance_phase5_monitoring_progress']['raw'].open("r") as f:
                governance_phase5_monitoring_progress_dict = json.load(f)
            query = (
                f"File 'initial-plan.txt':\n{plan_prompt}\n\n"
                f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n"
                f"File 'scenarios.md':\n{scenarios_markdown}\n\n"
                f"File 'assumptions.md':\n{consolidate_assumptions_markdown}\n\n"
                f"File 'project-plan.json':\n{format_json_for_use_in_query(project_plan_dict)}\n\n"
                f"File 'governance-phase1-audit.json':\n{format_json_for_use_in_query(governance_phase1_audit_dict)}\n\n"
                f"File 'governance-phase2-bodies.json':\n{format_json_for_use_in_query(governance_phase2_bodies_dict)}\n\n"
                f"File 'governance-phase3-impl-plan.json':\n{format_json_for_use_in_query(governance_phase3_impl_plan_dict)}\n\n"
                f"File 'governance-phase4-decision-escalation-matrix.json':\n{format_json_for_use_in_query(governance_phase4_decision_escalation_matrix_dict)}\n\n"
                f"File 'governance-phase5-monitoring-progress.json':\n{format_json_for_use_in_query(governance_phase5_monitoring_progress_dict)}"
            )
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "governance_phase6", "prompt_text": query[:10000], "status": "pending"}).id
            import time
            start_time = time.time()
            governance_phase6_extra = GovernancePhase6Extra.execute(llm, query)
            duration_seconds = time.time() - start_time
            response_dict = governance_phase6_extra.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(response_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.GOVERNANCE_PHASE6_EXTRA_RAW.value, "stage": "governance_phase6", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            markdown_content = governance_phase6_extra.markdown
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.GOVERNANCE_PHASE6_EXTRA_MARKDOWN.value, "stage": "governance_phase6", "content_type": "markdown", "content": markdown_content, "content_size_bytes": len(markdown_content.encode('utf-8'))})
            governance_phase6_extra.save_raw(self.output()['raw'].path)
            governance_phase6_extra.save_markdown(self.output()['markdown'].path)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception as db_error:
                    logger.error(f"Failed to update interaction status: {db_error}")
            raise
        finally:
            if db_service:
                db_service.close()

class ConsolidateGovernanceTask(PlanTask):
    def requires(self):
        return {
            'governance_phase1_audit': self.clone(GovernancePhase1AuditTask),
            'governance_phase2_bodies': self.clone(GovernancePhase2BodiesTask),
            'governance_phase3_impl_plan': self.clone(GovernancePhase3ImplPlanTask),
            'governance_phase4_decision_escalation_matrix': self.clone(GovernancePhase4DecisionEscalationMatrixTask),
            'governance_phase5_monitoring_progress': self.clone(GovernancePhase5MonitoringProgressTask),
            'governance_phase6_extra': self.clone(GovernancePhase6ExtraTask)
        }

    def output(self):
        return self.local_target(FilenameEnum.CONSOLIDATE_GOVERNANCE_MARKDOWN)

    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['governance_phase1_audit']['markdown'].open("r") as f:
                governance_phase1_audit_markdown = f.read()
            with self.input()['governance_phase2_bodies']['markdown'].open("r") as f:
                governance_phase2_bodies_markdown = f.read()
            with self.input()['governance_phase3_impl_plan']['markdown'].open("r") as f:
                governance_phase3_impl_plan_markdown = f.read()
            with self.input()['governance_phase4_decision_escalation_matrix']['markdown'].open("r") as f:
                governance_phase4_decision_escalation_matrix_markdown = f.read()
            with self.input()['governance_phase5_monitoring_progress']['markdown'].open("r") as f:
                governance_phase5_monitoring_progress_markdown = f.read()
            with self.input()['governance_phase6_extra']['markdown'].open("r") as f:
                governance_phase6_extra_markdown = f.read()
            markdown = []
            markdown.append(f"# Governance Audit\n\n{governance_phase1_audit_markdown}")
            markdown.append(f"# Internal Governance Bodies\n\n{governance_phase2_bodies_markdown}")
            markdown.append(f"# Governance Implementation Plan\n\n{governance_phase3_impl_plan_markdown}")
            markdown.append(f"# Decision Escalation Matrix\n\n{governance_phase4_decision_escalation_matrix_markdown}")
            markdown.append(f"# Monitoring Progress\n\n{governance_phase5_monitoring_progress_markdown}")
            markdown.append(f"# Governance Extra\n\n{governance_phase6_extra_markdown}")
            content = "\n\n".join(markdown)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.CONSOLIDATE_GOVERNANCE_MARKDOWN.value, "stage": "consolidate_governance", "content_type": "markdown", "content": content, "content_size_bytes": len(content.encode('utf-8'))})
            with self.output().open("w") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Error in ConsolidateGovernanceTask: {e}")
            raise
        finally:
            if db_service:
                db_service.close()

class RelatedResourcesTask(PlanTask):
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.RELATED_RESOURCES_RAW),
            'markdown': self.local_target(FilenameEnum.RELATED_RESOURCES_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                consolidate_assumptions_markdown = f.read()
            with self.input()['project_plan']['raw'].open("r") as f:
                project_plan_dict = json.load(f)
            query = (
                f"File 'initial-plan.txt':\n{plan_prompt}\n\n"
                f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n"
                f"File 'scenarios.md':\n{scenarios_markdown}\n\n"
                f"File 'assumptions.md':\n{consolidate_assumptions_markdown}\n\n"
                f"File 'project-plan.json':\n{format_json_for_use_in_query(project_plan_dict)}"
            )
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "related_resources", "prompt_text": query[:10000], "status": "pending"}).id
            import time
            start_time = time.time()
            related_resources = RelatedResources.execute(llm, query)
            duration_seconds = time.time() - start_time
            response_dict = related_resources.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(response_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(response_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.RELATED_RESOURCES_RAW.value, "stage": "related_resources", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            markdown_content = related_resources.markdown
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.RELATED_RESOURCES_MARKDOWN.value, "stage": "related_resources", "content_type": "markdown", "content": markdown_content, "content_size_bytes": len(markdown_content.encode('utf-8'))})
            related_resources.save_raw(self.output()['raw'].path)
            related_resources.save_markdown(self.output()['markdown'].path)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception as db_error:
                    logger.error(f"Failed to update interaction status: {db_error}")
            raise
        finally:
            if db_service:
                db_service.close()

class FindTeamMembersTask(PlanTask):
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'preproject': self.clone(PreProjectAssessmentTask),
            'project_plan': self.clone(ProjectPlanTask),
            'related_resources': self.clone(RelatedResourcesTask),
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.FIND_TEAM_MEMBERS_RAW),
            'clean': self.local_target(FilenameEnum.FIND_TEAM_MEMBERS_CLEAN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                consolidate_assumptions_markdown = f.read()
            with self.input()['preproject']['clean'].open("r") as f:
                pre_project_assessment_dict = json.load(f)
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['related_resources']['markdown'].open("r") as f:
                related_resources_markdown = f.read()
            query = (f"File 'initial-plan.txt':\n{plan_prompt}\n\nFile 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'assumptions.md':\n{consolidate_assumptions_markdown}\n\nFile 'pre-project-assessment.json':\n{format_json_for_use_in_query(pre_project_assessment_dict)}\n\nFile 'project-plan.md':\n{project_plan_markdown}\n\nFile 'related-resources.md':\n{related_resources_markdown}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "find_team_members", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            find_team_members = FindTeamMembers.execute(llm, query)
            duration_seconds = time.time() - start_time
            raw_dict = find_team_members.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(raw_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.FIND_TEAM_MEMBERS_RAW.value, "stage": "find_team_members", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            team_member_list = find_team_members.team_member_list
            clean_content = json.dumps(team_member_list, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.FIND_TEAM_MEMBERS_CLEAN.value, "stage": "find_team_members", "content_type": "json", "content": clean_content, "content_size_bytes": len(clean_content.encode('utf-8'))})
            with self.output()['raw'].open("w") as f:
                json.dump(raw_dict, f, indent=2)
            with self.output()['clean'].open("w") as f:
                json.dump(team_member_list, f, indent=2)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class EnrichTeamMembersWithContractTypeTask(PlanTask):
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'preproject': self.clone(PreProjectAssessmentTask),
            'project_plan': self.clone(ProjectPlanTask),
            'find_team_members': self.clone(FindTeamMembersTask),
            'related_resources': self.clone(RelatedResourcesTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.ENRICH_TEAM_MEMBERS_CONTRACT_TYPE_RAW),
            'clean': self.local_target(FilenameEnum.ENRICH_TEAM_MEMBERS_CONTRACT_TYPE_CLEAN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                consolidate_assumptions_markdown = f.read()
            with self.input()['preproject']['clean'].open("r") as f:
                pre_project_assessment_dict = json.load(f)
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['find_team_members']['clean'].open("r") as f:
                team_member_list = json.load(f)
            with self.input()['related_resources']['markdown'].open("r") as f:
                related_resources_markdown = f.read()
            query = (f"File 'initial-plan.txt':\n{plan_prompt}\n\nFile 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'assumptions.md':\n{consolidate_assumptions_markdown}\n\nFile 'pre-project-assessment.json':\n{format_json_for_use_in_query(pre_project_assessment_dict)}\n\nFile 'project-plan.md':\n{project_plan_markdown}\n\nFile 'team-members-that-needs-to-be-enriched.json':\n{format_json_for_use_in_query(team_member_list)}\n\nFile 'related-resources.md':\n{related_resources_markdown}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "enrich_team_contract_type", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            enrich_team_members_with_contract_type = EnrichTeamMembersWithContractType.execute(llm, query, team_member_list)
            duration_seconds = time.time() - start_time
            raw_dict = enrich_team_members_with_contract_type.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(raw_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.ENRICH_TEAM_MEMBERS_CONTRACT_TYPE_RAW.value, "stage": "enrich_team_contract_type", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            team_member_list = enrich_team_members_with_contract_type.team_member_list
            clean_content = json.dumps(team_member_list, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.ENRICH_TEAM_MEMBERS_CONTRACT_TYPE_CLEAN.value, "stage": "enrich_team_contract_type", "content_type": "json", "content": clean_content, "content_size_bytes": len(clean_content.encode('utf-8'))})
            with self.output()['raw'].open("w") as f:
                json.dump(raw_dict, f, indent=2)
            with self.output()['clean'].open("w") as f:
                json.dump(team_member_list, f, indent=2)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class EnrichTeamMembersWithBackgroundStoryTask(PlanTask):
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'preproject': self.clone(PreProjectAssessmentTask),
            'project_plan': self.clone(ProjectPlanTask),
            'enrich_team_members_with_contract_type': self.clone(EnrichTeamMembersWithContractTypeTask),
            'related_resources': self.clone(RelatedResourcesTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.ENRICH_TEAM_MEMBERS_BACKGROUND_STORY_RAW),
            'clean': self.local_target(FilenameEnum.ENRICH_TEAM_MEMBERS_BACKGROUND_STORY_CLEAN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                consolidate_assumptions_markdown = f.read()
            with self.input()['preproject']['clean'].open("r") as f:
                pre_project_assessment_dict = json.load(f)
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['enrich_team_members_with_contract_type']['clean'].open("r") as f:
                team_member_list = json.load(f)
            with self.input()['related_resources']['markdown'].open("r") as f:
                related_resources_markdown = f.read()
            query = (f"File 'initial-plan.txt':\n{plan_prompt}\n\nFile 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'assumptions.md':\n{consolidate_assumptions_markdown}\n\nFile 'pre-project-assessment.json':\n{format_json_for_use_in_query(pre_project_assessment_dict)}\n\nFile 'project-plan.md':\n{project_plan_markdown}\n\nFile 'team-members-that-needs-to-be-enriched.json':\n{format_json_for_use_in_query(team_member_list)}\n\nFile 'related-resources.md':\n{related_resources_markdown}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "enrich_team_background", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            enrich_team_members_with_background_story = EnrichTeamMembersWithBackgroundStory.execute(llm, query, team_member_list)
            duration_seconds = time.time() - start_time
            raw_dict = enrich_team_members_with_background_story.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(raw_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.ENRICH_TEAM_MEMBERS_BACKGROUND_STORY_RAW.value, "stage": "enrich_team_background", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            team_member_list = enrich_team_members_with_background_story.team_member_list
            clean_content = json.dumps(team_member_list, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.ENRICH_TEAM_MEMBERS_BACKGROUND_STORY_CLEAN.value, "stage": "enrich_team_background", "content_type": "json", "content": clean_content, "content_size_bytes": len(clean_content.encode('utf-8'))})
            with self.output()['raw'].open("w") as f:
                json.dump(raw_dict, f, indent=2)
            with self.output()['clean'].open("w") as f:
                json.dump(team_member_list, f, indent=2)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class EnrichTeamMembersWithEnvironmentInfoTask(PlanTask):
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'preproject': self.clone(PreProjectAssessmentTask),
            'project_plan': self.clone(ProjectPlanTask),
            'enrich_team_members_with_background_story': self.clone(EnrichTeamMembersWithBackgroundStoryTask),
            'related_resources': self.clone(RelatedResourcesTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.ENRICH_TEAM_MEMBERS_ENVIRONMENT_INFO_RAW),
            'clean': self.local_target(FilenameEnum.ENRICH_TEAM_MEMBERS_ENVIRONMENT_INFO_CLEAN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                consolidate_assumptions_markdown = f.read()
            with self.input()['preproject']['clean'].open("r") as f:
                pre_project_assessment_dict = json.load(f)
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['enrich_team_members_with_background_story']['clean'].open("r") as f:
                team_member_list = json.load(f)
            with self.input()['related_resources']['markdown'].open("r") as f:
                related_resources_markdown = f.read()
            query = (f"File 'initial-plan.txt':\n{plan_prompt}\n\nFile 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'assumptions.md':\n{consolidate_assumptions_markdown}\n\nFile 'pre-project-assessment.json':\n{format_json_for_use_in_query(pre_project_assessment_dict)}\n\nFile 'project-plan.md':\n{project_plan_markdown}\n\nFile 'team-members-that-needs-to-be-enriched.json':\n{format_json_for_use_in_query(team_member_list)}\n\nFile 'related-resources.md':\n{related_resources_markdown}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "enrich_team_environment", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            enrich_team_members_with_background_story = EnrichTeamMembersWithEnvironmentInfo.execute(llm, query, team_member_list)
            duration_seconds = time.time() - start_time
            raw_dict = enrich_team_members_with_background_story.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(raw_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.ENRICH_TEAM_MEMBERS_ENVIRONMENT_INFO_RAW.value, "stage": "enrich_team_environment", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            team_member_list = enrich_team_members_with_background_story.team_member_list
            clean_content = json.dumps(team_member_list, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.ENRICH_TEAM_MEMBERS_ENVIRONMENT_INFO_CLEAN.value, "stage": "enrich_team_environment", "content_type": "json", "content": clean_content, "content_size_bytes": len(clean_content.encode('utf-8'))})
            with self.output()['raw'].open("w") as f:
                json.dump(raw_dict, f, indent=2)
            with self.output()['clean'].open("w") as f:
                json.dump(team_member_list, f, indent=2)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class ReviewTeamTask(PlanTask):
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'preproject': self.clone(PreProjectAssessmentTask),
            'project_plan': self.clone(ProjectPlanTask),
            'enrich_team_members_with_environment_info': self.clone(EnrichTeamMembersWithEnvironmentInfoTask),
            'related_resources': self.clone(RelatedResourcesTask)
        }

    def output(self):
        return self.local_target(FilenameEnum.REVIEW_TEAM_RAW)

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                consolidate_assumptions_markdown = f.read()
            with self.input()['preproject']['clean'].open("r") as f:
                pre_project_assessment_dict = json.load(f)
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['enrich_team_members_with_environment_info']['clean'].open("r") as f:
                team_member_list = json.load(f)
            with self.input()['related_resources']['markdown'].open("r") as f:
                related_resources_markdown = f.read()
            builder = TeamMarkdownDocumentBuilder()
            builder.append_roles(team_member_list, title=None)
            team_document_markdown = builder.to_string()
            query = (f"File 'initial-plan.txt':\n{plan_prompt}\n\nFile 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'assumptions.md':\n{consolidate_assumptions_markdown}\n\nFile 'pre-project-assessment.json':\n{format_json_for_use_in_query(pre_project_assessment_dict)}\n\nFile 'project-plan.md':\n{project_plan_markdown}\n\nFile 'team-members.md':\n{team_document_markdown}\n\nFile 'related-resources.md':\n{related_resources_markdown}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "review_team", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            review_team = ReviewTeam.execute(llm, query)
            duration_seconds = time.time() - start_time
            raw_dict = review_team.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(raw_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.REVIEW_TEAM_RAW.value, "stage": "review_team", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            with self.output().open("w") as f:
                json.dump(raw_dict, f, indent=2)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class TeamMarkdownTask(PlanTask):
    def requires(self):
        return {
            'enrich_team_members_with_environment_info': self.clone(EnrichTeamMembersWithEnvironmentInfoTask),
            'review_team': self.clone(ReviewTeamTask)
        }

    def output(self):
        return self.local_target(FilenameEnum.TEAM_MARKDOWN)

    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['enrich_team_members_with_environment_info']['clean'].open("r") as f:
                team_member_list = json.load(f)
            with self.input()['review_team'].open("r") as f:
                review_team_json = json.load(f)
            builder = TeamMarkdownDocumentBuilder()
            builder.append_roles(team_member_list)
            builder.append_separator()
            builder.append_full_review(review_team_json)
            markdown_content = builder.to_string()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.TEAM_MARKDOWN.value, "stage": "team_markdown", "content_type": "markdown", "content": markdown_content, "content_size_bytes": len(markdown_content.encode('utf-8'))})
            builder.write_to_file(self.output().path)
        except Exception as e:
            raise
        finally:
            if db_service:
                db_service.close()

class SWOTAnalysisTask(PlanTask):
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'preproject': self.clone(PreProjectAssessmentTask),
            'project_plan': self.clone(ProjectPlanTask),
            'related_resources': self.clone(RelatedResourcesTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.SWOT_RAW),
            'markdown': self.local_target(FilenameEnum.SWOT_MARKDOWN)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['identify_purpose']['raw'].open("r") as f:
                identify_purpose_dict = json.load(f)
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                consolidate_assumptions_markdown = f.read()
            with self.input()['preproject']['clean'].open("r") as f:
                pre_project_assessment_dict = json.load(f)
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['related_resources']['markdown'].open("r") as f:
                related_resources_markdown = f.read()
            query = (f"File 'initial-plan.txt':\n{plan_prompt}\n\nFile 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'assumptions.md':\n{consolidate_assumptions_markdown}\n\nFile 'pre-project-assessment.json':\n{format_json_for_use_in_query(pre_project_assessment_dict)}\n\nFile 'project-plan.md':\n{project_plan_markdown}\n\nFile 'related-resources.md':\n{related_resources_markdown}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "swot_analysis", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            swot_analysis = SWOTAnalysis.execute(llm=llm, query=query, identify_purpose_dict=identify_purpose_dict)
            duration_seconds = time.time() - start_time
            swot_raw_dict = swot_analysis.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(swot_raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(swot_raw_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.SWOT_RAW.value, "stage": "swot_analysis", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            swot_markdown = swot_analysis.to_markdown(include_metadata=False, include_purpose=False)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.SWOT_MARKDOWN.value, "stage": "swot_analysis", "content_type": "markdown", "content": swot_markdown, "content_size_bytes": len(swot_markdown.encode('utf-8'))})
            with self.output()['raw'].open("w") as f:
                json.dump(swot_raw_dict, f, indent=2)
            with open(self.output()['markdown'].path, "w", encoding="utf-8") as f:
                f.write(swot_markdown)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class ExpertReviewTask(PlanTask):
    """
    Finds experts to review the SWOT analysis and have them provide criticism.
    """
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'preproject': self.clone(PreProjectAssessmentTask),
            'project_plan': self.clone(ProjectPlanTask),
            'swot_analysis': self.clone(SWOTAnalysisTask)
        }

    def output(self):
        return self.local_target(FilenameEnum.EXPERT_CRITICISM_MARKDOWN)

    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            llm_executor: LLMExecutor = self.create_llm_executor()
            with self.input()['setup'].open("r") as f:
                plan_prompt = f.read()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['preproject']['clean'].open("r") as f:
                pre_project_assessment_dict = json.load(f)
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with open(self.input()['swot_analysis']['markdown'].path, "r", encoding="utf-8") as f:
                swot_markdown = f.read()
            query = (f"File 'initial-plan.txt':\n{plan_prompt}\n\nFile 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'pre-project assessment.json':\n{format_json_for_use_in_query(pre_project_assessment_dict)}\n\nFile 'project_plan.md':\n{project_plan_markdown}\n\nFile 'SWOT Analysis.md':\n{swot_markdown}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "expert_review", "prompt_text": query[:10000], "status": "pending"}).id
            def phase1_post_callback(expert_finder: ExpertFinder) -> None:
                raw_path = self.run_id_dir / FilenameEnum.EXPERTS_RAW.value
                cleaned_path = self.run_id_dir / FilenameEnum.EXPERTS_CLEAN.value
                expert_finder.save_raw(str(raw_path))
                expert_finder.save_cleanedup(str(cleaned_path))
            def phase2_post_callback(expert_criticism: ExpertCriticism, expert_index: int) -> None:
                file_path = self.run_id_dir / FilenameEnum.EXPERT_CRITICISM_RAW_TEMPLATE.format(expert_index + 1)
                expert_criticism.save_raw(str(file_path))
            start_time = time.time()
            expert_orchestrator = ExpertOrchestrator()
            expert_orchestrator.phase1_post_callback = phase1_post_callback
            expert_orchestrator.phase2_post_callback = phase2_post_callback
            expert_orchestrator.execute(llm_executor, query)
            duration_seconds = time.time() - start_time
            expert_markdown = expert_orchestrator.to_markdown()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": expert_markdown[:10000], "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.EXPERT_CRITICISM_MARKDOWN.value, "stage": "expert_review", "content_type": "markdown", "content": expert_markdown, "content_size_bytes": len(expert_markdown.encode('utf-8'))})
            with self.file_path(FilenameEnum.EXPERT_CRITICISM_MARKDOWN).open("w") as f:
                f.write(expert_markdown)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()


class DataCollectionTask(PlanTask):
    """
    Determine what kind of data is to be collected.
    """
    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.DATA_COLLECTION_RAW),
            'markdown': self.local_target(FilenameEnum.DATA_COLLECTION_MARKDOWN)
        }
    
    def requires(self):
        return {
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'related_resources': self.clone(RelatedResourcesTask),
            'swot_analysis': self.clone(SWOTAnalysisTask),
            'team_markdown': self.clone(TeamMarkdownTask),
            'expert_review': self.clone(ExpertReviewTask)
        }
    
    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                assumptions_markdown = f.read()
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['related_resources']['markdown'].open("r") as f:
                related_resources_markdown = f.read()
            with self.input()['swot_analysis']['markdown'].open("r") as f:
                swot_analysis_markdown = f.read()
            with self.input()['team_markdown'].open("r") as f:
                team_markdown = f.read()
            with self.input()['expert_review'].open("r") as f:
                expert_review = f.read()
            query = (f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'assumptions.md':\n{assumptions_markdown}\n\nFile 'project-plan.md':\n{project_plan_markdown}\n\nFile 'related-resources.md':\n{related_resources_markdown}\n\nFile 'swot-analysis.md':\n{swot_analysis_markdown}\n\nFile 'team.md':\n{team_markdown}\n\nFile 'expert-review.md':\n{expert_review}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "data_collection", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            data_collection = DataCollection.execute(llm, query)
            duration_seconds = time.time() - start_time
            raw_dict = data_collection.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(raw_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.DATA_COLLECTION_RAW.value, "stage": "data_collection", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            markdown_content = data_collection.to_markdown()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.DATA_COLLECTION_MARKDOWN.value, "stage": "data_collection", "content_type": "markdown", "content": markdown_content, "content_size_bytes": len(markdown_content.encode('utf-8'))})
            data_collection.save_raw(self.output()['raw'].path)
            data_collection.save_markdown(self.output()['markdown'].path)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class IdentifyDocumentsTask(PlanTask):
    """
    Identify documents that need to be created or found for the project.
    """
    def output(self):
        return {
            "raw": self.local_target(FilenameEnum.IDENTIFIED_DOCUMENTS_RAW),
            "markdown": self.local_target(FilenameEnum.IDENTIFIED_DOCUMENTS_MARKDOWN),
            "documents_to_find": self.local_target(FilenameEnum.IDENTIFIED_DOCUMENTS_TO_FIND_JSON),
            "documents_to_create": self.local_target(FilenameEnum.IDENTIFIED_DOCUMENTS_TO_CREATE_JSON),
        }

    def requires(self):
        return {
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'related_resources': self.clone(RelatedResourcesTask),
            'swot_analysis': self.clone(SWOTAnalysisTask),
            'team_markdown': self.clone(TeamMarkdownTask),
            'expert_review': self.clone(ExpertReviewTask)
        }
    
    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['identify_purpose']['raw'].open("r") as f:
                identify_purpose_dict = json.load(f)
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                assumptions_markdown = f.read()
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['related_resources']['markdown'].open("r") as f:
                related_resources_markdown = f.read()
            with self.input()['swot_analysis']['markdown'].open("r") as f:
                swot_analysis_markdown = f.read()
            with self.input()['team_markdown'].open("r") as f:
                team_markdown = f.read()
            with self.input()['expert_review'].open("r") as f:
                expert_review = f.read()
            query = (f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'assumptions.md':\n{assumptions_markdown}\n\nFile 'project-plan.md':\n{project_plan_markdown}\n\nFile 'related-resources.md':\n{related_resources_markdown}\n\nFile 'swot-analysis.md':\n{swot_analysis_markdown}\n\nFile 'team.md':\n{team_markdown}\n\nFile 'expert-review.md':\n{expert_review}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "identify_documents", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            identify_documents = IdentifyDocuments.execute(llm=llm, user_prompt=query, identify_purpose_dict=identify_purpose_dict)
            duration_seconds = time.time() - start_time
            raw_dict = identify_documents.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(raw_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.IDENTIFIED_DOCUMENTS_RAW.value, "stage": "identify_documents", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            markdown_content = identify_documents.to_markdown()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.IDENTIFIED_DOCUMENTS_MARKDOWN.value, "stage": "identify_documents", "content_type": "markdown", "content": markdown_content, "content_size_bytes": len(markdown_content.encode('utf-8'))})
            docs_to_find = identify_documents.to_json_documents_to_find()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.IDENTIFIED_DOCUMENTS_TO_FIND_JSON.value, "stage": "identify_documents", "content_type": "json", "content": docs_to_find, "content_size_bytes": len(docs_to_find.encode('utf-8'))})
            docs_to_create = identify_documents.to_json_documents_to_create()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.IDENTIFIED_DOCUMENTS_TO_CREATE_JSON.value, "stage": "identify_documents", "content_type": "json", "content": docs_to_create, "content_size_bytes": len(docs_to_create.encode('utf-8'))})
            identify_documents.save_raw(self.output()["raw"].path)
            identify_documents.save_markdown(self.output()["markdown"].path)
            identify_documents.save_json_documents_to_find(self.output()["documents_to_find"].path)
            identify_documents.save_json_documents_to_create(self.output()["documents_to_create"].path)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class FilterDocumentsToFindTask(PlanTask):
    """
    The "documents to find" may be a long list of documents, some duplicates, irrelevant, not needed at an early stage of the project.
    This task narrows down to a handful of relevant documents.
    """
    def output(self):
        return {
            "raw": self.local_target(FilenameEnum.FILTER_DOCUMENTS_TO_FIND_RAW),
            "clean": self.local_target(FilenameEnum.FILTER_DOCUMENTS_TO_FIND_CLEAN)
        }

    def requires(self):
        return {
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'identified_documents': self.clone(IdentifyDocumentsTask),
        }
    
    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['identify_purpose']['raw'].open("r") as f:
                identify_purpose_dict = json.load(f)
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                assumptions_markdown = f.read()
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['identified_documents']['documents_to_find'].open("r") as f:
                documents_to_find = json.load(f)
            process_documents, integer_id_to_document_uuid = FilterDocumentsToFind.process_documents_and_integer_ids(documents_to_find)
            query = (f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'assumptions.md':\n{assumptions_markdown}\n\nFile 'project-plan.md':\n{project_plan_markdown}\n\nFile 'documents.json':\n{process_documents}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "filter_docs_to_find", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            filter_documents = FilterDocumentsToFind.execute(llm=llm, user_prompt=query, identified_documents_raw_json=documents_to_find, integer_id_to_document_uuid=integer_id_to_document_uuid, identify_purpose_dict=identify_purpose_dict)
            duration_seconds = time.time() - start_time
            raw_dict = filter_documents.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(raw_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.FILTER_DOCUMENTS_TO_FIND_RAW.value, "stage": "filter_docs_to_find", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            clean_content = filter_documents.to_filtered_documents_json()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.FILTER_DOCUMENTS_TO_FIND_CLEAN.value, "stage": "filter_docs_to_find", "content_type": "json", "content": clean_content, "content_size_bytes": len(clean_content.encode('utf-8'))})
            filter_documents.save_raw(self.output()["raw"].path)
            filter_documents.save_filtered_documents(self.output()["clean"].path)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class FilterDocumentsToCreateTask(PlanTask):
    """
    The "documents to create" may be a long list of documents, some duplicates, irrelevant, not needed at an early stage of the project.
    This task narrows down to a handful of relevant documents.
    """
    def output(self):
        return {
            "raw": self.local_target(FilenameEnum.FILTER_DOCUMENTS_TO_CREATE_RAW),
            "clean": self.local_target(FilenameEnum.FILTER_DOCUMENTS_TO_CREATE_CLEAN)
        }

    def requires(self):
        return {
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'identified_documents': self.clone(IdentifyDocumentsTask),
        }
    
    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['identify_purpose']['raw'].open("r") as f:
                identify_purpose_dict = json.load(f)
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                assumptions_markdown = f.read()
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['identified_documents']['documents_to_create'].open("r") as f:
                documents_to_create = json.load(f)
            process_documents, integer_id_to_document_uuid = FilterDocumentsToCreate.process_documents_and_integer_ids(documents_to_create)
            query = (f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'assumptions.md':\n{assumptions_markdown}\n\nFile 'project-plan.md':\n{project_plan_markdown}\n\nFile 'documents.json':\n{process_documents}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "filter_docs_to_create", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            filter_documents = FilterDocumentsToCreate.execute(llm=llm, user_prompt=query, identified_documents_raw_json=documents_to_create, integer_id_to_document_uuid=integer_id_to_document_uuid, identify_purpose_dict=identify_purpose_dict)
            duration_seconds = time.time() - start_time
            raw_dict = filter_documents.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(raw_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.FILTER_DOCUMENTS_TO_CREATE_RAW.value, "stage": "filter_docs_to_create", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            clean_content = filter_documents.to_filtered_documents_json()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.FILTER_DOCUMENTS_TO_CREATE_CLEAN.value, "stage": "filter_docs_to_create", "content_type": "json", "content": clean_content, "content_size_bytes": len(clean_content.encode('utf-8'))})
            filter_documents.save_raw(self.output()["raw"].path)
            filter_documents.save_filtered_documents(self.output()["clean"].path)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class DraftDocumentsToFindTask(PlanTask):
    """
    The "documents to find". Write bullet points to what each document roughly should contain.
    """
    def output(self):
        return self.local_target(FilenameEnum.DRAFT_DOCUMENTS_TO_FIND_CONSOLIDATED)

    def requires(self):
        return {
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'filter_documents_to_find': self.clone(FilterDocumentsToFindTask),
        }
    
    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            llm_executor: LLMExecutor = self.create_llm_executor()
            with self.input()['identify_purpose']['raw'].open("r") as f:
                identify_purpose_dict = json.load(f)
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                assumptions_markdown = f.read()
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['filter_documents_to_find']['clean'].open("r") as f:
                documents_to_find = json.load(f)
            accumulated_documents = documents_to_find.copy()
            if self.speedvsdetail == SpeedVsDetailEnum.FAST_BUT_SKIP_DETAILS:
                documents_to_find = documents_to_find[:2]
            for index, document in enumerate(documents_to_find):
                query = (f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'assumptions.md':\n{assumptions_markdown}\n\nFile 'project-plan.md':\n{project_plan_markdown}\n\nFile 'document.json':\n{document}")
                interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": f"draft_docs_find_{index+1}", "prompt_text": query[:10000], "status": "pending"}).id
                def execute_draft_document_to_find(llm: LLM) -> DraftDocumentToFind:
                    return DraftDocumentToFind.execute(llm=llm, user_prompt=query, identify_purpose_dict=identify_purpose_dict)
                start_time = time.time()
                try:
                    draft_document = llm_executor.run(execute_draft_document_to_find)
                    duration_seconds = time.time() - start_time
                    json_response = draft_document.to_dict()
                    db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(json_response), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
                    raw_content = json.dumps(json_response, indent=2)
                    raw_filename = FilenameEnum.DRAFT_DOCUMENTS_TO_FIND_RAW_TEMPLATE.value.format(index+1)
                    db_service.create_plan_content({"plan_id": plan_id, "filename": raw_filename, "stage": f"draft_docs_find_{index+1}", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
                    with open(self.run_id_dir / raw_filename, 'w') as f:
                        json.dump(json_response, f, indent=2)
                    document_updated = document.copy()
                    for key in draft_document.response.keys():
                        document_updated[key] = draft_document.response[key]
                    accumulated_documents[index] = document_updated
                except PipelineStopRequested:
                    raise
                except Exception as e:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                    raise ValueError(f"Document-to-find {index+1} LLM interaction failed.") from e
            consolidated_content = json.dumps(accumulated_documents, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.DRAFT_DOCUMENTS_TO_FIND_CONSOLIDATED.value, "stage": "draft_docs_find_consolidated", "content_type": "json", "content": consolidated_content, "content_size_bytes": len(consolidated_content.encode('utf-8'))})
            with self.output().open("w") as f:
                json.dump(accumulated_documents, f, indent=2)
        except Exception as e:
            raise
        finally:
            if db_service:
                db_service.close()

class DraftDocumentsToCreateTask(PlanTask):
    """
    The "documents to create". Write bullet points to what each document roughly should contain.
    """
    def output(self):
        return self.local_target(FilenameEnum.DRAFT_DOCUMENTS_TO_CREATE_CONSOLIDATED)

    def requires(self):
        return {
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'filter_documents_to_create': self.clone(FilterDocumentsToCreateTask),
        }
    
    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            llm_executor: LLMExecutor = self.create_llm_executor()
            with self.input()['identify_purpose']['raw'].open("r") as f:
                identify_purpose_dict = json.load(f)
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                assumptions_markdown = f.read()
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['filter_documents_to_create']['clean'].open("r") as f:
                documents_to_create = json.load(f)
            accumulated_documents = documents_to_create.copy()
            if self.speedvsdetail == SpeedVsDetailEnum.FAST_BUT_SKIP_DETAILS:
                documents_to_create = documents_to_create[:2]
            for index, document in enumerate(documents_to_create):
                query = (f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'assumptions.md':\n{assumptions_markdown}\n\nFile 'project-plan.md':\n{project_plan_markdown}\n\nFile 'document.json':\n{document}")
                interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": f"draft_docs_create_{index+1}", "prompt_text": query[:10000], "status": "pending"}).id
                def execute_draft_document_to_create(llm: LLM) -> DraftDocumentToCreate:
                    return DraftDocumentToCreate.execute(llm=llm, user_prompt=query, identify_purpose_dict=identify_purpose_dict)
                start_time = time.time()
                try:
                    draft_document = llm_executor.run(execute_draft_document_to_create)
                    duration_seconds = time.time() - start_time
                    json_response = draft_document.to_dict()
                    db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(json_response), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
                    raw_content = json.dumps(json_response, indent=2)
                    raw_filename = FilenameEnum.DRAFT_DOCUMENTS_TO_CREATE_RAW_TEMPLATE.value.format(index+1)
                    db_service.create_plan_content({"plan_id": plan_id, "filename": raw_filename, "stage": f"draft_docs_create_{index+1}", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
                    with open(self.run_id_dir / raw_filename, 'w') as f:
                        json.dump(json_response, f, indent=2)
                    document_updated = document.copy()
                    for key in draft_document.response.keys():
                        document_updated[key] = draft_document.response[key]
                    accumulated_documents[index] = document_updated
                except PipelineStopRequested:
                    raise
                except Exception as e:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                    raise ValueError(f"Document-to-create {index+1} LLM interaction failed.") from e
            consolidated_content = json.dumps(accumulated_documents, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.DRAFT_DOCUMENTS_TO_CREATE_CONSOLIDATED.value, "stage": "draft_docs_create_consolidated", "content_type": "json", "content": consolidated_content, "content_size_bytes": len(consolidated_content.encode('utf-8'))})
            with self.output().open("w") as f:
                json.dump(accumulated_documents, f, indent=2)
        except Exception as e:
            raise
        finally:
            if db_service:
                db_service.close()

class MarkdownWithDocumentsToCreateAndFindTask(PlanTask):
    """
    Create markdown with the "documents to create and find"
    """
    def output(self):
        return self.local_target(FilenameEnum.DOCUMENTS_TO_CREATE_AND_FIND_MARKDOWN)

    def requires(self):
        return {
            'draft_documents_to_create': self.clone(DraftDocumentsToCreateTask),
            'draft_documents_to_find': self.clone(DraftDocumentsToFindTask),
        }
    
    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['draft_documents_to_create'].open("r") as f:
                documents_to_create = json.load(f)
            with self.input()['draft_documents_to_find'].open("r") as f:
                documents_to_find = json.load(f)
            accumulated_rows = []
            accumulated_rows.append("# Documents to Create")
            for index, document in enumerate(documents_to_create, start=1):
                rows = markdown_rows_with_document_to_create(index, document)
                accumulated_rows.extend(rows)
            accumulated_rows.append("\n\n# Documents to Find")
            for index, document in enumerate(documents_to_find, start=1):
                rows = markdown_rows_with_document_to_find(index, document)
                accumulated_rows.extend(rows)
            markdown_representation = "\n".join(accumulated_rows)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.DOCUMENTS_TO_CREATE_AND_FIND_MARKDOWN.value, "stage": "documents_markdown", "content_type": "markdown", "content": markdown_representation, "content_size_bytes": len(markdown_representation.encode('utf-8'))})
            with open(self.output().path, 'w', encoding='utf-8') as f:
                f.write(markdown_representation)
        except Exception as e:
            raise
        finally:
            if db_service:
                db_service.close()

class CreateWBSLevel1Task(PlanTask):
    """
    Creates the Work Breakdown Structure (WBS) Level 1.
    Depends on:
      - ProjectPlanTask: provides the project plan as JSON.
    Produces:
      - Raw WBS Level 1 output file (xxx-wbs_level1_raw.json)
      - Cleaned up WBS Level 1 file (xxx-wbs_level1.json)
    """
    def requires(self):
        return {
            'project_plan': self.clone(ProjectPlanTask)
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.WBS_LEVEL1_RAW),
            'clean': self.local_target(FilenameEnum.WBS_LEVEL1),
            'project_title': self.local_target(FilenameEnum.WBS_LEVEL1_PROJECT_TITLE)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['project_plan']['raw'].open("r") as f:
                project_plan_dict = json.load(f)
            query = format_json_for_use_in_query(project_plan_dict)
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "wbs_level1", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            create_wbs_level1 = CreateWBSLevel1.execute(llm, query)
            duration_seconds = time.time() - start_time
            wbs_level1_raw_dict = create_wbs_level1.raw_response_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(wbs_level1_raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(wbs_level1_raw_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.WBS_LEVEL1_RAW.value, "stage": "wbs_level1", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            wbs_level1_result_json = create_wbs_level1.cleanedup_dict()
            clean_content = json.dumps(wbs_level1_result_json, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.WBS_LEVEL1.value, "stage": "wbs_level1", "content_type": "json", "content": clean_content, "content_size_bytes": len(clean_content.encode('utf-8'))})
            project_title = create_wbs_level1.project_title
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.WBS_LEVEL1_PROJECT_TITLE.value, "stage": "wbs_level1", "content_type": "txt", "content": project_title, "content_size_bytes": len(project_title.encode('utf-8'))})
            with self.output()['raw'].open("w") as f:
                json.dump(wbs_level1_raw_dict, f, indent=2)
            with self.output()['clean'].open("w") as f:
                json.dump(wbs_level1_result_json, f, indent=2)
            with self.output()['project_title'].open("w") as f:
                f.write(project_title)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class CreateWBSLevel2Task(PlanTask):
    """
    Creates the Work Breakdown Structure (WBS) Level 2.
    Depends on:
      - ProjectPlanTask: provides the project plan as JSON.
      - CreateWBSLevel1Task: provides the cleaned WBS Level 1 result.
    Produces:
      - Raw WBS Level 2 output (007-wbs_level2_raw.json)
      - Cleaned WBS Level 2 output (008-wbs_level2.json)
    """
    def requires(self):
        return {
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'wbs_level1': self.clone(CreateWBSLevel1Task),
            'data_collection': self.clone(DataCollectionTask),
        }

    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.WBS_LEVEL2_RAW),
            'clean': self.local_target(FilenameEnum.WBS_LEVEL2)
        }

    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['data_collection']['markdown'].open("r") as f:
                data_collection_markdown = f.read()
            with self.input()['wbs_level1']['clean'].open("r") as f:
                wbs_level1_result_json = json.load(f)
            query = (f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'project_plan.md':\n{project_plan_markdown}\n\nFile 'WBS Level 1.json':\n{format_json_for_use_in_query(wbs_level1_result_json)}\n\nFile 'data_collection.md':\n{data_collection_markdown}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "wbs_level2", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            create_wbs_level2 = CreateWBSLevel2.execute(llm, query)
            duration_seconds = time.time() - start_time
            wbs_level2_raw_dict = create_wbs_level2.raw_response_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(wbs_level2_raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(wbs_level2_raw_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.WBS_LEVEL2_RAW.value, "stage": "wbs_level2", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            clean_content = json.dumps(create_wbs_level2.major_phases_with_subtasks, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.WBS_LEVEL2.value, "stage": "wbs_level2", "content_type": "json", "content": clean_content, "content_size_bytes": len(clean_content.encode('utf-8'))})
            with self.output()['raw'].open("w") as f:
                json.dump(wbs_level2_raw_dict, f, indent=2)
            with self.output()['clean'].open("w") as f:
                json.dump(create_wbs_level2.major_phases_with_subtasks, f, indent=2)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class WBSProjectLevel1AndLevel2Task(PlanTask):
    """
    Create a WBS project from the WBS Level 1 and Level 2 JSON files.
    
    It depends on:
      - CreateWBSLevel1Task: providing the cleaned WBS Level 1 JSON.
      - CreateWBSLevel2Task: providing the major phases with subtasks and the task UUIDs.
    """
    def output(self):
        return self.local_target(FilenameEnum.WBS_PROJECT_LEVEL1_AND_LEVEL2)
    
    def requires(self):
        return {
            'wbs_level1': self.clone(CreateWBSLevel1Task),
            'wbs_level2': self.clone(CreateWBSLevel2Task),
        }
    
    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            wbs_level1_path = self.input()['wbs_level1']['clean'].path
            wbs_level2_path = self.input()['wbs_level2']['clean'].path
            wbs_project = WBSPopulate.project_from_level1_json(wbs_level1_path)
            WBSPopulate.extend_project_with_level2_json(wbs_project, wbs_level2_path)
            json_representation = json.dumps(wbs_project.to_dict(), indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.WBS_PROJECT_LEVEL1_AND_LEVEL2.value, "stage": "wbs_project", "content_type": "json", "content": json_representation, "content_size_bytes": len(json_representation.encode('utf-8'))})
            with self.output().open("w") as f:
                f.write(json_representation)
        except Exception as e:
            raise
        finally:
            if db_service:
                db_service.close()

class CreatePitchTask(PlanTask):
    """
    Create a the pitch that explains the project plan, from multiple perspectives.
    
    This task depends on:
      - ProjectPlanTask: provides the project plan JSON.
      - WBSProjectLevel1AndLevel2Task: containing the top level of the project plan.
    
    The resulting pitch JSON is written to the file specified by FilenameEnum.PITCH.
    """
    def output(self):
        return self.local_target(FilenameEnum.PITCH_RAW)
    
    def requires(self):
        return {
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'wbs_project': self.clone(WBSProjectLevel1AndLevel2Task),
            'related_resources': self.clone(RelatedResourcesTask)
        }
    
    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['wbs_project'].open("r") as f:
                wbs_project_dict = json.load(f)
            wbs_project = WBSProject.from_dict(wbs_project_dict)
            wbs_project_json = wbs_project.to_dict()
            with self.input()['related_resources']['markdown'].open("r") as f:
                related_resources_markdown = f.read()
            query = (f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'project_plan.md':\n{project_plan_markdown}\n\nFile 'Work Breakdown Structure.json':\n{format_json_for_use_in_query(wbs_project_json)}\n\nFile 'similar_projects.md':\n{related_resources_markdown}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "create_pitch", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            create_pitch = CreatePitch.execute(llm, query)
            duration_seconds = time.time() - start_time
            pitch_dict = create_pitch.raw_response_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(pitch_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            pitch_content = json.dumps(pitch_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.PITCH_RAW.value, "stage": "create_pitch", "content_type": "json", "content": pitch_content, "content_size_bytes": len(pitch_content.encode('utf-8'))})
            with self.output().open("w") as f:
                json.dump(pitch_dict, f, indent=2)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class ConvertPitchToMarkdownTask(PlanTask):
    """
    Human readable version of the pitch.
    
    This task depends on:
      - CreatePitchTask: Creates the pitch JSON.
    """
    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.PITCH_CONVERT_TO_MARKDOWN_RAW),
            'markdown': self.local_target(FilenameEnum.PITCH_MARKDOWN)
        }
    
    def requires(self):
        return {
            'pitch': self.clone(CreatePitchTask),
        }
    
    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['pitch'].open("r") as f:
                pitch_json = json.load(f)
            query = format_json_for_use_in_query(pitch_json)
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "convert_pitch_markdown", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            converted = ConvertPitchToMarkdown.execute(llm, query)
            duration_seconds = time.time() - start_time
            raw_dict = converted.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            raw_content = json.dumps(raw_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.PITCH_CONVERT_TO_MARKDOWN_RAW.value, "stage": "convert_pitch_markdown", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            markdown_content = converted.to_markdown()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.PITCH_MARKDOWN.value, "stage": "convert_pitch_markdown", "content_type": "markdown", "content": markdown_content, "content_size_bytes": len(markdown_content.encode('utf-8'))})
            converted.save_raw(self.output()['raw'].path)
            converted.save_markdown(self.output()['markdown'].path)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()


class IdentifyTaskDependenciesTask(PlanTask):
    """
    This task identifies the dependencies between WBS tasks.
    """
    def output(self):
        return self.local_target(FilenameEnum.TASK_DEPENDENCIES_RAW)
    
    def requires(self):
        return {
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'wbs_level2': self.clone(CreateWBSLevel2Task),
            'data_collection': self.clone(DataCollectionTask),
        }
    
    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['data_collection']['markdown'].open("r") as f:
                data_collection_markdown = f.read()
            with self.input()['wbs_level2']['clean'].open("r") as f:
                major_phases_with_subtasks = json.load(f)
            query = (f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\nFile 'scenarios.md':\n{scenarios_markdown}\n\nFile 'project_plan.md':\n{project_plan_markdown}\n\nFile 'Work Breakdown Structure.json':\n{format_json_for_use_in_query(major_phases_with_subtasks)}\n\nFile 'data_collection.md':\n{data_collection_markdown}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "task_dependencies", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            identify_dependencies = IdentifyWBSTaskDependencies.execute(llm, query)
            duration_seconds = time.time() - start_time
            dependencies_raw_dict = identify_dependencies.raw_response_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(dependencies_raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            dependencies_content = json.dumps(dependencies_raw_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.TASK_DEPENDENCIES_RAW.value, "stage": "task_dependencies", "content_type": "json", "content": dependencies_content, "content_size_bytes": len(dependencies_content.encode('utf-8'))})
            with self.output().open("w") as f:
                json.dump(dependencies_raw_dict, f, indent=2)
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class EstimateTaskDurationsTask(PlanTask):
    """
    This task estimates durations for WBS tasks in chunks.
    
    It depends on:
      - ProjectPlanTask: providing the project plan JSON.
      - WBSProjectLevel1AndLevel2Task: providing the major phases with subtasks and the task UUIDs.
    
    For each chunk of 3 task IDs, a raw JSON file (e.g. "011-1-task_durations_raw.json") is written,
    and an aggregated JSON file (defined by FilenameEnum.TASK_DURATIONS) is produced.

    IDEA: 1st estimate the Tasks that have zero children.
    2nd estimate tasks that have children where all children have been estimated.
    repeat until all tasks have been estimated.
    """
    def output(self):
        return self.local_target(FilenameEnum.TASK_DURATIONS)
    
    def requires(self):
        return {
            'project_plan': self.clone(ProjectPlanTask),
            'wbs_project': self.clone(WBSProjectLevel1AndLevel2Task),
        }
    
    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            llm_executor: LLMExecutor = self.create_llm_executor()
            with self.input()['project_plan']['raw'].open("r") as f:
                project_plan_dict = json.load(f)
            with self.input()['wbs_project'].open("r") as f:
                wbs_project_dict = json.load(f)
            wbs_project = WBSProject.from_dict(wbs_project_dict)
            root_task = wbs_project.root_task
            major_phases_with_subtasks = [child.to_dict() for child in root_task.task_children]
            decompose_task_id_list = []
            for task in wbs_project.root_task.task_children:
                decompose_task_id_list.extend(task.task_ids())
            task_ids_chunks = [decompose_task_id_list[i:i + 3] for i in range(0, len(decompose_task_id_list), 3)]
            if self.speedvsdetail == SpeedVsDetailEnum.FAST_BUT_SKIP_DETAILS:
                task_ids_chunks = task_ids_chunks[:2]
            accumulated_task_duration_list = []
            for index, task_ids_chunk in enumerate(task_ids_chunks, start=1):
                query = EstimateWBSTaskDurations.format_query(project_plan_dict, major_phases_with_subtasks, task_ids_chunk)
                interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": f"estimate_durations_{index}", "prompt_text": query[:10000], "status": "pending"}).id
                def execute_estimate_task_durations(llm: LLM) -> EstimateWBSTaskDurations:
                    return EstimateWBSTaskDurations.execute(llm, query)
                start_time = time.time()
                try:
                    estimate_durations = llm_executor.run(execute_estimate_task_durations)
                    duration_seconds = time.time() - start_time
                    durations_raw_dict = estimate_durations.raw_response_dict()
                    db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(durations_raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
                    raw_content = json.dumps(durations_raw_dict, indent=2)
                    filename = FilenameEnum.TASK_DURATIONS_RAW_TEMPLATE.format(index)
                    db_service.create_plan_content({"plan_id": plan_id, "filename": filename, "stage": f"estimate_durations_{index}", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
                    with open(self.run_id_dir / filename, "w") as f:
                        json.dump(durations_raw_dict, f, indent=2)
                    accumulated_task_duration_list.extend(durations_raw_dict.get('task_details', []))
                except PipelineStopRequested:
                    raise
                except Exception as e:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                    raise ValueError(f"Task durations chunk {index} LLM interaction failed.") from e
            aggregated_content = json.dumps(accumulated_task_duration_list, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.TASK_DURATIONS.value, "stage": "estimate_durations_aggregated", "content_type": "json", "content": aggregated_content, "content_size_bytes": len(aggregated_content.encode('utf-8'))})
            with open(self.file_path(FilenameEnum.TASK_DURATIONS), "w") as f:
                json.dump(accumulated_task_duration_list, f, indent=2)
        except Exception as e:
            raise
        finally:
            if db_service:
                db_service.close()
        
        logger.info("Task durations estimated and aggregated results written to %s", aggregated_path)

class CreateWBSLevel3Task(PlanTask):
    """
    This task creates the Work Breakdown Structure (WBS) Level 3, by decomposing tasks from Level 2 into subtasks.
    
    It depends on:
      - ProjectPlanTask: provides the project plan JSON.
      - WBSProjectLevel1AndLevel2Task: provides the major phases with subtasks and the task UUIDs.
      - EstimateTaskDurationsTask: provides the aggregated task durations (task_duration_list).
    
    For each task without any subtasks, a query is built and executed using the LLM. 
    The raw JSON result for each task is written to a file using the template from FilenameEnum. 
    Finally, all individual results are accumulated and written as an aggregated JSON file.
    """
    def output(self):
        return self.local_target(FilenameEnum.WBS_LEVEL3)
    
    def requires(self):
        return {
            'project_plan': self.clone(ProjectPlanTask),
            'wbs_project': self.clone(WBSProjectLevel1AndLevel2Task),
            'task_durations': self.clone(EstimateTaskDurationsTask),
            'data_collection': self.clone(DataCollectionTask),
        }
    
    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            llm_executor: LLMExecutor = self.create_llm_executor()
            logger.info("Creating Work Breakdown Structure (WBS) Level 3...")
            with self.input()['project_plan']['raw'].open("r") as f:
                project_plan_dict = json.load(f)
            with self.input()['wbs_project'].open("r") as f:
                wbs_project_dict = json.load(f)
            wbs_project = WBSProject.from_dict(wbs_project_dict)
            with self.input()['data_collection']['markdown'].open("r") as f:
                data_collection_markdown = f.read()
            task_duration_list_path = self.input()['task_durations'].path
            WBSPopulate.extend_project_with_durations_json(wbs_project, task_duration_list_path)
            tasks_with_no_children = []
            def visit_task(task):
                if len(task.task_children) == 0:
                    tasks_with_no_children.append(task)
                else:
                    for child in task.task_children:
                        visit_task(child)
            visit_task(wbs_project.root_task)
            decompose_task_id_list = []
            for task in tasks_with_no_children:
                decompose_task_id_list.append(task.id)
            logger.info("There are %d tasks to be decomposed.", len(decompose_task_id_list))
            logger.info(f"CreateWBSLevel3Task.speedvsdetail: {self.speedvsdetail}")
            if self.speedvsdetail == SpeedVsDetailEnum.FAST_BUT_SKIP_DETAILS:
                logger.info("FAST_BUT_SKIP_DETAILS mode, truncating to 2 chunks for testing.")
                decompose_task_id_list = decompose_task_id_list[:2]
            else:
                logger.info("Processing all chunks.")
            project_plan_str = format_json_for_use_in_query(project_plan_dict)
            wbs_project_str = format_json_for_use_in_query(wbs_project.to_dict())
            wbs_level3_result_accumulated = []
            total_tasks = len(decompose_task_id_list)
            for index, task_id in enumerate(decompose_task_id_list, start=1):
                logger.info("Decomposing task %d of %d", index, total_tasks)
                query = (f"The project plan:\n{project_plan_str}\n\n" f"Data collection:\n{data_collection_markdown}\n\n" f"Work breakdown structure:\n{wbs_project_str}\n\n" f"Only decompose this task:\n\"{task_id}\"")
                interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": f"wbs_level3_{index}", "prompt_text": query[:10000], "status": "pending"}).id
                def execute_create_wbs_level3(llm: LLM) -> CreateWBSLevel3:
                    return CreateWBSLevel3.execute(llm, query, task_id)
                start_time = time.time()
                try:
                    create_wbs_level3 = llm_executor.run(execute_create_wbs_level3)
                    duration_seconds = time.time() - start_time
                    wbs_level3_raw_dict = create_wbs_level3.raw_response_dict()
                    db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(wbs_level3_raw_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
                    raw_content = json.dumps(wbs_level3_raw_dict, indent=2)
                    raw_filename = FilenameEnum.WBS_LEVEL3_RAW_TEMPLATE.value.format(index)
                    db_service.create_plan_content({"plan_id": plan_id, "filename": raw_filename, "stage": f"wbs_level3_{index}", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
                    raw_chunk_path = self.run_id_dir / raw_filename
                    with open(raw_chunk_path, 'w') as f:
                        json.dump(wbs_level3_raw_dict, f, indent=2)
                    wbs_level3_result_accumulated.extend(create_wbs_level3.tasks)
                except PipelineStopRequested:
                    raise
                except Exception as e:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                    logger.error(f"WBS Level 3 task {index} LLM interaction failed.", exc_info=True)
                    raise ValueError(f"WBS Level 3 task {index} LLM interaction failed.") from e
            aggregated_content = json.dumps(wbs_level3_result_accumulated, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.WBS_LEVEL3.value, "stage": "wbs_level3_aggregated", "content_type": "json", "content": aggregated_content, "content_size_bytes": len(aggregated_content.encode('utf-8'))})
            aggregated_path = self.file_path(FilenameEnum.WBS_LEVEL3)
            with open(aggregated_path, 'w') as f:
                json.dump(wbs_level3_result_accumulated, f, indent=2)
            logger.info("WBS Level 3 created and aggregated results written to %s", aggregated_path)
        except Exception as e:
            raise
        finally:
            if db_service:
                db_service.close()

class WBSProjectLevel1AndLevel2AndLevel3Task(PlanTask):
    """
    Create a WBS project from the WBS Level 1 and Level 2 and Level 3 JSON files.
    
    It depends on:
      - WBSProjectLevel1AndLevel2Task: providing the major phases with subtasks and the task UUIDs.
      - CreateWBSLevel3Task: providing the decomposed tasks.
    """
    def output(self):
        return {
            'full': self.local_target(FilenameEnum.WBS_PROJECT_LEVEL1_AND_LEVEL2_AND_LEVEL3_FULL),
            'csv': self.local_target(FilenameEnum.WBS_PROJECT_LEVEL1_AND_LEVEL2_AND_LEVEL3_CSV)
        }
    
    def requires(self):
        return {
            'wbs_project12': self.clone(WBSProjectLevel1AndLevel2Task),
            'wbs_level3': self.clone(CreateWBSLevel3Task),
        }
    
    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            wbs_project_path = self.input()['wbs_project12'].path
            with open(wbs_project_path, "r") as f:
                wbs_project_dict = json.load(f)
            wbs_project = WBSProject.from_dict(wbs_project_dict)
            wbs_level3_path = self.input()['wbs_level3'].path
            WBSPopulate.extend_project_with_decomposed_tasks_json(wbs_project, wbs_level3_path)
            json_representation = json.dumps(wbs_project.to_dict(), indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.WBS_PROJECT_LEVEL1_AND_LEVEL2_AND_LEVEL3_FULL.value, "stage": "wbs_project_full", "content_type": "json", "content": json_representation, "content_size_bytes": len(json_representation.encode('utf-8'))})
            with self.output()['full'].open("w") as f:
                f.write(json_representation)
            csv_representation = wbs_project.to_csv_string()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.WBS_PROJECT_LEVEL1_AND_LEVEL2_AND_LEVEL3_CSV.value, "stage": "wbs_project_full", "content_type": "csv", "content": csv_representation, "content_size_bytes": len(csv_representation.encode('utf-8'))})
            with self.output()['csv'].open("w") as f:
                f.write(csv_representation)
        except Exception as e:
            raise
        finally:
            if db_service:
                db_service.close()

class CreateScheduleTask(PlanTask):
    def output(self):
        return {
            'mermaid_html': self.local_target(FilenameEnum.SCHEDULE_GANTT_MERMAID_HTML),
            'dhtmlx_html': self.local_target(FilenameEnum.SCHEDULE_GANTT_DHTMLX_HTML),
            'machai_csv': self.local_target(FilenameEnum.SCHEDULE_GANTT_MACHAI_CSV)
        }
    
    def requires(self):
        return {
            'start_time': self.clone(StartTimeTask),
            'wbs_level1': self.clone(CreateWBSLevel1Task),
            'dependencies': self.clone(IdentifyTaskDependenciesTask),
            'durations': self.clone(EstimateTaskDurationsTask),
            'wbs_project123': self.clone(WBSProjectLevel1AndLevel2AndLevel3Task)
        }
    
    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['wbs_level1']['project_title'].open("r") as f:
                title = f.read()
            with self.input()['dependencies'].open("r") as f:
                dependencies_dict = json.load(f)
            with self.input()['durations'].open("r") as f:
                duration_list: list[dict[str, Any]] = json.load(f)
            wbs_project_path = self.input()['wbs_project123']['full'].path
            with open(wbs_project_path, "r") as f:
                wbs_project_dict = json.load(f)
            wbs_project = WBSProject.from_dict(wbs_project_dict)
            with self.input()['start_time'].open("r") as f:
                start_time_dict = json.load(f)
            utc_timestamp = start_time_dict['server_iso_utc']
            project_start_dt: datetime = datetime.fromisoformat(utc_timestamp.replace('Z', '+00:00'))
            project_start: date = project_start_dt.date()
            task_id_to_html_tooltip_dict: dict[str, str] = WBSTaskTooltip.html_tooltips(wbs_project)
            task_id_to_text_tooltip_dict: dict[str, str] = WBSTaskTooltip.text_tooltips(wbs_project)
            project_schedule: ProjectSchedule = ProjectSchedulePopulator.populate(wbs_project=wbs_project, duration_list=duration_list)
            csv_data: str = ExportGanttCSV.to_gantt_csv(project_schedule=project_schedule, project_start=project_start, task_id_to_tooltip_dict=task_id_to_text_tooltip_dict)
            if PIPELINE_CONFIG.enable_csv_export == False:
                csv_data = None
            ExportGanttCSV.save(project_schedule=project_schedule, path=self.output()['machai_csv'].path, project_start=project_start, task_id_to_tooltip_dict=task_id_to_text_tooltip_dict)
            with open(self.output()['machai_csv'].path, "r") as f:
                csv_content = f.read()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.SCHEDULE_GANTT_MACHAI_CSV.value, "stage": "schedule", "content_type": "csv", "content": csv_content, "content_size_bytes": len(csv_content.encode('utf-8'))})
            task_ids_to_treat_as_project_activities = wbs_project.task_ids_with_one_or_more_children()
            ExportGanttMermaid.save(project_schedule=project_schedule, path=self.output()['mermaid_html'].path, project_start=project_start)
            with open(self.output()['mermaid_html'].path, "r") as f:
                mermaid_html = f.read()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.SCHEDULE_GANTT_MERMAID_HTML.value, "stage": "schedule", "content_type": "html", "content": mermaid_html, "content_size_bytes": len(mermaid_html.encode('utf-8'))})
            ExportGanttDHTMLX.save(project_schedule=project_schedule, path=self.output()['dhtmlx_html'].path, project_start=project_start, task_ids_to_treat_as_project_activities=task_ids_to_treat_as_project_activities, task_id_to_tooltip_dict=task_id_to_html_tooltip_dict, title=title, csv_data=csv_data)
            with open(self.output()['dhtmlx_html'].path, "r") as f:
                dhtmlx_html = f.read()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.SCHEDULE_GANTT_DHTMLX_HTML.value, "stage": "schedule", "content_type": "html", "content": dhtmlx_html, "content_size_bytes": len(dhtmlx_html.encode('utf-8'))})
        except Exception as e:
            raise
        finally:
            if db_service:
                db_service.close()

class ReviewPlanTask(PlanTask):
    """
    Ask questions about the almost finished plan.
    """
    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.REVIEW_PLAN_RAW),
            'markdown': self.local_target(FilenameEnum.REVIEW_PLAN_MARKDOWN)
        }
    
    def requires(self):
        return {
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'data_collection': self.clone(DataCollectionTask),
            'related_resources': self.clone(RelatedResourcesTask),
            'swot_analysis': self.clone(SWOTAnalysisTask),
            'team_markdown': self.clone(TeamMarkdownTask),
            'pitch_markdown': self.clone(ConvertPitchToMarkdownTask),
            'expert_review': self.clone(ExpertReviewTask),
            'wbs_project123': self.clone(WBSProjectLevel1AndLevel2AndLevel3Task)
        }
    
    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            llm_executor: LLMExecutor = self.create_llm_executor()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                assumptions_markdown = f.read()
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['data_collection']['markdown'].open("r") as f:
                data_collection_markdown = f.read()
            with self.input()['related_resources']['markdown'].open("r") as f:
                related_resources_markdown = f.read()
            with self.input()['swot_analysis']['markdown'].open("r") as f:
                swot_analysis_markdown = f.read()
            with self.input()['team_markdown'].open("r") as f:
                team_markdown = f.read()
            with self.input()['pitch_markdown']['markdown'].open("r") as f:
                pitch_markdown = f.read()
            with self.input()['expert_review'].open("r") as f:
                expert_review = f.read()
            with self.input()['wbs_project123']['csv'].open("r") as f:
                wbs_project_csv = f.read()
            query = (f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n" f"File 'scenarios.md':\n{scenarios_markdown}\n\n" f"File 'assumptions.md':\n{assumptions_markdown}\n\n" f"File 'project-plan.md':\n{project_plan_markdown}\n\n" f"File 'data-collection.md':\n{data_collection_markdown}\n\n" f"File 'related-resources.md':\n{related_resources_markdown}\n\n" f"File 'swot-analysis.md':\n{swot_analysis_markdown}\n\n" f"File 'team.md':\n{team_markdown}\n\n" f"File 'pitch.md':\n{pitch_markdown}\n\n" f"File 'expert-review.md':\n{expert_review}\n\n" f"File 'work-breakdown-structure.csv':\n{wbs_project_csv}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "review_plan", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            review_plan = ReviewPlan.execute(llm_executor=llm_executor, document=query, speed_vs_detail=self.speedvsdetail)
            duration_seconds = time.time() - start_time
            last_attempt = llm_executor.get_last_attempt()
            response_text = last_attempt.get('response_text', '') if last_attempt else ''
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": response_text[:10000], "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            json_path = self.output()['raw'].path
            review_plan.save_raw(json_path)
            with open(json_path, "r") as f:
                raw_content = f.read()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.REVIEW_PLAN_RAW.value, "stage": "review_plan", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            markdown_path = self.output()['markdown'].path
            review_plan.save_markdown(markdown_path)
            with open(markdown_path, "r") as f:
                markdown_content = f.read()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.REVIEW_PLAN_MARKDOWN.value, "stage": "review_plan", "content_type": "markdown", "content": markdown_content, "content_size_bytes": len(markdown_content.encode('utf-8'))})
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()


class ExecutiveSummaryTask(PlanTask):
    """
    Create an executive summary of the plan.    
    """
    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.EXECUTIVE_SUMMARY_RAW),
            'markdown': self.local_target(FilenameEnum.EXECUTIVE_SUMMARY_MARKDOWN)
        }
    
    def requires(self):
        return {
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'project_plan': self.clone(ProjectPlanTask),
            'data_collection': self.clone(DataCollectionTask),
            'related_resources': self.clone(RelatedResourcesTask),
            'swot_analysis': self.clone(SWOTAnalysisTask),
            'team_markdown': self.clone(TeamMarkdownTask),
            'pitch_markdown': self.clone(ConvertPitchToMarkdownTask),
            'expert_review': self.clone(ExpertReviewTask),
            'wbs_project123': self.clone(WBSProjectLevel1AndLevel2AndLevel3Task),
            'review_plan': self.clone(ReviewPlanTask)
        }
    
    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                assumptions_markdown = f.read()
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['data_collection']['markdown'].open("r") as f:
                data_collection_markdown = f.read()
            with self.input()['related_resources']['markdown'].open("r") as f:
                related_resources_markdown = f.read()
            with self.input()['swot_analysis']['markdown'].open("r") as f:
                swot_analysis_markdown = f.read()
            with self.input()['team_markdown'].open("r") as f:
                team_markdown = f.read()
            with self.input()['pitch_markdown']['markdown'].open("r") as f:
                pitch_markdown = f.read()
            with self.input()['expert_review'].open("r") as f:
                expert_review = f.read()
            with self.input()['wbs_project123']['csv'].open("r") as f:
                wbs_project_csv = f.read()
            with self.input()['review_plan']['markdown'].open("r") as f:
                review_plan_markdown = f.read()
            query = (f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n" f"File 'scenarios.md':\n{scenarios_markdown}\n\n" f"File 'assumptions.md':\n{assumptions_markdown}\n\n" f"File 'project-plan.md':\n{project_plan_markdown}\n\n" f"File 'data-collection.md':\n{data_collection_markdown}\n\n" f"File 'related-resources.md':\n{related_resources_markdown}\n\n" f"File 'swot-analysis.md':\n{swot_analysis_markdown}\n\n" f"File 'team.md':\n{team_markdown}\n\n" f"File 'pitch.md':\n{pitch_markdown}\n\n" f"File 'expert-review.md':\n{expert_review}\n\n" f"File 'work-breakdown-structure.csv':\n{wbs_project_csv}\n\n" f"File 'review-plan.md':\n{review_plan_markdown}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "executive_summary", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            executive_summary = ExecutiveSummary.execute(llm, query)
            duration_seconds = time.time() - start_time
            summary_dict = executive_summary.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(summary_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            json_path = self.output()['raw'].path
            executive_summary.save_raw(json_path)
            raw_content = json.dumps(summary_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.EXECUTIVE_SUMMARY_RAW.value, "stage": "executive_summary", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            markdown_path = self.output()['markdown'].path
            executive_summary.save_markdown(markdown_path)
            with open(markdown_path, "r") as f:
                markdown_content = f.read()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.EXECUTIVE_SUMMARY_MARKDOWN.value, "stage": "executive_summary", "content_type": "markdown", "content": markdown_content, "content_size_bytes": len(markdown_content.encode('utf-8'))})
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()


class QuestionsAndAnswersTask(PlanTask):
    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.QUESTIONS_AND_ANSWERS_RAW),
            'markdown': self.local_target(FilenameEnum.QUESTIONS_AND_ANSWERS_MARKDOWN),
            'html': self.local_target(FilenameEnum.QUESTIONS_AND_ANSWERS_HTML)
        }
    
    def requires(self):
        return {
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'team_markdown': self.clone(TeamMarkdownTask),
            'related_resources': self.clone(RelatedResourcesTask),
            'consolidate_governance': self.clone(ConsolidateGovernanceTask),
            'swot_analysis': self.clone(SWOTAnalysisTask),
            'pitch_markdown': self.clone(ConvertPitchToMarkdownTask),
            'data_collection': self.clone(DataCollectionTask),
            'documents_to_create_and_find': self.clone(MarkdownWithDocumentsToCreateAndFindTask),
            'wbs_project123': self.clone(WBSProjectLevel1AndLevel2AndLevel3Task),
            'expert_review': self.clone(ExpertReviewTask),
            'project_plan': self.clone(ProjectPlanTask),
            'review_plan': self.clone(ReviewPlanTask),
        }
    
    def run_with_llm(self, llm: LLM) -> None:
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                assumptions_markdown = f.read()
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['data_collection']['markdown'].open("r") as f:
                data_collection_markdown = f.read()
            with self.input()['related_resources']['markdown'].open("r") as f:
                related_resources_markdown = f.read()
            with self.input()['swot_analysis']['markdown'].open("r") as f:
                swot_analysis_markdown = f.read()
            with self.input()['team_markdown'].open("r") as f:
                team_markdown = f.read()
            with self.input()['pitch_markdown']['markdown'].open("r") as f:
                pitch_markdown = f.read()
            with self.input()['expert_review'].open("r") as f:
                expert_review = f.read()
            with self.input()['wbs_project123']['csv'].open("r") as f:
                wbs_project_csv = f.read()
            with self.input()['review_plan']['markdown'].open("r") as f:
                review_plan_markdown = f.read()
            query = (f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n" f"File 'scenarios.md':\n{scenarios_markdown}\n\n" f"File 'assumptions.md':\n{assumptions_markdown}\n\n" f"File 'project-plan.md':\n{project_plan_markdown}\n\n" f"File 'data-collection.md':\n{data_collection_markdown}\n\n" f"File 'related-resources.md':\n{related_resources_markdown}\n\n" f"File 'swot-analysis.md':\n{swot_analysis_markdown}\n\n" f"File 'team.md':\n{team_markdown}\n\n" f"File 'pitch.md':\n{pitch_markdown}\n\n" f"File 'expert-review.md':\n{expert_review}\n\n" f"File 'work-breakdown-structure.csv':\n{wbs_project_csv}\n\n" f"File 'review-plan.md':\n{review_plan_markdown}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "questions_answers", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            question_answers = QuestionsAnswers.execute(llm, query)
            duration_seconds = time.time() - start_time
            qa_dict = question_answers.to_dict()
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": json.dumps(qa_dict), "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            json_path = self.output()['raw'].path
            question_answers.save_raw(json_path)
            raw_content = json.dumps(qa_dict, indent=2)
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.QUESTIONS_AND_ANSWERS_RAW.value, "stage": "questions_answers", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            markdown_path = self.output()['markdown'].path
            question_answers.save_markdown(markdown_path)
            with open(markdown_path, "r") as f:
                markdown_content = f.read()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.QUESTIONS_AND_ANSWERS_MARKDOWN.value, "stage": "questions_answers", "content_type": "markdown", "content": markdown_content, "content_size_bytes": len(markdown_content.encode('utf-8'))})
            html_path = self.output()['html'].path
            question_answers.save_html(html_path)
            with open(html_path, "r") as f:
                html_content = f.read()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.QUESTIONS_AND_ANSWERS_HTML.value, "stage": "questions_answers", "content_type": "html", "content": html_content, "content_size_bytes": len(html_content.encode('utf-8'))})
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class PremortemTask(PlanTask):
    def output(self):
        return {
            'raw': self.local_target(FilenameEnum.PREMORTEM_RAW),
            'markdown': self.local_target(FilenameEnum.PREMORTEM_MARKDOWN)
        }
    
    def requires(self):
        return {
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'team_markdown': self.clone(TeamMarkdownTask),
            'related_resources': self.clone(RelatedResourcesTask),
            'consolidate_governance': self.clone(ConsolidateGovernanceTask),
            'swot_analysis': self.clone(SWOTAnalysisTask),
            'pitch_markdown': self.clone(ConvertPitchToMarkdownTask),
            'data_collection': self.clone(DataCollectionTask),
            'documents_to_create_and_find': self.clone(MarkdownWithDocumentsToCreateAndFindTask),
            'wbs_project123': self.clone(WBSProjectLevel1AndLevel2AndLevel3Task),
            'expert_review': self.clone(ExpertReviewTask),
            'project_plan': self.clone(ProjectPlanTask),
            'review_plan': self.clone(ReviewPlanTask),
            'questions_and_answers': self.clone(QuestionsAndAnswersTask)
        }
    
    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            llm_executor: LLMExecutor = self.create_llm_executor()
            with self.input()['strategic_decisions_markdown']['markdown'].open("r") as f:
                strategic_decisions_markdown = f.read()
            with self.input()['scenarios_markdown']['markdown'].open("r") as f:
                scenarios_markdown = f.read()
            with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
                assumptions_markdown = f.read()
            with self.input()['project_plan']['markdown'].open("r") as f:
                project_plan_markdown = f.read()
            with self.input()['data_collection']['markdown'].open("r") as f:
                data_collection_markdown = f.read()
            with self.input()['related_resources']['markdown'].open("r") as f:
                related_resources_markdown = f.read()
            with self.input()['swot_analysis']['markdown'].open("r") as f:
                swot_analysis_markdown = f.read()
            with self.input()['team_markdown'].open("r") as f:
                team_markdown = f.read()
            with self.input()['pitch_markdown']['markdown'].open("r") as f:
                pitch_markdown = f.read()
            with self.input()['expert_review'].open("r") as f:
                expert_review = f.read()
            with self.input()['wbs_project123']['csv'].open("r") as f:
                wbs_project_csv = f.read()
            with self.input()['review_plan']['markdown'].open("r") as f:
                review_plan_markdown = f.read()
            with self.input()['questions_and_answers']['markdown'].open("r") as f:
                questions_and_answers_markdown = f.read()
            query = (f"File 'strategic_decisions.md':\n{strategic_decisions_markdown}\n\n" f"File 'scenarios.md':\n{scenarios_markdown}\n\n" f"File 'assumptions.md':\n{assumptions_markdown}\n\n" f"File 'project-plan.md':\n{project_plan_markdown}\n\n" f"File 'data-collection.md':\n{data_collection_markdown}\n\n" f"File 'related-resources.md':\n{related_resources_markdown}\n\n" f"File 'swot-analysis.md':\n{swot_analysis_markdown}\n\n" f"File 'team.md':\n{team_markdown}\n\n" f"File 'pitch.md':\n{pitch_markdown}\n\n" f"File 'expert-review.md':\n{expert_review}\n\n" f"File 'work-breakdown-structure.csv':\n{wbs_project_csv}\n\n" f"File 'review-plan.md':\n{review_plan_markdown}\n\n" f"File 'questions-and-answers.md':\n{questions_and_answers_markdown}")
            interaction_id = db_service.create_llm_interaction({"plan_id": plan_id, "llm_model": str(self.llm_models[0]) if self.llm_models else "unknown", "stage": "premortem", "prompt_text": query[:10000], "status": "pending"}).id
            start_time = time.time()
            premortem = Premortem.execute(llm_executor=llm_executor, speed_vs_detail=self.speedvsdetail, user_prompt=query)
            duration_seconds = time.time() - start_time
            last_attempt = llm_executor.get_last_attempt()
            response_text = last_attempt.get('response_text', '') if last_attempt else ''
            db_service.update_llm_interaction(interaction_id, {"status": "completed", "response_text": response_text[:10000], "completed_at": datetime.utcnow(), "duration_seconds": duration_seconds})
            json_path = self.output()['raw'].path
            premortem.save_raw(json_path)
            with open(json_path, "r") as f:
                raw_content = f.read()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.PREMORTEM_RAW.value, "stage": "premortem", "content_type": "json", "content": raw_content, "content_size_bytes": len(raw_content.encode('utf-8'))})
            markdown_path = self.output()['markdown'].path
            premortem.save_markdown(markdown_path)
            with open(markdown_path, "r") as f:
                markdown_content = f.read()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.PREMORTEM_MARKDOWN.value, "stage": "premortem", "content_type": "markdown", "content": markdown_content, "content_size_bytes": len(markdown_content.encode('utf-8'))})
        except Exception as e:
            if db_service and 'interaction_id' in locals():
                try:
                    db_service.update_llm_interaction(interaction_id, {"status": "failed", "error_message": str(e), "completed_at": datetime.utcnow()})
                except Exception:
                    pass
            raise
        finally:
            if db_service:
                db_service.close()

class ReportTask(PlanTask):
    """
    Generate a report html document.
    """
    def output(self):
        return self.local_target(FilenameEnum.REPORT)
    
    def requires(self):
        return {
            'setup': self.clone(SetupTask),
            'redline_gate': self.clone(RedlineGateTask),
            'premise_attack': self.clone(PremiseAttackTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'team_markdown': self.clone(TeamMarkdownTask),
            'related_resources': self.clone(RelatedResourcesTask),
            'consolidate_governance': self.clone(ConsolidateGovernanceTask),
            'swot_analysis': self.clone(SWOTAnalysisTask),
            'pitch_markdown': self.clone(ConvertPitchToMarkdownTask),
            'data_collection': self.clone(DataCollectionTask),
            'documents_to_create_and_find': self.clone(MarkdownWithDocumentsToCreateAndFindTask),
            'wbs_level1': self.clone(CreateWBSLevel1Task),
            'wbs_project123': self.clone(WBSProjectLevel1AndLevel2AndLevel3Task),
            'expert_review': self.clone(ExpertReviewTask),
            'project_plan': self.clone(ProjectPlanTask),
            'review_plan': self.clone(ReviewPlanTask),
            'executive_summary': self.clone(ExecutiveSummaryTask),
            'create_schedule': self.clone(CreateScheduleTask),
            'questions_and_answers': self.clone(QuestionsAndAnswersTask),
            'premortem': self.clone(PremortemTask)
        }
    
    def run_inner(self):
        db_service = None
        plan_id = self.get_plan_id()
        try:
            db_service = self.get_database_service()
            with self.input()['wbs_level1']['project_title'].open("r") as f:
                title = f.read()
            rg = ReportGenerator()
            rg.append_markdown('Executive Summary', self.input()['executive_summary']['markdown'].path)
            rg.append_html('Gantt Overview', self.input()['create_schedule']['mermaid_html'].path)
            rg.append_html('Gantt Interactive', self.input()['create_schedule']['dhtmlx_html'].path)
            rg.append_markdown('Pitch', self.input()['pitch_markdown']['markdown'].path)
            rg.append_markdown('Project Plan', self.input()['project_plan']['markdown'].path)
            rg.append_markdown('Strategic Decisions', self.input()['strategic_decisions_markdown']['markdown'].path)
            rg.append_markdown('Scenarios', self.input()['scenarios_markdown']['markdown'].path)
            rg.append_markdown('Assumptions', self.input()['consolidate_assumptions_markdown']['full'].path)
            rg.append_markdown('Governance', self.input()['consolidate_governance'].path)
            rg.append_markdown('Related Resources', self.input()['related_resources']['markdown'].path)
            rg.append_markdown('Data Collection', self.input()['data_collection']['markdown'].path)
            rg.append_markdown('Documents to Create and Find', self.input()['documents_to_create_and_find'].path)
            rg.append_markdown('SWOT Analysis', self.input()['swot_analysis']['markdown'].path)
            rg.append_markdown('Team', self.input()['team_markdown'].path)
            rg.append_markdown('Expert Criticism', self.input()['expert_review'].path)
            rg.append_csv('Work Breakdown Structure', self.input()['wbs_project123']['csv'].path)
            rg.append_markdown('Review Plan', self.input()['review_plan']['markdown'].path)
            rg.append_html('Questions & Answers', self.input()['questions_and_answers']['html'].path)
            rg.append_markdown_with_tables('Premortem', self.input()['premortem']['markdown'].path)
            rg.append_initial_prompt_vetted(document_title='Initial Prompt Vetted', initial_prompt_file_path=self.input()['setup'].path, redline_gate_markdown_file_path=self.input()['redline_gate']['markdown'].path, premise_attack_markdown_file_path=self.input()['premise_attack']['markdown'].path)
            rg.save_report(self.output().path, title=title, execute_plan_section_hidden=REPORT_EXECUTE_PLAN_SECTION_HIDDEN)
            with open(self.output().path, "r") as f:
                report_html = f.read()
            db_service.create_plan_content({"plan_id": plan_id, "filename": FilenameEnum.REPORT.value, "stage": "report", "content_type": "html", "content": report_html, "content_size_bytes": len(report_html.encode('utf-8'))})
        except Exception as e:
            raise
        finally:
            if db_service:
                db_service.close()

class FullPlanPipeline(PlanTask):
    def requires(self):
        return {
            'start_time': self.clone(StartTimeTask),
            'setup': self.clone(SetupTask),
            'redline_gate': self.clone(RedlineGateTask),
            'premise_attack': self.clone(PremiseAttackTask),
            'identify_purpose': self.clone(IdentifyPurposeTask),
            'plan_type': self.clone(PlanTypeTask),
            'potential_levers': self.clone(PotentialLeversTask),
            'deduplicate_levers': self.clone(DeduplicateLeversTask),
            'enriched_levers': self.clone(EnrichLeversTask),
            'focus_on_vital_few_levers': self.clone(FocusOnVitalFewLeversTask),
            'strategic_decisions_markdown': self.clone(StrategicDecisionsMarkdownTask),
            'candidate_scenarios': self.clone(CandidateScenariosTask),
            'select_scenario': self.clone(SelectScenarioTask),
            'scenarios_markdown': self.clone(ScenariosMarkdownTask),
            'physical_locations': self.clone(PhysicalLocationsTask),
            'currency_strategy': self.clone(CurrencyStrategyTask),
            'identify_risks': self.clone(IdentifyRisksTask),
            'make_assumptions': self.clone(MakeAssumptionsTask),
            'assumptions': self.clone(DistillAssumptionsTask),
            'review_assumptions': self.clone(ReviewAssumptionsTask),
            'consolidate_assumptions_markdown': self.clone(ConsolidateAssumptionsMarkdownTask),
            'pre_project_assessment': self.clone(PreProjectAssessmentTask),
            'project_plan': self.clone(ProjectPlanTask),
            'governance_phase1_audit': self.clone(GovernancePhase1AuditTask),
            'governance_phase2_bodies': self.clone(GovernancePhase2BodiesTask),
            'governance_phase3_impl_plan': self.clone(GovernancePhase3ImplPlanTask),
            'governance_phase4_decision_escalation_matrix': self.clone(GovernancePhase4DecisionEscalationMatrixTask),
            'governance_phase5_monitoring_progress': self.clone(GovernancePhase5MonitoringProgressTask),
            'governance_phase6_extra': self.clone(GovernancePhase6ExtraTask),
            'consolidate_governance': self.clone(ConsolidateGovernanceTask),
            'related_resources': self.clone(RelatedResourcesTask),
            'find_team_members': self.clone(FindTeamMembersTask),
            'enrich_team_members_with_contract_type': self.clone(EnrichTeamMembersWithContractTypeTask),
            'enrich_team_members_with_background_story': self.clone(EnrichTeamMembersWithBackgroundStoryTask),
            'enrich_team_members_with_environment_info': self.clone(EnrichTeamMembersWithEnvironmentInfoTask),
            'review_team': self.clone(ReviewTeamTask),
            'team_markdown': self.clone(TeamMarkdownTask),
            'swot_analysis': self.clone(SWOTAnalysisTask),
            'expert_review': self.clone(ExpertReviewTask),
            'data_collection': self.clone(DataCollectionTask),
            'identified_documents': self.clone(IdentifyDocumentsTask),
            'filter_documents_to_find': self.clone(FilterDocumentsToFindTask),
            'filter_documents_to_create': self.clone(FilterDocumentsToCreateTask),
            'draft_documents_to_find': self.clone(DraftDocumentsToFindTask),
            'draft_documents_to_create': self.clone(DraftDocumentsToCreateTask),
            'documents_to_create_and_find': self.clone(MarkdownWithDocumentsToCreateAndFindTask),
            'wbs_level1': self.clone(CreateWBSLevel1Task),
            'wbs_level2': self.clone(CreateWBSLevel2Task),
            'wbs_project12': self.clone(WBSProjectLevel1AndLevel2Task),
            'pitch_raw': self.clone(CreatePitchTask),
            'pitch_markdown': self.clone(ConvertPitchToMarkdownTask),
            'dependencies': self.clone(IdentifyTaskDependenciesTask),
            'durations': self.clone(EstimateTaskDurationsTask),
            'wbs_level3': self.clone(CreateWBSLevel3Task),
            'wbs_project123': self.clone(WBSProjectLevel1AndLevel2AndLevel3Task),
            'plan_evaluator': self.clone(ReviewPlanTask),
            'executive_summary': self.clone(ExecutiveSummaryTask),
            'create_schedule': self.clone(CreateScheduleTask),
            'questions_and_answers': self.clone(QuestionsAndAnswersTask),
            'premortem': self.clone(PremortemTask),
            'report': self.clone(ReportTask),
        }

    def output(self):
        return self.local_target(FilenameEnum.PIPELINE_COMPLETE)

    def run_inner(self):
        with self.output().open("w") as f:
            f.write("Full pipeline executed successfully.\n")


@dataclass
class PipelineProgress:
    progress_message: str
    progress_percentage: float


@dataclass
class HandleTaskCompletionParameters:
    task: PlanTask
    progress: PipelineProgress
    duration: float


@dataclass
class ExecutePipeline:
    run_id_dir: Path
    speedvsdetail: SpeedVsDetailEnum
    llm_models: list[str]
    full_plan_pipeline_task: Optional[FullPlanPipeline] = field(default=None)
    all_expected_filenames: list[str] = field(default_factory=list)
    luigi_build_return_value: Optional[bool] = field(default=None, init=False)

    def setup(self) -> None:
        # Check that the run_id_dir exists and contains the required files.
        if not self.run_id_dir.exists():
            raise FileNotFoundError(f"The run_id_dir does not exist: {self.run_id_dir!r}")
        if not self.run_id_dir.is_dir():
            raise NotADirectoryError(f"The run_id_dir is not a directory: {self.run_id_dir!r}")
        if not (self.run_id_dir / FilenameEnum.START_TIME.value).exists():
            raise FileNotFoundError(f"The '{FilenameEnum.START_TIME.value}' file does not exist in the run_id_dir: {self.run_id_dir!r}")
        if not (self.run_id_dir / FilenameEnum.INITIAL_PLAN.value).exists():
            raise FileNotFoundError(f"The '{FilenameEnum.INITIAL_PLAN.value}' file does not exist in the run_id_dir: {self.run_id_dir!r}")

        full_plan_pipeline_task = FullPlanPipeline(
            run_id_dir=self.run_id_dir, 
            speedvsdetail=self.speedvsdetail, 
            llm_models=self.llm_models, 
            _pipeline_executor_callback=self.callback_run_task
        )
        self.full_plan_pipeline_task = full_plan_pipeline_task

        # Obtain a list of all the expected output files of the FullPlanPipeline task and all its dependencies
        obtain_output_files = ObtainOutputFiles.execute(full_plan_pipeline_task)
        self.all_expected_filenames = obtain_output_files.get_all_filenames()
    
    @classmethod
    def resolve_llm_models(cls, specified_llm_model: Optional[str]) -> list[str]:
        llm_models = get_llm_names_by_priority()
        if len(llm_models) == 0:
            logger.error("No LLM models found. Please check your llm_config.json file and add 'priority' values.")
            llm_models = [DEFAULT_LLM_MODEL]

        if specified_llm_model:
            llm_model = specified_llm_model
            logger.info(f"Using the specified LLM model: {llm_model!r}")
            if llm_model != SPECIAL_AUTO_ID:
                if not is_valid_llm_name(llm_model):
                    logger.error(f"Invalid LLM model: {llm_model!r}. Please check your llm_config.json file and add the model.")
                    raise ValueError(f"Invalid LLM model: {llm_model!r}. Please check your llm_config.json file and add the model.")
                llm_models = [llm_model]

        logger.info("These are the LLM models that will be used in the pipeline:")
        for index, llm_name in enumerate(llm_models):
            logger.info(f"{index}. {llm_name!r}")
        return llm_models
    
    def get_progress_percentage(self) -> PipelineProgress:
        files = []
        try:
            if self.run_id_dir.exists() and self.run_id_dir.is_dir():
                files = [f.name for f in self.run_id_dir.iterdir()]
        except OSError as e:
            logger.warning(f"Could not list files in {run_id_dir}: {e}")

        ignore_files = [
            ExtraFilenameEnum.EXPECTED_FILENAMES1_JSON.value,
            ExtraFilenameEnum.LOG_TXT.value,
            ExtraFilenameEnum.PIPELINE_STOP_REQUESTED_FLAG.value,
            '.DS_Store',
        ]
        files = [f for f in files if f not in ignore_files]
        # logger.debug(f"Files in run_id_dir for {job.run_id}: {files}") # Debug, can be noisy
        # logger.debug(f"Number of files in run_id_dir for {job.run_id}: {len(files)}") # Debug

        # Determine the progress, by comparing the generated files with the expected_filenames1.json
        set_files = set(files)
        set_expected_files = set(self.all_expected_filenames)
        intersection_files = set_files & set_expected_files
        extra_files = set_files - set_expected_files
        # if len(extra_files) > 0:
        #     logger.debug(f"Extra files: {extra_files}")
        progress_message_long = f"{len(intersection_files)} of {len(set_expected_files)}. Extra files: {len(extra_files)}"
        progress_message_short = f"{len(intersection_files)} of {len(set_expected_files)}"
        progress_message = progress_message_short if len(extra_files) == 0 else progress_message_long
        progress_percentage: float = 0.0
        if len(set_expected_files) > 0:
            progress_percentage = (len(intersection_files) * 100.0) / len(set_expected_files)

        return PipelineProgress(progress_message=progress_message, progress_percentage=progress_percentage)

    def _handle_task_completion(self, parameters: HandleTaskCompletionParameters) -> None:
        """
        Protected hook method for custom logic after a task completes.
        This method is called by callback_run_task.
        Subclasses can override this to implement custom behaviors such as:
        - Updating a database with the latest progress.
        - Checking an external source (like a database flag) to determine if the pipeline should continue or be aborted.

        Args:
            parameters: Details about the PlanTask instance that has successfully completed.
                 The `self` of this method is the ExecutePipeline instance,
                 so you can access `self.run_id_dir`, `self.get_progress_percentage()`, etc.

        Raises:
            PipelineStopRequested: To abort the pipeline execution.
        """
        logger.debug(f"ExecutePipeline._handle_task_completion: Default behavior for task {parameters.task.task_id} in run {self.run_id_dir}. Pipeline will continue.")
        # Default implementation simply allows the pipeline to continue.
        # Subclasses will provide meaningful implementations here.

    def callback_run_task(self, task: PlanTask, duration: float) -> None:
        logger.debug(f"ExecutePipeline.callback_run_task: Current task_id: {task.task_id}. Duration: {duration:.2f} seconds")

        progress: PipelineProgress = self.get_progress_percentage()
        logger.debug(f"ExecutePipeline.callback_run_task: Current progress for run {self.run_id_dir}: {progress!r}")

        parameters = HandleTaskCompletionParameters(task=task, progress=progress, duration=duration)

        # Delegate custom handling (like DB updates or stop checks) to the hook method.
        self._handle_task_completion(parameters)

    @property
    def has_pipeline_complete_file(self) -> bool:
        file_path = self.run_id_dir / FilenameEnum.PIPELINE_COMPLETE.value
        return file_path.exists()

    @property
    def has_report_file(self) -> bool:
        file_path = self.run_id_dir / FilenameEnum.REPORT.value
        return file_path.exists()

    @property
    def has_stop_flag_file(self) -> bool:
        file_path = self.run_id_dir / ExtraFilenameEnum.PIPELINE_STOP_REQUESTED_FLAG.value
        return file_path.exists()

    def run(self):
        # Clean up any pre-existing stop flag before the run.
        stop_flag_path = self.run_id_dir / ExtraFilenameEnum.PIPELINE_STOP_REQUESTED_FLAG.value
        if stop_flag_path.exists():
            logger.debug(f"Removing pre-existing stop flag file: {stop_flag_path!r}")
            stop_flag_path.unlink()

        # create a json file with the expected filenames. Save it to the run/run_id/expected_filenames1.json
        expected_filenames_path = self.run_id_dir / ExtraFilenameEnum.EXPECTED_FILENAMES1_JSON.value
        with open(expected_filenames_path, "w") as f:
            json.dump(self.all_expected_filenames, f, indent=2)
        logger.info(f"Saved {len(self.all_expected_filenames)} expected filenames to {expected_filenames_path}")

        # DIAGNOSTIC: Log before Luigi build starts
        logger.error(f"🔥 About to call luigi.build() with workers=1")
        print(f"🔥 About to call luigi.build() with workers=1")
        print(f"🔥 Luigi will build task: {self.full_plan_pipeline_task}")
        print(f"🔥 Task parameters: run_id_dir={self.run_id_dir}, speedvsdetail={self.speedvsdetail}, llm_models={self.llm_models}")

        # Enable Luigi's detailed logging
        import logging as stdlib_logging
        luigi_logger = stdlib_logging.getLogger('luigi')
        luigi_logger.setLevel(stdlib_logging.INFO)
        print(f"🔥 Enabled Luigi INFO logging")

        # Call luigi.build() with detailed logging
        try:
            print(f"🔥 Calling luigi.build() NOW...")
            self.luigi_build_return_value = luigi.build(
                [self.full_plan_pipeline_task],
                local_scheduler=True,
                workers=1,
                log_level='INFO',  # Enable Luigi's own verbose logging
                detailed_summary=True  # Show detailed task summary
            )
            print(f"🔥 luigi.build() returned!")
        except Exception as e:
            logger.error(f"🔥 luigi.build() raised exception: {type(e).__name__}: {e}")
            print(f"🔥 luigi.build() raised exception: {type(e).__name__}: {e}")
            raise

        # DIAGNOSTIC: Log Luigi build completion
        logger.error(f"🔥 luigi.build() COMPLETED with return value: {self.luigi_build_return_value}")
        print(f"🔥 luigi.build() COMPLETED with return value: {self.luigi_build_return_value}")

        # After the pipeline finishes (or fails), check for the stop flag.
        if self.has_stop_flag_file:
            logger.info("Pipeline was stopped intentionally via PipelineStopRequested exception.")

        logger.info(f"luigi_build_return_value: {self.luigi_build_return_value}")
        logger.info(f"has_pipeline_complete_file: {self.has_pipeline_complete_file}")
        logger.info(f"has_report_file: {self.has_report_file}")
        logger.info(f"has_stop_flag_file: {self.has_stop_flag_file}")

class DemoStoppingExecutePipeline(ExecutePipeline):
    """
    Exercise the pipeline stopping mechanism.
    when a task completes it raises PipelineStopRequested and causes the pipeline to stop.
    """
    def _handle_task_completion(self, parameters: HandleTaskCompletionParameters) -> None:
        logger.info("DemoStoppingExecutePipeline._handle_task_completion: Demo of stopping the pipeline.")
        raise PipelineStopRequested("Demo: Stopping the pipeline after task completion")


if __name__ == '__main__':
    import colorlog
    import sys
    from llama_index.core.instrumentation import get_dispatcher
    from planexe.llm_util.track_activity import TrackActivity

    # DIAGNOSTIC: Verify DATABASE_URL is set in subprocess environment
    print(f"🔥 LUIGI SUBPROCESS STARTED 🔥")
    print(f"🔥 DATABASE_URL in subprocess: {os.environ.get('DATABASE_URL', 'NOT SET')[:60]}...")
    print(f"🔥 OPENAI_API_KEY in subprocess: {os.environ.get('OPENAI_API_KEY', 'NOT SET')[:20]}...")
    print(f"🔥 Total environment variables: {len(os.environ)}")

    pipeline_environment = PipelineEnvironment.from_env()
    try:
        run_id_dir: Path = pipeline_environment.get_run_id_dir()
        print(f"🔥 RUN_ID_DIR: {run_id_dir}")
    except ValueError as e:
        msg = f"RUN_ID_DIR is not set or invalid. Error getting run_id_dir: {e!r}"
        logger.error(msg)
        print(f"Exiting... {msg}")
        sys.exit(1)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # DIAGNOSTIC: Log that logger is configured
    print(f"🔥 Logger configured, about to start Luigi pipeline...")

    # Log messages on the console
    colored_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    stdout_handler = colorlog.StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(colored_formatter)
    stdout_handler.setLevel(logging.DEBUG)
    logger.addHandler(stdout_handler)

    # Capture logs messages to 'run/yyyymmdd_hhmmss/log.txt'
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    log_file: Path = run_id_dir / ExtraFilenameEnum.LOG_TXT.value
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    logger.info(f"pipeline_environment: {pipeline_environment!r}")

    # Example logging messages
    if False:
        logger.debug("This is a debug message.")
        logger.info("This is an info message.")
        logger.warning("This is a warning message.")
        logger.error("This is an error message.")
        logger.critical("This is a critical message.")

    speedvsdetail = SpeedVsDetailEnum.ALL_DETAILS_BUT_SLOW
    speedvsdetail_value = pipeline_environment.speed_vs_detail
    if speedvsdetail_value:
        found = False
        for e in SpeedVsDetailEnum:
            if e.value == speedvsdetail_value:
                speedvsdetail = e
                found = True
                logger.info(f"Setting Speed vs Detail: {speedvsdetail}")
                break
        if not found:
            logger.error(f"Invalid value for SPEED_VS_DETAIL: {speedvsdetail_value}")
    logger.info(f"Speed vs Detail: {speedvsdetail}")

    if False:
        raise Exception("This is a test exception.")

    # logger.info("Environment variables Luigi:\n" + get_env_as_string() + "\n\n\n")

    if True:
        track_activity = TrackActivity(jsonl_file_path=run_id_dir / ExtraFilenameEnum.TRACK_ACTIVITY_JSONL.value, write_to_logger=False)
        get_dispatcher().add_event_handler(track_activity)

    llm_models = ExecutePipeline.resolve_llm_models(pipeline_environment.llm_model)

    if True:
        execute_pipeline = ExecutePipeline(run_id_dir=run_id_dir, speedvsdetail=speedvsdetail, llm_models=llm_models)
    else:
        execute_pipeline = DemoStoppingExecutePipeline(run_id_dir=run_id_dir, speedvsdetail=speedvsdetail, llm_models=llm_models)
    
    try:
        execute_pipeline.setup()
    except Exception as e:
        logger.error(f"Failed to setup pipeline: {e}")
        sys.exit(1)
    
    logger.info(f"execute_pipeline: {execute_pipeline!r}")
    
    try:
        execute_pipeline.run()
    except Exception as e:
        logger.error(f"Failed to run pipeline: {e}")
        sys.exit(1)
