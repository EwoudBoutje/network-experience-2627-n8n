**Nu plaatsen we het publieke Proxmox-CA-certificaat**, zodat de MCP-server de HTTPS-verbinding kan controleren.

**1. Maak op je Debian-VM de certificaatmap:**

```bash
cd ~/Projects/proxmox-agent
mkdir -p certs
```

**2. Open de shell van een Proxmox-node** via de Proxmox-webinterface en voer uit:

```bash
cat /etc/pve/pve-root-ca.pem
```

Kopieer het volledige certificaat, inclusief:

```text
-----BEGIN CERTIFICATE-----
...
-----END CERTIFICATE-----
```

Dit is het **publieke certificaat**; kopieer geen `.key`-bestand.

**3. Ga terug naar de Debian-terminal:**

```bash
nano certs/proxmox-ca.pem
```

Plak het certificaat en sla op met **Ctrl+O → Enter → Ctrl+X**.

**4. Controleer het bestand:**

```bash
openssl x509 -in certs/proxmox-ca.pem -noout -subject -issuer -dates
```

Als je certificaatgegevens ziet, is het bestand leesbaar.

Dit geldt voor het standaard Proxmox-clustercertificaat. Gebruikt jullie panel een certificaat van een andere interne CA, dan heb je het publieke CA-certificaat van die organisatie nodig. **De hostnaam in `.env` moet ook overeenkomen met het servercertificaat.**