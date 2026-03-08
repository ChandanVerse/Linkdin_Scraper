import json
import os
import time

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from config import (
    AUTO_APPLY_DEFAULTS,
    AUTO_APPLY_DELAY,
    AUTO_APPLY_PHONE,
    AUTO_APPLY_TIMEOUT,
    ENABLE_AUTO_APPLY,
    SEARCH_KEYWORDS,
)
from driver import get_driver
from gemini_client import ask_gemini, end_chat, start_chat

APPLIED_JOBS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "applied_jobs.json"
)
MAX_APPLIED_JOBS = 5000
MAX_FORM_STEPS = 10


# ── Applied jobs tracking ──────────────────────────────────────────────


def load_applied_jobs():
    if not os.path.exists(APPLIED_JOBS_FILE):
        return []
    try:
        with open(APPLIED_JOBS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_applied_jobs(applied):
    if len(applied) > MAX_APPLIED_JOBS:
        applied = applied[-MAX_APPLIED_JOBS:]
    with open(APPLIED_JOBS_FILE, "w") as f:
        json.dump(applied, f)


def mark_job_applied(job_id):
    applied = load_applied_jobs()
    if job_id not in applied:
        applied.append(job_id)
        save_applied_jobs(applied)


# ── Keyword matching ───────────────────────────────────────────────────


def _title_matches_keyword(title):
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in SEARCH_KEYWORDS)


# ── Easy Apply button detection ────────────────────────────────────────


def _find_easy_apply_button(driver):
    selectors = [
        (By.CSS_SELECTOR, "button.jobs-apply-button"),
        (By.CSS_SELECTOR, ".jobs-s-apply button"),
        (By.XPATH, "//button[contains(@aria-label, 'Easy Apply')]"),
    ]
    for by, selector in selectors:
        try:
            btn = driver.find_element(by, selector)
            if "easy apply" in btn.text.lower():
                return btn
        except NoSuchElementException:
            continue
    return None


# ── Modal helpers ──────────────────────────────────────────────────────


def _get_modal(driver):
    selectors = [
        "div.jobs-easy-apply-modal",
        "div.jobs-easy-apply-content",
        "div[data-test-modal]",
        "div.artdeco-modal",
    ]
    for sel in selectors:
        try:
            modal = driver.find_element(By.CSS_SELECTOR, sel)
            if modal.is_displayed():
                return modal
        except NoSuchElementException:
            continue
    return None


def _dismiss_modal(driver):
    # Click dismiss / close button
    close_selectors = [
        "button[aria-label='Dismiss']",
        "button[aria-label='Close']",
        "button.artdeco-modal__dismiss",
    ]
    for sel in close_selectors:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, sel)
            btn.click()
            time.sleep(1)
            break
        except (NoSuchElementException, ElementClickInterceptedException):
            continue

    # Handle "Discard application?" confirmation dialog
    try:
        discard_btn = driver.find_element(
            By.XPATH, "//button[contains(@data-control-name, 'discard')]"
            " | //button[.//span[contains(text(), 'Discard')]]"
        )
        discard_btn.click()
        time.sleep(1)
    except NoSuchElementException:
        pass


def _click_next_or_submit(driver):
    """Click Submit, Review, or Next button. Returns 'submitted', 'next', or 'error'."""
    # Try Submit first
    for label in ("Submit application", "Submit", "Review"):
        try:
            btn = driver.find_element(
                By.XPATH, f"//button[contains(@aria-label, '{label}')]"
            )
            btn.click()
            time.sleep(2)
            if "submit" in label.lower():
                return "submitted"
            return "next"
        except NoSuchElementException:
            continue

    # Try generic Next button
    try:
        btn = driver.find_element(
            By.XPATH,
            "//button[contains(@aria-label, 'Next')]"
            " | //button[contains(@aria-label, 'Continue')]",
        )
        btn.click()
        time.sleep(2)
        return "next"
    except NoSuchElementException:
        pass

    # Fallback: footer primary button
    try:
        btn = driver.find_element(
            By.CSS_SELECTOR, "footer button.artdeco-button--primary"
        )
        btn.click()
        time.sleep(2)
        btn_text = btn.text.lower()
        if "submit" in btn_text:
            return "submitted"
        return "next"
    except NoSuchElementException:
        pass

    return "error"


def _has_validation_errors(driver):
    try:
        errors = driver.find_elements(
            By.CSS_SELECTOR,
            ".artdeco-inline-feedback--error, "
            ".fb-dash-form-element__error-field, "
            "[data-test-form-element-error]",
        )
        return any(e.is_displayed() for e in errors)
    except Exception:
        return False


# ── Form field handlers ────────────────────────────────────────────────


def _match_default(label_lower):
    # Try longest keys first so "first name" matches before "name"
    matches = [(key, value) for key, value in AUTO_APPLY_DEFAULTS.items()
               if key in label_lower]
    if matches:
        # Return the value for the most specific (longest) matching key
        matches.sort(key=lambda kv: len(kv[0]), reverse=True)
        return matches[0][1]
    return None


def _fill_text_fields(modal, job_context):
    fields = modal.find_elements(
        By.CSS_SELECTOR,
        "input[type='text'], input[type='tel'], input[type='number'], textarea",
    )
    for field in fields:
        try:
            if not field.is_displayed():
                continue
            # Skip if already filled
            current_val = field.get_attribute("value") or ""
            if current_val.strip():
                continue

            # Find label
            field_id = field.get_attribute("id") or ""
            label = ""
            if field_id:
                try:
                    label_el = modal.find_element(
                        By.CSS_SELECTOR, f"label[for='{field_id}']"
                    )
                    label = label_el.text.strip()
                except NoSuchElementException:
                    pass
            if not label:
                label = field.get_attribute("aria-label") or ""
            if not label:
                label = field.get_attribute("placeholder") or ""

            label_lower = label.lower()

            # Phone number
            if any(kw in label_lower for kw in ("phone", "mobile", "contact number")):
                field.clear()
                field.send_keys(AUTO_APPLY_PHONE)
                continue

            # Check defaults
            default_val = _match_default(label_lower)
            if default_val is not None:
                # Numeric fields can't accept text like "Negotiable"
                field_type = (field.get_attribute("type") or "").lower()
                if field_type == "number" and not default_val.replace(".", "").isdigit():
                    default_val = "400000"
                field.clear()
                field.send_keys(default_val)
                continue

            # Ask Gemini
            answer = ask_gemini(label, job_context=job_context)
            if answer:
                field.clear()
                field.send_keys(answer)
        except StaleElementReferenceException:
            continue


def _fill_dropdowns(modal, job_context):
    selects = modal.find_elements(By.CSS_SELECTOR, "select")
    for select_el in selects:
        try:
            if not select_el.is_displayed():
                continue

            sel = Select(select_el)
            # Skip if already selected (not on placeholder)
            current = sel.first_selected_option.text.strip()
            if current and current.lower() not in ("select an option", "select", "--", ""):
                continue

            # Find label
            field_id = select_el.get_attribute("id") or ""
            label = ""
            if field_id:
                try:
                    label_el = modal.find_element(
                        By.CSS_SELECTOR, f"label[for='{field_id}']"
                    )
                    label = label_el.text.strip()
                except NoSuchElementException:
                    pass
            label_lower = label.lower()

            options = [o.text.strip() for o in sel.options if o.text.strip() and
                       o.text.strip().lower() not in ("select an option", "select", "--", "")]

            if not options:
                continue

            # Experience dropdowns → pick smallest numeric
            if any(kw in label_lower for kw in ("experience", "years")):
                for opt in options:
                    if any(c.isdigit() for c in opt):
                        sel.select_by_visible_text(opt)
                        break
                else:
                    sel.select_by_visible_text(options[0])
                continue

            # Check defaults
            default_val = _match_default(label_lower)
            if default_val is not None:
                # Find closest matching option
                for opt in options:
                    if default_val.lower() in opt.lower():
                        sel.select_by_visible_text(opt)
                        break
                else:
                    sel.select_by_visible_text(options[0])
                continue

            # Ask Gemini
            answer = ask_gemini(label, options=options, job_context=job_context)
            if answer:
                # Find closest matching option
                for opt in options:
                    if answer.lower() == opt.lower():
                        sel.select_by_visible_text(opt)
                        break
                else:
                    # Partial match
                    for opt in options:
                        if answer.lower() in opt.lower() or opt.lower() in answer.lower():
                            sel.select_by_visible_text(opt)
                            break
                    else:
                        sel.select_by_visible_text(options[0])
            else:
                sel.select_by_visible_text(options[0])
        except (StaleElementReferenceException, NoSuchElementException):
            continue


def _fill_radio_buttons(modal, job_context):
    fieldsets = modal.find_elements(By.CSS_SELECTOR, "fieldset")
    for fieldset in fieldsets:
        try:
            if not fieldset.is_displayed():
                continue

            radios = fieldset.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            if not radios:
                continue

            # Check if one is already selected
            if any(r.is_selected() for r in radios):
                continue

            # Get legend / label
            label = ""
            try:
                legend = fieldset.find_element(By.CSS_SELECTOR, "legend, span.fb-dash-form-element__label")
                label = legend.text.strip()
            except NoSuchElementException:
                pass
            label_lower = label.lower()

            # Get option labels
            option_labels = []
            for radio in radios:
                radio_id = radio.get_attribute("id") or ""
                opt_label = ""
                if radio_id:
                    try:
                        lbl = fieldset.find_element(By.CSS_SELECTOR, f"label[for='{radio_id}']")
                        opt_label = lbl.text.strip()
                    except NoSuchElementException:
                        pass
                option_labels.append(opt_label)

            options_lower = [o.lower() for o in option_labels]

            # Check defaults
            default_val = _match_default(label_lower)
            if default_val is not None:
                for i, opt in enumerate(options_lower):
                    if default_val.lower() in opt:
                        radios[i].click()
                        break
                continue

            # Yes/No default → Yes
            if "yes" in options_lower and "no" in options_lower:
                idx = options_lower.index("yes")
                radios[idx].click()
                continue

            # Ask Gemini
            answer = ask_gemini(label, options=option_labels, job_context=job_context)
            if answer:
                for i, opt in enumerate(option_labels):
                    if answer.lower() == opt.lower():
                        radios[i].click()
                        break
                else:
                    radios[0].click()
            else:
                radios[0].click()
        except StaleElementReferenceException:
            continue


def _fill_checkboxes(modal):
    checkboxes = modal.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
    for cb in checkboxes:
        try:
            if not cb.is_displayed():
                continue
            # Uncheck "Follow company"
            cb_id = cb.get_attribute("id") or ""
            label = ""
            if cb_id:
                try:
                    lbl = modal.find_element(By.CSS_SELECTOR, f"label[for='{cb_id}']")
                    label = lbl.text.strip().lower()
                except NoSuchElementException:
                    pass
            if "follow" in label and cb.is_selected():
                cb.click()
        except StaleElementReferenceException:
            continue


# ── Single job application ─────────────────────────────────────────────


def _apply_to_job(job):
    """Attempt to apply to a single job via Easy Apply.

    Returns: "applied", "not_easy_apply", "skipped", "error", "not_matched"
    """
    if not _title_matches_keyword(job["title"]):
        return "not_matched"

    applied_ids = load_applied_jobs()
    if job["job_id"] in applied_ids:
        return "skipped"

    driver = get_driver()
    job_context = {"title": job["title"], "company": job["company"]}

    # Start a Gemini chat session for this job (resume sent once)
    start_chat(job_context)

    try:
        # Navigate to job page to check for Easy Apply button
        driver.get(job["url"])
        time.sleep(3)

        # Find Easy Apply button on the actual page (don't rely on card badge)
        ea_button = _find_easy_apply_button(driver)
        if not ea_button:
            end_chat()
            return "not_easy_apply"

        ea_button.click()
        time.sleep(2)

        start_time = time.time()
        steps = 0

        while steps < MAX_FORM_STEPS:
            if time.time() - start_time > AUTO_APPLY_TIMEOUT:
                print(f"    [TIMEOUT] {job['title']}")
                _dismiss_modal(driver)
                return "error"

            modal = _get_modal(driver)
            if not modal:
                # Check if we landed on a success page
                try:
                    success = driver.find_element(
                        By.XPATH,
                        "//*[contains(text(), 'application was sent')]"
                        " | //*[contains(text(), 'Application submitted')]",
                    )
                    if success:
                        mark_job_applied(job["job_id"])
                        return "applied"
                except NoSuchElementException:
                    pass
                _dismiss_modal(driver)
                return "error"

            # Fill all form fields
            _fill_text_fields(modal, job_context)
            _fill_dropdowns(modal, job_context)
            _fill_radio_buttons(modal, job_context)
            _fill_checkboxes(modal)

            result = _click_next_or_submit(driver)

            if result == "submitted":
                time.sleep(2)
                # Check for post-submit confirmation
                mark_job_applied(job["job_id"])
                # Dismiss any success overlay
                _dismiss_modal(driver)
                return "applied"

            if result == "error":
                _dismiss_modal(driver)
                return "error"

            # Check validation errors after clicking Next
            time.sleep(1)
            if _has_validation_errors(driver):
                print(f"    [VALIDATION] {job['title']}")
                _dismiss_modal(driver)
                return "error"

            steps += 1

        # Too many steps
        _dismiss_modal(driver)
        return "error"

    except Exception as e:
        print(f"    [ERROR] Easy Apply failed for {job['title']}: {e}")
        try:
            _dismiss_modal(driver)
        except Exception:
            pass
        return "error"
    finally:
        end_chat()


# ── Public entry point ─────────────────────────────────────────────────


def auto_apply_to_jobs(new_jobs):
    """Attempt Easy Apply on matching jobs. Adds 'applied' key to each job dict."""
    if not ENABLE_AUTO_APPLY:
        return new_jobs

    for job in new_jobs:
        if job.get("source") != "LinkedIn":
            continue

        status = _apply_to_job(job)
        log_prefix = {
            "applied": "[APPLIED]",
            "not_easy_apply": "[NO-EA]",
            "skipped": "[SKIP]",
            "error": "[ERROR]",
            "not_matched": "[NO-MATCH]",
        }.get(status, "[???]")

        print(f"  {log_prefix} {job['title']} at {job['company']}")

        job["applied"] = status == "applied"

        if status in ("applied", "error"):
            time.sleep(AUTO_APPLY_DELAY)

    return new_jobs
