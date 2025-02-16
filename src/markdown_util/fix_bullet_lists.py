"""
Often the markdown files have bullet lists that are not properly formatted.
There bullet list must have 2 newlines before the list starts and 2 newlines after the list ends.
This script fixes the bullet lists in the markdown files.

The following input lacks the required 2 newlines before the list starts:
```markdown
Lorem ipsum:
- Item A
- Item B
- Item C
```

The fixed output:

```markdown
Lorem ipsum:

- Item A
- Item B
- Item C
```
"""

def fix_bullet_lists(markdown_text: str) -> str:
    """
    Fix the bullet lists in the markdown text that lacks the required 2 newlines before the list starts.
    """
    lines = markdown_text.split('\n')
    fixed_lines = []
    in_list = False

    for i, line in enumerate(lines):
        if line.startswith('- '):
            if not in_list:
                if i > 0 and lines[i-1].strip() != '':
                    fixed_lines.append('')
                in_list = True
            fixed_lines.append(line)
        else:
            if in_list:
                if line.strip() != '':
                    fixed_lines.append('')
                in_list = False
            fixed_lines.append(line)

    if in_list:
        fixed_lines.append('')

    return '\n'.join(fixed_lines)
