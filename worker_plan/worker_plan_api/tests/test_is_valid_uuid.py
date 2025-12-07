import unittest
import uuid

from worker_plan_api.uuid_util.is_valid_uuid import is_valid_uuid

class TestIsValidUUID(unittest.TestCase):
    def test_valid_uuid_hardcoded(self):
        """Test that a proper UUID (version 4) returns True."""
        valid_uuid = "1382d4a1-5eb0-42f3-b93a-74c066ae1c97"
        self.assertTrue(is_valid_uuid(valid_uuid))
        
    def test_valid_uuid_generated(self):
        """Test that a proper UUID (version 4) returns True."""
        valid_uuid = str(uuid.uuid4())
        self.assertTrue(is_valid_uuid(valid_uuid))
        
    def test_invalid_uuid_format(self):
        """Test that strings that don't follow the UUID format return False."""
        # Contains an invalid character ("x" is not a valid hexadecimal digit)
        bad_uuid = "x6e6e7e83-8db9-4ac9-88d3-0aeda252a19e"
        self.assertFalse(is_valid_uuid(bad_uuid))
        
    def test_non_uuid_string(self):
        """Test that a random non-UUID string returns False."""
        non_uuid = "this-is-not-a-uuid"
        self.assertFalse(is_valid_uuid(non_uuid))
        
    def test_empty_string(self):
        """Test that an empty string is not a valid UUID."""
        self.assertFalse(is_valid_uuid(""))

    def test_none(self):
        """Test that None is not a valid UUID."""
        self.assertFalse(is_valid_uuid(None))

    def test_non_canonical_format(self):
        """
        Test that a UUID in non-canonical format (e.g., uppercase) returns False.
        The function checks that the string form of the UUID is identical to the input.
        """
        valid_uuid = str(uuid.uuid4())
        non_canonical = valid_uuid.upper()  # Convert to uppercase
        self.assertFalse(is_valid_uuid(non_canonical))
