import os

from dotenv import load_dotenv

load_dotenv()

# Discord webhook URL
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# Search keywords — major roles first, then junior/intern variants
SEARCH_KEYWORDS = [
    "Data Scientist",
    "Python Developer",
    "ML Engineer",
    "AI Engineer",
    "Software Engineer",
    "Junior Python Developer",
    "Junior Data Scientist",
    "AI Intern",
    "Data Science Intern",
    "ML Intern",
    "ML Engineer Intern",
]

# Location for job search
LOCATION = "Bengaluru, Karnataka, India"

# f_TPR filter: r300 = jobs posted in last 5 minutes
TIME_FILTER = "r300"

# How often to run locally (in seconds)
RUN_INTERVAL = 300

# Max age of job posting to notify (in hours)
MAX_JOB_AGE_HOURS = 3

# Experience level filter: 1 = Internship, 2 = Entry level
EXPERIENCE_LEVELS = ["1", "2"]

# Blacklisted companies — jobs from these companies are skipped
BLACKLISTED_COMPANIES = [
    "skoollage",
    "dexter's tech",
    "sportsbuzz",
    "webs it solution",
    "zenithbyte",
    "skillzenloop",
    "Webs X UM",
    "inficore soft",
]

# Max seen job IDs to keep
MAX_SEEN_JOBS = 5000

# Path to seen jobs file
SEEN_JOBS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_jobs.json")

# Enable/disable job sites
ENABLE_LINKEDIN = True
ENABLE_NAUKRI = True
ENABLE_INDEED = True
ENABLE_FOUNDIT = True
