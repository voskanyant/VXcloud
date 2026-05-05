#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/vxcloud-node-metrics"
ENV_FILE="/etc/vxnode-metrics-agent.env"
SERVICE_FILE="/etc/systemd/system/vxnode-metrics-agent.service"
SOURCE_AGENT="${1:-scripts/ops/vxnode_metrics_agent.py}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root on the VPN node."
  exit 1
fi

if [[ ! -f "$SOURCE_AGENT" ]]; then
  echo "Agent source not found: $SOURCE_AGENT"
  exit 1
fi

install -d -m 0755 "$INSTALL_DIR"
install -m 0755 "$SOURCE_AGENT" "$INSTALL_DIR/vxnode_metrics_agent.py"

if [[ ! -f "$ENV_FILE" ]]; then
  TOKEN="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 40)"
  cat > "$ENV_FILE" <<EOF
VXNODE_METRICS_BIND=0.0.0.0
VXNODE_METRICS_PORT=9109
VXNODE_METRICS_TOKEN=${TOKEN}
VXNODE_METRICS_DISK_PATH=/
VXNODE_METRICS_INTERFACE_PREFIXES=e,eth,en
EOF
  chmod 600 "$ENV_FILE"
fi

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=VXcloud node metrics agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/vxnode_metrics_agent.py
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now vxnode-metrics-agent
systemctl status vxnode-metrics-agent --no-pager

echo
echo "Token file: ${ENV_FILE}"
echo "Use this URL in /ops node edit: http://<node-public-ip>:9109/metrics"
echo "Firewall example: ufw allow from <main-server-ip> to any port 9109 proto tcp"
