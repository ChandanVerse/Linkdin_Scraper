#!/bin/bash
# AWS EC2 Ubuntu setup script for Job Scraper
set -e

echo "=== Job Scraper - AWS Setup ==="

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python, pip, venv
sudo apt install -y python3 python3-pip python3-venv

# Install Xvfb
sudo apt install -y xvfb

# Install Google Chrome
wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y /tmp/chrome.deb || sudo apt --fix-broken install -y
rm /tmp/chrome.deb

# Clone repo
REPO_DIR="$HOME/scraper"
if [ -d "$REPO_DIR" ]; then
    echo "Updating existing repo..."
    cd "$REPO_DIR" && git pull
else
    git clone https://github.com/ChandanVerse/Linkdin_Scraper.git "$REPO_DIR"
fi

# Create venv and install dependencies
cd "$REPO_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create .env from template if it doesn't exist
if [ ! -f "$REPO_DIR/.env" ]; then
    cat > "$REPO_DIR/.env" <<'ENVEOF'
DISCORD_WEBHOOK_URL=
LINKEDIN_EMAIL=
LINKEDIN_PASSWORD=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-south-1
ENVEOF
    echo "Created .env template at $REPO_DIR/.env"
fi

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env:  nano $REPO_DIR/.env"
echo "  2. Test run:    cd $REPO_DIR && source venv/bin/activate && python3 -u main.py --once"
echo "  3. Install service:  sudo bash $REPO_DIR/install_service.sh"
