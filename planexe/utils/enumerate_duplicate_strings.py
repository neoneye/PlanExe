def enumerate_duplicate_strings(input: dict[str, str]) -> dict[str, str]:
    """
    Enumerate duplicate string values in a dictionary by appending (1), (2), (3), etc.

    Duplicate detection is case-insensitive while preserving the original
    casing in the returned values. Numbering is per case-insensitive group
    in the order the items appear in the input mapping.

    Args:
        input: Dictionary with string keys and string values

    Returns:
        Dictionary with the same keys but duplicate values are numbered

    Examples:
        Basic duplicates:
            >>> input = {'a': 'duplicate', 'b': 'duplicate', 'c': 'unique'}
            >>> enumerate_duplicate_strings(input)
            {'a': 'duplicate (1)', 'b': 'duplicate (2)', 'c': 'unique'}

        Case-insensitive duplicates (original casing preserved):
            >>> input = {'a': 'duplicate x', 'b': 'duplicate X'}
            >>> enumerate_duplicate_strings(input)
            {'a': 'duplicate x (1)', 'b': 'duplicate X (2)'}
    """
    if not isinstance(input, dict):
        raise ValueError("Input must be a dictionary")

    result: dict[str, str] = {}
    value_counts: dict[str, int] = {}

    # First pass: count occurrences using case-insensitive keys
    for _, value in input.items():
        normalized = value.casefold()
        value_counts[normalized] = value_counts.get(normalized, 0) + 1

    # Second pass: build result with numbering per normalized value
    value_used_counts: dict[str, int] = {}
    for key, value in input.items():
        normalized = value.casefold()
        count_for_value = value_counts.get(normalized, 0)
        if count_for_value > 1:
            value_used_counts[normalized] = value_used_counts.get(normalized, 0) + 1
            occurrence_index = value_used_counts[normalized]
            result[key] = f"{value} ({occurrence_index})"
        else:
            result[key] = value

    return result
