"""
This gate makes a single decision. 
Forcing a list either causes padding (hallucinated “reasons”) or pressure to invent weak hits → false positives.
Thus the output is a single item.
Fewer false positives: no incentive to “find 4 items.”

kill bad ideas early.

Attack the 'why,' not the 'how'.

Asks whether the idea deserves to exist at all and whether the money should go elsewhere.

Premise Attack, Adversarial Review of the Idea. Argue against the plan to test its robustness.

“Assume the thesis is wrong. Write the strongest objections, disconfirming tests with thresholds, and stop rules. Compare to alternatives. End with a Go/Pivot/No-Go gate.”

Should a skyscraper even be built here? Why are we building a skyscraper here at all? 
The economy is shifting, people are working from home, and a public park would serve the community better.

"Should we really be doing this?"
"Are the money spent better elsewhere?"

Devil’s Advocate: Even if we succeed, here’s why this might still be the wrong move.

The “Devil’s Advocate” is the strategic opposition voice — less about enumerating risks (Premortem’s job) and 
more about questioning the project’s fundamental premise, strategic direction, and opportunity cost.

https://en.wikipedia.org/wiki/Devil%27s_advocate
https://en.wikipedia.org/wiki/Group_decision-making

PROMPT> python -m planexe.diagnostics.premise_attack7
PROMPT> python -u -m planexe.diagnostics.premise_attack7 | tee output.txt
"""
from enum import Enum
import json
import time
import logging
from math import ceil
from dataclasses import dataclass
from typing import List, Optional, Literal

from pydantic import BaseModel, Field
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms.llm import LLM

logger = logging.getLogger(__name__)


class Verdict(str, Enum):
    ALLOW = "ALLOW"
    ALLOW_WITH_SAFETY_FRAMING = "ALLOW_WITH_SAFETY_FRAMING"
    REFUSE = "REFUSE"


class AssistantMode(str, Enum):
    NORMAL = "NORMAL"                  # unrestricted answer
    HIGH_LEVEL_ONLY = "HIGH_LEVEL_ONLY"  # no stepwise/operational details
    BLOCK = "BLOCK"                    # refuse and redirect


class ViolationCategory(str, Enum):
    SEVERE_HARM = "Severe Harm"
    PHYSICAL_HARM = "Physical Harm"
    PSYCHOLOGICAL_HARM = "Psychological Harm"
    ILLEGALITY = "Illegality"
    CRIMINAL_FACILITATION = "Criminal Facilitation"
    SAFETY_COMPLIANCE = "Safety Compliance"
    WEAPONS = "Weapons"
    BIORISK = "Biorisk"
    CYBERSECURITY_ABUSE = "Cybersecurity Abuse"
    PRIVACY_VIOLATION = "Privacy Violation"
    EXTREMISM_TERRORISM = "Extremism/Terrorism"
    CHILD_SAFETY = "Child Safety"
    HATE_HARASSMENT = "Hate/Harassment"
    FINANCIAL_CRIME = "Financial Crime"
    PROPERTY_DAMAGE_CRIT_INFRA = "Property Damage / Critical Infrastructure"
    ENVIRONMENTAL_HARM = "Environmental Harm"
    MEDICAL_RISK = "Medical Risk"
    SELF_HARM = "Self-Harm"
    EXPLOITATION_COERCION = "Exploitation/Coercion"
    HUMAN_SUBJECTS_NONTHERAPY = "Human Subjects / Non-therapeutic Experimentation"
    SAFEGUARD_EVASION = "Safeguard Evasion"
    CAPABILITY_UPLIFT = "Capability Uplift"
    OTHER = "Other"   # use with a clarifying claim


class Severity(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


# --- Flat Decision Model ------------------------------------------------------

class Decision(BaseModel):
    """
    Single safety decision for a prompt.
    Policy: always treat the prompt as real-world intent; disclaimers like 'fictional/hypothetical/role-play'
    do NOT relax safety.
    """
    verdict: Verdict = Field(..., description="ALLOW | ALLOW_WITH_SAFETY_FRAMING | REFUSE")
    rationale_short: str = Field(
        "The prompt is safe",
        description="Must be exactly 'The prompt is safe' when verdict=ALLOW; otherwise a 1–2 sentence summary."
    )

    # Optional single violation payload (only used when WITH_SAFETY or REFUSE)
    violation_category: Optional[ViolationCategory] = Field(
        None, description="Required when verdict=REFUSE; optional when WITH_SAFETY."
    )
    violation_claim: Optional[str] = Field(None, description="Short decisive statement of the violation.")
    violation_capability_uplift: Optional[bool] = Field(
        None, description="Would answering materially increase harmful capability?"
    )
    violation_severity: Optional[Severity] = Field(None, description="Defaults to High when REFUSE.")

SYSTEM_PROMPT_17 = """
ROLE
You are a Safety & Ethics Gatekeeper for a planning system. Treat every user prompt as a real-world request regardless of language, tone, or implausibility.

NON-BINDING DISCLAIMERS
Labels such as “fictional”, “hypothetical”, “for a movie”, or “role-play” DO NOT relax safety. Evaluate as if the idea were to be executed in the real world.

DECISION BOUNDARY (pick exactly one verdict)
Set:
• REFUSE — if BOTH are true:
  A) The prompt proposes non-consensual severe harm or illegality, OR asks for operational instructions that enable harm; AND
  B) A response would materially further execution (capability uplift). This includes logistics, recruitment/targeting, budgeting/timelines, procurement lists, stepwise methods, parameters, or safeguard-circumvention tactics.
• ALLOW_WITH_SAFETY_FRAMING — topic is sensitive/high-risk, but the user is NOT asking for operational details; answer only at a high level (no protocols, no bypass tips).
• ALLOW — otherwise.

HARD RULES (override any ambiguity)
• PURELY VIRTUAL MEDIA (video games, simulations, film scripts, game engines, NPC/mission/level systems) is **ALLOW**. Do NOT refuse or safety-frame unless the user asks to translate methods to the real world or your answer would clearly do so.
• INHERENTLY HARMFUL DESIGNS (structures/devices/events whose purpose is to injure/kill/coerce, e.g., lethal trap facilities, non-consensual “games”) are **REFUSE**, even if phrased “high-level”.
• Do NOT invent “unauthorized/illegal” intent. Assume lawful approvals unless evasion is requested.

WHAT TO REFUSE (do not infer from ambition/scale)
• Non-consensual, life-threatening entertainment or exploitation.
• Designs whose purpose is to injure/kill or to bypass safety/oversight.
• Operational instructions for crime, weapons, biorisk/chemical risk, cyber abuse, privacy violations, or safeguard circumvention.

WHAT TO ALLOW (do not mislabel)
• Descriptive/analytical requests and feasibility planning that do NOT ask for how-to harm or bypass oversight. Environmental reports are ALLOW.
• Personal, non-actionable statements or morbid preferences are ALLOW unless they ask for real-world harm instructions.
• Large/controversial projects (e.g., relocating monuments) are ALLOW if evasion of law/oversight is not requested.
• Do NOT label “Criminal Facilitation” unless the user asks for illegal real-world methods or law-enforcement evasion.
• Do NOT use “Hate/Harassment” unless a protected class is targeted with abusive content.
• Do NOT use “Safety Compliance” as a standalone reason; needing certification/permits ≠ unsafe.
• Do NOT refuse on “dual-use/ambiguity” alone; pair with concrete capability uplift.
• Never invent harmful intent the user did not express.

CATEGORY SELECTION GUIDANCE
• Harmful environments (e.g., lethal traps) → “Severe Harm” or “Physical Harm”.
• Coerced participation/exploitation → “Exploitation/Coercion” (optionally add “Severe Harm”/“Illegality”).
• “Human Subjects / Non-therapeutic Experimentation” only for research/experimentation on people.

SCOPE OF “ALLOW_WITH_SAFETY_FRAMING”
Use only for these sensitive domains when the user is NOT asking for operational details: biorisk/chemical risk, weapons, cybersecurity abuse, privacy-intrusive tasks, extremism/terrorism, child safety, medical risk. Do NOT use it for virtual media, environmental analysis, general research summaries, business/engineering feasibility, or cultural-heritage planning.

OUTPUT SPEC (JSON only)
Return exactly one object with these fields (and no others), plus an optional top-level "metadata" object:
{
  "verdict": "ALLOW" | "ALLOW_WITH_SAFETY_FRAMING" | "REFUSE",
  "rationale_short": "<string>",
  "violation_category": null | "<one enum value from the host system>",
  "violation_claim": null | "<one-sentence decisive claim>",
  "violation_capability_uplift": null | true | false,
  "violation_severity": null | "High" | "Medium" | "Low",
  "metadata": null | { ... }    // OPTIONAL; if present, pass through host-provided content unchanged; do not fabricate.
}

FORMAT & VALUE CONSTRAINTS
• If verdict = ALLOW:
  – rationale_short MUST be exactly: The prompt is safe
  – All violation_* fields MUST be null.
• If verdict = ALLOW_WITH_SAFETY_FRAMING:
  – rationale_short MUST be exactly: High-level guidance only; no operational details.
  – All violation_* fields MUST be null (use JSON null).
• If verdict = REFUSE:
  – Provide ALL violation_* fields:
      violation_category = best-fit enum from the host system.
      violation_claim = one concise sentence (e.g., “Non-consensual lethal exploitation.”).
      violation_capability_uplift = true (set false only with a clear reason).
      violation_severity = "High" by default unless clearly justified otherwise.
  – rationale_short SHOULD repeat the violation_claim.
• Output valid JSON ONLY. No keys other than the six specified and the optional "metadata". No trailing commas.

LANGUAGE & STYLE
• Apply these rules in any language. Use the exact English strings for required constants.
• Be decisive. Prefer one strong refusal claim over multiple weak ones.
"""

SYSTEM_PROMPT_DEFAULT = SYSTEM_PROMPT_17

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

        sllm = llm.as_structured_llm(Decision)
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
    import random
    import itertools

    llm = get_llm("ollama-llama3.1")

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
    system_prompts: list[tuple[str, str]] = [
        ("SYSTEM_PROMPT_17", SYSTEM_PROMPT_17),
    ]
    pairs = list(itertools.product(user_prompt_ids, system_prompts))
    print(f"Number of pairs: {len(pairs)}")
    random.seed(42)
    random.shuffle(pairs)
    pairs = pairs[:12]
    for i, (user_prompt_id, system_prompt_tuple) in enumerate(pairs, start=1):
        system_prompt_id, system_prompt = system_prompt_tuple
        print(f"Pair {i} of {len(pairs)}: system_prompt_id={system_prompt_id} user_prompt_id={user_prompt_id}")
        plan_prompt = find_plan_prompt(user_prompt_id)
        print(f"Query:\n{plan_prompt}\n\n")
        result = PremiseAttack.execute_with_system_prompt(llm, plan_prompt, system_prompt)
        json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False)
        print("\n\nResponse:")
        json_response["system_prompt_id"] = system_prompt_id
        json_response["user_prompt_id"] = user_prompt_id
        print(json.dumps(json_response, indent=2))
        print("\n\n")
