import re
import time

import requests
from bs4 import BeautifulSoup

from config import EXPERIENCE_LEVELS, LOCATION, TIME_FILTER, get_random_user_agent

# LinkedIn guest jobs API endpoint (returns HTML fragments, supports all filters)
GUEST_API_URL = "https://www.linkedin.com/jobs-guest/jobs/api/sideBarJobCount"
GUEST_JOBS_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPostings/jobs"

# Skip jobs with these words in the title (experienced roles)
SENIOR_KEYWORDS = [
    "senior", "sr.", "sr ", "lead", "principal", "staff", "manager",
    "director", "head of", "vp ", "vice president", "architect",
    "10+", "8+", "7+", "6+", "5+",
]


def scrape_jobs(keyword):
    """Scrape LinkedIn guest jobs API for a given keyword.

    Returns a list of dicts with keys: job_id, title, company, location, url, keyword
    """
    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    # Build URL with experience level filter passed as separate params
    params = {
        "keywords": keyword,
        "location": LOCATION,
        "f_TPR": TIME_FILTER,
    }
    # f_E needs to be passed as comma-separated values
    if EXPERIENCE_LEVELS:
        params["f_E"] = ",".join(EXPERIENCE_LEVELS)

    # Try guest API first, fall back to public search page
    for base_url in [GUEST_JOBS_URL, "https://www.linkedin.com/jobs/search/"]:
        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"  [ERROR] Failed to fetch from {base_url}: {e}")
            continue

        soup = BeautifulSoup(response.text, "lxml")
        jobs = parse_job_cards(soup, keyword)
        if jobs:
            return jobs

    return []


def parse_job_cards(soup, keyword):
    """Parse job cards from LinkedIn HTML response."""
    jobs = []

    # Try multiple selectors for different page formats
    job_cards = soup.find_all("div", class_="base-card")
    if not job_cards:
        job_cards = soup.find_all("li")

    for card in job_cards:
        try:
            # Extract job URL and ID
            link_tag = card.find("a", class_="base-card__full-link")
            if not link_tag:
                link_tag = card.find("a", href=re.compile(r"/jobs/view/"))
            if not link_tag:
                continue

            job_url = link_tag.get("href", "").strip()
            job_id = extract_job_id(job_url)
            if not job_id:
                continue

            # Extract title
            title_tag = card.find("h3", class_="base-search-card__title")
            if not title_tag:
                title_tag = card.find("h3")
            title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"

            # Extract company
            company_tag = card.find("h4", class_="base-search-card__subtitle")
            if not company_tag:
                company_tag = card.find("h4")
            company = company_tag.get_text(strip=True) if company_tag else "Unknown Company"

            # Extract location
            location_tag = card.find("span", class_="job-search-card__location")
            if not location_tag:
                location_tag = card.find("span", class_="job-result-card__location")
            location = location_tag.get_text(strip=True) if location_tag else "Unknown Location"

            # Skip senior/experienced roles based on title
            title_lower = title.lower()
            if any(kw in title_lower for kw in SENIOR_KEYWORDS):
                continue

            # Clean job URL (remove tracking params)
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
    """Extract the numeric job ID from a LinkedIn job URL.

    URLs can be:
      .../jobs/view/1234567890
      .../jobs/view/python-developer-at-company-1234567890?...
    """
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
