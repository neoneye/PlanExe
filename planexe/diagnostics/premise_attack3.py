
"""
Premise Attack: adversarial gate to kill bad ideas early.

Standardized checklist.

- Asks whether the idea deserves to exist at all.
- Forces counterfactuals and opportunity cost.
- Deterministic decision rules (stop on critical fail; alternative dominance).

PROMPT> python -m planexe.diagnostics.premise_attack3 --brief-file /absolute/path/to/plan.txt
"""

from __future__ import annotations

from typing import List, Optional, Any, Dict, Tuple
from dataclasses import dataclass, field, asdict
import json
import math
import re

# -----------------------------
# Data models
# -----------------------------
@dataclass
class PAItem:
    id: str
    category: str
    question: str
    status: str              # "Pass" | "Fail" | "Unknown"
    severity_5: int
    rationale: Optional[str] = None
    notes: Optional[str] = None
    owner: Optional[str] = None
    evidence_links: List[str] = field(default_factory=list)

@dataclass
class PACandidate:
    id: str                 # "P" for project; "A1"/"A2"/... for alternatives
    name: str
    total_cost: float
    delta_outcome: float
    cost_per_outcome: float
    meets_constraints: bool = True
    assumptions: Optional[str] = None

@dataclass
class PAOppCost:
    primary_outcome_metric: str
    candidates: List[PACandidate] = field(default_factory=list)

@dataclass
class PADecisionRules:
    stop_on_critical_fail: bool = True
    min_score_to_proceed: float = 70.0
    alt_dominance_threshold: float = 25.0  # percent advantage required to overrule

@dataclass
class PAScores:
    critical_failed: int = 0
    skepticism_score_100: float = 0.0

@dataclass
class PremiseAttackResult:
    items: List[PAItem]
    opportunity_cost: PAOppCost
    decision_rules: PADecisionRules = field(default_factory=PADecisionRules)
    scores: PAScores = field(default_factory=PAScores)
    decision: str = "Do NOT proceed"
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None
    raw_model_text: Optional[str] = None

    def to_dict(self, include_system_prompt: bool = False, include_user_prompt: bool = False) -> Dict[str, Any]:
        d = {
            "items": [asdict(x) for x in self.items],
            "opportunity_cost": {
                "primary_outcome_metric": self.opportunity_cost.primary_outcome_metric,
                "candidates": [asdict(c) for c in self.opportunity_cost.candidates],
            },
            "decision_rules": asdict(self.decision_rules),
            "scores": asdict(self.scores),
            "decision": self.decision,
        }
        if include_system_prompt:
            d["system_prompt"] = self.system_prompt
        if include_user_prompt:
            d["user_prompt"] = self.user_prompt
        if self.raw_model_text is not None:
            d["raw_model_text"] = self.raw_model_text
        return d

# -----------------------------
# Core logic
# -----------------------------
CRITICAL_IDS = ("C1","C2","C3","C4","C5","C6","C7","C8")

CRITICAL_QUESTIONS = [
    ("C1", "Public value", "What non-private value does this create, and for whom? Who pays? Evidence?"),
    ("C2", "Problem–solution fit", "Is this the cheapest way to solve the actual problem? What is the problem metric?"),
    ("C3", "Counterfactual impact", "If we did nothing, what happens? If we spent the same money on the top alternative, what happens?"),
    ("C4", "Strategic fit", "Does this align with top-level strategy and constraints (capital, risk, talent)?"),
    ("C5", "Legitimacy & license", "Is there credible social, legal, political license? Any veto players?"),
    ("C6", "Irreversibility", "What becomes hard to reverse (sunk CAPEX, lock-ins)? What is the exit plan?"),
    ("C7", "Execution sanity", "Do we have the team, supply chain, timing? If a key actor vanishes, can we still deliver?"),
    ("C8", "Measurable success", "What single north-star outcome decides success? What threshold equals 'kill it'?"),
]

HIGH_VALUE_QUESTIONS = [
    ("H1", "Evidence quality", "Is the case based on data from comparable contexts? What is the weakest link?"),
    ("H2", "Simplicity", "Can a simpler variant deliver ~80% of value for ~20% of cost?"),
    ("H3", "Hidden coupling", "What breaks elsewhere (ops, security, compliance, PR, dependencies)?"),
    ("H4", "Time value", "Why now? What valuable option do we lose by committing early?"),
    ("H5", "Failure surface", "Top 3 failure modes; tripwires; pre-authorized rollback."),
    ("H6", "Distributional effects", "Who is harmed or politically mobilized against us?"),
    ("H7", "Scalability", "If it works, can we scale without unit economics collapsing?"),
]

def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def compute_scores(items: List[PAItem]) -> PAScores:
    critical_failures = sum(1 for it in items if it.id in CRITICAL_IDS and it.status == "Fail" and it.severity_5 >= 4)
    noncritical_fails = sum(1 for it in items if it.id not in CRITICAL_IDS and it.status == "Fail")
    unknown_weight = sum(it.severity_5 for it in items if it.status == "Unknown")
    skepticism = 100 - (10 * critical_failures) - (3 * noncritical_fails) - (0.5 * unknown_weight)
    return PAScores(critical_failed=critical_failures, skepticism_score_100=max(0.0, round(skepticism, 1)))

def violates_alt_rule(opp: PAOppCost, rules: PADecisionRules) -> bool:
    P = next((c for c in opp.candidates if c.id == "P"), None)
    if not P:
        return True  # no baseline = reject
    if (P.cost_per_outcome in (None, 0)) and P.delta_outcome not in (None, 0):
        try:
            P.cost_per_outcome = P.total_cost / P.delta_outcome
        except Exception:
            pass
    if not isinstance(P.delta_outcome, (int, float)) or P.delta_outcome <= 0:
        return True
    thresh = 1 - rules.alt_dominance_threshold / 100.0
    for a in opp.candidates:
        if a.id == "P" or not a.meets_constraints:
            continue
        if (a.cost_per_outcome in (None, 0)) and a.delta_outcome not in (None, 0):
            try:
                a.cost_per_outcome = a.total_cost / a.delta_outcome
            except Exception:
                continue
        try:
            if a.delta_outcome > 0 and a.cost_per_outcome < P.cost_per_outcome * thresh:
                return True
        except Exception:
            continue
    return False

def decide(items: List[PAItem], opp: PAOppCost, rules: PADecisionRules) -> Tuple[PAScores, str]:
    scores = compute_scores(items)
    if rules.stop_on_critical_fail and scores.critical_failed > 0:
        return scores, "Do NOT proceed"
    if scores.skepticism_score_100 < rules.min_score_to_proceed:
        return scores, "Do NOT proceed"
    if violates_alt_rule(opp, rules):
        return scores, "Do NOT proceed"
    return scores, "Proceed"

# -----------------------------
# LLM integration & JSON sanitization
# -----------------------------
def _call_llm(llm: Any, prompt: str) -> str:
    # direct complete
    if hasattr(llm, "complete"):
        try:
            r = llm.complete(prompt)
            if hasattr(r, "text"):
                return r.text
            return str(r)
        except Exception:
            pass
    # predict
    if hasattr(llm, "predict"):
        try:
            r = llm.predict(prompt)
            return str(r)
        except Exception:
            pass
    # chat (LlamaIndex)
    try:
        from llama_index.core.llms import ChatMessage, MessageRole  # type: ignore
        msgs = [
            ChatMessage(role=MessageRole.SYSTEM, content="You are a rigorous analyst. Output JSON only."),
            ChatMessage(role=MessageRole.USER, content=prompt),
        ]
        r = llm.chat(msgs)
        if hasattr(r, "message") and hasattr(r.message, "content"):
            return r.message.content
        if hasattr(r, "text"):
            return r.text
        return str(r)
    except Exception:
        return ""

def _strip_code_fences(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S|re.I)
    return m.group(1).strip() if m else text

def _sanitize_jsonish(text: str) -> str:
    if not text:
        return ""
    t = _strip_code_fences(text)

    # Remove // line comments
    t = re.sub(r"(?m)\s*//.*$", "", t)
    # Remove /* ... */ block comments
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)

    # Evaluate bare arithmetic expressions used as values (e.g., 5000 / -10)
    def eval_expr(m):
        expr = m.group(1)
        try:
            if re.fullmatch(r"[\d\s\(\)\+\-\*/\.eE]+", expr):
                val = eval(expr, {"__builtins__": None}, {})
                return f": {val}{m.group(2)}"
        except Exception:
            pass
        return f": 0{m.group(2)}"

    t = re.sub(r":\s*([\d\s\(\)\+\-\*/\.eE]+)\s*(,|\})", eval_expr, t)

    # Remove trailing commas before } or ]
    t = re.sub(r",\s*(?=[\]\}])", "", t)

    return t

def _extract_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    # raw
    try:
        return json.loads(text)
    except Exception:
        pass
    # first brace block attempts
    m = re.search(r"\{.*\}", text, flags=re.S)
    if m:
        block = m.group(0)
        for candidate in (block, _sanitize_jsonish(block), _sanitize_jsonish(text)):
            try:
                return json.loads(candidate)
            except Exception:
                continue
    # final attempt
    try:
        return json.loads(_sanitize_jsonish(text))
    except Exception:
        return {}

# -----------------------------
# Coercion & normalization
# -----------------------------
def _coerce_items(raw_items: Any) -> List[PAItem]:
    items: List[PAItem] = []
    for it in (raw_items or []):
        try:
            status = str(it.get("status","Unknown")).strip().capitalize()
            items.append(PAItem(
                id=str(it.get("id","")).strip(),
                category=str(it.get("category","")).strip(),
                question=str(it.get("question","")).strip(),
                status=status if status in ("Pass","Fail","Unknown") else "Unknown",
                severity_5=int(it.get("severity_5", 3)),
                rationale=it.get("rationale"),
                notes=it.get("notes"),
                owner=it.get("owner"),
                evidence_links=[str(x) for x in it.get("evidence_links", [])]
            ))
        except Exception:
            continue
    if not items:
        for qid, cat, q in CRITICAL_QUESTIONS:
            items.append(PAItem(id=qid, category=cat, question=q, status="Unknown", severity_5=5))
        for qid, cat, q in HIGH_VALUE_QUESTIONS:
            items.append(PAItem(id=qid, category=cat, question=q, status="Unknown", severity_5=3))
    return items

def _coerce_opp(raw_opp: Any, fallback_metric: str = "€ per primary outcome unit") -> PAOppCost:
    metric = str((raw_opp or {}).get("primary_outcome_metric") or fallback_metric)
    cands: List[PACandidate] = []
    for c in (raw_opp or {}).get("candidates", []):
        total_cost = _safe_float(c.get("total_cost", 0.0))
        delta = _safe_float(c.get("delta_outcome", 0.0), default=1.0)
        cost_per = c.get("cost_per_outcome", None)
        try:
            cost_per = float(cost_per)
        except Exception:
            # compute later
            cost_per = None
        cands.append(PACandidate(
            id=str(c.get("id","")).strip() or f"A{len(cands)+1}",
            name=str(c.get("name","")).strip() or "Alternative",
            total_cost=total_cost,
            delta_outcome=delta,
            cost_per_outcome=(cost_per if cost_per is not None else (total_cost / delta if delta else 0.0)),
            meets_constraints=bool(c.get("meets_constraints", True)),
            assumptions=c.get("assumptions"),
        ))
    if not any(c.id == "P" for c in cands):
        cands.insert(0, PACandidate(id="P", name="Proposed Project", total_cost=0.0, delta_outcome=1.0, cost_per_outcome=0.0))
    # Normalize
    for c in cands:
        try:
            if (c.cost_per_outcome in (None, 0)) and c.delta_outcome not in (None, 0):
                c.cost_per_outcome = c.total_cost / c.delta_outcome
        except Exception:
            pass
        if not isinstance(c.delta_outcome, (int, float)) or c.delta_outcome <= 0:
            c.meets_constraints = False
    return PAOppCost(primary_outcome_metric=metric, candidates=cands)

# -----------------------------
# Public API
# -----------------------------
PROMPT_TEMPLATE = """You are performing a *Premise Attack*—an adversarial review that decides whether a proposed project should proceed at all.

PROJECT BRIEF (verbatim):
---
{brief}
---

TASK:
1) Evaluate the project using the **Critical** questions C1–C8 (below) and **High-Value** questions H1–H7.
2) Propose 2–3 plausible alternatives (include a simpler/cheaper variant and a do-nothing baseline).
3) Choose ONE primary outcome metric and estimate ΔOutcome and costs enough to compute cost_per_outcome for P (project) and alternatives.

CRITICAL QUESTIONS:
{critical_questions}

HIGH-VALUE QUESTIONS:
{high_value_questions}

REQUIRED OUTPUT (STRICT JSON, no commentary):
{{
  "items": [  // C1..C8 then H1..H7 in order
    {{
      "id": "C1",
      "category": "Public value",
      "question": "What non-private value does this create, and for whom? Who pays? Evidence?",
      "status": "Pass|Fail|Unknown",
      "severity_5": 1,
      "rationale": "Brief reasoning",
      "notes": "Optional notes",
      "owner": "Role best suited to resolve",
      "evidence_links": ["https://..."]
    }}
  ],
  "opportunity_cost": {{
    "primary_outcome_metric": "STRING",
    "candidates": [
      {{ "id": "P", "name": "Proposed Project", "total_cost": 0, "delta_outcome": 0, "cost_per_outcome": 0, "meets_constraints": true, "assumptions": "STRING" }},
      {{ "id": "A1", "name": "Cheaper Variant", "total_cost": 0, "delta_outcome": 0, "cost_per_outcome": 0, "meets_constraints": true, "assumptions": "STRING" }},
      {{ "id": "A2", "name": "Do-Nothing Baseline", "total_cost": 0, "delta_outcome": 0, "cost_per_outcome": 0, "meets_constraints": true, "assumptions": "STRING" }}
    ]
  }}
}}

NOTES:
- If data is insufficient, set "status": "Unknown" and assign "severity_5" appropriate to risk.
- Do NOT include comments or trailing commas; output valid JSON only.
- Ensure numbers allow computing cost_per_outcome = total_cost / delta_outcome (avoid division by zero).
"""

def _build_prompt(brief: str) -> str:
    crit = "\n".join([f"{qid}: {q}" for qid, _, q in CRITICAL_QUESTIONS])
    high = "\n".join([f"{qid}: {q}" for qid, _, q in HIGH_VALUE_QUESTIONS])
    return PROMPT_TEMPLATE.format(brief=brief.strip(), critical_questions=crit, high_value_questions=high)

class PremiseAttack:
    @staticmethod
    def execute(llm: Any,
                brief: str,
                primary_outcome_metric: str = "€ per additional active user (30-day)",
                decision_rules: Optional[PADecisionRules] = None) -> PremiseAttackResult:
        decision_rules = decision_rules or PADecisionRules()
        prompt = _build_prompt(brief)
        raw = _call_llm(llm, prompt)
        parsed = _extract_json(raw)

        items = _coerce_items(parsed.get("items"))
        opp = _coerce_opp(parsed.get("opportunity_cost"), fallback_metric=primary_outcome_metric)

        scores, decision = decide(items, opp, decision_rules)

        return PremiseAttackResult(
            items=items,
            opportunity_cost=opp,
            decision_rules=decision_rules,
            scores=scores,
            decision=decision,
            system_prompt="You are a rigorous analyst. Output JSON only.",
            user_prompt=prompt,
            raw_model_text=raw
        )

    @staticmethod
    def render_html_snippet(result: PremiseAttackResult) -> str:
        data = json.dumps(result.to_dict(), ensure_ascii=False)
        return f"""
<section id="premise-attack" class="section">
  <h2>Premise Attack & Opportunity Cost</h2>
  <details open><summary>Critical & High-Value Questions</summary><div id="premise-attack-crit"></div></details>
  <details><summary>Opportunity Cost</summary><div id="premise-attack-opp"></div></details>
  <details><summary>Decision</summary><div id="premise-attack-decision"></div></details>
</section>
<script>
(function(){{ 
  var data = {data};
  function el(t,a,cs){{var e=document.createElement(t);if(a)Object.entries(a).forEach(([k,v])=>k in e?e[k]=v:e.setAttribute(k,v));(cs||[]).forEach(c=>e.appendChild(typeof c==='string'?document.createTextNode(c):c));return e;}}
  // Items
  var cm = document.getElementById('premise-attack-crit');
  var table = el('table', {{ className: 'table premise-attack-table' }});
  table.appendChild(el('thead', null, [el('tr', null, ['ID','Category','Question','Status','Severity','Notes'].map(h=>el('th',null,[h])))]));
  var tb = el('tbody');
  (data.items||[]).forEach(function(it){{
    var cls = it.status==='Fail'?'fail':(it.status==='Unknown'?'unknown':'pass');
    tb.appendChild(el('tr', {{ className: cls }}, [
      el('td',null,[it.id||'']),
      el('td',null,[it.category||'']),
      el('td',null,[it.question||'']),
      el('td',null,[it.status||'']),
      el('td',null,[String(it.severity_5||'')]),
      el('td',null,[it.notes||''])
    ]));
  }});
  table.appendChild(tb); cm.appendChild(table);

  // Opp cost
  var om = document.getElementById('premise-attack-opp');
  var ot = el('table', {{ className: 'table opp-table' }});
  ot.appendChild(el('thead', null, [el('tr', null, ['ID','Option','Total Cost','ΔOutcome','Cost/Outcome','Feasible'].map(h=>el('th',null,[h])))]));
  var ob = el('tbody');
  ((data.opportunity_cost&&data.opportunity_cost.candidates)||[]).forEach(function(c){{
    ob.appendChild(el('tr', null, [
      el('td',null,[c.id||'']),
      el('td',null,[c.name||'']),
      el('td',null,[Intl.NumberFormat().format(c.total_cost||0)]),
      el('td',null,[String(c.delta_outcome||0)]),
      el('td',null,[String(c.cost_per_outcome!=null?c.cost_per_outcome:'')]),
      el('td',null,[c.meets_constraints?'Yes':'No'])
    ]));
  }});
  ot.appendChild(ob); om.appendChild(ot);

  // Decision
  var dm = document.getElementById('premise-attack-decision');
  var cf = (data.scores&&data.scores.critical_failed)||0;
  var score = (data.scores&&data.scores.skepticism_score_100)||0;
  var rules = data.decision_rules||{{}};
  function betterAlt() {{
    var cands = (data.opportunity_cost&&data.opportunity_cost.candidates)||[];
    var P = cands.find(x=>x.id==='P');
    if(!P) return true;
    var thresh = 1 - (rules.alt_dominance_threshold||25)/100;
    return cands.some(a=>a.id!=='P' && a.meets_constraints && a.cost_per_outcome < P.cost_per_outcome*thresh);
  }}
  var proceed = (cf===0) && (score >= (rules.min_score_to_proceed||70)) && !betterAlt();
  dm.appendChild(el('p',null,['Critical fails: '+cf+'. Skepticism score: '+score+'/100.']));
  dm.appendChild(el('p',null,[betterAlt()?'A feasible alternative dominates on cost/outcome.':'No feasible alternative dominates.']));
  dm.appendChild(el('p',{{ className: proceed?'go':'nogo' }},[proceed?'DECISION: Proceed':'DECISION: Do NOT proceed']));
}})();
</script>
<style>
  #premise-attack .table {{ width:100%; border-collapse:collapse; margin:.5rem 0; }}
  #premise-attack th, #premise-attack td {{ border:1px solid #ddd; padding:6px; vertical-align:top; }}
  #premise-attack tr.fail {{ background:#ffe5e5; }}
  #premise-attack tr.unknown {{ background:#fff8e1; }}
  #premise-attack tr.pass {{ background:#e8f5e9; }}
  #premise-attack .go, #premise-attack .nogo {{ font-weight:700; }}
</style>
""".strip()

    @staticmethod
    def inject_into_html(html_text: str, result: PremiseAttackResult) -> str:
        """Insert the snippet before <!--CONTENT-END-->; returns modified HTML text."""
        snippet = PremiseAttack.render_html_snippet(result)
        marker = "<!--CONTENT-END-->"
        if marker in html_text:
            return html_text.replace(marker, snippet + "\n\n" + marker)
        # fallback: append at end
        return html_text + "\n\n" + snippet

# -----------------------------
# CLI (optional)
# -----------------------------
def _load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _save_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Premise Attack gate")
    parser.add_argument("--brief-file", type=str, help="Path to file containing project brief text")
    parser.add_argument("--html-in", type=str, help="Optional: input HTML to inject section into")
    parser.add_argument("--html-out", type=str, help="Optional: output HTML path")
    parser.add_argument("--model", type=str, default="ollama-llama3.1", help="Model name for get_llm")
    parser.add_argument("--primary-metric", type=str, default="€ per additional active user (30-day)")
    args = parser.parse_args()

    try:
        from planexe.llm_factory import get_llm
    except Exception as e:
        raise SystemExit(f"Missing planexe.llm_factory.get_llm in your environment: {e}")

    if not args.brief_file:
        raise SystemExit("Provide --brief-file with the project brief.")

    brief = _load_text(args.brief_file)
    llm = get_llm(args.model)
    result = PremiseAttack.execute(llm, brief, primary_outcome_metric=args.primary_metric)

    print(json.dumps(result.to_dict(), indent=2))

    if args.html_in and args.html_out:
        html_in = _load_text(args.html_in)
        html_out = PremiseAttack.inject_into_html(html_in, result)
        _save_text(args.html_out, html_out)
        print(f"Injected Premise Attack section into: {args.html_out}")
