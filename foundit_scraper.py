import re
import time

from bs4 import BeautifulSoup

from driver import get_driver, passes_filters


def _build_search_url(keyword):
    q = keyword.replace(" ", "%20")
    return f"https://www.foundit.in/srp/results?sort=1&limit=25&query={q}&locations=Bengaluru&experienceRanges=0~2&postAge=1"



def _parse_job_cards(soup, keyword):
    jobs = []

    # Foundit: <div class="srpResultCardContainer"> > <div class="cardContainer" id="JOB_ID">
    job_cards = soup.find_all("div", class_="srpResultCardContainer")

    for card in job_cards:
        try:
            # Job ID from cardContainer id attribute
            container = card.find("div", class_="cardContainer")
            if not container:
                continue
            job_id = container.get("id")
            if not job_id:
                continue

            # Title: <div class="jobTitle">
            title_el = card.find("div", class_="jobTitle")
            title = title_el.get_text(strip=True) if title_el else "Unknown Title"

            # Company: <div class="companyName"> > <p>
            comp_el = card.find("div", class_="companyName")
            if comp_el:
                p = comp_el.find("p")
                company = p.get_text(strip=True) if p else comp_el.get_text(strip=True)
            else:
                company = "Unknown Company"

            # Location: <div class="details location">
            loc_el = card.find("div", class_=re.compile(r"location"))
            location = loc_el.get_text(strip=True) if loc_el else "Unknown Location"

            # Posted time: <p class="timeText">
            time_el = card.find("p", class_="timeText")
            card_text = time_el.get_text(strip=True) if time_el else ""

            # Filters
            passes, reason = passes_filters(title, company, card_text, location)
            if not passes:
                print(f"    [SKIP] {reason}")
                continue

            job_url = f"https://www.foundit.in/job/{job_id}"

            jobs.append({
                "job_id": f"fi_{job_id}",
                "title": title,
                "company": company,
                "location": location,
                "url": job_url,
                "keyword": keyword,
                "source": "Foundit",
            })
        except Exception as e:
            print(f"  [WARN] Foundit parse error: {e}")

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
