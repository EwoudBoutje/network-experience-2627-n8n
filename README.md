# Network Experience 2627 - n8n

Deze repository bevat een n8n-automatiseringsomgeving en meerdere werkende of experimentele workflows voor:

- Minecraft-dashboard, whitelist en RCON/MCP;
- Proxmox-dashboard en beheerchat;
- Trello- en GitHub-tools;
- infrastructuurprovisioning met Terraform en Ansible;
- een centrale n8n-stack met PostgreSQL, SearXNG en een n8n-sandbox.

De repository is een projectomgeving, geen kant-en-klare productie-installatie. Controleer credentials, netwerken, databaseschema's en beveiligingsinstellingen voordat je een workflow gebruikt.

## Snelstart

### 1. Vereisten

Gebruik een Debian 12- of 13-VM met Docker Compose. Een VM is aanbevolen; een LXC-container is voor de n8n-sandbox niet geschikt.

Minimaal voor de centrale stack:

| Onderdeel | Advies |
|---|---:|
| CPU | 2 vCPU |
| RAM | 4 GB |
| Schijf | 32 GB |
| Netwerk | Gebruik een vast LAN-IP |

### 2. Installeer Docker

Op Debian:

```bash
sudo apt update
sudo apt install -y ca-certificates curl openssl
```

Volg vervolgens de officiële Docker-installatie voor Debian. Controleer de installatie:

```bash
sudo docker version
sudo docker compose version
```

### 3. Start de centrale stack

Vanaf de repositorymap:

```bash
cp .env.example .env
nano .env
```

Vervang alle voorbeeldwaarden door sterke, eigen geheimen. Maak bijvoorbeeld:

```bash
openssl rand -hex 32
```

Start daarna:

```bash
sudo docker compose config
sudo docker compose up -d
sudo docker compose ps
```

Let op:

- `.env` bevat echte geheimen en moet **niet** in Git worden geplaatst.
- Bewaar `N8N_ENCRYPTION_KEY` apart. Zonder dezelfde sleutel kun je opgeslagen n8n-credentials niet herstellen.
- In de huidige [compose.yml](compose.yml) is n8n alleen gebonden aan `127.0.0.1:5679`. Gebruik voor toegang een SSH-tunnel of pas de poort en bind-adres bewust aan.
- Gebruik `docker compose down -v` niet: hiermee worden ook de n8n- en databasevolumes verwijderd.

Voor een SSH-tunnel:

```bash
ssh -L 5679:127.0.0.1:5679 <gebruiker>@<VM-IP>
```

Open daarna op je laptop:

```text
http://localhost:5679
```

## Centrale configuratie

### Services

| Service | Doel |
|---|---|
| `n8n` | Workfloweditor en uitvoeringsengine |
| `postgres` | PostgreSQL-database voor n8n |
| `runners` | Externe taakuitvoering voor Code-nodes |
| `searxng` | Zoekservice voor workflows en AI |
| `sandbox-certs` | Maakt eenmalig sandboxcertificaten aan |
| `sandbox-api` | API voor de n8n-sandbox |
| `sandbox-runner-1` | Voert sandboxtaken uit met Docker-in-Docker |

Het bestand [.env.example](.env.example) bevat de basisvariabelen voor database, n8n, runners en SearXNG. De sandboxvariabelen die worden verwacht door [compose.yml](compose.yml), zoals de sandbox API- en runner-tokens, moeten ook expliciet worden gecontroleerd en ingevuld voordat de volledige stack wordt gebruikt.

### Handige commando's

```bash
# Status en logs
sudo docker compose ps
sudo docker compose logs -f
sudo docker compose logs -f n8n

# Starten, stoppen en wijzigingen toepassen
sudo docker compose up -d
sudo docker compose stop
sudo docker compose down

# Alleen containers en images bijwerken
sudo docker compose pull
sudo docker compose up -d
```

## Workflows in deze repository

Workflows staan als JSON-export in `n8n-workflows/` en worden ook per onderwerp gedocumenteerd.

| Onderdeel | Locatie | Status / gebruik |
|---|---|---|
| Minecraft-dashboard en whitelist | [Minecraft_dashboard/README.md](Minecraft_dashboard/README.md) | MCP/RCON-, Pterodactyl-, dashboard- en whitelistworkflow |
| Minecraft MCP-server | [Minecraft_dashboard/minecraft-mcp/compose.yaml](Minecraft_dashboard/minecraft-mcp/compose.yaml) | Lokale MCP-server voor Minecraft-consolecommando's |
| Proxmox-agent en dashboard | [Proxmox_agent_dashboard/README.md](Proxmox_agent_dashboard/README.md) | Proxmox-chatagent en VM-dashboard |
| Live Proxmox-dashboard | [Proxmox_agent_dashboard/proxmox-dashboard-live/README.md](Proxmox_agent_dashboard/proxmox-dashboard-live/README.md) | JWT-, live-data- en dashboardvariant |
| Trello en GitHub | [Trello/README.md](Trello/README.md) | Chatagent met MCP-registrytools |
| Terraform en Ansible | [ansible-terraform-agent/README.md](ansible-terraform-agent/README.md) | Proefopzet voor VM-provisioning en menselijke goedkeuring |
| Geavanceerde workshop | [workshop-proxmox-agent/Stap1.md](workshop-proxmox-agent/Stap1.md) | Stapsgewijze installatie van ProxmoxMCP-Plus |
| Templates | [templates/README.md](templates/README.md) | Nog niet geïmplementeerde voorbeelden |

De volledige JSON-exports staan onder [n8n-workflows/](n8n-workflows/).

### Een workflow toevoegen

1. Open n8n.
2. Kies **Import from File**.
3. Selecteer het gewenste JSON-bestand.
4. Controleer alle nodes en vervang credentialverwijzingen door eigen credentials.
5. Vul hosts, API-URL's, databasegegevens en toegestane tools aan.
6. Test eerst in een testomgeving.
7. Controleer foutpaden en activeer/publiceer pas daarna.

Exporteer workflows zonder productiesecrets. Credential-ID's kunnen in een export blijven staan, maar de geheime waarden horen daar niet in.

## Belangrijke bestanden

| Bestand/map | Beschrijving |
|---|---|
| [compose.yml](compose.yml) | Centrale Docker Compose-stack |
| [.env.example](.env.example) | Voorbeeld van centrale omgevingsvariabelen |
| [searxng-settings.yml](searxng-settings.yml) | HTML- en JSON-instellingen voor SearXNG |
| [minecraft-whitelist-schema.sql](minecraft-whitelist-schema.sql) | PostgreSQL-schema voor de Minecraft-whitelist |
| [opdracht.md](opdracht.md) | Projectopdracht, eisen en acceptatietests |
| [n8n-workflows/](n8n-workflows/) | Workflowexports per onderwerp |
| [step1_n8n_installation](step1_n8n_installation) | Oudere, eenvoudige basisinstallatie van n8n |
| [step2_instructions_mcp_client.md](step2_instructions_mcp_client.md) | Voorbeeld voor n8n en Minecraft-MCP |

## Database en Minecraft

Het bestand [minecraft-whitelist-schema.sql](minecraft-whitelist-schema.sql) maakt het basisschema in de PostgreSQL-database. Controleer eerst databasegebruikers, rollen en doeldatabase.

Het huidige schema en bepaalde Minecraft-workflowexports zijn niet volledig gelijk aan elkaar. De echte wijzigingen in `invites`, `registrations` en de portal moeten daarom eerst in een testdatabase worden vergeleken. Controleer daarnaast altijd:

- PostgreSQL-schema-eigenaar;
- ingevulde `search_path`;
- toegangsrechten voor n8n;
- toevoeging van `pgcrypto` wanneer `gen_random_bytes` of `digest` wordt gebruikt;
- uitschakeling van destructieve testnodes;
- geen echte registraties verwijderen tijdens tests.

## Beveiliging

### Basisregels

- Gebruik HTTPS/reverse proxy voor n8n buiten een vertrouwd lokaal netwerk.
- Stel geen beheerpoorten publiek open.
- Gebruik verschillende accounts voor beheer en uitvoering.
- Bewaar API-, RCON-, database- en MCP-geheimen buiten Git.
- Geef API-tokens alleen leesrechten die nodig zijn.
- Gebruik menselijke goedkeuring voor acties met impact.
- Voer destructieve acties alleen uit op een goedgekeurde testomgeving.
- Test dubbele gebeurtenissen en controleer idempotentie.
- Beperk retries en stel een time-out in op externe HTTP- en MCP-aanroepen.
- Log geen persoonsgegevens, credentials of volledige tokens.

### MCP en externe systemen

Een MCP-tool of AI-resultaat is geen bevestiging dat een externe actie geslaagd is. Controleer serverresponsen en registreer:

- wie de actie heeft gevraagd;
- welke workflow en tool zijn uitgevoerd;
- welke doelidentiteit of VM is geraakt;
- of de actie definitief geslaagd, mislukt of onzeker is.

MCP-tools die RCON of Proxmox kunnen wijzigen, mogen alleen in een vertrouwde omgeving worden aangeboden.

## Back-up

Een minimale back-up bevat:

- PostgreSQL-database;
- n8n-workflowexports zonder credentials;
- `N8N_ENCRYPTION_KEY`;
- MCP-, API- en databaseconfiguratie zonder geheime waarden;
- een herstelprocedure.

Maak een PostgreSQL-back-up:

```bash
sudo docker compose exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > "backup-$(date +%F).sql"
```

Test herstel altijd in een aparte database of instantie. Gebruik bij een restore dezelfde `N8N_ENCRYPTION_KEY` als op het moment van de back-up.

## Problemen oplossen

| Probleem | Controle |
|---|---|
| n8n is niet bereikbaar op poort 5678 | De huidige stack bindt op loopbackpoort 5679: `127.0.0.1:5679`; controleer met `docker compose ps` |
| Secure-cookie waarschuwing | Gebruik HTTPS of een SSH-tunnel naar localhost |
| PostgreSQL is niet healthy | Controleer `.env`, Docker-volumes en `docker compose logs postgres` |
| Sandbox start niet | Controleer alle sandbox-variabelen, de n8n-sandboxversie en logs van `sandbox-certs` en `sandbox-api` |
| Docker kan de sandbox niet starten | Controleer of Docker op een VM draait en niet in een beperkte LXC-container |
| MCP-tool geeft 401 | Controleer het Bearer-token, de MCP-credential en de MCP-serverconfiguratie |
| MCP-service is niet bereikbaar | Controleer Docker-netwerk, servicenaam, poort en containerlogs |
| Restore toont ongebruikte credentials | Gebruik dezelfde `N8N_ENCRYPTION_KEY` als in de oorspronkelijke installatie |
| Gegevens verdwijnen na restart | Gebruik geen `down -v`; controleer of de Docker-volumes bestaan |

## Voor productie gereed

Een installatie is pas klaar wanneer de volgende punten aantoonbaar zijn:

- [ ] n8n is afgeschermd en gebruikt HTTPS;
- [ ] PostgreSQL is ondersteund en geback-upt;
- [ ] de encryptiesleutel staat veilig in een vault;
- [ ] beheer- en uitvoeringsgebruikers zijn gescheiden;
- [ ] credentials staan niet in Git;
- [ ] workflows hebben begrensde retries en foutafhandeling;
- [ ] destructieve acties vragen menselijke goedkeuring;
- [ ] workflowexports zijn schoon en bijgehouden;
- [ ] een database- en configuratierecovery is getest;
- [ ] logs, monitoring en runbooks zijn ingericht.
