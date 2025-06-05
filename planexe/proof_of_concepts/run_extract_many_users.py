import json
from typing import List, Optional
from pydantic import BaseModel, Field
from planexe.llm_factory import get_llm

class User(BaseModel):
    """Details about a single user."""
    name: str = "Jane Doe"
    email: Optional[str] = None

class DocumentDetails(BaseModel):
    """A markdown document with details about a project."""
    user_items: list[User] = Field(
        description="A list with info about every user mentioned in this document"
    )
    license: Optional[str] = Field(
        description="What kind of license for this project, such as: GPL, MIT, Apache, etc."
    )
    urls: list[str] = Field(
        description="List of all URLs appearing in this document"
    )

llm = get_llm("ollama-llama3.1")
sllm = llm.as_structured_llm(DocumentDetails)

text = """
# ARC-Heavy

- [BARC Synthetic Examples](https://www.basis.ai/arc_interface/examples) - visualization and navigate the datasets and corresponding code for each puzzle.
- Repo: [github](https://github.com/xu3kev/BARC)
- Datasets: [huggingface](https://huggingface.co/collections/barc0/synthetic-arc-dataset-6725aa6031376d3bacc34f76)
- Users: Wen-Ding Li, Keya Hu, Carter Larsen, Yuqing Wu, Simon Alford, Caleb Woo, Spencer M. Dunn, Hao Tang, Michelangelo Naim, Dat Nguyen, Wei-Long Zheng,
Zenna Tavares, Yewen Pu, Kevin Ellis
- License: MIT
"""

response = sllm.complete(text)

json_response = json.loads(response.text)
print(json.dumps(json_response, indent=2))
