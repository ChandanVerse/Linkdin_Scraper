# Job Scraper

A parallel job scraping tool for **LinkedIn**, **Naukri**, and **Internshala** with instant Discord notifications.

## Features

- **Parallel Scraping** — LinkedIn runs in one thread, Naukri + Internshala in another.
- **Headless Browser** — Runs Chrome in headless mode (no visible window).
- **Guest Mode** — LinkedIn is scraped via public/guest search (no login required).
- **Instant Discord Alerts** — Jobs are sent to Discord the moment they're found.
- **Smart Filtering** — Filters by title keywords, company blacklist, location, experience level, and posting age.
- **Startup Sweep** — Catches jobs posted in the last 24 hours when the scraper first starts.
- **Deduplication** — Tracks seen jobs to avoid duplicate notifications.

## Project Structure

```
├── main.py               # Entry point — parallel scrape loop + Discord notifier
├── linkedin_scraper.py   # LinkedIn guest-mode scraper
├── internshala_scraper.py# Internshala jobs + internships scraper
├── naukri_scraper.py     # Naukri scraper
├── driver.py             # Headless Selenium driver + job filters + age parser
├── config.py             # All settings: keywords, filters, blacklists
├── notifier.py           # Discord webhook notifications
├── tracker.py            # Seen-job persistence (JSON)
├── .env                  # Discord webhook URL (secret)
└── requirements.txt      # Python dependencies
```

## Setup

1. **Clone** the repository
2. **Create a virtual environment** and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate     # Windows
   pip install -r requirements.txt
   ```
3. **Configure `.env`** with your Discord webhook URL:
   ```
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
   ```
4. **Edit `config.py`** to customise search keywords, location, blacklists, and filters.

## Usage

```bash
# Run continuously (scrapes every 5 minutes)
python main.py

# Run a single cycle and exit
python main.py --once
```

## Configuration

All settings are in `config.py`:

| Setting | Description | Default |
|---|---|---|
| `SEARCH_KEYWORDS` | List of job search terms | Data Scientist, ML Engineer, etc. |
| `LOCATION` | Job location filter | Bengaluru, Karnataka, India |
| `TIME_FILTER` | LinkedIn time filter (seconds) | `r600` (last 10 min) |
| `RUN_INTERVAL` | Seconds between scrape cycles | `300` (5 min) |
| `MAX_JOB_AGE_HOURS` | Max posting age to notify | `3` hours |
| `EXPERIENCE_LEVELS` | LinkedIn experience filter | `1` (Intern), `2` (Entry) |
| `ENABLE_LINKEDIN` | Toggle LinkedIn scraping | `True` |
| `ENABLE_INTERNSHALA` | Toggle Internshala scraping | `True` |
| `ENABLE_NAUKRI` | Toggle Naukri scraping | `True` |
