"""
Go through a checklist, to determine if there are problems with the plan.

The Primary Reader (The "Go/No-Go" Decision-Maker): This is a senior executive, a project sponsor, or even a political figure (like a Chief of Staff) who commissioned this report.

    Value: This section is the most valuable part of the entire report for this reader. They may not have the time or expertise to read the full 100+ page plan. This checklist provides an immediate, at-a-glance diagnostic. The overwhelming number of 🛑 High risk items sends an unambiguous message: "This plan, in its current form, is fundamentally non-viable and dangerous." It's a powerful visual tool for communicating extreme risk without needing to parse complex paragraphs.

The Secondary Reader (The Project Manager/Lead): This is the person tasked with potentially fixing the plan.

    Value: It serves as a prioritized "fix-it" list. It tells the project manager which fires are the biggest. They don't need to worry about the team size (a ⚠️ Medium risk) if the entire project is a 🛑 High "Legal Minefield." It focuses their attention on the foundational, existential threats to the project's success.

PROMPT> python -u -m planexe.viability.checklist | tee output.txt
"""
import json
import logging
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass
from llama_index.core.llms.llm import LLM
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from planexe.llm_util.llm_executor import LLMExecutor, PipelineStopRequested

logger = logging.getLogger(__name__)

class ChecklistAnswer(BaseModel):
    id: str = Field(
        description="Id of this checklist item."
    )
    level: str = Field(
        description="low, medium, high."
    )
    justification: str = Field(
        description="Why this level and not another level. 30 words."
    )
    mitigation: str = Field(
        description="One concrete action that reduces/removes the flag. 30 words."
    )

class ChecklistResponse(BaseModel):
    checklist_answers: list[ChecklistAnswer] = Field(
        description="Answers to the checklist items."
    )

class ChecklistAnswerCleaned(BaseModel):
    id: str = Field(
        description="Id of this checklist item."
    )
    index: int = Field(
        description="Index of this checklist item."
    )
    title: str = Field(
        description="Title of this checklist item."
    )
    subtitle: str = Field(
        description="Subtitle of this checklist item."
    )
    level: str = Field(
        description="low, medium, high."
    )
    justification: str = Field(
        description="Why this level and not another level. 30 words."
    )
    mitigation: str = Field(
        description="One concrete action that reduces/removes the flag. 30 words."
    )

CHECKLIST = [
    {
        "index": 1,
        "title": "Violates Known Physics",
        "subtitle": "The project cannot succeed without a major, unpredictable discovery in fundamental science.",
        "instruction": "Evaluate if the plan violates physics (e.g., FTL). If no violations are found and the plan relies on known engineering, set level to 'low' and justify this.",
        "comment": "If the initial prompt is vague/scifi/aggressive or asks for something that is physically impossible, then the generated plan usually end up with some fantasy parts, making the plan unrealistic."
    },
    {
        "index": 2,
        "title": "No Real-World Proof",
        "subtitle": "Success depends on a technology or system that has not been proven in real projects at this scale or in this domain.",
        "instruction": "No Real-World Proof: Is there credible, real-world evidence that the core mechanism works outside of a lab/demo? If this is a first-of-its-kind or unregulated/novel construct, set level to 'high'. In the justification, cite the exact areas with no precedent (markets, technology, policy) rather than saying 'insufficient information'. In the mitigation, propose a parallel, multi‑track validation that includes: (T1) technical threat‑model + security PoC with red‑team; (T2) legal/compliance review for the relevant domains (e.g., securities/market integrity/AML/data protection) and licensing feasibility; (T3) market validation (letters of intent, regulator pre‑reads, partner commitments); (T4) ethics/abuse analysis (manipulation/foreign‑influence/dual‑use). Define explicit go/no‑go gates and realistic timeframes; declare NO‑GO if any track blocks.",
        "comment": "It's rarely smooth sailing when using new technology, novel concepts that no human has ever been used before. PlanExe sometimes picking a scenario that is way too ambitious."
    },
    {
        "index": 3,
        "title": "Buzzwords",
        "subtitle": "Does the plan use excessive buzzwords without evidence of knowledge.",
        "instruction": "Buzzwords: Does the plan use excessive buzzwords without evidence of knowledge.",
        "comment": "PlanExe often ends up using buzzwords such as blockchain, DAO, VR, AR, and expects that one person without developer background can implement the plan."
    },
    {
        "index": 4,
        "title": "Underestimating Risks",
        "subtitle": "Does this plan grossly underestimate risks.",
        "instruction": "Perform a risk gap analysis. Compare the risks explicitly mentioned in the plan's risk assessment against the risks implied by the project's core activities (e.g., high-impact, controversial actions). Set LEVEL to HIGH if the plan ignores or significantly downplays 'showstopper' risks (e.g., public outrage, political backlash, insurmountable barriers). Justify by naming a critical, unaddressed risk.",
        "comment": "Despite PlanExe trying to uncover many risks, there are often risks that are not identified, or some significant risk gets neglected."
    },
    {
        "index": 5,
        "title": "Timeline Issues",
        "subtitle": "Does this plan have unrealistic timelines.",
        "instruction": "Timeline Issues: Does this plan have unrealistic timelines. Can it be parallelized to be done in a shorter timeframe.",
        "comment": "PlanExe currently has no knowledge about the resources available. In the first draft of the plan makes no attempt at parallelizing the tasks to be done in a shorter timeframe. I imagine a human will have to configure the resources, before rescheduling the tasks to be done in a shorter timeframe."
    },
    {
        "index": 6,
        "title": "Money Issues",
        "subtitle": "Flaws in the money calculations.",
        "instruction": "Assess the financial strategy's viability. First, evaluate the core revenue or funding model: is it based on proven methods or highly speculative concepts (e.g., unproven monetization schemes, first-of-its-kind financial instruments)? Second, check for major internal inconsistencies between stated budget, revenue/funding projections, and operational costs. Set LEVEL to HIGH if the model is unproven/high-risk OR if there are clear contradictions in the financial data. Justify by citing the specific model or inconsistency.",
        "comment": "PlanExe currently has no Cost Breakdown Structure. Some projects are intended to generate revenue, other projects are not intended for profit, but for a specific purpose. Yet, there can be significant money issues that are not identified."
    },
    {
        "index": 7,
        "title": "Budget Too Low",
        "subtitle": "Is there a significant mismatch between the project's stated goals and the financial resources allocated, suggesting an unrealistic or inadequate budget.",
        "instruction": "Budget Too Low: Is there a significant mismatch between the project's stated goals and the financial resources allocated, suggesting an unrealistic or inadequate budget.",
        "comment": "Often the user specifies a 100 USD budget in the initial prompt, where the generated plan requires millions of dollars to implement. Or the budget grows during the plan generation, so the money needed ends up being much higher than expected."
    },
    {
        "index": 8,
        "title": "Overly Optimistic Projections",
        "subtitle": "Does this plan grossly overestimate the likelihood of success, while neglecting potential setbacks, buffers, or contingency plans.",
        "instruction": "Overly Optimistic Projections: Does this plan grossly overestimate the likelihood of success, while neglecting potential setbacks, buffers, or contingency plans.",
        "comment": "The generated plan describes a sunshine scenario that is likely to go wrong, without any buffers or contingency plans."
    },
    {
        "index": 9,
        "title": "Lacks Technical Depth",
        "subtitle": "Does the plan omit critical technical details or engineering steps required to overcome foreseeable challenges, especially for complex components of the project.",
        "instruction": "Act as a technical due-diligence checker. Evaluate technical completeness and assign LEVEL.\n\nSteps:\n1) Identify critical technical challenges (cover the full critical path; don’t cap at 3).\n2) Scrutinize the HOW: look for concrete methods, calculations, materials/tolerances, data specs, algorithms, logistics/method statements.\n3) Evidence quality: require reviewable artifacts—architecture + interfaces, BOM, capacity/performance budgets, safety/compliance plan, security/threat model, test & validation plan (incl. acceptance criteria), and TRL/prototype plan.\n4) Flag “magic box” claims (e.g., “AI will optimize X”) that lack inputs/outputs/assumptions.\n\nSet LEVEL:\n- LOW: All critical challenges have specific artifacts above; a competent engineer could estimate cost/schedule with only minor clarifications.\n- MEDIUM: One or more critical subsystems are underspecified OR artifacts exist but lack key specifics (interfaces, budgets, tests), creating estimation risk.\n- HIGH: Novel/critical components lack core artifacts (architecture/interfaces, safety/compliance, test/validation) or rely on “magic box” claims—credible cost/schedule or execution planning is not possible.",
        "comment": "Some plans involves serious engineering, but the generated plan is missing the technical details that explain how to overcome the technical challenges. Nailing the technical details is crucial."
    },
    {
        "index": 10,
        "title": "Assertions Without Evidence",
        "subtitle": "Exclude timeline & budget. Find one hard proof for a critical claim.",
        "instruction": "Scope: Exclude timeline and budget (handled elsewhere). Evaluate existential assertions about: legality/permits; stakeholder/partner commitment; safety/security/compliance effectiveness; technical feasibility of the core approach; and operational capacity to deliver/run. Action: Identify the single most impactful assertion in scope and look for one verifiable evidence item in the plan (e.g., statutory/regulatory citation or formal opinion; signed LOI/MOU; independent test/inspection/validation report; prototype/PoC results or expert review; accredited certification or prior deployment). If none is found, flag it. Scoring: High—no verifiable evidence or only hand-waving; Medium—evidence exists but is weak/unverifiable or contradicts the plan; Low—one clear, checkable item exists. Output: Justification ≤2 sentences naming the assertion and where evidence was/wasn’t found. Mitigation 1 sentence naming the single next proof step (e.g., obtain formal opinion; secure written commitment; deliver independent test/validation).",
        "comment": "Often the generated plan specifies numbers/facts/concepts without any evidence to support the claims. These will have to be fact checked and adjusted in a refinement of the plan."
    },
    {
        "index": 11,
        "title": "Unclear Deliverables",
        "subtitle": "Are the project's final outputs or key milestones poorly defined, lacking specific criteria for completion, making success difficult to measure objectively.",
        "instruction": "Unclear Deliverables: Are success criteria and acceptance tests defined for the key work‑packages, not just the end artifact? If deliverables are vague, set level to 'medium' and in the justification identify the specific missing definitions (e.g., permits/process milestones, security acceptance tests, construction logistics plan, commissioning/operational readiness, stakeholder approvals). In the mitigation, require a Deliverables & Acceptance spec with SMART criteria and a 'Definition of Done' per work‑package, each tied to dated milestones and go/no‑go tripwires.",
        "comment": "Some projects involves many components, without a clear specification of each component."
    },
    {
        "index": 12,
        "title": "Overengineered Plan",
        "subtitle": "Is the proposed solution disproportionately complex or resource-intensive relative to the problem it aims to solve, suggesting over-engineering.",
        "instruction": "Overengineered Plan: Is the proposed solution disproportionately complex or resource-intensive relative to the problem it aims to solve, suggesting over-engineering.",
        "comment": "For a 'Make me a cup of coffee' prompt, then the generated plan is overkill and involves lots of people and resources."
    },
    {
        "index": 13,
        "title": "Underestimate Team Size",
        "subtitle": "Does the plan underestimate the number of people needed to achieve the goals.",
        "instruction": "Underestimate Team Size: Does the plan underestimate the number of people needed to achieve the goals.",
        "comment": "For a 'Construct a bridge' prompt, then the generated plan is likely to underestimate the number of people needed to achieve the goals."
    },
    {
        "index": 14,
        "title": "Overestimate Team Size",
        "subtitle": "Does the plan overestimate the number of people needed to achieve the goals.",
        "instruction": "Overestimate Team Size: Does the plan overestimate the number of people needed to achieve the goals.",
        "comment": "For a 'Im a solo entrepreneur and is making everything myself' prompt, then the generated plan is likely suggesting to hire a huge team of people, and ignoring the fact that the entrepreneur is doing everything themselves."
    },
    {
        "index": 15,
        "title": "Legal Minefield",
        "subtitle": "Does the plan involve activities with high legal, regulatory, or ethical exposure, such as potential lawsuits, corruption, illegal actions, or societal harm.",
        "instruction": "Legal Minefield: Does the plan trigger multiple overlapping jurisdictions or regimes with low probability of approval and high litigation risk (e.g., environmental impact, land use/zoning, sector‑specific licensing, securities/market integrity, data protection, export controls, financial crime/AML, public safety)? If so, set level to 'high'. In the justification, reference the specific regimes/laws/processes implicated (by name where possible) and explain why approval is unlikely. In the mitigation, propose a legal feasibility & pathway study (12–16 weeks) that delivers: (1) a statute/regulation matrix; (2) regulatory process maps (e.g., impact assessment steps and required agency consultations); (3) preliminary regulator/agency readouts; (4) case analogs; (5) a permit/approval probability model with confidence intervals; (6) litigation exposure; and (7) alternatives analysis. Include explicit go/no‑go gates (e.g., NO‑GO if approval probability <10% or an agency indicates no plausible path).",
        "comment": "Sometimes the generated plan describes a sunshine scenario where everything goes smoothly, without any lawyers or legal issues."
    },
    {
        "index": 16,
        "title": "Infeasible Constraints",
        "subtitle": "Does the project depend on overcoming constraints that are practically insurmountable, such as obtaining permits that are almost certain to be denied.",
        "instruction": "Infeasible Constraints: Does the project depend on overcoming constraints that are practically insurmountable, such as obtaining permits that are almost certain to be denied.",
        "comment": "Getting a permit to build a spaceship launch pad in the center of the city is likely going to be rejected."
    },
    {
        "index": 17,
        "title": "Uncategorized Red Flags",
        "subtitle": "Are there any other significant risks or major issues that are not covered by other items in this checklist but still threaten the project's viability.",
        "instruction": "Uncategorized Red Flags: Are there any other significant risks or major issues that are not covered by other items in this checklist but still threaten the project's viability.",
        "comment": "This checklist is not exhaustive. Besides what is listed in this checklist, there are other red flags that are not accounted for in this checklist."
    }
]

def enrich_checklist_with_batch_id_and_item_index(checklist: list[dict], batch_size: int = 5) -> list[dict]:
    enriched_checklist: list[dict] = []
    for i, item in enumerate(checklist):
        batch_id = i // batch_size
        item_index = i % batch_size
        id = f"batch={batch_id}&item={item_index}"
        item_enriched = {"id": id, "batch_index": batch_id, **item}
        enriched_checklist.append(item_enriched)
    return enriched_checklist

def format_system_prompt(*, checklist: list[dict], batch_size: int = 5, current_batch_index: int = 0) -> str:
    number_of_batches = len(checklist) // batch_size
    remainder = len(checklist) % batch_size
    if remainder > 0:
        number_of_batches += 1

    enriched_checklist = enrich_checklist_with_batch_id_and_item_index(checklist, batch_size)

    # remove the "comment" key from each item in the enriched_checklist
    enriched_checklist = [{k: v for k, v in item.items() if k != "comment"} for item in enriched_checklist]
    enriched_checklist = [{k: v for k, v in item.items() if k != "title"} for item in enriched_checklist]
    enriched_checklist = [{k: v for k, v in item.items() if k != "subtitle"} for item in enriched_checklist]

    # assign status=TODO to the items that have batch_index == current_batch_index
    for item in enriched_checklist:
        batch_index = item["batch_index"]
        if batch_index == current_batch_index:
            item["status"] = "TODO"
        else:
            item["status"] = "IGNORE"

    checklist_answers: list[ChecklistAnswer] = []
    for item in enriched_checklist:
        if item["batch_index"] != current_batch_index:
            continue
        checklist_answer = ChecklistAnswer(
            id=item["id"],
            level="LEVEL_PLACEHOLDER",
            justification="JUSTIFICATION_PLACEHOLDER",
            mitigation="MITIGATION_PLACEHOLDER",
        )
        checklist_answers.append(checklist_answer)
    checklist_response = ChecklistResponse(
        checklist_answers=checklist_answers,
    )
    json_response_skeleton: str = json.dumps(checklist_response.model_dump(), indent=2)
    # print(f"json_response_skeleton: {json_response_skeleton}")
    # exit(0)

    # remove the "index" key from each item in the enriched_checklist
    enriched_checklist = [{k: v for k, v in item.items() if k != "index"} for item in enriched_checklist]
    # remove the "batch_index" key from each item in the enriched_checklist
    enriched_checklist = [{k: v for k, v in item.items() if k != "batch_index"} for item in enriched_checklist]

    json_enriched_checklist = json.dumps(enriched_checklist, indent=2)
    # print(f"Enriched checklist: {json_enriched_checklist}")
    # exit(0)

    expected_ids = [item["id"] for item in enriched_checklist if item["status"] == "TODO"]
    json_expected_ids = json.dumps(expected_ids, indent=2)

    system_prompt = f"""
You are an expert strategic analyst. Your task is to answer a checklist with red flags.
You will output only valid JSON. No explanations, no chit-chat, no Markdown, no code fences.

GOAL
Return exactly one object per checklist item with keys in this order: id, level, justification, mitigation.

STRICT RULES
- Output must be a single JSON array, same length and order as the expected ids.
- Answer only for checklist entries whose status is "TODO"; treat "IGNORE" items as read-only context and never output them.
- Copy id from input unchanged; never invent, drop, or reorder ids.
- If you output any id that is not listed in the expected ids, you fail the task; do not add or duplicate ids.
- Keep only these keys and preserve this exact key order.
- Use standard JSON with double quotes for keys and string values. No trailing commas. No comments. No nulls.
- level must be one of: "low", "medium", "high".
- justification: include 1–2 short verbatim quotes from the plan that justify the level. As the only exception, if a red flag is absent, state that no evidence was found and briefly explain why the level is 'low'.
- justification must quote only from the plan text; never quote or paraphrase the checklist instructions or inject examples that are not present in the plan.
- Only conclude "insufficient information" when the plan truly lacks relevant content; do not default to this if ordinary, real-world activities are described.
- If no supporting quote exists, set justification to exactly "insufficient information" (lowercase) and do not add any other words.
- If justification is "insufficient information", you must set level to either "medium" or "high".
- mitigation: ONE assignable task. Start with a suggested role/team, followed by a verb, and include a suggested timeframe (e.g., "Legal Team: Draft a memo... within 30 days."). ~30 words.
- mitigation must be actionable; never respond with "N/A" or similar placeholders.
- Mitigation must be specific to the identified issue; avoid vague directives like "review the plan", "consult experts", or "investigate" unless paired with a concrete deliverable that directly reduces the flagged risk.
- If the level is "low", mitigation should reinforce existing good practice (e.g., document evidence, schedule routine monitoring) rather than delegating a broad re-check of the entire plan.
- If information is genuinely missing, set justification to "insufficient information", choose level "medium" or "high", and craft mitigation that acquires the missing evidence.

INPUTS (do not echo them back; use them to produce the output):
status legend:
- "TODO": must answer.
- "IGNORE": ignore completely; never include in output.
Expected ids (order to follow):
{json_expected_ids}

Checklist to evaluate:
{json_enriched_checklist}

RETURN THIS EXACT SHAPE (fill in the values; keep ids as-is; do not alter structure, punctuation, or key order):
{json_response_skeleton}
"""
    # print(f"System prompt:\n{system_prompt}")
    # exit(0)
    return system_prompt

BATCH_SIZE = 5

@dataclass
class ViabilityChecklist:
    system_prompt_list: list[str]
    user_prompt_list: list[str]
    responses: list[ChecklistResponse]
    measurements: list[ChecklistAnswerCleaned]
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, user_prompt: str) -> 'ViabilityChecklist':
        if not isinstance(llm_executor, LLMExecutor):
            raise ValueError("Invalid LLMExecutor instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        
        number_of_groups = len(CHECKLIST) // BATCH_SIZE
        remainder = len(CHECKLIST) % BATCH_SIZE
        if remainder > 0:
            number_of_groups += 1

        system_prompt_list = []
        for group_index in range(0, number_of_groups):
            system_prompt = format_system_prompt(checklist=CHECKLIST, batch_size=BATCH_SIZE, current_batch_index=group_index)
            system_prompt_list.append(system_prompt)

        enriched_checklist = enrich_checklist_with_batch_id_and_item_index(CHECKLIST, BATCH_SIZE)
        expected_ids_list = []
        for group_index in range(0, number_of_groups):
            ids_for_this_group = [item["id"] for item in enriched_checklist if item["batch_index"] == group_index]
            expected_ids_list.append(ids_for_this_group)
        # print(f"Expected ids list: {expected_ids_list}")
        # exit(0)

        responses: list[ChecklistResponse] = []
        metadata_list: list[dict] = []
        user_prompt_list = []
        for group_index in range(0, number_of_groups):
            logger.info(f"Processing group {group_index+1} of {number_of_groups}")
            system_prompt = system_prompt_list[group_index]
            expected_ids = expected_ids_list[group_index]

            # Add previous checklist responses to the bottom of the user prompt
            if group_index > 0:
                checklist_answers_raw: list[ChecklistAnswer] = []
                for response in responses:
                    checklist_answers_raw.extend(response.checklist_answers)
                previous_responses_dict = [answer.model_dump() for answer in checklist_answers_raw]
                previous_responses_str = json.dumps(previous_responses_dict, indent=2)
                user_prompt_with_previous_responses = f"{user_prompt}\n\n# Checklist Answers\n{previous_responses_str}"
            else:
                user_prompt_with_previous_responses = user_prompt

            user_prompt_list.append(user_prompt_with_previous_responses)

            chat_message_list = [
                ChatMessage(
                    role=MessageRole.SYSTEM,
                    content=system_prompt,
                ),
                ChatMessage(
                    role=MessageRole.USER,
                    content=user_prompt_with_previous_responses,
                )
            ]

            def execute_function(llm: LLM) -> dict:
                sllm = llm.as_structured_llm(ChecklistResponse)
                chat_response = sllm.chat(chat_message_list)

                # Ensure that all the checklist items for this batch have been answered just once.
                # Sometimes the LLM answers the checklist in a different order. This is ok.
                # Sometimes the LLM answers the same checklist item multiple times. This is not ok.
                # Sometimes the LLM answers all the checklist items, ignoring the small batch it was supposed to answer, so the response is huge. This is not ok.
                response_ids: list[str] = [answer.id for answer in chat_response.raw.checklist_answers]

                response_ids_set = set[str](response_ids)
                expected_ids_set = set[str](expected_ids)
                if response_ids_set != expected_ids_set or len(response_ids_set) != len(expected_ids_set):
                    diff = expected_ids_set - response_ids_set
                    sorted_diff = sorted(diff)
                    raise ValueError(f"Mismatch between expected and response ids. Expected ids: {expected_ids!r} but got response ids: {response_ids!r}. Group index: {group_index}. Missing ids: {sorted_diff!r}")

                metadata = dict(llm.metadata)
                metadata["llm_classname"] = llm.class_name()
                return {
                    "chat_response": chat_response,
                    "metadata": metadata
                }

            try:
                result = llm_executor.run(execute_function)
            except PipelineStopRequested:
                # Re-raise PipelineStopRequested without wrapping it
                raise
            except Exception as e:
                logger.debug(f"LLM chat interaction failed: {e}")
                logger.error("LLM chat interaction failed.", exc_info=True)
                raise ValueError("LLM chat interaction failed.") from e
            
            chat_message_list.append(
                ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=result["chat_response"].raw.model_dump(),
                )
            )

            logger.debug(f"Chat response: {result['chat_response'].raw.model_dump()}")
            responses.append(result["chat_response"].raw)
            metadata_list.append(result["metadata"])

        # from the raw_responses, extract the measurements into a flatten list
        checklist_answers_raw: list[ChecklistAnswer] = []
        for response in responses:
            checklist_answers_raw.extend(response.checklist_answers)

        # convert CHECKLIST from list to dict, using the index as the key
        checklist_dict = {item["id"]: item for item in enriched_checklist}
        if len(checklist_dict) != len(CHECKLIST):
            raise ValueError("Checklist dict length does not match checklist list length.")

        # Clean the raw measurements
        measurements_cleaned: list[ChecklistAnswerCleaned] = []
        for measurement in checklist_answers_raw:
            checklist_id = measurement.id
            checklist_item = checklist_dict.get(checklist_id)
            if checklist_item is None:
                raise ValueError(f"Checklist item not found for id: {checklist_id}")
            checklist_item_index = checklist_item["index"]
            checklist_item_title = checklist_item["title"]
            checklist_item_subtitle = checklist_item["subtitle"]
            measurement_cleaned = ChecklistAnswerCleaned(
                id=checklist_id,
                index=checklist_item_index,
                title=checklist_item_title,
                subtitle=checklist_item_subtitle,
                level=measurement.level,
                justification=measurement.justification,
                mitigation=measurement.mitigation,
            )
            measurements_cleaned.append(measurement_cleaned)
        
        # Sort checklist answers by index, in case the LLM answers the checklist items in a different order.
        measurements_cleaned.sort(key=lambda x: x.index)

        metadata = {}
        for metadata_index, metadata_item in enumerate(metadata_list, start=1):
            metadata[f"metadata_{metadata_index}"] = metadata_item

        markdown = cls.convert_to_markdown(measurements_cleaned)

        result = ViabilityChecklist(
            system_prompt_list=system_prompt_list,
            user_prompt_list=user_prompt_list,
            responses=responses,
            measurements=measurements_cleaned,
            metadata=metadata,
            markdown=markdown,
        )
        return result    

    def to_dict(self, include_responses=True, include_cleaned_measurments=True, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = {}
        if include_responses:
            d["responses"] = [response.model_dump() for response in self.responses]
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt_list'] = self.system_prompt_list
        if include_user_prompt:
            d['user_prompt_list'] = self.user_prompt_list
        if include_cleaned_measurments:
            d['measurements'] = [measurement.model_dump() for measurement in self.measurements]
        return d

    def save_raw(self, file_path: str) -> None:
        Path(file_path).write_text(json.dumps(self.to_dict(), indent=2))

    def measurement_item_list(self) -> list[dict]:
        """
        Return a list of dictionaries, each representing a measurement.
        """
        return [measurement.model_dump() for measurement in self.measurements]
    
    def save_clean(self, file_path: str) -> None:
        measurements_dict = self.measurement_item_list()
        Path(file_path).write_text(json.dumps(measurements_dict, indent=2))

    @staticmethod
    def convert_to_markdown(checklist_answers: list[ChecklistAnswerCleaned]) -> str:
        """
        Convert the raw checklist answers to markdown.
        """
        level_map = {
            "low": "✅ Low",
            "medium": "⚠️ Medium",
            "high": "🛑 High",
        }
        rows = []

        # Histogram
        num_low = sum(1 for item in checklist_answers if item.level == "low")
        num_medium = sum(1 for item in checklist_answers if item.level == "medium")
        num_high = sum(1 for item in checklist_answers if item.level == "high")

        rows.append("### Summary\n")
        rows.append("| Level | Count |")
        rows.append("|---|---|")
        rows.append(f"| {level_map['low']} | {num_low} |")
        rows.append(f"| {level_map['medium']} | {num_medium} |")
        rows.append(f"| {level_map['high']} | {num_high} |")

        rows.append("\n\n## Checklist\n")
        for index, item in enumerate(checklist_answers):
            if index > 0:
                rows.append("\n")
            rows.append(f"## {index+1}. {item.title}\n")
            rows.append(f"*{item.subtitle}*\n")
            level_description = level_map.get(item.level, "Unknown level")
            rows.append(f"**Level**: {level_description}\n")
            rows.append(f"**Justification**: {item.justification}\n")
            rows.append(f"**Mitigation**: {item.mitigation}")
        return "\n".join(rows)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(self.markdown)

if __name__ == "__main__":
    from planexe.llm_util.llm_executor import LLMModelFromName
    from planexe.prompt.prompt_catalog import PromptCatalog

    # logging.basicConfig(level=logging.DEBUG)

    prompt_catalog = PromptCatalog()
    prompt_catalog.load_simple_plan_prompts()

    prompt_id = "b9afce6c-f98d-4e9d-8525-267a9d153b51"
    # prompt_id = "a6bef08b-c768-4616-bc28-7503244eff02"
    # prompt_id = "19dc0718-3df7-48e3-b06d-e2c664ecc07d"
    # prompt_id = "e42eafce-5c8c-4801-b9f1-b8b2a402cd78"
    prompt_item = prompt_catalog.find(prompt_id)
    if not prompt_item:
        raise ValueError("Prompt item not found.")
    query = prompt_item.prompt

    model_names = [
        "ollama-llama3.1",
        # "openrouter-paid-gemini-2.0-flash-001",
        # "openrouter-paid-qwen3-30b-a3b"
    ]
    llm_models = LLMModelFromName.from_names(model_names)
    llm_executor = LLMExecutor(llm_models=llm_models)

    print(f"Query: {query}")
    result = ViabilityChecklist.execute(llm_executor, query)

    print("\nResult:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))

    test_data_filename = f"viability_checklist_{prompt_id}.json"
    result.save_clean(Path(test_data_filename))
    print(f"Test data saved to: {test_data_filename!r}")

    markdown_filename = f"viability_checklist_{prompt_id}.md"
    result.save_markdown(Path(markdown_filename))
    print(f"Markdown saved to: {markdown_filename!r}")