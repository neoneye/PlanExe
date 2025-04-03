# Governance

This directory contains Python modules designed to automatically generate components of a project governance framework using LLMs. The process is broken down into multiple stages to manage complexity and potentially allow for the use of different LLMs with varying capabilities.

## Why is Project Governance Important?

Project governance provides the **framework of authority, accountability, control, and decision-making** necessary for a project to achieve its objectives successfully and responsibly. Without effective governance, projects are prone to:

1.  **Lack of Strategic Alignment:** Drifting away from organizational goals or stakeholder expectations.
2.  **Poor Decision-Making:** Unclear authority leads to delays, bottlenecks, or suboptimal choices.
3.  **Insufficient Oversight:** Risks are missed, budgets overrun, and quality suffers without proper checks and balances.
4.  **Lack of Accountability:** It becomes unclear who is responsible for specific outcomes or failures.
5.  **Increased Risk Exposure:** Financial, operational, legal, ethical, and reputational risks are not adequately identified or managed.
6.  **Resource Misallocation:** Funds, time, and personnel are not used effectively or efficiently.
7.  **Stakeholder Dissatisfaction:** Needs and concerns of sponsors, users, or the community are not properly addressed.
8.  **Compliance Failures:** Legal and regulatory requirements (like GDPR, permits, safety standards) may be overlooked, leading to penalties.
9.  **Ethical Lapses:** Potential conflicts of interest, bias, or other ethical concerns are not managed appropriately.

In essence, good governance provides the structure and processes to **steer the project correctly, ensure responsible execution, and increase the likelihood of success.**

## Multi-Stage Generation Approach

Initially I had everything in a single system prompt, and the LLMs struggles generating a good response.
`Llama3.1` often misunderstands the `Governance` topic.

I ended up with a multi-agent approach where each stage focuses on generating a specific part of the overall governance structure. This allows for:

*   **Focused Prompts:** Each agent receives a highly specific system prompt tailored to its task.
*   **Reduced Complexity:** Breaks down a large, complex generation task into smaller, more manageable pieces.
*   **Improved LLM Performance:** Increases the likelihood of success, especially with less capable LLMs, by reducing the context and complexity required for each call.
*   **Modularity:** Allows for potential swapping or refinement of individual stages.

**Crucially, later stages often require the output of earlier stages as input context to ensure consistency.**

## Governance Stages

The generation process is divided into the following stages (Python modules):

1.  **`governance_phase1_audit.py` (`GovernancePhase1Audit`)**
    *   **Focus:** Identifying potential audit-related risks and control measures.
    *   **Output:** `AuditDetails` containing `corruption_list`, `misallocation_list`, `audit_procedures`, and `transparency_measures`.
    *   **Rationale:** Establishes the baseline risks and controls relevant to the project context early on.

2.  **`governance_phase2_bodies.py` (`GovernancePhase2Bodies`)**
    *   **Focus:** Defining the structure of *internal* project governance bodies (committees, teams).
    *   **Output:** `DocumentDetails` containing a list of `InternalGovernanceBody` objects, each detailing name, rationale, responsibilities, setup actions, membership, decision rights/mechanism, cadence, agenda items, and escalation path.
    *   **Rationale:** Defines the core organizational structure for oversight and management.

3.  **`governance_phase3_impl_plan.py` (`GovernancePhase3ImplPlan`)**
    *   **Focus:** Creating the step-by-step plan to *establish and operationalize* the governance bodies defined in Stage 2.
    *   **Input Dependency:** Requires the output of Stage 2 (`internal_governance_bodies`).
    *   **Output:** `DocumentDetails` containing a list of `ImplementationStep` objects.
    *   **Rationale:** Provides an actionable roadmap for setting up the defined governance structure.

4.  **`governance_phase4_decision_escalation_matrix.py` (`GovernancePhase4DecisionEscalationMatrix`)**
    *   **Focus:** Defining how specific types of problems or decisions requiring higher authority are escalated through the structure defined in Stage 2.
    *   **Input Dependency:** Requires the output of Stage 2 (`internal_governance_bodies`).
    *   **Output:** `DocumentDetails` containing a list of `DecisionEscalationItem` objects.
    *   **Rationale:** Clarifies decision pathways for critical issues, preventing bottlenecks and ensuring timely resolution at the appropriate level.

5.  **`governance_phase5_monitoring_progress.py` (`GovernancePhase5MonitoringProgress`)**
    *   **Focus:** Defining how project progress, risk, compliance, and critical success factors will be monitored, and how the plan adapts based on this monitoring.
    *   **Input Dependency:** Can benefit from the output of Stage 2 (`internal_governance_bodies`) for assigning responsibility.
    *   **Output:** `DocumentDetails` containing a list of `MonitoringProgress` objects.
    *   **Rationale:** Establishes the mechanisms for ongoing tracking, reporting, and course correction.

6.  **`governance_phase6_extra.py` (`GovernancePhase6Extra`)**
    *   **Focus:** Performing a final validation check on the generated governance components, generating key accountability questions, and providing an overall summary.
    *   **Input Dependency:** Requires the outputs of most, if not all, previous stages for context.
    *   **Output:** `DocumentDetails` containing `governance_validation_checks`, `tough_questions`, and `summary`.
    *   **Rationale:** Provides a quality check on the generated framework and equips project leadership with tools for ongoing accountability.

## Usage

Each module (`governance_phaseX_*.py`) can typically be run independently (as shown in their `if __name__ == "__main__":` blocks), provided the correct user prompt containing the project description (and potentially outputs from previous stages, formatted appropriately) is supplied.

The `execute` class method handles the interaction with the configured LLM via LlamaIndex, using the specific system prompt and Pydantic output schema defined within that module. The results are saved as JSON (`save_raw`) and Markdown (`save_markdown`).

A higher-level orchestration script would be needed to run these stages sequentially, passing the necessary context between them to generate a complete, consistent governance framework document.
