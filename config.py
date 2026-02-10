import os
import random

# Discord webhook URL from environment variable (set as GitHub Secret)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# Search keywords for LinkedIn job search
SEARCH_KEYWORDS = [
    "Python Developer",
    "Data Scientist",
    "AI/ML Engineer",
    "ML Engineer",
    "AI Intern",
    "Data Science Intern",
    "ML Intern",
    "ML Engineer Intern",
]

# Location for job search
LOCATION = "Bengaluru, Karnataka, India"

# LinkedIn public job search base URL
LINKEDIN_BASE_URL = "https://www.linkedin.com/jobs/search/"

# f_TPR=r120 means jobs posted in last 2 minutes (buffer for cron drift on 1-min schedule)
# In test mode (TEST_MODE=1 env var), use r86400 (last 24 hours) to find jobs
TIME_FILTER = "r86400" if os.environ.get("TEST_MODE") else "r120"

# LinkedIn experience level filter (f_E parameter)
# 1 = Internship, 2 = Entry level, 3 = Associate
# 4 = Mid-Senior level, 5 = Director, 6 = Executive
EXPERIENCE_LEVELS = ["1", "2"]  # Internship + Entry level (fresher roles)

# Rotating User-Agent headers to avoid blocks
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Max seen job IDs to keep (prevents unbounded growth)
MAX_SEEN_JOBS = 5000

# Path to seen jobs file
SEEN_JOBS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_jobs.json")


def get_random_user_agent():
    return random.choice(USER_AGENTS)
