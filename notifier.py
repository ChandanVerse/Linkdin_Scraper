"""Discord webhook notifications for new job postings."""

import time
from datetime import datetime, timezone

import requests

from config import DISCORD_WEBHOOK_URL

SOURCE_COLORS = {
    "LinkedIn": 0x0A66C2,
    "Naukri": 0x2D69F0,
    "Internshala": 0x00A5EC,
}


def _post_embed(embed: dict) -> bool:
    """POST a single embed to Discord, handling 429 rate-limit with one retry."""
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)
        if resp.status_code == 429:
            delay = resp.json().get("retry_after", 5) if resp.text else 5
            time.sleep(delay)
            resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)
        return resp.status_code in (200, 204)
    except requests.RequestException as e:
        print(f"  [ERROR] Discord POST failed: {e}")
        return False


def send_discord_notification(job):
    """Send a rich embed to Discord for a single job posting."""
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
    return _post_embed(embed)
