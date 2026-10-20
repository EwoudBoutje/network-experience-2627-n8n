**Stap 2: download ProxmoxMCP-Plus op je Debian-VM.**

Voer achtereenvolgens uit:

```bash
sudo apt update
sudo apt install -y git openssl nano
```

Maak de projectmap en ga erin:

```bash
mkdir -p ~/Projects/proxmox-agent
cd ~/Projects/proxmox-agent
```

Download de broncode:

```bash
git clone https://github.com/RekklesNA/ProxmoxMCP-Plus.git source
```

Controleer of de Dockerfile aanwezig is:

```bash
ls source/Dockerfile
```

Verwachte uitvoer:

```text
source/Dockerfile
```

Blijf in **`~/Projects/proxmox-agent`**. Hier maken we straks `.env` en `compose.yaml`; je hoeft niet naar de map `source` te gaan.