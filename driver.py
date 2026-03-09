import os
import platform
import re
import subprocess
import threading

import undetected_chromedriver as uc

from config import (
    BLACKLISTED_COMPANIES,
    BLACKLISTED_TITLE_KEYWORDS,
    MAX_JOB_AGE_HOURS,
    RELEVANT_TITLE_TERMS,
)

# Thread-local storage: each thread gets its own driver + profile
_tls = threading.local()

# Track all drivers across threads for close_all_drivers()
_all_drivers = []
_all_drivers_lock = threading.Lock()

_display = None


def set_profile(suffix: str):
    """Set Chrome profile suffix for the current thread."""
    _tls.profile_suffix = suffix


def _get_profile() -> str:
    return getattr(_tls, "profile_suffix", os.environ.get("CHROME_PROFILE_SUFFIX", ""))


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
    driver = getattr(_tls, "driver", None)
    if driver is not None:
        try:
            driver.title  # verify session is still alive
            return driver
        except Exception:
            print("  [WARN] Browser session died, restarting...")
            try:
                driver.quit()
            except Exception:
                pass
            _tls.driver = None

    _start_xvfb()

    options = uc.ChromeOptions()

    # Per-thread Chrome profile support
    profile_suffix = _get_profile()
    if profile_suffix:
        profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   f"chrome_profile_{profile_suffix}")
        os.makedirs(profile_dir, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_dir}")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # Memory-saving flags for EC2 / low-RAM servers
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--js-flags=--max-old-space-size=512")

    chrome_ver = None
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                r'reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version',
                shell=True, text=True
            )
            chrome_ver = int(out.strip().split()[-1].split(".")[0])
        else:
            out = subprocess.check_output(["google-chrome", "--version"], text=True)
            chrome_ver = int(out.strip().split()[-1].split(".")[0])
    except Exception:
        pass

    driver = uc.Chrome(options=options, headless=False, version_main=chrome_ver)
    driver.set_page_load_timeout(60)
    _tls.driver = driver

    with _all_drivers_lock:
        _all_drivers.append(driver)

    return driver


def reset_driver():
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
    """Close every driver across all threads + Xvfb."""
    global _display
    with _all_drivers_lock:
        for d in _all_drivers:
            try:
                d.quit()
            except Exception:
                pass
        _all_drivers.clear()
    _tls.driver = None
    if _display:
        try:
            _display.stop()
        except Exception:
            pass
        _display = None


# Keep backward compat alias
close_driver = close_all_drivers


def parse_age_hours(text):
    """Parse job posting age and return hours. Handles multiple formats.

    Supports:
      - Immediate: "just now", "right now", "now", "today", "posted today",
        "moments ago", "recently", "few seconds ago", "new"
      - Articles: "a minute ago", "an hour ago", "a day ago", "a month ago"
      - Qualifiers: "about 2 hours ago", "over 3 days ago", "almost a week ago",
        "less than an hour ago"
      - Prefixed: "Posted 3 days ago", "Active 2 days ago", "Updated 1 hour ago"
      - "Few" expressions: "few minutes ago", "few hours ago", "few days ago"
      - Long form: "7 minutes ago", "2 hours ago", "3 days ago", "1 year ago"
      - Plurals with +: "30+ days ago"
      - Short form: "1d", "2w", "3mo", "5h", "30m", "10s", "1y", "2yr", "2yrs"
      - Short form with ago: "2d ago", "3h ago", "1mo ago"
      - Time without "ago": "2 days", "1 month" (some sites omit "ago")
      - Special: "yesterday", "last week", "last month", "this week"
      - Absolute dates: "Jan 15, 2025", "15 Jan 2025", "2025-01-15", "01/15/2025"
    """
    from datetime import datetime

    text = text.lower().strip()

    # ── Immediate / zero-age keywords ──────────────────────────────────
    immediate_keywords = (
        "just now", "right now", "moments ago", "moment ago",
        "recently", "few seconds", "a few seconds", "posted today",
        "today", "now", "just posted", "actively hiring",
        "actively recruiting",
    )
    if any(kw in text for kw in immediate_keywords):
        return 0

    # Also match bare "new" only in standalone time-context (not in company/city names)
    if re.search(r"^\s*new\s*$", text):
        return 0

    # ── "Few <unit> ago" → small value ─────────────────────────────────
    m = re.search(
        r"(?:a\s+)?few\s+(second|minute|hour|day|week|month|year)s?\s*(?:ago)?",
        text,
    )
    if m:
        unit = m.group(1)
        if unit in ("second", "minute"):
            return 0
        elif unit == "hour":
            return 2                # "few hours" ≈ 2-3
        elif unit == "day":
            return 72               # "few days" ≈ 3
        elif unit == "week":
            return 504              # "few weeks" ≈ 3
        elif unit == "month":
            return 2160             # "few months" ≈ 3
        elif unit == "year":
            return 26280            # "few years" ≈ 3

    # ── Article form: "a minute ago", "an hour ago", "a day ago" ───────
    m = re.search(
        r"\b(?:about|over|almost|less\s+than|more\s+than)?\s*"
        r"an?\s+(second|minute|hour|day|week|month|year)\s*(?:ago)?",
        text,
    )
    if m:
        unit = m.group(1)
        if unit in ("second", "minute"):
            return 0
        elif unit == "hour":
            return 1
        elif unit == "day":
            return 24
        elif unit == "week":
            return 168
        elif unit == "month":
            return 720
        elif unit == "year":
            return 8760

    # ── Long format: "7 minutes ago", "2 hours ago", "30+ days ago" ────
    # Handles optional qualifiers ("about", "over", "almost", etc.),
    # optional plus sign after number, optional "ago" suffix, and
    # optional prefixes like "Posted", "Active", "Updated".
    m = re.search(
        r"(\d+)\+?\s*(second|minute|hour|day|week|month|year)s?"
        r"(?:\s*(?:ago|old|back))?",
        text,
    )
    if m:
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
        elif unit == "year":
            return num * 8760

    # ── Short format: "1d", "2w", "3mo", "5h", "30m", "10s", "1y" ─────
    # Also handles "2d ago", "1yr", "2yrs", "1yr ago"
    m = re.search(r"(\d+)\+?\s*(sec|min|mo|yr|yrs|[smhdwy])\w*(?:\s*ago)?", text)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit in ("s", "sec"):
            return 0
        elif unit in ("m", "min"):
            return 0
        elif unit == "h":
            return num
        elif unit == "d":
            return num * 24
        elif unit == "w":
            return num * 168
        elif unit in ("mo",):
            return num * 720
        elif unit in ("y", "yr", "yrs"):
            return num * 8760

    # ── Special keywords ───────────────────────────────────────────────
    if "yesterday" in text:
        return 24
    if "last week" in text or "this week" in text:
        return 168
    if "last month" in text or "this month" in text:
        return 720
    if "last year" in text:
        return 8760

    # ── Absolute date: "Jan 15, 2025" / "15 Jan 2025" ─────────────────
    date_formats = [
        r"%b %d, %Y",     # Jan 15, 2025
        r"%b %d %Y",      # Jan 15 2025
        r"%d %b %Y",      # 15 Jan 2025
        r"%d %b, %Y",     # 15 Jan, 2025
        r"%Y-%m-%d",      # 2025-01-15
        r"%m/%d/%Y",      # 01/15/2025
        r"%d/%m/%Y",      # 15/01/2025
    ]
    for fmt in date_formats:
        try:
            parsed = datetime.strptime(text.strip(), fmt)
            delta = datetime.now() - parsed
            return max(0, int(delta.total_seconds() / 3600))
        except ValueError:
            continue

    # ── Absolute date without year: "Jan 15" / "15 Jan" ───────────────
    short_date_formats = [r"%b %d", r"%d %b"]
    for fmt in short_date_formats:
        try:
            parsed = datetime.strptime(text.strip(), fmt)
            parsed = parsed.replace(year=datetime.now().year)
            if parsed > datetime.now():
                parsed = parsed.replace(year=datetime.now().year - 1)
            delta = datetime.now() - parsed
            return max(0, int(delta.total_seconds() / 3600))
        except ValueError:
            continue

    return None


VALID_LOCATIONS = ["bangalore", "bengaluru"]


def passes_filters(title, company, card_text=None, location=None):
    """Return (passes, skip_reason) tuple."""
    title_lower = title.lower()
    if any(kw in title_lower for kw in BLACKLISTED_TITLE_KEYWORDS):
        return False, f"{title}"
    if not any(term in title_lower for term in RELEVANT_TITLE_TERMS):
        return False, f"{title} (irrelevant)"
    if any(bl in company.lower() for bl in BLACKLISTED_COMPANIES):
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
