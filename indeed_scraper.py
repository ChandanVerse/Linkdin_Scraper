"""
Indeed scraper — with Cloudflare / human-verification handling.

When Cloudflare or Indeed's bot-detection triggers, the scraper:
  1. Detects the challenge page automatically
  2. Plays an alert sound (Windows + Linux)
  3. Prints a clear console banner
  4. Pauses and polls until the challenge is solved
  5. Resumes scraping automatically once the real page loads

No data is lost — the keyword is retried after verification passes.
"""

import re
import time
import sys
import os

from bs4 import BeautifulSoup

from driver import get_driver, passes_filters

# ── Challenge detection ────────────────────────────────────────────────

# Titles / text that appear on Cloudflare / Indeed bot-detection pages
_CHALLENGE_TITLE_PATTERNS = [
    re.compile(r"just a moment", re.I),
    re.compile(r"access denied", re.I),
    re.compile(r"please verify", re.I),
    re.compile(r"are you a human", re.I),
    re.compile(r"security check", re.I),
    re.compile(r"checking your browser", re.I),
    re.compile(r"attention required", re.I),
    re.compile(r"ray id", re.I),               # Cloudflare footer
    re.compile(r"cf-browser-verification", re.I),
]

_CHALLENGE_URL_PATTERNS = [
    "challenges.cloudflare.com",
    "/cdn-cgi/challenge-platform",
    "indeed.com/rc/",                          # Indeed's own re-captcha flow
    "indeedinteract.com",
]


def _is_challenge_page(driver) -> bool:
    """Return True if the current page looks like a bot-challenge page."""
    url = driver.current_url.lower()
    if any(p in url for p in _CHALLENGE_URL_PATTERNS):
        return True

    try:
        title = driver.title.lower()
        if any(p.search(title) for p in _CHALLENGE_TITLE_PATTERNS):
            return True
    except Exception:
        pass

    try:
        source = driver.page_source
        if "cf-turnstile" in source or "cf_chl_opt" in source:
            return True
        if "g-recaptcha" in source and "indeed" in url:
            return True
    except Exception:
        pass

    return False


# ── Alert helpers ──────────────────────────────────────────────────────

def _beep():
    """Cross-platform terminal beep / OS alert."""
    try:
        if sys.platform == "win32":
            import winsound
            for _ in range(3):
                winsound.Beep(1000, 400)
                time.sleep(0.2)
        else:
            # Linux / macOS — try paplay, aplay, or just bell chars
            if os.system("which paplay > /dev/null 2>&1") == 0:
                os.system("paplay /usr/share/sounds/freedesktop/stereo/bell.oga 2>/dev/null &")
            elif os.system("which aplay > /dev/null 2>&1") == 0:
                os.system("aplay /usr/share/sounds/alsa/Front_Left.wav 2>/dev/null &")
            else:
                print("\a\a\a", end="", flush=True)   # terminal bell
    except Exception:
        print("\a", end="", flush=True)


def _print_verification_banner(keyword: str, url: str):
    border = "=" * 65
    print(f"\n{border}")
    print("  ⚠   HUMAN VERIFICATION REQUIRED — Indeed / Cloudflare")
    print(border)
    print(f"  Keyword : {keyword}")
    print(f"  URL     : {url}")
    print()
    print("  → Switch to the browser window")
    print("  → Complete the CAPTCHA / checkbox / puzzle")
    print("  → The scraper will resume automatically once done")
    print(f"{border}\n")


# ── Verification wait loop ─────────────────────────────────────────────

VERIFICATION_POLL_INTERVAL = 3    # seconds between polls
VERIFICATION_TIMEOUT = 300        # give up after 5 minutes


def _wait_for_human(driver, keyword: str) -> bool:
    """
    Block until the challenge is solved (page changes away from challenge)
    or until VERIFICATION_TIMEOUT seconds pass.

    Returns True if verification succeeded, False if timed out.
    """
    _beep()
    _print_verification_banner(keyword, driver.current_url)

    deadline = time.time() + VERIFICATION_TIMEOUT
    dots = 0

    while time.time() < deadline:
        time.sleep(VERIFICATION_POLL_INTERVAL)
        try:
            if not _is_challenge_page(driver):
                print(f"\n  ✓ Verification passed! Resuming scrape for '{keyword}'...\n")
                time.sleep(2)   # let page finish loading
                return True
        except Exception:
            pass

        dots = (dots + 1) % 4
        remaining = int(deadline - time.time())
        print(f"  Waiting for verification{'.' * (dots + 1)}  ({remaining}s left)   \r",
              end="", flush=True)

    print(f"\n  ✗ Verification timed out for '{keyword}'. Skipping this keyword.")
    print("  ℹ  LinkedIn / Naukri / Foundit / Internshala are still running normally.\n")
    return False


# ── URL building ───────────────────────────────────────────────────────

def _build_search_url(keyword: str) -> str:
    q = keyword.replace(" ", "+")
    return f"https://in.indeed.com/jobs?q={q}&l=Bengaluru%2C+Karnataka&fromage=1"


# ── Card parsing ───────────────────────────────────────────────────────

def _parse_job_cards(soup: BeautifulSoup, keyword: str) -> list[dict]:
    jobs = []
    job_cards = soup.find_all("div", class_="job_seen_beacon")

    for card in job_cards:
        try:
            title_el = card.find("h2", class_=re.compile(r"jobTitle"))
            if not title_el:
                continue

            link_tag = title_el.find("a")
            if not link_tag:
                continue

            job_id = link_tag.get("data-jk")
            if not job_id:
                continue

            span = link_tag.find("span")
            title = span.get_text(strip=True) if span else link_tag.get_text(strip=True)

            href = link_tag.get("href", "")
            job_url = f"https://in.indeed.com{href}" if href.startswith("/") else href

            comp_el = card.find("span", attrs={"data-testid": "company-name"})
            company = comp_el.get_text(strip=True) if comp_el else "Unknown Company"

            loc_el = card.find("div", attrs={"data-testid": "text-location"})
            location = loc_el.get_text(strip=True) if loc_el else "Unknown Location"

            card_text = card.get_text(" ", strip=True)
            passes, reason = passes_filters(title, company, card_text, location)
            if not passes:
                print(f"    [SKIP] {reason}")
                continue

            jobs.append({
                "job_id": f"in_{job_id}",
                "title": title,
                "company": company,
                "location": location,
                "url": job_url,
                "keyword": keyword,
                "source": "Indeed",
            })
        except Exception as e:
            print(f"  [WARN] Indeed parse error: {e}")

    return jobs


# ── Keyword scraper with retry-on-challenge ────────────────────────────

MAX_CHALLENGE_RETRIES = 2   # how many times to retry a keyword after solving


def _scrape_keyword(driver, keyword: str) -> list[dict]:
    """Scrape one keyword, handling Cloudflare challenges with human pause."""
    url = _build_search_url(keyword)

    for attempt in range(1 + MAX_CHALLENGE_RETRIES):
        if attempt > 0:
            print(f"  [Indeed] Retrying '{keyword}' (attempt {attempt + 1})...")

        try:
            driver.get(url)
            time.sleep(2)

            # Check immediately for challenge
            if _is_challenge_page(driver):
                solved = _wait_for_human(driver, keyword)
                if not solved:
                    return []   # give up on this keyword
                # After solving, navigate to the target URL again
                if _is_challenge_page(driver):
                    # Still on challenge — try loading the url
                    driver.get(url)
                    time.sleep(3)

            # Scroll to load all cards
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)

            # Check again after scrolling (some challenges appear after interaction)
            if _is_challenge_page(driver):
                solved = _wait_for_human(driver, keyword)
                if not solved:
                    return []
                driver.get(url)
                time.sleep(3)
                for _ in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)

            soup = BeautifulSoup(driver.page_source, "lxml")
            jobs = _parse_job_cards(soup, keyword)
            return jobs

        except Exception as e:
            print(f"  [ERROR] Indeed '{keyword}': {e}")
            if attempt < MAX_CHALLENGE_RETRIES:
                time.sleep(3)

    return []


# ── Public entry point ─────────────────────────────────────────────────

def scrape_all_keywords(keywords: list[str], batch_size: int = 1) -> list[dict]:
    """
    Scrape Indeed for all keywords.

    Note: batch_size defaults to 1 here (single tab per request) because
    Indeed's bot-detection is much more sensitive to concurrent tab opens
    from the same browser session. Opening multiple tabs simultaneously
    increases the chance of triggering Cloudflare.
    """
    all_jobs: list[dict] = []
    driver = get_driver()

    # Indeed is sensitive — always do one keyword at a time
    for keyword in keywords:
        jobs = _scrape_keyword(driver, keyword)
        print(f"  [Indeed] {keyword}: {len(jobs)} job(s)")
        all_jobs.extend(jobs)
        # Small human-like delay between requests
        time.sleep(1.5)

    return all_jobs
