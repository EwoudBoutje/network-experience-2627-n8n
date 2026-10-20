Het netwerk **`proxmox-tools` is aangemaakt**. Verbind nu n8n ermee:

```bash
sudo docker network connect proxmox-tools network-experience-2627-n8n-n8n-1
```

Geen uitvoer betekent doorgaans succes. Controleer met:

```bash
sudo docker network inspect proxmox-tools --format '{{range .Containers}}{{println .Name}}{{end}}'
```

Je moet dan zien:

```text
network-experience-2627-n8n-n8n-1
```

Ga daarna naar de aparte projectmap voor Proxmox-MCP:

```bash
mkdir -p ~/Projects/proxmox-agent
cd ~/Projects/proxmox-agent
```

Daar voer je **stap 2: ProxmoxMCP-Plus downloaden** uit.
