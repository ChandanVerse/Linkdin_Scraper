import re
import time

import requests
from bs4 import BeautifulSoup

from config import EXPERIENCE_LEVELS, LOCATION, TIME_FILTER, get_random_user_agent

# Skip jobs with these words in the title (experienced/senior roles)
EXCLUDE_TITLE_KEYWORDS = [
    "senior", "sr.", "sr ", "lead", "principal", "staff", "manager",
    "director", "head of", "vp ", "vice president", "architect",
    "10+", "8+", "7+", "6+", "5+", "4+",
    "14+", "12+", "11+", "9+",
    "years", "yrs",
    "l4", "l5", "l6", "l7",
    "sde 3", "sde3", "sde-3", "sde iii", "sde-iii",
    "associate 2", "associate 3",
    "technologist",
]

# Only notify jobs that match at least one of these (fresher-friendly titles)
INCLUDE_TITLE_KEYWORDS = [
    "intern", "fresher", "junior", "jr.", "jr ",
    "entry level", "entry-level", "trainee", "graduate",
    "associate", "analyst",
    "sde 1", "sde1", "sde-1", "sde i", "sde-i",
    "l1", "l2", "l3",
    "python", "data scientist", "data science", "data engineer",
    "ml engineer", "machine learning", "ai engineer", "ai/ml",
    "developer", "software engineer",
]


def scrape_jobs(keyword):
    """Scrape LinkedIn public job search page for a given keyword.

    Returns a list of dicts with keys: job_id, title, company, location, url, keyword
    """
    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    params = {
        "keywords": keyword,
        "location": LOCATION,
        "f_TPR": TIME_FILTER,
        "f_E": ",".join(EXPERIENCE_LEVELS),
    }

    # Try guest API first, fall back to public search page
    urls = [
        "https://www.linkedin.com/jobs-guest/jobs/api/sideBarJobCount",
        "https://www.linkedin.com/jobs/search/",
    ]
    for base_url in urls:
        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"  [WARN] {base_url} failed: {e}")
            continue

        soup = BeautifulSoup(response.text, "lxml")
        jobs = parse_job_cards(soup, keyword)
        if jobs:
            return jobs

    return []


def parse_job_cards(soup, keyword):
    """Parse job cards from LinkedIn HTML response."""
    jobs = []
    job_cards = soup.find_all("div", class_="base-card")

    for card in job_cards:
        try:
            link_tag = card.find("a", class_="base-card__full-link")
            if not link_tag:
                continue

            job_url = link_tag.get("href", "").strip()
            job_id = extract_job_id(job_url)
            if not job_id:
                continue

            title_tag = card.find("h3", class_="base-search-card__title")
            title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"

            company_tag = card.find("h4", class_="base-search-card__subtitle")
            company = company_tag.get_text(strip=True) if company_tag else "Unknown Company"

            location_tag = card.find("span", class_="job-search-card__location")
            location = location_tag.get_text(strip=True) if location_tag else "Unknown Location"

            title_lower = title.lower()

            # EXCLUDE: skip senior/experienced roles
            if any(kw in title_lower for kw in EXCLUDE_TITLE_KEYWORDS):
                print(f"    [SKIP] {title} (matched exclude filter)")
                continue

            # INCLUDE: only keep fresher-friendly titles
            if not any(kw in title_lower for kw in INCLUDE_TITLE_KEYWORDS):
                print(f"    [SKIP] {title} (no fresher keyword match)")
                continue

            clean_url = job_url.split("?")[0] if "?" in job_url else job_url

            jobs.append({
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "url": clean_url,
                "keyword": keyword,
            })

        except Exception as e:
            print(f"  [WARN] Failed to parse a job card: {e}")
            continue

    return jobs


def extract_job_id(url):
    """Extract the numeric job ID from a LinkedIn job URL."""
    try:
        path = url.split("?")[0].rstrip("/")
        last_segment = path.split("/")[-1]
        if last_segment.isdigit():
            return last_segment
        match = re.search(r"-(\d{5,})$", last_segment)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def scrape_all_keywords(keywords):
    """Scrape jobs for all keywords with a small delay between requests."""
    all_jobs = []
    for keyword in keywords:
        print(f"  Scraping jobs for: {keyword}")
        jobs = scrape_jobs(keyword)
        print(f"    Found {len(jobs)} job(s)")
        all_jobs.extend(jobs)
        time.sleep(2)
    return all_jobs
