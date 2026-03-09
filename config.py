import os

from dotenv import load_dotenv

load_dotenv()

# Discord webhook URL
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

def _load_accounts_from_env():
    accounts = []
    i = 0
    while True:
        email = os.environ.get(f"LINKEDIN_ACCOUNT_{i}_EMAIL")
        password = os.environ.get(f"LINKEDIN_ACCOUNT_{i}_PASSWORD")
        if not email or not password:
            break
        name = os.environ.get(f"LINKEDIN_ACCOUNT_{i}_NAME", f"Account {i}")
        accounts.append({"email": email, "password": password, "name": name})
        i += 1
    return accounts

LINKEDIN_ACCOUNTS = _load_accounts_from_env()

# ── Rotation settings ──────────────────────────────────────────────────
ACCOUNT_COOLDOWN_HOURS = 2.0    # hours to cool down an account after a challenge
MIN_ROTATION_DELAY = 8.0        # min seconds to pause between account switches
MAX_ROTATION_DELAY = 20.0       # max seconds to pause between account switches

# ── Search settings ────────────────────────────────────────────────────
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
    "Artificial Intelligence Engineer",
    "Associate AI/ML Engineer",
    "Generative AI Engineer",
    "Applied AI Engineer",
]

# Relevant domain terms — job title must contain at least one of these
RELEVANT_TITLE_TERMS = [
    "data science", "data scientist", "python", "ml", "ai", "machine learning",
    "artificial intelligence", "deep learning", "software", "mlops", "backend",
    "cloud", "computer vision", "nlp", "generative ai", "gen ai", "genai", "llm",
]

# Location for job search
LOCATION = "Bengaluru, Karnataka, India"

# f_TPR filter: r300 = jobs posted in last 5 minutes
TIME_FILTER = "r300"

# How often to run the full cycle (in seconds)
RUN_INTERVAL = 300

# Max age of job posting to notify (in hours)
MAX_JOB_AGE_HOURS = 3

# Experience level filter: 1 = Internship, 2 = Entry level
EXPERIENCE_LEVELS = ["1", "2"]

# Blacklisted companies — jobs from these are skipped
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
    "Uplers",
    "Atricu MakeuspeakEdtech",
    "Binated",
    "scoutit",
]

# Blacklisted title keywords — jobs with these in the title are skipped
BLACKLISTED_TITLE_KEYWORDS = [
    "senior", "sr.", "sr ", "lead", "principal", "staff", "manager",
    "director", "head of", "vp ", "vice president", "architect",
    "10+", "8+", "7+", "6+", "5+", "4+",
    "14+", "12+", "11+", "9+",
    "years", "yrs",
    "l4", "l5", "l6", "l7",
    "sde 3", "sde3", "sde-3", "sde iii", "sde-iii",
    "technologist",
]

# Enable/disable job sites
ENABLE_LINKEDIN = True
ENABLE_INTERNSHALA = True
ENABLE_NAUKRI = True
ENABLE_INDEED = False
ENABLE_FOUNDIT = False
ENABLE_GOOGLE_JOBS = True