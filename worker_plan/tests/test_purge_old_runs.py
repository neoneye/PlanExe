import unittest
import os
import shutil
import time
import sys

# Ensure the worker_plan directory is on the path for imports.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worker_plan.purge_old_runs import purge_old_runs


class TestPurgeOldRuns(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary directory for the runs
        self.test_run_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_run"))
        if os.path.exists(self.test_run_dir):
            shutil.rmtree(self.test_run_dir)
        os.makedirs(self.test_run_dir, exist_ok=True)

        # Create some dummy run directories with different modification times
        self.create_dummy_dir("myrun_dir1", hours_old=0.5)
        self.create_dummy_dir("myrun_dir2", hours_old=1.5)
        self.create_dummy_dir("myrun_dir3", hours_old=2)
        self.create_dummy_dir("myrun_dir4", hours_old=0.25)
        self.create_dummy_dir("myrun_dir5", hours_old=1)
        self.create_dummy_dir("myrun_dir6", hours_old=0)
        self.create_dummy_dir("other_dir7", hours_old=1.5) # doesn't have the prefix, so don't delete
        self.create_dummy_file("other_file.txt", hours_old=5) # doesn't have the prefix, so don't delete
        self.create_dummy_file("myrun_file1.txt", hours_old=0.25)
        self.create_dummy_file("myrun_file2.txt", hours_old=1.5)

    def tearDown(self):
        """Clean up test environment after each test."""
        # Remove the temporary run directory and its contents
        if os.path.exists(self.test_run_dir):
            shutil.rmtree(self.test_run_dir)

    def create_dummy_dir(self, dirname: str, hours_old: float):
        """Creates a dummy run directory with a specific modification time."""
        path = os.path.join(self.test_run_dir, dirname)
        os.makedirs(path, exist_ok=True)

        # Set the modification time of the directory
        mtime = time.time() - (hours_old * 3600)  # seconds
        os.utime(path, (mtime, mtime))

    def create_dummy_file(self, filename: str, hours_old: float):
        """Create a dummy file in the test directory."""
        path = os.path.join(self.test_run_dir, filename)
        with open(path, "w") as f:
            f.write("This is a dummy file.")

        # Set the modification time of the file
        mtime = time.time() - (hours_old * 3600)  # seconds
        os.utime(path, (mtime, mtime))

    def test_purge_old_runs(self):
        """Tests the purge_old_runs function."""
        max_age_hours = 0.95
        purge_old_runs(self.test_run_dir, max_age_hours=max_age_hours, prefix="myrun_")  # Pass the directory

        # Check which runs should have been purged
        runs_to_keep = ["myrun_dir1", "myrun_dir4", "myrun_dir6", "other_dir7", "other_file.txt", "myrun_file1.txt"]
        runs_to_purge = ["myrun_dir2", "myrun_dir3", "myrun_dir5", "myrun_file2.txt"]

        for run_id in runs_to_keep:
            run_path = os.path.join(self.test_run_dir, run_id)
            self.assertTrue(os.path.exists(run_path), f"Run {run_id} should not have been purged.")

        for run_id in runs_to_purge:
            run_path = os.path.join(self.test_run_dir, run_id)
            self.assertFalse(os.path.exists(run_path), f"Run {run_id} should have been purged.")

    def test_purge_no_runs(self):
        """Test when no runs are older than the max_age_hours."""

        # Set all runs to be very recent.
        for item in os.listdir(self.test_run_dir):
          item_path = os.path.join(self.test_run_dir, item)
          mtime = time.time()  # Now
          os.utime(item_path, (mtime, mtime))

        max_age_hours = 1.0
        purge_old_runs(self.test_run_dir, max_age_hours=max_age_hours, prefix="myrun_")  # Pass the directory

        # All runs should still exist, including the one with the wrong prefix.
        expected_runs = ["myrun_dir1", "myrun_dir2", "myrun_dir3", "myrun_dir4", "myrun_dir5", "myrun_dir6", "other_dir7", "other_file.txt", "myrun_file1.txt", "myrun_file2.txt"]
        for run_id in expected_runs:
            run_path = os.path.join(self.test_run_dir, run_id)
            self.assertTrue(os.path.exists(run_path), f"Run {run_id} should not have been purged.")
