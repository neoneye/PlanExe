"""
Escape special markdown characters to prevent syntax interference.

This module provides functionality to escape markdown special characters that
could interfere with proper markdown rendering. For example, `>` at the start
of a line creates a blockquote, `*` creates emphasis, etc.

Example input with problematic characters:
```
>=10% contingency approved
*Important* note
```

Escaped output:
```
\>=10% contingency approved
\*Important\* note
```
"""

def escape_markdown(text: str) -> str:
    """
    Escape special markdown characters to prevent syntax interference.
    
    Args:
        text: The text to escape
        
    Returns:
        The text with markdown special characters escaped with backslashes
    """
    # Escape common markdown special characters
    # Order matters: backslash first, then others
    replacements = [
        ("\\", "\\\\"),  # Backslash
        ("`", "\\`"),    # Backtick
        ("*", "\\*"),    # Asterisk
        ("_", "\\_"),    # Underscore
        ("{", "\\{"),    # Curly braces
        ("}", "\\}"),
        ("[", "\\["),    # Square brackets
        ("]", "\\]"),
        ("(", "\\("),    # Parentheses
        (")", "\\)"),
        ("#", "\\#"),    # Hash
        ("+", "\\+"),    # Plus
        ("-", "\\-"),    # Minus (only at start of line is problematic, but escape all)
        (".", "\\."),    # Dot (only after number is problematic, but escape all)
        ("!", "\\!"),    # Exclamation
        ("|", "\\|"),    # Pipe
        (">", "\\>"),    # Greater than (blockquote)
        ("<", "\\<"),    # Less than
    ]
    
    for old, new in replacements:
        text = text.replace(old, new)
    
    return text

