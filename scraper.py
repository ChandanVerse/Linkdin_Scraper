import re
import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from config import EXPERIENCE_LEVELS, LOCATION, TIME_FILTER

EXCLUDE_TITLE_KEYWORDS = [
    "senior", "sr.", "sr ", "lead", "principal", "staff", "manager",
    "director", "head of", "vp ", "vice president", "architect",
    "10+", "8+", "7+", "6+", "5+", "4+",
    "14+", "12+", "11+", "9+",
    "years", "yrs",
    "l4", "l5", "l6", "l7",
    "sde 3", "sde3", "sde-3", "sde iii", "sde-iii",
    "technologist",
]

_driver = None


def get_driver():
    global _driver
    if _driver is not None:
        return _driver

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    service = Service(ChromeDriverManager().install())
    _driver = webdriver.Chrome(service=service, options=options)
    return _driver


def linkedin_login(email, password):
    driver = get_driver()
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
            return True
        elif "checkpoint" in driver.current_url or "challenge" in driver.current_url:
            print("  [WARN] LinkedIn requires verification. Waiting 60s...")
            time.sleep(60)
            return "feed" in driver.current_url
        else:
            print(f"  [ERROR] Login may have failed. URL: {driver.current_url}")
            return False
    except Exception as e:
        print(f"  [ERROR] Login failed: {e}")
        return False


def build_search_url(keyword):
    params = [
        f"keywords={keyword.replace(' ', '%20')}",
        f"location={LOCATION.replace(' ', '%20').replace(',', '%2C')}",
        f"f_TPR={TIME_FILTER}",
    ]
    if EXPERIENCE_LEVELS:
        params.append(f"f_E={'%2C'.join(EXPERIENCE_LEVELS)}")
    return f"https://www.linkedin.com/jobs/search/?{'&'.join(params)}"


def scrape_jobs(keyword):
    driver = get_driver()
    url = build_search_url(keyword)

    try:
        driver.get(url)
        time.sleep(3)

        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        soup = BeautifulSoup(driver.page_source, "lxml")
        return parse_job_cards(soup, keyword)
    except Exception as e:
        print(f"  [ERROR] Failed to scrape '{keyword}': {e}")
        return []


def parse_job_cards(soup, keyword):
    jobs = []

    job_cards = soup.find_all("div", class_="base-card")
    if not job_cards:
        job_cards = soup.find_all("li", class_="jobs-search-results__list-item")
    if not job_cards:
        job_cards = soup.find_all("div", class_="job-card-container")

    for card in job_cards:
        try:
            link_tag = (
                card.find("a", class_="base-card__full-link")
                or card.find("a", class_="job-card-container__link")
                or card.find("a", href=re.compile(r"/jobs/view/"))
            )
            if not link_tag:
                continue

            job_url = link_tag.get("href", "").strip()
            job_id = extract_job_id(job_url)
            if not job_id:
                continue

            title = _get_text(card, [
                ("h3", "base-search-card__title"),
                ("a", "job-card-list__title"),
                ("h3", None),
            ], "Unknown Title")

            company = _get_text(card, [
                ("h4", "base-search-card__subtitle"),
                ("span", "job-card-container__primary-description"),
                ("h4", None),
            ], "Unknown Company")

            location = _get_text(card, [
                ("span", "job-search-card__location"),
                ("span", "job-card-container__metadata-item"),
            ], "Unknown Location")

            if any(kw in title.lower() for kw in EXCLUDE_TITLE_KEYWORDS):
                print(f"    [SKIP] {title}")
                continue

            clean_url = job_url.split("?")[0]
            if not clean_url.startswith("http"):
                clean_url = f"https://www.linkedin.com{clean_url}"

            jobs.append({
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "url": clean_url,
                "keyword": keyword,
            })
        except Exception as e:
            print(f"  [WARN] Failed to parse job card: {e}")

    return jobs


def _get_text(card, selectors, default):
    for tag, cls in selectors:
        el = card.find(tag, class_=cls) if cls else card.find(tag)
        if el:
            return el.get_text(strip=True)
    return default


def extract_job_id(url):
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
        jobs = scrape_jobs(keyword)
        print(f"    Found {len(jobs)} job(s)")
        all_jobs.extend(jobs)
        time.sleep(2)
    return all_jobs


def close_driver():
    global _driver
    if _driver:
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None
