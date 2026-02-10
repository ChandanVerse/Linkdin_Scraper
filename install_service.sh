#!/bin/bash
# Creates a systemd service to run the scraper 24/7
# Run with: sudo bash install_service.sh

USER=$(whoami)
if [ "$USER" = "root" ]; then
    USER="ubuntu"
fi

cat > /etc/systemd/system/linkedin-scraper.service << EOF
[Unit]
Description=LinkedIn Job Scraper
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/scraper
ExecStart=/home/$USER/scraper/venv/bin/python main.py
Restart=always
RestartSec=30
EnvironmentFile=/home/$USER/scraper/.env

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable linkedin-scraper
systemctl start linkedin-scraper

echo "Service installed and started!"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status linkedin-scraper   # Check status"
echo "  sudo journalctl -u linkedin-scraper -f    # View live logs"
echo "  sudo systemctl restart linkedin-scraper   # Restart"
echo "  sudo systemctl stop linkedin-scraper      # Stop"
