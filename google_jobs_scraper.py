"""
Google Jobs scraper — scrapes the Google Jobs panel (google.com/search?...&ibp=htl;jobs).

Uses Selenium to interact with the JS-heavy job listing panel, clicking each
card to extract details from the detail pane on the right.
"""

import time
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from driver import get_driver, passes_filters


def _build_search_url(keyword):
    q = keyword.replace(" ", "+")
    return (
        f"https://www.google.com/search?q={q}+jobs+in+Bengaluru"
        f"&ibp=htl;jobs&htivrt=jobs"
        f"&htichips=date_posted:today"
    )


def _parse_jobs_from_panel(driver, keyword):
    """Click through job cards in the Google Jobs panel and extract details."""
    jobs = []

    try:
        # Wait for the jobs panel to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.iFjolb"))
        )
    except Exception:
        print(f"    [WARN] Google Jobs panel did not load for '{keyword}'")
        return jobs

    job_cards = driver.find_elements(By.CSS_SELECTOR, "li.iFjolb")
    if not job_cards:
        # Try alternate selectors
        job_cards = driver.find_elements(By.CSS_SELECTOR, "div.PwjeAc")

    for idx, card in enumerate(job_cards):
        try:
            # Scroll card into view and click to load details
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
            time.sleep(0.3)
            card.click()
            time.sleep(0.5)

            # Extract title
            title_el = card.find_element(By.CSS_SELECTOR, "div.BjJfJf")
            title = title_el.text.strip() if title_el else ""
            if not title:
                continue

            # Extract company
            try:
                company_el = card.find_element(By.CSS_SELECTOR, "div.vNEEBe")
                company = company_el.text.strip()
            except Exception:
                company = "Unknown Company"

            # Extract location
            try:
                location_el = card.find_element(By.CSS_SELECTOR, "div.Qk80Jf")
                location = location_el.text.strip()
            except Exception:
                location = "Unknown Location"

            # Extract posted time
            try:
                time_el = card.find_element(By.CSS_SELECTOR, "span.LL4CDc")
                card_text = time_el.text.strip()
            except Exception:
                card_text = ""

            # Build a job ID from title + company
            job_id = f"gj_{re.sub(r'[^a-z0-9]', '', (title + company).lower())[:80]}"

            passes, reason = passes_filters(title, company, card_text, location)
            if not passes:
                print(f"    [SKIP] {reason}")
                continue

            # Try to get the apply link from the detail pane
            job_url = ""
            try:
                apply_link = driver.find_element(
                    By.CSS_SELECTOR, "a.pMhGee"
                )
                job_url = apply_link.get_attribute("href") or ""
            except Exception:
                pass

            if not job_url:
                try:
                    apply_link = driver.find_element(
                        By.CSS_SELECTOR, "div.B8oxKe a"
                    )
                    job_url = apply_link.get_attribute("href") or ""
                except Exception:
                    # Fallback: Google search URL
                    q = f"{title} {company} jobs".replace(" ", "+")
                    job_url = f"https://www.google.com/search?q={q}&ibp=htl;jobs"

            jobs.append({
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "url": job_url,
                "keyword": keyword,
                "source": "Google Jobs",
            })

        except Exception as e:
            print(f"    [WARN] Google Jobs parse error (card {idx}): {e}")

    return jobs


def scrape_all_keywords(keywords, on_new_job=None):
    all_jobs = []
    driver = get_driver()

    for keyword in keywords:
        url = _build_search_url(keyword)
        try:
            driver.get(url)
            time.sleep(2)

            # Scroll down in the jobs list panel to load more cards
            try:
                jobs_list = driver.find_element(By.CSS_SELECTOR, "div.zxU94d")
                for _ in range(5):
                    driver.execute_script(
                        "arguments[0].scrollTop = arguments[0].scrollHeight;",
                        jobs_list,
                    )
                    time.sleep(0.5)
            except Exception:
                pass

            jobs = _parse_jobs_from_panel(driver, keyword)
            print(f"  [Google Jobs] {keyword}: {len(jobs)} job(s)")

            for job in jobs:
                if on_new_job:
                    on_new_job(job)
                else:
                    all_jobs.append(job)

        except Exception as e:
            print(f"  [ERROR] Google Jobs '{keyword}': {e}")

        time.sleep(1)

    return all_jobs
