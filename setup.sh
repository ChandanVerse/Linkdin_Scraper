#!/bin/bash
# AWS EC2 setup script for LinkedIn Job Scraper
# Run after SSH-ing into your instance: bash setup.sh

set -e

echo "=== Updating system ==="
sudo apt update && sudo apt upgrade -y

echo "=== Installing Python 3 and pip ==="
sudo apt install -y python3 python3-venv python3-pip

echo "=== Installing Chrome ==="
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb || sudo apt --fix-broken install -y
rm google-chrome-stable_current_amd64.deb
google-chrome --version

echo "=== Cloning project ==="
cd ~
git clone https://github.com/ChandanVerse/Linkdin_Scraper.git scraper
cd scraper

echo "=== Creating virtual environment ==="
python3 -m venv venv
source venv/bin/activate

echo "=== Installing dependencies ==="
pip install -r requirements.txt

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Create .env file:  nano ~/scraper/.env"
echo "     Add these lines:"
echo "       DISCORD_WEBHOOK_URL=your_webhook_url"
echo "       LINKEDIN_EMAIL=your_email"
echo "       LINKEDIN_PASSWORD=your_password"
echo ""
echo "  2. Start the service:  sudo bash ~/scraper/install_service.sh"
