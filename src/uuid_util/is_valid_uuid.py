import uuid

def is_valid_uuid(uuid_to_test, version: int = 4) -> bool:
    """
    Check if uuid_to_test is a valid UUID.

    Args:
        uuid_to_test: The UUID string to validate.
        version (int): The UUID version to check against. Defaults to 4.

    Returns:
        bool: True if uuid_to_test is a valid UUID in canonical form, False otherwise.
    """
    try:
        uuid_obj = uuid.UUID(uuid_to_test, version=version)
    except (ValueError, TypeError):
        return False

    # Optionally, ensure that the string is in the canonical form.
    return str(uuid_obj) == uuid_to_test
