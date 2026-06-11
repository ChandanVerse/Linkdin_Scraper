"""
main.py — parallel scraping with instant per-job Discord notifications.

Thread 1: LinkedIn
Thread 2: Internshala → Naukri

Jobs are sent to Discord the moment they are found and verified as new.
"""

import signal
import sys
import threading
from datetime import datetime

from config import (
    DISCORD_WEBHOOK_URL,
    ENABLE_INTERNSHALA,
    ENABLE_LINKEDIN,
    ENABLE_NAUKRI,
    RUN_INTERVAL,
    SEARCH_KEYWORDS,
)

_shutdown = threading.Event()


def _handle_sigint(sig, frame):
    print("\n[INFO] Ctrl+C received — shutting down gracefully...")
    _shutdown.set()


signal.signal(signal.SIGINT, _handle_sigint)


def _make_instant_notifier(label: str, tracking_file: str):
    """
    Returns a callback: on_new_job(job) → notify Discord instantly + mark seen.
    Thread-safe via internal lock.
    """
    from notifier import send_discord_notification
    from tracker import load_seen_jobs, mark_jobs_seen

    seen_jobs = load_seen_jobs(tracking_file)
    seen_set = set(seen_jobs)
    lock = threading.Lock()

    def on_new_job(job: dict):
        nonlocal seen_jobs, seen_set
        job_id = job["job_id"]
        with lock:
            if job_id in seen_set:
                return
            print(f"  [NOTIFY] {job['title']} at {job['company']} [{label}]")
            if send_discord_notification(job):
                seen_set.add(job_id)
                seen_jobs = mark_jobs_seen([job], seen_jobs, tracking_file)
            else:
                print(f"  [WARN] Discord notify failed for {job_id}")

    def reload():
        nonlocal seen_jobs, seen_set
        with lock:
            seen_jobs = load_seen_jobs(tracking_file)
            seen_set = set(seen_jobs)

    on_new_job.reload = reload
    return on_new_job


def _run_startup_sweep(li_notify):
    """One-time 24h LinkedIn sweep to catch jobs posted while offline."""
    if not ENABLE_LINKEDIN:
        return
    print("\n--- [LinkedIn] Startup 24h sweep ---")
    try:
        from linkedin_scraper import startup_sweep
        startup_sweep(SEARCH_KEYWORDS, on_new_job=li_notify)
    except Exception as e:
        print(f"[LinkedIn] Startup sweep ERROR: {e}")
        from driver import reset_driver
        reset_driver()


def _run_group1(li_notify):
    """Thread 1: LinkedIn."""
    if ENABLE_LINKEDIN:
        print("\n--- [LinkedIn] (Thread 1) ---")
        try:
            from linkedin_scraper import scrape_all_keywords
            scrape_all_keywords(SEARCH_KEYWORDS, on_new_job=li_notify)
        except Exception as e:
            print(f"[LinkedIn] ERROR: {e}")
            from driver import reset_driver
            reset_driver()


def _run_group2(oth_notify):
    """Thread 2: Internshala → Naukri."""
    if ENABLE_INTERNSHALA:
        print("\n--- [Internshala] (Thread 2) ---")
        try:
            from internshala_scraper import scrape_all_keywords
            scrape_all_keywords(SEARCH_KEYWORDS, on_new_job=oth_notify)
        except Exception as e:
            print(f"[Internshala] ERROR: {e}")
            from driver import reset_driver
            reset_driver()

    if ENABLE_NAUKRI:
        print("\n--- [Naukri] (Thread 2) ---")
        try:
            from naukri_scraper import scrape_all_keywords
            scrape_all_keywords(SEARCH_KEYWORDS, on_new_job=oth_notify)
        except Exception as e:
            print(f"[Naukri] ERROR: {e}")
            from driver import reset_driver
            reset_driver()

    from driver import reset_driver
    reset_driver()


def main():
    if not DISCORD_WEBHOOK_URL:
        print("[ERROR] DISCORD_WEBHOOK_URL is not set. Check your .env file.")
        sys.exit(1)

    once = "--once" in sys.argv

    li_notify  = _make_instant_notifier("LinkedIn", "seen_jobs_linkedin.json")
    oth_notify = _make_instant_notifier("Others",   "seen_jobs_others.json")

    # Startup sweep
    if not _shutdown.is_set():
        print(f"\n{'=' * 55}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running startup 24h sweep")
        print("=" * 55)
        _run_startup_sweep(li_notify)

    while not _shutdown.is_set():
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{'=' * 55}")
        print(f"[{now}] Starting scrape cycle (parallel)")
        print("=" * 55)

        li_notify.reload()
        oth_notify.reload()

        t1 = threading.Thread(target=_run_group1, args=(li_notify,), name="LinkedIn", daemon=True)
        t2 = threading.Thread(target=_run_group2, args=(oth_notify,), name="Others",   daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        if _shutdown.is_set():
            break
        if once:
            print("\nDone (--once mode).")
            break
        if RUN_INTERVAL > 0:
            print(f"\nCycle complete. Next run in {RUN_INTERVAL}s...")
            _shutdown.wait(timeout=RUN_INTERVAL)
        else:
            print("\nCycle complete. Starting next cycle immediately...")

    print("[INFO] Cleaning up drivers...")
    from driver import close_all_drivers
    close_all_drivers()
    print("[INFO] Shutdown complete.")


if __name__ == "__main__":
    main()
