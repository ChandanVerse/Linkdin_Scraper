import re
import time

from bs4 import BeautifulSoup

from driver import get_driver, passes_filters


def _build_search_url(keyword):
    slug = keyword.lower().replace(" ", "-")
    return f"https://www.naukri.com/{slug}-jobs-in-bengaluru?experience=0&jobAge=1"


def _scrape_jobs(keyword):
    driver = get_driver()
    url = _build_search_url(keyword)

    try:
        driver.get(url)
        time.sleep(4)

        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        soup = BeautifulSoup(driver.page_source, "lxml")
        return _parse_job_cards(soup, keyword)
    except Exception as e:
        print(f"  [ERROR] Naukri failed for '{keyword}': {e}")
        return []


def _parse_job_cards(soup, keyword):
    jobs = []

    # Naukri: <div class="srp-jobtuple-wrapper" data-job-id="...">
    job_cards = soup.find_all("div", class_="srp-jobtuple-wrapper")
    if not job_cards:
        job_cards = soup.find_all(attrs={"data-job-id": True})

    for card in job_cards:
        try:
            job_id = card.get("data-job-id")
            if not job_id:
                continue

            # Title: <a class="title">
            title_el = card.find("a", class_="title")
            title = title_el.get_text(strip=True) if title_el else "Unknown Title"
            job_url = title_el.get("href", "") if title_el else ""

            # Company: <a class="comp-name">
            comp_el = card.find("a", class_="comp-name")
            company = comp_el.get_text(strip=True) if comp_el else "Unknown Company"

            # Location: <span class="locWdth">
            loc_el = card.find("span", class_="locWdth")
            location = loc_el.get_text(strip=True) if loc_el else "Unknown Location"

            # Posted time: <span class="job-post-day">
            time_el = card.find("span", class_="job-post-day")
            card_text = time_el.get_text(strip=True) if time_el else ""

            # Filters
            passes, reason = passes_filters(title, company, card_text)
            if not passes:
                print(f"    [SKIP] {reason}")
                continue

            if not job_url.startswith("http"):
                job_url = f"https://www.naukri.com{job_url}"

            jobs.append({
                "job_id": f"nk_{job_id}",
                "title": title,
                "company": company,
                "location": location,
                "url": job_url,
                "keyword": keyword,
                "source": "Naukri",
            })
        except Exception as e:
            print(f"  [WARN] Naukri parse error: {e}")

    return jobs


def scrape_all_keywords(keywords):
    all_jobs = []
    for keyword in keywords:
        print(f"  Scraping: {keyword}")
        jobs = _scrape_jobs(keyword)
        print(f"    Found {len(jobs)} job(s)")
        all_jobs.extend(jobs)
        time.sleep(2)
    return all_jobs
