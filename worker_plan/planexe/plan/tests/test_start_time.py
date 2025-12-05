from datetime import datetime
import unittest
import pytz
from planexe.plan.start_time import StartTime

class TestStartTime(unittest.TestCase):        
    def test_create_current_time(self):
        """Test that current time is properly handled"""
        # Arrange
        t = datetime.now().astimezone()

        # Act
        start_time = StartTime.create(t)
        
        # Assert
        self.assertRegex(start_time.server_iso_utc, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertIsNotNone(start_time.server_iso_local)
        self.assertIsNotNone(start_time.server_timezone_name)

    def test_create_with_weird_timezone1(self):
        # Arrange
        # The Pacific/Chatham timezonehas an unusual 45-minute offset from UTC.
        # UTC+12:45 for standard time, UTC+13:45 for daylight saving time.
        # Most timezones have offsets in whole hours or 30-minute increments
        # The Chatham Islands are one of the few places with a quarter-hour timezone offset
        tz = pytz.timezone('Pacific/Chatham')
        naive_dt = datetime(1984, 12, 30, 23, 59, 59)
        t = tz.localize(naive_dt)

        # Act
        start_time = StartTime.create(t)

        # Assert
        self.assertEqual(start_time.server_iso_utc, "1984-12-30T10:14:59Z")
        self.assertEqual(start_time.server_iso_local, "1984-12-30T23:59:59+13:45")
        self.assertEqual(start_time.server_timezone_name, "+1345")

    def test_create_with_weird_timezone2(self):
        # Arrange
        # The Pacific/Niue timezone is one of the latest timezones with UTC-11 offset.
        # UTC-11:00, meaning it's 11 hours behind UTC.
        # This makes it one of the last places on Earth to see each new day
        tz = pytz.timezone('Pacific/Niue')
        naive_dt = datetime(1984, 12, 30, 23, 59, 59)
        t = tz.localize(naive_dt)

        # Act
        start_time = StartTime.create(t)

        # Assert
        self.assertEqual(start_time.server_iso_utc, "1984-12-31T10:59:59Z")
        self.assertEqual(start_time.server_iso_local, "1984-12-30T23:59:59-11:00")
        self.assertEqual(start_time.server_timezone_name, "-11")

    def test_create_discard_unwanted_microseconds(self):
        # Arrange
        # At this point I don't want microseconds. PlanExe uses days, and sometimes hours.
        tz = pytz.timezone('Pacific/Auckland')
        naive_dt = datetime(1984, 12, 30, 23, 59, 59, 123456)
        t = tz.localize(naive_dt)

        # Act
        start_time = StartTime.create(t)

        # Assert
        self.assertEqual(start_time.server_iso_utc, "1984-12-30T10:59:59Z")
        self.assertEqual(start_time.server_iso_local, "1984-12-30T23:59:59+13:00")
        self.assertEqual(start_time.server_timezone_name, "NZDT")
