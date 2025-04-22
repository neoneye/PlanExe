import textwrap

def dedent_strip(text: str) -> str:
    """
    Multi-line strings in Python are indented.
    This function removes the common indent and trims leading/trailing whitespace.

    Usage
    -----
    >>> expected = dedent_strip(\"""
    ...     A
    ...     B
    ... \""")
    """
    return textwrap.dedent(text).strip()
