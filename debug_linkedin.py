"""Debug script to diagnose LinkedIn scraper issues on EC2."""
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from driver import get_driver
from linkedin_scraper import _load_cookies, _build_search_url, _parse_job_cards, COOKIES_FILE
from bs4 import BeautifulSoup


def main():
    print("=" * 50)
    print("LinkedIn Debug Script")
    print("=" * 50)

    # 1. Check cookies file
    print(f"\n[1] Cookies file: {COOKIES_FILE}")
    if os.path.exists(COOKIES_FILE):
        import json
        with open(COOKIES_FILE) as f:
            cookies = json.load(f)
        print(f"    Found {len(cookies)} cookies")
    else:
        print("    NOT FOUND - no cookies file")
        print("    Copy from local: scp linkedin_cookies.json ubuntu@<ec2-ip>:~/scraper/")

    # 2. Start driver
    print("\n[2] Starting Chrome driver...")
    driver = get_driver()
    print(f"    Driver started OK")

    # 3. Load cookies
    print("\n[3] Loading cookies...")
    ok = _load_cookies(driver)
    print(f"    Cookie load result: {ok}")
    print(f"    Current URL: {driver.current_url}")
    print(f"    Page title: {driver.title}")

    # 4. Check if logged in
    print("\n[4] Login check...")
    logged_in = "feed" in driver.current_url or "mynetwork" in driver.current_url
    print(f"    Logged in: {logged_in}")

    if not logged_in:
        # Try manual login
        li_email = os.environ.get("LINKEDIN_EMAIL", "")
        li_password = os.environ.get("LINKEDIN_PASSWORD", "")
        if li_email:
            print(f"    Trying login with {li_email}...")
            from linkedin_scraper import linkedin_login
            ok = linkedin_login(li_email, li_password)
            print(f"    Login result: {ok}")
            logged_in = ok
        else:
            print("    No LINKEDIN_EMAIL in env")

    # 5. Try a job search
    print("\n[5] Testing job search...")
    url = _build_search_url("Data Scientist")
    print(f"    URL: {url}")
    driver.get(url)
    time.sleep(5)
    print(f"    Landed on: {driver.current_url}")
    print(f"    Page title: {driver.title}")

    # 6. Parse the page
    soup = BeautifulSoup(driver.page_source, "lxml")
    page_text = soup.get_text()
    page_len = len(driver.page_source)
    print(f"    Page source size: {page_len} chars")

    # Check for common issues
    if "sign in" in page_text.lower() or "join now" in page_text.lower():
        print("    WARNING: Page shows sign-in prompt (not logged in)")
    if "no matching jobs" in page_text.lower() or "no results" in page_text.lower():
        print("    WARNING: LinkedIn says no matching jobs")
    if "unusual activity" in page_text.lower() or "captcha" in page_text.lower():
        print("    WARNING: LinkedIn is showing captcha/block page")

    # 7. Look for job cards
    print("\n[6] Looking for job cards...")
    import re
    cards_v1 = soup.find_all("li", class_=re.compile(r"jobs-search-results__list-item"))
    cards_v2 = soup.find_all("div", class_=re.compile(r"job-card-container"))
    cards_v3 = soup.find_all("div", class_="base-card")
    print(f"    jobs-search-results__list-item: {len(cards_v1)}")
    print(f"    job-card-container: {len(cards_v2)}")
    print(f"    base-card: {len(cards_v3)}")

    jobs = _parse_job_cards(soup, "Data Scientist")
    print(f"    Parsed jobs (after filters): {len(jobs)}")

    # 8. Save page for manual inspection
    debug_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_page.html")
    with open(debug_file, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"\n[7] Saved full page to: {debug_file}")

    # 9. Test recommended page
    print("\n[8] Testing recommended jobs page...")
    driver.get("https://www.linkedin.com/jobs/collections/recommended/")
    time.sleep(5)
    print(f"    Landed on: {driver.current_url}")
    soup2 = BeautifulSoup(driver.page_source, "lxml")
    cards_rec = soup2.find_all("li", class_=re.compile(r"jobs-search-results__list-item"))
    cards_rec2 = soup2.find_all("div", class_=re.compile(r"job-card-container"))
    print(f"    jobs-search-results__list-item: {len(cards_rec)}")
    print(f"    job-card-container: {len(cards_rec2)}")

    driver.quit()
    print("\n" + "=" * 50)
    print("Debug complete. Share output above to diagnose.")
    print("=" * 50)


if __name__ == "__main__":
    main()
