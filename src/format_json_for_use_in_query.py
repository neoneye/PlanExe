import json
from typing import Union, Dict, List, Any

# Define a type alias for JSON data that can be either a dict or a list
JSONType = Union[Dict[str, Any], List[Any]]

def format_json_for_use_in_query(d: JSONType) -> str:
    """
    Format a dictionary or list as a JSON string for use in a query.
    We are not interested in the several unwanted fields if it's a dictionary.
    """
    if isinstance(d, dict):
        # Make a copy to avoid mutating the original data
        result_dict = d.copy()
        # Remove unwanted keys if they exist
        result_dict.pop('metadata', None)
        result_dict.pop('query', None)
        result_dict.pop('user_prompt', None)
        result_dict.pop('system_prompt', None)
        return json.dumps(result_dict, separators=(',', ':'))
    elif isinstance(d, list):
        # If it's a list, simply convert it to a JSON string
        return json.dumps(d, separators=(',', ':'))
    else:
        raise TypeError("Input must be a dictionary or a list")

if __name__ == "__main__":
    data_dict = {
        'key1': 'value1',
        'key2': 'value2',
        'query': 'long text input from the user',
        'metadata': {
            'duration': 42,
        }
    }
    expected_dict = '{"key1":"value1","key2":"value2"}'
    assert format_json_for_use_in_query(data_dict) == expected_dict

    data_list = [
        'item1',
        'item2',
        'item3',
    ]
    expected_list = '["item1","item2","item3"]'
    assert format_json_for_use_in_query(data_list) == expected_list
    print('PASSED')
