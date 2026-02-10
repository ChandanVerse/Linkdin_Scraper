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

# f_TPR filter: r3600 = jobs posted in last 1 hour
TIME_FILTER = "r3600"

# How often to run locally (in seconds)
RUN_INTERVAL = 120

# Experience level filter: 1 = Internship, 2 = Entry level
EXPERIENCE_LEVELS = ["1", "2"]

# Max seen job IDs to keep
MAX_SEEN_JOBS = 5000

# Path to seen jobs file
SEEN_JOBS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_jobs.json")
