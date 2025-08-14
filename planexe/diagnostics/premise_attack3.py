
"""
PROMPT> python -m planexe.diagnostics.premise_attack3 --brief-file /absolute/path/to/plan.txt
"""

from __future__ import annotations

from typing import List, Optional, Any, Dict, Tuple
from dataclasses import dataclass, field, asdict
import json, re

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
    alt_dominance_threshold: float = 25.0  # % advantage

@dataclass
class PAScores:
    critical_failed: int = 0
    skepticism_score_100: float = 0.0

@dataclass
class DecisionReasons:
    critical_fail_gate: bool = False
    score_gate: bool = False
    alt_dominance_gate: bool = False
    missing_alternatives: bool = False

@dataclass
class PremiseAttackResult:
    items: List[PAItem]
    opportunity_cost: PAOppCost
    decision_rules: PADecisionRules = field(default_factory=PADecisionRules)
    scores: PAScores = field(default_factory=PAScores)
    decision: str = "Do NOT proceed"
    reasons: DecisionReasons = field(default_factory=DecisionReasons)
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
            "reasons": asdict(self.reasons),
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

# -----------------------------
# Canonical metadata & heuristics
# -----------------------------
def _canonical_map():
    m = {}
    for qid, cat, q in CRITICAL_QUESTIONS + HIGH_VALUE_QUESTIONS:
        m[qid] = (cat, q)
    return m

def _derive_status_from_answer(ans: str) -> str:
    if not ans:
        return "Unknown"
    t = ans.strip().lower()
    # simple, deterministic rules
    if t.startswith("yes"):
        return "Pass"
    if t.startswith("no"):
        return "Fail"
    if "insufficient" in t or "unclear" in t or "unknown" in t:
        return "Unknown"
    return "Unknown"


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
        return True  # no baseline
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

def decide(items: List[PAItem], opp: PAOppCost, rules: PADecisionRules) -> Tuple[PAScores, str, DecisionReasons]:
    reasons = DecisionReasons()
    scores = compute_scores(items)
    if rules.stop_on_critical_fail and scores.critical_failed > 0:
        reasons.critical_fail_gate = True
    if scores.skepticism_score_100 < rules.min_score_to_proceed:
        reasons.score_gate = True
    if len(opp.candidates) <= 1:
        reasons.missing_alternatives = True
    if violates_alt_rule(opp, rules):
        reasons.alt_dominance_gate = True
    if reasons.critical_fail_gate or reasons.score_gate or reasons.alt_dominance_gate or reasons.missing_alternatives:
        return scores, "Do NOT proceed", reasons
    return scores, "Proceed", reasons

# -----------------------------
# LLM integration & JSON handling
# -----------------------------
def _call_llm(llm: Any, prompt: str) -> str:
    if hasattr(llm, "complete"):
        try:
            r = llm.complete(prompt)
            return getattr(r, "text", str(r))
        except Exception:
            pass
    if hasattr(llm, "predict"):
        try:
            return str(llm.predict(prompt))
        except Exception:
            pass
    try:
        from llama_index.core.llms import ChatMessage, MessageRole  # type: ignore
        msgs = [ChatMessage(role=MessageRole.SYSTEM, content="Output ONE JSON object only. No prose."),
                ChatMessage(role=MessageRole.USER, content=prompt)]
        r = llm.chat(msgs)
        return getattr(getattr(r, "message", None), "content", getattr(r, "text", str(r)))
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
    t = re.sub(r"(?m)\s*//.*$", "", t)              # // comments
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)     # /* */ comments
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
    t = re.sub(r",\s*(?=[\]\}])", "", t)            # trailing commas
    return t

def _find_all_json_blocks(text: str) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    if not text:
        return blocks
    # try fenced first
    for m in re.finditer(r"```(?:json)?\s*(.*?)```", text, flags=re.S|re.I):
        s = _sanitize_jsonish(m.group(1))
        try:
            blocks.append(json.loads(s))
        except Exception:
            pass
    # then raw curly blocks
    for m in re.finditer(r"\{.*?\}", text, flags=re.S):
        s = _sanitize_jsonish(m.group(0))
        try:
            blocks.append(json.loads(s))
        except Exception:
            pass
    return blocks

def _extract_and_merge(text: str) -> Dict[str, Any]:
    """Prefer a single well-formed object; else merge keys from multiple blocks."""
    # First try straight
    try:
        return json.loads(_sanitize_jsonish(text))
    except Exception:
        pass
    blocks = _find_all_json_blocks(text)
    merged: Dict[str, Any] = {}
    if not blocks:
        return merged
    # pick the block with most keys as base
    blocks = sorted(blocks, key=lambda b: (-len(b.keys())))
    merged.update(blocks[0])
    # merge remaining
    for b in blocks[1:]:
        # merge items array
        if "items" in b:
            merged.setdefault("items", [])
            merged["items"].extend(b["items"])
        # use the first opportunity_cost found if missing
        if "opportunity_cost" in b and "opportunity_cost" not in merged:
            merged["opportunity_cost"] = b["opportunity_cost"]
    return merged

# -----------------------------
# Coercion & normalization
# -----------------------------

def _coerce_items(raw_items: Any) -> List[PAItem]:
    items: List[PAItem] = []
    canon = _canonical_map()
    for it in (raw_items or []):
        try:
            qid = str(it.get("id","")).strip()
            cat, ques = canon.get(qid, ("", ""))
            status_in = str(it.get("status","Unknown")).strip().capitalize()
            # derive from 'answer' if status missing/weak
            answer = it.get("answer")
            if (not status_in or status_in == "Unknown") and answer:
                status_in = _derive_status_from_answer(answer)
            sev = it.get("severity_5")
            if sev is None:
                # default severity: Fail critical=4, else 3
                sev = 4 if (status_in == "Fail" and qid in CRITICAL_IDS) else 3
            items.append(PAItem(
                id=qid,
                category=str(it.get("category", cat) or cat),
                question=str(it.get("question", ques) or ques),
                status=status_in if status_in in ("Pass","Fail","Unknown") else "Unknown",
                severity_5=int(sev),
                rationale=it.get("rationale", answer),
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
    else:
        # Ensure all canonical questions exist; if some IDs are missing, append as Unknown
        present = {it.id for it in items}
        for qid, cat, q in CRITICAL_QUESTIONS + HIGH_VALUE_QUESTIONS:
            if qid not in present:
                default_sev = 5 if qid in CRITICAL_IDS else 3
                items.append(PAItem(id=qid, category=cat, question=q, status="Unknown", severity_5=default_sev))
    return items

def _coerce_opp(raw_opp: Any, fallback_metric: str) -> PAOppCost:
    metric = str((raw_opp or {}).get("primary_outcome_metric") or fallback_metric)
    cands: List[PACandidate] = []
    for c in (raw_opp or {}).get("candidates", []):
        try:
            total_cost = float(c.get("total_cost", 0.0))
        except Exception:
            total_cost = 0.0
        try:
            delta = float(c.get("delta_outcome", 0.0))
        except Exception:
            delta = 0.0
        try:
            cost_per = float(c.get("cost_per_outcome", total_cost / delta if delta else 0.0))
        except Exception:
            cost_per = (total_cost / delta) if delta else 0.0
        cands.append(PACandidate(
            id=str(c.get("id","")).strip() or f"A{len(cands)+1}",
            name=str(c.get("name","")).strip() or "Alternative",
            total_cost=total_cost,
            delta_outcome=delta,
            cost_per_outcome=cost_per,
            meets_constraints=bool(c.get("meets_constraints", True)),
            assumptions=c.get("assumptions"),
        ))
    return PAOppCost(primary_outcome_metric=metric, candidates=cands)

# -----------------------------
# Public API
# -----------------------------
PROMPT_TEMPLATE = """You are performing a *Premise Attack*—an adversarial review that decides whether a proposed project should proceed at all.

STRICT OUTPUT RULE: Return **ONE** JSON object only. No prose, no markdown fences.

PROJECT BRIEF (verbatim):
---
{brief}
---

TASK:
1) Answer the Critical questions C1–C8 and High-Value questions H1–H7.
2) Propose 2–3 alternatives (include a cheaper variant and a do-nothing baseline).
3) Choose ONE primary outcome metric and compute cost_per_outcome = total_cost / delta_outcome for P and alternatives.

CRITICAL QUESTIONS:
{critical_questions}

HIGH-VALUE QUESTIONS:
{high_value_questions}

REQUIRED OUTPUT (single JSON object only):
{{
  "items": [ /* C1..C8 then H1..H7 */ ],
  "opportunity_cost": {{
    "primary_outcome_metric": "STRING",
    "candidates": [
      {{ "id": "P",  "name": "Proposed Project", "total_cost": 0, "delta_outcome": 1, "cost_per_outcome": 0, "meets_constraints": true }},
      {{ "id": "A1", "name": "Cheaper Variant",  "total_cost": 0, "delta_outcome": 1, "cost_per_outcome": 0, "meets_constraints": true }},
      {{ "id": "A2", "name": "Do-Nothing",       "total_cost": 0, "delta_outcome": 1, "cost_per_outcome": 0, "meets_constraints": true }}
    ]
  }}
}}
"""

def _build_prompt(brief: str) -> str:
    crit = "\\n".join([f"{qid}: {q}" for qid, _, q in CRITICAL_QUESTIONS])
    high = "\\n".join([f"{qid}: {q}" for qid, _, q in HIGH_VALUE_QUESTIONS])
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
        parsed = _extract_and_merge(raw)

        items = _coerce_items(parsed.get("items"))
        opp = _coerce_opp(parsed.get("opportunity_cost"), fallback_metric=primary_outcome_metric)

        # Fallback: if the model didn't provide alternatives, keep P and mark missing_alternatives
        if not any(c.id == "P" for c in opp.candidates):
            opp.candidates.insert(0, PACandidate(id="P", name="Proposed Project", total_cost=0.0, delta_outcome=1.0, cost_per_outcome=0.0))
        scores, decision, reasons = decide(items, opp, decision_rules)

        return PremiseAttackResult(
            items=items,
            opportunity_cost=opp,
            decision_rules=decision_rules,
            scores=scores,
            decision=decision,
            reasons=reasons,
            system_prompt="Output ONE JSON object only. No prose.",
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

  var dm = document.getElementById('premise-attack-decision');
  var cf = (data.scores&&data.scores.critical_failed)||0;
  var score = (data.scores&&data.scores.skepticism_score_100)||0;
  var rules = data.decision_rules||{{}};
  var rs = data.reasons || {{}};
  function betterAlt(){{return !!rs.alt_dominance_gate;}}
  var proceed = (cf===0) && (score >= (rules.min_score_to_proceed||70)) && !betterAlt() && !rs.missing_alternatives;
  dm.appendChild(el('p',null,['Critical fails: '+cf+'. Skepticism: '+score+'/100.']));
  if(rs.missing_alternatives) dm.appendChild(el('p',null,['Missing alternatives: provide A1/A2 with costs & ΔOutcome.']));
  if(rs.alt_dominance_gate) dm.appendChild(el('p',null,['A feasible alternative dominates on cost/outcome.']));
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
        snippet = PremiseAttack.render_html_snippet(result)
        marker = "<!--CONTENT-END-->"
        if marker in html_text:
            return html_text.replace(marker, snippet + "\\n\\n" + marker)
        return html_text + "\\n\\n" + snippet

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
    parser = argparse.ArgumentParser(description="Premise Attack v3 gate")
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
