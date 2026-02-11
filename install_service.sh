#!/bin/bash
# Install systemd service for Job Scraper
set -e

REPO_DIR="$HOME/scraper"
USER=$(whoami)

echo "Creating systemd service..."

sudo tee /etc/systemd/system/job-scraper.service > /dev/null <<EOF
[Unit]
Description=Job Scraper (LinkedIn, Naukri, Indeed, Foundit, Internshala)
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$REPO_DIR
EnvironmentFile=$REPO_DIR/.env
ExecStart=$REPO_DIR/venv/bin/python3 -u main.py
Restart=always
RestartSec=30
Environment=DISPLAY=:99

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable job-scraper
sudo systemctl start job-scraper

echo ""
echo "=== Service installed and running! ==="
echo ""
echo "Commands:"
echo "  sudo systemctl status job-scraper       # Check status"
echo "  sudo journalctl -u job-scraper -f       # Live logs"
echo "  sudo systemctl restart job-scraper      # Restart"
echo "  sudo systemctl stop job-scraper         # Stop"
