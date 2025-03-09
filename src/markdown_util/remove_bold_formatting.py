import re

def remove_bold_formatting(text: str) -> str:
    """
    Remove bold formatting from the text.

    When processing long texts with LLMs, the token count is a limiting factor.
    This function removes the bold formatting from the text to reduce the token count.
    """
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    return re.sub(r'__([^_]+?)__', r'\1', text)
