"""
Internshala scraper — searches BOTH the Jobs section and Internships section.

Jobs URL:        https://internshala.com/jobs/{keyword}-jobs-in-bangalore/
Internships URL: https://internshala.com/internships/{keyword}-internship-in-bangalore/

The two sections have different HTML structures so each has its own parser.
Results are deduplicated by job_id before notifying.
"""

import re
import time

from bs4 import BeautifulSoup

from driver import get_driver, passes_filters


# ── URL builders ───────────────────────────────────────────────────────

def _jobs_url(keyword: str) -> str:
    slug = keyword.lower().replace(" ", "-")
    return f"https://internshala.com/jobs/{slug}-jobs-in-bangalore/"


def _internships_url(keyword: str) -> str:
    slug = keyword.lower().replace(" ", "-")
    return f"https://internshala.com/internships/{slug}-internship-in-bangalore/"


# ── Jobs section parser ────────────────────────────────────────────────

def _parse_jobs_cards(soup: BeautifulSoup, keyword: str) -> list[dict]:
    """Parse the /jobs/ section — different HTML from /internships/."""
    jobs = []

    # Job cards in the jobs section
    cards = soup.select(".individual_internship")   # same outer class, different internals
    if not cards:
        cards = soup.select("[data-internship_id]")
    if not cards:
        cards = soup.select(".job-internship-card, .internship-card")

    for card in cards:
        try:
            # ID
            job_id = card.get("data-internship_id") or card.get("internshipid")
            if not job_id:
                link = card.find("a", href=re.compile(r"/job-detail/|/jobs/detail/"))
                if link:
                    m = re.search(r"(\d+)/?$", link.get("href", ""))
                    job_id = m.group(1) if m else None
            if not job_id:
                continue

            # Title — jobs section uses .profile or .job-title-name
            title_el = (
                card.select_one(".profile a")
                or card.select_one(".job-title-name a")
                or card.select_one("h3 a")
                or card.find("a", href=re.compile(r"/job-detail/|/jobs/detail/"))
            )
            title = title_el.get_text(strip=True) if title_el else "Unknown Title"
            job_url = title_el.get("href", "") if title_el else ""

            # Company
            comp_el = (
                card.select_one(".company_name a")
                or card.select_one(".company-name a")
                or card.select_one(".link_display_like_text")
                or card.select_one(".company_name")
            )
            company = comp_el.get_text(strip=True) if comp_el else "Unknown Company"

            # Location
            loc_el = (
                card.select_one("#location_names a")
                or card.select_one(".locations a")
                or card.select_one(".location_link")
                or card.select_one(".locations")
            )
            location = loc_el.get_text(strip=True) if loc_el else "Bangalore"

            # Posted time
            time_el = card.select_one(".status-success span, .status span, .posting-time, .job-duration-label")
            card_text = time_el.get_text(strip=True) if time_el else ""

            passes, reason = passes_filters(title, company, card_text, location)
            if not passes:
                print(f"    [SKIP] {reason}")
                continue

            if job_url and not job_url.startswith("http"):
                job_url = f"https://internshala.com{job_url}"

            jobs.append({
                "job_id": f"isj_{job_id}",   # isj = internshala job
                "title": title,
                "company": company,
                "location": location,
                "url": job_url,
                "keyword": keyword,
                "source": "Internshala",
            })
        except Exception as e:
            print(f"  [WARN] Internshala jobs parse error: {e}")

    return jobs


# ── Internships section parser ─────────────────────────────────────────

def _parse_internship_cards(soup: BeautifulSoup, keyword: str) -> list[dict]:
    """Parse the /internships/ section."""
    jobs = []

    cards = soup.select(".individual_internship")
    if not cards:
        cards = soup.select(".internship_meta")
    if not cards:
        cards = soup.select("[data-internship_id]")

    for card in cards:
        try:
            job_id = card.get("data-internship_id") or card.get("internshipid")
            if not job_id:
                link = card.find("a", href=re.compile(r"/internship/detail/"))
                if link:
                    m = re.search(r"(\d+)/?$", link.get("href", ""))
                    job_id = m.group(1) if m else None
            if not job_id:
                continue

            title_el = card.select_one(".profile a, h3.job-internship-name a, .heading_4_5 a")
            if not title_el:
                title_el = card.find("a", href=re.compile(r"/internship/detail/"))
            title = title_el.get_text(strip=True) if title_el else "Unknown Title"
            job_url = title_el.get("href", "") if title_el else ""

            comp_el = card.select_one(".company_name a, .link_display_like_text, p.company-name")
            if not comp_el:
                comp_el = card.select_one(".company_name")
            company = comp_el.get_text(strip=True) if comp_el else "Unknown Company"

            loc_el = card.select_one("#location_names a, .locations a, .location_link")
            if not loc_el:
                loc_el = card.select_one("#location_names, .locations")
            location = loc_el.get_text(strip=True) if loc_el else "Bangalore"

            time_el = card.select_one(".status-success span, .status span, .posting-time")
            card_text = time_el.get_text(strip=True) if time_el else ""

            passes, reason = passes_filters(title, company, card_text, location)
            if not passes:
                print(f"    [SKIP] {reason}")
                continue

            if job_url and not job_url.startswith("http"):
                job_url = f"https://internshala.com{job_url}"

            jobs.append({
                "job_id": f"isi_{job_id}",   # isi = internshala internship
                "title": title,
                "company": company,
                "location": location,
                "url": job_url,
                "keyword": keyword,
                "source": "Internshala",
            })
        except Exception as e:
            print(f"  [WARN] Internshala internship parse error: {e}")

    return jobs


# ── Main scraper ───────────────────────────────────────────────────────

def scrape_all_keywords(keywords: list, batch_size: int = 2, on_new_job=None) -> list:
    """
    For each keyword, scrape both:
      1. /jobs/   section (full-time jobs)
      2. /internships/ section (internships)

    Opens two tabs per keyword (one for jobs, one for internships),
    deduplicates by job_id, then notifies via on_new_job callback.
    """
    all_jobs = []
    seen_ids: set = set()
    driver = get_driver()

    for keyword in keywords:
        jobs_url = _jobs_url(keyword)
        interns_url = _internships_url(keyword)

        try:
            # Tab 0: jobs section
            driver.get(jobs_url)
            # Tab 1: internships section
            driver.switch_to.new_window("tab")
            driver.get(interns_url)
            time.sleep(2)

            keyword_jobs = []

            # Parse jobs tab
            driver.switch_to.window(driver.window_handles[0])
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)
            soup = BeautifulSoup(driver.page_source, "lxml")
            found_jobs = _parse_jobs_cards(soup, keyword)
            keyword_jobs.extend(found_jobs)

            # Parse internships tab
            driver.switch_to.window(driver.window_handles[1])
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)
            soup = BeautifulSoup(driver.page_source, "lxml")
            found_interns = _parse_internship_cards(soup, keyword)
            keyword_jobs.extend(found_interns)

            # Close internship tab, keep jobs tab as base
            driver.switch_to.window(driver.window_handles[1])
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

            # Dedup and notify
            new_count = 0
            for job in keyword_jobs:
                if job["job_id"] in seen_ids:
                    continue
                seen_ids.add(job["job_id"])
                new_count += 1
                if on_new_job:
                    on_new_job(job)
                else:
                    all_jobs.append(job)

            print(f"  [Internshala] {keyword}: "
                  f"{len(found_jobs)} job(s) + {len(found_interns)} internship(s) "
                  f"= {new_count} new")

        except Exception as e:
            print(f"  [ERROR] Internshala '{keyword}': {e}")
            # Clean up any extra tabs
            while len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])
                driver.close()
            if driver.window_handles:
                driver.switch_to.window(driver.window_handles[0])

    return all_jobs  # empty when on_new_job is used