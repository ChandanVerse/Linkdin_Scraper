import time
from datetime import datetime, timezone

import requests

from config import DISCORD_WEBHOOK_URL


def send_discord_notification(job):
    embed = {
        "title": job["title"],
        "url": job["url"],
        "color": 0x0A66C2,
        "fields": [
            {"name": "Company", "value": job["company"], "inline": True},
            {"name": "Location", "value": job["location"], "inline": True},
            {"name": "Keyword", "value": job["keyword"], "inline": True},
            {"name": "Apply", "value": f"[View on LinkedIn]({job['url']})"},
        ],
        "footer": {"text": f"Job ID: {job['job_id']}"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)

        if resp.status_code == 429:
            time.sleep(resp.json().get("retry_after", 5))
            resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)

        return resp.status_code in (200, 204)
    except requests.RequestException as e:
        print(f"  [ERROR] Discord notification failed: {e}")
        return False


def notify_new_jobs(jobs):
    sent = 0
    for job in jobs:
        print(f"  Notifying: {job['title']} at {job['company']}")
        if send_discord_notification(job):
            sent += 1
        time.sleep(1)
    return sent
