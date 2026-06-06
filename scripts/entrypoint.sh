#!/bin/bash
set -euo pipefail

echo "=== piavpn startar ==="

mkdir -p /data/configs

if [ -z "$(ls /data/configs/*.ovpn 2>/dev/null || true)" ]; then
    echo "Hämtar PIA-configs (engångsnedladdning per volym)..."
    curl -fsSL "https://www.privateinternetaccess.com/openvpn/openvpn-strong.zip" -o /tmp/pia.zip
    unzip -oq /tmp/pia.zip "*.ovpn" -d /data/configs
    rm /tmp/pia.zip
    COUNT=$(ls /data/configs/*.ovpn | wc -l)
    echo "  $COUNT configs hämtade."
else
    COUNT=$(ls /data/configs/*.ovpn | wc -l)
    echo "  Configs hittade ($COUNT regioner)."
fi

printf '%s\n%s\n' "${PIA_USER}" "${PIA_PASS}" > /tmp/pia-auth.txt
chmod 600 /tmp/pia-auth.txt

bash /scripts/iptables.sh

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
