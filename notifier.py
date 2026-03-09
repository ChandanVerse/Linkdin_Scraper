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
    "Google Jobs": 0x4285F4,
}


def _post_embed(embed: dict) -> bool:
    """POST a single embed to Discord, handling 429 rate-limit with one retry."""
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)
        if resp.status_code == 429:
            try:
                delay = resp.json().get("retry_after", 5)
            except ValueError:
                delay = 5
            time.sleep(delay)
            resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)
        return resp.status_code in (200, 204)
    except requests.RequestException as e:
        print(f"  [ERROR] Discord POST failed: {e}")
        return False


def send_discord_notification(job):
    source = job.get("source", "Unknown")
    applied = job.get("applied", False)

    if applied:
        color = 0x00C853  # green for auto-applied
        title = f"Applied: {job['title']}"
    else:
        color = SOURCE_COLORS.get(source, 0x808080)
        title = job["title"]

    fields = [
        {"name": "Company", "value": job["company"], "inline": True},
        {"name": "Location", "value": job["location"], "inline": True},
        {"name": "Source", "value": source, "inline": True},
        {"name": "Keyword", "value": job["keyword"], "inline": True},
        {"name": "Apply", "value": f"[View Job]({job['url']})"},
    ]
    if applied:
        fields.append({"name": "Status", "value": "Auto-Applied", "inline": True})

    embed = {
        "title": title,
        "url": job["url"],
        "color": color,
        "fields": fields,
        "footer": {"text": f"Job ID: {job['job_id']}"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return _post_embed(embed)


def send_discord_alert(message: str, color: int = 0xFF0000):
    """Send a plain-text alert embed to Discord (e.g. login failures)."""
    embed = {
        "title": "Scraper Alert",
        "description": message,
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return _post_embed(embed)


def notify_new_jobs(jobs):
    sent = 0
    for job in jobs:
        source = job.get("source", "")
        print(f"  Notifying: {job['title']} at {job['company']} [{source}]")
        if send_discord_notification(job):
            sent += 1
        time.sleep(1)
    return sent
