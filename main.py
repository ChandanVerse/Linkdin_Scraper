import sys

import os

from config import DISCORD_WEBHOOK_URL, SEARCH_KEYWORDS
from notifier import notify_new_jobs
from scraper import scrape_all_keywords
from tracker import filter_new_jobs, load_seen_jobs, mark_jobs_seen, save_seen_jobs


def main():
    print("=" * 50)
    print("LinkedIn Job Scraper + Discord Notifier")
    print("=" * 50)

    # Validate webhook URL
    if not DISCORD_WEBHOOK_URL:
        print("[ERROR] DISCORD_WEBHOOK_URL environment variable is not set.")
        print("Set it as a GitHub Secret or export it locally.")
        sys.exit(1)

    # Load previously seen jobs
    seen_jobs = load_seen_jobs()
    print(f"Loaded {len(seen_jobs)} previously seen job IDs")

    # Scrape jobs for all keywords
    # In test mode, only use first keyword to speed things up
    keywords = SEARCH_KEYWORDS[:1] if os.environ.get("TEST_MODE") else SEARCH_KEYWORDS
    print("\nScraping LinkedIn for new jobs...")
    all_jobs = scrape_all_keywords(keywords)
    print(f"\nTotal jobs found across all keywords: {len(all_jobs)}")

    # Filter out duplicates (same job may appear under multiple keywords)
    unique_jobs = {}
    for job in all_jobs:
        if job["job_id"] not in unique_jobs:
            unique_jobs[job["job_id"]] = job
    all_jobs = list(unique_jobs.values())
    print(f"Unique jobs after dedup: {len(all_jobs)}")

    # Filter out already-seen jobs
    new_jobs = filter_new_jobs(all_jobs, seen_jobs)
    print(f"New (unseen) jobs: {len(new_jobs)}")

    if new_jobs:
        # Send Discord notifications
        print("\nSending Discord notifications...")
        sent = notify_new_jobs(new_jobs)
        print(f"Successfully sent {sent}/{len(new_jobs)} notifications")

        # Mark jobs as seen
        seen_jobs = mark_jobs_seen(new_jobs, seen_jobs)
        save_seen_jobs(seen_jobs)
        print(f"Updated seen jobs file ({len(seen_jobs)} total)")
    else:
        print("No new jobs to notify about.")

    print("\nDone!")


if __name__ == "__main__":
    main()
