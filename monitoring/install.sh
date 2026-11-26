#!/usr/bin/env bash
# Ejecutar EN LA EC2:  cd ~/app && bash monitoring/install.sh
set -e
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
sudo apt-get update -y
sudo apt-get install -y python3-psutil
sudo tee /etc/systemd/system/infra-monitor.service >/dev/null <<UNIT
[Unit]
Description=Monitor de infraestructura -> OpenObserve
After=network-online.target docker.service

[Service]
User=$USER
EnvironmentFile=-$APP_DIR/.env
ExecStart=/usr/bin/python3 $APP_DIR/monitoring/infra_monitor.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now infra-monitor
sleep 3
systemctl --no-pager status infra-monitor | head -8
