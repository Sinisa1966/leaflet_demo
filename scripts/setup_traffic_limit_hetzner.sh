#!/bin/bash
# Ograniči outbound bandwidth da ne probijemo 20 TB/mesec (Hetzner: $1.20/TB preko toga).
# tc tbf ograničava BRZINU – teorijski max = rate × 30 dana.
# 40 Mbit/s × 30 dana ≈ 13 TB/mesec (7 TB rezerve ispod 20 TB).
#
# Pokretati na serveru: bash scripts/setup_traffic_limit_hetzner.sh
# Ukloniti: bash scripts/remove_traffic_limit_hetzner.sh

set -e
RATE="40mbit"      # ~13 TB/mesec max; smanji za veću rezervu
BURST="1mbit"
LATENCY="400ms"
# Hetzner: obično eth0; ako drugačije – IFACE=$(ip route | grep default | awk '{print $5}' | head -1)
IFACE="${IFACE:-eth0}"

echo "=== Traffic limit – postavljam ${RATE} na ${IFACE} (max ~13 TB/mesec) ==="

# Ukloni postojeći qdisc ako postoji
tc qdisc del dev "$IFACE" root 2>/dev/null || true

# Dodaj tbf (Token Bucket Filter)
tc qdisc add dev "$IFACE" root tbf rate "$RATE" burst "$BURST" latency "$LATENCY"

echo "  OK. Proveri: tc -s qdisc show dev $IFACE"
echo ""
echo "Traffic limit AKTIVAN. Za uklanjanje: tc qdisc del dev $IFACE root"
