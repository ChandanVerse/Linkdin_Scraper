import os
import sys
import time
from datetime import datetime

from config import (
    DISCORD_WEBHOOK_URL,
    ENABLE_FOUNDIT,
    ENABLE_INDEED,
    ENABLE_LINKEDIN,
    ENABLE_NAUKRI,
    RUN_INTERVAL,
    SEARCH_KEYWORDS,
)
from driver import close_driver
from notifier import notify_new_jobs
from tracker import filter_new_jobs, load_seen_jobs, mark_jobs_seen, save_seen_jobs


def run_once():
    """Run a single scrape cycle."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'=' * 50}")
    print(f"[{now}] Job Scraper")
    print("=" * 50)

    seen_jobs = load_seen_jobs()
    print(f"Loaded {len(seen_jobs)} previously seen job IDs")

    all_jobs = []

    if ENABLE_LINKEDIN:
        from linkedin_scraper import scrape_all_keywords as linkedin_scrape
        print("\n[LinkedIn]")
        all_jobs.extend(linkedin_scrape(SEARCH_KEYWORDS))

    if ENABLE_NAUKRI:
        from naukri_scraper import scrape_all_keywords as naukri_scrape
        print("\n[Naukri]")
        all_jobs.extend(naukri_scrape(SEARCH_KEYWORDS))

    if ENABLE_INDEED:
        from indeed_scraper import scrape_all_keywords as indeed_scrape
        print("\n[Indeed]")
        all_jobs.extend(indeed_scrape(SEARCH_KEYWORDS))

    if ENABLE_FOUNDIT:
        from foundit_scraper import scrape_all_keywords as foundit_scrape
        print("\n[Foundit]")
        all_jobs.extend(foundit_scrape(SEARCH_KEYWORDS))

    print(f"\nTotal jobs found across all sources: {len(all_jobs)}")

    # Dedup across keywords and sources
    unique_jobs = {}
    for job in all_jobs:
        if job["job_id"] not in unique_jobs:
            unique_jobs[job["job_id"]] = job
    all_jobs = list(unique_jobs.values())
    print(f"Unique jobs after dedup: {len(all_jobs)}")

    new_jobs = filter_new_jobs(all_jobs, seen_jobs)
    print(f"New (unseen) jobs: {len(new_jobs)}")

    if new_jobs:
        print("\nSending Discord notifications...")
        sent = notify_new_jobs(new_jobs)
        print(f"Successfully sent {sent}/{len(new_jobs)} notifications")

        seen_jobs = mark_jobs_seen(new_jobs, seen_jobs)
        save_seen_jobs(seen_jobs)
        print(f"Updated seen jobs file ({len(seen_jobs)} total)")
    else:
        print("No new jobs to notify about.")


def main():
    if not DISCORD_WEBHOOK_URL:
        print("[ERROR] DISCORD_WEBHOOK_URL environment variable is not set.")
        print("Set it in .env file or as environment variable.")
        sys.exit(1)

    # LinkedIn login
    if ENABLE_LINKEDIN:
        li_email = os.environ.get("LINKEDIN_EMAIL", "")
        li_password = os.environ.get("LINKEDIN_PASSWORD", "")

        if li_email and li_password:
            from linkedin_scraper import linkedin_login
            print("Logging into LinkedIn...")
            if not linkedin_login(li_email, li_password):
                print("[WARN] Login failed. Continuing without login.")
        else:
            print("[INFO] No LinkedIn credentials set. Running without login.")

    if "--once" in sys.argv:
        run_once()
        close_driver()
        return

    print(f"\nStarting scraper loop (every {RUN_INTERVAL}s). Press Ctrl+C to stop.\n")
    try:
        while True:
            try:
                run_once()
                print(f"\nNext run in {RUN_INTERVAL} seconds...")
                time.sleep(RUN_INTERVAL)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"\n[ERROR] {e}")
                print(f"Retrying in {RUN_INTERVAL} seconds...")
                time.sleep(RUN_INTERVAL)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        close_driver()


if __name__ == "__main__":
    main()
