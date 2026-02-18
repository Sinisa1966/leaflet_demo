#!/bin/bash
# Instalira systemd servis da traffic limit preživi reboot.
# Pokretati kao root na serveru.
#
# bash scripts/install_traffic_limit_systemd.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="/etc/systemd/system/kopernikus-traffic-limit.service"

cat > "$SERVICE_FILE" << 'EOF'
[Unit]
Description=Kopernikus GIS – ograniči outbound na 40 Mbit/s (max ~13 TB/mesec)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c 'tc qdisc del dev eth0 root 2>/dev/null; tc qdisc add dev eth0 root tbf rate 40mbit burst 1mbit latency 400ms'
ExecStop=/bin/bash -c 'tc qdisc del dev eth0 root 2>/dev/null || true'

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable kopernikus-traffic-limit.service
systemctl start kopernikus-traffic-limit.service
echo "Servis instaliran i pokrenut. Proveri: systemctl status kopernikus-traffic-limit"
echo "Na reboot će se limit automatski primeniti."
