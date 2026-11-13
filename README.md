# Network Experience 2026–2027 – n8n Automation

Dit project bevat verschillende automatiseringen die gebouwd zijn met **n8n**. De workflows maken gebruik van AI-agents, MCP-servers en externe diensten.

Het project bestaat uit een centrale n8n-installatie en verschillende afzonderlijke automatiseringen.

## Inhoud

- [Network Experience 2026–2027 – n8n Automation](#network-experience-20262027--n8n-automation)
  - [Inhoud](#inhoud)
  - [Projectoverzicht](#projectoverzicht)
  - [Projectstructuur](#projectstructuur)
  - [Benodigdheden](#benodigdheden)
  - [Installatie](#installatie)
    - [1. Docker installeren](#1-docker-installeren)
    - [2. Repository clonen](#2-repository-clonen)
    - [3. Environment variables configureren](#3-environment-variables-configureren)
    - [4. De centrale omgeving starten](#4-de-centrale-omgeving-starten)
  - [n8n starten](#n8n-starten)
  - [Workflows importeren](#workflows-importeren)
  - [Configuratie en IP-adressen](#configuratie-en-ip-adressen)
    - [Waar moet je dit aanpassen?](#waar-moet-je-dit-aanpassen)
  - [Credentials en beveiliging](#credentials-en-beveiliging)
  - [Documentatie per onderdeel](#documentatie-per-onderdeel)
    - [Minecraft Dashboard](#minecraft-dashboard)
    - [Trello](#trello)
    - [Proxmox Agent Dashboard](#proxmox-agent-dashboard)
    - [Proxmox MCP Workshop](#proxmox-mcp-workshop)
  - [Beheer](#beheer)
    - [Containers bekijken](#containers-bekijken)
    - [Logs bekijken](#logs-bekijken)
    - [Containers opnieuw starten](#containers-opnieuw-starten)
    - [Omgeving stoppen](#omgeving-stoppen)
  - [Back-ups](#back-ups)
  - [Bekende aandachtspunten](#bekende-aandachtspunten)

---

## Projectoverzicht

De centrale omgeving bestaat uit n8n, PostgreSQL, SearXNG en de AI Sandbox.

De verschillende workflows kunnen externe diensten aanspreken via MCP-servers.

| Onderdeel | Functie |
|---|---|
| n8n | Uitvoeren en beheren van workflows |
| PostgreSQL | Database voor n8n |
| SearXNG | Zoekmachine voor AI-agents |
| AI Sandbox | Afgeschermde omgeving voor bepaalde AI-acties |
| Minecraft MCP | Communicatie met de Minecraft-omgeving |
| Proxmox MCP | Communicatie met Proxmox |
| Trello MCP | Integratie met Trello |

## Projectstructuur

```text
network-experience-2627-n8n/
│
├── compose.yml
├── .env.example
├── .gitignore
├── README.md
├── opdracht.md
├── searxng-settings.yml
│
├── step1_n8n_installation
├── step2_instructions_mcp_client.md
│
├── minecraft-whitelist-schema.sql
│
├── Minecraft_dashboard/
│   ├── README.md
│   ├── Minecraft_Whitelist.json
│   └── minecraft-mcp/
│       ├── compose.yaml
│       ├── Dockerfile
│       └── server.py
│
├── Trello/
│   ├── README.md
│   └── workflow.json
│
├── Proxmox_agent_dashboard/
│   ├── README.md
│   └── workflow.json
│
└── workshop-proxmox-agent/
    ├── Stap1.md
    ├── Stap2.md
    ├── Stap3.md
    ├── Stap4.md
    ├── Stap5.md
    └── Stap6.md
```

## Benodigdheden

Voor de installatie heb je het volgende nodig:

- Een Debian 13 VM.
- Docker Engine.
- Docker Compose-plugin.
- Git.
- Een werkende netwerkverbinding.
- Een n8n-account.
- De nodige API-credentials voor de workflows die je wilt gebruiken.

De benodigde resources zijn afhankelijk van het aantal actieve workflows en de gebruikte AI-modellen.

## Installatie

### 1. Docker installeren

Werk Debian eerst bij:

```bash
sudo apt update
sudo apt upgrade -y
```

Installeer Docker volgens de officiële documentatie:

https://docs.docker.com/engine/install/debian/

Controleer de installatie:

```bash
docker --version
docker compose version
```

### 2. Repository clonen

```bash
git clone https://github.com/EwoudBoutje/network-experience-2627-n8n.git
cd network-experience-2627-n8n
```

### 3. Environment variables configureren

Maak een eigen `.env`-bestand op basis van het voorbeeld:

```bash
cp .env.example .env
nano .env
```

Vul de nodige waarden in.

**Belangrijk:**

- Gebruik eigen wachtwoorden, tokens en encryption keys.
- Deel je `.env`-bestand nooit via GitHub.
- Gebruik niet zomaar de voorbeeldwaarden voor een echte installatie.

### 4. De centrale omgeving starten

Start de Docker-containers:

```bash
docker compose up -d
```

Controleer de status:

```bash
docker compose ps
```

Bekijk indien nodig de logs:

```bash
docker compose logs -f
```

## n8n starten

Open n8n via:

```text
http://<IP-ADRES-VAN-DE-VM>:5678
```

Bij de eerste start moet je een owner-account aanmaken.

Daarna kan je workflows importeren en de nodige credentials configureren.

## Workflows importeren

De workflows worden als JSON-bestanden bijgehouden in deze repository.

Om een workflow te importeren:

1. Open n8n.
2. Ga naar **Overview** of **Workflows**.
3. Kies de optie om een workflow te importeren.
4. Selecteer het juiste JSON-bestand.
5. Controleer de configuratie van de nodes.
6. Stel de vereiste credentials in.
7. Test de workflow voordat je deze activeert.

De workflowbestanden zijn exports. Ze bevatten niet automatisch alle benodigde API-credentials, externe configuratie of actieve verbindingen.

Een geïmporteerde workflow moet dus eerst gecontroleerd en geconfigureerd worden.

## Configuratie en IP-adressen

Sommige workflows moeten verbinding maken met diensten op een ander systeem.

IP-adressen en URL's kunnen verschillen per installatie. Daarom zijn enkele adressen in de Minecraft-workflow vervangen door placeholders.

Vervang deze placeholders door de adressen van je eigen omgeving.

| Placeholder | Betekenis |
|---|---|
| `PTERODACTYL_HOST` | Hostname of IP-adres van de Pterodactyl-server |
| `N8N_HOST` | Hostname of IP-adres waarop n8n bereikbaar is |

### Waar moet je dit aanpassen?

Open na het importeren de workflow **Minecraft Whitelist**.

Zoek de betreffende HTTP Request- en URL-configuraties en vervang:

```text
http://PTERODACTYL_HOST
```

door bijvoorbeeld:

```text
http://192.168.1.100
```

Vervang ook:

```text
http://N8N_HOST:5678
```

door bijvoorbeeld:

```text
http://192.168.1.50:5678
```

Gebruik uiteraard de adressen van je eigen omgeving.

**Let op:** vervang alleen de hostname of het IP-adres. De bestaande `http://` en eventuele poort moeten behouden blijven.

Controleer daarnaast de MCP-endpoints. De standaard Minecraft MCP-configuratie gebruikt:

```text
http://minecraft-mcp:8000
```

De Proxmox MCP-configuratie gebruikt:

```text
http://proxmox-mcp:8000/mcp
```

Deze Docker-servicenamen werken alleen wanneer de betrokken containers op een gedeeld Docker-netwerk zitten.

## Credentials en beveiliging

De workflows kunnen verbinding maken met externe diensten zoals:

- OpenAI of een andere AI-provider.
- Trello.
- GitHub.
- Proxmox.
- Pterodactyl.

Configureer de benodigde credentials via **Credentials** in n8n.

Gebruik geen API-tokens, wachtwoorden of andere geheimen rechtstreeks in workflowbestanden.

De workflowbestanden in GitHub bevatten configuratie, maar je moet zelf de nodige credentials aanmaken en koppelen.

## Documentatie per onderdeel

Elk onderdeel heeft een eigen README met de specifieke installatie- en configuratiestappen.

### Minecraft Dashboard

[Minecraft Dashboard – README.md](Minecraft_dashboard/README.md)

Bevat onder andere:

- Importeren en configureren van de Minecraft-workflow.
- Installatie van de Minecraft MCP-server.
- Docker-configuratie.
- Configuratie van de Pterodactyl-verbinding.
- Minecraft Whitelist-database en SQL-schema.
- Testen van de workflow.

De SQL-configuratie staat in:

```text
minecraft-whitelist-schema.sql
```

Controleer vóór het uitvoeren van dit bestand of de juiste database en databasegebruiker bestaan.

De Minecraft MCP-server staat in:

```text
Minecraft_dashboard/minecraft-mcp/
```

De MCP-server moet bereikbaar zijn vanuit n8n. Zorg daarom dat beide containers op een gedeeld Docker-netwerk zitten.

### Trello

[Trello – README.md](Trello/README.md)

Bevat onder andere:

- Importeren van de Trello-workflow.
- Trello MCP-configuratie.
- Aanmaken van Trello-credentials.
- GitHub MCP-configuratie.
- Testen van de AI-agent.

De workflow gebruikt externe MCP-integraties. Controleer of deze servers beschikbaar zijn en of de juiste credentials gekoppeld zijn.

### Proxmox Agent Dashboard

[Proxmox Agent Dashboard – README.md](Proxmox_agent_dashboard/README.md)

Bevat onder andere:

- Importeren van de Proxmox-workflow.
- Installatie en configuratie van de Proxmox MCP-server.
- Docker-netwerkconfiguratie.
- Dashboard-webhook.
- Basic Authentication.
- Testen van de VM-informatie.

De Proxmox MCP-server moet bereikbaar zijn vanuit n8n. De standaardconfiguratie gebruikt het endpoint:

```text
http://proxmox-mcp:8000/mcp
```

### Proxmox MCP Workshop

De afzonderlijke workshopstappen vind je in:

[Workshop Proxmox Agent](workshop-proxmox-agent/)

Deze map bevat de installatie- en configuratiestappen van de Proxmox Agent.

## Beheer

### Containers bekijken

```bash
docker compose ps
```

### Logs bekijken

```bash
docker compose logs -f
```

### Containers opnieuw starten

```bash
docker compose restart
```

### Omgeving stoppen

```bash
docker compose down
```

Dit verwijdert de containers en het netwerk van deze Compose-stack, maar verwijdert normaal gezien niet de volumes.

**Gebruik geen `docker compose down -v` tenzij je bewust ook de volumes en opgeslagen gegevens wilt verwijderen.**

## Back-ups

Maak regelmatig een back-up van:

- De PostgreSQL-database.
- De `.env`-configuratie.
- De workflow-exports.
- De configuratiebestanden van de MCP-servers.

Bewaar back-ups op een veilige locatie en controleer of ze effectief teruggezet kunnen worden.

## Bekende aandachtspunten

- Een geïmporteerde workflow is niet automatisch klaar voor gebruik.
- Credentials moeten na het importeren opnieuw ingesteld of gekoppeld worden.
- IP-adressen en URL's moeten aangepast worden aan de eigen omgeving.
- De Minecraft MCP-server en n8n moeten op een gedeeld Docker-netwerk kunnen communiceren.
- De Proxmox MCP-server moet bereikbaar zijn vanuit n8n.
- De Trello- en Proxmox-workflows moeten eerst getest worden voordat ze geactiveerd worden.
- Een succesvolle Docker-start betekent niet automatisch dat alle workflows correct werken.
- Controleer na het importeren of alle gebruikte MCP-servers beschikbaar zijn.

---

**Repository:**

https://github.com/EwoudBoutje/network-experience-2627-n8n
