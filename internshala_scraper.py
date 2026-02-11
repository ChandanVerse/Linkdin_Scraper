import re
import time

from bs4 import BeautifulSoup

from driver import get_driver, passes_filters


def _build_search_url(keyword):
    slug = keyword.lower().replace(" ", "-")
    return f"https://internshala.com/internships/{slug}-internship-in-bangalore/"


def _parse_job_cards(soup, keyword):
    jobs = []

    job_cards = soup.select(".individual_internship")
    if not job_cards:
        job_cards = soup.select(".internship_meta")
    if not job_cards:
        job_cards = soup.select("[data-internship_id]")

    if not job_cards:
        return jobs

    for card in job_cards:
        try:
            # Job ID from data attribute or link
            job_id = card.get("data-internship_id") or card.get("internshipid")
            if not job_id:
                link = card.find("a", href=re.compile(r"/internship/detail/"))
                if link:
                    m = re.search(r"(\d+)/?$", link.get("href", ""))
                    job_id = m.group(1) if m else None
            if not job_id:
                continue

            # Title
            title_el = card.select_one(".profile a, h3.job-internship-name a, .heading_4_5 a")
            if not title_el:
                title_el = card.find("a", href=re.compile(r"/internship/detail/"))
            title = title_el.get_text(strip=True) if title_el else "Unknown Title"
            job_url = title_el.get("href", "") if title_el else ""

            # Company
            comp_el = card.select_one(".company_name a, .link_display_like_text, p.company-name")
            if not comp_el:
                comp_el = card.select_one(".company_name")
            company = comp_el.get_text(strip=True) if comp_el else "Unknown Company"

            # Location
            loc_el = card.select_one("#location_names a, .locations a, .location_link")
            if not loc_el:
                loc_el = card.select_one("#location_names, .locations")
            location = loc_el.get_text(strip=True) if loc_el else "Bangalore"

            # Posted time
            time_el = card.select_one(".status-success span, .status span, .posting-time")
            card_text = time_el.get_text(strip=True) if time_el else ""
            # Internshala uses "X days ago", "Today", "Just now", etc.
            if card_text.lower() in ("today", "just now"):
                card_text = "0 hours ago"

            # Filters
            passes, reason = passes_filters(title, company, card_text, location)
            if not passes:
                print(f"    [SKIP] {reason}")
                continue

            if job_url and not job_url.startswith("http"):
                job_url = f"https://internshala.com{job_url}"

            jobs.append({
                "job_id": f"is_{job_id}",
                "title": title,
                "company": company,
                "location": location,
                "url": job_url,
                "keyword": keyword,
                "source": "Internshala",
            })
        except Exception as e:
            print(f"  [WARN] Internshala parse error: {e}")

    return jobs


def scrape_all_keywords(keywords, batch_size=4):
    all_jobs = []
    driver = get_driver()

    for i in range(0, len(keywords), batch_size):
        batch = keywords[i:i + batch_size]

        for j, keyword in enumerate(batch):
            url = _build_search_url(keyword)
            if j == 0:
                driver.get(url)
            else:
                driver.switch_to.new_window('tab')
                driver.get(url)

        time.sleep(2)

        for j, keyword in enumerate(batch):
            try:
                driver.switch_to.window(driver.window_handles[j])
                for _ in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)

                soup = BeautifulSoup(driver.page_source, "lxml")
                jobs = _parse_job_cards(soup, keyword)
                print(f"  {keyword}: {len(jobs)} job(s)")
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"  [ERROR] '{keyword}': {e}")

        while len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            driver.close()
        driver.switch_to.window(driver.window_handles[0])

    return all_jobs
