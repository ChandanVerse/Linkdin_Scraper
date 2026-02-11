import time

from bs4 import BeautifulSoup

from driver import get_driver, passes_filters


def _build_search_url(keyword):
    slug = keyword.lower().replace(" ", "-")
    return f"https://www.naukri.com/{slug}-jobs-in-bengaluru?experience=0&jobAge=1"


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
            passes, reason = passes_filters(title, company, card_text, location)
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


def scrape_all_keywords(keywords, batch_size=2):
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
