import re
import time

from bs4 import BeautifulSoup

from driver import get_driver, passes_filters


def _build_search_url(keyword):
    q = keyword.replace(" ", "+")
    return f"https://in.indeed.com/jobs?q={q}&l=Bengaluru%2C+Karnataka&fromage=1"



def _parse_job_cards(soup, keyword):
    jobs = []

    # Indeed: <div class="job_seen_beacon">
    job_cards = soup.find_all("div", class_="job_seen_beacon")

    for card in job_cards:
        try:
            # Title: <h2 class="jobTitle"> > <a data-jk="...">
            title_el = card.find("h2", class_=re.compile(r"jobTitle"))
            if not title_el:
                continue

            link_tag = title_el.find("a")
            if not link_tag:
                continue

            job_id = link_tag.get("data-jk")
            if not job_id:
                continue

            title = link_tag.find("span").get_text(strip=True) if link_tag.find("span") else link_tag.get_text(strip=True)

            # URL
            href = link_tag.get("href", "")
            job_url = f"https://in.indeed.com{href}" if href.startswith("/") else href

            # Company: <span data-testid="company-name">
            comp_el = card.find("span", attrs={"data-testid": "company-name"})
            company = comp_el.get_text(strip=True) if comp_el else "Unknown Company"

            # Location: <div data-testid="text-location">
            loc_el = card.find("div", attrs={"data-testid": "text-location"})
            location = loc_el.get_text(strip=True) if loc_el else "Unknown Location"

            # Filters
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
