### Is This Over-Engineered? A Balanced Assessment

Short answer: **Potentially yes, for a prototype or if your 61-task Luigi DAG is already reliable and mostly deterministic**. The proposed MCP-agent hybrid is a sophisticated upgrade that could make your planning system more adaptive and intelligent (e.g., dynamic research for risks/assumptions), but it introduces significant complexity, maintenance overhead, and potential failure modes compared to simpler orchestration. It's not wildly overkill if your goal is a production-grade, extensible "planning office" with web-aware agents—but for validation, it feels heavyweight. Think of it as building a smart factory: Agents (via MCP) handle creative/research tasks well, but Luigi's DAG ensures the assembly line doesn't break. If simpler methods suffice for 80% of your needs, this might be premature optimization.

I'll break it down based on technical realities, drawing from current (2025) best practices in LLM orchestration (e.g., frameworks like LangChain, AutoGen; agent patterns like ReAct; and analyses of scaling LLM agents vs. code-based pipelines). No, you shouldn't start from the ground up—incremental iteration is smarter. But let's evaluate.

#### Why It Might Feel Over-Engineered
- **Layered Complexity Stacks Up**:
  - **MCP + Agents**: MCP is a solid open standard for tool integration (as Anthropic intended for multi-LLM compatibility), but setting up servers (fetch, filesystem, git) + prompts + client coordination adds glue code and debugging. Agents excel at multi-step reasoning (e.g., WBS Engineer using search → tools → JSON output), but they can hallucinate schemas or loop infinitely without tight guardrails. Your 10 "office" agents sound modular, but wiring 61 tasks to them could balloon into 20+ prompts and validators.
  - **Luigi Integration**: Using `ExternalTask` for agent artifacts is elegant (preserves atomicity/retries), but it doubles your task count (staging → validation). Luigi's in-process model is great for batch jobs, but mixing it with async agent calls (MCP over HTTP) risks races or stalls—locks help, but they're not foolproof.
  - **Overhead Metrics** (from 2025 orchestration benchmarks):
    - Latency: Basic Luigi task: ~seconds; Add MCP agents: 10-60s per role (tool calls + LLM inference). For 61 tasks, end-to-end could jump from hours to days if not parallelized.
    - Cost: Agents burn tokens (~1k-5k per run for research-heavy roles); at $0.01/1k tokens (e.g., Claude), that's $0.50-2.00 per full plan vs. near-zero for pure Luigi.
    - Debugging: Agent drift (e.g., invalid JSON) means Luigi retries spike; provenance (git manifests) helps reproducibility but adds steps.
  - **Ecosystem Maturity**: MCP is gaining traction (e.g., in LangGraph for agentic flows), but community servers like `brave-search` have quirks (API keys, rate limits). If your needs are internal (no heavy web research), why not simpler HTTP tools?

- **When Over-Engineering Hits**: If your current Luigi pipeline is already handling 80% of tasks deterministically (e.g., static WBS templates, fixed risks), agents are like using a sports car for groceries—fun, but unnecessary. Recent analyses (e.g., on LLM agent patterns) note that full agents shine for open-ended tasks (like "enrich team data via web"), but simpler chains/orchestrators often outperform on structured planning (e.g., ReAct vs. Plan-and-Execute: The latter is more reliable for DAG-like flows but less adaptive).

- **Comparison to Simpler Methods**:
  | Approach | Pros | Cons | Fit for Your 61 Tasks |
  |----------|------|------|-----------------------|
  | **Current Luigi (Pure)** | Deterministic, battle-tested for DAGs; zero new deps. | Static—no dynamic research (e.g., no auto-fetch benchmarks for budgets). | Good baseline if agents add little value. |
  | **Luigi + Basic LLM Chains** (e.g., LangChain in tasks) | Embed LLMs directly (e.g., prompt for WBS in a task); simple tools via APIs. No MCP servers. | Less modular; vendor-locked to one LLM. | Simpler upgrade—handles ~70% of your roles without agents. |
  | **Full Agents (This Plan)** | Adaptive (web tools, roles); MCP for portability. | High setup (2-4 weeks); reliability risks. | Overkill unless research/dynamic is core (e.g., 20%+ tasks need fetch/search). |
  | **Alternative Orchestrators** (e.g., Airflow + AutoGen) | AutoGen for multi-agent convos; Airflow for DAGs (better parallelism than Luigi). | Learning curve; migrate from Luigi. | If scaling beyond 61 tasks—simpler than MCP for teams. |

  Per orchestration guides (e.g., evaluating LLM agents), code-based orchestration (like enhanced Luigi tasks with direct API calls) scales better than function-calling agents for predictable pipelines, as agents don't "internalize" logic reliably.

#### Why It's Not *Necessarily* Over-Engineered
- **Your Use Case Justifies It**: A 61-task planning system (WBS, risks, governance, etc.) screams for intelligence. Agents can automate the "human office" (e.g., Strategist role pulling market data via MCP fetch/search), making outputs richer than static Luigi. The hybrid preserves what's working (Luigi for exports/scheduling) while upgrading upstream. Emerging architectures (e.g., in a16z's LLM app stack) recommend this: Agents for reasoning/planning, deterministic runners for execution.
- **Future-Proofing**: MCP avoids lock-in (works with Claude, GPT, etc.); prompts enable easy iteration. For enterprise planning, reproducibility (git provenance) and modularity pay off long-term.
- **Not Unprecedented**: Similar setups exist (e.g., Routine framework for enterprise agents; LangGraph's agentic DAGs). If your team has FastAPI/Luigi expertise, the plan's steps (e.g., spike on MCP wrapping) mitigate bloat.

#### Should You Start from the Ground Up?
**No—absolutely not**. Scrapping Luigi would be a mistake; it's your proven foundation (handles dependencies, failures). Starting over (e.g., new framework) risks 3-6 months lost, especially with 61 tasks. Instead:
- **Incremental Build**: Follow the plan's modularity but scope down:
  1. **MVP (1 Week)**: Pick 2-3 high-value roles (e.g., Assumptions Analyst, WBS Engineer). Enhance Luigi tasks with basic LLM calls (no MCP yet—use OpenAI/Anthropic SDK directly for prompts/tools). Test agent-like behavior in isolation.
  2. **Spike MCP (Week 2)**: Wrap your FastAPI as tools using fastapi-mcp (optional, as per plan). Add one server (filesystem for runs/). Run a full flow for those roles, validating Luigi integration.
  3. **Expand (Weeks 3-4)**: Add more agents/prompts; measure vs. baseline (time, accuracy, cost). If agents underperform (e.g., >20% invalid outputs), pivot to chains.
  4. **Fallback**: If MCP feels heavy, drop it—use LangChain's tool-calling within Luigi for 90% of benefits with 50% effort.

- **When to Rethink**: If testing shows agents add <20% value (e.g., manual inputs suffice for research), simplify to Luigi + embedded LLMs. Or evaluate AutoGen (gaining popularity for multi-agent orchestration) as a Luigi alternative—it's lighter for planning workflows.

In summary, this is engineered for ambition, not excess—proceed if adaptability is key, but prototype ruthlessly to avoid overcommitment. If you share more on pain points (e.g., what's slow/manual now?), I can refine alternatives.