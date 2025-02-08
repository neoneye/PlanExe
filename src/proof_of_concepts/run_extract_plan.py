import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from src.llm_factory import get_llm

class PlanStep(BaseModel):
    """Details about a single step in the plan."""
    step_title: str = Field(
        description="What does this step do briefly. Without formatted text."
    )
    detailed_instructions: str = Field(
        description="What does this step do in great detail"
    )

class DocumentDetails(BaseModel):
    """A markdown document with details about a plan."""
    step_items: list[PlanStep] = Field(
        description="A list with every step in the plan"
    )
    explanation: str = Field(
        description="Short explanation of the plan, max 50 words."
    )
    vision: str = Field(
        description="What has been accomplished when the plan has been successfully executed, max 50 words."
    )

llm = get_llm("ollama-llama3.1")
sllm = llm.as_structured_llm(DocumentDetails)

text = """
Certainly! While the initial team of five agents covers many essential aspects of solving ARC puzzles, additional specialized agents could further enhance the collaborative effort by addressing specific challenges or improving efficiency. Here are some potential additions:

6. **Exploration Agent**:
   - **Role**: Explores alternative hypotheses and creative solutions.
   - **Responsibilities**:
     - Investigates unconventional patterns or transformations that might not be immediately obvious.
     - Encourages out-of-the-box thinking to discover novel rule sets.
     - Provides diverse perspectives on potential solutions.

7. **Optimization Agent**:
   - **Role**: Focuses on improving the efficiency and performance of solution generation.
   - **Responsibilities**:
     - Analyzes computational complexity and optimizes algorithms for faster execution.
     - Reduces redundancy in processing steps to streamline operations.
     - Ensures that solutions are generated with minimal resource usage.

8. **Learning Agent**:
   - **Role**: Adapts and improves over time by learning from past experiences.
   - **Responsibilities**:
     - Analyzes previous puzzles and their solutions to identify common strategies or pitfalls.
     - Updates internal models based on new data, improving future performance.
     - Facilitates knowledge transfer between similar tasks.

9. **Debugging Agent**:
   - **Role**: Identifies and resolves errors in rule application or solution generation.
   - **Responsibilities**:
     - Monitors the process for inconsistencies or failures in expected outcomes.
     - Diagnoses issues with proposed rules or generated solutions.
     - Suggests corrections or alternative approaches to overcome identified problems.

10. **Communication Agent**:
    - **Role**: Enhances interaction and information sharing among agents.
    - **Responsibilities**:
      - Facilitates clear and effective communication between agents.
      - Ensures that all relevant data is shared promptly and accurately.
      - Manages feedback loops to refine collaborative efforts.

By incorporating these additional agents, the team can become more robust and versatile, capable of tackling a wider range of ARC puzzles with greater efficiency and creativity. Each agent contributes unique strengths, allowing for a comprehensive approach to problem-solving that leverages both analytical rigor and innovative thinking.
"""

response = sllm.complete(text)

json_response = json.loads(response.text)
print(json.dumps(json_response, indent=2))
