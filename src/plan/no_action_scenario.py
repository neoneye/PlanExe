"""
Status Quo Scenario - The risk of not acting.

- No-Action Scenario (straightforward and common in project management)
- Do-Nothing Scenario
- Baseline Scenario (neutral and clear, commonly understood in strategic contexts)
- Inaction Analysis
- Inaction Scenario Analysis
- Business-as-Usual Scenario
- Standstill Scenario
- Consequences of No Change
- Consequences of Inaction (directly emphasizes negative implications)
- Passive Scenario
- Static Scenario
- Current Path Scenario
- Implications of Non-Action
- Default Future Scenario
- Do-Nothing Baseline (explicitly highlights the comparison to the action scenario)
- Project Abandonment Scenario
- Risk of Inertia Scenario
- Future Without Project (very clear, intuitive wording emphasizing future states clearly)
- Justification for Project

Outlining the consequences of doing nothing. What happens if the big project is cancelled or not pursued? Exploring the consequences of project abandonment.

Present a "do-nothing baseline" vs. the draft plan outcomes.

Follows roughly these steps:
1. Identifying assumptions about what will happen if the project is not pursued.
2. Exploring the consequences of the project not being pursued.
3. Presenting the status quo baseline vs. the draft plan outcomes.

PROMPT> python -m src.plan.no_action_scenario
"""
import os
import json
import time
import logging
from math import ceil
from dataclasses import dataclass
from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class DocumentDetails(BaseModel):
    """Structured output describing the consequences of PROJECT ABANDONMENT / INACTION."""

    # -- Context & Baseline --
    project_goal_summary: str = Field(
        description="≤30 words. The core objective the *planned project* aimed to achieve."
    )
    inaction_baseline_summary: str = Field(
        description="≤50 words. The likely state of affairs related to the project's domain if this specific planned project is *not* pursued."
    )

    # -- Consequences of Inaction (Project Abandonment) --
    strategic_positioning_consequences: list[str] = Field(
        description="Bullet points. Impacts on competitive standing, market position, influence, standard-setting, or strategic alignment if the project is abandoned."
    )
    capability_development_consequences: list[str] = Field(
        description="Bullet points. Impacts on the development, maturation, or deployment of relevant skills, technologies, resources, or infrastructure if the project is abandoned."
    )
    economic_financial_consequences: list[str] = Field(
        description="Bullet points. Short-term savings versus long-term opportunity costs (revenue, market share, efficiency gains, cost avoidance) from abandonment."
    )
    knowledge_objective_consequences: list[str] = Field(
        description="Bullet points. Specific knowledge gaps, research questions, learning opportunities, or secondary objectives that remain unaddressed due to abandonment."
    )
    risks_avoided_by_inaction: list[str] = Field(
        description="Bullet points. Specific risks inherent in the *planned project* (e.g., technical failure, financial loss, negative side-effects) that are *avoided* by not proceeding. Consider this the 'risk reduction' achieved through inaction."
    )

    # -- Impact & Stakeholder Summary --
    stakeholder_impact_summary: dict[str, str] = Field(
        description="Key/value pairs. Describe the net effect (positive, negative, mixed - consider 'Winners/Losers') on key identified stakeholders (individuals, groups, organizations) if the project is abandoned. Infer stakeholders from plan context."
    )
    quantifiable_impacts_of_inaction: dict[str, str] = Field(
        description="Key/value pairs for relevant impact dimensions (e.g., Financial, Time, Market Share). Rough ranges/estimates for consequences of *abandonment*. Use 'Not readily quantifiable' if needed. Be cautious with speculation."
    )
    missed_opportunities: list[str] = Field(
        description="Bullet points. Key strategic, developmental, financial, or learning opportunities forgone by abandoning the project."
    )

    # -- Strategic Outlook & Meta-Assessment --
    status_quo_assumptions: list[str] = Field(
        description="Bullet points. Key assumptions about the relevant environment or domain *without* this specific project proceeding (e.g., competitor actions, market trends, resource availability)."
    )
    key_inflection_points: list[str] = Field(
        description="Bullet points. Future events, milestones, competitor actions, or market shifts that inaction makes the entity vulnerable to or reactive towards. Represents points where the cost of inaction becomes more apparent."
    )
    timescale_impact: str = Field(
        description="Horizon keyword (e.g., Short-term, Mid-term, Long-term) + ≤15 words. Timescale over which the main consequences of inaction will manifest."
    )
    overall_assessment_of_inaction: str = Field(
        description="One‑word level (e.g., Benign, Manageable, Detrimental, Critical) + justification ≤20 words. Overall severity of *abandoning* the planned project."
    )

    # -- Executive Contrast & Recommendation --
    summary_if_project_abandoned: str = Field(
        description="~40 words. Concise summary of the future state if the planned project is *not* pursued."
    )
    summary_if_project_executed_successfully: str = Field(
        description="~40 words. Concise summary of the potential positive future state if the planned project *is* pursued and overcomes its challenges successfully (as implied by the plan)."
    )
    recommendation_rationale: str = Field(
        description="1-2 sentences. Briefly explain the reasoning for the final recommendation based on the comparison of risks (inherent in plan), potential rewards (if plan succeeds), and consequences of inaction/abandonment."
    )
    recommendation: str = Field(
        description="Single word: 'Proceed' or 'Abandon'. Must be consistent with the rationale."
    )
    summary: str = Field(
        description="2–3 sentences directly contrasting the two potential futures (abandonment vs. potential successful execution of the plan)."
    )

STATUS_QUO_SYSTEM_PROMPT = """
You are an expert strategy and risk analyst.

TASK ► Analyze the provided **Draft Plan** and the **Original Goal/Problem** it addresses. Based *only* on this context, perform an **Inaction Scenario Analysis**. This means assessing the likely future state and consequences if the specific actions outlined in the **Draft Plan** are **NOT** taken (i.e., the project is abandoned or not pursued). Populate the JSON exactly according to the `DocumentDetails` schema.

• Focus exclusively on the consequences of **NOT** executing the **Draft Plan**. Infer the context, domain, stakeholders, technologies, resources, and competitive landscape *solely* from the provided plan document.
• Do **NOT** invent external information or critique the plan's feasibility extensively, but *do* consider the risks *mentioned or implied within the plan* when weighing the recommendation. Assume the plan outlines a path to potential success *if* those risks are overcome. Your primary task is to analyze the implications of choosing **NOT** to pursue the plan as written.
• Use generic, abstract terms where appropriate, interpreting specifics from the plan.
• Briefly consider plausible second-order effects where strongly implied by the direct consequences, but maintain focus on the primary impacts of inaction.

Follow these field instructions precisely:
  1. project_goal_summary: ≤30 words summarizing the core aim of the *planned project being abandoned*.
  2. inaction_baseline_summary: ≤50 words describing the likely state *without* this specific planned project.
  3. strategic_positioning_consequences: Impacts on competitive standing, influence, etc., *if abandoned*. **Explicitly mention loss of leadership or falling behind key competitors/alternatives, and how competitors might fill the void, if implied by the plan context.**
  4. capability_development_consequences: Impacts on skills, tech, resources *if abandoned*.
  5. economic_financial_consequences: Savings vs. opportunity costs *if abandoned*. Consider direct and potentially significant indirect economic effects.
  6. knowledge_objective_consequences: Knowledge gaps, unaddressed objectives *if abandoned*.
  7. risks_avoided_by_inaction: Specific risks *from the plan* that are avoided by cancellation. Frame as risks *not* incurred or 'risk reduction opportunities' gained by inaction.
  8. stakeholder_impact_summary: Net effect on *identified stakeholders* (infer from plan). Explicitly consider the "Winners/Losers" dynamic and briefly note differing short-term vs. long-term impacts where relevant *if abandoned*.
  9. quantifiable_impacts_of_inaction: Rough ranges/estimates for consequences of *abandonment*. Use 'Not readily quantifiable' if needed. **Explicitly label highly speculative figures (e.g., far-future revenue, precise market shifts) by appending `(highly speculative)`. Be cautious and avoid inventing precise numbers without strong basis in the plan context.**
 10. missed_opportunities: Key opportunities forgone *by abandonment*.
 11. status_quo_assumptions: Assumptions about the relevant environment *without* this project.
 12. key_inflection_points: Future external events/milestones that inaction makes the entity vulnerable or reactive to. Points where inaction costs become clearer.
 13. timescale_impact: Horizon + ≤15 words for when abandonment impacts manifest.
 14. overall_assessment_of_inaction: "Level – justification ≤20 words" assessing severity of *abandonment*.
 15. summary_if_project_abandoned: ~40 words describing the future *without* the planned project. **Clearly state potential loss of strategic advantage or leadership position.**
 16. summary_if_project_executed_successfully: ~40 words describing the potential *positive* future *with* a successful execution of the plan (acknowledging its inherent risks), implying leadership or advantage.
 17. recommendation_rationale: **1-2 sentences explaining the final recommendation.** Compare potential rewards (if successful according to plan) against the plan's inherent risks *and* the consequences of abandonment (including potential loss of leadership).
 18. recommendation: **Provide ONE word: 'Proceed' or 'Abandon'.** This MUST logically follow from the `recommendation_rationale`.
       • "Proceed" → The potential benefits of successful execution (despite plan risks) appear greater than the downsides of abandonment.
       • "Abandon" → The downsides of abandonment appear less severe than the high risks/costs associated with attempting the project (as described in the plan), even considering its potential rewards.
 19. summary: 2–3 sentences directly contrasting the *abandonment* future (potentially including falling behind or ceding leadership) vs. the *potential successful execution* future (implying leadership/advantage) based on the plan's context.

OUTPUT ► Return only valid JSON matching the schema. No extra keys or comments.
"""

@dataclass
class NoActionScenario:
    """
    Take a look at the draft plan and present the status quo scenario.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict
    markdown: str

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> 'NoActionScenario':
        """
        Invoke LLM with the project description.
        """
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        system_prompt = STATUS_QUO_SYSTEM_PROMPT.strip()

        chat_message_list = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_prompt,
            ),
            ChatMessage(
                role=MessageRole.USER,
                content=user_prompt,
            )
        ]

        sllm = llm.as_structured_llm(DocumentDetails)
        start_time = time.perf_counter()
        try:
            chat_response = sllm.chat(chat_message_list)
        except Exception as e:
            logger.debug(f"LLM chat interaction failed: {e}")
            logger.error("LLM chat interaction failed.", exc_info=True)
            raise ValueError("LLM chat interaction failed.") from e

        end_time = time.perf_counter()
        duration = int(ceil(end_time - start_time))
        response_byte_count = len(chat_response.message.content.encode('utf-8'))
        logger.info(f"LLM chat interaction completed in {duration} seconds. Response byte count: {response_byte_count}")

        json_response = chat_response.raw.model_dump()

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        markdown = cls.convert_to_markdown(chat_response.raw)

        result = NoActionScenario(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
            markdown=markdown
        )
        return result
    
    def to_dict(self, include_metadata=True, include_system_prompt=True, include_user_prompt=True) -> dict:
        d = self.response.copy()
        if include_metadata:
            d['metadata'] = self.metadata
        if include_system_prompt:
            d['system_prompt'] = self.system_prompt
        if include_user_prompt:
            d['user_prompt'] = self.user_prompt
        return d

    def save_raw(self, file_path: str) -> None:
        with open(file_path, 'w') as f:
            f.write(json.dumps(self.to_dict(), indent=2))

    @staticmethod
    def convert_to_markdown(document_details: DocumentDetails) -> str:
        """
        Convert the raw document details to markdown.
        """
        rows = []
        
        rows.append(f"\n## Summary\n{document_details.summary}")
        return "\n".join(rows)

    def save_markdown(self, output_file_path: str):
        with open(output_file_path, 'w', encoding='utf-8') as out_f:
            out_f.write(self.markdown)

if __name__ == "__main__":
    from src.llm_factory import get_llm
    from src.plan.find_plan_prompt import find_plan_prompt

    llm = get_llm("ollama-llama3.1")

    plan_prompt = find_plan_prompt("de626417-4871-4acc-899d-2c41fd148807")
    query = (
        f"{plan_prompt}\n\n"
        "Today's date:\n2025-Feb-27\n\n"
        "Project start ASAP"
    )
    print(f"Query: {query}")

    no_action_scenario = NoActionScenario.execute(llm, query)
    json_response = no_action_scenario.to_dict(include_system_prompt=False, include_user_prompt=False)
    print("\n\nResponse:")
    print(json.dumps(json_response, indent=2))

    print(f"\n\nMarkdown:\n{no_action_scenario.markdown}")
