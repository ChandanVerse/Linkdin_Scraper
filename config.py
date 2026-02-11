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
    "Junior Python Developer",
    "Junior Data Scientist",
    "AI Intern",
    "Data Science Intern",
    "ML Intern",
    "ML Engineer Intern",
    "MLOps",
    "DevOps",
]

# Relevant domain terms — job title must contain at least one of these
# NOTE: broad words like "intern", "engineer", "analyst", "developer" are excluded
# because they match irrelevant roles (Recruiting Intern, Business Dev Intern, etc.)
# Domain-specific terms ensure only tech/data/AI jobs pass through.
RELEVANT_TITLE_TERMS = [
    "data", "python", "ml", "ai", "machine learning", "artificial intelligence",
    "deep learning", "software", "devops", "mlops", "backend", "frontend",
    "full stack", "fullstack", "cloud", "computer vision", "nlp",
    "generative ai", "gen ai", "genai", "llm", "sde", "swe",
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
    "VEDIST SYSTEMS PRIVATE LIMITED",
]

# Enable/disable job sites
ENABLE_LINKEDIN = True
ENABLE_NAUKRI = True
ENABLE_INDEED = True
ENABLE_FOUNDIT = True
ENABLE_INTERNSHALA = True

# AWS DynamoDB settings (set AWS_ACCESS_KEY_ID & AWS_SECRET_ACCESS_KEY in .env)
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "job_scraper_seen_jobs")
