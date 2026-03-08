import json
import os

MAX_SEEN_JOBS = 5000


def _get_path(filename="seen_jobs.json"):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def load_seen_jobs(filename="seen_jobs.json"):
    path = _get_path(filename)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_seen_jobs(seen_jobs, filename="seen_jobs.json"):
    # Cap to prevent unbounded growth
    if len(seen_jobs) > MAX_SEEN_JOBS:
        seen_jobs = seen_jobs[-MAX_SEEN_JOBS:]
    with open(_get_path(filename), "w") as f:
        json.dump(seen_jobs, f)


def filter_new_jobs(jobs, seen_jobs):
    seen_set = set(seen_jobs)
    return [job for job in jobs if job["job_id"] not in seen_set]


def mark_jobs_seen(new_jobs, seen_jobs, filename="seen_jobs.json"):
    seen_jobs.extend(job["job_id"] for job in new_jobs)
    save_seen_jobs(seen_jobs, filename)
    return seen_jobs
