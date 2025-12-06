"""
Utilities for generating run IDs shared between worker and frontend.
"""
from datetime import datetime
import uuid

RUN_ID_PREFIX = "PlanExe_"


def generate_run_id(use_uuid: bool, start_time: datetime) -> str:
    """Generates a unique run ID.

    This function creates a unique identifier for a run, prefixed with `RUN_ID_PREFIX` for easy identification by purging scripts.

    Args:
        use_uuid:  If True, generates a UUID-based ID. If False, generates a timestamp-based ID.
        start_time: The time when the run was started.

    Returns:
        A string representing the unique run ID.

    The choice between UUID and timestamp depends on the environment:

    *   **Multi-user environments:** Use UUIDs to guarantee uniqueness and avoid conflicts.
    *   **Single-user environments:**  Use timestamps for improved human readability.
    """
    if use_uuid:
        return RUN_ID_PREFIX + str(uuid.uuid4())
    return RUN_ID_PREFIX + start_time.strftime("%Y%m%d_%H%M%S")


if __name__ == "__main__":
    start_time: datetime = datetime.now().astimezone()
    print(generate_run_id(use_uuid=True, start_time=start_time))
    print(generate_run_id(use_uuid=False, start_time=start_time))
