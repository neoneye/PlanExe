"""
PROMPT> python -m src.plan.run_plan_pipeline

In order to resume an unfinished run.
Insert the run_id of the thing you want to resume.
If it's an already finished run, then remove the "999-pipeline_complete.txt" file.
PROMPT> RUN_ID=PlanExe_20250216_150332 python -m src.plan.run_plan_pipeline
"""
from datetime import datetime
import logging
import json
import luigi
from pathlib import Path

from src.plan.filenames import FilenameEnum
from src.plan.speedvsdetail import SpeedVsDetailEnum
from src.plan.plan_file import PlanFile
from src.plan.find_plan_prompt import find_plan_prompt
from src.assume.identify_plan_type import IdentifyPlanType
from src.assume.physical_locations import PhysicalLocations
from src.assume.currency_strategy import CurrencyStrategy
from src.assume.identify_risks import IdentifyRisks
from src.assume.make_assumptions import MakeAssumptions
from src.assume.distill_assumptions import DistillAssumptions
from src.assume.review_assumptions import ReviewAssumptions
from src.assume.shorten_markdown import ShortenMarkdown
from src.expert.pre_project_assessment import PreProjectAssessment
from src.plan.project_plan import ProjectPlan
from src.swot.swot_analysis import SWOTAnalysis
from src.expert.expert_finder import ExpertFinder
from src.expert.expert_criticism import ExpertCriticism
from src.expert.expert_orchestrator import ExpertOrchestrator
from src.plan.create_wbs_level1 import CreateWBSLevel1
from src.plan.create_wbs_level2 import CreateWBSLevel2
from src.plan.create_wbs_level3 import CreateWBSLevel3
from src.pitch.create_pitch import CreatePitch
from src.pitch.convert_pitch_to_markdown import ConvertPitchToMarkdown
from src.plan.identify_wbs_task_dependencies import IdentifyWBSTaskDependencies
from src.plan.estimate_wbs_task_durations import EstimateWBSTaskDurations
from src.plan.review_plan import ReviewPlan
from src.plan.executive_summary import ExecutiveSummary
from src.team.find_team_members import FindTeamMembers
from src.team.enrich_team_members_with_contract_type import EnrichTeamMembersWithContractType
from src.team.enrich_team_members_with_background_story import EnrichTeamMembersWithBackgroundStory
from src.team.enrich_team_members_with_environment_info import EnrichTeamMembersWithEnvironmentInfo
from src.team.team_markdown_document import TeamMarkdownDocumentBuilder
from src.team.review_team import ReviewTeam
from src.wbs.wbs_task import WBSTask, WBSProject
from src.wbs.wbs_populate import WBSPopulate
from src.llm_factory import get_llm
from src.format_json_for_use_in_query import format_json_for_use_in_query
from src.utils.get_env_as_string import get_env_as_string
from src.report.report_generator import ReportGenerator

logger = logging.getLogger(__name__)
DEFAULT_LLM_MODEL = "ollama-llama3.1"

class PlanTask(luigi.Task):
    # Default it to the current timestamp, eg. 19841231_235959
    run_id = luigi.Parameter(default=datetime.now().strftime("%Y%m%d_%H%M%S"))

    # By default, run everything but it's slow.
    # This can be overridden in developer mode, where a quick turnaround is needed, and the details are not important.
    speedvsdetail = luigi.EnumParameter(enum=SpeedVsDetailEnum, default=SpeedVsDetailEnum.ALL_DETAILS_BUT_SLOW)

    @property
    def run_dir(self) -> Path:
        return Path('run') / self.run_id

    def file_path(self, filename: FilenameEnum) -> Path:
        return self.run_dir / filename.value


class SetupTask(PlanTask):
    def output(self):
        return luigi.LocalTarget(str(self.file_path(FilenameEnum.INITIAL_PLAN)))

    def run(self):
        # Ensure the run directory exists.
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # Pick a random prompt.
        plan_prompt = find_plan_prompt("4dc34d55-0d0d-4e9d-92f4-23765f49dd29")
        plan_file = PlanFile.create(plan_prompt)
        plan_file.save(self.output().path)

class PlanTypeTask(PlanTask):
    """
    Determine if the plan is purely digital or requires physical locations.
    Depends on:
      - SetupTask (for the initial plan)
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return SetupTask(run_id=self.run_id)

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.PLAN_TYPE_RAW))),
            'markdown': luigi.LocalTarget(str(self.file_path(FilenameEnum.PLAN_TYPE_MARKDOWN)))
        }

    def run(self):
        logger.info("Identifying PlanType of the plan...")

        # Read inputs from required tasks.
        with self.input().open("r") as f:
            plan_prompt = f.read()

        llm = get_llm(self.llm_model)

        identify_plan_type = IdentifyPlanType.execute(llm, plan_prompt)

        # Write the result to disk.
        output_raw_path = self.output()['raw'].path
        identify_plan_type.save_raw(str(output_raw_path))
        output_markdown_path = self.output()['markdown'].path
        identify_plan_type.save_markdown(str(output_markdown_path))


class PhysicalLocationsTask(PlanTask):
    """
    Identify/suggest physical locations for the plan.
    Depends on:
      - SetupTask (for the initial plan)
      - PlanTypeTask (for the plan type)
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'setup': SetupTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail),
            'plan_type': PlanTypeTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.PHYSICAL_LOCATIONS_RAW))),
            'markdown': luigi.LocalTarget(str(self.file_path(FilenameEnum.PHYSICAL_LOCATIONS_MARKDOWN)))
        }

    def run(self):
        logger.info("Identify/suggest physical locations for the plan...")

        # Read inputs from required tasks.
        with self.input()['setup'].open("r") as f:
            plan_prompt = f.read()

        with self.input()['plan_type']['raw'].open("r") as f:
            plan_type_dict = json.load(f)

        output_raw_path = self.output()['raw'].path
        output_markdown_path = self.output()['markdown'].path

        llm = get_llm(self.llm_model)

        plan_type = plan_type_dict.get("plan_type")
        if plan_type == "physical":
            query = (
                f"File 'plan.txt':\n{plan_prompt}\n\n"
                f"File 'plan_type.json':\n{format_json_for_use_in_query(plan_type_dict)}"
            )

            physical_locations = PhysicalLocations.execute(llm, query)

            # Write the physical locations to disk.
            physical_locations.save_raw(str(output_raw_path))
            physical_locations.save_markdown(str(output_markdown_path))
        else:
            # Write an empty file to indicate that there are no physical locations.
            data = {
                "comment": "The plan is purely digital, without any physical locations."
            }
            with open(output_raw_path, "w") as f:
                json.dump(data, f, indent=2)
            
            with open(output_markdown_path, "w", encoding='utf-8') as f:
                f.write("The plan is purely digital, without any physical locations.")

class CurrencyStrategyTask(PlanTask):
    """
    Identify/suggest what currency to use for the plan, depending on the physical locations.
    Depends on:
      - SetupTask (for the initial plan)
      - PlanTypeTask (for the plan type)
      - PhysicalLocationsTask (for the physical locations)
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'setup': SetupTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail),
            'plan_type': PlanTypeTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'physical_locations': PhysicalLocationsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.CURRENCY_STRATEGY_RAW))),
            'markdown': luigi.LocalTarget(str(self.file_path(FilenameEnum.CURRENCY_STRATEGY_MARKDOWN)))
        }

    def run(self):
        logger.info("Currency strategy for the plan...")

        # Read inputs from required tasks.
        with self.input()['setup'].open("r") as f:
            plan_prompt = f.read()

        with self.input()['plan_type']['raw'].open("r") as f:
            plan_type_dict = json.load(f)

        with self.input()['physical_locations']['raw'].open("r") as f:
            physical_locations_dict = json.load(f)

        query = (
            f"File 'plan.txt':\n{plan_prompt}\n\n"
            f"File 'plan_type.json':\n{format_json_for_use_in_query(plan_type_dict)}\n\n"
            f"File 'physical_locations.json':\n{format_json_for_use_in_query(physical_locations_dict)}"
        )

        llm = get_llm(self.llm_model)

        currency_strategy = CurrencyStrategy.execute(llm, query)

        # Write the result to disk.
        output_raw_path = self.output()['raw'].path
        currency_strategy.save_raw(str(output_raw_path))
        output_markdown_path = self.output()['markdown'].path
        currency_strategy.save_markdown(str(output_markdown_path))


class IdentifyRisksTask(PlanTask):
    """
    Identify risks for the plan, depending on the physical locations.
    Depends on:
      - SetupTask (for the initial plan)
      - PlanTypeTask (for the plan type)
      - PhysicalLocationsTask (for the physical locations)
      - CurrencyStrategy (for the currency strategy)
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'setup': SetupTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail),
            'plan_type': PlanTypeTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'physical_locations': PhysicalLocationsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'currency_strategy': CurrencyStrategyTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.IDENTIFY_RISKS_RAW))),
            'markdown': luigi.LocalTarget(str(self.file_path(FilenameEnum.IDENTIFY_RISKS_MARKDOWN)))
        }

    def run(self):
        logger.info("Identifying risks for the plan...")

        # Read inputs from required tasks.
        with self.input()['setup'].open("r") as f:
            plan_prompt = f.read()

        with self.input()['plan_type']['raw'].open("r") as f:
            plan_type_dict = json.load(f)

        with self.input()['physical_locations']['raw'].open("r") as f:
            physical_locations_dict = json.load(f)

        with self.input()['currency_strategy']['raw'].open("r") as f:
            currency_strategy_dict = json.load(f)

        query = (
            f"File 'plan.txt':\n{plan_prompt}\n\n"
            f"File 'plan_type.json':\n{format_json_for_use_in_query(plan_type_dict)}\n\n"
            f"File 'physical_locations.json':\n{format_json_for_use_in_query(physical_locations_dict)}\n\n"
            f"File 'currency_strategy.json':\n{format_json_for_use_in_query(currency_strategy_dict)}"
        )

        llm = get_llm(self.llm_model)

        identify_risks = IdentifyRisks.execute(llm, query)

        # Write the result to disk.
        output_raw_path = self.output()['raw'].path
        identify_risks.save_raw(str(output_raw_path))
        output_markdown_path = self.output()['markdown'].path
        identify_risks.save_markdown(str(output_markdown_path))


class MakeAssumptionsTask(PlanTask):
    """
    Make assumptions about the plan.
    Depends on:
      - SetupTask (for the initial plan)
      - PlanTypeTask (for the plan type)
      - PhysicalLocationsTask (for the physical locations)
      - CurrencyStrategy (for the currency strategy)
      - IdentifyRisksTask (for the identified risks)
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'setup': SetupTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail),
            'plan_type': PlanTypeTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'physical_locations': PhysicalLocationsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'currency_strategy': CurrencyStrategyTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'identify_risks': IdentifyRisksTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.MAKE_ASSUMPTIONS_RAW))),
            'clean': luigi.LocalTarget(str(self.file_path(FilenameEnum.MAKE_ASSUMPTIONS_CLEAN))),
            'markdown': luigi.LocalTarget(str(self.file_path(FilenameEnum.MAKE_ASSUMPTIONS_MARKDOWN)))
        }

    def run(self):
        logger.info("Making assumptions about the plan...")

        # Read inputs from required tasks.
        with self.input()['setup'].open("r") as f:
            plan_prompt = f.read()

        with self.input()['plan_type']['raw'].open("r") as f:
            plan_type_dict = json.load(f)

        with self.input()['physical_locations']['raw'].open("r") as f:
            physical_locations_dict = json.load(f)

        with self.input()['currency_strategy']['raw'].open("r") as f:
            currency_strategy_dict = json.load(f)

        with self.input()['identify_risks']['raw'].open("r") as f:
            identify_risks_dict = json.load(f)

        query = (
            f"File 'plan.txt':\n{plan_prompt}\n\n"
            f"File 'plan_type.json':\n{format_json_for_use_in_query(plan_type_dict)}\n\n"
            f"File 'physical_locations.json':\n{format_json_for_use_in_query(physical_locations_dict)}\n\n"
            f"File 'currency_strategy.json':\n{format_json_for_use_in_query(currency_strategy_dict)}\n\n"
            f"File 'identify_risks.json':\n{format_json_for_use_in_query(identify_risks_dict)}"
        )

        llm = get_llm(self.llm_model)

        make_assumptions = MakeAssumptions.execute(llm, query)

        # Write the result to disk.
        output_raw_path = self.output()['raw'].path
        make_assumptions.save_raw(str(output_raw_path))
        output_clean_path = self.output()['clean'].path
        make_assumptions.save_assumptions(str(output_clean_path))
        output_markdown_path = self.output()['markdown'].path
        make_assumptions.save_markdown(str(output_markdown_path))


class DistillAssumptionsTask(PlanTask):
    """
    Distill raw assumption data.
    Depends on:
      - SetupTask (for the initial plan)
      - MakeAssumptionsTask (for the draft assumptions)
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'setup': SetupTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail),
            'make_assumptions': MakeAssumptionsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.DISTILL_ASSUMPTIONS_RAW))),
            'markdown': luigi.LocalTarget(str(self.file_path(FilenameEnum.DISTILL_ASSUMPTIONS_MARKDOWN)))
        }

    def run(self):
        logger.info("Distilling assumptions...")

        # Read the plan prompt from SetupTask's output.
        setup_target = self.input()['setup']
        with setup_target.open("r") as f:
            plan_prompt = f.read()

        # Read the assumptions from MakeAssumptionsTask's output.
        make_assumptions_target = self.input()['make_assumptions']['clean']
        with make_assumptions_target.open("r") as f:
            assumptions_raw_data = json.load(f)

        llm = get_llm(self.llm_model)

        query = (
            f"{plan_prompt}\n\n"
            f"assumption.json:\n{assumptions_raw_data}"
        )

        distill_assumptions = DistillAssumptions.execute(llm, query)

        # Write the result to disk.
        output_raw_path = self.output()['raw'].path
        distill_assumptions.save_raw(str(output_raw_path))
        output_markdown_path = self.output()['markdown'].path
        distill_assumptions.save_markdown(str(output_markdown_path))


class ReviewAssumptionsTask(PlanTask):
    """
    Find issues with the assumptions.
    Depends on:
      - PlanTypeTask
      - PhysicalLocationsTask
      - CurrencyStrategyTask
      - IdentifyRisksTask
      - MakeAssumptionsTask
      - DistillAssumptionsTask
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'plan_type': PlanTypeTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'physical_locations': PhysicalLocationsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'currency_strategy': CurrencyStrategyTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'identify_risks': IdentifyRisksTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'make_assumptions': MakeAssumptionsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'distill_assumptions': DistillAssumptionsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.REVIEW_ASSUMPTIONS_RAW))),
            'markdown': luigi.LocalTarget(str(self.file_path(FilenameEnum.REVIEW_ASSUMPTIONS_MARKDOWN)))
        }

    def run(self):
        # Define the list of (title, path) tuples
        title_path_list = [
            ('Plan Type', self.input()['plan_type']['markdown'].path),
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

        llm = get_llm(self.llm_model)

        review_assumptions = ReviewAssumptions.execute(llm, full_markdown)

        # Write the result to disk.
        output_raw_path = self.output()['raw'].path
        review_assumptions.save_raw(str(output_raw_path))
        output_markdown_path = self.output()['markdown'].path
        review_assumptions.save_markdown(str(output_markdown_path))


class ConsolidateAssumptionsMarkdownTask(PlanTask):
    """
    Combines multiple small markdown documents into a single big document.
    Depends on:
      - PlanTypeTask
      - PhysicalLocationsTask
      - CurrencyStrategyTask
      - IdentifyRisksTask
      - MakeAssumptionsTask
      - DistillAssumptionsTask
      - ReviewAssumptionsTask
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'plan_type': PlanTypeTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'physical_locations': PhysicalLocationsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'currency_strategy': CurrencyStrategyTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'identify_risks': IdentifyRisksTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'make_assumptions': MakeAssumptionsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'distill_assumptions': DistillAssumptionsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'review_assumptions': ReviewAssumptionsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'full': luigi.LocalTarget(str(self.file_path(FilenameEnum.CONSOLIDATE_ASSUMPTIONS_FULL_MARKDOWN))),
            'short': luigi.LocalTarget(str(self.file_path(FilenameEnum.CONSOLIDATE_ASSUMPTIONS_SHORT_MARKDOWN)))
        }

    def run(self):
        llm = get_llm(self.llm_model)

        # Define the list of (title, path) tuples
        title_path_list = [
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

            try:
                shorten_markdown = ShortenMarkdown.execute(llm, markdown_chunk)
                short_markdown_chunks.append(f"# {title}\n{shorten_markdown.markdown}")
            except Exception as e:
                logger.error(f"Error shortening markdown file {path} (from {title}): {e}")
                short_markdown_chunks.append(f"**Problem with document:** '{title}'\n\nError shortening markdown file.")
                continue
            
        # Combine the markdown chunks
        full_markdown = "\n\n".join(full_markdown_chunks)
        short_markdown = "\n\n".join(short_markdown_chunks)

        # Write the result to disk.
        output_full_markdown_path = self.output()['full'].path
        with open(output_full_markdown_path, "w", encoding="utf-8") as f:
            f.write(full_markdown)

        output_short_markdown_path = self.output()['short'].path
        with open(output_short_markdown_path, "w", encoding="utf-8") as f:
            f.write(short_markdown)


class PreProjectAssessmentTask(PlanTask):
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'setup': SetupTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail),
            'consolidate_assumptions_markdown': ConsolidateAssumptionsMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.PRE_PROJECT_ASSESSMENT_RAW))),
            'clean': luigi.LocalTarget(str(self.file_path(FilenameEnum.PRE_PROJECT_ASSESSMENT)))
        }

    def run(self):
        logger.info("Conducting pre-project assessment...")

        # Read the plan prompt from the SetupTask's output.
        with self.input()['setup'].open("r") as f:
            plan_prompt = f.read()

        with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
            consolidate_assumptions_markdown = f.read()

        # Build the query.
        query = (
            f"File 'plan.txt':\n{plan_prompt}\n\n"
            f"File 'assumptions.md':\n{consolidate_assumptions_markdown}"
        )

        # Get an instance of your LLM.
        llm = get_llm(self.llm_model)

        # Execute the pre-project assessment.
        pre_project_assessment = PreProjectAssessment.execute(llm, query)

        # Save raw output.
        raw_path = self.file_path(FilenameEnum.PRE_PROJECT_ASSESSMENT_RAW)
        pre_project_assessment.save_raw(str(raw_path))

        # Save cleaned pre-project assessment.
        clean_path = self.file_path(FilenameEnum.PRE_PROJECT_ASSESSMENT)
        pre_project_assessment.save_preproject_assessment(str(clean_path))


class ProjectPlanTask(PlanTask):
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        """
        This task depends on:
          - SetupTask: produces the plan prompt
          - ConsolidateAssumptionsMarkdownTask: the assumptions and scope.
          - PreProjectAssessmentTask: produces the pre‑project assessment files
        """
        return {
            'setup': SetupTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail),
            'consolidate_assumptions_markdown': ConsolidateAssumptionsMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'preproject': PreProjectAssessmentTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.PROJECT_PLAN_RAW))),
            'markdown': luigi.LocalTarget(str(self.file_path(FilenameEnum.PROJECT_PLAN_MARKDOWN)))
        }

    def run(self):
        logger.info("Creating plan...")

        # Read the plan prompt from SetupTask's output.
        setup_target = self.input()['setup']
        with setup_target.open("r") as f:
            plan_prompt = f.read()

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
            f"File 'assumptions.md':\n{consolidate_assumptions_markdown}\n\n"
            f"File 'pre-project-assessment.json':\n{format_json_for_use_in_query(pre_project_assessment_dict)}"
        )

        # Get an LLM instance.
        llm = get_llm(self.llm_model)

        # Execute the plan creation.
        project_plan = ProjectPlan.execute(llm, query)
        
        # Save raw output
        project_plan.save_raw(self.output()['raw'].path)
        
        # Save markdown output
        project_plan.save_markdown(self.output()['markdown'].path)

        logger.info("Project plan created and saved")


class FindTeamMembersTask(PlanTask):
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'setup': SetupTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail),
            'consolidate_assumptions_markdown': ConsolidateAssumptionsMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'preproject': PreProjectAssessmentTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.FIND_TEAM_MEMBERS_RAW))),
            'clean': luigi.LocalTarget(str(self.file_path(FilenameEnum.FIND_TEAM_MEMBERS_CLEAN)))
        }

    def run(self):
        logger.info("FindTeamMembers. Loading files...")

        # Read the plan prompt from SetupTask.
        with self.input()['setup'].open("r") as f:
            plan_prompt = f.read()

        # Load the consolidated assumptions.
        with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
            consolidate_assumptions_markdown = f.read()

        # Read the pre-project assessment from PreProjectAssessmentTask.
        with self.input()['preproject']['clean'].open("r") as f:
            pre_project_assessment_dict = json.load(f)

        # Read the project plan from ProjectPlanTask.
        with self.input()['project_plan']['raw'].open("r") as f:
            project_plan_dict = json.load(f)

        logger.info("FindTeamMembers. All files are now ready. Brainstorming a team...")

        # Build the query.
        query = (
            f"File 'initial-plan.txt':\n{plan_prompt}\n\n"
            f"File 'assumptions.md':\n{consolidate_assumptions_markdown}\n\n"
            f"File 'pre-project-assessment.json':\n{format_json_for_use_in_query(pre_project_assessment_dict)}\n\n"
            f"File 'project-plan.json':\n{format_json_for_use_in_query(project_plan_dict)}"
        )

        # Create LLM instance.
        llm = get_llm(self.llm_model)

        # Execute.
        try:
            find_team_members = FindTeamMembers.execute(llm, query)
        except Exception as e:
            logger.error("FindTeamMembers failed: %s", e)
            raise

        # Save the raw output.
        raw_dict = find_team_members.to_dict()
        with self.output()['raw'].open("w") as f:
            json.dump(raw_dict, f, indent=2)

        # Save the cleaned up result.
        team_member_list = find_team_members.team_member_list
        with self.output()['clean'].open("w") as f:
            json.dump(team_member_list, f, indent=2)

        logger.info("FindTeamMembers complete.")

class EnrichTeamMembersWithContractTypeTask(PlanTask):
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'setup': SetupTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail),
            'consolidate_assumptions_markdown': ConsolidateAssumptionsMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'preproject': PreProjectAssessmentTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'find_team_members': FindTeamMembersTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.ENRICH_TEAM_MEMBERS_CONTRACT_TYPE_RAW))),
            'clean': luigi.LocalTarget(str(self.file_path(FilenameEnum.ENRICH_TEAM_MEMBERS_CONTRACT_TYPE_CLEAN)))
        }

    def run(self):
        logger.info("EnrichTeamMembersWithContractType. Loading files...")

        # Read the plan prompt from SetupTask.
        with self.input()['setup'].open("r") as f:
            plan_prompt = f.read()

        # Load the consolidated assumptions.
        with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
            consolidate_assumptions_markdown = f.read()

        # Read the pre-project assessment from PreProjectAssessmentTask.
        with self.input()['preproject']['clean'].open("r") as f:
            pre_project_assessment_dict = json.load(f)

        # Read the project plan from ProjectPlanTask.
        with self.input()['project_plan']['raw'].open("r") as f:
            project_plan_dict = json.load(f)

        # Read the team_member_list from FindTeamMembersTask.
        with self.input()['find_team_members']['clean'].open("r") as f:
            team_member_list = json.load(f)

        logger.info("EnrichTeamMembersWithContractType. All files are now ready. Processing...")

        # Build the query.
        query = (
            f"File 'initial-plan.txt':\n{plan_prompt}\n\n"
            f"File 'assumptions.md':\n{consolidate_assumptions_markdown}\n\n"
            f"File 'pre-project-assessment.json':\n{format_json_for_use_in_query(pre_project_assessment_dict)}\n\n"
            f"File 'project-plan.json':\n{format_json_for_use_in_query(project_plan_dict)}"
            f"File 'team-members-that-needs-to-be-enriched.json':\n{format_json_for_use_in_query(team_member_list)}"
        )

        # Create LLM instance.
        llm = get_llm(self.llm_model)

        # Execute.
        try:
            enrich_team_members_with_contract_type = EnrichTeamMembersWithContractType.execute(llm, query, team_member_list)
        except Exception as e:
            logger.error("EnrichTeamMembersWithContractType failed: %s", e)
            raise

        # Save the raw output.
        raw_dict = enrich_team_members_with_contract_type.to_dict()
        with self.output()['raw'].open("w") as f:
            json.dump(raw_dict, f, indent=2)

        # Save the cleaned up result.
        team_member_list = enrich_team_members_with_contract_type.team_member_list
        with self.output()['clean'].open("w") as f:
            json.dump(team_member_list, f, indent=2)

        logger.info("EnrichTeamMembersWithContractType complete.")

class EnrichTeamMembersWithBackgroundStoryTask(PlanTask):
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'setup': SetupTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail),
            'consolidate_assumptions_markdown': ConsolidateAssumptionsMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'preproject': PreProjectAssessmentTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'enrich_team_members_with_contract_type': EnrichTeamMembersWithContractTypeTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.ENRICH_TEAM_MEMBERS_BACKGROUND_STORY_RAW))),
            'clean': luigi.LocalTarget(str(self.file_path(FilenameEnum.ENRICH_TEAM_MEMBERS_BACKGROUND_STORY_CLEAN)))
        }

    def run(self):
        logger.info("EnrichTeamMembersWithBackgroundStoryTask. Loading files...")

        # Read the plan prompt from SetupTask.
        with self.input()['setup'].open("r") as f:
            plan_prompt = f.read()

        # Load the consolidated assumptions.
        with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
            consolidate_assumptions_markdown = f.read()

        # Read the pre-project assessment from PreProjectAssessmentTask.
        with self.input()['preproject']['clean'].open("r") as f:
            pre_project_assessment_dict = json.load(f)

        # Read the project plan from ProjectPlanTask.
        with self.input()['project_plan']['raw'].open("r") as f:
            project_plan_dict = json.load(f)

        # Read the team_member_list from EnrichTeamMembersWithContractTypeTask.
        with self.input()['enrich_team_members_with_contract_type']['clean'].open("r") as f:
            team_member_list = json.load(f)

        logger.info("EnrichTeamMembersWithBackgroundStoryTask. All files are now ready. Processing...")

        # Build the query.
        query = (
            f"File 'initial-plan.txt':\n{plan_prompt}\n\n"
            f"File 'assumptions.md':\n{consolidate_assumptions_markdown}\n\n"
            f"File 'pre-project-assessment.json':\n{format_json_for_use_in_query(pre_project_assessment_dict)}\n\n"
            f"File 'project-plan.json':\n{format_json_for_use_in_query(project_plan_dict)}"
            f"File 'team-members-that-needs-to-be-enriched.json':\n{format_json_for_use_in_query(team_member_list)}"
        )

        # Create LLM instance.
        llm = get_llm(self.llm_model)

        # Execute.
        try:
            enrich_team_members_with_background_story = EnrichTeamMembersWithBackgroundStory.execute(llm, query, team_member_list)
        except Exception as e:
            logger.error("EnrichTeamMembersWithBackgroundStory failed: %s", e)
            raise

        # Save the raw output.
        raw_dict = enrich_team_members_with_background_story.to_dict()
        with self.output()['raw'].open("w") as f:
            json.dump(raw_dict, f, indent=2)

        # Save the cleaned up result.
        team_member_list = enrich_team_members_with_background_story.team_member_list
        with self.output()['clean'].open("w") as f:
            json.dump(team_member_list, f, indent=2)

        logger.info("EnrichTeamMembersWithBackgroundStoryTask complete.")

class EnrichTeamMembersWithEnvironmentInfoTask(PlanTask):
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'setup': SetupTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail),
            'consolidate_assumptions_markdown': ConsolidateAssumptionsMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'preproject': PreProjectAssessmentTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'enrich_team_members_with_background_story': EnrichTeamMembersWithBackgroundStoryTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.ENRICH_TEAM_MEMBERS_ENVIRONMENT_INFO_RAW))),
            'clean': luigi.LocalTarget(str(self.file_path(FilenameEnum.ENRICH_TEAM_MEMBERS_ENVIRONMENT_INFO_CLEAN)))
        }

    def run(self):
        logger.info("EnrichTeamMembersWithEnvironmentInfoTask. Loading files...")

        # Read the plan prompt from SetupTask.
        with self.input()['setup'].open("r") as f:
            plan_prompt = f.read()

        # Load the consolidated assumptions.
        with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
            consolidate_assumptions_markdown = f.read()

        # Read the pre-project assessment from PreProjectAssessmentTask.
        with self.input()['preproject']['clean'].open("r") as f:
            pre_project_assessment_dict = json.load(f)

        # Read the project plan from ProjectPlanTask.
        with self.input()['project_plan']['raw'].open("r") as f:
            project_plan_dict = json.load(f)

        # Read the team_member_list from EnrichTeamMembersWithBackgroundStoryTask.
        with self.input()['enrich_team_members_with_background_story']['clean'].open("r") as f:
            team_member_list = json.load(f)

        logger.info("EnrichTeamMembersWithEnvironmentInfoTask. All files are now ready. Processing...")

        # Build the query.
        query = (
            f"File 'initial-plan.txt':\n{plan_prompt}\n\n"
            f"File 'assumptions.md':\n{consolidate_assumptions_markdown}\n\n"
            f"File 'pre-project-assessment.json':\n{format_json_for_use_in_query(pre_project_assessment_dict)}\n\n"
            f"File 'project-plan.json':\n{format_json_for_use_in_query(project_plan_dict)}"
            f"File 'team-members-that-needs-to-be-enriched.json':\n{format_json_for_use_in_query(team_member_list)}"
        )

        # Create LLM instance.
        llm = get_llm(self.llm_model)

        # Execute.
        try:
            enrich_team_members_with_background_story = EnrichTeamMembersWithEnvironmentInfo.execute(llm, query, team_member_list)
        except Exception as e:
            logger.error("EnrichTeamMembersWithEnvironmentInfo failed: %s", e)
            raise

        # Save the raw output.
        raw_dict = enrich_team_members_with_background_story.to_dict()
        with self.output()['raw'].open("w") as f:
            json.dump(raw_dict, f, indent=2)

        # Save the cleaned up result.
        team_member_list = enrich_team_members_with_background_story.team_member_list
        with self.output()['clean'].open("w") as f:
            json.dump(team_member_list, f, indent=2)

        logger.info("EnrichTeamMembersWithEnvironmentInfoTask complete.")

class ReviewTeamTask(PlanTask):
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'setup': SetupTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail),
            'consolidate_assumptions_markdown': ConsolidateAssumptionsMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'preproject': PreProjectAssessmentTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'enrich_team_members_with_environment_info': EnrichTeamMembersWithEnvironmentInfoTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return luigi.LocalTarget(str(self.file_path(FilenameEnum.REVIEW_TEAM_RAW)))

    def run(self):
        logger.info("ReviewTeamTask. Loading files...")

        # Read the plan prompt from SetupTask.
        with self.input()['setup'].open("r") as f:
            plan_prompt = f.read()

        # Load the consolidated assumptions.
        with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
            consolidate_assumptions_markdown = f.read()

        # Read the pre-project assessment from PreProjectAssessmentTask.
        with self.input()['preproject']['clean'].open("r") as f:
            pre_project_assessment_dict = json.load(f)

        # Read the project plan from ProjectPlanTask.
        with self.input()['project_plan']['raw'].open("r") as f:
            project_plan_dict = json.load(f)

        # Read the team_member_list from EnrichTeamMembersWithEnvironmentInfoTask.
        with self.input()['enrich_team_members_with_environment_info']['clean'].open("r") as f:
            team_member_list = json.load(f)

        logger.info("ReviewTeamTask. All files are now ready. Processing...")

        # Convert the team members to a Markdown document.
        builder = TeamMarkdownDocumentBuilder()
        builder.append_roles(team_member_list, title=None)
        team_document_markdown = builder.to_string()

        # Build the query.
        query = (
            f"File 'initial-plan.txt':\n{plan_prompt}\n\n"
            f"File 'assumptions.md':\n{consolidate_assumptions_markdown}\n\n"
            f"File 'pre-project-assessment.json':\n{format_json_for_use_in_query(pre_project_assessment_dict)}\n\n"
            f"File 'project-plan.json':\n{format_json_for_use_in_query(project_plan_dict)}"
            f"File 'team-members.md':\n{team_document_markdown}"
        )

        # Create LLM instance.
        llm = get_llm(self.llm_model)

        # Execute.
        try:
            review_team = ReviewTeam.execute(llm, query)
        except Exception as e:
            logger.error("ReviewTeam failed: %s", e)
            raise

        # Save the raw output.
        raw_dict = review_team.to_dict()
        with self.output().open("w") as f:
            json.dump(raw_dict, f, indent=2)

        logger.info("ReviewTeamTask complete.")

class TeamMarkdownTask(PlanTask):
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'enrich_team_members_with_environment_info': EnrichTeamMembersWithEnvironmentInfoTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'review_team': ReviewTeamTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return luigi.LocalTarget(str(self.file_path(FilenameEnum.TEAM_MARKDOWN)))

    def run(self):
        logger.info("TeamMarkdownTask. Loading files...")

        # 1. Read the team_member_list from EnrichTeamMembersWithEnvironmentInfoTask.
        with self.input()['enrich_team_members_with_environment_info']['clean'].open("r") as f:
            team_member_list = json.load(f)

        # 2. Read the json from ReviewTeamTask.
        with self.input()['review_team'].open("r") as f:
            review_team_json = json.load(f)

        logger.info("TeamMarkdownTask. All files are now ready. Processing...")

        # Combine the team members and the review into a Markdown document.
        builder = TeamMarkdownDocumentBuilder()
        builder.append_roles(team_member_list)
        builder.append_separator()
        builder.append_full_review(review_team_json)
        builder.write_to_file(self.output().path)

        logger.info("TeamMarkdownTask complete.")

class SWOTAnalysisTask(PlanTask):
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'setup': SetupTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail),
            'consolidate_assumptions_markdown': ConsolidateAssumptionsMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'preproject': PreProjectAssessmentTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.SWOT_RAW))),
            'markdown': luigi.LocalTarget(str(self.file_path(FilenameEnum.SWOT_MARKDOWN)))
        }

    def run(self):
        logger.info("SWOTAnalysisTask. Loading files...")

        # Read the plan prompt from SetupTask.
        with self.input()['setup'].open("r") as f:
            plan_prompt = f.read()

        # Load the consolidated assumptions.
        with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
            consolidate_assumptions_markdown = f.read()

        # Read the pre-project assessment from PreProjectAssessmentTask.
        with self.input()['preproject']['clean'].open("r") as f:
            pre_project_assessment_dict = json.load(f)

        # Read the project plan from ProjectPlanTask.
        with self.input()['project_plan']['raw'].open("r") as f:
            project_plan_dict = json.load(f)

        logger.info("SWOTAnalysisTask. All files are now ready. Performing analysis...")

        # Build the query for SWOT analysis.
        query = (
            f"File 'initial-plan.txt':\n{plan_prompt}\n\n"
            f"File 'assumptions.md':\n{consolidate_assumptions_markdown}\n\n"
            f"File 'pre-project-assessment.json':\n{format_json_for_use_in_query(pre_project_assessment_dict)}\n\n"
            f"File 'project-plan.json':\n{format_json_for_use_in_query(project_plan_dict)}"
        )

        # Create LLM instances for SWOT analysis.
        llm = get_llm(self.llm_model)

        # Execute the SWOT analysis.
        try:
            swot_analysis = SWOTAnalysis.execute(llm, query)
        except Exception as e:
            logger.error("SWOT analysis failed: %s", e)
            raise

        # Convert the SWOT analysis to a dict and markdown.
        swot_raw_dict = swot_analysis.to_dict()
        swot_markdown = swot_analysis.to_markdown(include_metadata=False)

        # Write the raw SWOT JSON.
        with self.output()['raw'].open("w") as f:
            json.dump(swot_raw_dict, f, indent=2)

        # Write the SWOT analysis as Markdown.
        markdown_path = self.output()['markdown'].path
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(swot_markdown)

        logger.info("SWOT analysis complete.")

class ExpertReviewTask(PlanTask):
    """
    Finds experts to review the SWOT analysis and have them provide criticism.
    Depends on:
      - SetupTask (for the initial plan)
      - PreProjectAssessmentTask (for the pre‑project assessment)
      - ProjectPlanTask (for the project plan)
      - SWOTAnalysisTask (for the SWOT analysis)
    Produces:
      - Raw experts file (006-experts_raw.json)
      - Cleaned experts file (007-experts.json)
      - For each expert, a raw expert criticism file (008-XX-expert_criticism_raw.json) [side effects via callbacks]
      - Final expert criticism markdown (009-expert_criticism.md)
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'setup': SetupTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail),
            'preproject': PreProjectAssessmentTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'swot_analysis': SWOTAnalysisTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return luigi.LocalTarget(str(self.file_path(FilenameEnum.EXPERT_CRITICISM_MARKDOWN)))

    def run(self):
        logger.info("Finding experts to review the SWOT analysis, and having them provide criticism...")

        # Read inputs from required tasks.
        with self.input()['setup'].open("r") as f:
            plan_prompt = f.read()
        with self.input()['preproject']['clean'].open("r") as f:
            pre_project_assessment_dict = json.load(f)
        with self.input()['project_plan']['raw'].open("r") as f:
            project_plan_dict = json.load(f)
        swot_markdown_path = self.input()['swot_analysis']['markdown'].path
        with open(swot_markdown_path, "r", encoding="utf-8") as f:
            swot_markdown = f.read()

        # Build the query.
        query = (
            f"Initial plan: {plan_prompt}\n\n"
            f"Pre-project assessment:\n{format_json_for_use_in_query(pre_project_assessment_dict)}\n\n"
            f"Project plan:\n{format_json_for_use_in_query(project_plan_dict)}\n\n"
            f"SWOT Analysis:\n{swot_markdown}"
        )

        llm = get_llm(self.llm_model)

        # Define callback functions.
        def phase1_post_callback(expert_finder: ExpertFinder) -> None:
            raw_path = self.run_dir / FilenameEnum.EXPERTS_RAW.value
            cleaned_path = self.run_dir / FilenameEnum.EXPERTS_CLEAN.value
            expert_finder.save_raw(str(raw_path))
            expert_finder.save_cleanedup(str(cleaned_path))

        def phase2_post_callback(expert_criticism: ExpertCriticism, expert_index: int) -> None:
            file_path = self.run_dir / FilenameEnum.EXPERT_CRITICISM_RAW_TEMPLATE.format(expert_index + 1)
            expert_criticism.save_raw(str(file_path))

        # Execute the expert orchestration.
        expert_orchestrator = ExpertOrchestrator()
        # IDEA: max_expert_count. don't truncate to 2 experts. Interview them all in production mode.
        expert_orchestrator.phase1_post_callback = phase1_post_callback
        expert_orchestrator.phase2_post_callback = phase2_post_callback
        expert_orchestrator.execute(llm, query)

        # Write final expert criticism markdown.
        expert_criticism_markdown_file = self.file_path(FilenameEnum.EXPERT_CRITICISM_MARKDOWN)
        with expert_criticism_markdown_file.open("w") as f:
            f.write(expert_orchestrator.to_markdown())

class CreateWBSLevel1Task(PlanTask):
    """
    Creates the Work Breakdown Structure (WBS) Level 1.
    Depends on:
      - ProjectPlanTask: provides the project plan as JSON.
    Produces:
      - Raw WBS Level 1 output file (xxx-wbs_level1_raw.json)
      - Cleaned up WBS Level 1 file (xxx-wbs_level1.json)
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.WBS_LEVEL1_RAW))),
            'clean': luigi.LocalTarget(str(self.file_path(FilenameEnum.WBS_LEVEL1)))
        }

    def run(self):
        logger.info("Creating Work Breakdown Structure (WBS) Level 1...")
        
        # Read the project plan JSON from the dependency.
        with self.input()['project_plan']['raw'].open("r") as f:
            project_plan_dict = json.load(f)
        
        # Build the query using the project plan.
        query = format_json_for_use_in_query(project_plan_dict)
        
        # Get an LLM instance.
        llm = get_llm(self.llm_model)
        
        # Execute the WBS Level 1 creation.
        create_wbs_level1 = CreateWBSLevel1.execute(llm, query)
        
        # Save the raw output.
        wbs_level1_raw_dict = create_wbs_level1.raw_response_dict()
        with self.output()['raw'].open("w") as f:
            json.dump(wbs_level1_raw_dict, f, indent=2)
        
        # Save the cleaned up result.
        wbs_level1_result_json = create_wbs_level1.cleanedup_dict()
        with self.output()['clean'].open("w") as f:
            json.dump(wbs_level1_result_json, f, indent=2)
        
        logger.info("WBS Level 1 created successfully.")

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
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'wbs_level1': CreateWBSLevel1Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.WBS_LEVEL2_RAW))),
            'clean': luigi.LocalTarget(str(self.file_path(FilenameEnum.WBS_LEVEL2)))
        }

    def run(self):
        logger.info("Creating Work Breakdown Structure (WBS) Level 2...")
        
        # Read the project plan from the ProjectPlanTask output.
        with self.input()['project_plan']['raw'].open("r") as f:
            project_plan_dict = json.load(f)
        
        # Read the cleaned WBS Level 1 result from the CreateWBSLevel1Task output.
        # Here we assume the cleaned output is under the 'clean' key.
        with self.input()['wbs_level1']['clean'].open("r") as f:
            wbs_level1_result_json = json.load(f)
        
        # Build the query using CreateWBSLevel2's format_query method.
        query = CreateWBSLevel2.format_query(project_plan_dict, wbs_level1_result_json)
        
        # Get an LLM instance.
        llm = get_llm(self.llm_model)
        
        # Execute the WBS Level 2 creation.
        create_wbs_level2 = CreateWBSLevel2.execute(llm, query)
        
        # Retrieve and write the raw output.
        wbs_level2_raw_dict = create_wbs_level2.raw_response_dict()
        with self.output()['raw'].open("w") as f:
            json.dump(wbs_level2_raw_dict, f, indent=2)
        
        # Retrieve and write the cleaned output (e.g. major phases with subtasks).
        with self.output()['clean'].open("w") as f:
            json.dump(create_wbs_level2.major_phases_with_subtasks, f, indent=2)
        
        logger.info("WBS Level 2 created successfully.")

class WBSProjectLevel1AndLevel2Task(PlanTask):
    """
    Create a WBS project from the WBS Level 1 and Level 2 JSON files.
    
    It depends on:
      - CreateWBSLevel1Task: providing the cleaned WBS Level 1 JSON.
      - CreateWBSLevel2Task: providing the major phases with subtasks and the task UUIDs.
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def output(self):
        return luigi.LocalTarget(str(self.file_path(FilenameEnum.WBS_PROJECT_LEVEL1_AND_LEVEL2)))
    
    def requires(self):
        return {
            'wbs_level1': CreateWBSLevel1Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'wbs_level2': CreateWBSLevel2Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
        }
    
    def run(self):
        wbs_level1_path = self.input()['wbs_level1']['clean'].path
        wbs_level2_path = self.input()['wbs_level2']['clean'].path
        wbs_project = WBSPopulate.project_from_level1_json(wbs_level1_path)
        WBSPopulate.extend_project_with_level2_json(wbs_project, wbs_level2_path)

        json_representation = json.dumps(wbs_project.to_dict(), indent=2)
        with self.output().open("w") as f:
            f.write(json_representation)

class CreatePitchTask(PlanTask):
    """
    Create a the pitch that explains the project plan, from multiple perspectives.
    
    This task depends on:
      - ProjectPlanTask: provides the project plan JSON.
      - WBSProjectLevel1AndLevel2Task: containing the top level of the project plan.
    
    The resulting pitch JSON is written to the file specified by FilenameEnum.PITCH.
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)
    
    def output(self):
        return luigi.LocalTarget(str(self.file_path(FilenameEnum.PITCH_RAW)))
    
    def requires(self):
        return {
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'wbs_project': WBSProjectLevel1AndLevel2Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
        }
    
    def run(self):
        logger.info("Creating pitch...")
        
        # Read the project plan JSON.
        with self.input()['project_plan']['raw'].open("r") as f:
            project_plan_dict = json.load(f)
        
        wbs_project_path = self.input()['wbs_project'].path
        with open(wbs_project_path, "r") as f:
            wbs_project_dict = json.load(f)
        wbs_project = WBSProject.from_dict(wbs_project_dict)
        wbs_project_json = wbs_project.to_dict()
        
        # Build the query
        query = (
            f"The project plan:\n{format_json_for_use_in_query(project_plan_dict)}\n\n"
            f"Work Breakdown Structure:\n{format_json_for_use_in_query(wbs_project_json)}"
        )
        
        # Get the LLM instance.
        llm = get_llm(self.llm_model)
        
        # Execute the pitch creation.
        create_pitch = CreatePitch.execute(llm, query)
        pitch_dict = create_pitch.raw_response_dict()
        
        # Write the resulting pitch JSON to the output file.
        with self.output().open("w") as f:
            json.dump(pitch_dict, f, indent=2)
        
        logger.info("Pitch created and written to %s", self.output().path)

class ConvertPitchToMarkdownTask(PlanTask):
    """
    Human readable version of the pitch.
    
    This task depends on:
      - CreatePitchTask: Creates the pitch JSON.
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)
    
    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.PITCH_CONVERT_TO_MARKDOWN_RAW))),
            'markdown': luigi.LocalTarget(str(self.file_path(FilenameEnum.PITCH_MARKDOWN)))
        }
    
    def requires(self):
        return {
            'pitch': CreatePitchTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
        }
    
    def run(self):
        logger.info("Converting raw pitch to markdown...")
        
        # Read the project plan JSON.
        with self.input()['pitch'].open("r") as f:
            pitch_json = json.load(f)
        
        # Build the query
        query = format_json_for_use_in_query(pitch_json)
        
        # Get the LLM instance.
        llm = get_llm(self.llm_model)
        
        # Execute the convertion.
        converted = ConvertPitchToMarkdown.execute(llm, query)

        # Save the results.
        json_path = self.output()['raw'].path
        converted.save_raw(json_path)
        markdown_path = self.output()['markdown'].path
        converted.save_markdown(markdown_path)

        logger.info("Converted raw pitch to markdown.")

class IdentifyTaskDependenciesTask(PlanTask):
    """
    This task identifies the dependencies between WBS tasks.
    
    It depends on:
      - ProjectPlanTask: provides the project plan JSON.
      - CreateWBSLevel2Task: provides the major phases with subtasks.
    
    The raw JSON response is written to the file specified by FilenameEnum.TASK_DEPENDENCIES_RAW.
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)
    
    def output(self):
        return luigi.LocalTarget(str(self.file_path(FilenameEnum.TASK_DEPENDENCIES_RAW)))
    
    def requires(self):
        return {
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'wbs_level2': CreateWBSLevel2Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }
    
    def run(self):
        logger.info("Identifying task dependencies...")
        
        # Read the project plan JSON.
        with self.input()['project_plan']['raw'].open("r") as f:
            project_plan_dict = json.load(f)
        
        # Read the major phases with subtasks from WBS Level 2 output.
        with self.input()['wbs_level2']['clean'].open("r") as f:
            major_phases_with_subtasks = json.load(f)
        
        # Build the query using the provided format method.
        query = IdentifyWBSTaskDependencies.format_query(project_plan_dict, major_phases_with_subtasks)
        
        # Get the LLM instance.
        llm = get_llm(self.llm_model)
        
        # Execute the dependency identification.
        identify_dependencies = IdentifyWBSTaskDependencies.execute(llm, query)
        dependencies_raw_dict = identify_dependencies.raw_response_dict()
        
        # Write the raw dependencies JSON to the output file.
        with self.output().open("w") as f:
            json.dump(dependencies_raw_dict, f, indent=2)
        
        logger.info("Task dependencies identified and written to %s", self.output().path)

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
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)
    
    def output(self):
        # The primary output is the aggregated task durations JSON.
        return luigi.LocalTarget(str(self.file_path(FilenameEnum.TASK_DURATIONS)))
    
    def requires(self):
        return {
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'wbs_project': WBSProjectLevel1AndLevel2Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
        }
    
    def run(self):
        logger.info("Estimating task durations...")
        
        # Load the project plan JSON.
        with self.input()['project_plan']['raw'].open("r") as f:
            project_plan_dict = json.load(f)

        with self.input()['wbs_project'].open("r") as f:
            wbs_project_dict = json.load(f)
        wbs_project = WBSProject.from_dict(wbs_project_dict)

        # json'ish representation of the major phases in the WBS, and their subtasks.
        root_task = wbs_project.root_task
        major_tasks = [child.to_dict() for child in root_task.task_children]
        major_phases_with_subtasks = major_tasks

        # Don't include uuid of the root task. It's the child tasks that are of interest to estimate.
        decompose_task_id_list = []
        for task in wbs_project.root_task.task_children:
            decompose_task_id_list.extend(task.task_ids())

        logger.info(f"There are {len(decompose_task_id_list)} tasks to be estimated.")
        
        # Split the task IDs into chunks of 3.
        task_ids_chunks = [decompose_task_id_list[i:i + 3] for i in range(0, len(decompose_task_id_list), 3)]
        
        # In production mode, all chunks are processed.
        # In developer mode, truncate to only 2 chunks for fast turnaround cycle. Otherwise LOTS of tasks are to be estimated.
        logger.info(f"EstimateTaskDurationsTask.speedvsdetail: {self.speedvsdetail}")
        if self.speedvsdetail == SpeedVsDetailEnum.FAST_BUT_SKIP_DETAILS:
            logger.info("FAST_BUT_SKIP_DETAILS mode, truncating to 2 chunks for testing.")
            task_ids_chunks = task_ids_chunks[:2]
        else:
            logger.info("Processing all chunks.")

        # Get the LLM instance.
        llm = get_llm(self.llm_model)
        
        # Process each chunk.
        accumulated_task_duration_list = []
        for index, task_ids_chunk in enumerate(task_ids_chunks, start=1):
            logger.info("Processing chunk %d of %d", index, len(task_ids_chunks))
            
            query = EstimateWBSTaskDurations.format_query(
                project_plan_dict,
                major_phases_with_subtasks,
                task_ids_chunk
            )
            
            estimate_durations = EstimateWBSTaskDurations.execute(llm, query)
            durations_raw_dict = estimate_durations.raw_response_dict()
            
            # Write the raw JSON for this chunk.
            filename = FilenameEnum.TASK_DURATIONS_RAW_TEMPLATE.format(index)
            raw_chunk_path = self.run_dir / filename
            with open(raw_chunk_path, "w") as f:
                json.dump(durations_raw_dict, f, indent=2)
            
            accumulated_task_duration_list.extend(durations_raw_dict.get('task_details', []))
        
        # Write the aggregated task durations.
        aggregated_path = self.file_path(FilenameEnum.TASK_DURATIONS)
        with open(aggregated_path, "w") as f:
            json.dump(accumulated_task_duration_list, f, indent=2)
        
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
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)
    
    def output(self):
        return luigi.LocalTarget(str(self.file_path(FilenameEnum.WBS_LEVEL3)))
    
    def requires(self):
        return {
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'wbs_project': WBSProjectLevel1AndLevel2Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'task_durations': EstimateTaskDurationsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }
    
    def run(self):
        logger.info("Creating Work Breakdown Structure (WBS) Level 3...")
        
        # Load the project plan JSON.
        with self.input()['project_plan']['raw'].open("r") as f:
            project_plan_dict = json.load(f)
        
        with self.input()['wbs_project'].open("r") as f:
            wbs_project_dict = json.load(f)
        wbs_project = WBSProject.from_dict(wbs_project_dict)

        # Load the estimated task durations.
        task_duration_list_path = self.input()['task_durations'].path
        WBSPopulate.extend_project_with_durations_json(wbs_project, task_duration_list_path)

        # for each task in the wbs_project, find the task that has no children
        tasks_with_no_children = []
        def visit_task(task):
            if len(task.task_children) == 0:
                tasks_with_no_children.append(task)
            else:
                for child in task.task_children:
                    visit_task(child)
        visit_task(wbs_project.root_task)

        # for each task with no children, extract the task_id
        decompose_task_id_list = []
        for task in tasks_with_no_children:
            decompose_task_id_list.append(task.id)
        
        logger.info("There are %d tasks to be decomposed.", len(decompose_task_id_list))

        # In production mode, all chunks are processed.
        # In developer mode, truncate to only 2 chunks for fast turnaround cycle. Otherwise LOTS of tasks are to be decomposed.
        logger.info(f"CreateWBSLevel3Task.speedvsdetail: {self.speedvsdetail}")
        if self.speedvsdetail == SpeedVsDetailEnum.FAST_BUT_SKIP_DETAILS:
            logger.info("FAST_BUT_SKIP_DETAILS mode, truncating to 2 chunks for testing.")
            decompose_task_id_list = decompose_task_id_list[:2]
        else:
            logger.info("Processing all chunks.")
        
        # Get an LLM instance.
        llm = get_llm(self.llm_model)
        
        project_plan_str = format_json_for_use_in_query(project_plan_dict)
        wbs_project_str = format_json_for_use_in_query(wbs_project.to_dict())

        # Loop over each task ID.
        wbs_level3_result_accumulated = []
        total_tasks = len(decompose_task_id_list)
        for index, task_id in enumerate(decompose_task_id_list, start=1):
            logger.info("Decomposing task %d of %d", index, total_tasks)
            
            query = (
                f"The project plan:\n{project_plan_str}\n\n"
                f"Work breakdown structure:\n{wbs_project_str}\n\n"
                f"Only decompose this task:\n\"{task_id}\""
            )

            create_wbs_level3 = CreateWBSLevel3.execute(llm, query, task_id)
            wbs_level3_raw_dict = create_wbs_level3.raw_response_dict()
            
            # Write the raw JSON for this task using the FilenameEnum template.
            raw_filename = FilenameEnum.WBS_LEVEL3_RAW_TEMPLATE.value.format(index)
            raw_chunk_path = self.run_dir / raw_filename
            with open(raw_chunk_path, 'w') as f:
                json.dump(wbs_level3_raw_dict, f, indent=2)
            
            # Accumulate the decomposed tasks.
            wbs_level3_result_accumulated.extend(create_wbs_level3.tasks)
        
        # Write the aggregated WBS Level 3 result.
        aggregated_path = self.file_path(FilenameEnum.WBS_LEVEL3)
        with open(aggregated_path, 'w') as f:
            json.dump(wbs_level3_result_accumulated, f, indent=2)
        
        logger.info("WBS Level 3 created and aggregated results written to %s", aggregated_path)

class WBSProjectLevel1AndLevel2AndLevel3Task(PlanTask):
    """
    Create a WBS project from the WBS Level 1 and Level 2 and Level 3 JSON files.
    
    It depends on:
      - WBSProjectLevel1AndLevel2Task: providing the major phases with subtasks and the task UUIDs.
      - CreateWBSLevel3Task: providing the decomposed tasks.
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def output(self):
        return {
            'full': luigi.LocalTarget(str(self.file_path(FilenameEnum.WBS_PROJECT_LEVEL1_AND_LEVEL2_AND_LEVEL3_FULL))),
            'csv': luigi.LocalTarget(str(self.file_path(FilenameEnum.WBS_PROJECT_LEVEL1_AND_LEVEL2_AND_LEVEL3_CSV)))
        }
    
    def requires(self):
        return {
            'wbs_project12': WBSProjectLevel1AndLevel2Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'wbs_level3': CreateWBSLevel3Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
        }
    
    def run(self):
        wbs_project_path = self.input()['wbs_project12'].path
        with open(wbs_project_path, "r") as f:
            wbs_project_dict = json.load(f)
        wbs_project = WBSProject.from_dict(wbs_project_dict)

        wbs_level3_path = self.input()['wbs_level3'].path
        WBSPopulate.extend_project_with_decomposed_tasks_json(wbs_project, wbs_level3_path)

        json_representation = json.dumps(wbs_project.to_dict(), indent=2)
        with self.output()['full'].open("w") as f:
            f.write(json_representation)
        
        csv_representation = wbs_project.to_csv_string()
        with self.output()['csv'].open("w") as f:
            f.write(csv_representation)

class ReviewPlanTask(PlanTask):
    """
    Ask questions about the almost finished plan.
    
    It depends on:
      - ConsolidateAssumptionsMarkdownTask: provides the assumptions as Markdown.
      - ProjectPlanTask: provides the project plan as Markdown.
      - SWOTAnalysisTask: provides the SWOT analysis as Markdown.
      - TeamMarkdownTask: provides the team as Markdown.
      - ConvertPitchToMarkdownTask: provides the pitch as Markdown.
      - ExpertReviewTask: provides the expert criticism as Markdown.
      - WBSProjectLevel1AndLevel2AndLevel3Task: provides the table csv file.
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.REVIEW_PLAN_RAW))),
            'markdown': luigi.LocalTarget(str(self.file_path(FilenameEnum.REVIEW_PLAN_MARKDOWN)))
        }
    
    def requires(self):
        return {
            'consolidate_assumptions_markdown': ConsolidateAssumptionsMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'swot_analysis': SWOTAnalysisTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'team_markdown': TeamMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'pitch_markdown': ConvertPitchToMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'expert_review': ExpertReviewTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'wbs_project123': WBSProjectLevel1AndLevel2AndLevel3Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }
    
    def run(self):
        # Read inputs from required tasks.
        with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
            assumptions_markdown = f.read()
        with self.input()['project_plan']['markdown'].open("r") as f:
            project_plan_markdown = f.read()
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

        # Build the query.
        query = (
            f"File 'assumptions.md':\n{assumptions_markdown}\n\n"
            f"File 'project-plan.md':\n{project_plan_markdown}\n\n"
            f"File 'swot-analysis.md':\n{swot_analysis_markdown}\n\n"
            f"File 'team.md':\n{team_markdown}\n\n"
            f"File 'pitch.md':\n{pitch_markdown}\n\n"
            f"File 'expert-review.md':\n{expert_review}\n\n"
            f"File 'work-breakdown-structure.csv':\n{wbs_project_csv}"
        )

        llm = get_llm(self.llm_model)

        # Perform the review.
        review_plan = ReviewPlan.execute(llm, query)

        # Save the results.
        json_path = self.output()['raw'].path
        review_plan.save_raw(json_path)
        markdown_path = self.output()['markdown'].path
        review_plan.save_markdown(markdown_path)

        logger.info("Reviewed the plan.")


class ExecutiveSummaryTask(PlanTask):
    """
    Create an executive summary of the plan.
    
    It depends on:
      - ConsolidateAssumptionsMarkdownTask: provides the assumptions as Markdown.
      - ProjectPlanTask: provides the project plan as Markdown.
      - SWOTAnalysisTask: provides the SWOT analysis as Markdown.
      - TeamMarkdownTask: provides the team as Markdown.
      - ConvertPitchToMarkdownTask: provides the pitch as Markdown.
      - ExpertReviewTask: provides the expert criticism as Markdown.
      - WBSProjectLevel1AndLevel2AndLevel3Task: provides the table csv file.
      - ReviewPlanTask: provides the reviewed plan as Markdown.
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def output(self):
        return {
            'raw': luigi.LocalTarget(str(self.file_path(FilenameEnum.EXECUTIVE_SUMMARY_RAW))),
            'markdown': luigi.LocalTarget(str(self.file_path(FilenameEnum.EXECUTIVE_SUMMARY_MARKDOWN)))
        }
    
    def requires(self):
        return {
            'consolidate_assumptions_markdown': ConsolidateAssumptionsMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'swot_analysis': SWOTAnalysisTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'team_markdown': TeamMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'pitch_markdown': ConvertPitchToMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'expert_review': ExpertReviewTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'wbs_project123': WBSProjectLevel1AndLevel2AndLevel3Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'review_plan': ReviewPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }
    
    def run(self):
        # Read inputs from required tasks.
        with self.input()['consolidate_assumptions_markdown']['short'].open("r") as f:
            assumptions_markdown = f.read()
        with self.input()['project_plan']['markdown'].open("r") as f:
            project_plan_markdown = f.read()
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

        # Build the query.
        query = (
            f"File 'assumptions.md':\n{assumptions_markdown}\n\n"
            f"File 'project-plan.md':\n{project_plan_markdown}\n\n"
            f"File 'swot-analysis.md':\n{swot_analysis_markdown}\n\n"
            f"File 'team.md':\n{team_markdown}\n\n"
            f"File 'pitch.md':\n{pitch_markdown}\n\n"
            f"File 'expert-review.md':\n{expert_review}\n\n"
            f"File 'work-breakdown-structure.csv':\n{wbs_project_csv}\n\n"
            f"File 'review-plan.md':\n{review_plan_markdown}"
        )

        llm = get_llm(self.llm_model)

        # Create the executive summary.
        executive_summary = ExecutiveSummary.execute(llm, query)

        # Save the results.
        json_path = self.output()['raw'].path
        executive_summary.save_raw(json_path)
        markdown_path = self.output()['markdown'].path
        executive_summary.save_markdown(markdown_path)

        logger.info("Created executive summary.")


class ReportTask(PlanTask):
    """
    Generate a report html document.
    
    It depends on:
      - SWOTAnalysisTask: provides the SWOT analysis as Markdown.
      - ConvertPitchToMarkdownTask: provides the pitch as Markdown.
      - WBSProjectLevel1AndLevel2AndLevel3Task: provides the table csv file.
      - ExpertReviewTask: provides the expert criticism as Markdown.
      - ProjectPlanTask: provides the project plan as Markdown.
      - ReviewPlanTask: provides the reviewed plan as Markdown.
      - ExecutiveSummaryTask: provides the executive summary as Markdown.
    """
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def output(self):
        return luigi.LocalTarget(str(self.file_path(FilenameEnum.REPORT)))
    
    def requires(self):
        return {
            'consolidate_assumptions_markdown': ConsolidateAssumptionsMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'team_markdown': TeamMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'swot_analysis': SWOTAnalysisTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'pitch_markdown': ConvertPitchToMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'wbs_project123': WBSProjectLevel1AndLevel2AndLevel3Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'expert_review': ExpertReviewTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'review_plan': ReviewPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'executive_summary': ExecutiveSummaryTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model)
        }
    
    def run(self):
        rg = ReportGenerator()
        rg.append_markdown('Executive Summary', self.input()['executive_summary']['markdown'].path)
        rg.append_markdown('Pitch', self.input()['pitch_markdown']['markdown'].path)
        rg.append_markdown('Project Plan', self.input()['project_plan']['markdown'].path)
        rg.append_markdown('Assumptions', self.input()['consolidate_assumptions_markdown']['full'].path)
        rg.append_markdown('SWOT Analysis', self.input()['swot_analysis']['markdown'].path)
        rg.append_markdown('Team', self.input()['team_markdown'].path)
        rg.append_markdown('Expert Criticism', self.input()['expert_review'].path)
        rg.append_csv('Work Breakdown Structure', self.input()['wbs_project123']['csv'].path)
        rg.append_markdown('Review Plan', self.input()['review_plan']['markdown'].path)
        rg.save_report(self.output().path)

class FullPlanPipeline(PlanTask):
    llm_model = luigi.Parameter(default=DEFAULT_LLM_MODEL)

    def requires(self):
        return {
            'setup': SetupTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail),
            'plan_type': PlanTypeTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'physical_locations': PhysicalLocationsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'currency_strategy': CurrencyStrategyTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'identify_risks': IdentifyRisksTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'make_assumptions': MakeAssumptionsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'assumptions': DistillAssumptionsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'review_assumptions': ReviewAssumptionsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'consolidate_assumptions_markdown': ConsolidateAssumptionsMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'pre_project_assessment': PreProjectAssessmentTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'project_plan': ProjectPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'find_team_members': FindTeamMembersTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'enrich_team_members_with_contract_type': EnrichTeamMembersWithContractTypeTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'enrich_team_members_with_background_story': EnrichTeamMembersWithBackgroundStoryTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'enrich_team_members_with_environment_info': EnrichTeamMembersWithEnvironmentInfoTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'review_team': ReviewTeamTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'team_markdown': TeamMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'swot_analysis': SWOTAnalysisTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'expert_review': ExpertReviewTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'wbs_level1': CreateWBSLevel1Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'wbs_level2': CreateWBSLevel2Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'wbs_project12': WBSProjectLevel1AndLevel2Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'pitch_raw': CreatePitchTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'pitch_markdown': ConvertPitchToMarkdownTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'dependencies': IdentifyTaskDependenciesTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'durations': EstimateTaskDurationsTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'wbs_level3': CreateWBSLevel3Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'wbs_project123': WBSProjectLevel1AndLevel2AndLevel3Task(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'plan_evaluator': ReviewPlanTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'executive_summary': ExecutiveSummaryTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
            'report': ReportTask(run_id=self.run_id, speedvsdetail=self.speedvsdetail, llm_model=self.llm_model),
        }

    def output(self):
        return luigi.LocalTarget(str(self.file_path(FilenameEnum.PIPELINE_COMPLETE)))

    def run(self):
        with self.output().open("w") as f:
            f.write("Full pipeline executed successfully.\n")


if __name__ == '__main__':
    import colorlog
    import sys
    import os

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # specify a hardcoded, and it will resume work on that directory
    # run_id = "20250205_141025"

    # if env contains "RUN_ID" then use that as the run_id
    if "RUN_ID" in os.environ:
        run_id = os.environ["RUN_ID"]

    run_dir = os.path.join("run", run_id)
    os.makedirs(run_dir, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

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
    log_file = os.path.join(run_dir, "log.txt")
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    logger.info(f"run_id: {run_id}")

    # Example logging messages
    if False:
        logger.debug("This is a debug message.")
        logger.info("This is an info message.")
        logger.warning("This is a warning message.")
        logger.error("This is an error message.")
        logger.critical("This is a critical message.")

    model = DEFAULT_LLM_MODEL # works
    model = "openrouter-paid-gemini-2.0-flash-001" # works
    # model = "openrouter-paid-openai-gpt-4o-mini" # often fails, I think it's not good at structured output

    if "LLM_MODEL" in os.environ:
        model = os.environ["LLM_MODEL"]

    logger.info(f"LLM model: {model}")

    speedvsdetail = SpeedVsDetailEnum.ALL_DETAILS_BUT_SLOW
    if "SPEED_VS_DETAIL" in os.environ:
        speedvsdetail_value = os.environ["SPEED_VS_DETAIL"]
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

    task = FullPlanPipeline(speedvsdetail=speedvsdetail, llm_model=model)
    if run_id is not None:
        task.run_id = run_id

    # logger.info("Environment variables Luigi:\n" + get_env_as_string() + "\n\n\n")

    luigi.build([task], local_scheduler=True, workers=1)
