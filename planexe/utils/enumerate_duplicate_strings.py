def enumerate_duplicate_strings(input: dict[str, str]) -> dict[str, str]:
    """
    Enumerate duplicate string values in a dictionary by appending (1), (2), (3), etc.
    
    Args:
        input: Dictionary with string keys and string values
        
    Returns:
        Dictionary with the same keys but duplicate values are numbered
        
    Example:
        >>> input = {'a': 'duplicate', 'b': 'duplicate', 'c': 'unique'}
        >>> enumerate_duplicate_strings(input)
        {'a': 'duplicate (1)', 'b': 'duplicate (2)', 'c': 'unique'}
    """
    if not isinstance(input, dict):
        raise ValueError("Input must be a dictionary")
    
    result = {}
    value_counts = {}
    
    # First pass: count occurrences
    for key, value in input.items():
        value_counts[value] = value_counts.get(value, 0) + 1
    
    # Second pass: build result with numbering
    value_used_counts = {}
    for key, value in input.items():
        if value_counts[value] > 1:
            value_used_counts[value] = value_used_counts.get(value, 0) + 1
            result[key] = f"{value} ({value_used_counts[value]})"
        else:
            result[key] = value
    
    return result
