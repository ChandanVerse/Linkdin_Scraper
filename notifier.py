import time
from datetime import datetime, timezone

import requests

from config import DISCORD_WEBHOOK_URL


def send_discord_notification(job):
    """Send a rich embed message to Discord for a new job posting."""
    if not DISCORD_WEBHOOK_URL:
        print("  [WARN] DISCORD_WEBHOOK_URL not set, skipping notification")
        return False

    embed = {
        "title": job["title"],
        "url": job["url"],
        "color": 0x0A66C2,  # LinkedIn blue
        "fields": [
            {"name": "Company", "value": job["company"], "inline": True},
            {"name": "Location", "value": job["location"], "inline": True},
            {"name": "Keyword", "value": job["keyword"], "inline": True},
            {"name": "Apply", "value": f"[View on LinkedIn]({job['url']})", "inline": False},
        ],
        "footer": {"text": f"Job ID: {job['job_id']}"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    payload = {
        "embeds": [embed],
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)

        # Handle Discord rate limits
        if response.status_code == 429:
            retry_after = response.json().get("retry_after", 5)
            print(f"  [RATE LIMITED] Waiting {retry_after}s before retrying...")
            time.sleep(retry_after)
            response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)

        if response.status_code in (200, 204):
            return True
        else:
            print(f"  [ERROR] Discord returned status {response.status_code}: {response.text}")
            return False

    except requests.RequestException as e:
        print(f"  [ERROR] Failed to send Discord notification: {e}")
        return False


def notify_new_jobs(jobs):
    """Send Discord notifications for a list of new jobs.

    Returns the count of successfully sent notifications.
    """
    sent = 0
    for job in jobs:
        print(f"  Notifying: {job['title']} at {job['company']}")
        if send_discord_notification(job):
            sent += 1
        # Small delay between messages to respect rate limits
        time.sleep(1)
    return sent
