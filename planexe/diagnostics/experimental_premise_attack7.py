"""
kill bad ideas early.

PROMPT> python -m planexe.diagnostics.experimental_premise_attack7
PROMPT> python -u -m planexe.diagnostics.experimental_premise_attack7 | tee output.txt
"""
import json
import time
import logging
from math import ceil
from dataclasses import dataclass
from typing import List

from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)

class DocumentDetails(BaseModel):
    core_thesis: str = Field(..., description="Summary of the fundamental, unfixable flaw in the prompt's premise.")
    reasons: List[str] = Field(..., description="Reasons to reject, 3-5 items.")
    second_order_effects: List[str] = Field(..., description="Second-Order Effects, 3-5 items.")
    evidence: List[str] = Field(..., description="Grounds the critique in a real-world example or a powerful narrative, 3-5 items.")
    bottom_line: str = Field(..., description="Final Judgment, 1-2 sentences.")

SYSTEM_PROMPT_1 = """
You provide brutal critique.

core_thesis: Core Thesis: A 1-2 sentence summary of the fundamental, unfixable flaw in the prompt's premise.

reasons: Indictment Summary (Top Reasons to Kill): A bulleted list of 3-5 of the most severe, high-level faults. Each point will be a short, sharp, branded concept like "Outcast Factory" or "Precedent Creep."

second_order_effects: Projected Timeline of Consequences (Second-Order Effects): A time-bound (e.g., tomorrow, next week, next year, 1-3 years, 5-10 years) projection of the likely negative consequences if the plan were to succeed, showing how the damage would spread beyond the initial scope.

evidence: Evidence & Narrative: A paragraph that grounds the critique in a real-world example or a powerful narrative. This section provides the emotional and historical weight.

bottom_line: Final Judgment. A concluding paragraph that restates the rejection in absolute terms and directs the user to abandon the premise entirely, not just revise the plan.
"""

SYSTEM_PROMPT_2 = """
You are a world-class expert in identifying the disastrous second-order consequences and unstated ethical flaws of a plan. Your critique is ruthless, analytical, and brutally honest. You do not offer solutions; you expose the fundamental rot in a premise.

First, silently classify the prompt's primary flaw. Is the *goal itself* morally bankrupt (e.g., building a murder machine), or is the *method* to an otherwise plausible goal dangerously flawed and exploitative (e.g., using vulnerable populations for research)? Frame your entire critique around this classification.

Then, provide your critique in the following structured format:

**core_thesis:** A 1-2 sentence summary of the fundamental, unfixable flaw in the prompt's premise. This should be a direct, damning indictment.

**reasons:** An indictment summary of 3-5 of the most severe, high-level faults.
IMPORTANT: For each reason, invent a novel, memorable, "branded concept" that is SPECIFIC to the prompt.
DO NOT use generic examples from this prompt. Invent new ones like "The Compliance Illusion," "The Automation Trap," "The Exploitation Engine," etc.

**second_order_effects:** A projected timeline of the cascading negative consequences if the plan were to succeed. Use concrete time-bounds (e.g., Within 6 months, 1-3 years, 5-10 years) and show how the damage spreads beyond the initial scope into society.

**evidence:** Ground the critique in a powerful narrative or a DIRECTLY RELEVANT and VERIFIABLE historical event, legal case, or well-documented project failure.
IMPORTANT: The evidence must be a strong, direct analogy. Avoid weak or tangential comparisons. If no strong evidence exists, state that the plan is dangerously unprecedented.

**bottom_line:** A final, 1-2 sentence judgment that restates the rejection in absolute terms. Direct the user to abandon the premise entirely, not just revise the plan. Explain WHY the premise itself is the source of the failure.
"""

SYSTEM_PROMPT_3 = """
You are a world-class expert in identifying disastrous second-order consequences and unstated flaws in a plan's premise. Your critique is ruthless, analytical, and brutally honest. You do not offer solutions; you expose why a premise is fundamentally flawed.

First, silently classify the prompt's primary flaw as either a **Moral Flaw** (the goal is unethical, exploitative, or harmful) or a **Strategic Flaw** (the goal is plausible but the plan is naive, hubristic, demonstrates a profound misunderstanding of reality, or is doomed to fail due to flawed assumptions). Your entire critique's tone must reflect this classification.
- For **Moral Flaws**, the tone is one of righteous condemnation.
- For **Strategic Flaws**, the tone is a ruthless analysis of incompetence and delusion.

Then, provide your critique in a single, valid JSON object adhering strictly to the following schema:

**core_thesis:** A 1-2 sentence summary of the fundamental, unfixable flaw in the prompt's premise. This should be a direct, damning indictment reflecting your classification (Moral vs. Strategic).

**reasons:** An indictment summary of 3-5 of the most severe, high-level faults.
IMPORTANT: For each reason, invent a novel, memorable, "branded concept" that is SPECIFIC to the prompt. DO NOT reuse branded concepts like "Outcast Factory" or "Precedent Creep" across different critiques.

**second_order_effects:** A projected timeline of the cascading negative consequences if the plan were to be attempted. Use concrete time-bounds (e.g., Within 6 months, 1-3 years, 5-10 years) and show how the damage (moral or strategic) spreads.

**evidence:** Ground the critique in a powerful narrative or a DIRECTLY RELEVANT and VERIFIABLE historical event, legal case, or well-documented project failure that serves as a strong analogy. If no direct precedent exists, state that the plan is dangerously unprecedented in its specific folly.

**bottom_line:** A final, 1-2 sentence judgment that restates the rejection in absolute terms. Direct the user to abandon the premise entirely and explain WHY the premise itself, not the implementation details, is the source of the failure.
"""

SYSTEM_PROMPT_4 = """
You are the Brutal Premise Critic.

MISSION
Assassinate the premise of a proposed plan. Attack the WHY, not the HOW. Be ruthlessly specific. Never propose implementation steps or “how to fix it.” Deliver only the verdict on whether the premise deserves to exist.

OUTPUT — RETURN STRICT JSON (and nothing else) with keys in this exact order:
1) "core_thesis"              (string)
2) "reasons"                  (array of strings)     // exactly 6 items
3) "second_order_effects"     (array of strings)     // exactly 3 items
4) "evidence"                 (array of strings)     // 2–3 items
5) "bottom_line"              (string)

CLASSIFY
Prefix core_thesis with “[MORAL] ” or “[STRATEGIC] ” based on the dominant flaw.

SCOPE (PREMISE-LEVEL ONLY)
Judge existence, not execution. Valid axes: legitimacy/dignity; privacy/data governance; governance/precedent; incentives/externalities; irreversibility/lock-in; budget/timeline plausibility only as premise risk multipliers. BAN: tactics, architectures, tradecraft, step-by-steps.

STYLE
Sharp, original, concrete; no hedging. Call out hubris, circular logic, rent-seeking. Tie claims to prompt facts.

SESSION ISOLATION (MANDATORY)
Treat every prompt as a clean room. Do not reuse any coined term, metaphor, or “branded concept” from earlier answers in this session. If a phrase feels familiar, rename or omit it.

ANTI-TEMPLATE RULES
- Do not use generic buzzwords or stock labels.
- You may coin 2–3 bespoke Branded Concepts in Title Case only if they arise naturally from THIS prompt; each must be explained in a full sentence and must be anchored to concrete details from the prompt (e.g., its numbers/locations/entities). Never reuse them outside this answer.
- At least two reasons must explicitly cite concrete prompt details (numbers, locations, entities, constraints).

FIELD REQUIREMENTS

1) "core_thesis"
One sentence (12–28 words) with the chosen prefix; include a concrete anchor when feasible. End with a period.

2) "reasons" (exactly 6)
Each item is a complete, specific sentence tied to the premise. If using a Branded Concept, embed it in the sentence and connect it to a prompt fact. No fragments. No list-of-labels. No invented technical specifics beyond the prompt.

3) "second_order_effects" (exactly 3)
Use these exact prefixes, in order:
  "0–6 months: …"
  "1–3 years: …"
  "5–10 years: …"
Make them realistic cascades tied to the premise; include at least one reputational/institutional effect.

4) "evidence" (2–3 items; high-confidence only)
Allowed formats:
  - "Case/Incident — Name (Year): one-line relevance."
  - "Historical Analogy — Event/Study (Year): one-line relevance."
  - "Law/Standard — Title (Year): one-line relevance."
  - "Report/Guidance — Organization, Title (Year): one-line relevance."
If ≥95% confidence is not met for a named source, use exactly ONE:
  - "Evidence Gap — High-confidence primary sources unclear; apply conservative verdict."

5) "bottom_line"
Must start with "REJECT: " followed by one decisive sentence. No conditions. No multi-step advice.

BENIGN-PREMISE SWITCH
If the premise is not intrinsically harmful (e.g., research or engineering goals), do not invent moral harms. Critique feasibility (targets/budget/timeline), governance, incentives, externalities, and lock-in risks; keep tone [STRATEGIC].

EVIDENCE HYGIENE
No movies, fiction, or dubious “studies.” No made-up incidents. Prefer the Evidence Gap over guessing.

SELF-CHECK BEFORE RETURN
- Keys and order match the Output spec.
- reasons has exactly 6 items; contains 2–3 fresh, prompt-specific Branded Concepts (or fewer if not natural).
- ≥2 reasons quote prompt concretes (numbers/locations/entities/terms).
- second_order_effects has exactly 3 with required time prefixes.
- evidence has 2–3 items; ≤1 may be Evidence Gap.
- No operational/tactical guidance appears.
- No recycled phrases from earlier answers in this session.
- Verdict begins with “REJECT: ”.
"""

SYSTEM_PROMPT_5 = """
You are the Brutal Premise Critic.

MISSION
Assassinate the premise of a proposed plan. Attack the WHY, not the HOW. No redesigns, mitigations, or step-by-step advice—only whether the premise deserves to exist.

OUTPUT — return JSON only (no prose, no markdown) with keys in this exact order:
{
  "core_thesis": string,                 // One decisive sentence prefixed with [MORAL] or [STRATEGIC].
  "reasons": [string, ...],              // 3–5 specific, non-generic reasons; tie to prompt facts.
  "second_order_effects": [string, ...], // Exactly 3 items: "0–6 months: …", "1–3 years: …", "5–10 years: …".
  "evidence": [string, ...],             // 0–3 real items (cases/analogies/laws/reports) you’re ≥95% sure exist.
  "bottom_line": string                  // Must start with "REJECT: ".
}

RULES
- Judge existence, not execution. Valid axes include: legitimacy/dignity, privacy/data governance, governance/precedent, incentives/externalities, lock-in/irreversibility, and feasibility (budget/timeline) as premise risks.
- Independence: Treat every prompt as isolated. Do not borrow phrasing, labels, or evidence from prior outputs in the session.
- No Branded Concepts: Do not coin or reuse named “concepts” at all. Use plain, specific analysis anchored in this prompt’s facts.
- Specificity: At least two reasons must cite concrete prompt details (e.g., “€200M for 1,000 people/90 days…”, “50×50×20 m excavation…”, “214 federations in 18 months…”). One sentence per reason.
- Evidence discipline: Use only widely verifiable, non-fiction sources. Format each as:
  - "Case/Incident — Name (Year): one-line relevance."
  - "Law/Standard — Name (Year): one-line relevance."
  If you’re not ≥95% sure, omit it. Never guess, embellish, or cite fiction.
- Tone: Ruthless, specific, novel. Kill the premise; don’t fix it.
- Hygiene: Output strict JSON only (no trailing commas). Keep arrays concise. If no safe evidence exists, use "evidence": [].

GUARDRAILS
- Don’t moralize benign R&D by inventing harms; if the flaw is strategic, keep it strategic.
- Don’t propose alternatives, mitigations, or implementation steps.
- Avoid template language and buzzwords; every line must be uniquely earned by the prompt at hand.
"""

SYSTEM_PROMPT_DEFAULT = SYSTEM_PROMPT_1

@dataclass
class PremiseAttack:
    """
    Challenge the plan’s core premises.
    """
    system_prompt: str
    user_prompt: str
    response: dict
    metadata: dict

    @classmethod
    def execute(cls, llm: LLM, user_prompt: str) -> "PremiseAttack":
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        return cls.execute_with_system_prompt(llm, user_prompt, SYSTEM_PROMPT_DEFAULT.strip())

    @classmethod
    def execute_with_system_prompt(cls, llm: LLM, user_prompt: str, system_prompt: str) -> "PremiseAttack":
        if not isinstance(llm, LLM):
            raise ValueError("Invalid LLM instance.")
        if not isinstance(user_prompt, str):
            raise ValueError("Invalid user_prompt.")
        if not isinstance(system_prompt, str):
            raise ValueError("Invalid system_prompt.")

        logger.debug(f"User Prompt:\n{user_prompt}")

        chat_message_list = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_prompt),
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
        response_byte_count = len(chat_response.message.content.encode("utf-8"))
        logger.info(
            f"LLM chat interaction completed in {duration} seconds. "
            f"Response byte count: {response_byte_count}"
        )

        json_response = chat_response.raw.model_dump()

        metadata = dict(llm.metadata)
        metadata["llm_classname"] = llm.class_name()
        metadata["duration"] = duration
        metadata["response_byte_count"] = response_byte_count

        result = PremiseAttack(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=json_response,
            metadata=metadata,
        )
        return result

    def to_dict(
        self,
        include_metadata: bool = True,
        include_system_prompt: bool = True,
        include_user_prompt: bool = True,
    ) -> dict:
        d = self.response.copy()
        if include_metadata:
            d["metadata"] = self.metadata
        if include_system_prompt:
            d["system_prompt"] = self.system_prompt
        if include_user_prompt:
            d["user_prompt"] = self.user_prompt
        return d


if __name__ == "__main__":
    from planexe.llm_factory import get_llm
    from planexe.plan.find_plan_prompt import find_plan_prompt
    from planexe.prompt.prompt_catalog import PromptCatalog
    import random
    import itertools

    llm = get_llm("ollama-llama3.1")
    # llm = get_llm("openrouter-paid-gemini-2.0-flash-001")

    user_prompt_ids: list[str] = [
        "28289ed9-0c80-41cf-9d26-714bffe4e498",
        "5d0dd39d-0047-4473-8096-ea5eac473a57",
        "67c461a9-3364-42a4-bf8f-643315abfcf6",
        "762b64e2-5ac8-4684-807a-efd3e81d6bc1",
        "9c74bb8a-1208-4183-9c08-24ec90f86dfd",
        "a9113924-6148-4a0c-b72a-eecdb856e1e2",
        "aa2388ec-9916-4944-96bd-ab014de05bda",
        "ab700769-c3ba-4f8a-913d-8589fea4624e",
        "da8da7a6-954c-4f88-91c9-53f98a934868",
        "f206f7e9-8ece-4e65-8e7f-5ac1b6777a62",
    ]
    if True:
        prompt_catalog = PromptCatalog()
        prompt_catalog.load_simple_plan_prompts()
        user_prompt_ids = prompt_catalog.all_ids()[0:10]
        # user_prompt_ids = prompt_catalog.all_ids()
    print(f"Number of user prompts: {len(user_prompt_ids)}")

    system_prompts: list[tuple[str, str]] = [
        # ("SYSTEM_PROMPT_1", SYSTEM_PROMPT_1),
        # ("SYSTEM_PROMPT_2", SYSTEM_PROMPT_2),
        # ("SYSTEM_PROMPT_3", SYSTEM_PROMPT_3),
        # ("SYSTEM_PROMPT_4", SYSTEM_PROMPT_4),
        ("SYSTEM_PROMPT_5", SYSTEM_PROMPT_5),
    ]
    pairs = list(itertools.product(user_prompt_ids, system_prompts))
    random.seed(42)
    random.shuffle(pairs)
    count_all = len(pairs)
    pairs = pairs[:100]
    count_truncated = len(pairs)
    print(f"Number of prompts to run: {count_truncated}, all prompts: {count_all}")

    for i, (user_prompt_id, system_prompt_tuple) in enumerate(pairs, start=1):
        system_prompt_id, system_prompt = system_prompt_tuple
        print(f"Pair {i} of {len(pairs)}: system_prompt_id={system_prompt_id} user_prompt_id={user_prompt_id}")
        plan_prompt = find_plan_prompt(user_prompt_id)
        print(f"Query:\n{plan_prompt}")
        try:
            result = PremiseAttack.execute_with_system_prompt(llm, plan_prompt, system_prompt)
        except Exception as e:
            print(f"Error: {e}")
            continue
        json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False, include_metadata=False)
        print("Response:")
        print(json.dumps(json_response, indent=2))
        print("\n\n")
