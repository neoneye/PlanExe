import os
import time
from pathlib import Path
from typing import Optional


def time_since_last_modification(path_dir: Path) -> Optional[float]:
    """
    Returns how many seconds ago the directory was last modified by checking file mtimes.
    Returns None if no files are present or the directory is missing.
    """
    if not path_dir.exists():
        return None

    most_recent_mtime: Optional[float] = None
    try:
        for filename in os.listdir(path_dir):
            filepath = path_dir / filename
            try:
                stat_info = filepath.stat()
            except FileNotFoundError:
                # File disappeared between listdir and stat; skip.
                continue

            if most_recent_mtime is None or stat_info.st_mtime > most_recent_mtime:
                most_recent_mtime = stat_info.st_mtime
    except FileNotFoundError:
        return None
    except Exception:
        # Keep worker running if file scanning fails unexpectedly.
        return None

    if most_recent_mtime is None:
        return None

    return time.time() - most_recent_mtime


if __name__ == "__main__":
    path_dir = (Path(__file__).resolve().parent.parent).resolve()
    print(f"Time since last modification in {path_dir}: {time_since_last_modification(path_dir)} seconds")
