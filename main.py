import os
import sys
import time
from datetime import datetime

from config import DISCORD_WEBHOOK_URL, RUN_INTERVAL, SEARCH_KEYWORDS
from notifier import notify_new_jobs
from scraper import close_driver, linkedin_login, scrape_all_keywords
from tracker import filter_new_jobs, load_seen_jobs, mark_jobs_seen, save_seen_jobs


def run_once():
    """Run a single scrape cycle."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'=' * 50}")
    print(f"[{now}] LinkedIn Job Scraper")
    print("=" * 50)

    seen_jobs = load_seen_jobs()
    print(f"Loaded {len(seen_jobs)} previously seen job IDs")

    print("\nScraping LinkedIn for new jobs...")
    all_jobs = scrape_all_keywords(SEARCH_KEYWORDS)
    print(f"\nTotal jobs found across all keywords: {len(all_jobs)}")

    # Dedup across keywords
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
    li_email = os.environ.get("LINKEDIN_EMAIL", "")
    li_password = os.environ.get("LINKEDIN_PASSWORD", "")

    if li_email and li_password:
        print("Logging into LinkedIn...")
        if not linkedin_login(li_email, li_password):
            print("[WARN] Login failed. Continuing without login (filters may not work).")
    else:
        print("[INFO] No LinkedIn credentials set. Running without login.")
        print("  Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD env vars for full filter support.")

    # If --once flag, run single cycle and exit
    if "--once" in sys.argv:
        run_once()
        close_driver()
        return

    # Otherwise loop forever (for local use)
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
