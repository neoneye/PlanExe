"""
PROMPT> python -m src.utils.get_env_as_string
"""
import os

def get_env_as_string():
    lines = []
    for key in sorted(os.environ.keys()):
        lines.append(f"{key}: {os.environ[key]}")
    return "\n".join(lines)

if __name__ == "__main__":
    env_string = get_env_as_string()
    print(env_string)
