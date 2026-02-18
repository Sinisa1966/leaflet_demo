#!/bin/bash
# Ukloni traffic limit sa eth0 (ili IFACE).
IFACE="${IFACE:-eth0}"
echo "Uklanjam traffic limit sa $IFACE..."
tc qdisc del dev "$IFACE" root 2>/dev/null && echo "  OK" || echo "  (nije bilo postavljeno)"
