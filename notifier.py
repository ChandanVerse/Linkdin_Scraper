import time
from datetime import datetime, timezone

import requests

from config import DISCORD_WEBHOOK_URL

SOURCE_COLORS = {
    "LinkedIn": 0x0A66C2,
    "Naukri": 0x2D69F0,
    "Indeed": 0x003A9B,
    "Foundit": 0xFF6B35,
    "Internshala": 0x00A5EC,
}


def send_discord_notification(job):
    source = job.get("source", "Unknown")
    color = SOURCE_COLORS.get(source, 0x808080)

    embed = {
        "title": job["title"],
        "url": job["url"],
        "color": color,
        "fields": [
            {"name": "Company", "value": job["company"], "inline": True},
            {"name": "Location", "value": job["location"], "inline": True},
            {"name": "Source", "value": source, "inline": True},
            {"name": "Keyword", "value": job["keyword"], "inline": True},
            {"name": "Apply", "value": f"[View Job]({job['url']})"},
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
        source = job.get("source", "")
        print(f"  Notifying: {job['title']} at {job['company']} [{source}]")
        if send_discord_notification(job):
            sent += 1
        time.sleep(1)
    return sent
