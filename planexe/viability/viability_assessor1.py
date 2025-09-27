"""
Why long risk lists demotivate—and why 3–5 targeted recommendations boost morale

Problem
-------
Dumping a long list of risks reads like a verdict: "this will fail." Users see dozens
of threats with no order or path forward. That creates overload and paralysis:
- Signal dilution: real blockers get lost among minor risks.
- No agency: nothing says “do this next,” so effort feels pointless.
- Perceived infeasibility: many YELLOW/RED flags imply the project is doomed.

Impact
------
Motivation drops, users disengage, and iteration stalls. Teams either ignore the
report or push ahead blindly, both of which defeat the purpose of planning.

Remedy
------
Surface only the 3–5 highest-leverage “serious things” and attach a short, concrete
Path-to-Green for each (owner, steps, acceptance tests, ETA). This restores agency:
- Focus: attention goes to the few fixes that move the needle.
- Momentum: clear steps + quick wins → visible progress.
- Reframe: from “failure audit” to “fixable gaps.” Morale improves, iteration resumes.

Practical rule of thumb
-----------------------
Cap the list at five. Anything without a specific fix and acceptance test becomes
background context, not a blocker. Flip unknowns to GRAY (data to collect) instead
of painting them RED.

PROMPT> python -m planexe.plan.viability_assessor1
"""
