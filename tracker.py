import json
import os

from config import MAX_SEEN_JOBS, SEEN_JOBS_FILE


def load_seen_jobs():
    """Load seen job IDs from the JSON file."""
    if not os.path.exists(SEEN_JOBS_FILE):
        return []
    try:
        with open(SEEN_JOBS_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except (json.JSONDecodeError, IOError):
        pass
    return []


def save_seen_jobs(seen_jobs):
    """Save seen job IDs to the JSON file, capping at MAX_SEEN_JOBS."""
    # Keep only the most recent entries if we exceed the cap
    if len(seen_jobs) > MAX_SEEN_JOBS:
        seen_jobs = seen_jobs[-MAX_SEEN_JOBS:]
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen_jobs, f, indent=2)


def filter_new_jobs(jobs, seen_jobs):
    """Filter out jobs that have already been seen.

    Returns a list of new (unseen) jobs.
    """
    seen_set = set(seen_jobs)
    new_jobs = [job for job in jobs if job["job_id"] not in seen_set]
    return new_jobs


def mark_jobs_seen(new_jobs, seen_jobs):
    """Add new job IDs to the seen list and return the updated list."""
    for job in new_jobs:
        seen_jobs.append(job["job_id"])
    return seen_jobs
