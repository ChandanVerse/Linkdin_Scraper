"""
Shared Selenium driver and job filters for all scrapers.
"""

import os
import re
import threading

from seleniumbase import Driver

from config import (
    BLACKLISTED_COMPANIES,
    BLACKLISTED_TITLE_KEYWORDS,
    MAX_JOB_AGE_HOURS,
    RELEVANT_TITLE_TERMS,
)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Thread-local storage: each thread gets its own driver
_tls = threading.local()

# Track all drivers across threads for close_all_drivers()
_all_drivers = []
_all_drivers_lock = threading.Lock()
_creation_lock = threading.Lock()


# ── Driver lifecycle ───────────────────────────────────────────────────

def get_driver():
    """Get or create a headless Chrome driver for the current thread."""
    driver = getattr(_tls, "driver", None)
    if driver is not None:
        try:
            driver.title
            return driver
        except Exception:
            print("  [WARN] Browser session died, restarting...")
            try:
                driver.quit()
            except Exception:
                pass
            _tls.driver = None

    with _creation_lock:
        driver = Driver(
            uc=True,
            headless=True,
            chromium_arg="--no-sandbox,--disable-dev-shm-usage,--disable-gpu",
            page_load_strategy="normal",
        )
        driver.set_page_load_timeout(60)
        _tls.driver = driver
        with _all_drivers_lock:
            _all_drivers.append(driver)

    return driver


def reset_driver():
    """Quit the current thread's driver."""
    driver = getattr(_tls, "driver", None)
    if driver:
        try:
            driver.quit()
        except Exception:
            pass
        with _all_drivers_lock:
            if driver in _all_drivers:
                _all_drivers.remove(driver)
    _tls.driver = None


def close_all_drivers():
    """Quit every driver across all threads."""
    with _all_drivers_lock:
        for d in _all_drivers:
            try:
                d.quit()
            except Exception:
                pass
        _all_drivers.clear()
    _tls.driver = None


# ── Age parsing ────────────────────────────────────────────────────────

# Unit → hours multiplier
_UNIT_HOURS = {
    "second": 0, "minute": 0, "hour": 1, "day": 24,
    "week": 168, "month": 720, "year": 8760,
}
_SHORT_UNIT_HOURS = {
    "s": 0, "sec": 0, "m": 0, "min": 0, "h": 1,
    "d": 24, "w": 168, "mo": 720, "y": 8760, "yr": 8760, "yrs": 8760,
}
# "Few X" defaults (≈3 of that unit)
_FEW_HOURS = {
    "second": 0, "minute": 0, "hour": 2, "day": 72,
    "week": 504, "month": 2160, "year": 26280,
}


def parse_age_hours(text):
    """Parse a relative time string and return the age in hours (or None)."""
    from datetime import datetime

    text = text.lower().strip()

    # Immediate / zero-age
    if any(kw in text for kw in (
        "just now", "right now", "moments ago", "moment ago", "recently",
        "few seconds", "a few seconds", "posted today", "today", "now",
        "just posted", "actively hiring", "actively recruiting",
    )):
        return 0
    if re.search(r"^\s*new\s*$", text):
        return 0

    # "Few <unit> ago"
    m = re.search(r"(?:a\s+)?few\s+(second|minute|hour|day|week|month|year)s?\s*(?:ago)?", text)
    if m:
        return _FEW_HOURS.get(m.group(1), 0)

    # Article form: "a minute ago", "an hour ago"
    m = re.search(
        r"\b(?:about|over|almost|less\s+than|more\s+than)?\s*"
        r"an?\s+(second|minute|hour|day|week|month|year)\s*(?:ago)?", text,
    )
    if m:
        return _UNIT_HOURS.get(m.group(1), 0)

    # Long form: "7 minutes ago", "30+ days ago"
    m = re.search(r"(\d+)\+?\s*(second|minute|hour|day|week|month|year)s?(?:\s*(?:ago|old|back))?", text)
    if m:
        return int(m.group(1)) * _UNIT_HOURS.get(m.group(2), 0)

    # Short form: "1d", "2w", "3mo", "5h"
    m = re.search(r"(\d+)\+?\s*(sec|min|mo|yr|yrs|[smhdwy])\w*(?:\s*ago)?", text)
    if m:
        return int(m.group(1)) * _SHORT_UNIT_HOURS.get(m.group(2), 0)

    # Keywords
    if "yesterday" in text:
        return 24
    if "last week" in text or "this week" in text:
        return 168
    if "last month" in text or "this month" in text:
        return 720
    if "last year" in text:
        return 8760

    # Absolute dates
    for fmt in ("%b %d, %Y", "%b %d %Y", "%d %b %Y", "%d %b, %Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            delta = datetime.now() - datetime.strptime(text.strip(), fmt)
            return max(0, int(delta.total_seconds() / 3600))
        except ValueError:
            continue

    for fmt in ("%b %d", "%d %b"):
        try:
            parsed = datetime.strptime(text.strip(), fmt).replace(year=datetime.now().year)
            if parsed > datetime.now():
                parsed = parsed.replace(year=datetime.now().year - 1)
            return max(0, int((datetime.now() - parsed).total_seconds() / 3600))
        except ValueError:
            continue

    return None


# ── Job filters ────────────────────────────────────────────────────────

VALID_LOCATIONS = ["bangalore", "bengaluru"]


def passes_filters(title, company, card_text=None, location=None):
    """Return (passes, skip_reason) tuple."""
    title_lower = title.lower()
    if any(kw in title_lower for kw in BLACKLISTED_TITLE_KEYWORDS):
        return False, f"{title}"
    if not any(term in title_lower for term in RELEVANT_TITLE_TERMS):
        return False, f"{title} (irrelevant)"
    if any(bl.lower() in company.lower() for bl in BLACKLISTED_COMPANIES):
        return False, f"{company} (blacklisted)"
    if location and not any(loc in location.lower() for loc in VALID_LOCATIONS):
        return False, f"{title} (location: {location})"
    if card_text:
        age = parse_age_hours(card_text.lower())
        if age is not None and age > MAX_JOB_AGE_HOURS:
            return False, f"{title} (posted {age}h ago)"
        if age is None:
            print(f"    [WARN] Unknown posting age: '{card_text[:60]}' for {title}")
    return True, None


def enforce_tab_limit(max_tabs=2):
    """
    Checks the number of open window handles for the current thread's driver
    and closes any extra handles beyond max_tabs.
    """
    driver = getattr(_tls, "driver", None)
    if not driver:
        return
    try:
        handles = driver.window_handles
        if len(handles) > max_tabs:
            print(f"  [WARN] Found {len(handles)} tabs open. Enforcing limit of {max_tabs}...")
            # Close extra handles from the end
            for handle in reversed(handles[max_tabs:]):
                driver.switch_to.window(handle)
                driver.close()
            # Switch back to the first handle
            driver.switch_to.window(handles[0])
    except Exception as e:
        print(f"  [WARN] Failed to enforce tab limit: {e}")
