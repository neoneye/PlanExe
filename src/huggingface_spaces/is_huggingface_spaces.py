"""
PROMPT> IS_HUGGINGFACE_SPACES=true python -m src.huggingface_spaces.is_huggingface_spaces
True

PROMPT> python -m src.huggingface_spaces.is_huggingface_spaces
False
"""
import os

def is_huggingface_spaces() -> bool:
    return os.getenv("IS_HUGGINGFACE_SPACES", "false").lower() == "true"

if __name__ == "__main__":
    print(is_huggingface_spaces())
