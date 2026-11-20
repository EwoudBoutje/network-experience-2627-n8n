#!/bin/bash
# Richt de Terraform-VM in als MCP-server "infra-tf" voor de n8n-agent.
# Uitvoeren als root, vanuit een kopie van de repository op de Terraform-VM:
#
#   sudo ./ansible-terraform-agent/terraform-vm/setup.sh
#
# Herhaalbaar: bestaande configuratie in /etc/infra-agent wordt niet overschreven.
# Na een git pull: opnieuw uitvoeren om module en server bij te werken.
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
MODULE_SRC="$(cd "$SRC_DIR/../terraform" && pwd)"
[ "$(id -u)" -eq 0 ] || { echo "Voer uit als root (sudo)." >&2; exit 1; }

echo "== Pakketten"
apt-get update -qq
apt-get install -y -qq python3 python3-venv ca-certificates curl gnupg >/dev/null
if ! command -v terraform >/dev/null; then
  codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"
  curl -fsI "https://apt.releases.hashicorp.com/dists/$codename/Release" >/dev/null || codename=bookworm
  curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor --yes -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $codename main" \
    > /etc/apt/sources.list.d/hashicorp.list
  apt-get update -qq
  apt-get install -y -qq terraform >/dev/null
fi
terraform version | head -n 1

echo "== Gebruiker tfrunner en mappen"
id tfrunner >/dev/null 2>&1 || useradd --system --home-dir /var/lib/infra-agent --create-home --shell /usr/sbin/nologin tfrunner
install -d -o tfrunner -g tfrunner -m 0750 /var/lib/infra-agent /var/lib/infra-agent/deployments \
  /var/lib/infra-agent/archive /var/lib/infra-agent/plugin-cache /var/log/infra-agent
install -d -o root -g tfrunner -m 0750 /etc/infra-agent

echo "== Python-omgeving"
[ -x /opt/infra-agent/venv/bin/python ] || python3 -m venv /opt/infra-agent/venv
/opt/infra-agent/venv/bin/pip install -q --upgrade pip
/opt/infra-agent/venv/bin/pip install -q "fastmcp>=2.12,<3"

echo "== Code (module + server)"
install -d -o root -g root -m 0755 /opt/infra-agent/bin
rm -rf /opt/infra-agent/module.new
install -d -o root -g root -m 0755 /opt/infra-agent/module.new
install -o root -g root -m 0644 "$MODULE_SRC"/*.tf /opt/infra-agent/module.new/
if [ -f "$MODULE_SRC/.terraform.lock.hcl" ]; then
  install -m 0644 "$MODULE_SRC/.terraform.lock.hcl" /opt/infra-agent/module.new/
fi
rm -rf /opt/infra-agent/module && mv /opt/infra-agent/module.new /opt/infra-agent/module
install -m 0644 "$SRC_DIR/infra_tf_mcp.py" /opt/infra-agent/bin/infra_tf_mcp.py
install -m 0644 "$SRC_DIR/infra-tf-mcp.service" /etc/systemd/system/infra-tf-mcp.service

echo "== Configuratie"
if [ ! -f /etc/infra-agent/config.env ]; then
  install -o root -g tfrunner -m 0640 "$SRC_DIR/config.env.example" /etc/infra-agent/config.env
  echo "   -> vul /etc/infra-agent/config.env in"
fi
if [ ! -f /etc/infra-agent/proxmox.env ]; then
  install -o root -g tfrunner -m 0640 "$SRC_DIR/proxmox.env.example" /etc/infra-agent/proxmox.env
  echo "   -> vul /etc/infra-agent/proxmox.env in"
fi
if [ ! -s /etc/infra-agent/admin_ssh_public_key ]; then
  install -o root -g tfrunner -m 0640 /dev/null /etc/infra-agent/admin_ssh_public_key
  echo "   -> zet de publieke sleutel van ansible-mcp (vm_ssh_key.pub) in /etc/infra-agent/admin_ssh_public_key"
fi

systemctl daemon-reload
systemctl enable infra-tf-mcp.service >/dev/null
if grep -q VUL_IN /etc/infra-agent/config.env /etc/infra-agent/proxmox.env || [ ! -s /etc/infra-agent/admin_ssh_public_key ]; then
  echo
  echo "Configuratie nog niet volledig: vul de bestanden in /etc/infra-agent in en start dan:"
  echo "  sudo systemctl restart infra-tf-mcp && sudo systemctl status infra-tf-mcp"
else
  systemctl restart infra-tf-mcp.service
  systemctl --no-pager --lines=5 status infra-tf-mcp.service || true
fi

echo
echo "Nog te doen (eenmalig):"
echo "  - Proxmox-CA vertrouwen: cp proxmox-ca.pem /usr/local/share/ca-certificates/proxmox-ca.crt && update-ca-certificates"
echo "  - Firewall: poort \${MCP_PORT:-8001}/tcp alleen toelaten vanaf het IP van de n8n-VM"
