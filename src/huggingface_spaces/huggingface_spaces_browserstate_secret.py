"""
PROMPT> HUGGINGFACE_SPACES_BROWSERSTATE_SECRET=hello python -m src.huggingface_spaces.huggingface_spaces_browserstate_secret
hello

PROMPT> python -m src.huggingface_spaces.huggingface_spaces_browserstate_secret
None
"""
import os
from typing import Optional

def huggingface_spaces_browserstate_secret() -> Optional[str]:
    """
    Returns the secret key to use for encryption of the Gradio BrowserState that is stored in the browser's localStorage.
    """
    return os.getenv("HUGGINGFACE_SPACES_BROWSERSTATE_SECRET")

if __name__ == "__main__":
    print(huggingface_spaces_browserstate_secret())
