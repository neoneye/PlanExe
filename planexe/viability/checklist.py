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
    level: str = Field(
        description="low, medium, high."
    )
    justification: str = Field(
        description="Why this level and not another level. 30 words."
    )
    mitigation: str = Field(
        description="One concrete action that reduces/removes the flag. 30 words."
    )

class ChecklistAnswerCleaned(BaseModel):
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

ALL_CHECKLIST_ITEMS = [
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
        "title": "Lacks Operational Sustainability",
        "subtitle": "Even if the project is successfully completed, can it be sustained, maintained, and operated effectively over the long term without ongoing issues.",
        "instruction": "Lacks Operational Sustainability: Assess whether the project can be sustained post-completion. Evaluate: (1) Ongoing operational costs vs. available funding/revenue—is there a sustainable business model? (2) Maintenance requirements—are specialized skills, parts, or vendors needed that may not be available long-term? (3) Scalability—can the system handle growth or changing conditions? (4) Personnel dependency—does operation depend on specific individuals who may leave? (5) Technology obsolescence—will critical technology become unsupported or obsolete? (6) Environmental/social impact—can negative impacts be managed long-term? Set LEVEL to HIGH if: operational costs exceed sustainable funding, maintenance requires unavailable resources, or the system cannot adapt to changing conditions. Set LEVEL to MEDIUM if: sustainability concerns exist but can be addressed with planning. Set LEVEL to LOW if: a clear, sustainable operational model exists with adequate resources. In the justification, identify the specific sustainability gap (funding, maintenance, scalability, etc.). In the mitigation, propose an operational sustainability plan including: funding/resource strategy, maintenance schedule, succession planning, technology roadmap, or adaptation mechanisms.",
        "comment": "Many projects focus on completion but ignore operational sustainability. A perfectly built project can fail if it requires unsustainable funding, impossible maintenance, or cannot adapt to changing conditions. PlanExe may generate plans that work in theory but cannot be sustained in practice."
    },
    {
        "index": 17,
        "title": "Infeasible Constraints",
        "subtitle": "Does the project depend on overcoming constraints that are practically insurmountable, such as obtaining permits that are almost certain to be denied.",
        "instruction": "Infeasible Constraints: Does the project depend on overcoming constraints that are practically insurmountable, such as obtaining permits that are almost certain to be denied.",
        "comment": "Getting a permit to build a spaceship launch pad in the center of the city is likely going to be rejected."
    },
    {
        "index": 18,
        "title": "External Dependencies",
        "subtitle": "Does the project depend on critical external factors, third parties, suppliers, or vendors that may fail, delay, or be unavailable when needed.",
        "instruction": "External Dependencies: Identify all critical dependencies on external entities (vendors, suppliers, partners, third-party services, infrastructure providers, regulatory agencies, or market conditions). Evaluate the risk of each dependency: single-source suppliers, uncommitted partners, third-party services with no SLA, or infrastructure that may not be available. Set LEVEL to HIGH if the project has critical dependencies on entities that: (1) have not provided formal commitments/contracts, (2) are single-source with no alternatives, (3) have a history of delays or failures, (4) operate in unstable markets/regions, or (5) may have conflicting interests. Set LEVEL to MEDIUM if dependencies exist but have mitigations or alternatives. Set LEVEL to LOW if all critical dependencies are secured with contracts/commitments and have backup options. In the justification, name the specific dependency and why it is risky. In the mitigation, propose securing formal commitments, identifying alternatives, or establishing backup suppliers/providers.",
        "comment": "Plans often assume external parties will deliver as expected, without considering vendor lock-in, supplier failures, or partner non-commitment. Real projects can fail if a critical supplier goes out of business or a partner doesn't follow through."
    },
    {
        "index": 19,
        "title": "Stakeholder Misalignment",
        "subtitle": "Are there conflicting interests, misaligned incentives, or lack of genuine commitment from key stakeholders that could derail the project.",
        "instruction": "Stakeholder Misalignment: Map all key stakeholders (funders, partners, end users, regulators, affected communities, internal teams). Evaluate alignment: (1) Do stakeholders have conflicting goals or incentives? (2) Are stakeholders genuinely committed, or just giving lip service? (3) Do stakeholders have the authority/resources to deliver on commitments? (4) Will stakeholders remain supportive if costs increase or timelines slip? (5) Are there power imbalances or political dynamics that could sabotage the project? Set LEVEL to HIGH if: stakeholders have fundamentally conflicting interests, key stakeholders are uncommitted or have made no formal agreements, or there are political/social dynamics likely to cause opposition. Set LEVEL to MEDIUM if: some misalignment exists but can be managed through negotiation or incentives. Set LEVEL to LOW if: all stakeholders are aligned with formal agreements and shared incentives. In the justification, identify the specific stakeholder(s) and the misalignment. In the mitigation, propose stakeholder alignment workshops, formal agreements (MOUs/contracts), incentive restructuring, or conflict resolution processes.",
        "comment": "Projects can fail even with perfect technical execution if stakeholders have hidden agendas, conflicting priorities, or lose interest halfway through. PlanExe may assume stakeholders are fully supportive without verifying commitment or alignment."
    },
    {
        "index": 20,
        "title": "Uncategorized Red Flags",
        "subtitle": "Are there any other significant risks or major issues that are not covered by other items in this checklist but still threaten the project's viability.",
        "instruction": "Uncategorized Red Flags: Are there any other significant risks or major issues that are not covered by other items in this checklist but still threaten the project's viability.",
        "comment": "This checklist is not exhaustive. Besides what is listed in this checklist, there are other red flags that are not accounted for in this checklist."
    }
]

def format_system_prompt(*, checklist: list[dict], current_index: int) -> str:
    if current_index < 0 or current_index >= len(checklist):
        raise ValueError(f"Current index must be between 0 and {len(checklist)-1}. Got {current_index}.")
    
    enriched_checklist = checklist

    # remove the "comment" key from each item in the enriched_checklist
    enriched_checklist = [{k: v for k, v in item.items() if k != "comment"} for item in enriched_checklist]

    expected_index_to_be_answered = None
    instruction_to_follow = None
    for index, item in enumerate(enriched_checklist):
        if index == current_index:
            expected_index_to_be_answered = item["index"]
            instruction_to_follow = item["instruction"]
            break

    # assign status=TODO to the items that have index == current_index
    for index, item in enumerate(enriched_checklist):
        if index == current_index:
            item["status"] = "TODO"
        else:
            item["status"] = "IGNORE"

    # Older LLMs can't handle with all the long instruction text. 
    # The solution is to only show the long instruction for the current batch,
    # and show title/subtitle for the other batches, these texts are much shorter.
    for index, item in enumerate(enriched_checklist):
        if index != current_index:
            item["instruction"] = item["title"] + "\n" + item["subtitle"]

    enriched_checklist = [{k: v for k, v in item.items() if k != "title"} for item in enriched_checklist]
    enriched_checklist = [{k: v for k, v in item.items() if k != "subtitle"} for item in enriched_checklist]

    checklist_answer = ChecklistAnswer(
        level="LEVEL_PLACEHOLDER",
        justification="JUSTIFICATION_PLACEHOLDER",
        mitigation="MITIGATION_PLACEHOLDER",
    )
    json_response_skeleton: str = json.dumps(checklist_answer.model_dump(), indent=2)
    # print(f"json_response_skeleton: {json_response_skeleton}")
    # exit(0)

    # remove the "index" key from each item in the enriched_checklist
    # enriched_checklist = [{k: v for k, v in item.items() if k != "index"} for item in enriched_checklist]

    json_enriched_checklist = json.dumps(enriched_checklist, indent=2)
    # print(f"Enriched checklist: {json_enriched_checklist}")
    # exit(0)

    system_prompt = f"""
You are an expert strategic analyst. Your task is to answer a checklist with red flags.
You will output only valid JSON. No explanations, no chit-chat, no Markdown, no code fences.

GOAL
Return exactly one object per checklist item with keys in this order: level, justification, mitigation.

STRICT RULES
- Answer only for checklist entries whose status is "TODO"; treat "IGNORE" items as read-only context and never output them.
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

Expected index to answer:
{expected_index_to_be_answered}

Follow these instructions to answer the item:
{instruction_to_follow}

Checklist to evaluate:
{json_enriched_checklist}

RETURN THIS EXACT SHAPE (fill in the values):
{json_response_skeleton}
"""
    # print(f"System prompt:\n{system_prompt}")
    # exit(0)
    return system_prompt

@dataclass
class ViabilityChecklist:
    system_prompt_list: list[str]
    user_prompt_list: list[str]
    responses: dict[int, ChecklistAnswer]
    checklist_answers_cleaned: list[ChecklistAnswerCleaned]
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm_executor: LLMExecutor, user_prompt: str, max_number_of_items: Optional[int] = None) -> 'ViabilityChecklist':
        if not isinstance(llm_executor, LLMExecutor):
            raise ValueError("Invalid LLMExecutor instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        if max_number_of_items is not None and not isinstance(max_number_of_items, int):
            raise ValueError("Invalid max_number_of_items.")

        checklist_items = ALL_CHECKLIST_ITEMS
        if max_number_of_items is not None:
            checklist_items = checklist_items[:max_number_of_items]
        
        system_prompt_list = []
        for index in range(0, len(checklist_items)):
            system_prompt = format_system_prompt(checklist=checklist_items, current_index=index)
            system_prompt_list.append(system_prompt)

        responses: dict[int, ChecklistAnswer] = {}
        metadata_list: list[dict] = []
        user_prompt_list = []
        checklist_answers_cleaned: list[ChecklistAnswerCleaned] = []
        for index in range(0, len(checklist_items)):
            logger.info(f"Processing item {index+1} of {len(checklist_items)}")
            system_prompt = system_prompt_list[index]

            # Add previous checklist responses to the bottom of the user prompt
            if index > 0:
                previous_responses_dict = {k: v.model_dump() for k, v in responses.items()}
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
                sllm = llm.as_structured_llm(ChecklistAnswer)
                chat_response = sllm.chat(chat_message_list)

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

            checklist_answer: ChecklistAnswer = result["chat_response"].raw
            checklist_item = checklist_items[index]
            checklist_item_index = checklist_item["index"]
            checklist_answer_cleaned = ChecklistAnswerCleaned(
                index=checklist_item_index,
                title=checklist_item["title"],
                subtitle=checklist_item["subtitle"],
                level=checklist_answer.level,
                justification=checklist_answer.justification,
                mitigation=checklist_answer.mitigation,
            )
            checklist_answers_cleaned.append(checklist_answer_cleaned)

            responses[checklist_item_index] = checklist_answer
            metadata_list.append(result["metadata"])

        
        # Sort checklist answers by index, in case the LLM answers the checklist items in a different order.
        checklist_answers_cleaned.sort(key=lambda x: x.index)

        metadata = {}
        for metadata_index, metadata_item in enumerate(metadata_list, start=1):
            metadata[f"metadata_{metadata_index}"] = metadata_item

        markdown = cls.convert_to_markdown(checklist_answers_cleaned)

        result = ViabilityChecklist(
            system_prompt_list=system_prompt_list,
            user_prompt_list=user_prompt_list,
            responses=responses,
            checklist_answers_cleaned=checklist_answers_cleaned,
            metadata=metadata,
            markdown=markdown,
        )
        return result    

    def to_dict(self, include_responses=True, include_cleaned_answers=True, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = {}
        if include_responses:
            d["responses"] = {k: v.model_dump() for k, v in self.responses.items()}
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt_list'] = self.system_prompt_list
        if include_user_prompt:
            d['user_prompt_list'] = self.user_prompt_list
        if include_cleaned_answers:
            d['checklist_answers_cleaned'] = [checklist_answer.model_dump() for checklist_answer in self.checklist_answers_cleaned]
        return d

    def save_raw(self, file_path: str) -> None:
        Path(file_path).write_text(json.dumps(self.to_dict(), indent=2))

    def measurement_item_list(self) -> list[dict]:
        """
        Return a list of dictionaries, each representing a measurement.
        """
        return [checklist_answer.model_dump() for checklist_answer in self.checklist_answers_cleaned]
    
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

    # Configure logging to only show __main__ logs
    logging.basicConfig(level=logging.WARNING)  # Set root logger to WARNING to suppress most logs
    logging.getLogger("__main__").setLevel(logging.INFO)  # Only show INFO for __main__
    logging.getLogger("httpx").setLevel(logging.WARNING)  # Suppress httpx logs
    logging.getLogger("planexe.llm_util.llm_executor").setLevel(logging.WARNING)  # Suppress llm_executor logs

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
    result = ViabilityChecklist.execute(llm_executor=llm_executor, user_prompt=query, max_number_of_items=3)

    print("\nResult:")
    json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
    print(json.dumps(json_response, indent=2))

    test_data_filename = f"viability_checklist_{prompt_id}.json"
    result.save_clean(Path(test_data_filename))
    print(f"Test data saved to: {test_data_filename!r}")

    markdown_filename = f"viability_checklist_{prompt_id}.md"
    result.save_markdown(Path(markdown_filename))
    print(f"Markdown saved to: {markdown_filename!r}")