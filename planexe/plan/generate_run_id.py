from datetime import datetime
import uuid

RUN_ID_PREFIX = "PlanExe_"

def generate_run_id(use_uuid: bool) -> str:
    """Generates a unique run ID.

    This function creates a unique identifier for a run, prefixed with `RUN_ID_PREFIX` for easy identification by purging scripts.

    Args:
        use_uuid:  If True, generates a UUID-based ID. If False, generates a timestamp-based ID.

    Returns:
        A string representing the unique run ID.

    The choice between UUID and timestamp depends on the environment:

    *   **Multi-user environments:** Use UUIDs to guarantee uniqueness and avoid conflicts.
    *   **Single-user environments:**  Use timestamps for improved human readability.
    """
    if use_uuid:
        return RUN_ID_PREFIX + str(uuid.uuid4())
    else:
        return RUN_ID_PREFIX + datetime.now().strftime("%Y%m%d_%H%M%S")


if __name__ == "__main__":
    print(generate_run_id(use_uuid=True))
    print(generate_run_id(use_uuid=False))
