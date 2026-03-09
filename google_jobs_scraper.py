"""
Google Jobs scraper — scrapes Google's job search results (udm=8).

Uses JavaScript extraction to parse job cards from the page.
CSS classes (as of March 2026):
  - a.MQUd2b       = job card link (contains vhid/docid in href)
  - .tNxQIb        = job title
  - .MKCbgd.a3jPc  = company name
  - .FqK3wc        = location
  - .K3eUK         = posted time ("4 days ago")
"""

import re
import time
import urllib.parse

from driver import get_driver, passes_filters


_EXTRACT_JOBS_JS = """
var cards = document.querySelectorAll('a.MQUd2b');
var results = [];
for (var i = 0; i < cards.length; i++) {
    var link = cards[i];
    var href = link.getAttribute('href') || '';
    var docMatch = href.match(/docid[=%3D]+([^&]+)/);
    if (!docMatch) continue;

    var titleEl = link.querySelector('.tNxQIb');
    var companyEl = link.querySelector('.MKCbgd.a3jPc');
    var locationEl = link.querySelector('.FqK3wc');
    var timeEl = link.parentElement.querySelector('.K3eUK');

    var title = titleEl ? titleEl.textContent.trim() : '';
    if (!title) continue;

    results.push({
        docid: docMatch[1],
        title: title,
        company: companyEl ? companyEl.textContent.trim() : 'Unknown Company',
        location: locationEl ? locationEl.textContent.trim() : 'Unknown Location',
        time: timeEl ? timeEl.textContent.trim() : ''
    });
}
return results;
"""

# JS to extract the external apply URL from the job detail panel after clicking a card
_EXTRACT_APPLY_URL_JS = """
// Look for the "Apply" button/link in the job detail panel
var applyLinks = document.querySelectorAll('a.pMhGee, a[jsname="HUL5je"], a[data-ved]');
for (var i = 0; i < applyLinks.length; i++) {
    var href = applyLinks[i].href || '';
    // Filter out Google internal links — we want the external apply URL
    if (href && !href.includes('google.com/search') && !href.startsWith('javascript:')
        && (href.startsWith('http://') || href.startsWith('https://'))) {
        return href;
    }
}
// Fallback: try any external link in the job detail area
var detailPanel = document.querySelector('.whazf, .gws-plugins-horizon-jobs__tl-lif');
if (detailPanel) {
    var links = detailPanel.querySelectorAll('a[href]');
    for (var i = 0; i < links.length; i++) {
        var href = links[i].href || '';
        if (href && !href.includes('google.com') && !href.startsWith('javascript:')
            && (href.startsWith('http://') || href.startsWith('https://'))) {
            return href;
        }
    }
}
return '';
"""


def _build_search_url(keyword):
    q = keyword.replace(" ", "+")
    return f"https://www.google.com/search?q={q}+jobs+in+Bengaluru&udm=8"


def _build_google_jobs_url(keyword, docid):
    """Build a direct Google Jobs URL that opens the specific job listing panel."""
    q = urllib.parse.quote_plus(f"{keyword} jobs in Bengaluru")
    return (
        f"https://www.google.com/search?q={q}&udm=8"
        f"#htivrt=jobs&htidocid={docid}"
    )


def _try_get_apply_url(driver, card_index):
    """Click a job card and try to extract the external apply URL."""
    try:
        click_js = f"""
        var cards = document.querySelectorAll('a.MQUd2b');
        if (cards[{card_index}]) {{
            cards[{card_index}].click();
            return true;
        }}
        return false;
        """
        clicked = driver.execute_script(click_js)
        if not clicked:
            return ""

        time.sleep(1.5)  # wait for the detail panel to load

        apply_url = driver.execute_script(_EXTRACT_APPLY_URL_JS)
        return apply_url or ""
    except Exception:
        return ""


def _extract_jobs(driver, keyword):
    """Extract job data from the Google Jobs page using JavaScript."""
    jobs = []

    try:
        raw_jobs = driver.execute_script(_EXTRACT_JOBS_JS)
    except Exception as e:
        print(f"    [WARN] Google Jobs JS extraction failed for '{keyword}': {e}")
        return jobs

    if not raw_jobs:
        print(f"    [WARN] No Google Jobs cards found for '{keyword}'")
        return jobs

    for idx, raw in enumerate(raw_jobs):
        try:
            title = raw.get("title", "")
            company = raw.get("company", "Unknown Company")
            location = raw.get("location", "Unknown Location")
            time_text = raw.get("time", "")
            docid = raw.get("docid", "")

            if not title:
                continue

            # Clean location: remove "• via ..." suffix
            location = re.split(r"\s*[•·]\s*via\s", location)[0].strip()

            job_id = f"gj_{re.sub(r'[^a-z0-9]', '', docid.lower())[:80]}"

            passes, reason = passes_filters(title, company, time_text, location)
            if not passes:
                print(f"    [SKIP] {reason}")
                continue

            # Try to get the actual external apply URL by clicking the card
            apply_url = _try_get_apply_url(driver, idx)

            if apply_url:
                url = apply_url
            else:
                # Fallback: build a direct Google Jobs URL with the docid
                # This opens Google Jobs with the specific job panel open
                url = _build_google_jobs_url(keyword, docid)

            jobs.append({
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "keyword": keyword,
                "source": "Google Jobs",
            })

        except Exception as e:
            print(f"    [WARN] Google Jobs parse error: {e}")

    return jobs


def scrape_all_keywords(keywords, on_new_job=None):
    all_jobs = []
    driver = get_driver()

    for keyword in keywords:
        url = _build_search_url(keyword)
        try:
            driver.get(url)
            time.sleep(3)

            # Scroll page to load more results
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)

            jobs = _extract_jobs(driver, keyword)
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
