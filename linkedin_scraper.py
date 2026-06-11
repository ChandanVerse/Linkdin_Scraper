"""
LinkedIn scraper — guest-mode, headless.

Searches LinkedIn's public job listings without login.
Filters (f_TPR, f_E) work on guest/public URLs.
"""

import random
import re
import time

from bs4 import BeautifulSoup

from config import (
    EXPERIENCE_LEVELS,
    LOCATION,
    MAX_JOB_AGE_HOURS,
    SEARCH_DELAY_MAX,
    SEARCH_DELAY_MIN,
    STARTUP_MAX_JOB_AGE_HOURS,
    STARTUP_TIME_FILTER,
    TIME_FILTER,
)
from driver import enforce_tab_limit, get_driver, parse_age_hours, passes_filters, reset_driver

MAX_CONSECUTIVE_OLD = 3


# ── URL building ───────────────────────────────────────────────────────

def _build_search_url(keyword: str, time_filter: str | None = None) -> str:
    tpr = time_filter or TIME_FILTER
    params = [
        f"keywords={keyword.replace(' ', '%20')}",
        f"location={LOCATION.replace(' ', '%20').replace(',', '%2C')}",
        f"f_TPR={tpr}",
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
    # Try multiple card selectors (logged-in and guest HTML variants)
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

def _apply_time_filter(jobs: list[dict], on_new_job=None,
                       max_age_hours: float | None = None) -> None:
    """
    Validate posting age for each job using card-level time text.
    Calls on_new_job(job) instantly for each job that passes.
    """
    age_limit = max_age_hours if max_age_hours is not None else MAX_JOB_AGE_HOURS
    consecutive_skips = 0

    for job in jobs:
        card_time = job.pop("_card_time", None)

        if card_time:
            is_reposted = "reposted" in card_time.lower()
            if is_reposted:
                print(f"    [REPOST] {job['title']} at {job['company']} — including reposted job")
                consecutive_skips = 0
            else:
                age = parse_age_hours(card_time.lower())
                if age is not None and age > age_limit:
                    print(f"    [SKIP] {job['title']} (posted {age}h ago) - too old")
                    consecutive_skips += 1
                    if consecutive_skips >= MAX_CONSECUTIVE_OLD:
                        print(f"    [STOP] {MAX_CONSECUTIVE_OLD} consecutive skips — stopping this keyword")
                        break
                    continue
                if age is None:
                    print(f"    [SKIP] Unrecognised time '{card_time}' for {job['title']} — skipping")
                    consecutive_skips += 1
                    if consecutive_skips >= MAX_CONSECUTIVE_OLD:
                        print(f"    [STOP] {MAX_CONSECUTIVE_OLD} consecutive skips — stopping this keyword")
                        break
                    continue
                consecutive_skips = 0
        else:
            print(f"    [SKIP] No posting time for {job['title']} — skipping")
            consecutive_skips += 1
            if consecutive_skips >= MAX_CONSECUTIVE_OLD:
                print(f"    [STOP] {MAX_CONSECUTIVE_OLD} consecutive skips — stopping this keyword")
                break
            continue

        # Notify instantly for jobs with confirmed recent age
        if on_new_job:
            on_new_job(job)


# ── Scroll helper ──────────────────────────────────────────────────────

def _scroll_page(driver, scrolls: int = 3):
    """Scroll the page to load lazy-loaded job cards."""
    for _ in range(scrolls):
        scroll_px = random.randint(300, 600)
        driver.execute_script(f"window.scrollBy(0, {scroll_px});")
        time.sleep(random.uniform(0.8, 2.0))


# ── Public entrypoints ─────────────────────────────────────────────────

def scrape_all_keywords(keywords: list[str], on_new_job=None) -> None:
    """Single pass through all keywords as a guest user."""
    driver = get_driver()

    for idx, keyword in enumerate(keywords):
        url = _build_search_url(keyword)
        driver.get(url)
        time.sleep(random.uniform(3, 6))

        _scroll_page(driver, scrolls=random.randint(3, 5))

        soup = BeautifulSoup(driver.page_source, "lxml")
        jobs = _parse_job_cards(soup, keyword)
        print(f"  {keyword}: {len(jobs)} candidate(s)")
        _apply_time_filter(jobs, on_new_job)

        enforce_tab_limit(2)

        if idx < len(keywords) - 1:
            time.sleep(random.uniform(SEARCH_DELAY_MIN, SEARCH_DELAY_MAX))

    reset_driver()


def startup_sweep(keywords: list[str], on_new_job=None) -> None:
    """
    One-time 24-hour sweep on startup: search each keyword once with
    STARTUP_TIME_FILTER (r86400) and STARTUP_MAX_JOB_AGE_HOURS (24h).
    """
    print("\n  === STARTUP SWEEP (24h catch-up) ===")
    driver = get_driver()

    for idx, keyword in enumerate(keywords):
        url = _build_search_url(keyword, time_filter=STARTUP_TIME_FILTER)
        driver.get(url)
        time.sleep(random.uniform(3, 6))

        _scroll_page(driver, scrolls=random.randint(3, 5))

        soup = BeautifulSoup(driver.page_source, "lxml")
        jobs = _parse_job_cards(soup, keyword)
        print(f"  {keyword}: {len(jobs)} candidate(s) (24h)")
        _apply_time_filter(jobs, on_new_job, max_age_hours=STARTUP_MAX_JOB_AGE_HOURS)

        enforce_tab_limit(2)

        if idx < len(keywords) - 1:
            time.sleep(random.uniform(SEARCH_DELAY_MIN, SEARCH_DELAY_MAX))

    reset_driver()
    print("  === STARTUP SWEEP COMPLETE ===\n")
