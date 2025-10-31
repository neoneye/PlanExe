"""
Go through a checklist, to determine if there are problems with the plan.

The Primary Reader (The "Go/No-Go" Decision-Maker): This is a senior executive, a project sponsor, or even a political figure (like a Chief of Staff) who commissioned this report.

    Value: This section is the most valuable part of the entire report for this reader. They may not have the time or expertise to read the full 100+ page plan. This checklist provides an immediate, at-a-glance diagnostic. The overwhelming number of 🛑 High risk items sends an unambiguous message: "This plan, in its current form, is fundamentally non-viable and dangerous." It's a powerful visual tool for communicating extreme risk without needing to parse complex paragraphs.

The Secondary Reader (The Project Manager/Lead): This is the person tasked with potentially fixing the plan.

    Value: It serves as a prioritized "fix-it" list. It tells the project manager which fires are the biggest. They don't need to worry about the team size (a ⚠️ Medium risk) if the entire project is a 🛑 High "Legal Minefield." It focuses their attention on the foundational, existential threats to the project's success.

Calibation. Skewed distribution: 16 “High” flags out of 20 reads like alarm fatigue. 
Yes, the majority may be red. Holding the items up against each other is not the job for this checklist. It's further downstream.
I'm not going to reserve High for the most significant issues.
The primary task with this checklist is to detect that there is something fundamentally wrong with the plan.

Some of the checklist items overlaps with each other, and I don't care about things being mutually exclusive where things are not supposed to overlap.
I care about what problems I observe in the generated reports.

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
        "subtitle": "Does the project require a major, unpredictable discovery in fundamental science to succeed?",
        "instruction": "Assess whether the project's core goal or claimed mechanisms contradict well-established scientific laws or consensus (e.g., in physics, biology, earth sciences). You must judge the scientific validity of the subject matter itself, NOT just the methods of implementation.\n\n**Crucially, you must distinguish between a violation of fundamental scientific laws (e.g., perpetual motion) and an extreme-scale engineering or logistical challenge (e.g., constructing a space elevator or a massive ocean platform). An engineering challenge, no matter how immense, is NOT a violation for this specific check.**\n\nSet LEVEL=HIGH **only if** any success condition requires a true physical impossibility, treats pseudoscience as fact, or assumes overturning a well-tested scientific law without extraordinary evidence. **Do not set LEVEL=HIGH for projects that are merely politically, legally, or financially infeasible; other checklist items will capture those flaws.** Otherwise, set LEVEL=LOW.\n\nIn the justification, you MUST follow this exact 3-part structure:\n  (1) Name the specific scientific principle(s) being violated.\n  (2) Quote the exact line(s) from the plan that reveal this conflict.\n  (3) In one sentence, state the direct project-level consequence, explaining why this makes the plan's goal fundamentally non-viable.\n\nMitigation for HIGH must be a stop/go fatal-flaw gate assigned to the specific highest-level stakeholder identified in the plan text (e.g., 'Project Sponsor', 'CEO'). The gate must be evidence-based.",
        "comment": "If the initial prompt is vague/scifi/aggressive or asks for something that is physically impossible, then the generated plan usually end up with some fantasy parts, making the plan unrealistic."
    },
    {
        "index": 2,
        "title": "No Real-World Proof",
        "subtitle": "Does success depend on a technology or system that has not been proven in real projects at this scale or in this domain?",
        "instruction": "No Real-World Proof: Is there credible, real-world evidence that the core mechanism works outside of a lab/demo? If this is a first-of-its-kind or unregulated/novel construct, set level to 'high'. In the justification, cite the exact areas with no precedent (markets, technology, policy) rather than saying 'missing referenced artifacts'. In the mitigation, propose a parallel, multi‑track validation that includes: (T1) technical threat‑model + security PoC with red‑team; (T2) legal/compliance review for the relevant domains (e.g., securities/market integrity/AML/data protection) and licensing feasibility; (T3) market validation (letters of intent, regulator pre‑reads, partner commitments); (T4) ethics/abuse analysis (manipulation/foreign‑influence/dual‑use). Define explicit go/no‑go gates and realistic timeframes; declare NO‑GO if any track blocks.",
        "comment": "It's rarely smooth sailing when using new technology, novel concepts that no human has ever been used before. PlanExe sometimes picking a scenario that is way too ambitious."
    },
    {
        "index": 3,
        "title": "Buzzwords",
        "subtitle": "Does the plan use excessive buzzwords without evidence of knowledge?",
        "instruction": "Flag any term that reads like a buzzword and require a one-page mechanism-of-action per term: role in the system; inputs/outputs & interface/architecture sketch; measurable success criteria; dependencies; abuse/failure modes; accountable owner. Log any missing piece as a gap with an owner + due date.",
        "comment": "PlanExe often ends up using buzzwords such as blockchain, NFT, DAO, VR, AR, and expects that one person without developer background can implement the plan."
    },
    {
        "index": 4,
        "title": "Underestimating Risks",
        "subtitle": "Does this plan grossly underestimate risks?",
        "instruction": "Find a critical risk that is mentioned in the plan's risk register. Then, describe a plausible second-order (knock-on) effect of that risk materializing that the plan fails to consider. Your justification must explain this causal chain (If Risk X happens, then Consequence Y will follow, which the plan ignores). The mitigation must be a task to add this specific second-order risk and its contingency plan to the risk register.",
        "comment": "Despite PlanExe trying to uncover many risks, there are often risks that are not identified, or some significant risk gets neglected."
    },
    {
        "index": 5,
        "title": "Timeline Issues",
        "subtitle": "Does the plan rely on unrealistic or internally inconsistent schedules?",
        "instruction": "Assess the project timeline for realism. Set LEVEL to HIGH if the durations are obviously too short for the described tasks (e.g., 'build a new software platform in one week') or if critical preparatory steps like 'securing permits' or 'design approval' are given no time at all. Also flag if the plan has a hard deadline but no clear path to meet it. In the justification, cite the specific unrealistic duration or the missing critical step. For mitigation, require the creation of a more detailed timeline with key milestones, ensuring the deadline is realistic for the project's actual scope and urgency.",
        "comment": "PlanExe currently has no knowledge about the resources available. In the first draft of the plan makes no attempt at parallelizing the tasks to be done in a shorter timeframe. I imagine a human will have to configure the resources, before rescheduling the tasks to be done in a shorter timeframe. A plan for a funeral for some rock star legend and it's happening next week, here a 60 days delay wont work. There are tiny plans such as 'I want to make a cup of coffee, I have all the ingredients, I know how to do it'. Typical projects are people that want to make changes to their business or renovate their house."
    },
    {
        "index": 6,
        "title": "Money Issues",
        "subtitle": "Are there flaws in the financial model, funding plan, or cost realism?",
        "instruction": "Assess the plan's financial realism. First, check if any cost or budget numbers are provided. Set LEVEL to HIGH if the plan describes activities with obvious costs (e.g., purchasing, construction, hiring) but provides no budget figures, or if the stated budget is grossly mismatched with the project's scale. If funding sources are mentioned, note whether they are confirmed or speculative. In the justification, cite the specific lack of figures or the uncommitted nature of funding. For mitigation, propose developing an initial cost estimate and funding plan, making the deadline proportional to the project's lifecycle (e.g., 'as a prerequisite for the execution phase', or 'within the first week' for urgent projects).",
        "comment": "PlanExe currently has no Cost Breakdown Structure. Some projects are intended to generate revenue, other projects are not intended for profit, but for a specific purpose. Yet, there can be significant money issues that are not identified. For a solo entrepeneur it may be overkill with a CBS. For a private project it's likely not relevant."
    },
    {
        "index": 7,
        "title": "Budget Too Low",
        "subtitle": "Is there a significant mismatch between the project's stated goals and the financial resources allocated, suggesting an unrealistic or inadequate budget?",
        "instruction": "Budget Too Low: Is there a significant mismatch between the project's stated goals and the allocated budget? In the justification, after citing the plan's budget figures, provide Order-of-Magnitude (OOM) context by comparing them to analogous real-world projects (e.g., 'The plan budgets $5M, but similar public infrastructure projects typically exceed $50M.'). Set level to 'high' if the mismatch is significant. Mitigation must be a task to produce an independent, detailed cost analysis. Normalize comparators: express costs per-year, per-hectare, or per-objective; note scope differences (R&D vs enforcement/commercialization); include 2–3 analogous programs.",
        "comment": "Often the user specifies a 100 USD budget in the initial prompt, where the generated plan requires millions of dollars to implement. Or the budget grows during the plan generation, so the money needed ends up being much higher than expected."
    },
    {
        "index": 8,
        "title": "Overly Optimistic Projections",
        "subtitle": "Does this plan grossly overestimate the likelihood of success, while neglecting potential setbacks, buffers, or contingency plans?",
        "instruction": "Assess if the plan's projections are one-sided. Set LEVEL to HIGH if the plan presents key projections (e.g., revenue, user adoption, completion dates) as a single number without providing a range, confidence interval, or discussing alternative scenarios (e.g., a 'worst-case' or 'conservative' case). The lack of contingency planning for projections indicates optimism. For mitigation, require a sensitivity analysis or a best/worst/base-case scenario analysis for the most critical projection.",
        "comment": "The generated plan describes a sunshine scenario that is likely to go wrong, without any buffers or contingency plans."
    },
    {
        "index": 9,
        "title": "Lacks Technical Depth",
        "subtitle": "Does the plan omit critical technical details or engineering steps required to overcome foreseeable challenges, especially for complex components of the project?",
        "instruction": "Flag this when any critical-path component lacks concrete engineering artifacts: (1) mechanism-of-action/architecture or process flow, (2) quantified performance targets with acceptance tests/DoE, and (3) integration & dependency mapping (interfaces, resources, capacities). If ≥2 are missing for a critical area, mark this item.",
        "comment": "Some plans involves serious engineering, but the generated plan is missing the technical details that explain how to overcome the technical challenges. Nailing the technical details is crucial."
    },
    {
        "index": 10,
        "title": "Assertions Without Evidence",
        "subtitle": "Does each critical claim (excluding timeline and budget) include at least one verifiable piece of evidence?",
        "instruction": "For every critical claim (excluding schedule/budget), require one verifiable artifact: signed LOI/MOU/contract, regulator pre-read, benchmark/validation report with methods, or public dataset + reproducible analysis. If none exists, record as a gap with owner, due date, and the specific artifact to obtain.",
        "comment": "Often the generated plan specifies numbers/facts/concepts without any evidence to support the claims. These will have to be fact checked and adjusted in a refinement of the plan."
    },
    {
        "index": 11,
        "title": "Unclear Deliverables",
        "subtitle": "Are the project's final outputs or key milestones poorly defined, lacking specific criteria for completion, making success difficult to measure objectively?",
        "instruction": "Unclear Deliverables: Are the project's final outputs or key milestones poorly defined? Set LEVEL to HIGH if a major deliverable is mentioned without specific, verifiable qualities. For justification, name the abstract deliverable. The mitigation must be a task to define SMART acceptance criteria for that deliverable, including at least one specific, quantifiable Key Performance Indicator (KPI). For example, for 'a new system,' the mitigation could be 'Define SMART criteria, including a KPI for system uptime (e.g., 99.9% availability).'",
        "comment": "Some projects involves many components, without a clear specification of each component."
    },
    {
        "index": 12,
        "title": "Gold Plating",
        "subtitle": "Does the plan add unnecessary features, complexity, or cost beyond the core goal?",
        "instruction": "Your task is to detect 'Gold Plating'. Flag as HIGH RISK any feature, component, or activity that adds significant cost or complexity without demonstrably supporting one of the project's primary, stated objectives or satisfying a binding legal/contractual requirement.\n\nYour justification MUST:\n  (1) Identify the feature you are flagging as potential Gold Plating.\n  (2) State that it does not appear to directly support the core project goals (list 1-2 core goals from the plan for context).\n\nMitigation for HIGH must require a 'Benefit Case Review': For each flagged feature, the project team must produce a one-page benefit case justifying its inclusion, complete with a KPI, owner, and estimated cost, or else move the feature to the project backlog.",
        "comment": "For a 'Make me a cup of coffee' prompt, then the generated plan is overkill and involves lots of people and resources. Flags when the solution is excessively elaborate for the problem. A feature is Gold Plating if it doesn't directly serve a core project goal or meet a mandatory requirement. https://en.wikipedia.org/wiki/Gold_plating_(project_management)"
    },
    {
        "index": 13,
        "title": "Staffing Fit & Rationale",
        "subtitle": "Do the roles, capacity, and skills match the work, or is the plan under- or over-staffed?",
        "instruction": "Staffing Fit & Rationale: Analyze the plan to identify the single most specialized, novel, or mission-critical role required for success (the 'unicorn role'). Set level to 'high' if this role is both essential and likely difficult to fill. The justification must name this unicorn role and explain why its expertise is both critical and rare. The mitigation must be a task to validate the talent market for that specific role as an early go/no-go check.",
        "comment": "For a 'Im a solo entrepreneur and is making everything myself' prompt, then the generated plan is likely suggesting to hire a huge team of people, and ignoring the fact that the entrepreneur is doing everything themselves. For a 'Construct a bridge' prompt, then the generated plan is likely to underestimate the number of people needed to achieve the goals."
    },
    {
        "index": 14,
        "title": "Legal Minefield",
        "subtitle": "Does the plan involve activities with high legal, regulatory, or ethical exposure, such as potential lawsuits, corruption, illegal actions, or societal harm?",
        "instruction": "Legal Minefield: Does the plan trigger multiple overlapping jurisdictions or regimes with low probability of approval and high litigation risk (e.g., environmental impact, land use, data protection, public safety)? Set level to 'high' if so. In the justification, reference the specific regimes/laws implicated. In the mitigation, propose a phased legal validation with early go/no-go points, starting with the lowest-cost step first. Example: \"Phase 1 (Immediate): A 'Fatal Flaw Analysis' to find absolute statutory blockers. Phase 2 (Short-Term): If viable, 'Preliminary Engagement' with a key regulator. Phase 3 (Full Study): Only if engagement is positive, commission a full 'Regulatory Pathway Study'.\"",
        "comment": "Sometimes the generated plan describes a sunshine scenario where everything goes smoothly, without any lawyers or legal issues."
    },
    {
        "index": 15,
        "title": "Lacks Operational Sustainability",
        "subtitle": "Even if the project is successfully completed, can it be sustained, maintained, and operated effectively over the long term without ongoing issues?",
        "instruction": "Lacks Operational Sustainability: Assess whether the project can be sustained post-completion. Evaluate: (1) Ongoing operational costs vs. available funding/revenue—is there a sustainable business model? (2) Maintenance requirements—are specialized skills, parts, or vendors needed that may not be available long-term? (3) Scalability—can the system handle growth or changing conditions? (4) Personnel dependency—does operation depend on specific individuals who may leave? (5) Technology obsolescence—will critical technology become unsupported or obsolete? (6) Environmental/social impact—can negative impacts be managed long-term? Set LEVEL to HIGH if: operational costs exceed sustainable funding, maintenance requires unavailable resources, or the system cannot adapt to changing conditions. Set LEVEL to MEDIUM if: sustainability concerns exist but can be addressed with planning. Set LEVEL to LOW if: a clear, sustainable operational model exists with adequate resources. In the justification, identify the specific sustainability gap (funding, maintenance, scalability, etc.). In the mitigation, propose an operational sustainability plan including: funding/resource strategy, maintenance schedule, succession planning, technology roadmap, or adaptation mechanisms.",
        "comment": "Many projects focus on completion but ignore operational sustainability. A perfectly built project can fail if it requires unsustainable funding, impossible maintenance, or cannot adapt to changing conditions. PlanExe may generate plans that work in theory but cannot be sustained in practice."
    },
    {
        "index": 16,
        "title": "Infeasible Constraints",
        "subtitle": "Does the project depend on overcoming constraints that are practically insurmountable, such as obtaining permits that are almost certain to be denied?",
        "instruction": "Infeasible Constraints: Does the project depend on overcoming constraints that are practically insurmountable, such as obtaining permits that are almost certain to be denied. Explicitly assess land-tenure insecurity and conflicting national interests as structural blockers; either identify jurisdictions with viable permitting paths (or historical approval/denial rates) or rate as high risk.",
        "comment": "Getting a permit to build a spaceship launch pad in the center of the city is likely going to be rejected."
    },
    {
        "index": 17,
        "title": "External Dependencies",
        "subtitle": "Does the project depend on critical external factors, third parties, suppliers, or vendors that may fail, delay, or be unavailable when needed?",
        "instruction": "Scan for critical third-party dependencies on the critical path (e.g., regulatory approvals, vendors, data/platform access, facilities, financing tranches). Set HIGH if any critical milestone depends on an external party without a signed commitment (LOI/MOU/contract), regulator pre-read, capacity confirmation, or equivalent artifact. If dependencies are mentioned but unproven, set at least MEDIUM. In justification, name the specific dependency and the missing artifact. Mitigation: produce a Dependency Register (owner, artifact, lead time, fallback).",
        "comment": "Plans often assume external parties will deliver as expected, without considering vendor lock-in, supplier failures, or partner non-commitment. Real projects can fail if a critical supplier goes out of business or a partner doesn't follow through."
    },
    {
        "index": 18,
        "title": "Stakeholder Misalignment",
        "subtitle": "Are there conflicting interests, misaligned incentives, or lack of genuine commitment from key stakeholders that could derail the project?",
        "instruction": "Analyze the stated goals of two key stakeholders (e.g., 'Finance Department' and 'R&D Team'). Identify a plausible, unstated conflict in their underlying incentives (e.g., Finance is incentivized by quarterly budget adherence, while R&D is incentivized by long-term innovation, creating a conflict over experimental spending). The justification must state the two stakeholders and their conflicting incentives. The mitigation must be a task to create a shared, measurable objective (OKR) that aligns both stakeholders on a common outcome.",
        "comment": "Projects can fail even with perfect technical execution if stakeholders have hidden agendas, conflicting priorities, or lose interest halfway through. PlanExe may assume stakeholders are fully supportive without verifying commitment or alignment."
    },
    {
        "index": 19,
        "title": "No Adaptive Framework",
        "subtitle": "Does the plan lack a clear process for monitoring progress and managing changes, treating the initial plan as final?",
        "instruction": "Set HIGH if the plan lacks a feedback loop: KPIs, review cadence, owners, and a basic change-control process with thresholds (when to re-plan/stop). Vague ‘we will monitor’ is insufficient. Mitigation: add a monthly review with KPI dashboard and a lightweight change board.",
        "comment": "A plan is a starting point, not a final script. Without a way to measure progress and adapt to unforeseen problems (scope creep, delays, new requirements), even the best initial plan will fail. This checks if the project has a steering wheel."
    },
    {
        "index": 20,
        "title": "Uncategorized Red Flags",
        "subtitle": "Are there any other significant risks or major issues that are not covered by other items in this checklist but still threaten the project's viability?",
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

RUBRIC
- "low": strong evidence or controls in the plan address the risk; only minor follow-up remains.
- "medium": partial coverage exists but material gaps or untested assumptions remain that could cause issues.
- "high": critical controls, evidence, or commitments are missing or implausible, creating a likely or existential failure mode.

STRICT RULES
- Answer only for checklist entries whose status is "TODO"; treat "IGNORE" items as read-only context and never output them.
- level must be one of: "low", "medium", "high".
- Start each justification with "Rated LOW/MEDIUM/HIGH because..." (use the chosen level) so the reader sees how the rubric was applied.
- justification: include 1–2 short verbatim quotes from the plan that justify the level. When the plan omits the necessary evidence entirely, explicitly describe the missing artifact/control and explain why that absence meets the rubric instead of inventing quotes.
- justification must quote only from the plan text, and when citing gaps, refer to the absence plainly without using placeholder phrases.
- Never use the phrase "missing referenced artifacts" or similar placeholders; spell out what evidence is missing and the consequence.
- mitigation: ONE assignable task. Start with a suggested role/team, followed by a verb, and include a suggested timeframe (e.g., "Legal Team: Draft a memo... within 30 days."). ~30 words.
- mitigation must be actionable; never respond with "N/A" or similar placeholders.
- Mitigation must be specific to the identified issue; avoid vague directives like "review the plan", "consult experts", or "investigate" unless paired with a concrete deliverable that directly reduces the flagged risk.
- If the level is "low", mitigation should reinforce existing good practice (e.g., document evidence, schedule routine monitoring) rather than delegating a broad re-check of the entire plan.
- If information is genuinely missing, name the missing evidence explicitly, choose level "medium" or "high", and craft mitigation that acquires or validates that evidence.

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
        explanation_map = {
            "low": "Strong evidence or controls already cover the risk; only minor follow-up remains.",
            "medium": "Partial coverage exists but material gaps or untested assumptions could cause issues.",
            "high": "Critical controls or evidence are missing, making failure likely without intervention.",
        }
        rows = []

        # Histogram
        num_low = sum(1 for item in checklist_answers if item.level == "low")
        num_medium = sum(1 for item in checklist_answers if item.level == "medium")
        num_high = sum(1 for item in checklist_answers if item.level == "high")

        rows.append("### Summary\n")
        rows.append("| Level | Count | Explanation |")
        rows.append("|---|---|---|")
        rows.append(f"| {level_map['high']} | {num_high} | {explanation_map['high']} |")
        rows.append(f"| {level_map['medium']} | {num_medium} | {explanation_map['medium']} |")
        rows.append(f"| {level_map['low']} | {num_low} | {explanation_map['low']} |")

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