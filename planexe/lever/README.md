# Exploring the Solution Space

The biggest lever is the initial prompt for PlanExe. You can modify it.
Often I find that the LLMs interprets the constraints/requirements as if they are set in stone, non-negotiable.
I would like to come up with suggestions for changing the initial prompt, redefining the scope, timeline, or even the goal.
By tweaking the initial prompt, maybe there is a nearby optimum.

Every project starts with a set of initial parameters—or **strategic levers**—that strongly shape the outcome. If you begin with sub-optimal lever settings, even the best algorithms can’t rescue you. Follow these steps to zero in on the adjustments that matter most.

A single, optimized plan is useful, but its weakness is that it's a "point estimate." It represents one possible future. The real world is about trade-offs, and true strategic advantage comes from understanding those trade-offs. Analyze multiple combos of these levers, that's my intention.

---

## The 5-Step Pipeline

### Step 1: Brainstorm Potential Levers

Brainstorm a comprehensive list of all potential levers that could influence the project's outcome.
The goal is to create a [MECE (Mutually Exclusive, Collectively Exhaustive)](https://en.wikipedia.org/wiki/MECE_principle) set of levers. This ensures we cover all critical dimensions of the problem without overlap. Some overlap is ok. 

Near duplicates also appears in this brainstorm, the 80/20 filtering takes care of removing them.

1. **Define “Levers”**
   - List every aspect of the plan you could tweak (e.g. modularization approach, feedstock strategy, automation level, emerging-tech integration).
2. **Enumerate Options**
   - For each lever, jot down all feasible settings (e.g. “Additive Only,” “Subtractive Only,” “Hybrid”).

### Step 2: Enrich Potential Levers

Raw brainstormed ideas often lack the necessary detail for rigorous analysis. This step enriches each lever with a `description` that clarifies its purpose, scope, mechanism, and key success metrics. This additional context is crucial for the subsequent filtering step.

1. **Description**
  - The description provides a clear overview of the lever’s purpose, scope, and mechanism. It summarizes the lever’s objectives, impact range, and approach, while highlighting key success metrics and any prerequisites for effectiveness. This concise summary aids understanding and evaluation of the lever.
  - Why: without it, stakeholders won’t understand the lever or its relevance.
2. **Interaction with other levers**
  - With what other levers does this lever boost the outcome. 
  - With what other levers does this lever weaken the outcome. 

### Step 3: Focus on the "Vital Few" levers

Not all levers are created equal. Applying the 80/20 principle, this step uses an LLM to assess the strategic importance of each *enriched* lever. 
It filters the comprehensive list down to the "vital few" (typically 4-6) that will drive the majority of the project's outcome.

1. **Apply the 80/20 Rule**
   - From your brainstorm, identify the handful (≈4–6) of levers that will likely drive ≈80% of the impact.
2. **Assess Importance**
   - Score each candidate lever on:
     - **Strategic Impact** (e.g. cost reduction, scalability gain)
     - **Implementation Feasibility** (e.g. tech readiness, capex)
3. **Select the “Vital Few”**
   - Retain only those levers that combine high impact with manageable effort. Discard the rest or park them for later.

### Step 4: Scenarios of Lever combinations

Propose 3 different scenarios:
1. **Aggressive, High risk, High reward**
2. **Medium**
3. **Slow and safe**

### Step 5: Select the best fitting scenario

Compare each of the scenarios with the initial prompt.

Pick the one that fits the best.
