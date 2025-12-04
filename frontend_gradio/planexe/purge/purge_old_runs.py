import logging
import os
import shutil
import datetime
import threading
import time

logger = logging.getLogger(__name__)

def purge_old_runs(run_dir: str, max_age_hours: float = 1.0, prefix: str = "myrun_") -> None:
    """
    Deletes files and directories in the specified run_dir older than max_age_hours and matching the specified prefix.
    """
    if not os.path.isabs(run_dir):
        raise ValueError(f"run_dir must be an absolute path: {run_dir}")
    
    if not os.path.exists(run_dir):
        logger.error(f"run_dir does not exist: {run_dir} -- skipping purge")
        return
    
    logger.info("Running purge...")
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(hours=max_age_hours)

    count_deleted = 0
    count_skip_without_prefix = 0
    count_skip_recent = 0
    count_error = 0
    for item in os.listdir(run_dir):
        if not item.startswith(prefix):
            count_skip_without_prefix += 1
            continue  # Skip files and directories that don't match the prefix

        item_path = os.path.join(run_dir, item)

        try:
            # Get the modification time of the item (file or directory)
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(item_path))

            if mtime < cutoff:
                logger.debug(f"Deleting old data: {item} from {run_dir}")
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)  # Delete the directory and all its contents
                else:
                    os.remove(item_path)  # Delete the file
                count_deleted += 1
            else:
                logger.debug(f"Skipping {item} in {run_dir}, last modified: {mtime}")
                count_skip_recent += 1

        except Exception as e:
            logger.error(f"Error processing {item} in {run_dir}: {e}")
            count_error += 1
    logger.info(f"Purge complete: {count_deleted} deleted, {count_skip_recent} skipped (recent), {count_skip_without_prefix} skipped (no prefix), {count_error} errors")

def start_purge_scheduler(run_dir: str, purge_interval_seconds: float = 3600, prefix: str = "myrun_") -> None:
    """
    Start the purge scheduler in a background thread.
    """
    logger.info(f"Starting purge scheduler for {run_dir} every {purge_interval_seconds} seconds. Prefix: {prefix}")

    if not os.path.isabs(run_dir):
        raise ValueError(f"run_dir must be an absolute path: {run_dir}")

    def purge_scheduler():
        """
        Schedules the purge_old_runs function to run periodically.
        """
        while True:
            purge_old_runs(run_dir, prefix=prefix)
            time.sleep(purge_interval_seconds)

    purge_thread = threading.Thread(target=purge_scheduler, daemon=True)
    purge_thread.start()
