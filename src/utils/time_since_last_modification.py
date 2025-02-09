import os
import time

def time_since_last_modification(path_dir: str) -> float:
    """
    Returns how many seconds ago the directory `path_dir` was last modified.
    Specifically, looks at all files in the directory and finds the newest mtime.
    If the directory is empty, returns 0.
    """
    all_mtimes = []
    for filename in os.listdir(path_dir):
        filepath = os.path.join(path_dir, filename)
        st = os.stat(filepath)
        all_mtimes.append(st.st_mtime)

    if not all_mtimes:
        return 0.0  # No files at all, treat as 0 or handle specially

    most_recent_mtime = max(all_mtimes)
    return time.time() - most_recent_mtime

if __name__ == "__main__":
    path_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    print(f"Time since last modification in {path_dir}: {time_since_last_modification(path_dir)} seconds")