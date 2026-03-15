"""
LinkedIn scraper with multi-account rotation.

Each account gets its own isolated Chrome profile directory so cookies,
sessions, and browser state never mix between accounts.

Login flow (per account, per driver session):
  1. Set CHROME_PROFILE_SUFFIX so get_driver() opens the right profile
  2. Try restoring session from saved cookies
  3. If cookies expired/missing → fresh username+password login
  4. Save cookies on success

Rotation: AccountManager decides when to switch (every N keyword searches).
On rotation, the current Chrome session is closed and a new one opens with
the next account's profile.
"""

import json
import os
import re
import time

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from account_manager import AccountManager
from config import (
    ACCOUNT_COOLDOWN_HOURS,
    EXPERIENCE_LEVELS,
    LINKEDIN_ACCOUNTS,
    LOCATION,
    MAX_JOB_AGE_HOURS,
    MAX_ROTATION_DELAY,
    MIN_ROTATION_DELAY,
    TIME_FILTER,
)
from driver import get_driver, parse_age_hours, passes_filters, reset_driver, set_profile
from notifier import send_discord_alert

COOKIES_DIR = os.path.dirname(os.path.abspath(__file__))

_TIME_PATTERN = re.compile(
    r"(?:reposted\s+|posted\s+|active\s+)?"
    r"(?:\d+\s*(?:second|minute|hour|day|week|month|year)s?\s*(?:ago)?"
    r"|just\s+now|today|yesterday|moments?\s+ago"
    r"|\d+[smhdwy]\s*(?:ago)?)",
    re.I,
)

MAX_CONSECUTIVE_OLD = 3

# Single AccountManager instance for the process lifetime
_account_manager: AccountManager | None = None


def _get_account_manager() -> AccountManager:
    global _account_manager
    if _account_manager is None:
        if not LINKEDIN_ACCOUNTS:
            raise RuntimeError(
                "No LinkedIn accounts configured!\n"
                "Add accounts to LINKEDIN_ACCOUNTS in config.py."
            )
        os.environ.setdefault("ACCOUNT_COOLDOWN_HOURS", str(ACCOUNT_COOLDOWN_HOURS))
        os.environ.setdefault("MIN_ROTATION_DELAY", str(MIN_ROTATION_DELAY))
        os.environ.setdefault("MAX_ROTATION_DELAY", str(MAX_ROTATION_DELAY))
        _account_manager = AccountManager(LINKEDIN_ACCOUNTS)
    return _account_manager


# ── URL / session checks ───────────────────────────────────────────────

def _is_logged_in(url: str) -> bool:
    from urllib.parse import urlparse
    path = urlparse(url).path.rstrip("/")
    if any(x in path for x in ("login", "uas", "checkpoint", "challenge")):
        return False
    return path in ("/feed", "/mynetwork") or path.startswith("/jobs")


def _is_challenge(url: str) -> bool:
    return any(x in url for x in ("checkpoint", "challenge", "captcha"))


# ── Cookie helpers ─────────────────────────────────────────────────────

def _cookies_file(account_idx: int) -> str:
    return os.path.join(COOKIES_DIR, f"linkedin_cookies_{account_idx}.json")


def _save_cookies(driver, account_idx: int):
    try:
        cookies = driver.get_cookies()
        with open(_cookies_file(account_idx), "w") as f:
            json.dump(cookies, f)
        print(f"  Saved {len(cookies)} cookies for account {account_idx}")
    except Exception as e:
        print(f"  [WARN] Could not save cookies: {e}")


def _restore_cookies(driver, account_idx: int) -> bool:
    """Load saved cookies into an already-open browser. Returns True if session is valid."""
    path = _cookies_file(account_idx)
    if not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            cookies = json.load(f)

        # Must be on linkedin.com domain before adding cookies
        driver.get("https://www.linkedin.com")
        time.sleep(2)

        for cookie in cookies:
            cookie.pop("sameSite", None)
            cookie.pop("expiry", None)
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass

        driver.get("https://www.linkedin.com/feed/")
        time.sleep(4)

        if _is_logged_in(driver.current_url):
            print(f"  Cookie session restored for account {account_idx}")
            return True

        print(f"  Cookies expired for account {account_idx} (landed on {driver.current_url})")
        return False
    except Exception as e:
        print(f"  [WARN] Cookie restore failed for account {account_idx}: {e}")
        return False


# ── Login ──────────────────────────────────────────────────────────────

def _dismiss_welcome_back(driver, email: str, password: str) -> bool:
    """
    Handle the LinkedIn 'Welcome back / Continue as [account]' interstitial.

    LinkedIn sometimes shows this page instead of the normal login form when
    the browser profile already has a remembered session or the user has
    visited before. The page has a 'Continue as [Name]' button that skips
    the email field and sometimes the password field too.

    Returns True if the interstitial was detected and handled (successfully
    logged in), False if the page looked normal (caller should proceed with
    the standard form).
    """
    try:
        # Detect: page has no visible #username field OR has a "continue as" button
        continue_btn = None

        # Try multiple selectors LinkedIn has used for this button
        for selector in [
            "button.btn__primary--large[data-litms-control-urn]",
            "button[data-control-name='continue_as_member']",
            "a[data-control-name='continue_as_member']",
            ".join-form__form-body button[type='submit']",
        ]:
            try:
                continue_btn = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except Exception:
                pass

        # Also check by button text as a fallback
        if not continue_btn:
            try:
                buttons = driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    txt = btn.text.strip().lower()
                    if txt.startswith("continue as") or txt.startswith("sign in as"):
                        continue_btn = btn
                        break
            except Exception:
                pass

        if not continue_btn:
            return False  # Normal login page — let the standard flow handle it

        print("  Detected 'Welcome back / Continue as' screen — clicking to proceed ...")
        driver.execute_script("arguments[0].click();", continue_btn)
        time.sleep(3)

        # After clicking, LinkedIn may land on a password-only page or go straight to feed
        if _is_logged_in(driver.current_url):
            return True

        # Password step may appear
        try:
            pwd_field = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.ID, "password"))
            )
            pwd_field.clear()
            pwd_field.send_keys(password)
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            time.sleep(5)
        except Exception:
            pass  # No password step needed

        return True  # Caller will verify the final URL

    except Exception as e:
        print(f"  [WARN] Welcome-back handler error: {e}")
        return False


def _login_fresh(driver, account: dict, account_idx: int) -> bool:
    """Perform a fresh username+password login. Returns True on success."""
    email = account.get("email", "")
    password = account.get("password", "")
    name = account.get("name", f"Account {account_idx}")

    if not email or not password:
        print(f"  [WARN] No credentials for {name}. Cannot log in.")
        return False

    print(f"  Logging in fresh as {name} ({email}) ...")
    try:
        driver.get("https://www.linkedin.com/login")
        time.sleep(3)

        # Handle "Welcome back / Continue as [account]" interstitial first
        if _dismiss_welcome_back(driver, email, password):
            print(f"  Welcome-back flow completed for {name}")
            current = driver.current_url
            if _is_logged_in(current):
                print(f"  Login successful for {name}")
                _save_cookies(driver, account_idx)
                return True
            if _is_challenge(current):
                print(f"  LinkedIn challenge/verification required for {name}")
                print("  -> Complete the verification in the browser window.")
                print("  -> Waiting up to 120 seconds...")
                for _ in range(40):
                    time.sleep(3)
                    if _is_logged_in(driver.current_url):
                        print(f"  Verification passed for {name}")
                        _save_cookies(driver, account_idx)
                        return True
                print(f"  Verification timed out for {name}")
                _get_account_manager().mark_challenge()
                return False
            print(f"  Welcome-back flow did not complete login for {name} — URL: {current}")
            # Fall through to try the standard form in case the page changed

        # Standard username + password form
        try:
            email_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
        except Exception:
            # #username field not found — check if we somehow ended up logged in
            if _is_logged_in(driver.current_url):
                print(f"  Login successful for {name} (no form needed)")
                _save_cookies(driver, account_idx)
                return True
            print(f"  [WARN] Could not locate login form for {name} — URL: {driver.current_url}")
            return False

        email_field.clear()
        email_field.send_keys(email)

        pwd_field = driver.find_element(By.ID, "password")
        pwd_field.clear()
        pwd_field.send_keys(password)

        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(6)   # wait for redirect

        current = driver.current_url
        if _is_logged_in(current):
            print(f"  Login successful for {name}")
            _save_cookies(driver, account_idx)
            return True

        if _is_challenge(current):
            print(f"  LinkedIn challenge/verification required for {name}")
            print("  -> Complete the verification in the browser window.")
            print("  -> Waiting up to 120 seconds...")
            for _ in range(40):  # 40 x 3s = 120s
                time.sleep(3)
                if _is_logged_in(driver.current_url):
                    print(f"  Verification passed for {name}")
                    _save_cookies(driver, account_idx)
                    return True
            print(f"  Verification timed out for {name}")
            _get_account_manager().mark_challenge()
            return False

        print(f"  Login failed for {name} - unexpected URL: {current}")
        return False

    except Exception as e:
        print(f"  [ERROR] Login exception for {name}: {e}")
        return False


def _ensure_logged_in(account: dict, account_idx: int) -> tuple:
    """
    Make sure the browser for this account is open and logged in.
    Sets CHROME_PROFILE_SUFFIX BEFORE opening the driver so the correct
    profile is used from the start.
    Returns (driver, is_logged_in).
    """
    # CRITICAL: set profile suffix before get_driver() so the right
    # Chrome profile directory is used
    profile = f"li_{account_idx}"
    set_profile(profile)
    print(f"  Opening Chrome profile: chrome_profile_{profile}")

    driver = get_driver()

    # Check if this profile already has a live session
    try:
        current = driver.current_url
        if _is_logged_in(current):
            print(f"  Already logged in (profile: {profile})")
            return driver, True
    except Exception:
        pass

    # Try cookies first (fast path - no password needed)
    if _restore_cookies(driver, account_idx):
        return driver, True

    # Fall back to fresh login
    success = _login_fresh(driver, account, account_idx)
    return driver, success


# ── Account cycling ───────────────────────────────────────────────────

def _try_next_account(am) -> tuple:
    """
    Cycle through accounts until one logs in successfully.
    Returns (driver, account_name, logged_in).
    """
    for _ in range(len(LINKEDIN_ACCOUNTS)):
        account = am.current
        account_idx = am.current_idx

        if account is None:
            # All on cooldown — no point continuing the loop
            break

        account_name = account.get("name", f"Account {account_idx}")
        reset_driver()
        driver, logged_in = _ensure_logged_in(account, account_idx)

        if logged_in:
            return driver, account_name, True

        print(f"  [LinkedIn] Login FAILED for {account_name}")
        send_discord_alert(
            f"LinkedIn: Login failed for **{account_name}** — trying next account."
        )
        reset_driver()
        am.rotate()

    return None, "None", False


# ── URL building ───────────────────────────────────────────────────────

def _build_search_url(keyword: str) -> str:
    params = [
        f"keywords={keyword.replace(' ', '%20')}",
        f"location={LOCATION.replace(' ', '%20').replace(',', '%2C')}",
        f"f_TPR={TIME_FILTER}",
    ]
    if EXPERIENCE_LEVELS:
        params.append(f"f_E={'%2C'.join(EXPERIENCE_LEVELS)}")
    return f"https://www.linkedin.com/jobs/search/?{'&'.join(params)}"


# ── Card parsing ───────────────────────────────────────────────────────

def _get_text(card, selectors, default):
    for tag, cls in selectors:
        el = card.find(tag, class_=cls) if cls else card.find(tag)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)
    return default


def _extract_job_id(url: str) -> str | None:
    try:
        path = url.split("?")[0].rstrip("/")
        last = path.split("/")[-1]
        if last.isdigit():
            return last
        m = re.search(r"-(\d{5,})$", last)
        if m:
            return m.group(1)
        m = re.search(r"/view/(\d+)", url)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def _parse_job_cards(soup: BeautifulSoup, keyword: str) -> list[dict]:
    jobs = []
    job_cards = soup.find_all("li", class_=re.compile(r"jobs-search-results__list-item"))
    if not job_cards:
        job_cards = soup.find_all("div", class_=re.compile(r"job-card-container"))
    if not job_cards:
        job_cards = soup.find_all("div", class_="base-card")

    for card in job_cards:
        try:
            link_tag = (
                card.find("a", class_=re.compile(r"job-card-list__title"))
                or card.find("a", class_=re.compile(r"job-card-container__link"))
                or card.find("a", href=re.compile(r"/jobs/view/"))
                or card.find("a", class_="base-card__full-link")
            )
            if not link_tag:
                continue

            job_url = link_tag.get("href", "").strip()
            job_id = _extract_job_id(job_url)
            if not job_id:
                continue

            title = _get_text(card, [
                ("a", "job-card-list__title"),
                ("strong", None),
                ("h3", "base-search-card__title"),
                ("h3", None),
            ], None) or link_tag.get_text(strip=True) or "Unknown Title"

            company_div = card.find("div", class_=re.compile(r"artdeco-entity-lockup__subtitle"))
            if company_div:
                span = company_div.find("span")
                company = span.get_text(strip=True) if span else "Unknown Company"
            else:
                company = _get_text(card, [
                    ("span", "job-card-container__primary-description"),
                    ("h4", "base-search-card__subtitle"),
                ], "Unknown Company")

            caption_div = card.find("div", class_=re.compile(r"artdeco-entity-lockup__caption"))
            if caption_div:
                span = caption_div.find("span")
                location = span.get_text(strip=True) if span else "Unknown Location"
            else:
                location = _get_text(card, [
                    ("li", "job-card-container__metadata-item"),
                    ("span", "job-search-card__location"),
                ], "Unknown Location")

            card_time = None
            time_el = card.find("time")
            if time_el:
                card_time = time_el.get_text(strip=True) or time_el.get("datetime")

            passes, reason = passes_filters(title, company, card_text=None, location=location)
            if not passes:
                print(f"    [SKIP] {reason}")
                continue

            clean_url = job_url.split("?")[0]
            if not clean_url.startswith("http"):
                clean_url = f"https://www.linkedin.com{clean_url}"

            jobs.append({
                "job_id": f"li_{job_id}",
                "title": title,
                "company": company,
                "location": location,
                "url": clean_url,
                "keyword": keyword,
                "source": "LinkedIn",
                "_card_time": card_time,
            })
        except Exception as e:
            print(f"  [WARN] Card parse error: {e}")

    return jobs


# ── Time filtering ─────────────────────────────────────────────────────

def _get_time_from_detail_panel(driver) -> str | None:
    try:
        soup = BeautifulSoup(driver.page_source, "lxml")
        container = soup.find("div", class_=re.compile(r"tertiary-description"))
        candidates = container.find_all("span", class_=re.compile(r"tvm__text")) if container else []
        if not candidates:
            candidates = soup.find_all("span", class_=re.compile(r"tvm__text"))
        for span in candidates:
            text = span.get_text(strip=True)
            if _TIME_PATTERN.search(text):
                return text
    except Exception:
        pass
    return None


def _apply_time_filter(driver, jobs: list[dict], logged_in: bool, on_new_job=None) -> None:
    """
    Validate posting age for each job. Calls on_new_job(job) instantly for
    each job that passes. Returns nothing — notification happens in-place.

    Jobs are SKIPPED (not notified) when:
    - Posting age exceeds MAX_JOB_AGE_HOURS
    - No posting time could be determined (unknown age = skip)
    - Time text is present but unparseable
    """
    consecutive_skips = 0

    for job in jobs:
        card_time = job.pop("_card_time", None)
        time_text = card_time

        if not time_text and logged_in:
            try:
                job_id_num = job["job_id"].replace("li_", "")
                link = driver.find_element(
                    By.CSS_SELECTOR, f"a[href*='/jobs/view/{job_id_num}']"
                )
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", link)
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", link)
                time.sleep(1.5)

                if _is_challenge(driver.current_url):
                    print("  Challenge while browsing detail panel!")
                    _get_account_manager().mark_challenge()
                    break

                time_text = _get_time_from_detail_panel(driver)
            except Exception as e:
                print(f"    [WARN] Detail panel error for '{job['title']}': {e}")

        if time_text:
            # Reposted jobs are still active — always let them through
            is_reposted = "reposted" in time_text.lower()
            if is_reposted:
                print(f"    [REPOST] {job['title']} at {job['company']} — including reposted job")
                consecutive_skips = 0
            else:
                age = parse_age_hours(time_text.lower())
                if age is not None and age > MAX_JOB_AGE_HOURS:
                    print(f"    [SKIP] {job['title']} (posted {age}h ago) - too old")
                    consecutive_skips += 1
                    if consecutive_skips >= MAX_CONSECUTIVE_OLD:
                        print(f"    [STOP] {MAX_CONSECUTIVE_OLD} consecutive skips — stopping this keyword")
                        break
                    continue
                if age is None:
                    print(f"    [SKIP] Unrecognised time '{time_text}' for {job['title']} — skipping")
                    consecutive_skips += 1
                    if consecutive_skips >= MAX_CONSECUTIVE_OLD:
                        print(f"    [STOP] {MAX_CONSECUTIVE_OLD} consecutive skips — stopping this keyword")
                        break
                    continue
                # Age is valid and within limit — reset skip counter
                consecutive_skips = 0
        else:
            print(f"    [SKIP] No posting time for {job['title']} — skipping")
            consecutive_skips += 1
            if consecutive_skips >= MAX_CONSECUTIVE_OLD:
                print(f"    [STOP] {MAX_CONSECUTIVE_OLD} consecutive skips — stopping this keyword")
                break
            continue

        # ── Notify instantly (only jobs with confirmed recent age) ─────
        if on_new_job:
            on_new_job(job)


# ── Recommended collections ────────────────────────────────────────────

def _scrape_recommended(driver, logged_in: bool, on_new_job=None) -> None:
    if not logged_in:
        return
    for url in [
        "https://www.linkedin.com/jobs/collections/recommended/",
        "https://www.linkedin.com/jobs/collections/top-applicant/",
    ]:
        try:
            driver.get(url)
            time.sleep(3)
            if _is_challenge(driver.current_url):
                print("  Challenge on collections page!")
                _get_account_manager().mark_challenge()
                break
            for _ in range(5):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
            soup = BeautifulSoup(driver.page_source, "lxml")
            page_jobs = _parse_job_cards(soup, "Recommended")
            label = url.rstrip("/").split("/")[-1]
            print(f"  [{label}]: {len(page_jobs)} candidate(s)")
            _apply_time_filter(driver, page_jobs, logged_in, on_new_job)
        except Exception as e:
            print(f"  [ERROR] Collections: {e}")


# ── Public entrypoint ──────────────────────────────────────────────────

def linkedin_login(email: str, password: str):
    """Legacy shim - login is now handled automatically inside scrape_all_keywords."""
    pass


def scrape_all_keywords(keywords: list[str], batch_size: int = 1, on_new_job=None) -> None:
    """
    Scrape all keywords for ONE round, then rotate to the next account.

    Login is REQUIRED — if an account fails to log in, it notifies Discord
    and tries the next account. If ALL accounts fail, the round is skipped.
    """
    am = _get_account_manager()
    print(am.status())

    # ── Try to log in ──────────────────────────────────────────────────
    driver, account_name, logged_in = _try_next_account(am)

    if not logged_in:
        print("  [LinkedIn] No account could log in — skipping this round.")
        send_discord_alert(
            "LinkedIn: ALL accounts failed to log in — skipping this round.\n"
            "Check credentials or resolve challenges manually."
        )
        reset_driver()
        return

    print(f"  Active account: {account_name}")
    already_rotated = False

    # ── Scrape all keywords ────────────────────────────────────────────
    i = 0
    while i < len(keywords):
        batch = keywords[i:i + batch_size]

        for j, keyword in enumerate(batch):
            url = _build_search_url(keyword)
            if j == 0:
                driver.get(url)
            else:
                driver.switch_to.new_window("tab")
                driver.get(url)
            time.sleep(1)

        time.sleep(2)

        challenge_triggered = False
        for j, keyword in enumerate(batch):
            try:
                driver.switch_to.window(driver.window_handles[j])

                if _is_challenge(driver.current_url):
                    print(f"  ⚠ Challenge on '{keyword}'!")
                    am.mark_challenge()
                    send_discord_alert(
                        f"LinkedIn: Challenge/CAPTCHA hit on **{account_name}** "
                        f"while scraping '{keyword}' — switching to next account."
                    )
                    challenge_triggered = True
                    break

                for _ in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)

                soup = BeautifulSoup(driver.page_source, "lxml")
                jobs = _parse_job_cards(soup, keyword)
                print(f"  [{account_name}] {keyword}: {len(jobs)} candidate(s)")
                _apply_time_filter(driver, jobs, logged_in, on_new_job)

            except Exception as e:
                print(f"  [ERROR] keyword='{keyword}': {e}")

        # Close extra tabs
        while len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            driver.close()
        if driver.window_handles:
            driver.switch_to.window(driver.window_handles[0])

        if challenge_triggered:
            reset_driver()
            am.rotate()
            driver, account_name, logged_in = _try_next_account(am)
            already_rotated = True

            if not logged_in:
                print("  [LinkedIn] No more accounts available — stopping remaining keywords.")
                send_discord_alert(
                    "LinkedIn: All accounts exhausted mid-round — "
                    "remaining keywords skipped."
                )
                break

            print(f"  Switched to: {account_name}")

        i += batch_size

    # ── Recommended collections ───────────────────────────────────────
    if logged_in:
        print("  --- Recommended collections ---")
        _scrape_recommended(driver, logged_in, on_new_job)

    # ── Rotate to next account for the next round ──────────────────────
    am.record_used()
    reset_driver()
    if not already_rotated:
        am.rotate()
    print(am.status())
