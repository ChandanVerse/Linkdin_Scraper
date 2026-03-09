"""
main.py — sequential scraping with instant per-job Discord notifications.

Order: LinkedIn → Internshala → Naukri

Jobs are sent to Discord the moment they are found and verified as new —
not after the full scrape cycle finishes.
"""

import os
import shutil
import sys
import time
from datetime import datetime

from config import (
    DISCORD_WEBHOOK_URL,
    ENABLE_GOOGLE_JOBS,
    ENABLE_INTERNSHALA,
    ENABLE_LINKEDIN,
    ENABLE_NAUKRI,
    LINKEDIN_ACCOUNTS,
    RUN_INTERVAL,
    SEARCH_KEYWORDS,
)


def _migrate_seen_jobs():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(base_dir, "seen_jobs.json")
    if not os.path.exists(src):
        return
    for target_name in ("seen_jobs_linkedin.json", "seen_jobs_others.json"):
        target = os.path.join(base_dir, target_name)
        if not os.path.exists(target):
            shutil.copy2(src, target)
            print(f"  Migrated {src} -> {target}")


def _make_instant_notifier(label: str, tracking_file: str):
    """
    Returns a callback: on_new_job(job) → notify Discord instantly + mark seen.

    The scraper calls this for every job the moment it passes filters.
    Seen-job state is kept in memory and flushed to disk after each notify
    so duplicate suppression works across restarts too.
    """
    from notifier import send_discord_notification
    from tracker import load_seen_jobs, mark_jobs_seen

    seen_jobs = load_seen_jobs(tracking_file)
    seen_set = set(seen_jobs)

    def on_new_job(job: dict):
        nonlocal seen_jobs, seen_set
        job_id = job["job_id"]
        if job_id in seen_set:
            return  # already notified this run or a previous one

        print(f"  [NOTIFY] {job['title']} at {job['company']} [{label}]")
        ok = send_discord_notification(job)
        if ok:
            seen_set.add(job_id)
            seen_jobs = mark_jobs_seen([job], seen_jobs, tracking_file)
        else:
            print(f"  [WARN] Discord notify failed for {job_id}")

    def reload():
        """Call at the start of each cycle to pick up any new seen_jobs from disk."""
        nonlocal seen_jobs, seen_set
        seen_jobs = load_seen_jobs(tracking_file)
        seen_set = set(seen_jobs)

    on_new_job.reload = reload
    return on_new_job


def main():
    if not DISCORD_WEBHOOK_URL:
        print("[ERROR] DISCORD_WEBHOOK_URL is not set. Check your .env file.")
        sys.exit(1)

    _migrate_seen_jobs()

    if ENABLE_LINKEDIN and not LINKEDIN_ACCOUNTS:
        print("[ERROR] ENABLE_LINKEDIN is True but no accounts are configured in .env.")
        sys.exit(1)

    once = "--once" in sys.argv

    # Create per-source instant notifiers (persist across cycles)
    li_notify  = _make_instant_notifier("LinkedIn",    "seen_jobs_linkedin.json")
    oth_notify = _make_instant_notifier("Others",      "seen_jobs_others.json")

    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{'=' * 55}")
        print(f"[{now}] Starting scrape cycle")
        print("=" * 55)

        # Reload seen-job sets at the top of each cycle
        li_notify.reload()
        oth_notify.reload()

        # ── 1. LinkedIn ────────────────────────────────────────────────
        if ENABLE_LINKEDIN:
            print("\n--- [LinkedIn] ---")
            try:
                from linkedin_scraper import scrape_all_keywords
                scrape_all_keywords(SEARCH_KEYWORDS, on_new_job=li_notify)
            except Exception as e:
                print(f"[LinkedIn] ERROR: {e}")
                from driver import reset_driver
                reset_driver()

        # ── 2. Internshala ─────────────────────────────────────────────
        if ENABLE_INTERNSHALA:
            print("\n--- [Internshala] ---")
            try:
                from internshala_scraper import scrape_all_keywords
                scrape_all_keywords(SEARCH_KEYWORDS, on_new_job=oth_notify)
            except Exception as e:
                print(f"[Internshala] ERROR: {e}")
                from driver import reset_driver
                reset_driver()

        # ── 3. Naukri ──────────────────────────────────────────────────
        if ENABLE_NAUKRI:
            print("\n--- [Naukri] ---")
            try:
                from naukri_scraper import scrape_all_keywords
                scrape_all_keywords(SEARCH_KEYWORDS, on_new_job=oth_notify)
            except Exception as e:
                print(f"[Naukri] ERROR: {e}")
                from driver import reset_driver
                reset_driver()

        # ── 4. Google Jobs ────────────────────────────────────────────
        if ENABLE_GOOGLE_JOBS:
            print("\n--- [Google Jobs] ---")
            try:
                from google_jobs_scraper import scrape_all_keywords
                scrape_all_keywords(SEARCH_KEYWORDS, on_new_job=oth_notify)
            except Exception as e:
                print(f"[Google Jobs] ERROR: {e}")
                from driver import reset_driver
                reset_driver()

        if once:
            print("\nDone (--once mode).")
            break

        print(f"\nCycle complete. Next run in {RUN_INTERVAL}s...")
        time.sleep(RUN_INTERVAL)


if __name__ == "__main__":
    main()