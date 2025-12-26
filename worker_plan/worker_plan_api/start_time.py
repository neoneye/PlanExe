"""
Captures the timestamp when the PlanExe job was initiated.
This should run as early as possible in the pipeline to capture the true start time of the job,
since a job may run for 30+ minutes.

The start time is used as the project start date for creating Gantt charts.
This ensures that it's the same reference time for all tasks in the pipeline.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import re

@dataclass
class StartTime:
    server_iso_utc: str
    server_iso_local: str
    server_timezone_name: str

    @staticmethod
    def create(local_time: datetime) -> "StartTime":
        if not isinstance(local_time, datetime):
            raise ValueError(f"local_time must be a datetime object, got {type(local_time)}")

        # Convert local time to UTC, rounded to seconds
        utc_time = local_time.astimezone(timezone.utc).replace(microsecond=0)        

        # Format as YYYY-MM-DDTHH:MM:SSZ (with Z suffix instead of +00:00)
        # As in https://en.wikipedia.org/wiki/ISO_8601
        utc_str = utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Verify that the utc string has the format YYYY-MM-DDTHH:MM:SSZ
        if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", utc_str):
            raise ValueError(f"Invalid UTC string: {utc_str!r}")
        
        # Get timezone name from the local time
        timezone_name = local_time.tzname() or "unknown"

        # Remove microseconds from local time for consistent formatting
        local_time_no_microseconds = local_time.replace(microsecond=0)

        return StartTime(
            server_iso_utc=utc_str,
            server_iso_local=local_time_no_microseconds.isoformat(),
            server_timezone_name=timezone_name
        )

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)
