import json
import os

from config import MAX_SEEN_JOBS, SEEN_JOBS_FILE


def load_seen_jobs():
    if not os.path.exists(SEEN_JOBS_FILE):
        return []
    try:
        with open(SEEN_JOBS_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def save_seen_jobs(seen_jobs):
    if len(seen_jobs) > MAX_SEEN_JOBS:
        seen_jobs = seen_jobs[-MAX_SEEN_JOBS:]
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen_jobs, f)


def filter_new_jobs(jobs, seen_jobs):
    seen_set = set(seen_jobs)
    return [job for job in jobs if job["job_id"] not in seen_set]


def mark_jobs_seen(new_jobs, seen_jobs):
    seen_jobs.extend(job["job_id"] for job in new_jobs)
    return seen_jobs
