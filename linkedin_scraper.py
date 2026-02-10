import json
import os
import re
import time

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import EXPERIENCE_LEVELS, LOCATION, TIME_FILTER
from driver import get_driver, passes_filters, reset_driver

COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "linkedin_cookies.json")


def _save_cookies(driver):
    cookies = driver.get_cookies()
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f)
    print(f"  Saved {len(cookies)} cookies")


def _load_cookies(driver):
    if not os.path.exists(COOKIES_FILE):
        return False
    try:
        with open(COOKIES_FILE, "r") as f:
            cookies = json.load(f)
        driver.get("https://www.linkedin.com")
        time.sleep(2)
        for cookie in cookies:
            cookie.pop("sameSite", None)
            cookie.pop("expiry", None)
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
        driver.get("https://www.linkedin.com/feed/")
        time.sleep(3)
        if "feed" in driver.current_url or "mynetwork" in driver.current_url:
            print("  Restored session from saved cookies!")
            return True
        print("  Saved cookies expired, logging in fresh...")
        return False
    except Exception:
        return False


def linkedin_login(email, password):
    driver = get_driver()

    if _load_cookies(driver):
        return True

    driver.get("https://www.linkedin.com/login")
    time.sleep(2)

    try:
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        email_field.send_keys(email)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(3)

        if "feed" in driver.current_url or "mynetwork" in driver.current_url:
            print("  LinkedIn login successful!")
            _save_cookies(driver)
            return True
        elif "checkpoint" in driver.current_url or "challenge" in driver.current_url:
            print("  [WARN] LinkedIn requires verification.")
            print("  Complete the verification in the browser window...")
            for i in range(24):
                time.sleep(5)
                try:
                    url = driver.current_url
                    if "feed" in url or "mynetwork" in url or "jobs" in url:
                        print("  LinkedIn login successful!")
                        _save_cookies(driver)
                        return True
                except Exception:
                    print("  [ERROR] Browser closed during verification.")
                    reset_driver()
                    return False
            print("  [WARN] Verification timed out after 120s.")
            return False
        else:
            print(f"  [ERROR] Login may have failed. URL: {driver.current_url}")
            return False
    except Exception as e:
        print(f"  [ERROR] Login failed: {e}")
        reset_driver()
        return False


def _build_search_url(keyword):
    params = [
        f"keywords={keyword.replace(' ', '%20')}",
        f"location={LOCATION.replace(' ', '%20').replace(',', '%2C')}",
        f"f_TPR={TIME_FILTER}",
    ]
    if EXPERIENCE_LEVELS:
        params.append(f"f_E={'%2C'.join(EXPERIENCE_LEVELS)}")
    return f"https://www.linkedin.com/jobs/search/?{'&'.join(params)}"


def _scrape_jobs(keyword):
    driver = get_driver()
    url = _build_search_url(keyword)

    try:
        driver.get(url)
        time.sleep(3)

        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        soup = BeautifulSoup(driver.page_source, "lxml")
        return _parse_job_cards(soup, keyword)
    except Exception as e:
        print(f"  [ERROR] Failed to scrape '{keyword}': {e}")
        return []


def _parse_job_cards(soup, keyword):
    jobs = []

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
            ], None)
            if not title and link_tag:
                title = link_tag.get_text(strip=True)
            if not title:
                title = "Unknown Title"

            company_div = card.find("div", class_=re.compile(r"artdeco-entity-lockup__subtitle"))
            if company_div:
                company_span = company_div.find("span")
                company = company_span.get_text(strip=True) if company_span else "Unknown Company"
            else:
                company = _get_text(card, [
                    ("span", "job-card-container__primary-description"),
                    ("h4", "base-search-card__subtitle"),
                ], "Unknown Company")

            caption_div = card.find("div", class_=re.compile(r"artdeco-entity-lockup__caption"))
            if caption_div:
                loc_span = caption_div.find("span")
                location = loc_span.get_text(strip=True) if loc_span else "Unknown Location"
            else:
                location = _get_text(card, [
                    ("li", "job-card-container__metadata-item"),
                    ("span", "job-search-card__location"),
                ], "Unknown Location")

            card_text = card.get_text(" ", strip=True)
            passes, reason = passes_filters(title, company, card_text)
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
            })
        except Exception as e:
            print(f"  [WARN] Failed to parse job card: {e}")

    return jobs


def _get_text(card, selectors, default):
    for tag, cls in selectors:
        if cls:
            el = card.find(tag, class_=cls)
        else:
            el = card.find(tag)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)
    return default


def _extract_job_id(url):
    try:
        path = url.split("?")[0].rstrip("/")
        last = path.split("/")[-1]
        if last.isdigit():
            return last
        match = re.search(r"-(\d{5,})$", last)
        if match:
            return match.group(1)
        match = re.search(r"/view/(\d+)", url)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def scrape_all_keywords(keywords):
    all_jobs = []
    for keyword in keywords:
        print(f"  Scraping: {keyword}")
        jobs = _scrape_jobs(keyword)
        print(f"    Found {len(jobs)} job(s)")
        all_jobs.extend(jobs)
        time.sleep(2)
    return all_jobs
