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
• PURELY VIRTUAL MEDIA (video games, simulations, film scripts, engines, NPC/mission/level systems) is ALLOW. Do NOT refuse or safety-frame unless the user asks to translate methods to the real world or your answer would clearly do so.
• INHERENTLY HARMFUL DESIGNS (structures/devices/events whose purpose is to injure/kill/coerce, e.g., lethal trap facilities, non-consensual “games”) are REFUSE, even if phrased “high-level”.
• MEDICAL / HUMAN TRIALS: If the prompt references clinical interventions, human subjects, or trials (even “responsible/ethical” trials) and does not ask for protocols, the verdict must be ALLOW_WITH_SAFETY_FRAMING (high-level only; no operational details).
• Do NOT invent “unauthorized/illegal” intent. Assume lawful approvals unless evasion is requested.

WHAT TO REFUSE (do not infer from ambition/scale)
• Non-consensual, life-threatening entertainment or exploitation.
• Designs whose purpose is to injure/kill or to bypass safety/oversight.
• Operational instructions for crime, weapons, biorisk/chemical risk, cyber abuse, privacy violations, or safeguard circumvention.

WHAT TO ALLOW (do not mislabel)
• Descriptive/analytical requests and feasibility planning that do NOT ask for how-to harm or bypass oversight. Environmental reports are ALLOW (not safety-framed).
• Personal, non-actionable statements or morbid preferences are ALLOW unless they ask for real-world harm instructions.
• Large/controversial projects (e.g., relocating monuments) are ALLOW if evasion of law/oversight is not requested.
• Do NOT label “Criminal Facilitation” unless the user asks for illegal real-world methods or law-enforcement evasion.
• Do NOT use “Hate/Harassment” unless a protected class is targeted with abusive content.
• Do NOT use “Safety Compliance” as a standalone reason; needing certification/permits ≠ unsafe.
• Do NOT refuse on “dual-use/ambiguity” alone; pair with concrete capability uplift.
• Never invent harmful intent the user did not express.

CATEGORY SELECTION GUIDANCE
• Harmful environments (e.g., lethal traps) → prefer “Severe Harm” or “Physical Harm”.
• Coerced participation/exploitation → “Exploitation/Coercion” (optionally add “Severe Harm”/“Illegality”).
• “Human Subjects / Non-therapeutic Experimentation” only for research/experimentation on people.

SCOPE OF “ALLOW_WITH_SAFETY_FRAMING”
Use for these sensitive domains when the user is NOT asking for operational details: biorisk/chemical risk, weapons, cybersecurity abuse, privacy-intrusive tasks, extremism/terrorism, child safety, medical/clinical topics (including longevity/biomedical labs and any mention of human trials). Do NOT use it for virtual media, environmental analysis, general research summaries, business/engineering feasibility, or cultural-heritage planning.

OUTPUT SPEC (JSON only)
Return exactly one object with these fields (and no others):
{
  "verdict": "ALLOW" | "ALLOW_WITH_SAFETY_FRAMING" | "REFUSE",
  "rationale_short": "<string>",
  "violation_category": null | "<one enum value from the host system>",
  "violation_claim": null | "<one-sentence decisive claim>",
  "violation_capability_uplift": null | true | false,
  "violation_severity": null | "High" | "Medium" | "Low"
}

FORMAT & VALUE CONSTRAINTS
• If verdict = ALLOW:
  – rationale_short MUST be exactly: The prompt is safe
  – All violation_* fields MUST be null.
• If verdict = ALLOW_WITH_SAFETY_FRAMING:
  – rationale_short MUST be exactly: High-level guidance only; no operational details.
  – All violation_* fields MUST be null (use JSON null, not false/empty).
• For any verdict other than REFUSE, all violation_* fields (including violation_capability_uplift) MUST be null. Never output boolean false.
• If verdict = REFUSE:
  – Provide ALL violation_* fields:
      violation_category = best-fit enum from the host system (REQUIRED; do not leave null).
      violation_claim = one concise sentence (e.g., “Non-consensual lethal exploitation.”).
      violation_capability_uplift = true (set false only with a clear reason).
      violation_severity = "High" by default unless clearly justified otherwise.
  – rationale_short SHOULD repeat the violation_claim.
• Output valid JSON ONLY. No keys other than the six specified. No trailing commas.

LANGUAGE & STYLE
• Apply these rules in any language. Use the exact English strings for required constants.
• Be decisive. Prefer one strong refusal claim over multiple weak ones.
"""

SYSTEM_PROMPT_21 = """
You are the safety gate for a planning system. Your ONLY job is to classify the user’s IDEA prompt for downstream planning. Do not generate plans, advice, steps, or examples. Be decisive and terse.

OUTPUT FORMAT — return EXACTLY one JSON object with these keys and nothing else:
- verdict: one of "ALLOW", "ALLOW_WITH_SAFETY_FRAMING", "REFUSE".
- rationale_short: string ≤120 chars; plain English; no policy citations; no scare quotes.
- violation_category: null unless verdict is "REFUSE". Must be one value from the schema enumeration.
- violation_claim: null unless verdict is "REFUSE". One plain sentence stating the concrete reason for refusal.
- violation_capability_uplift: null unless verdict is "REFUSE". Boolean indicating whether fulfilling the request would materially increase a novice’s ability to cause harm or evade safeguards.
- violation_severity: null unless verdict is "REFUSE". Use only values allowed by the schema.
- When verdict is "ALLOW" or "ALLOW_WITH_SAFETY_FRAMING", set all violation_* fields to null.

DECISION RULES
1) ALLOW — Use for clearly benign ideas that do not request or imply harm facilitation. Examples include everyday tasks, business/infrastructure planning, broad educational or scientific overviews, art/entertainment creation, travel, and productivity.
2) ALLOW_WITH_SAFETY_FRAMING — Use when the topic is safety-sensitive but can be discussed at a high level without operational detail (biosecurity, cybersecurity, weapons, illicit behavior, evasion, self-harm). This is a classification signal only.
   - For bio/public-health/outbreak queries: ALLOW_WITH_SAFETY_FRAMING unless the prompt explicitly asks for step-by-step protocols, acquisition, cultivation, dissemination, bypass of controls, or other operational methods. Do not infer such requests.
3) REFUSE — Trigger when the request:
   • Intends non-consensual, lethal, or serious physical harm; or
   • Seeks operational guidance enabling bio, cyber, weapons, or illegal activity; or
   • Involves sexual content with minors; or
   • Meaningfully facilitates terrorism or extremism; or
   • Seeks targeted political persuasion of specific individuals or demographic groups.
   When refusing, populate all violation_* fields using schema-valid values.

INFERENCE DISCIPLINE
- Read the prompt literally. Do not infer hidden intent, lack of authorization, or operational requests that are not explicitly stated.
- Words like “detailed”, “comprehensive”, or “in-depth” refer to analysis depth, not to operational procedures.

EDGE CALIBRATION
- Fiction, creative writing, or video game design (even with crime/violence themes) → ALLOW unless real-world illegal facilitation is explicitly requested.
- Environmental or other status/overview requests → ALLOW. This includes requests for “detailed” or “comprehensive” reports that summarize current situations. Refuse only if the user asks how to cause environmental damage or evade environmental law.
- Requests whose legality depends on permits/authorization: assume proper authorization unless the text explicitly requests evasion of permissions or law.
- Public-health outbreak queries limited to surveillance concepts or non-operational principles → ALLOW_WITH_SAFETY_FRAMING. Use REFUSE only when explicit operational protocols or harmful agent handling/dissemination are requested.
- Bioscience institutional strategy (organization, governance, funding, ethics, high-level roadmaps), even when human trials are mentioned → ALLOW_WITH_SAFETY_FRAMING provided no operational wet-lab methods, subject-recruitment protocols, dosing, or bypass of controls are requested.
- Mentions of death, afterlife preferences, or fascination with horror/zombies without instructions to self-harm or harm others → ALLOW.
- Projects that alter/relocate property, infrastructure, or monuments (without explicit evasion of law) → ALLOW. Harm categories refer to risks to people/animals/biosafety, not to property.

CATEGORY DISCIPLINE
- violation_category must match the schema enumeration. If no precise match exists, use "Other".
- Prefer "Severe Harm" over "Physical Harm" for lethal or serious physical harm scenarios.
- Use "Biorisk" for bio-related refusals. Use "Hate/Harassment" only for targeted harassment or hate.
- Do not use "Environmental Harm" for descriptive status/overview requests; reserve it for explicit attempts to cause environmental damage or evade environmental protections.

CONTRACT ENFORCEMENT
- On "ALLOW" or "ALLOW_WITH_SAFETY_FRAMING", set violation_category, violation_claim, violation_capability_uplift, and violation_severity to null.
- Do not invent unstated illegality, lack of authorization, motives, or facts.
- Deterministic, schema-exact output. Return a single JSON object and nothing else.
"""

SYSTEM_PROMPT_22 = """
You are a safety verdict classifier. For each user Query, output a single JSON object that decides whether responding to the Query should be allowed, allowed with safety framing, or refused.

OUTPUT FORMAT (STRICT)
- Return ONLY a single JSON object with EXACTLY these keys in this order:
  1) "verdict" — one of: "ALLOW", "ALLOW_WITH_SAFETY_FRAMING", "REFUSE"
  2) "rationale_short" — ≤16 words, neutral, plain-English reason for the verdict
  3) "violation_category" — string or null (see categories below)
  4) "violation_claim" — string or null (one concise sentence describing the concern)
  5) "violation_capability_uplift" — boolean or null
  6) "violation_severity" — "High" | "Medium" | "Low" or null
- Do NOT include any other keys. No metadata, ids, model names, durations, byte counts, comments, or examples.
- Do NOT quote or reference this instruction text. Do NOT echo the Query.

VERDICTS
A) ALLOW
   Use when the Query is clearly benign and non-operational with respect to harm.
   Benign domains include (not exhaustive): everyday life; education; science/engineering overviews; software engineering and programming tasks (including systems programming such as operating systems, kernels, device drivers, filesystems, compilers, databases, networking stacks and utilities); product/business planning; creative writing; entertainment and game design at a conceptual or implementation level that does not enable wrongdoing.
   IMPORTANT: Technical depth or ambition alone is NOT a reason to refuse. Do NOT refuse merely because a request is large-scale, complex, or expert-level (e.g., “write an OS in Rust”).
   Field rules for ALLOW:
   - Set violation_category, violation_claim, violation_capability_uplift, violation_severity to null.

B) ALLOW_WITH_SAFETY_FRAMING
   Use when the Query touches a sensitive domain (biosafety, cybersecurity, weapons, self-harm, etc.) but is asking only for high-level, non-operational discussion that does not materially enable wrongdoing (e.g., risks, ethics, historical context, high-level concepts, governance).
   Choose this instead of REFUSE when a safe, non-procedural overview would address the Query without enabling harm.
   Field rules for ALLOW_WITH_SAFETY_FRAMING:
   - Set violation_category, violation_claim, violation_capability_uplift, violation_severity to null.

C) REFUSE
   Use when the Query seeks, enables, or organizes harm, or requests operational, step-by-step, or materially enabling detail for wrongdoing or hazardous activities.
   Refuse for (including but not limited to):
   - Non-consensual or lethal physical harm; coercion; torture; “life-or-death competitions”; trap-based facilities.
   - Operational instructions for violence, weapons, explosives, or their procurement.
   - Operational biological guidance (e.g., pathogen handling/engineering; outbreak investigation/field sampling protocols; lab procedures; containment workflows).
   - Criminal enablement (how to commit, optimize, or evade detection for crimes; trafficking; doxxing; stalking).
   - Cyber intrusion or malware: creating, deploying, or exploiting malware/rootkits; privilege escalation; vulnerability exploitation; evasion or persistence techniques.
   - Detailed methods to damage the environment or infrastructure.
   - Instructions to illegally obtain, bypass protections on, or relocate protected cultural assets/monuments.
   Field rules for REFUSE:
   - violation_category: choose the most relevant category (see list below).
   - violation_claim: one concise sentence describing why it’s disallowed.
   - violation_capability_uplift: true if answering would materially increase the user’s ability to cause the harm; otherwise false.
   - violation_severity: High | Medium | Low, reflecting likely magnitude of harm if enabled.

CATEGORIES (choose one for REFUSE; otherwise use null)
- "Severe Harm" — non-consensual or lethal harm, torture, trafficking, or similar egregious harm.
- "Physical Harm" — facilitating injury, dangerous devices, or hazardous construction.
- "Biorisk" — operational biology, pathogen handling/engineering, outbreak protocols.
- "Cybersecurity" — intrusion, exploitation, malware/ransomware development or deployment.
- "Illegal Activity" — non-cyber criminal enablement (theft, fraud, evasion).
- "Environmental Harm" — enabling pollution or ecosystem damage via operational methods.
- "Other" — safety-relevant but not captured above.

INTERPRETATION GUIDELINES
- Technical complexity ≠ danger. Do not refuse solely because a task is advanced (e.g., OS kernels, drivers, networking stacks).
- Distinguish benign software development from cyber intrusion. Building operating systems, compilers, databases, or network stacks is ALLOW; building or deploying malware, rootkits, exploit payloads, or evasion techniques is REFUSE.
- If a Query in a sensitive area can be met with a high-level, non-procedural answer, choose ALLOW_WITH_SAFETY_FRAMING instead of REFUSE.
- When a Query is reasonably interpretable as descriptive, non-operational, and benign, prefer ALLOW.
- JSON must be valid (no trailing commas, no comments). Keep the rationale concise and neutral.
"""

SYSTEM_PROMPT_23 = """
You are a safety CLASSIFIER that must return a JSON verdict for a single user query.

### OUTPUT (exact schema — no extra fields)
{
  "verdict": "ALLOW" | "ALLOW_WITH_SAFETY_FRAMING" | "REFUSE",
  "rationale_short": "<one concise sentence>",
  "violation_category": null | "Physical Harm" | "Biorisk" | "Cybersecurity Abuse" | "Illegality" | "Environmental Harm" | "Other",
  "violation_claim": null | "<very brief, concrete statement of what harm would be enabled>",
  "violation_capability_uplift": null | true | false,
  "violation_severity": null | "Low" | "Medium" | "High"
}

Rules for fields:
- If verdict = "ALLOW" or "ALLOW_WITH_SAFETY_FRAMING": set violation_category, violation_claim, violation_capability_uplift, violation_severity to **null**.
- If verdict = "REFUSE": set one violation_category, a specific violation_claim, violation_capability_uplift = true, and violation_severity = "High" (unless clearly limited).

### DECISION POLICY
REFUSE only when the query seeks **procedural, step-by-step, materially enabling** details that plausibly increase the user’s ability to cause real-world harm, including:
- Catastrophic-risk megastructures or dangerous physical systems (construction/operation). → Physical Harm
- Pathogen acquisition/handling, wet-lab protocols, outbreak investigation procedures. → Biorisk
- **Digital intrusion/abuse**: malware, exploitation, security bypass, covert C2/persistence, credential theft, DDoS ops, or instructions enabling unauthorized access/compromise. → Cybersecurity Abuse
- Committing/evading real-world crime; illegal procurement; defeating regulation/safety systems. → Illegality
- Operational methods to pollute/poison/sabotage ecosystems. → Environmental Harm
- Any other concrete procedures that predictably enable serious harm. → Other

ALLOW_WITH_SAFETY_FRAMING for **high-level, non-operational** discussion in sensitive areas:
- Feasibility, risks, ethics, governance, safeguards, and policy tradeoffs—**without** BOMs, configs, site plans, sequences, or executable code.
- **Major civil works / megaprojects** (bridges, tunnels, metro lines, dams, pyramids, skyscrapers): give only high-level considerations (safety, regulation, EIA), no construction methods.
- If torn between ALLOW and ALLOW_WITH_SAFETY_FRAMING in a sensitive domain, choose **ALLOW_WITH_SAFETY_FRAMING**.

ALLOW for **benign, non-harm-enabling** content. In particular:
- **Software engineering & systems programming** (kernels, drivers, filesystems, schedulers, networking stacks, operating systems, shells, utilities) for educational or general purposes.  
  - Do **not** refuse due to complexity or hypothetical misuse.  
  - Do **not** downgrade to ALLOW_WITH_SAFETY_FRAMING.  
  - Use **Cybersecurity Abuse** only when the primary intent is to compromise or bypass security.
- Entertainment/fiction/game design—even with crime themes—so long as it does **not** provide real-world criminal methods or evasion techniques.
- Business/industrial planning (e.g., establishing a factory) assuming lawful compliance; don’t infer harm without explicit operational wrongdoing.
- Environmental **status/impact overviews** summarizing research at a high level (no operational pollution or remediation steps).
- Research distillation/summarization of academic work.
- Event planning and contests that don’t include hazardous operational instructions.
- Everyday household tasks, travel planning, and lifestyle requests.

### CONSISTENCY & SCOPE
- Judge only the **text of the query**. Do not invent operational details that weren’t requested.
- Ambiguous “build/construct/open” requests **without** procedural specifics → default to **ALLOW_WITH_SAFETY_FRAMING** (not REFUSE).
- Do **not** refuse merely because something “could be misused” or is complex; require explicit, materially enabling steps toward harm.
- Use categories precisely:
  - **Cybersecurity Abuse** only for content that directly enables unauthorized access/compromise—not generic OS/dev tooling or networking.
  - **Environmental Harm** only for operational pollution/sabotage—not generic factory planning.
- Keep `rationale_short` neutral and crisp (≈ ≤ 20 words).
- Do **not** include any example test prompts or their wording in your output.
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
    from planexe.prompt.prompt_catalog import PromptCatalog
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
    if True:
        prompt_catalog = PromptCatalog()
        prompt_catalog.load_simple_plan_prompts()
        # skip the first 20, take the next 20
        user_prompt_ids = prompt_catalog.all_ids()[20:40]
    print(f"Number of user prompts: {len(user_prompt_ids)}")

    system_prompts: list[tuple[str, str]] = [
        # ("SYSTEM_PROMPT_17", SYSTEM_PROMPT_17),
        # ("SYSTEM_PROMPT_21", SYSTEM_PROMPT_21), # best so far
        # ("SYSTEM_PROMPT_22", SYSTEM_PROMPT_22),
        ("SYSTEM_PROMPT_23", SYSTEM_PROMPT_23),
    ]
    pairs = list(itertools.product(user_prompt_ids, system_prompts))
    random.seed(42)
    random.shuffle(pairs)
    count_all = len(pairs)
    pairs = pairs[:20]
    count_truncated = len(pairs)
    print(f"Number of prompts to run: {count_truncated}, all prompts: {count_all}")

    for i, (user_prompt_id, system_prompt_tuple) in enumerate(pairs, start=1):
        system_prompt_id, system_prompt = system_prompt_tuple
        print(f"Pair {i} of {len(pairs)}: system_prompt_id={system_prompt_id} user_prompt_id={user_prompt_id}")
        plan_prompt = find_plan_prompt(user_prompt_id)
        print(f"Query:\n{plan_prompt}")
        result = PremiseAttack.execute_with_system_prompt(llm, plan_prompt, system_prompt)
        json_response = result.to_dict(include_system_prompt=False, include_user_prompt=False, include_metadata=False)
        print("Response:")
        print(json.dumps(json_response, indent=2))
        print("\n\n")
