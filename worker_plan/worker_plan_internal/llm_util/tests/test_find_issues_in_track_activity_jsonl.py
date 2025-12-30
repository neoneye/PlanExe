"""
Find issues in the track_activity.jsonl file.

The "track_activity.jsonl" file has records for when the LLM starts and ends.
I'm interested in finding rows that starts, but does not end, which usually means something went wrong,
such as timeout, invalid response, interrupted, etc.

Start rows
"event_type": "LLMChatStartEvent"

End rows
"event_type": "LLMChatEndEvent"
"event_type": "LLMStructuredPredictEndEvent"

Rows that are connected have the same `"llm_executor_uuid"`, for example:
"llm_executor_uuid": "e1ae174f-00f6-42ca-b509-914d52280b3d"

For the start rows without a corresponding end row. Print out the "timestamp" field and the "llm_executor_uuid" field.
This gives me a list of LLM invocations that I have to investigate further.

USAGE:
python -m worker_plan_internal.llm_util.tests.test_find_issues_in_track_activity_jsonl /absolute/path/to/track_activity.jsonl
"""

import json
import sys
import unittest
import tempfile
import os
from typing import List, Dict, Set, Any
from dataclasses import dataclass


@dataclass
class Issue:
    """Represents an issue found in the track activity log."""
    timestamp: str
    llm_executor_uuid: str
    event_type: str


def find_issues_in_track_activity_jsonl(file_path: str) -> List[Issue]:
    """
    Find issues in the track_activity.jsonl file.
    
    Returns a list of start events that don't have corresponding end events.
    
    Args:
        file_path: Path to the JSONL file
        
    Returns:
        List of Issue objects representing start events without end events
    """
    start_events: Dict[str, Dict[str, Any]] = {}  # llm_executor_uuid -> event_data
    end_events: Set[str] = set()  # llm_executor_uuid
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"Warning: Invalid JSON on line {line_num}: {e}", file=sys.stderr)
                    continue
                
                event_type = event.get('event_type')
                event_data = event.get('event_data', {})
                tags = event_data.get('tags', {})
                llm_executor_uuid = tags.get('llm_executor_uuid')
                
                if not llm_executor_uuid:
                    continue
                
                if event_type == 'LLMChatStartEvent':
                    start_events[llm_executor_uuid] = {
                        'timestamp': event.get('timestamp'),
                        'event_type': event_type,
                        'llm_executor_uuid': llm_executor_uuid
                    }
                elif event_type in ['LLMChatEndEvent', 'LLMStructuredPredictEndEvent']:
                    end_events.add(llm_executor_uuid)
    
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except Exception as e:
        raise RuntimeError(f"Error reading file {file_path}: {e}")
    
    # Find start events without corresponding end events
    issues = []
    for llm_executor_uuid, event_data in start_events.items():
        if llm_executor_uuid not in end_events:
            issues.append(Issue(
                timestamp=event_data['timestamp'],
                llm_executor_uuid=event_data['llm_executor_uuid'],
                event_type=event_data['event_type']
            ))
    
    return issues


def main():
    """Main function for command line usage."""
    if len(sys.argv) != 2:
        print("Usage: python -m worker_plan_internal.llm_util.tests.test_find_issues_in_track_activity_jsonl <file_path>", file=sys.stderr)
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    try:
        issues = find_issues_in_track_activity_jsonl(file_path)
        
        if not issues:
            print("No issues found - all start events have corresponding end events.")
        else:
            print(f"Found {len(issues)} issues:")
            for issue in issues:
                print(f"  Timestamp: {issue.timestamp}")
                print(f"  LLM Executor UUID: {issue.llm_executor_uuid}")
                print(f"  Event Type: {issue.event_type}")
                print()
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


class TestFindIssuesInTrackActivityJsonl(unittest.TestCase):
    def test_no_issues_when_all_events_have_end(self):
        """Test that no issues are found when all start events have corresponding end events."""
        # Arrange
        test_data = [
            {"timestamp": "1984-09-20T20:41:19.925148", "event_type": "LLMChatStartEvent", 
             "event_data": {"tags": {"llm_executor_uuid": "uuid1"}}},
            {"timestamp": "1984-09-20T20:41:20.022721", "event_type": "LLMChatStartEvent", 
             "event_data": {"tags": {"llm_executor_uuid": "uuid2"}}},
            {"timestamp": "1984-09-20T20:41:23.469387", "event_type": "LLMStructuredPredictEndEvent", 
             "event_data": {"tags": {"llm_executor_uuid": "uuid1"}}},
            {"timestamp": "1984-09-20T20:41:23.482472", "event_type": "LLMChatEndEvent", 
             "event_data": {"tags": {"llm_executor_uuid": "uuid2"}}}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as tmp:
            for event in test_data:
                tmp.write(json.dumps(event) + '\n')
            tmp_path = tmp.name
        
        try:
            # Act
            issues = find_issues_in_track_activity_jsonl(tmp_path)
            
            # Assert
            self.assertEqual(len(issues), 0)
        
        finally:
            os.unlink(tmp_path)

    def test_finds_orphaned_start_events(self):
        """Test that orphaned start events (without end events) are found."""
        # Arrange
        test_data = [
            {"timestamp": "1984-09-20T20:41:19.925148", "event_type": "LLMChatStartEvent", 
             "event_data": {"tags": {"llm_executor_uuid": "uuid1"}}},
            {"timestamp": "1984-09-20T20:41:20.022721", "event_type": "LLMChatStartEvent", 
             "event_data": {"tags": {"llm_executor_uuid": "uuid2"}}},
            {"timestamp": "1984-09-20T20:41:25.123456", "event_type": "LLMChatStartEvent", 
             "event_data": {"tags": {"llm_executor_uuid": "orphan-uuid"}}},
            {"timestamp": "1984-09-20T20:41:23.469387", "event_type": "LLMStructuredPredictEndEvent", 
             "event_data": {"tags": {"llm_executor_uuid": "uuid1"}}},
            {"timestamp": "1984-09-20T20:41:23.482472", "event_type": "LLMChatEndEvent", 
             "event_data": {"tags": {"llm_executor_uuid": "uuid2"}}}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as tmp:
            for event in test_data:
                tmp.write(json.dumps(event) + '\n')
            tmp_path = tmp.name
        
        try:
            # Act
            issues = find_issues_in_track_activity_jsonl(tmp_path)
            
            # Assert
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].llm_executor_uuid, "orphan-uuid")
            self.assertEqual(issues[0].timestamp, "1984-09-20T20:41:25.123456")
            self.assertEqual(issues[0].event_type, "LLMChatStartEvent")
        
        finally:
            os.unlink(tmp_path)

    def test_handles_missing_file_gracefully(self):
        """Test that the function raises FileNotFoundError for missing files."""
        # Act & Assert
        with self.assertRaises(FileNotFoundError):
            find_issues_in_track_activity_jsonl("/nonexistent/file.jsonl")

    def test_handles_invalid_json_gracefully(self):
        """Test that the function handles invalid JSON lines gracefully."""
        # Arrange
        test_data = [
            '{"timestamp": "1984-09-20T20:41:19.925148", "event_type": "LLMChatStartEvent", "event_data": {"tags": {"llm_executor_uuid": "uuid1"}}}',
            'invalid json line',
            '{"timestamp": "1984-09-20T20:41:20.022721", "event_type": "LLMChatStartEvent", "event_data": {"tags": {"llm_executor_uuid": "uuid2"}}}',
            '{"timestamp": "1984-09-20T20:41:23.469387", "event_type": "LLMStructuredPredictEndEvent", "event_data": {"tags": {"llm_executor_uuid": "uuid1"}}}'
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as tmp:
            for line in test_data:
                tmp.write(line + '\n')
            tmp_path = tmp.name
        
        try:
            # Act
            issues = find_issues_in_track_activity_jsonl(tmp_path)
            
            # Assert - should find one orphaned event (uuid2)
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].llm_executor_uuid, "uuid2")
        
        finally:
            os.unlink(tmp_path)

    def test_works_with_production_file(self):
        """Test that the function works with the actual production test file."""
        # Arrange
        test_file_path = os.path.join(os.path.dirname(__file__), 'test_data', 'test_track_activity.jsonl')
        
        # Act
        issues = find_issues_in_track_activity_jsonl(test_file_path)
        
        # Assert - based on our test data, we should find one orphaned event
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].llm_executor_uuid, "orphan-uuid-123")
        self.assertEqual(issues[0].event_type, "LLMChatStartEvent")


if __name__ == '__main__':
    # Run tests if called directly, otherwise run main for command line usage
    if len(sys.argv) > 1 and sys.argv[1] != 'test':
        main()
    else:
        unittest.main()

