import os
import platform
import re

import undetected_chromedriver as uc

from config import BLACKLISTED_COMPANIES, MAX_JOB_AGE_HOURS

_driver = None
_display = None

EXCLUDE_TITLE_KEYWORDS = [
    "senior", "sr.", "sr ", "lead", "principal", "staff", "manager",
    "director", "head of", "vp ", "vice president", "architect",
    "10+", "8+", "7+", "6+", "5+", "4+",
    "14+", "12+", "11+", "9+",
    "years", "yrs",
    "l4", "l5", "l6", "l7",
    "sde 3", "sde3", "sde-3", "sde iii", "sde-iii",
    "technologist",
]


def _start_xvfb():
    """Start virtual display on Linux (for AWS/cloud servers)."""
    global _display
    if _display is not None:
        return
    if platform.system() != "Linux":
        return
    if os.environ.get("DISPLAY"):
        return
    try:
        from xvfbwrapper import Xvfb
        _display = Xvfb(width=1920, height=1080)
        _display.start()
        print("  Started Xvfb virtual display")
    except ImportError:
        print("  [WARN] xvfbwrapper not installed. Install with: pip install xvfbwrapper")


def get_driver():
    global _driver
    if _driver is not None:
        return _driver

    _start_xvfb()

    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    _driver = uc.Chrome(options=options, headless=False)
    return _driver


def reset_driver():
    global _driver
    try:
        _driver.quit()
    except Exception:
        pass
    _driver = None


def close_driver():
    global _driver, _display
    if _driver:
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None
    if _display:
        try:
            _display.stop()
        except Exception:
            pass
        _display = None


def parse_age_hours(text):
    """Parse '7 minutes ago', '2 hours ago', '3 days ago' etc. and return age in hours."""
    m = re.search(r"(\d+)\s*(second|minute|hour|day|week|month)s?\s*ago", text)
    if not m:
        return None
    num = int(m.group(1))
    unit = m.group(2)
    if unit in ("second", "minute"):
        return 0
    elif unit == "hour":
        return num
    elif unit == "day":
        return num * 24
    elif unit == "week":
        return num * 168
    elif unit == "month":
        return num * 720
    return None


def passes_filters(title, company, card_text=None):
    """Return (passes, skip_reason) tuple."""
    if any(kw in title.lower() for kw in EXCLUDE_TITLE_KEYWORDS):
        return False, f"{title}"
    if any(bl in company.lower() for bl in BLACKLISTED_COMPANIES):
        return False, f"{company} (blacklisted)"
    if card_text:
        age = parse_age_hours(card_text.lower())
        if age is not None and age > MAX_JOB_AGE_HOURS:
            return False, f"{title} (posted {age}h+ ago)"
    return True, None
