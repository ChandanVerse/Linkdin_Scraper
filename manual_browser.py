import os
import sys
import time
import random
from seleniumbase import Driver

def main():
    print("=== Manual Chrome Browser Launcher ===")
    print("Available profiles typically include: li_0, li_1, li_2, others")
    profile = input("Enter profile suffix (e.g., li_0): ").strip()
    
    if not profile:
        print("No profile entered. Exiting.")
        sys.exit(1)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    user_data_dir = os.path.join(base_dir, f"chrome_profile_{profile}")
    os.makedirs(user_data_dir, exist_ok=True)

    w = random.randint(1890, 1920)
    h = random.randint(1020, 1080)
    extra_args = "--no-sandbox,--disable-dev-shm-usage,--disable-gpu"

    print(f"\n[INFO] Opening Chrome using profile directory: chrome_profile_{profile}")
    print("[INFO] Use this window to manually log in, solve CAPTCHAs, or fix issues.")
    print("[INFO] The browser will remain open until you close the window or press Ctrl+C.\n")

    try:
        driver = Driver(
            uc=True,
            headless=False,
            user_data_dir=user_data_dir,
            chromium_arg=extra_args,
            window_size=f"{w},{h}",
            page_load_strategy="normal",
        )
    except Exception as e:
        print(f"Failed to launch Chrome driver: {e}")
        sys.exit(1)
    
    # Optionally open LinkedIn to make it easier to log in if it's a LinkedIn profile
    if "li_" in profile:
        print("Navigating to LinkedIn login page...")
        driver.get("https://www.linkedin.com/login")
    else:
        print("Navigating to Google...")
        driver.get("https://www.google.com")

    try:
        # Keep the script alive while the browser is open
        while True:
            time.sleep(1)
            # Check if the browser is still alive
            try:
                _ = driver.title
            except Exception:
                print("Browser window was closed by the user. Exiting script.")
                break
    except KeyboardInterrupt:
        print("\nCtrl+C received. Closing browser...")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

if __name__ == "__main__":
    main()
