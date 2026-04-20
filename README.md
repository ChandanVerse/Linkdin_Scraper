# Job Scraper

A robust, parallel job scraping tool for LinkedIn, Naukri, and Internshala with instant Discord notifications.

## Features
- **Parallel Scraping**: Runs LinkedIn scraping and others (Naukri, Internshala) in parallel.
- **Discord Integration**: Sends notifications instantly when a new job is found.
- **Account Rotation**: Automatically rotates LinkedIn accounts to avoid rate limits.

## Setup
1. Install requirements: `pip install -r requirements.txt`
2. Configure `.env` with your Discord Webhook URL and LinkedIn credentials.
3. Run the application: `python main.py`
