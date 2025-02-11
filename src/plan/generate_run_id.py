from datetime import datetime
import uuid

def generate_run_id(use_uuid: bool):
    """
    Generates a unique ID, either a UUID or a timestamp.

    In a multi user environment, use UUID to avoid conflicts.
    In a single user environment, use timestamp for human readability.
    """
    if use_uuid:
        return str(uuid.uuid4())
    else:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

if __name__ == "__main__":
    print(generate_run_id(use_uuid=True))
    print(generate_run_id(use_uuid=False))
